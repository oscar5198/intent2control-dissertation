"""Phase 6G.4A targeted GPT-5.5 production recovery runner.

This module recovers only Run 03 operational failures. Valid Run 03 scientific
predictions are preserved and never rerun.
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
from llm_experiments.inference.phase6g4a_gpt import (
    EXPECTED_RETURNED_MODEL,
    GPT_SHARD,
    MODEL_KEY,
    PROMPT_HASH_MANIFEST,
    RENDERED_PROMPTS,
    REQUEST_MODEL,
    RESPONSE_SCHEMA,
    inspect_openai_api_key,
    normalize_usage,
    object_to_dict,
    sum_usage,
    usage_to_dict,
)
from llm_experiments.inference.records import sanitize_provider_metadata
from llm_experiments.inference.validation import load_response_schema, validate_response_text
from llm_experiments.prompts.freeze_package import verify_prompt_package
from llm_experiments.prompts.render import render_format_repair
from llm_experiments.prompts.prompt_spec import write_json


BASE_OUTPUT_DIR = Path("llm-experiments/outputs/real/phase6g4/gpt")
SOURCE_RUN03_DIR = BASE_OUTPUT_DIR / "corrected_run_03"
OUTPUT_DIR = BASE_OUTPUT_DIR / "recovery_run_04"
RECOVERY_RUN_ID = "phase6g4a_gpt_recovery_run_04"
SOURCE_RUN03_ID = "phase6g4a_gpt_corrected_run_03"
RECOVERY_MANIFEST = OUTPUT_DIR / "recovery_manifest.json"
RECOVERY_ELIGIBILITY = OUTPUT_DIR / "recovery_eligibility.jsonl"
FINAL_GPT_PREDICTIONS = OUTPUT_DIR / "final_gpt_predictions.jsonl"
FINAL_GPT_PROVENANCE = OUTPUT_DIR / "final_gpt_prediction_provenance.jsonl"
FINAL_GPT_COMPLETION_SUMMARY = OUTPUT_DIR / "final_gpt_completion_summary.json"
FINAL_GPT_QC_REPORT = OUTPUT_DIR / "final_gpt_qc_report.md"
CONNECTION_RECOVERY_MAX_OUTPUT_TOKENS = 4096
OUTPUT_BUDGET_RECOVERY_MAX_OUTPUT_TOKENS = 8192
MAX_TRANSPORT_RETRIES = 2
MAX_FORMAT_REPAIRS = 1
TERMINAL_RECOVERY_STATUSES = {
    "valid_primary",
    "valid_after_repair",
    "invalid_after_repair",
    "backend_failed",
    "output_budget_exhausted",
    "quota_exhausted",
}


def run_gpt_recovery(repo_root: Path, guarded_batch_size: int = 6, output_dir: Path = OUTPUT_DIR, run_id: str = RECOVERY_RUN_ID) -> dict[str, Any]:
    out = repo_root / output_dir
    out.mkdir(parents=True, exist_ok=True)
    preflight = run_preflight(repo_root, output_dir)
    eligibility = build_recovery_eligibility(repo_root)
    write_jsonl(out / "recovery_eligibility.jsonl", eligibility)
    manifest = build_recovery_manifest(repo_root, preflight, eligibility, guarded_batch_size, output_dir, run_id)
    write_json(out / "recovery_manifest.json", manifest)
    if not preflight["passed"]:
        summary = build_recovery_summary(manifest, [], [], preflight, 0, False, False)
        write_json(out / "preflight_report.json", preflight)
        write_json(out / "execution_summary.json", summary)
        write_json(out / "failure_summary.json", {"schema_version": "phase6g4a_gpt_recovery_failure_summary_v1", "blocked_by_preflight": True, "failures": preflight["failures"]})
        write_final_merge_artifacts(repo_root, out, eligibility, [], summary)
        return summary

    response_schema = load_response_schema(repo_root / RESPONSE_SCHEMA)
    rendered = {row["rendered_prompt_id"]: row for row in load_jsonl(repo_root / RENDERED_PROMPTS)}
    existing_predictions = load_jsonl(out / "predictions.jsonl")
    successful_recovery_source_ids = {
        row["source_run03_prediction_id"]
        for row in existing_predictions
        if row.get("final_status") in {"valid_primary", "valid_after_repair"}
    }
    terminal_recovery_source_ids = {
        row["source_run03_prediction_id"]
        for row in existing_predictions
        if row.get("final_status") in TERMINAL_RECOVERY_STATUSES
    }
    attempts = load_jsonl(out / "attempt_log.jsonl")
    executed_this_invocation = 0
    stopped_after_guarded_batch = False
    halted_due_quota = False

    for unit in eligibility:
        if unit["source_run03_prediction_id"] in successful_recovery_source_ids:
            continue
        if unit["source_run03_prediction_id"] in terminal_recovery_source_ids:
            continue
        if executed_this_invocation >= guarded_batch_size:
            stopped_after_guarded_batch = True
            break
        rendered_prompt = rendered[unit["rendered_prompt_id"]]
        prediction_attempts = execute_recovery_prediction(unit, rendered_prompt, response_schema, run_id)
        attempts.extend(prediction_attempts)
        append_jsonl(out / "attempt_log.jsonl", prediction_attempts)
        prediction = finalize_recovery_prediction(unit, prediction_attempts, run_id)
        append_jsonl(out / "predictions.jsonl", [prediction])
        terminal_recovery_source_ids.add(unit["source_run03_prediction_id"])
        if prediction["final_status"] in {"valid_primary", "valid_after_repair"}:
            successful_recovery_source_ids.add(unit["source_run03_prediction_id"])
        executed_this_invocation += 1
        if any(row.get("failure_code") == "quota_exhausted" for row in prediction_attempts):
            halted_due_quota = True
            break

    predictions = load_jsonl(out / "predictions.jsonl")
    summary = build_recovery_summary(manifest, attempts, predictions, preflight, executed_this_invocation, stopped_after_guarded_batch, halted_due_quota)
    write_json(out / "execution_summary.json", summary)
    write_json(out / "failure_summary.json", build_failure_summary(attempts, predictions))
    write_final_merge_artifacts(repo_root, out, eligibility, predictions, summary)
    return summary


def run_preflight(repo_root: Path, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    failures: list[str] = []
    prompt_verification = verify_prompt_package(repo_root)
    source_summary = load_json(repo_root / SOURCE_RUN03_DIR / "execution_summary.json")
    source_manifest = load_json(repo_root / SOURCE_RUN03_DIR / "run_manifest.json")
    source_predictions = load_jsonl(repo_root / SOURCE_RUN03_DIR / "predictions.jsonl")
    source_attempts = load_jsonl(repo_root / SOURCE_RUN03_DIR / "attempt_log.jsonl")
    shard = load_json(repo_root / GPT_SHARD)
    hash_manifest = load_json(repo_root / PROMPT_HASH_MANIFEST)
    rendered = {row["rendered_prompt_id"]: row for row in load_jsonl(repo_root / RENDERED_PROMPTS)}
    prompt_hashes = {row["rendered_prompt_id"]: row["message_payload_sha256"] for row in hash_manifest["records"]}
    prompt_hash_mismatches = verify_source_prompt_hashes(shard["requests"], source_predictions, rendered, prompt_hashes)
    statuses = Counter(row["final_status"] for row in source_predictions)
    key_state = inspect_openai_api_key()
    checks = {
        "phase6d_prompt_package_frozen": bool(prompt_verification.get("PHASE6D_PROMPT_PACKAGE_FROZEN")),
        "phase6g3_prompt_freeze_ready": bool(load_json(repo_root / "llm-experiments/outputs/real/phase6g3/phase6g3_freeze_manifest.json").get("REAL_PRODUCTION_PROMPTS_FROZEN")),
        "source_run03_id_valid": source_manifest.get("run_id") == SOURCE_RUN03_ID and source_summary.get("run_id") == SOURCE_RUN03_ID,
        "source_run03_count_valid": len(source_predictions) == 396 and source_summary.get("attempted_prediction_count") == 396,
        "source_run03_status_counts_valid": statuses == {"valid_primary": 264, "backend_failed": 126, "output_budget_exhausted": 6},
        "source_run03_attempt_count_valid": len(source_attempts) == 648,
        "source_run03_prompt_hashes_valid": not prompt_hash_mismatches,
        "source_run03_model_config_valid": source_manifest.get("exact_requested_model") == REQUEST_MODEL and source_manifest.get("expected_returned_model") == EXPECTED_RETURNED_MODEL and source_manifest.get("max_output_tokens") == 4096,
        "gpt_shard_count_valid": len(shard.get("requests", [])) == 396,
        "openai_api_key_present": key_state["present"],
        "openai_api_key_has_no_leading_or_trailing_whitespace": key_state["has_no_leading_or_trailing_whitespace"],
        "openai_api_key_contains_no_cr_or_lf": key_state["contains_no_cr_or_lf"],
        "openai_sdk_installed": bool(util.find_spec("openai")),
        "output_directory_recovery_namespace": str(output_dir).replace("\\", "/").endswith("phase6g4/gpt/recovery_run_04"),
        "no_hidden_ground_truth_loaded": not shard.get("contains_hidden_ground_truth", False),
    }
    failures = [key for key, value in checks.items() if not value]
    return {
        "schema_version": "phase6g4a_gpt_recovery_preflight_v1",
        "checked_at_utc": iso_now(),
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "source_status_counts": dict(sorted(statuses.items())),
        "prompt_hash_mismatches": prompt_hash_mismatches,
        "credential_policy": "OPENAI_API_KEY presence checked as boolean only; secret value is never logged.",
        "ground_truth_dependency": False,
    }


def build_recovery_eligibility(repo_root: Path) -> list[dict[str, Any]]:
    source_predictions = load_jsonl(repo_root / SOURCE_RUN03_DIR / "predictions.jsonl")
    shard = load_json(repo_root / GPT_SHARD)
    requests_by_id = {row["request_id"]: row for row in shard["requests"]}
    statuses = Counter(row["final_status"] for row in source_predictions)
    if statuses != {"valid_primary": 264, "backend_failed": 126, "output_budget_exhausted": 6}:
        raise AssertionError(f"Unexpected Run 03 status counts: {dict(statuses)}")
    eligible = []
    preserved_valid = 0
    for source in source_predictions:
        request = requests_by_id[source["request_id"]]
        verify_prediction_against_shard(source, request)
        if source["final_status"] == "valid_primary":
            preserved_valid += 1
            continue
        if source["final_status"] == "backend_failed":
            reason = "quota_transport_recovery"
            max_tokens = CONNECTION_RECOVERY_MAX_OUTPUT_TOKENS
        elif source["final_status"] == "output_budget_exhausted":
            reason = "output_budget_recovery"
            max_tokens = OUTPUT_BUDGET_RECOVERY_MAX_OUTPUT_TOKENS
        else:
            continue
        eligible.append({
            "schema_version": "phase6g4a_gpt_recovery_eligibility_v1",
            "recovery_unit_id": recovery_unit_id(source),
            "recovery_prediction_id": recovery_prediction_id(source),
            "source_run03_id": SOURCE_RUN03_ID,
            "source_run03_prediction_id": source["prediction_id"],
            "source_run03_final_status": source["final_status"],
            "recovery_eligibility_reason": reason,
            "request_id": source["request_id"],
            "prediction_example_id": source["prediction_example_id"],
            "condition": source["condition"],
            "rendered_prompt_id": source["rendered_prompt_id"],
            "prompt_hash": source["prompt_hash"],
            "model_key": MODEL_KEY,
            "exact_requested_model": REQUEST_MODEL,
            "expected_returned_model": EXPECTED_RETURNED_MODEL,
            "response_schema_version": request["response_schema_version"],
            "max_output_tokens": max_tokens,
        })
    if preserved_valid != 264 or len(eligible) != 132 or preserved_valid + len(eligible) != 396:
        raise AssertionError("Run 04 recovery eligibility does not satisfy 264 + 132 = 396")
    if Counter(row["recovery_eligibility_reason"] for row in eligible) != {"quota_transport_recovery": 126, "output_budget_recovery": 6}:
        raise AssertionError("Unexpected Run 04 recovery reason counts")
    return eligible


def verify_prediction_against_shard(prediction: dict[str, Any], request: dict[str, Any]) -> None:
    expected = {
        "prediction_example_id": request["prediction_example_id"],
        "condition": request["condition"],
        "rendered_prompt_id": request["rendered_prompt_id"],
        "prompt_hash": request["prompt_hash"],
        "model_key": request["model_key"],
    }
    observed = {key: prediction.get(key) for key in expected}
    if observed != expected or request.get("response_schema_version") != "preference_prediction_response_v1":
        raise AssertionError(f"Run 03 prediction does not match frozen shard: {prediction.get('request_id')}")


def verify_source_prompt_hashes(requests: list[dict[str, Any]], predictions: list[dict[str, Any]], rendered: dict[str, Any], prompt_hashes: dict[str, str]) -> list[str]:
    prediction_by_request = {row["request_id"]: row for row in predictions}
    mismatches = []
    for request in requests:
        rendered_prompt = rendered.get(request["rendered_prompt_id"])
        prediction = prediction_by_request.get(request["request_id"])
        expected_hash = prompt_hashes.get(request["rendered_prompt_id"])
        if prediction is None or rendered_prompt is None or expected_hash != sha256_json(rendered_prompt["messages"]) or request.get("prompt_hash") != expected_hash or prediction.get("prompt_hash") != expected_hash:
            mismatches.append(request["request_id"])
    return mismatches


def build_recovery_manifest(repo_root: Path, preflight: dict[str, Any], eligibility: list[dict[str, Any]], guarded_batch_size: int, output_dir: Path, run_id: str) -> dict[str, Any]:
    reasons = Counter(row["recovery_eligibility_reason"] for row in eligibility)
    return {
        "schema_version": "phase6g4a_gpt_recovery_manifest_v1",
        "created_at_utc": iso_now(),
        "run_id": run_id,
        "source_run03_id": SOURCE_RUN03_ID,
        "source_run03_dir": str(SOURCE_RUN03_DIR).replace("\\", "/"),
        "source_run03_predictions_sha256": sha256_file(repo_root / SOURCE_RUN03_DIR / "predictions.jsonl"),
        "source_run03_attempt_log_sha256": sha256_file(repo_root / SOURCE_RUN03_DIR / "attempt_log.jsonl"),
        "frozen_prompt_dataset": str(RENDERED_PROMPTS).replace("\\", "/"),
        "frozen_prompt_dataset_sha256": sha256_file(repo_root / RENDERED_PROMPTS),
        "gpt_shard_manifest": str(GPT_SHARD).replace("\\", "/"),
        "gpt_shard_manifest_sha256": sha256_file(repo_root / GPT_SHARD),
        "output_dir": str(output_dir).replace("\\", "/"),
        "preserved_valid_count": 264,
        "transport_quota_recovery_count": reasons.get("quota_transport_recovery", 0),
        "output_budget_recovery_count": reasons.get("output_budget_recovery", 0),
        "total_recovery_count": len(eligibility),
        "eligibility_assertion": "264 preserved valid + 132 recovery eligible = 396 canonical GPT slots",
        "max_output_tokens_by_recovery_class": {
            "quota_transport_recovery": CONNECTION_RECOVERY_MAX_OUTPUT_TOKENS,
            "output_budget_recovery": OUTPUT_BUDGET_RECOVERY_MAX_OUTPUT_TOKENS,
        },
        "exact_requested_model": REQUEST_MODEL,
        "expected_returned_model": EXPECTED_RETURNED_MODEL,
        "response_schema_version": "preference_prediction_response_v1",
        "reasoning_policy": "provider_native_reasoning; no reasoning.effort, no chain-of-thought request, no reasoning summaries",
        "temperature_sent": False,
        "top_p_sent": False,
        "seed_sent": False,
        "guarded_batch_requested": True,
        "guarded_batch_limit": guarded_batch_size,
        "guarded_batch_semantics": "execute at most N unresolved recovery prediction units during this invocation",
        "quota_diagnosis": "Later live diagnosis established OpenAI HTTP 429 insufficient_quota/credit_balance_exhausted after Run 03; historical Run 03 connection_error logs are preserved unchanged.",
        "operational_recovery_rationale": "Eligibility is based only on Run 03 operational terminal status, never prediction correctness or human outcomes.",
        "prompt_hash_verification": {"passed": not preflight["prompt_hash_mismatches"], "mismatches": preflight["prompt_hash_mismatches"]},
        "preflight": preflight,
        "no_ground_truth_dependency": True,
    }


def execute_recovery_prediction(unit: dict[str, Any], rendered_prompt: dict[str, Any], response_schema: dict[str, Any], run_id: str) -> list[dict[str, Any]]:
    attempts = []
    primary_attempt = call_with_transport_retries(unit, rendered_prompt, response_schema, "primary", 1, run_id)
    attempts.extend(primary_attempt)
    final_primary = primary_attempt[-1]
    if should_repair(final_primary["validation_status"], final_primary["request_status"], final_primary.get("raw_response_text")):
        repair_messages = render_format_repair(final_primary["raw_response_text"], response_schema)["messages"]
        repair_attempts = call_with_transport_retries(unit, {"messages": repair_messages}, response_schema, "format_repair", 2, run_id)
        attempts.extend(repair_attempts[: MAX_FORMAT_REPAIRS + MAX_TRANSPORT_RETRIES])
    return attempts


def call_with_transport_retries(unit: dict[str, Any], rendered_prompt: dict[str, Any], response_schema: dict[str, Any], attempt_type: str, attempt_number: int, run_id: str) -> list[dict[str, Any]]:
    attempts = []
    for transport_attempt in range(1, MAX_TRANSPORT_RETRIES + 2):
        started = time.perf_counter()
        started_at = iso_now()
        try:
            provider = invoke_openai(rendered_prompt["messages"], attempt_type, unit["max_output_tokens"])
            raw_text = provider.get("output_text")
            validation = validate_response_text(raw_text, response_schema)
            request_status = provider.get("status", "completed")
            error = provider.get("error")
        except Exception as exc:  # pragma: no cover - only hit during live provider errors
            raw_text = None
            validation = validate_response_text(None, response_schema)
            request_status = "error"
            error = error_from_exception(exc)
            provider = {"metadata": {}, "usage": None, "incomplete_details": None, "error": error}
        latency = time.perf_counter() - started
        failure = classify_failure({"status": request_status, "error": error, "incomplete_details": provider.get("incomplete_details")}, validation)
        attempt = build_attempt_record(unit, attempt_type, attempt_number, transport_attempt, request_status, raw_text, validation, provider, failure, latency, started_at, run_id)
        attempts.append(attempt)
        if failure["failure_code"] == "quota_exhausted":
            return attempts
        if request_status == "completed" or failure["failure_code"] not in RETRYABLE_FAILURES or transport_attempt > MAX_TRANSPORT_RETRIES:
            return attempts
    return attempts


def invoke_openai(messages: list[dict[str, str]], attempt_type: str, max_output_tokens: int) -> dict[str, Any]:
    from openai import OpenAI  # type: ignore[import-not-found]

    client = OpenAI()
    kwargs = {"model": REQUEST_MODEL, "max_output_tokens": max_output_tokens}
    if len(messages) == 2 and messages[0]["role"] == "system":
        kwargs["instructions"] = messages[0]["content"]
        kwargs["input"] = messages[1]["content"]
    else:
        kwargs["input"] = messages[0]["content"]
    started = time.perf_counter()
    response = client.responses.create(**kwargs)
    return {
        "status": getattr(response, "status", "completed"),
        "output_text": response.output_text,
        "incomplete_details": object_to_dict(getattr(response, "incomplete_details", None)),
        "metadata": {"model": getattr(response, "model", REQUEST_MODEL), "request_api": "OpenAI.responses.create", "attempt_type": attempt_type, "latency_seconds": time.perf_counter() - started},
        "usage": usage_to_dict(getattr(response, "usage", None)),
    }


def error_from_exception(exc: Exception) -> dict[str, Any]:
    response = getattr(exc, "response", None)
    body = getattr(exc, "body", None) or getattr(exc, "error", None) or {}
    if hasattr(response, "json"):
        try:
            body = response.json()
        except Exception:
            pass
    error = body.get("error", body) if isinstance(body, dict) else {}
    return {
        "type": error.get("type") or getattr(exc, "type", None) or "connection_error",
        "code": error.get("code") or getattr(exc, "code", None),
        "message": error.get("message") or str(exc),
        "http_status_code": getattr(exc, "status_code", None) or getattr(response, "status_code", None),
    }


def build_attempt_record(unit: dict[str, Any], attempt_type: str, attempt_number: int, transport_attempt: int, request_status: str, raw_text: str | None, validation: dict[str, Any], provider: dict[str, Any], failure: dict[str, Any], latency: float, started_at: str, run_id: str) -> dict[str, Any]:
    metadata = sanitize_provider_metadata(provider.get("metadata") or {})
    return {
        "schema_version": "phase6g4a_gpt_recovery_attempt_v1",
        "run_id": run_id,
        "request_id": unit["request_id"],
        "recovery_unit_id": unit["recovery_unit_id"],
        "prediction_id": unit["recovery_prediction_id"],
        "source_run03_prediction_id": unit["source_run03_prediction_id"],
        "recovery_eligibility_reason": unit["recovery_eligibility_reason"],
        "rendered_prompt_id": unit["rendered_prompt_id"],
        "prompt_hash": unit["prompt_hash"],
        "prediction_example_id": unit["prediction_example_id"],
        "condition": unit["condition"],
        "model_key": MODEL_KEY,
        "exact_requested_model": REQUEST_MODEL,
        "actual_returned_model": metadata.get("model"),
        "max_output_tokens": unit["max_output_tokens"],
        "attempt_type": attempt_type,
        "attempt_number": attempt_number,
        "transport_attempt_number": transport_attempt,
        "request_status": request_status,
        "validation_status": validation["status"],
        "response_schema_valid": validation["valid"],
        "validation_errors": validation["errors"],
        "raw_response_text": raw_text,
        "token_usage": normalize_usage(provider.get("usage")),
        "latency_seconds": latency,
        "started_at": started_at,
        "ended_at": iso_now(),
        "provider_response_metadata": metadata,
        "incomplete_details": provider.get("incomplete_details"),
        "failure_code": failure["failure_code"],
        "failure_category": failure["failure_category"],
        "retryable": failure["retryable"],
        "temperature_sent": False,
        "top_p_sent": False,
        "seed_sent": False,
        "reasoning_effort_sent": False,
    }


def finalize_recovery_prediction(unit: dict[str, Any], attempts: list[dict[str, Any]], run_id: str) -> dict[str, Any]:
    successful = next((row for row in attempts if row["response_schema_valid"]), None)
    primary_valid = next((row for row in attempts if row["attempt_type"] == "primary" and row["response_schema_valid"]), None)
    if primary_valid:
        status = "valid_primary"
    elif successful:
        status = "valid_after_repair"
    elif any(row.get("failure_code") == "quota_exhausted" for row in attempts):
        status = "quota_exhausted"
    elif any(row.get("failure_code") == "output_budget_exhausted" for row in attempts):
        status = "output_budget_exhausted"
    elif any(row["request_status"] != "completed" for row in attempts):
        status = "backend_failed"
    else:
        status = "invalid_after_repair"
    return {
        "schema_version": "phase6g4a_gpt_recovery_prediction_v1",
        "run_id": run_id,
        "request_id": unit["request_id"],
        "prediction_id": unit["recovery_prediction_id"],
        "source_run03_prediction_id": unit["source_run03_prediction_id"],
        "recovery_eligibility_reason": unit["recovery_eligibility_reason"],
        "rendered_prompt_id": unit["rendered_prompt_id"],
        "prediction_example_id": unit["prediction_example_id"],
        "condition": unit["condition"],
        "model_key": MODEL_KEY,
        "exact_requested_model": REQUEST_MODEL,
        "actual_returned_model": (successful or attempts[-1]).get("actual_returned_model"),
        "prompt_hash": unit["prompt_hash"],
        "max_output_tokens": unit["max_output_tokens"],
        "final_status": status,
        "terminal": status in TERMINAL_RECOVERY_STATUSES,
        "attempt_count": len(attempts),
        "transport_retry_count": sum(1 for row in attempts if row["transport_attempt_number"] > 1),
        "formatting_repair_count": sum(1 for row in attempts if row["attempt_type"] == "format_repair"),
        "response_schema_valid": bool(successful),
        "raw_final_response_text": (successful or attempts[-1]).get("raw_response_text"),
        "token_usage_totals": sum_usage(attempts),
    }


def build_recovery_summary(manifest: dict[str, Any], attempts: list[dict[str, Any]], predictions: list[dict[str, Any]], preflight: dict[str, Any], executed_this_invocation: int, stopped_after_guarded_batch: bool, halted_due_quota: bool) -> dict[str, Any]:
    statuses = Counter(row["final_status"] for row in predictions)
    valid_count = statuses.get("valid_primary", 0) + statuses.get("valid_after_repair", 0)
    terminal_count = sum(1 for row in predictions if row["terminal"])
    return {
        "schema_version": "phase6g4a_gpt_recovery_execution_summary_v1",
        "run_id": manifest["run_id"],
        "source_run03_id": SOURCE_RUN03_ID,
        "preflight_passed": preflight["passed"],
        "expected_recovery_predictions": 132,
        "guarded_batch_requested": True,
        "guarded_batch_limit": manifest["guarded_batch_limit"],
        "recovery_predictions_executed_this_invocation": executed_this_invocation,
        "attempted_recovery_prediction_count": len(predictions),
        "terminal_recovery_prediction_count": terminal_count,
        "valid_recovery_prediction_count": valid_count,
        "remaining_unresolved_recovery_predictions": 132 - terminal_count,
        "stopped_after_guarded_batch": stopped_after_guarded_batch,
        "halted_due_quota_exhaustion": halted_due_quota,
        "valid_primary_count": statuses.get("valid_primary", 0),
        "valid_after_repair_count": statuses.get("valid_after_repair", 0),
        "backend_failure_count": statuses.get("backend_failed", 0),
        "output_budget_exhausted_count": statuses.get("output_budget_exhausted", 0),
        "quota_exhausted_count": statuses.get("quota_exhausted", 0),
        "invalid_after_repair_count": statuses.get("invalid_after_repair", 0),
        "transport_retry_count": sum(row.get("transport_retry_count", 0) for row in predictions),
        "formatting_repair_count": sum(row.get("formatting_repair_count", 0) for row in predictions),
        "token_usage_totals": sum_usage(attempts),
        "total_api_calls": len(attempts),
        "ground_truth_dependency": False,
        "GPT_RECOVERY_RUN_COMPLETE": terminal_count == 132,
        "ALL_GPT_RECOVERY_PREDICTIONS_VALID": len(predictions) == 132 and valid_count == 132,
    }


def build_failure_summary(attempts: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "phase6g4a_gpt_recovery_failure_summary_v1",
        "blocked_by_preflight": False,
        "failure_codes": dict(Counter(row.get("failure_code") for row in attempts if row.get("failure_code"))),
        "final_statuses": dict(Counter(row["final_status"] for row in predictions)),
        "non_valid_recovery_predictions": [row for row in predictions if not row["response_schema_valid"]],
    }


def write_final_merge_artifacts(repo_root: Path, out: Path, eligibility: list[dict[str, Any]], recovery_predictions: list[dict[str, Any]], recovery_summary: dict[str, Any]) -> None:
    source_predictions = load_jsonl(repo_root / SOURCE_RUN03_DIR / "predictions.jsonl")
    source_by_request = {row["request_id"]: row for row in source_predictions}
    recovery_by_source = {
        row["source_run03_prediction_id"]: row
        for row in recovery_predictions
        if row.get("final_status") in {"valid_primary", "valid_after_repair"}
    }
    eligibility_by_source = {row["source_run03_prediction_id"]: row for row in eligibility}
    final_rows = []
    provenance_rows = []
    for source in source_predictions:
        if source["final_status"] in {"valid_primary", "valid_after_repair"}:
            final = dict(source)
            source_type = "run03_original_valid_prediction"
            selected_run_id = SOURCE_RUN03_ID
        elif source["prediction_id"] in recovery_by_source:
            final = dict(recovery_by_source[source["prediction_id"]])
            source_type = "run04_recovered_prediction"
            selected_run_id = RECOVERY_RUN_ID
        else:
            final = build_unresolved_final_record(source, eligibility_by_source[source["prediction_id"]])
            source_type = "run03_non_valid_pending_or_non_valid_recovery"
            selected_run_id = final["run_id"]
        final_rows.append(final)
        provenance_rows.append({
            "schema_version": "phase6g4a_gpt_final_prediction_provenance_v1",
            "request_id": source["request_id"],
            "canonical_prediction_slot_id": source["prediction_id"],
            "selected_prediction_id": final["prediction_id"],
            "selected_run_id": selected_run_id,
            "source_type": source_type,
            "run03_prediction_id": source["prediction_id"],
            "run03_final_status": source["final_status"],
            "run04_recovery_prediction_id": recovery_by_source.get(source["prediction_id"], {}).get("prediction_id"),
            "merge_precedence": "valid Run 03 wins; otherwise valid Run 04 fills failed Run 03 slot; otherwise preserve unresolved/non-valid state",
        })
    if len(final_rows) != 396 or len({row["request_id"] for row in final_rows}) != 396:
        raise AssertionError("Final GPT merge must contain exactly one row per frozen request")
    write_jsonl(out / "final_gpt_predictions.jsonl", final_rows)
    write_jsonl(out / "final_gpt_prediction_provenance.jsonl", provenance_rows)
    write_json(out / "final_gpt_completion_summary.json", build_final_completion_summary(final_rows, provenance_rows, recovery_summary))
    write_final_report(out / "final_gpt_qc_report.md", final_rows, provenance_rows, recovery_summary)


def build_unresolved_final_record(source: dict[str, Any], unit: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "phase6g4a_gpt_final_unresolved_prediction_v1",
        "run_id": SOURCE_RUN03_ID,
        "request_id": source["request_id"],
        "prediction_id": source["prediction_id"],
        "source_run03_prediction_id": source["prediction_id"],
        "recovery_eligibility_reason": unit["recovery_eligibility_reason"],
        "rendered_prompt_id": source["rendered_prompt_id"],
        "prediction_example_id": source["prediction_example_id"],
        "condition": source["condition"],
        "model_key": MODEL_KEY,
        "exact_requested_model": REQUEST_MODEL,
        "actual_returned_model": source.get("actual_returned_model"),
        "prompt_hash": source["prompt_hash"],
        "final_status": source["final_status"],
        "response_schema_valid": False,
        "raw_final_response_text": source.get("raw_final_response_text"),
        "token_usage_totals": source.get("token_usage_totals"),
        "terminal": True,
    }


def build_final_completion_summary(final_rows: list[dict[str, Any]], provenance_rows: list[dict[str, Any]], recovery_summary: dict[str, Any]) -> dict[str, Any]:
    statuses = Counter(row["final_status"] for row in final_rows)
    sources = Counter(row["source_type"] for row in provenance_rows)
    return {
        "schema_version": "phase6g4a_gpt_final_completion_summary_v1",
        "source_run03_id": SOURCE_RUN03_ID,
        "recovery_run_id": RECOVERY_RUN_ID,
        "canonical_prediction_count": len(final_rows),
        "unique_request_count": len({row["request_id"] for row in final_rows}),
        "status_counts": dict(sorted(statuses.items())),
        "source_counts": dict(sorted(sources.items())),
        "preserved_valid_run03_count": sources.get("run03_original_valid_prediction", 0),
        "recovered_valid_run04_count": sources.get("run04_recovered_prediction", 0),
        "unresolved_or_non_valid_count": sources.get("run03_non_valid_pending_or_non_valid_recovery", 0),
        "ground_truth_dependency": False,
        "recovery_summary": recovery_summary,
    }


def write_final_report(path: Path, final_rows: list[dict[str, Any]], provenance_rows: list[dict[str, Any]], recovery_summary: dict[str, Any]) -> None:
    status_counts = Counter(row["final_status"] for row in final_rows)
    source_counts = Counter(row["source_type"] for row in provenance_rows)
    lines = [
        "# Phase 6G.4A GPT Recovery Run 04 QC Report",
        "",
        f"- Source Run 03: `{SOURCE_RUN03_ID}`",
        f"- Recovery Run 04: `{RECOVERY_RUN_ID}`",
        f"- Canonical GPT slots: `{len(final_rows)}`",
        f"- Preserved valid Run 03 predictions: `{source_counts.get('run03_original_valid_prediction', 0)}`",
        f"- Valid Run 04 recovered predictions: `{source_counts.get('run04_recovered_prediction', 0)}`",
        f"- Unresolved/non-valid slots: `{source_counts.get('run03_non_valid_pending_or_non_valid_recovery', 0)}`",
        f"- Final status counts: `{dict(sorted(status_counts.items()))}`",
        f"- Recovery executed this invocation: `{recovery_summary['recovery_predictions_executed_this_invocation']}`",
        f"- Halted due quota: `{str(recovery_summary['halted_due_quota_exhaustion']).lower()}`",
        "",
        "No scoring, human ground truth, Claude, Llama, or Centaur execution is included.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def recovery_unit_id(source: dict[str, Any]) -> str:
    return "phase6g4a_gpt_recovery_unit_" + hashlib.sha256(f"{SOURCE_RUN03_ID}::{source['prediction_id']}::{source['final_status']}".encode("utf-8")).hexdigest()[:32]


def recovery_prediction_id(source: dict[str, Any]) -> str:
    return "phase6g4a_gpt_recovery_pred_" + hashlib.sha256(f"{RECOVERY_RUN_ID}::{source['prediction_id']}".encode("utf-8")).hexdigest()[:32]


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()
