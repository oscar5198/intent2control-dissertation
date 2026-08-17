"""Phase 6E.4 deterministic prediction failure-handling state machine."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from llm_experiments.inference.adapters.mock import MockAdapter
from llm_experiments.inference.configuration import PRIMARY_INFERENCE_CONFIG_VERSION, production_preflight
from llm_experiments.inference.failures import FAILURE_HANDLING_VERSION, classify_failure, should_repair
from llm_experiments.inference.records import (
    JsonlAttemptLogger,
    create_run_manifest,
    finalize_prediction_record,
    make_attempt_record,
    make_prediction_record_id,
    read_jsonl,
    write_execution_summary,
    write_json_atomic,
    write_jsonl,
    write_predictions,
    iso_now,
)
from llm_experiments.inference.registry import load_backend_registry, load_model_registry, resolve_backend, resolve_model
from llm_experiments.inference.requests import make_inference_request, make_inference_request_id
from llm_experiments.inference.responses import make_raw_result
from llm_experiments.inference.retry import default_failure_policy, policy_summary, should_retry_transport
from llm_experiments.inference.validation import validate_response_text
from llm_experiments.prompts.render import render_format_repair
from llm_experiments.prompts.prompt_spec import load_jsonl


TERMINAL_STATES = {"valid_primary", "valid_after_repair", "invalid_after_repair", "backend_failed"}
NON_TERMINAL_STATES = {"pending", "primary_in_progress", "repair_pending", "repair_in_progress", "backend_retry_pending", "not_run"}

VALID_RESPONSE = json.dumps(
    {
        "predicted_preferred_mix": "C",
        "predicted_ratings": {"A": 60, "B": 45, "C": 80, "D": 70, "E": 55},
        "predicted_ranking": ["C", "D", "A", "E", "B"],
    },
    sort_keys=True,
)


def next_prediction_state(attempts: list[dict[str, Any]], policy: dict[str, Any]) -> str:
    if not attempts:
        return "pending"
    prediction = finalize_prediction_record(attempts)
    if prediction["final_status"] in TERMINAL_STATES:
        return prediction["final_status"]
    primary = [row for row in attempts if row["attempt_type"] == "primary"]
    repairs = [row for row in attempts if row["attempt_type"] == "format_repair"]
    latest = sorted(attempts, key=lambda row: (row["attempt_number"], row.get("transport_attempt_number", 1)))[-1]
    if primary and should_repair(primary[-1]["response_validation_status"], primary[-1]["request_status"], primary[-1]["raw_response_text"]) and not repairs:
        return "repair_pending"
    if latest.get("retryable") and latest.get("attempt_type") == "primary" and latest.get("transport_attempt_number", 1) <= policy["max_transport_retries"]:
        return "backend_retry_pending"
    return prediction["final_status"]


def execute_primary_with_transport_retry(
    request: dict[str, Any],
    adapter: MockAdapter,
    response_schema: dict[str, Any],
    policy: dict[str, Any],
    logger: JsonlAttemptLogger,
    run_id: str,
    model_identity: dict[str, Any],
    backend_provenance: dict[str, Any],
    request_parameters: dict[str, Any],
    existing_attempts: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    attempts = list(existing_attempts or [])
    if any(row["attempt_type"] == "primary" and row["response_validation_status"] in {"valid", "invalid_json", "schema_invalid"} for row in attempts):
        return attempts
    parent_id = request["inference_request_id"]
    start_transport = max([row.get("transport_attempt_number", 0) for row in attempts if row.get("parent_inference_request_id") == parent_id] or [0]) + 1
    for transport_number in range(start_transport, policy["max_transport_retries"] + 2):
        transport_request = with_transport_metadata(request, parent_id, parent_id, transport_number)
        attempt = invoke_and_log(transport_request, adapter, response_schema, logger, run_id, model_identity, backend_provenance, request_parameters)
        attempts.append(attempt)
        failure = classify_failure({"status": attempt["request_status"], "error": {"type": attempt["failure_code"], "http_status_code": attempt.get("http_status_code")}}, {"status": attempt["response_validation_status"]})
        if attempt["response_validation_status"] in {"valid", "invalid_json", "schema_invalid"}:
            return attempts
        if not should_retry_transport(failure["failure_code"], transport_number, policy):
            return attempts
    return attempts


def execute_format_repair(
    primary_request: dict[str, Any],
    adapter: MockAdapter,
    response_schema: dict[str, Any],
    policy: dict[str, Any],
    logger: JsonlAttemptLogger,
    run_id: str,
    model_identity: dict[str, Any],
    backend_provenance: dict[str, Any],
    request_parameters: dict[str, Any],
    attempts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if int(policy.get("max_format_repair_generations", 1)) < 1:
        return attempts
    if any(row["attempt_type"] == "format_repair" for row in attempts):
        return attempts
    primary = latest_primary_generation(attempts)
    if not primary or not should_repair(primary["response_validation_status"], primary["request_status"], primary["raw_response_text"]):
        return attempts
    repair_prompt = render_format_repair(primary["raw_response_text"], response_schema)
    repair_request = {
        **primary_request,
        "inference_request_id": make_inference_request_id(
            primary_request["rendered_prompt_id"],
            primary_request["model_key"],
            primary_request["inference_config_id"],
            "format_repair",
            2,
        ),
        "parent_inference_request_id": primary_request["inference_request_id"],
        "scientific_generation_id": make_inference_request_id(
            primary_request["rendered_prompt_id"],
            primary_request["model_key"],
            primary_request["inference_config_id"],
            "format_repair",
            2,
        ),
        "attempt_type": "format_repair",
        "attempt_number": 2,
        "transport_attempt_number": 1,
        "failure_handling_version": FAILURE_HANDLING_VERSION,
        "messages": repair_prompt["messages"],
    }
    repair_attempt = invoke_and_log(repair_request, adapter, response_schema, logger, run_id, model_identity, backend_provenance, request_parameters)
    attempts.append(repair_attempt)
    return attempts


def resume_prediction(
    request: dict[str, Any],
    adapter: MockAdapter,
    response_schema: dict[str, Any],
    policy: dict[str, Any],
    logger: JsonlAttemptLogger,
    run_id: str,
    model_identity: dict[str, Any],
    backend_provenance: dict[str, Any],
    request_parameters: dict[str, Any],
) -> dict[str, Any]:
    prediction_id = make_prediction_record_id(request["prediction_example_id"], request["condition"], request["model_key"], request["inference_config_id"])
    attempts = [row for row in read_jsonl(logger.path) if row["prediction_record_id"] == prediction_id]
    if attempts and finalize_prediction_record(attempts)["final_status"] in TERMINAL_STATES:
        return finalize_prediction_record(attempts)
    attempts = execute_primary_with_transport_retry(request, adapter, response_schema, policy, logger, run_id, model_identity, backend_provenance, request_parameters, attempts)
    attempts = execute_format_repair(request, adapter, response_schema, policy, logger, run_id, model_identity, backend_provenance, request_parameters, attempts)
    return finalize_prediction_record(attempts)


def finalize_terminal_prediction(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    return finalize_prediction_record(attempts)


def run_synthetic_failure_matrix(
    repo_root: Path,
    run_id: str = "phase6e4_synthetic_failure_matrix",
    output_root: Path = Path("llm-experiments/outputs/synthetic/phase6e4"),
) -> dict[str, Any]:
    policy = default_failure_policy(repo_root)
    rendered_prompts_path = Path("llm-experiments/outputs/synthetic/phase6d2_rendered_prompts/rendered_prompts.jsonl")
    response_schema_path = Path("llm-experiments/schema/preference_prediction_response_v1.json")
    model_registry_path = Path("llm-experiments/config/phase6e1_model_registry.json")
    backend_registry_path = Path("llm-experiments/config/phase6e1_backend_registry.json")
    rendered_prompts = load_jsonl(repo_root / rendered_prompts_path)
    response_schema = json.loads((repo_root / response_schema_path).read_text(encoding="utf-8"))
    model_registry = load_model_registry(repo_root / model_registry_path)
    backend_registry = load_backend_registry(repo_root / backend_registry_path)
    run_dir = repo_root / output_root / run_id
    reset_run_dir(run_dir)
    cases = failure_matrix_cases()
    manifest = create_run_manifest(
        run_id=run_id,
        run_type="synthetic_mock",
        rendered_prompt_dataset_path=repo_root / rendered_prompts_path,
        rendered_prompt_count=len(cases),
        model_keys=sorted({case["model_key"] for case in cases}),
        expected_request_count=len(cases),
        inference_config_version=PRIMARY_INFERENCE_CONFIG_VERSION,
        environment_summary={"backend": "mock", "real_model_calls": False, **policy_summary(policy)},
    )
    manifest["failure_handling_version"] = FAILURE_HANDLING_VERSION
    write_json_atomic(run_dir / "run_manifest.json", manifest)
    logger = JsonlAttemptLogger(run_dir, resume=True)
    audit_rows = []
    predictions = []
    for index, case in enumerate(cases):
        rendered = rendered_prompts[index % len(rendered_prompts)]
        model_spec = {**resolve_model(case["model_key"], model_registry), "default_backend_key": "mock", "inference_config_version": PRIMARY_INFERENCE_CONFIG_VERSION}
        request = make_inference_request(rendered, model_spec, inference_config_version=PRIMARY_INFERENCE_CONFIG_VERSION)
        request["failure_handling_version"] = FAILURE_HANDLING_VERSION
        adapter = MockAdapter({**resolve_backend("mock", backend_registry), "mock_sequence": case["sequence"], "mock_repair_mode": case.get("repair_mode")})
        prediction = resume_prediction(
            request,
            adapter,
            response_schema,
            policy,
            logger,
            run_id,
            {"exact_model_id": f"mock::{case['model_key']}", "checkpoint_or_revision": "mock_v1"},
            {"deployment_environment": case["backend_environment"], "serving_mode": "deterministic_failure_matrix"},
            request_parameters(),
        )
        predictions.append(prediction)
        case_attempts = [row for row in read_jsonl(logger.path) if row["prediction_record_id"] == prediction["prediction_record_id"]]
        audit_rows.append(state_audit_row(case, case_attempts, prediction, policy))
    attempts = read_jsonl(logger.path)
    predictions = write_predictions(run_dir, attempts)
    summary = write_execution_summary(run_dir, manifest, attempts, predictions)
    write_jsonl(run_dir / "state_transition_audit.jsonl", audit_rows)
    manifest["ended_at"] = iso_now()
    manifest["completed_count"] = summary["predictions_attempted"]
    manifest["valid_count"] = summary["valid_primary"] + summary["valid_after_repair"]
    manifest["invalid_count"] = summary["invalid"]
    manifest["failed_count"] = summary["backend_failures"]
    write_json_atomic(run_dir / "run_manifest.json", manifest)
    return summary


def production_failure_handler_preflight(repo_root: Path) -> dict[str, Any]:
    preflight = production_preflight(repo_root)
    return {
        "failure_handling_version": FAILURE_HANDLING_VERSION,
        "production_inference_allowed": bool(preflight.get("production_inference_allowed")),
        "blocked_by_preflight": not bool(preflight.get("production_inference_allowed")),
        "preflight": preflight,
    }


def invoke_and_log(
    request: dict[str, Any],
    adapter: MockAdapter,
    response_schema: dict[str, Any],
    logger: JsonlAttemptLogger,
    run_id: str,
    model_identity: dict[str, Any],
    backend_provenance: dict[str, Any],
    request_parameters: dict[str, Any],
) -> dict[str, Any]:
    provider = adapter.invoke({"messages": request["messages"], **request})
    extraction_error = None
    try:
        raw_text = adapter.extract_raw_response(provider)
    except Exception as exc:
        extraction_error = exc
        raw_text = None
    validation = validate_response_text(raw_text, response_schema)
    failure = classify_failure(provider, validation, extraction_error)
    error = provider.get("error") or ({"type": failure["failure_code"]} if failure["failure_code"] else None)
    request_status = provider.get("status", "completed")
    raw_result = make_raw_result(
        request,
        backend_type=adapter.backend_type,
        request_status=request_status,
        raw_response_text=raw_text,
        provider_response_metadata=provider.get("metadata"),
        usage=adapter.extract_usage(provider),
        latency={"total_seconds": 0.0, "source": "local_mock"},
        error=error,
    )
    attempt = make_attempt_record(request, raw_result, validation, model_identity, backend_provenance, request_parameters, run_id=run_id)
    if failure.get("http_status_code") is not None:
        attempt["http_status_code"] = failure["http_status_code"]
    logger.log_attempt(attempt)
    return attempt


def with_transport_metadata(request: dict[str, Any], parent_id: str, scientific_generation_id: str, transport_number: int) -> dict[str, Any]:
    request_id = parent_id if transport_number == 1 else f"{parent_id}__transport_{transport_number}"
    return {
        **request,
        "inference_request_id": request_id,
        "parent_inference_request_id": parent_id,
        "scientific_generation_id": scientific_generation_id,
        "transport_attempt_number": transport_number,
        "transport_retry_of": None if transport_number == 1 else parent_id,
        "failure_handling_version": FAILURE_HANDLING_VERSION,
    }


def latest_primary_generation(attempts: list[dict[str, Any]]) -> dict[str, Any] | None:
    primary = [row for row in attempts if row["attempt_type"] == "primary"]
    if not primary:
        return None
    return sorted(primary, key=lambda row: row.get("transport_attempt_number", 1))[-1]


def request_parameters() -> dict[str, Any]:
    return {
        "temperature_requested": 0,
        "top_p_requested": None,
        "seed_requested": 20260814,
        "max_output_tokens": 256,
        "structured_output_strategy": "local_schema_validation",
        "parameter_snapshot": {"failure_handling_version": FAILURE_HANDLING_VERSION},
    }


def failure_matrix_cases() -> list[dict[str, Any]]:
    return [
        {"case_id": "primary_valid", "model_key": "gpt", "backend_environment": "QMUL mock", "sequence": ["valid_response"], "expected_final_state": "valid_primary"},
        {"case_id": "invalid_json_repair_valid", "model_key": "gpt", "backend_environment": "QMUL mock", "sequence": ["invalid_json"], "repair_mode": "valid_response", "expected_final_state": "valid_after_repair"},
        {"case_id": "invalid_json_repair_invalid", "model_key": "gpt", "backend_environment": "QMUL mock", "sequence": ["invalid_json"], "repair_mode": "invalid_json", "expected_final_state": "invalid_after_repair"},
        {"case_id": "schema_invalid_repair_valid", "model_key": "claude_sonnet", "backend_environment": "QMUL mock", "sequence": ["schema_invalid"], "repair_mode": "valid_response", "expected_final_state": "valid_after_repair"},
        {"case_id": "timeout_retry_success", "model_key": "llama_3_1_70b_instruct", "backend_environment": "QMUL mock", "sequence": ["timeout", "valid_response"], "expected_final_state": "valid_primary"},
        {"case_id": "timeout_retry_exhausted", "model_key": "llama_3_1_70b_instruct", "backend_environment": "QMUL mock", "sequence": ["timeout", "timeout", "timeout"], "expected_final_state": "backend_failed"},
        {"case_id": "http_500_retry_success", "model_key": "gpt", "backend_environment": "QMUL mock", "sequence": ["http_500", "valid_response"], "expected_final_state": "valid_primary"},
        {"case_id": "rate_limit_retry_success", "model_key": "claude_sonnet", "backend_environment": "QMUL mock", "sequence": ["rate_limited", "valid_response"], "expected_final_state": "valid_primary"},
        {"case_id": "http_400_no_retry", "model_key": "gpt", "backend_environment": "QMUL mock", "sequence": ["http_400"], "expected_final_state": "backend_failed"},
        {"case_id": "empty_response_retry_success", "model_key": "centaur", "backend_environment": "RunPod mock", "sequence": ["empty_response", "valid_response"], "expected_final_state": "valid_primary"},
        {"case_id": "connection_error_exhausted", "model_key": "centaur", "backend_environment": "RunPod mock", "sequence": ["connection_error", "connection_error", "connection_error"], "expected_final_state": "backend_failed"},
        {"case_id": "auth_failure_no_retry", "model_key": "centaur", "backend_environment": "RunPod mock", "sequence": ["auth_failure"], "expected_final_state": "backend_failed"},
    ]


def state_audit_row(case: dict[str, Any], attempts: list[dict[str, Any]], prediction: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "phase6e4_state_transition_audit_v1",
        "failure_handling_version": FAILURE_HANDLING_VERSION,
        "case_id": case["case_id"],
        "initial_state": "pending",
        "attempt_ids": [row["inference_request_id"] for row in attempts],
        "attempt_statuses": [row["attempt_status"] for row in attempts],
        "failure_codes": [row["failure_code"] for row in attempts],
        "transport_retry_count": sum(1 for row in attempts if row.get("transport_attempt_number", 1) > 1),
        "repair_attempted": any(row["attempt_type"] == "format_repair" for row in attempts),
        "repair_decision": "repair_attempted" if any(row["attempt_type"] == "format_repair" for row in attempts) else "no_repair",
        "scientific_generation_count": prediction["scientific_generation_count"],
        "forbidden_extra_generation": prediction["format_repair_attempt_count"] > policy["max_format_repair_generations"],
        "final_state": prediction["final_status"],
        "expected_final_state": case["expected_final_state"],
        "passed": prediction["final_status"] == case["expected_final_state"] and prediction["format_repair_attempt_count"] <= policy["max_format_repair_generations"],
    }


def reset_run_dir(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    for filename in ["attempt_log.jsonl", "predictions.jsonl", "execution_summary.json", "run_manifest.json", "state_transition_audit.jsonl"]:
        path = run_dir / filename
        if path.exists():
            path.unlink()
