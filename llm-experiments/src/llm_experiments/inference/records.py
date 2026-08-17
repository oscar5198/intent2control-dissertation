"""Phase 6E.3 prediction logging and provenance records."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_experiments.inference.adapters.mock import MockAdapter
from llm_experiments.inference.configuration import PRIMARY_INFERENCE_CONFIG_VERSION
from llm_experiments.inference.failures import FAILURE_HANDLING_VERSION, classify_failure
from llm_experiments.inference.registry import load_backend_registry, load_model_registry, resolve_backend, resolve_model
from llm_experiments.inference.requests import INFERENCE_INTERFACE_VERSION, canonical_json, make_inference_request
from llm_experiments.inference.responses import make_raw_result
from llm_experiments.inference.validation import validate_response_text
from llm_experiments.prompts.prompt_spec import load_jsonl, write_json


PREDICTION_LOGGING_VERSION = "phase6e_prediction_logging_v1"
ATTEMPT_SCHEMA_VERSION = "phase6e_attempt_log_v1"
PREDICTION_SCHEMA_VERSION = "phase6e_prediction_record_v1"
RUN_MANIFEST_SCHEMA_VERSION = "phase6e_run_manifest_v1"
EXECUTION_SUMMARY_SCHEMA_VERSION = "phase6e_execution_summary_v1"

FINAL_STATUSES = {
    "pending",
    "primary_in_progress",
    "valid_primary",
    "repair_pending",
    "repair_in_progress",
    "valid_after_repair",
    "invalid_after_repair",
    "backend_retry_pending",
    "backend_failed",
    "not_run",
    "blocked_by_preflight",
}

SECRET_KEY_MARKERS = ["api_key", "authorization", "password", "secret", "access_token", "refresh_token"]
SECRET_VALUE_MARKERS = ["bearer ", "sk-"]


def make_prediction_record_id(
    prediction_example_id: str,
    condition: str,
    model_key: str,
    inference_config_version: str,
) -> str:
    stable = "::".join([prediction_example_id, condition, model_key, inference_config_version])
    return f"phase6e_pred_{hashlib.sha256(stable.encode('utf-8')).hexdigest()[:32]}"


def hash_prompt_payload(messages: list[dict[str, str]]) -> str:
    return sha256_json({"messages": messages})


def hash_inference_config(config: dict[str, Any]) -> str:
    scientific_keys = [
        "model_key",
        "exact_model_id",
        "checkpoint_or_revision",
        "inference_config_version",
        "prompt_package_version",
        "response_schema_version",
        "temperature_requested",
        "top_p_requested",
        "seed_requested",
        "max_output_tokens",
        "structured_output_strategy",
    ]
    return sha256_json({key: config.get(key) for key in scientific_keys})


def create_run_manifest(
    run_id: str,
    run_type: str,
    rendered_prompt_dataset_path: Path,
    rendered_prompt_count: int,
    model_keys: list[str],
    expected_request_count: int,
    prompt_package_version: str = "phase6d_prompt_package_v1",
    inference_config_version: str = PRIMARY_INFERENCE_CONFIG_VERSION,
    environment_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rendered_prompt_dataset_display_path = portable_artifact_path(rendered_prompt_dataset_path)
    return {
        "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
        "prediction_logging_version": PREDICTION_LOGGING_VERSION,
        "run_id": run_id,
        "run_type": run_type,
        "inference_interface_version": INFERENCE_INTERFACE_VERSION,
        "prompt_package_version": prompt_package_version,
        "inference_config_version": inference_config_version,
        "model_set": model_keys,
        "rendered_prompt_dataset": {
            "path": rendered_prompt_dataset_display_path,
            "sha256": sha256_file(rendered_prompt_dataset_path),
            "rendered_prompt_count": rendered_prompt_count,
            "prompt_package_version": prompt_package_version,
        },
        "started_at": iso_now(),
        "ended_at": None,
        "expected_request_count": expected_request_count,
        "completed_count": 0,
        "valid_count": 0,
        "invalid_count": 0,
        "failed_count": 0,
        "environment_summary": sanitize_provider_metadata(environment_summary or {}),
    }


def make_attempt_record(
    request: dict[str, Any],
    raw_result: dict[str, Any],
    validation: dict[str, Any],
    model_identity: dict[str, Any] | None = None,
    backend_provenance: dict[str, Any] | None = None,
    request_parameters: dict[str, Any] | None = None,
    run_id: str = "synthetic_mock_phase6e3",
    process_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    model_identity = model_identity or {}
    backend_provenance = backend_provenance or {}
    request_parameters = request_parameters or {}
    start_time = start_time or iso_now()
    end_time = end_time or start_time
    raw_text = raw_result.get("raw_response_text")
    failure = classify_failure(raw_result, validation)
    parent_request_id = request.get("parent_inference_request_id") or request["inference_request_id"]
    transport_attempt_number = int(request.get("transport_attempt_number", 1))
    scientific_generation_id = request.get("scientific_generation_id") or parent_request_id
    config_for_hash = {
        "model_key": request["model_key"],
        "exact_model_id": model_identity.get("exact_model_id"),
        "checkpoint_or_revision": model_identity.get("checkpoint_or_revision"),
        "inference_config_version": request["inference_config_id"],
        "prompt_package_version": request["prompt_package_version"],
        "response_schema_version": request["response_schema_version"],
        **request_parameters,
    }
    return {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "prediction_logging_version": PREDICTION_LOGGING_VERSION,
        "failure_handling_version": request.get("failure_handling_version", FAILURE_HANDLING_VERSION),
        "run_id": run_id,
        "process_id": process_id or f"pid-{os.getpid()}",
        "inference_request_id": request["inference_request_id"],
        "parent_inference_request_id": parent_request_id,
        "scientific_generation_id": scientific_generation_id,
        "transport_attempt_number": transport_attempt_number,
        "transport_retry_of": request.get("transport_retry_of"),
        "prediction_record_id": make_prediction_record_id(
            request["prediction_example_id"],
            request["condition"],
            request["model_key"],
            request["inference_config_id"],
        ),
        "prediction_example_id": request["prediction_example_id"],
        "rendered_prompt_id": request["rendered_prompt_id"],
        "condition_object_id": request.get("condition_object_id"),
        "condition": request["condition"],
        "model_key": request["model_key"],
        "exact_model_id": model_identity.get("exact_model_id"),
        "checkpoint_or_revision": model_identity.get("checkpoint_or_revision"),
        "quantisation": model_identity.get("quantisation"),
        "serving_framework": model_identity.get("serving_framework"),
        "backend_key": request["backend_key"],
        "deployment_environment": backend_provenance.get("deployment_environment", raw_result.get("backend_type")),
        "serving_mode": backend_provenance.get("serving_mode"),
        "endpoint_type": backend_provenance.get("endpoint_type"),
        "host_identifier": backend_provenance.get("host_identifier"),
        "server_software_version": backend_provenance.get("server_software_version"),
        "prompt_package_version": request["prompt_package_version"],
        "response_schema_version": request["response_schema_version"],
        "inference_config_version": request["inference_config_id"],
        "attempt_type": request["attempt_type"],
        "attempt_number": request["attempt_number"],
        "request_status": raw_result["request_status"],
        "response_validation_status": validation["status"],
        "response_schema_valid": validation["valid"],
        "attempt_status": derive_attempt_status(raw_result["request_status"], validation["status"], failure["failure_code"]),
        "failure_code": failure["failure_code"],
        "failure_category": failure["failure_category"],
        "start_time": start_time,
        "end_time": end_time,
        "latency_seconds": numeric_or_null((raw_result.get("latency") or {}).get("total_seconds")),
        "latency_source": (raw_result.get("latency") or {}).get("source"),
        "temperature_requested": request_parameters.get("temperature_requested"),
        "top_p_requested": request_parameters.get("top_p_requested"),
        "seed_requested": request_parameters.get("seed_requested"),
        "max_output_tokens": request_parameters.get("max_output_tokens"),
        "structured_output_strategy": request_parameters.get("structured_output_strategy"),
        "parameter_snapshot": sanitize_provider_metadata(request_parameters.get("parameter_snapshot")),
        "prompt_payload_sha256": hash_prompt_payload(request["messages"]),
        "inference_config_sha256": hash_inference_config(config_for_hash),
        "raw_response_text": raw_text,
        "raw_response_storage_ref": None,
        "extracted_model_text": raw_text,
        "provider_response_metadata": sanitize_provider_metadata(
            {
                **(raw_result.get("provider_response_metadata") or {}),
                **({"retry_after_seconds": failure["retry_after_seconds"]} if failure.get("retry_after_seconds") is not None else {}),
            }
        ),
        "token_usage": normalize_usage(raw_result.get("usage")),
        "cost_metadata": normalize_cost(raw_result.get("cost_metadata")),
        "finish_reason": (raw_result.get("provider_response_metadata") or {}).get("finish_reason"),
        "error_category": failure["failure_category"],
        "error_code": (raw_result.get("error") or {}).get("code"),
        "safe_error_message": sanitize_text((raw_result.get("error") or {}).get("message")),
        "http_status_code": (raw_result.get("error") or {}).get("http_status_code"),
        "timeout": raw_result["request_status"] == "timeout",
        "retryable": failure["retryable"],
    }


def finalize_prediction_record(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    if not attempts:
        raise ValueError("Cannot finalize prediction record without attempts.")
    attempts = sorted(attempts, key=lambda row: (row["attempt_number"], row["attempt_type"], row.get("transport_attempt_number", 1)))
    first = attempts[0]
    primary = next((row for row in attempts if row["attempt_type"] == "primary"), None)
    repair = next((row for row in attempts if row["attempt_type"] == "format_repair"), None)
    successful = next((row for row in attempts if row["response_validation_status"] == "valid"), None)
    failed_backend = any(row["request_status"] in {"timeout", "error", "backend_unavailable"} for row in attempts)
    if successful and successful["attempt_type"] == "primary":
        status = "valid_primary"
    elif successful and successful["attempt_type"] == "format_repair":
        status = "valid_after_repair"
    elif repair:
        status = "invalid_after_repair"
    elif failed_backend:
        status = "backend_failed"
    else:
        status = "pending"
    parsed = parse_raw_if_valid(successful)
    diagnostics = consistency_diagnostics(parsed)
    return {
        "schema_version": PREDICTION_SCHEMA_VERSION,
        "prediction_logging_version": PREDICTION_LOGGING_VERSION,
        "failure_handling_version": first.get("failure_handling_version"),
        "prediction_record_id": first["prediction_record_id"],
        "prediction_example_id": first["prediction_example_id"],
        "condition": first["condition"],
        "model_key": first["model_key"],
        "exact_model_id": first["exact_model_id"],
        "checkpoint_or_revision": first["checkpoint_or_revision"],
        "backend_environment": first["deployment_environment"],
        "prompt_package_version": first["prompt_package_version"],
        "inference_config_version": first["inference_config_version"],
        "final_status": status,
        "successful_attempt_id": successful["inference_request_id"] if successful else None,
        "primary_attempt_id": primary["inference_request_id"] if primary else None,
        "repair_attempt_id": repair["inference_request_id"] if repair else None,
        "number_of_attempts": len(attempts),
        "scientific_generation_count": len({row.get("scientific_generation_id", row["inference_request_id"]) for row in attempts}),
        "transport_attempt_count": len(attempts),
        "transport_retry_count": sum(1 for row in attempts if int(row.get("transport_attempt_number", 1)) > 1),
        "format_repair_attempt_count": sum(1 for row in attempts if row["attempt_type"] == "format_repair"),
        "response_validity": successful["response_validation_status"] if successful else attempts[-1]["response_validation_status"],
        "predicted_preferred_mix": parsed.get("predicted_preferred_mix") if parsed else None,
        "predicted_rating_A": parsed.get("predicted_ratings", {}).get("A") if parsed else None,
        "predicted_rating_B": parsed.get("predicted_ratings", {}).get("B") if parsed else None,
        "predicted_rating_C": parsed.get("predicted_ratings", {}).get("C") if parsed else None,
        "predicted_rating_D": parsed.get("predicted_ratings", {}).get("D") if parsed else None,
        "predicted_rating_E": parsed.get("predicted_ratings", {}).get("E") if parsed else None,
        "predicted_ranking": parsed.get("predicted_ranking") if parsed else None,
        "raw_final_response_ref": successful["raw_response_storage_ref"] if successful else None,
        "raw_final_response_text": successful["raw_response_text"] if successful else attempts[-1]["raw_response_text"],
        "final_usage_totals": sum_usage(attempts),
        "total_latency_seconds": sum_nullable(row["latency_seconds"] for row in attempts),
        "run_id": first["run_id"],
        "run_provenance_version": PREDICTION_LOGGING_VERSION,
        **diagnostics,
    }


class JsonlAttemptLogger:
    def __init__(self, run_dir: Path, resume: bool = False):
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "raw_responses").mkdir(exist_ok=True)
        self.path = self.run_dir / "attempt_log.jsonl"
        self.completed = load_completed_request_ids(self.path) if resume else set()
        self.existing = {row["inference_request_id"]: row for row in read_jsonl(self.path)} if self.path.exists() else {}

    def log_attempt(self, record: dict[str, Any]) -> None:
        request_id = record["inference_request_id"]
        if request_id in self.existing:
            if self.existing[request_id] == record:
                raise ValueError(f"Duplicate completed attempt blocked: {request_id}")
            raise ValueError(f"Conflicting duplicate attempt detected: {request_id}")
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(record) + "\n")
            handle.flush()
        self.existing[request_id] = record
        self.completed.add(request_id)


def load_completed_request_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {row["inference_request_id"] for row in read_jsonl(path) if row.get("request_status") == "completed"}


def load_resume_state(run_dir: Path) -> dict[str, Any]:
    attempts = read_jsonl(run_dir / "attempt_log.jsonl")
    predictions = read_jsonl(run_dir / "predictions.jsonl")
    return {
        "completed_primary_attempts": [row["inference_request_id"] for row in attempts if row.get("attempt_type") == "primary" and row.get("request_status") == "completed"],
        "completed_repair_attempts": [row["inference_request_id"] for row in attempts if row.get("attempt_type") == "format_repair" and row.get("request_status") == "completed"],
        "failed_predictions": [row["prediction_record_id"] for row in predictions if row.get("final_status") in {"backend_failed", "invalid_after_repair"}],
        "pending_predictions": [row["prediction_record_id"] for row in predictions if row.get("final_status") == "pending"],
    }


def write_predictions(run_dir: Path, attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_prediction: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        by_prediction[attempt["prediction_record_id"]].append(attempt)
    predictions = [finalize_prediction_record(rows) for _, rows in sorted(by_prediction.items())]
    write_jsonl(run_dir / "predictions.jsonl", predictions)
    return predictions


def write_execution_summary(run_dir: Path, run_manifest: dict[str, Any], attempts: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(row["final_status"] for row in predictions)
    model_counts = Counter(row["model_key"] for row in predictions)
    condition_counts = Counter(row["condition"] for row in predictions)
    by_model_condition: dict[str, dict[str, Any]] = {}
    for model in sorted(model_counts):
        for condition in sorted(condition_counts):
            key = f"{model}__{condition}"
            subset = [row for row in predictions if row["model_key"] == model and row["condition"] == condition]
            by_model_condition[key] = {
                "predictions": len(subset),
                "valid_outputs": sum(1 for row in subset if row["final_status"] in {"valid_primary", "valid_after_repair"}),
                "primary_validity_rate": safe_rate(sum(1 for row in subset if row["final_status"] == "valid_primary"), len(subset)),
                "repairs_attempted": sum(row.get("format_repair_attempt_count", 0) for row in subset),
                "repairs_successful": sum(1 for row in subset if row["final_status"] == "valid_after_repair"),
                "invalid_outputs": sum(1 for row in subset if row["final_status"] in {"invalid_after_repair"}),
                "backend_failures": sum(1 for row in subset if row["final_status"] == "backend_failed"),
                "transport_retries": sum(row.get("transport_retry_count", 0) for row in subset),
                "unresolved_pending": sum(1 for row in subset if row["final_status"] in {"pending", "primary_in_progress", "repair_pending", "repair_in_progress", "backend_retry_pending"}),
            }
    terminal_statuses = {"valid_primary", "valid_after_repair", "invalid_after_repair", "backend_failed"}
    valid_statuses = {"valid_primary", "valid_after_repair"}
    summary = {
        "schema_version": EXECUTION_SUMMARY_SCHEMA_VERSION,
        "prediction_logging_version": PREDICTION_LOGGING_VERSION,
        "run_id": run_manifest["run_id"],
        "run_type": run_manifest["run_type"],
        "expected_predictions": run_manifest["expected_request_count"],
        "predictions_attempted": len(predictions),
        "valid_primary": status_counts.get("valid_primary", 0),
        "valid_after_repair": status_counts.get("valid_after_repair", 0),
        "invalid": status_counts.get("invalid_after_repair", 0),
        "backend_failures": status_counts.get("backend_failed", 0),
        "blocked": status_counts.get("blocked_by_preflight", 0),
        "pending": sum(status_counts.get(status, 0) for status in {"pending", "primary_in_progress", "repair_pending", "repair_in_progress", "backend_retry_pending", "not_run"}),
        "attempts_total": len(attempts),
        "total_transport_retries": sum(1 for row in attempts if int(row.get("transport_attempt_number", 1)) > 1),
        "total_formatting_repairs": sum(1 for row in attempts if row.get("attempt_type") == "format_repair"),
        "INFERENCE_RUN_COMPLETE": len(predictions) == run_manifest["expected_request_count"] and all(row["final_status"] in terminal_statuses for row in predictions),
        "ALL_EXPECTED_PREDICTIONS_VALID": len(predictions) == run_manifest["expected_request_count"] and all(row["final_status"] in valid_statuses for row in predictions),
        "token_usage_totals": sum_usage(attempts),
        "cost_totals": sum_cost(attempts),
        "latency_summary": latency_summary(attempts),
        "model_counts": dict(sorted(model_counts.items())),
        "condition_counts": dict(sorted(condition_counts.items())),
        "by_model_condition": by_model_condition,
        "contains_ground_truth": False,
    }
    write_json_atomic(run_dir / "execution_summary.json", summary)
    return summary


def derive_attempt_status(request_status: str, validation_status: str, failure_code: str | None) -> str:
    if request_status == "timeout":
        return "timeout"
    if failure_code in {"connection_error", "http_client_error", "http_server_error", "backend_unavailable", "rate_limited", "bad_credentials", "unsupported_model"}:
        return failure_code
    if failure_code == "empty_response" or validation_status == "missing_response":
        return "empty_response"
    if validation_status in {"invalid_json", "schema_invalid", "valid"}:
        return validation_status
    if request_status == "completed":
        return "request_completed"
    return "request_not_started"


def safe_rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def merge_run_logs(source_run_dirs: list[Path], output_dir: Path) -> dict[str, Any]:
    attempts: dict[str, dict[str, Any]] = {}
    predictions: dict[str, dict[str, Any]] = {}
    run_types = set()
    conflicts = []
    for run_dir in source_run_dirs:
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        run_types.add(manifest["run_type"])
        for attempt in read_jsonl(run_dir / "attempt_log.jsonl"):
            validate_merge_attempt(attempt)
            existing = attempts.get(attempt["inference_request_id"])
            if existing and existing != attempt:
                conflicts.append(f"conflicting attempt {attempt['inference_request_id']}")
            attempts[attempt["inference_request_id"]] = attempt
        for prediction in read_jsonl(run_dir / "predictions.jsonl"):
            validate_merge_prediction(prediction)
            existing = predictions.get(prediction["prediction_record_id"])
            if existing and existing != prediction:
                conflicts.append(f"conflicting prediction {prediction['prediction_record_id']}")
            predictions[prediction["prediction_record_id"]] = prediction
    if len(run_types) > 1:
        conflicts.append("mixed real/synthetic run types")
    if conflicts:
        raise ValueError("; ".join(conflicts))
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "attempt_log.jsonl", list(attempts.values()))
    write_jsonl(output_dir / "predictions.jsonl", list(predictions.values()))
    result = {
        "schema_version": "phase6e3_merged_log_manifest_v1",
        "prediction_logging_version": PREDICTION_LOGGING_VERSION,
        "source_run_count": len(source_run_dirs),
        "attempt_count": len(attempts),
        "prediction_count": len(predictions),
        "run_type": next(iter(run_types)) if run_types else None,
        "conflicts": [],
    }
    write_json(output_dir / "merged_log_manifest.json", result)
    return result


def run_logged_synthetic_mock(
    repo_root: Path,
    run_id: str = "phase6e3_synthetic_mock_run",
    rendered_prompts_path: Path = Path("llm-experiments/outputs/synthetic/phase6d2_rendered_prompts/rendered_prompts.jsonl"),
    model_registry_path: Path = Path("llm-experiments/config/phase6e1_model_registry.json"),
    backend_registry_path: Path = Path("llm-experiments/config/phase6e1_backend_registry.json"),
    response_schema_path: Path = Path("llm-experiments/schema/preference_prediction_response_v1.json"),
    output_root: Path = Path("llm-experiments/outputs/synthetic/phase6e3"),
) -> dict[str, Any]:
    run_dir = repo_root / output_root / run_id
    if run_dir.exists():
        for filename in ["attempt_log.jsonl", "predictions.jsonl", "execution_summary.json", "run_manifest.json"]:
            path = run_dir / filename
            if path.exists():
                path.unlink()
    rendered_prompts = load_jsonl(repo_root / rendered_prompts_path)
    model_registry = load_model_registry(repo_root / model_registry_path)
    backend_registry = load_backend_registry(repo_root / backend_registry_path)
    response_schema = json.loads((repo_root / response_schema_path).read_text(encoding="utf-8"))
    model_keys = ["gpt", "claude_sonnet", "llama_3_1_70b_instruct", "centaur"]
    manifest = create_run_manifest(
        run_id=run_id,
        run_type="synthetic_mock",
        rendered_prompt_dataset_path=repo_root / rendered_prompts_path,
        rendered_prompt_count=len(rendered_prompts),
        model_keys=model_keys,
        expected_request_count=len(rendered_prompts) * len(model_keys),
        inference_config_version=PRIMARY_INFERENCE_CONFIG_VERSION,
        environment_summary={"backend": "mock", "real_model_calls": False},
    )
    write_json_atomic(run_dir / "run_manifest.json", manifest)
    logger = JsonlAttemptLogger(run_dir)
    attempts = []
    mock_backend = resolve_backend("mock", backend_registry)
    adapter = MockAdapter(mock_backend)
    request_parameters = {
        "temperature_requested": 0,
        "top_p_requested": None,
        "seed_requested": 20260814,
        "max_output_tokens": 256,
        "structured_output_strategy": "local_schema_validation",
        "parameter_snapshot": {"mock_mode": "valid_response"},
    }
    for model_key in model_keys:
        model_spec = {**resolve_model(model_key, model_registry), "default_backend_key": "mock", "inference_config_version": PRIMARY_INFERENCE_CONFIG_VERSION}
        for rendered_prompt in rendered_prompts:
            request = make_inference_request(rendered_prompt, model_spec, inference_config_version=PRIMARY_INFERENCE_CONFIG_VERSION)
            provider = adapter.invoke(adapter.prepare_request(request))
            raw_result = make_raw_result(
                request,
                backend_type=adapter.backend_type,
                request_status=provider.get("status", "completed"),
                raw_response_text=adapter.extract_raw_response(provider),
                provider_response_metadata=provider.get("metadata"),
                usage=adapter.extract_usage(provider),
                latency={"total_seconds": 0.0, "source": "local_mock"},
                error=provider.get("error"),
            )
            validation = validate_response_text(raw_result["raw_response_text"], response_schema)
            attempt = make_attempt_record(
                request,
                raw_result,
                validation,
                model_identity={"exact_model_id": f"mock::{model_key}", "checkpoint_or_revision": "mock_v1"},
                backend_provenance={"deployment_environment": "mock", "serving_mode": "deterministic_mock"},
                request_parameters=request_parameters,
                run_id=run_id,
            )
            logger.log_attempt(attempt)
            attempts.append(attempt)
    predictions = write_predictions(run_dir, attempts)
    summary = write_execution_summary(run_dir, manifest, attempts, predictions)
    manifest["ended_at"] = iso_now()
    manifest["completed_count"] = summary["attempts_total"]
    manifest["valid_count"] = summary["valid_primary"] + summary["valid_after_repair"]
    manifest["invalid_count"] = summary["invalid"]
    manifest["failed_count"] = summary["backend_failures"]
    write_json_atomic(run_dir / "run_manifest.json", manifest)
    write_controlled_multi_attempt_fixtures(repo_root / output_root / "controlled_multi_attempt_fixtures", response_schema)
    return summary


def write_controlled_multi_attempt_fixtures(output_dir: Path, response_schema: dict[str, Any]) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    base_request = {
        "inference_request_id": "fixture_primary",
        "prediction_example_id": "fixture_example",
        "rendered_prompt_id": "fixture_rendered",
        "condition_object_id": "fixture_condition",
        "condition": "non_history",
        "model_key": "mock_fixture",
        "backend_key": "mock",
        "prompt_package_version": "phase6d_prompt_package_v1",
        "response_schema_version": "preference_prediction_response_v1",
        "inference_config_id": PRIMARY_INFERENCE_CONFIG_VERSION,
        "attempt_type": "primary",
        "attempt_number": 1,
        "messages": [{"role": "system", "content": "fixture"}, {"role": "user", "content": "fixture"}],
    }
    valid_text = '{"predicted_preferred_mix":"C","predicted_ratings":{"A":60,"B":45,"C":80,"D":70,"E":55},"predicted_ranking":["C","D","A","E","B"]}'
    invalid_text = '{"predicted_preferred_mix":"F"}'
    cases = {}
    for name, attempt_specs in {
        "primary_valid": [("primary", 1, "completed", valid_text)],
        "primary_invalid_repair_valid": [("primary", 1, "completed", invalid_text), ("format_repair", 2, "completed", valid_text)],
        "primary_invalid_repair_invalid": [("primary", 1, "completed", invalid_text), ("format_repair", 2, "completed", invalid_text)],
        "backend_failure": [("primary", 1, "error", None)],
    }.items():
        attempts = []
        for attempt_type, number, status, raw_text in attempt_specs:
            request = {**base_request, "inference_request_id": f"fixture_{name}_{attempt_type}_{number}", "attempt_type": attempt_type, "attempt_number": number}
            raw_result = make_raw_result(request, "mock", status, raw_response_text=raw_text, error={"type": "connection_error"} if status == "error" else None)
            validation = validate_response_text(raw_text, response_schema)
            attempts.append(make_attempt_record(request, raw_result, validation, {"exact_model_id": "mock::fixture", "checkpoint_or_revision": "mock_v1"}, {"deployment_environment": "mock"}, run_id=f"fixture_{name}"))
        prediction = finalize_prediction_record(attempts)
        cases[name] = {"attempts": attempts, "prediction": prediction}
        write_json(output_dir / f"{name}.json", cases[name])
    return cases


def validate_merge_attempt(attempt: dict[str, Any]) -> None:
    if attempt.get("prompt_package_version") != "phase6d_prompt_package_v1":
        raise ValueError("incompatible prompt package")
    if attempt.get("response_schema_version") != "preference_prediction_response_v1":
        raise ValueError("incompatible response schema")
    if not attempt.get("exact_model_id"):
        raise ValueError("missing model identity")
    if contains_secret(attempt):
        raise ValueError("attempt contains secret-like content")


def validate_merge_prediction(prediction: dict[str, Any]) -> None:
    if prediction.get("prompt_package_version") != "phase6d_prompt_package_v1":
        raise ValueError("incompatible prompt package")
    if prediction.get("inference_config_version") != PRIMARY_INFERENCE_CONFIG_VERSION:
        raise ValueError("incompatible config version")
    if not prediction.get("exact_model_id"):
        raise ValueError("missing model identity")
    if contains_secret(prediction):
        raise ValueError("prediction contains secret-like content")


def sanitize_provider_metadata(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        clean = {}
        for key, nested in value.items():
            if any(marker in str(key).lower() for marker in SECRET_KEY_MARKERS):
                clean[key] = "[REDACTED]"
            else:
                clean[key] = sanitize_provider_metadata(nested)
        return clean
    if isinstance(value, list):
        return [sanitize_provider_metadata(item) for item in value]
    if isinstance(value, str):
        return sanitize_text(value)
    return value


def sanitize_text(text: Any) -> Any:
    if text is None:
        return None
    text = str(text)
    lowered = text.lower()
    if any(marker in lowered for marker in SECRET_VALUE_MARKERS):
        return "[REDACTED]"
    return text


def contains_secret(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_secret = any(marker in str(key).lower() for marker in SECRET_KEY_MARKERS)
            if key_secret and nested not in {None, "", "[REDACTED]"}:
                return True
            if contains_secret(nested):
                return True
    elif isinstance(value, list):
        return any(contains_secret(item) for item in value)
    elif isinstance(value, str):
        lowered = value.lower()
        return any(marker in lowered for marker in SECRET_VALUE_MARKERS) and value != "[REDACTED]"
    return False


def consistency_diagnostics(parsed: dict[str, Any] | None) -> dict[str, Any]:
    if not parsed:
        return {
            "preferred_matches_highest_rating": None,
            "ranking_first_matches_highest_rating": None,
            "ranking_complete": None,
            "predicted_rating_tie_present": None,
        }
    ratings = parsed["predicted_ratings"]
    max_rating = max(ratings.values())
    top = sorted([label for label, value in ratings.items() if value == max_rating])
    return {
        "preferred_matches_highest_rating": parsed["predicted_preferred_mix"] in top,
        "ranking_first_matches_highest_rating": parsed["predicted_ranking"][0] in top,
        "ranking_complete": sorted(parsed["predicted_ranking"]) == ["A", "B", "C", "D", "E"],
        "predicted_rating_tie_present": len(top) > 1,
    }


def parse_raw_if_valid(attempt: dict[str, Any] | None) -> dict[str, Any] | None:
    if not attempt or attempt["response_validation_status"] != "valid":
        return None
    return json.loads(attempt["raw_response_text"])


def normalize_usage(usage: dict[str, Any] | None) -> dict[str, Any]:
    usage = usage or {}
    return {
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }


def normalize_cost(cost: dict[str, Any] | None) -> dict[str, Any]:
    cost = cost or {}
    return {
        "input_cost": cost.get("input_cost"),
        "output_cost": cost.get("output_cost"),
        "total_cost": cost.get("total_cost"),
        "currency": cost.get("currency"),
        "cost_source": cost.get("cost_source", "unavailable"),
    }


def sum_usage(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {}
    for key in ["input_tokens", "output_tokens", "total_tokens"]:
        values = [row.get("token_usage", {}).get(key) for row in attempts if row.get("token_usage", {}).get(key) is not None]
        totals[key] = sum(values) if values else None
    return totals


def sum_cost(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    values = [row.get("cost_metadata", {}).get("total_cost") for row in attempts if row.get("cost_metadata", {}).get("total_cost") is not None]
    return {"total_cost": sum(values) if values else None, "currency": None, "cost_source": "unavailable" if not values else "calculated"}


def latency_summary(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    values = [row["latency_seconds"] for row in attempts if row.get("latency_seconds") is not None]
    if not values:
        return {"count": 0, "min_seconds": None, "max_seconds": None, "total_seconds": None}
    return {"count": len(values), "min_seconds": min(values), "max_seconds": max(values), "total_seconds": sum(values)}


def sum_nullable(values: Any) -> float | None:
    numbers = [value for value in values if value is not None]
    return sum(numbers) if numbers else None


def numeric_or_null(value: Any) -> float | int | None:
    return value if isinstance(value, (int, float)) else None


def portable_artifact_path(path: Path) -> str:
    normalized = str(path).replace("\\", "/")
    parts = normalized.split("/")
    if "llm-experiments" in parts:
        return "/".join(parts[parts.index("llm-experiments"):])
    return normalized


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return load_jsonl(path)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(canonical_json(row) + "\n")


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()
