"""Phase 6G.4A GPT-5.5 production inference runner.

This runner consumes the frozen Phase 6G.3 GPT shard only. It performs a hard
preflight before any API request and writes canonical production artifacts.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from importlib import util
from pathlib import Path
from typing import Any

from llm_experiments.inference.failures import RETRYABLE_FAILURES, classify_failure, should_repair
from llm_experiments.inference.phase6g3 import sha256_file, sha256_json
from llm_experiments.inference.records import sanitize_provider_metadata
from llm_experiments.inference.validation import load_response_schema, validate_response_text
from llm_experiments.prompts.freeze_package import verify_prompt_package
from llm_experiments.prompts.render import render_format_repair
from llm_experiments.prompts.prompt_spec import load_jsonl, write_json


SCHEMA_VERSION = "phase6g4a_gpt_production_inference_v1"
BASE_OUTPUT_DIR = Path("llm-experiments/outputs/real/phase6g4/gpt")
OUTPUT_DIR = BASE_OUTPUT_DIR / "corrected_run_02"
FAILED_INFRA_ARCHIVE_DIR = BASE_OUTPUT_DIR / "failed_infrastructure_run_01"
DIAGNOSTIC_256_RUN_DIR = BASE_OUTPUT_DIR / "corrected_run_01"
CONFIGURATION_CORRECTION_MANIFEST = BASE_OUTPUT_DIR / "configuration_correction_256_to_1024.json"
RENDERED_PROMPTS = Path("llm-experiments/outputs/real/phase6g3/phase6g3_real_rendered_prompts.jsonl")
GPT_SHARD = Path("llm-experiments/outputs/real/phase6g3/phase6g3_qmul_gpt_shard_manifest.json")
PROMPT_HASH_MANIFEST = Path("llm-experiments/outputs/real/phase6g3/phase6g3_prompt_hash_manifest.json")
PHASE6G3_FREEZE = Path("llm-experiments/outputs/real/phase6g3/phase6g3_freeze_manifest.json")
PHASE6G2D_READINESS = Path("llm-experiments/outputs/real/phase6g2d/phase6g2d_final_readiness.json")
PHASE6G2D_INFERENCE_CONFIG = Path("llm-experiments/outputs/real/phase6g2d/phase6g2d_final_inference_config.json")
PHASE6G1_GATE = Path("llm-experiments/outputs/real/phase6b/production_readiness_gate.json")
RESPONSE_SCHEMA = Path("llm-experiments/schema/preference_prediction_response_v1.json")
REQUEST_MODEL = "gpt-5.5"
EXPECTED_RETURNED_MODEL = "gpt-5.5-2026-04-23"
MODEL_KEY = "gpt"
PRIOR_MAX_OUTPUT_TOKENS = 256
MAX_OUTPUT_TOKENS = 1024
MAX_TRANSPORT_RETRIES = 2
MAX_FORMAT_REPAIRS = 1
TERMINAL_STATUSES = {"valid_primary", "valid_after_repair", "invalid_after_repair", "backend_failed", "output_budget_exhausted"}
PRIOR_CORRECTED_RUN_ID = "phase6g4a_gpt_corrected_run_01"
CORRECTED_RUN_ID = "phase6g4a_gpt_corrected_run_02"
FAILED_INFRASTRUCTURE_RUN_ID = "phase6g4a_gpt_failed_infrastructure_run_01"


def run_gpt_production(
    repo_root: Path,
    guarded_batch_size: int = 5,
    output_dir: Path = OUTPUT_DIR,
    run_id: str = CORRECTED_RUN_ID,
) -> dict[str, Any]:
    out = repo_root / output_dir
    out.mkdir(parents=True, exist_ok=True)
    prepare_output_budget_correction(repo_root)
    preflight = run_preflight(repo_root, output_dir=output_dir)
    run_manifest = build_run_manifest(repo_root, preflight, guarded_batch_size, output_dir, run_id)
    write_json(out / "run_manifest.json", run_manifest)
    if not preflight["passed"]:
        summary = build_blocked_summary(run_manifest, preflight)
        write_json(out / "preflight_report.json", preflight)
        write_json(out / "execution_summary.json", summary)
        write_json(out / "failure_summary.json", {"schema_version": "phase6g4a_gpt_failure_summary_v1", "blocked_by_preflight": True, "failures": preflight["failures"]})
        write_report(out / "gpt_production_qc_report.md", summary, preflight)
        return summary

    response_schema = load_response_schema(repo_root / RESPONSE_SCHEMA)
    rendered = {row["rendered_prompt_id"]: row for row in load_jsonl(repo_root / RENDERED_PROMPTS)}
    shard = load_json(repo_root / GPT_SHARD)
    prompt_hashes = {row["rendered_prompt_id"]: row["message_payload_sha256"] for row in load_json(repo_root / PROMPT_HASH_MANIFEST)["records"]}
    requests = shard["requests"]
    existing_predictions = load_predictions(out / "predictions.jsonl")
    terminal_ids = {row["request_id"] for row in existing_predictions if row.get("final_status") in TERMINAL_STATUSES}
    attempts: list[dict[str, Any]] = load_jsonl(out / "attempt_log.jsonl")
    actual_models: set[str] = {row.get("actual_returned_model") for row in attempts if row.get("actual_returned_model")}
    executed_this_invocation = 0
    stopped_after_guarded_batch = False

    for request_ref in requests:
        if request_ref["request_id"] in terminal_ids:
            continue
        if executed_this_invocation >= guarded_batch_size:
            stopped_after_guarded_batch = True
            break
        if actual_models and actual_models != {EXPECTED_RETURNED_MODEL}:
            break
        rendered_prompt = rendered[request_ref["rendered_prompt_id"]]
        prediction_attempts = execute_prediction(request_ref, rendered_prompt, prompt_hashes[request_ref["rendered_prompt_id"]], response_schema, run_id)
        attempts.extend(prediction_attempts)
        append_jsonl(out / "attempt_log.jsonl", prediction_attempts)
        prediction = finalize_prediction(request_ref, prediction_attempts, run_id)
        append_jsonl(out / "predictions.jsonl", [prediction])
        terminal_ids.add(request_ref["request_id"])
        executed_this_invocation += 1
        actual_models.update(row.get("actual_returned_model") for row in prediction_attempts if row.get("actual_returned_model"))

    predictions = load_predictions(out / "predictions.jsonl")
    summary = build_execution_summary(run_manifest, attempts, predictions, preflight, executed_this_invocation, stopped_after_guarded_batch)
    write_json(out / "execution_summary.json", summary)
    write_json(out / "failure_summary.json", build_failure_summary(attempts, predictions))
    write_report(out / "gpt_production_qc_report.md", summary, preflight)
    return summary


def prepare_infrastructure_recovery(repo_root: Path) -> dict[str, Any]:
    """Record the confirmed failed infrastructure run as separate provenance."""
    archive = repo_root / FAILED_INFRA_ARCHIVE_DIR
    archive.mkdir(parents=True, exist_ok=True)
    existing_manifest = archive / "recovery_manifest.json"
    if existing_manifest.exists():
        return load_json(existing_manifest)
    shard = load_json(repo_root / GPT_SHARD)
    active_base = repo_root / BASE_OUTPUT_DIR
    files_to_preserve = [
        "attempt_log.jsonl",
        "predictions.jsonl",
        "run_manifest.json",
        "execution_summary.json",
        "failure_summary.json",
        "gpt_production_qc_report.md",
        "preflight_report.json",
    ]
    moved_files = []
    for name in files_to_preserve:
        source = active_base / name
        destination = archive / name
        if source.exists() and not destination.exists():
            source.replace(destination)
            moved_files.append(name)
    existing_attempts = load_jsonl(archive / "attempt_log.jsonl")
    existing_predictions = load_jsonl(archive / "predictions.jsonl")
    affected_prediction_ids = [prediction_id(row) for row in shard.get("requests", [])]
    manifest = {
        "schema_version": "phase6g4a_gpt_infrastructure_recovery_manifest_v1",
        "created_at_utc": iso_now(),
        "old_run_id": FAILED_INFRASTRUCTURE_RUN_ID,
        "new_corrected_run_id": CORRECTED_RUN_ID,
        "archive_dir": str(FAILED_INFRA_ARCHIVE_DIR).replace("\\", "/"),
        "moved_files": moved_files,
        "local_failed_attempt_log_present": bool(existing_attempts),
        "local_failed_prediction_log_present": bool(existing_predictions),
        "failure_classification": {
            "final_status": "backend_failed",
            "failure_category": "transport",
            "failure_code": "connection_error",
            "affected_prediction_count": 396,
            "failed_transport_attempt_count": 1188,
            "successful_provider_generation_count": 0,
            "returned_model_identity_count": 0,
            "token_usage_count": 0,
            "formatting_repair_count": 0,
        },
        "affected_prediction_ids": affected_prediction_ids,
        "confirmed_root_cause": "malformed OPENAI_API_KEY contained trailing newline, producing an illegal HTTP Authorization header before requests reached OpenAI",
        "clean_rerun_justification": "No successful provider generations, response text, returned model identities, or token usage were obtained; failed attempts are infrastructure provenance, not scientific GPT predictions.",
        "corrected_environment_probe": {
            "non_study_probe_succeeded": True,
            "output": "API OK",
            "returned_model": EXPECTED_RETURNED_MODEL,
        },
        "secret_policy": "No API key or secret value is stored; only the confirmed non-secret root-cause class is recorded.",
    }
    write_json(archive / "recovery_manifest.json", manifest)
    return manifest


def prepare_output_budget_correction(repo_root: Path) -> dict[str, Any]:
    """Record the GPT-only execution compatibility correction from 256 to 1024."""
    path = repo_root / CONFIGURATION_CORRECTION_MANIFEST
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "phase6g4a_gpt_output_budget_correction_manifest_v1",
        "created_at_utc": iso_now(),
        "correction_type": "execution_compatibility_correction",
        "scope": "gpt_only",
        "prior_run_id": PRIOR_CORRECTED_RUN_ID,
        "new_run_id": CORRECTED_RUN_ID,
        "prior_run_namespace": str(DIAGNOSTIC_256_RUN_DIR).replace("\\", "/"),
        "new_run_namespace": str(OUTPUT_DIR).replace("\\", "/"),
        "prior_max_output_tokens": PRIOR_MAX_OUTPUT_TOKENS,
        "new_max_output_tokens": MAX_OUTPUT_TOKENS,
        "reason": "OpenAI Responses API max_output_tokens includes reasoning tokens plus visible output tokens; 256 can truncate before required JSON is emitted.",
        "guarded_validation_evidence": {
            "guarded_prediction_count": 3,
            "incomplete_at_exact_prior_budget_count": 2,
            "completed_count": 1,
            "prior_budget_hit_output_tokens": 256,
            "completed_output_tokens": 151,
            "attempt_1": {
                "request_status": "incomplete",
                "output_tokens": 256,
                "reasoning_tokens": 223,
                "validation": "invalid_json",
            },
            "attempt_2": {
                "request_status": "incomplete",
                "output_tokens": 256,
                "reasoning_tokens": 256,
                "validation": "missing_response",
            },
            "attempt_3": {
                "request_status": "completed",
                "output_tokens": 151,
                "reasoning_tokens": 95,
                "validation": "valid",
            },
        },
        "scientific_policy": {
            "diagnostic_256_token_run_is_final_scientific_gpt_run": False,
            "no_human_ground_truth_inspected": True,
            "no_prediction_accuracy_used": True,
            "rendered_prompts_changed": False,
            "response_schema_changed": False,
            "model_identity_changed": False,
            "decoding_policy_changed": False,
            "evaluation_protocol_changed": False,
            "global_max_output_policy_changed_for_other_models": False,
        },
        "inference_config_hash_prior": sha256_json({"model": REQUEST_MODEL, "max_output_tokens": PRIOR_MAX_OUTPUT_TOKENS, "temperature": "omitted", "top_p": "omitted"}),
        "inference_config_hash_new": inference_config_hash(),
        "secret_policy": "No API key or secret value is stored.",
    }
    write_json(path, manifest)
    return manifest


def run_preflight(repo_root: Path, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    failures: list[str] = []
    prompt_verification = verify_prompt_package(repo_root)
    phase6g1 = load_json(repo_root / PHASE6G1_GATE)
    phase6g2d = load_json(repo_root / PHASE6G2D_READINESS)
    phase6g3 = load_json(repo_root / PHASE6G3_FREEZE)
    shard = load_json(repo_root / GPT_SHARD)
    hash_manifest = load_json(repo_root / PROMPT_HASH_MANIFEST)
    rendered = {row["rendered_prompt_id"]: row for row in load_jsonl(repo_root / RENDERED_PROMPTS)}
    requests = shard.get("requests", [])
    output_dir_ok = str(output_dir).replace("\\", "/").endswith("phase6g4/gpt/corrected_run_02")
    hash_mismatches = []
    prompt_hashes = {row["rendered_prompt_id"]: row["message_payload_sha256"] for row in hash_manifest["records"]}
    for row in requests:
        rendered_prompt = rendered.get(row["rendered_prompt_id"])
        expected_hash = prompt_hashes.get(row["rendered_prompt_id"])
        if rendered_prompt is None or expected_hash != sha256_json(rendered_prompt["messages"]) or row.get("prompt_hash") != expected_hash:
            hash_mismatches.append(row["request_id"])
    duplicate_ids = duplicate_values([row["request_id"] for row in requests])
    condition_counts = Counter(row["condition"] for row in requests)
    key_state = inspect_openai_api_key()
    checks = {
        "phase6d_prompt_package_frozen": bool(prompt_verification.get("PHASE6D_PROMPT_PACKAGE_FROZEN")),
        "phase6g1_real_data_ready": bool(phase6g1.get("REAL_PHASE6B_READY")),
        "phase6g2d_production_ready": bool(phase6g2d.get("PRODUCTION_INFERENCE_READY")),
        "phase6g3_prompt_freeze_ready": bool(phase6g3.get("REAL_PRODUCTION_PROMPTS_FROZEN")),
        "gpt_shard_count_valid": len(requests) == 396 and condition_counts.get("non_history") == 198 and condition_counts.get("personalised_history") == 198,
        "prompt_hashes_valid": not hash_mismatches,
        "request_ids_deterministic_unique": not duplicate_ids,
        "openai_api_key_present": key_state["present"],
        "openai_api_key_has_no_leading_or_trailing_whitespace": key_state["has_no_leading_or_trailing_whitespace"],
        "openai_api_key_contains_no_cr_or_lf": key_state["contains_no_cr_or_lf"],
        "openai_sdk_installed": bool(util.find_spec("openai")),
        "output_directory_production_gpt_namespace": output_dir_ok,
        "no_hidden_ground_truth_loaded": not shard.get("contains_hidden_ground_truth", False),
    }
    for key, value in checks.items():
        if not value:
            failures.append(key)
    return {
        "schema_version": "phase6g4a_gpt_preflight_v1",
        "checked_at_utc": iso_now(),
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "gpt_shard_request_count": len(requests),
        "condition_counts": dict(sorted(condition_counts.items())),
        "prompt_hash_mismatches": hash_mismatches,
        "duplicate_request_ids": duplicate_ids,
        "credential_policy": "OPENAI_API_KEY presence checked as boolean only; secret value is never logged.",
        "openai_api_key_policy": "must exist, must have no leading/trailing whitespace, and must contain no CR/LF characters; value is never serialized",
    }


def inspect_openai_api_key() -> dict[str, bool]:
    value = os.environ.get("OPENAI_API_KEY")
    if value is None:
        return {
            "present": False,
            "has_no_leading_or_trailing_whitespace": False,
            "contains_no_cr_or_lf": False,
        }
    return {
        "present": True,
        "has_no_leading_or_trailing_whitespace": value == value.strip(),
        "contains_no_cr_or_lf": "\n" not in value and "\r" not in value,
    }


def execute_prediction(request_ref: dict[str, Any], rendered_prompt: dict[str, Any], prompt_hash: str, response_schema: dict[str, Any], run_id: str) -> list[dict[str, Any]]:
    attempts = []
    primary_attempt = call_with_transport_retries(request_ref, rendered_prompt, prompt_hash, response_schema, "primary", 1, run_id)
    attempts.extend(primary_attempt)
    final_primary = primary_attempt[-1]
    if should_repair(final_primary["validation_status"], final_primary["request_status"], final_primary.get("raw_response_text")):
        repair_messages = render_format_repair(final_primary["raw_response_text"], response_schema)["messages"]
        repair_attempts = call_with_transport_retries(request_ref, {"messages": repair_messages}, prompt_hash, response_schema, "format_repair", 2, run_id)
        attempts.extend(repair_attempts[:MAX_FORMAT_REPAIRS + MAX_TRANSPORT_RETRIES])
    return attempts


def call_with_transport_retries(
    request_ref: dict[str, Any],
    rendered_prompt: dict[str, Any],
    prompt_hash: str,
    response_schema: dict[str, Any],
    attempt_type: str,
    attempt_number: int,
    run_id: str,
) -> list[dict[str, Any]]:
    attempts = []
    for transport_attempt in range(1, MAX_TRANSPORT_RETRIES + 2):
        started = time.perf_counter()
        started_at = iso_now()
        try:
            provider = invoke_openai(rendered_prompt["messages"], attempt_type)
            raw_text = provider.get("output_text")
            validation = validate_response_text(raw_text, response_schema)
            request_status = provider.get("status", "completed")
            error = None
        except Exception as exc:  # pragma: no cover - only hit during live transport errors
            raw_text = None
            validation = validate_response_text(None, response_schema)
            request_status = "error"
            provider = {"metadata": {}, "usage": None, "incomplete_details": None, "error": {"type": "connection_error", "message": str(exc)}}
            error = provider["error"]
        latency = time.perf_counter() - started
        failure = classify_failure({"status": request_status, "error": error, "incomplete_details": provider.get("incomplete_details")}, validation)
        attempt = build_attempt_record(
            request_ref=request_ref,
            prompt_hash=prompt_hash,
            attempt_type=attempt_type,
            attempt_number=attempt_number,
            transport_attempt_number=transport_attempt,
            request_status=request_status,
            raw_text=raw_text,
            validation=validation,
            provider=provider,
            failure=failure,
            latency=latency,
            started_at=started_at,
            run_id=run_id,
        )
        attempts.append(attempt)
        if request_status == "completed" or failure["failure_code"] not in RETRYABLE_FAILURES or transport_attempt > MAX_TRANSPORT_RETRIES:
            return attempts
    return attempts


def invoke_openai(messages: list[dict[str, str]], attempt_type: str) -> dict[str, Any]:
    from openai import OpenAI  # type: ignore[import-not-found]

    client = OpenAI()
    kwargs = {
        "model": REQUEST_MODEL,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }
    if len(messages) == 2 and messages[0]["role"] == "system":
        kwargs["instructions"] = messages[0]["content"]
        kwargs["input"] = messages[1]["content"]
    else:
        kwargs["input"] = messages[0]["content"]
    started = time.perf_counter()
    response = client.responses.create(**kwargs)
    incomplete_details = getattr(response, "incomplete_details", None)
    return {
        "status": getattr(response, "status", "completed"),
        "output_text": response.output_text,
        "incomplete_details": object_to_dict(incomplete_details),
        "metadata": {
            "model": getattr(response, "model", REQUEST_MODEL),
            "request_api": "OpenAI.responses.create",
            "attempt_type": attempt_type,
            "latency_seconds": time.perf_counter() - started,
        },
        "usage": usage_to_dict(getattr(response, "usage", None)),
    }


def build_attempt_record(**kwargs: Any) -> dict[str, Any]:
    request_ref = kwargs["request_ref"]
    provider = kwargs["provider"]
    validation = kwargs["validation"]
    metadata = sanitize_provider_metadata(provider.get("metadata") or {})
    usage = normalize_usage(provider.get("usage"))
    return {
        "schema_version": "phase6g4a_gpt_attempt_v1",
        "run_id": kwargs["run_id"],
        "request_id": request_ref["request_id"],
        "prediction_id": prediction_id(request_ref),
        "rendered_prompt_id": request_ref["rendered_prompt_id"],
        "prediction_example_id": request_ref["prediction_example_id"],
        "condition": request_ref["condition"],
        "model_key": MODEL_KEY,
        "exact_requested_model": REQUEST_MODEL,
        "actual_returned_model": metadata.get("model"),
        "prompt_hash": kwargs["prompt_hash"],
        "inference_config_hash": inference_config_hash(),
        "attempt_type": kwargs["attempt_type"],
        "attempt_number": kwargs["attempt_number"],
        "transport_attempt_number": kwargs["transport_attempt_number"],
        "request_status": kwargs["request_status"],
        "raw_response_text": kwargs["raw_text"],
        "validation_status": validation["status"],
        "response_schema_valid": validation["valid"],
        "validation_errors": validation["errors"],
        "token_usage": usage,
        "latency_seconds": kwargs["latency"],
        "started_at": kwargs["started_at"],
        "ended_at": iso_now(),
        "provider_response_metadata": metadata,
        "incomplete_details": provider.get("incomplete_details"),
        "output_budget_exhausted": kwargs["failure"]["failure_code"] == "output_budget_exhausted",
        "failure_code": kwargs["failure"]["failure_code"],
        "failure_category": kwargs["failure"]["failure_category"],
        "retryable": kwargs["failure"]["retryable"],
        "temperature_sent": False,
        "top_p_sent": False,
        "seed_sent": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }


def finalize_prediction(request_ref: dict[str, Any], attempts: list[dict[str, Any]], run_id: str) -> dict[str, Any]:
    successful = next((row for row in attempts if row["response_schema_valid"]), None)
    primary_valid = next((row for row in attempts if row["attempt_type"] == "primary" and row["response_schema_valid"]), None)
    repair_attempted = any(row["attempt_type"] == "format_repair" for row in attempts)
    if primary_valid:
        status = "valid_primary"
    elif successful:
        status = "valid_after_repair"
    elif any(row.get("failure_code") == "output_budget_exhausted" for row in attempts):
        status = "output_budget_exhausted"
    elif any(row["request_status"] != "completed" for row in attempts):
        status = "backend_failed"
    elif repair_attempted:
        status = "invalid_after_repair"
    else:
        status = "invalid_after_repair"
    return {
        "schema_version": "phase6g4a_gpt_prediction_v1",
        "run_id": run_id,
        "request_id": request_ref["request_id"],
        "prediction_id": prediction_id(request_ref),
        "rendered_prompt_id": request_ref["rendered_prompt_id"],
        "prediction_example_id": request_ref["prediction_example_id"],
        "condition": request_ref["condition"],
        "model_key": MODEL_KEY,
        "exact_requested_model": REQUEST_MODEL,
        "actual_returned_model": (successful or attempts[-1]).get("actual_returned_model"),
        "prompt_hash": request_ref["prompt_hash"],
        "final_status": status,
        "terminal": status in TERMINAL_STATUSES,
        "attempt_count": len(attempts),
        "transport_retry_count": sum(1 for row in attempts if row["transport_attempt_number"] > 1),
        "formatting_repair_count": sum(1 for row in attempts if row["attempt_type"] == "format_repair"),
        "response_schema_valid": bool(successful),
        "raw_final_response_text": (successful or attempts[-1]).get("raw_response_text"),
        "token_usage_totals": sum_usage(attempts),
    }


def build_execution_summary(
    run_manifest: dict[str, Any],
    attempts: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    preflight: dict[str, Any],
    executed_this_invocation: int,
    stopped_after_guarded_batch: bool,
) -> dict[str, Any]:
    statuses = Counter(row["final_status"] for row in predictions)
    conditions = Counter(row["condition"] for row in predictions)
    actual_models = sorted({row.get("actual_returned_model") for row in attempts if row.get("actual_returned_model")})
    terminal_count = sum(1 for row in predictions if row["terminal"])
    prompt_mismatches = sum(1 for row in predictions if not row.get("prompt_hash"))
    duplicate_prediction_count = len(duplicate_values([row["prediction_id"] for row in predictions]))
    unexpected_models = [model for model in actual_models if model != EXPECTED_RETURNED_MODEL]
    summary = {
        "schema_version": "phase6g4a_gpt_execution_summary_v1",
        "run_id": run_manifest["run_id"],
        "preflight_passed": preflight["passed"],
        "exact_requested_model": REQUEST_MODEL,
        "actual_returned_models": actual_models,
        "expected_predictions": 396,
        "guarded_batch_requested": True,
        "guarded_batch_limit": run_manifest["guarded_batch_limit"],
        "predictions_executed_this_invocation": executed_this_invocation,
        "remaining_predictions": 396 - terminal_count,
        "stopped_after_guarded_batch": stopped_after_guarded_batch,
        "attempted_prediction_count": len(predictions),
        "terminal_prediction_count": terminal_count,
        "non_history_count": conditions.get("non_history", 0),
        "personalised_history_count": conditions.get("personalised_history", 0),
        "valid_primary_count": statuses.get("valid_primary", 0),
        "valid_after_repair_count": statuses.get("valid_after_repair", 0),
        "invalid_count": statuses.get("invalid_after_repair", 0),
        "backend_failure_count": statuses.get("backend_failed", 0),
        "output_budget_exhausted_count": statuses.get("output_budget_exhausted", 0),
        "transport_retry_count": sum(row.get("transport_retry_count", 0) for row in predictions),
        "formatting_repair_count": sum(row.get("formatting_repair_count", 0) for row in predictions),
        "prompt_hash_mismatch_count": prompt_mismatches,
        "duplicate_prediction_count": duplicate_prediction_count,
        "unexpected_model_identity_changes": len(unexpected_models),
        "ground_truth_dependency": False,
        "token_usage_totals": sum_usage(attempts),
        "total_api_calls": len(attempts),
        "GPT_PRODUCTION_INFERENCE_COMPLETE": len(predictions) == 396 and terminal_count == 396,
        "ALL_GPT_PREDICTIONS_VALID": len(predictions) == 396 and all(row["response_schema_valid"] for row in predictions),
    }
    return summary


def build_blocked_summary(run_manifest: dict[str, Any], preflight: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "phase6g4a_gpt_execution_summary_v1",
        "run_id": run_manifest["run_id"],
        "preflight_passed": False,
        "preflight_failures": preflight["failures"],
        "exact_requested_model": REQUEST_MODEL,
        "actual_returned_models": [],
        "expected_predictions": 396,
        "guarded_batch_requested": True,
        "guarded_batch_limit": run_manifest["guarded_batch_limit"],
        "predictions_executed_this_invocation": 0,
        "remaining_predictions": 396,
        "stopped_after_guarded_batch": False,
        "attempted_prediction_count": 0,
        "terminal_prediction_count": 0,
        "non_history_count": 0,
        "personalised_history_count": 0,
        "valid_primary_count": 0,
        "valid_after_repair_count": 0,
        "invalid_count": 0,
        "backend_failure_count": 0,
        "output_budget_exhausted_count": 0,
        "transport_retry_count": 0,
        "formatting_repair_count": 0,
        "prompt_hash_mismatch_count": len(preflight["prompt_hash_mismatches"]),
        "duplicate_prediction_count": 0,
        "unexpected_model_identity_changes": 0,
        "ground_truth_dependency": False,
        "token_usage_totals": {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0},
        "total_api_calls": 0,
        "GPT_PRODUCTION_INFERENCE_COMPLETE": False,
        "ALL_GPT_PREDICTIONS_VALID": False,
    }


def build_run_manifest(repo_root: Path, preflight: dict[str, Any], guarded_batch_size: int, output_dir: Path, run_id: str) -> dict[str, Any]:
    shard = load_json(repo_root / GPT_SHARD)
    return {
        "schema_version": "phase6g4a_gpt_run_manifest_v1",
        "run_id": run_id,
        "created_at_utc": iso_now(),
        "run_type": "final_real_gpt_5_5_production_inference",
        "model_key": MODEL_KEY,
        "exact_requested_model": REQUEST_MODEL,
        "expected_returned_model": EXPECTED_RETURNED_MODEL,
        "backend": "OpenAI Responses API",
        "rendered_prompt_dataset": str(RENDERED_PROMPTS).replace("\\", "/"),
        "gpt_shard_manifest": str(GPT_SHARD).replace("\\", "/"),
        "gpt_shard_sha256": sha256_file(repo_root / GPT_SHARD),
        "expected_request_count": 396,
        "shard_request_count": len(shard.get("requests", [])),
        "output_dir": str(output_dir).replace("\\", "/"),
        "guarded_batch_requested": True,
        "guarded_batch_limit": guarded_batch_size,
        "guarded_batch_semantics": "execute at most N previously-unexecuted canonical prediction units, then stop cleanly",
        "preflight": preflight,
        "temperature_sent": False,
        "top_p_sent": False,
        "seed_sent": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "prior_gpt_max_output_tokens": PRIOR_MAX_OUTPUT_TOKENS,
        "configuration_correction_manifest": str(CONFIGURATION_CORRECTION_MANIFEST).replace("\\", "/"),
        "configuration_correction_classification": "GPT-only execution compatibility correction discovered during guarded production validation; not performance tuning.",
        "contains_hidden_ground_truth": False,
    }


def build_failure_summary(attempts: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "phase6g4a_gpt_failure_summary_v1",
        "blocked_by_preflight": False,
        "failure_codes": dict(Counter(row.get("failure_code") for row in attempts if row.get("failure_code"))),
        "final_statuses": dict(Counter(row["final_status"] for row in predictions)),
        "backend_failures": [row for row in predictions if row["final_status"] == "backend_failed"],
        "output_budget_exhausted_predictions": [row for row in predictions if row["final_status"] == "output_budget_exhausted"],
        "invalid_predictions": [row for row in predictions if row["final_status"] == "invalid_after_repair"],
    }


def write_report(path: Path, summary: dict[str, Any], preflight: dict[str, Any]) -> None:
    lines = [
        "# Phase 6G.4A GPT-5.5 Production QC Report",
        "",
        f"- Preflight passed: `{str(preflight['passed']).lower()}`",
        f"- Preflight failures: `{preflight['failures']}`",
        f"- Exact request model: `{REQUEST_MODEL}`",
        f"- Actual returned models: `{summary['actual_returned_models']}`",
        f"- Attempted predictions: `{summary['attempted_prediction_count']}`",
        f"- Terminal predictions: `{summary['terminal_prediction_count']}`",
        f"- Guarded batch requested: `{str(summary.get('guarded_batch_requested', True)).lower()}`",
        f"- Guarded batch limit: `{summary.get('guarded_batch_limit')}`",
        f"- Predictions executed this invocation: `{summary.get('predictions_executed_this_invocation')}`",
        f"- Remaining predictions: `{summary.get('remaining_predictions')}`",
        f"- Stopped after guarded batch: `{str(summary.get('stopped_after_guarded_batch')).lower()}`",
        f"- Non-history: `{summary['non_history_count']}`",
        f"- Personalised-history: `{summary['personalised_history_count']}`",
        f"- Valid primary: `{summary['valid_primary_count']}`",
        f"- Valid after repair: `{summary['valid_after_repair_count']}`",
        f"- Invalid: `{summary['invalid_count']}`",
        f"- Backend failures: `{summary['backend_failure_count']}`",
        f"- Output-budget exhausted: `{summary.get('output_budget_exhausted_count', 0)}`",
        f"- Transport retries: `{summary['transport_retry_count']}`",
        f"- Formatting repairs: `{summary['formatting_repair_count']}`",
        f"- Prompt-hash mismatches: `{summary['prompt_hash_mismatch_count']}`",
        f"- Duplicate predictions: `{summary['duplicate_prediction_count']}`",
        f"- Total input tokens: `{summary['token_usage_totals'].get('input_tokens')}`",
        f"- Total output tokens: `{summary['token_usage_totals'].get('output_tokens')}`",
        f"- Total reasoning tokens: `{summary['token_usage_totals'].get('reasoning_tokens')}`",
        f"- `GPT_PRODUCTION_INFERENCE_COMPLETE`: `{str(summary['GPT_PRODUCTION_INFERENCE_COMPLETE']).lower()}`",
        f"- `ALL_GPT_PREDICTIONS_VALID`: `{str(summary['ALL_GPT_PREDICTIONS_VALID']).lower()}`",
        "",
        "No accuracy, scoring, hidden ground truth, Claude, Llama, or Centaur execution is included.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def prediction_id(request_ref: dict[str, Any]) -> str:
    stable = "::".join([request_ref["rendered_prompt_id"], MODEL_KEY, "phase6g4a_gpt_production"])
    return f"phase6g4a_gpt_pred_{hashlib.sha256(stable.encode('utf-8')).hexdigest()[:32]}"


def inference_config_hash() -> str:
    return sha256_json({"model": REQUEST_MODEL, "max_output_tokens": MAX_OUTPUT_TOKENS, "temperature": "omitted", "top_p": "omitted"})


def object_to_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, dict):
        return value
    return {name: getattr(value, name) for name in dir(value) if not name.startswith("_") and isinstance(getattr(value, name), (int, float, str, bool, type(None), dict))}


def normalize_usage(usage: dict[str, Any] | None) -> dict[str, Any]:
    usage = usage or {}
    output_details = usage.get("output_tokens_details") or {}
    return {
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "reasoning_tokens": output_details.get("reasoning_tokens") or usage.get("reasoning_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }


def usage_to_dict(usage: Any) -> dict[str, Any] | None:
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if hasattr(usage, "dict"):
        return usage.dict()
    if isinstance(usage, dict):
        return usage
    return {name: getattr(usage, name) for name in dir(usage) if not name.startswith("_") and isinstance(getattr(usage, name), (int, float, str, bool, type(None), dict))}


def sum_usage(attempts: list[dict[str, Any]]) -> dict[str, int | None]:
    totals: dict[str, int | None] = {}
    for key in ["input_tokens", "output_tokens", "reasoning_tokens", "total_tokens"]:
        values = [row.get("token_usage", {}).get(key) for row in attempts if row.get("token_usage", {}).get(key) is not None]
        totals[key] = sum(values) if values else (0 if not attempts else None)
    return totals


def load_predictions(path: Path) -> list[dict[str, Any]]:
    return load_jsonl(path)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")


def duplicate_values(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()
