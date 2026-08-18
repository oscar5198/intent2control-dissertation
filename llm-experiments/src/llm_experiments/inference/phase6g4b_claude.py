"""Phase 6G.4B Claude Sonnet 5 production inference runner."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
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
from llm_experiments.prompts.prompt_spec import write_json


SCHEMA_VERSION = "phase6g4b_claude_production_inference_v1"
OUTPUT_DIR = Path("llm-experiments/outputs/real/phase6g4/claude")
RENDERED_PROMPTS = Path("llm-experiments/outputs/real/phase6g3/phase6g3_real_rendered_prompts.jsonl")
CLAUDE_SHARD = Path("llm-experiments/outputs/real/phase6g3/phase6g3_qmul_claude_shard_manifest.json")
PROMPT_HASH_MANIFEST = Path("llm-experiments/outputs/real/phase6g3/phase6g3_prompt_hash_manifest.json")
PHASE6G3_FREEZE = Path("llm-experiments/outputs/real/phase6g3/phase6g3_freeze_manifest.json")
PHASE6G2D_READINESS = Path("llm-experiments/outputs/real/phase6g2d/phase6g2d_final_readiness.json")
PHASE6G1_GATE = Path("llm-experiments/outputs/real/phase6b/production_readiness_gate.json")
RESPONSE_SCHEMA = Path("llm-experiments/schema/preference_prediction_response_v1.json")
RUN_ID = "phase6g4b_claude_production_run_01"
MODEL_KEY = "claude"
SHARD_MODEL_KEY = "claude_sonnet"
REQUEST_MODEL = "claude-sonnet-5"
MAX_TOKENS = 1024
MAX_TRANSPORT_RETRIES = 2
MAX_FORMAT_REPAIRS = 1
TERMINAL_STATUSES = {"valid_primary", "valid_after_repair", "invalid_after_repair", "backend_failed", "output_budget_exhausted", "quota_exhausted", "refusal"}
NORMALIZER_VERSION = "phase6g4b_claude_response_normalizer_v1"


def run_claude_production(repo_root: Path, guarded_batch_size: int = 5, output_dir: Path = OUTPUT_DIR, run_id: str = RUN_ID) -> dict[str, Any]:
    out = repo_root / output_dir
    out.mkdir(parents=True, exist_ok=True)
    preflight = run_preflight(repo_root, output_dir)
    run_manifest = build_run_manifest(repo_root, preflight, guarded_batch_size, output_dir, run_id)
    write_json(out / "run_manifest.json", run_manifest)
    if not preflight["passed"]:
        summary = build_blocked_summary(run_manifest, preflight)
        write_json(out / "preflight_report.json", preflight)
        write_json(out / "execution_summary.json", summary)
        write_json(out / "failure_summary.json", {"schema_version": "phase6g4b_claude_failure_summary_v1", "blocked_by_preflight": True, "failures": preflight["failures"]})
        write_report(out / "claude_production_qc_report.md", summary, preflight)
        return summary

    response_schema = load_response_schema(repo_root / RESPONSE_SCHEMA)
    rendered = {row["rendered_prompt_id"]: row for row in load_jsonl(repo_root / RENDERED_PROMPTS)}
    shard = load_json(repo_root / CLAUDE_SHARD)
    prompt_hashes = {row["rendered_prompt_id"]: row["message_payload_sha256"] for row in load_json(repo_root / PROMPT_HASH_MANIFEST)["records"]}
    existing_predictions = load_jsonl(out / "predictions.jsonl")
    terminal_ids = {row["request_id"] for row in existing_predictions if row.get("final_status") in TERMINAL_STATUSES}
    attempts = load_jsonl(out / "attempt_log.jsonl")
    actual_models = {row.get("actual_returned_model") for row in attempts if row.get("actual_returned_model")}
    executed_this_invocation = 0
    stopped_after_guarded_batch = False
    halted_due_quota = False

    for request_ref in shard["requests"]:
        if request_ref["request_id"] in terminal_ids:
            continue
        if executed_this_invocation >= guarded_batch_size:
            stopped_after_guarded_batch = True
            break
        if actual_models and actual_models != {REQUEST_MODEL}:
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
        if any(row.get("failure_code") == "quota_exhausted" for row in prediction_attempts):
            halted_due_quota = True
            break

    predictions = load_jsonl(out / "predictions.jsonl")
    summary = build_execution_summary(run_manifest, attempts, predictions, preflight, executed_this_invocation, stopped_after_guarded_batch, halted_due_quota)
    write_json(out / "execution_summary.json", summary)
    write_json(out / "failure_summary.json", build_failure_summary(attempts, predictions))
    write_report(out / "claude_production_qc_report.md", summary, preflight)
    return summary


def run_preflight(repo_root: Path, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    prompt_verification = verify_prompt_package(repo_root)
    phase6g1 = load_json(repo_root / PHASE6G1_GATE)
    phase6g2d = load_json(repo_root / PHASE6G2D_READINESS)
    phase6g3 = load_json(repo_root / PHASE6G3_FREEZE)
    shard = load_json(repo_root / CLAUDE_SHARD)
    hash_manifest = load_json(repo_root / PROMPT_HASH_MANIFEST)
    rendered = {row["rendered_prompt_id"]: row for row in load_jsonl(repo_root / RENDERED_PROMPTS)}
    requests = shard.get("requests", [])
    prompt_hashes = {row["rendered_prompt_id"]: row["message_payload_sha256"] for row in hash_manifest["records"]}
    condition_counts = Counter(row["condition"] for row in requests)
    hash_mismatches = []
    for row in requests:
        rendered_prompt = rendered.get(row["rendered_prompt_id"])
        expected_hash = prompt_hashes.get(row["rendered_prompt_id"])
        if rendered_prompt is None or expected_hash != sha256_json(rendered_prompt["messages"]) or row.get("prompt_hash") != expected_hash:
            hash_mismatches.append(row["request_id"])
    key_state = inspect_anthropic_api_key()
    duplicate_ids = duplicate_values([row["request_id"] for row in requests])
    checks = {
        "phase6d_prompt_package_frozen": bool(prompt_verification.get("PHASE6D_PROMPT_PACKAGE_FROZEN")),
        "phase6g1_real_data_ready": bool(phase6g1.get("REAL_PHASE6B_READY")),
        "phase6g2d_production_ready": bool(phase6g2d.get("PRODUCTION_INFERENCE_READY")),
        "phase6g3_prompt_freeze_ready": bool(phase6g3.get("REAL_PRODUCTION_PROMPTS_FROZEN")),
        "claude_shard_manifest_exists": (repo_root / CLAUDE_SHARD).exists(),
        "claude_shard_count_valid": len(requests) == 396 and condition_counts.get("non_history") == 198 and condition_counts.get("personalised_history") == 198,
        "claude_model_ids_valid": {row.get("exact_model_id") for row in requests} == {REQUEST_MODEL} and {row.get("model_key") for row in requests} == {SHARD_MODEL_KEY},
        "prompt_hashes_valid": not hash_mismatches,
        "request_ids_deterministic_unique": not duplicate_ids,
        "anthropic_api_key_present": key_state["present"],
        "anthropic_api_key_has_no_leading_or_trailing_whitespace": key_state["has_no_leading_or_trailing_whitespace"],
        "anthropic_api_key_contains_no_cr_or_lf": key_state["contains_no_cr_or_lf"],
        "anthropic_sdk_installed": bool(util.find_spec("anthropic")),
        "output_directory_production_claude_namespace": str(output_dir).replace("\\", "/").endswith("phase6g4/claude"),
        "no_hidden_ground_truth_loaded": not shard.get("contains_hidden_ground_truth", False),
    }
    failures = [key for key, value in checks.items() if not value]
    return {
        "schema_version": "phase6g4b_claude_preflight_v1",
        "checked_at_utc": iso_now(),
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "claude_shard_request_count": len(requests),
        "condition_counts": dict(sorted(condition_counts.items())),
        "prompt_hash_mismatches": hash_mismatches,
        "duplicate_request_ids": duplicate_ids,
        "credential_policy": "ANTHROPIC_API_KEY presence checked as boolean only; secret value is never logged.",
        "ground_truth_dependency": False,
    }


def revalidate_existing_claude_attempts(repo_root: Path, output_dir: Path = OUTPUT_DIR, run_id: str = RUN_ID) -> dict[str, Any]:
    out = repo_root / output_dir
    out.mkdir(parents=True, exist_ok=True)
    attempt_path = out / "attempt_log.jsonl"
    attempts = load_jsonl(attempt_path)
    response_schema = load_response_schema(repo_root / RESPONSE_SCHEMA)
    shard = load_json(repo_root / CLAUDE_SHARD)
    request_by_id = {row["request_id"]: row for row in shard["requests"]}
    source_attempt_hash = sha256_file(attempt_path) if attempt_path.exists() else None
    if (out / "predictions.jsonl").exists() and not (out / "predictions_before_revalidation.jsonl").exists():
        shutil.copy2(out / "predictions.jsonl", out / "predictions_before_revalidation.jsonl")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for attempt in attempts:
        grouped.setdefault(attempt["request_id"], []).append(attempt)
    predictions = []
    provenance = []
    recovered_primary = 0
    recovered_repair = 0
    still_invalid = 0
    for request_id in sorted(grouped, key=lambda key: request_order(key, shard["requests"])):
        request_ref = request_by_id[request_id]
        revalidated_attempts = [revalidate_attempt(row, response_schema) for row in grouped[request_id]]
        selected = next((row for row in revalidated_attempts if row["response_schema_valid"]), None)
        if selected is not None and selected["attempt_type"] == "primary":
            recovered_primary += 1
        elif selected is not None:
            recovered_repair += 1
        else:
            still_invalid += 1
        prediction = finalize_prediction(request_ref, revalidated_attempts, run_id)
        predictions.append(prediction)
        original_primary = next((row for row in grouped[request_id] if row["attempt_type"] == "primary"), None)
        repair = next((row for row in grouped[request_id] if row["attempt_type"] == "format_repair"), None)
        provenance.append({
            "schema_version": "phase6g4b_claude_offline_revalidation_record_v1",
            "request_id": request_id,
            "primary_response_exists": original_primary is not None,
            "primary_valid_after_normalization": bool(original_primary and revalidate_attempt(original_primary, response_schema)["response_schema_valid"]),
            "repair_response_exists": repair is not None,
            "primary_and_repair_predictions_differ": predictions_differ(original_primary, repair, response_schema),
            "canonical_attempt_type": selected["attempt_type"] if selected else None,
            "canonical_prediction_id": prediction["prediction_id"],
            "final_status": prediction["final_status"],
        })
    write_jsonl(out / "predictions.jsonl", predictions)
    production_preflight = load_historical_production_preflight(out)
    run_manifest = load_json(out / "run_manifest.json") if (out / "run_manifest.json").exists() else build_run_manifest(repo_root, production_preflight, 5, output_dir, run_id)
    summary = build_execution_summary(
        run_manifest,
        [row for rows in grouped.values() for row in rows],
        predictions,
        production_preflight,
        0,
        False,
        False,
    )
    summary["offline_revalidation_performed"] = True
    summary["offline_revalidation_api_calls"] = 0
    summary["production_preflight_source"] = production_preflight.get("source", "unknown")
    write_json(out / "execution_summary.json", summary)
    write_json(out / "failure_summary.json", build_failure_summary([row for rows in grouped.values() for row in rows], predictions))
    write_report(out / "claude_production_qc_report.md", summary, production_preflight)
    manifest = {
        "schema_version": "phase6g4b_claude_offline_revalidation_manifest_v1",
        "created_at_utc": iso_now(),
        "run_id": run_id,
        "parser_normalizer_version": NORMALIZER_VERSION,
        "source_attempt_log": str(Path(output_dir) / "attempt_log.jsonl").replace("\\", "/"),
        "source_attempt_log_sha256": source_attempt_hash,
        "requests_revalidated": len(grouped),
        "predictions_recovered_from_primary_attempts": recovered_primary,
        "predictions_recovered_from_repair_attempts": recovered_repair,
        "predictions_still_invalid": still_invalid,
        "api_calls_during_offline_recovery": 0,
        "production_preflight_passed": production_preflight["passed"],
        "production_preflight_source": production_preflight.get("source", "unknown"),
        "offline_revalidation_performed": True,
        "ground_truth_dependency": False,
        "selection_rule": "choose earliest attempt that becomes schema-valid under deterministic Claude response normalisation",
        "normalization_policy": "accept bare JSON, one outer json Markdown fence, or one outer generic Markdown fence; reject prose, trailing text, multiple fences, malformed JSON, and schema-invalid JSON via existing validator",
        "records": provenance,
    }
    write_json(out / "offline_revalidation_manifest.json", manifest)
    return manifest


def load_historical_production_preflight(out: Path) -> dict[str, Any]:
    run_manifest_path = out / "run_manifest.json"
    if run_manifest_path.exists():
        run_manifest = load_json(run_manifest_path)
        preflight = run_manifest.get("preflight")
        if isinstance(preflight, dict) and "passed" in preflight:
            historical = dict(preflight)
            historical["source"] = "run_manifest.preflight"
            return historical
    preflight_path = out / "preflight_report.json"
    if preflight_path.exists():
        preflight = load_json(preflight_path)
        if "passed" in preflight:
            historical = dict(preflight)
            historical["source"] = "preflight_report.json"
            return historical
    return {
        "schema_version": "phase6g4b_claude_historical_preflight_unavailable_v1",
        "passed": False,
        "checks": {},
        "failures": ["historical_production_preflight_unavailable"],
        "prompt_hash_mismatches": [],
        "duplicate_request_ids": [],
        "source": "unavailable",
        "ground_truth_dependency": False,
    }


def revalidate_attempt(attempt: dict[str, Any], response_schema: dict[str, Any]) -> dict[str, Any]:
    updated = dict(attempt)
    normalized = normalize_claude_response_text(attempt.get("raw_response_text"))
    validation = validate_response_text(normalized["normalized_response_text"], response_schema)
    updated["normalized_response_text"] = normalized["normalized_response_text"]
    updated["response_normalization"] = normalized["response_normalization"]
    updated["response_normalizer_version"] = NORMALIZER_VERSION
    updated["validation_status"] = validation["status"]
    updated["response_schema_valid"] = validation["valid"]
    updated["validation_errors"] = validation["errors"]
    return updated


def request_order(request_id: str, requests: list[dict[str, Any]]) -> int:
    order = {row["request_id"]: idx for idx, row in enumerate(requests)}
    return order.get(request_id, 10**9)


def predictions_differ(primary: dict[str, Any] | None, repair: dict[str, Any] | None, response_schema: dict[str, Any]) -> bool | None:
    if primary is None or repair is None:
        return None
    primary_valid = revalidate_attempt(primary, response_schema)
    repair_valid = revalidate_attempt(repair, response_schema)
    if not primary_valid["response_schema_valid"] or not repair_valid["response_schema_valid"]:
        return None
    return json.loads(primary_valid["normalized_response_text"]) != json.loads(repair_valid["normalized_response_text"])


def inspect_anthropic_api_key() -> dict[str, bool]:
    value = os.environ.get("ANTHROPIC_API_KEY")
    if value is None:
        return {"present": False, "has_no_leading_or_trailing_whitespace": False, "contains_no_cr_or_lf": False}
    return {"present": True, "has_no_leading_or_trailing_whitespace": value == value.strip(), "contains_no_cr_or_lf": "\n" not in value and "\r" not in value}


def execute_prediction(request_ref: dict[str, Any], rendered_prompt: dict[str, Any], prompt_hash: str, response_schema: dict[str, Any], run_id: str) -> list[dict[str, Any]]:
    attempts = []
    primary = call_with_transport_retries(request_ref, rendered_prompt, prompt_hash, response_schema, "primary", 1, run_id)
    attempts.extend(primary)
    final_primary = primary[-1]
    if should_repair(final_primary["validation_status"], final_primary["request_status"], final_primary.get("raw_response_text")):
        repair_messages = render_format_repair(final_primary["raw_response_text"], response_schema)["messages"]
        repair = call_with_transport_retries(request_ref, {"messages": repair_messages}, prompt_hash, response_schema, "format_repair", 2, run_id)
        attempts.extend(repair[: MAX_FORMAT_REPAIRS + MAX_TRANSPORT_RETRIES])
    return attempts


def call_with_transport_retries(request_ref: dict[str, Any], rendered_prompt: dict[str, Any], prompt_hash: str, response_schema: dict[str, Any], attempt_type: str, attempt_number: int, run_id: str) -> list[dict[str, Any]]:
    attempts = []
    for transport_attempt in range(1, MAX_TRANSPORT_RETRIES + 2):
        started = time.perf_counter()
        started_at = iso_now()
        try:
            provider = invoke_anthropic(rendered_prompt["messages"], attempt_type)
            raw_text = provider.get("output_text")
            normalized = normalize_claude_response_text(raw_text)
            validation = validate_response_text(normalized["normalized_response_text"], response_schema)
            request_status = provider.get("status", "completed")
            error = provider.get("error")
        except Exception as exc:  # pragma: no cover - only live provider errors
            raw_text = None
            normalized = normalize_claude_response_text(raw_text)
            validation = validate_response_text(None, response_schema)
            request_status = "error"
            error = error_from_exception(exc)
            provider = {"metadata": {}, "usage": None, "incomplete_details": None, "error": error}
        failure = classify_failure({"status": request_status, "error": error, "incomplete_details": provider.get("incomplete_details")}, validation)
        attempt = build_attempt_record(request_ref, prompt_hash, attempt_type, attempt_number, transport_attempt, request_status, raw_text, normalized, validation, provider, failure, time.perf_counter() - started, started_at, run_id)
        attempts.append(attempt)
        if request_status == "completed" or failure["failure_code"] not in RETRYABLE_FAILURES or transport_attempt > MAX_TRANSPORT_RETRIES:
            return attempts
    return attempts


def invoke_anthropic(messages: list[dict[str, str]], attempt_type: str) -> dict[str, Any]:
    from anthropic import Anthropic  # type: ignore[import-not-found]

    system, user = split_system_user(messages)
    client = Anthropic()
    kwargs = {
        "model": REQUEST_MODEL,
        "max_tokens": MAX_TOKENS,
        "thinking": {"type": "disabled"},
        "messages": [{"role": "user", "content": user}],
    }
    if system:
        kwargs["system"] = system
    started = time.perf_counter()
    response = client.messages.create(**kwargs)
    output_text = extract_text(response)
    stop_reason = getattr(response, "stop_reason", None)
    request_status = "incomplete" if stop_reason == "max_tokens" else "completed"
    incomplete_details = {"reason": "max_output_tokens", "stop_reason": stop_reason} if stop_reason == "max_tokens" else None
    error = {"type": "refusal", "message": "Anthropic response stop_reason=refusal"} if stop_reason == "refusal" else None
    return {
        "status": request_status,
        "output_text": output_text,
        "incomplete_details": incomplete_details,
        "error": error,
        "metadata": {
            "model": getattr(response, "model", None),
            "request_api": "Anthropic.messages.create",
            "attempt_type": attempt_type,
            "latency_seconds": time.perf_counter() - started,
            "stop_reason": stop_reason,
            "provider_request_id": getattr(response, "id", None),
        },
        "usage": usage_to_dict(getattr(response, "usage", None)),
    }


def split_system_user(messages: list[dict[str, str]]) -> tuple[str | None, str]:
    if len(messages) == 2 and messages[0]["role"] == "system":
        return messages[0]["content"], messages[1]["content"]
    return None, messages[0]["content"]


def extract_text(response: Any) -> str | None:
    chunks = []
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "text":
            chunks.append(getattr(block, "text", ""))
        elif isinstance(block, dict) and block.get("type") == "text":
            chunks.append(block.get("text", ""))
    return "".join(chunks) if chunks else None


def error_from_exception(exc: Exception) -> dict[str, Any]:
    status_code = getattr(exc, "status_code", None)
    body = getattr(exc, "body", None) or {}
    error = body.get("error", body) if isinstance(body, dict) else {}
    message = error.get("message") or str(exc)
    error_type = error.get("type") or getattr(exc, "type", None)
    code = error.get("code")
    if "overloaded" in message.lower():
        error_type = "backend_unavailable"
    return {"type": error_type or "connection_error", "code": code, "message": message, "http_status_code": status_code}


def build_attempt_record(request_ref: dict[str, Any], prompt_hash: str, attempt_type: str, attempt_number: int, transport_attempt: int, request_status: str, raw_text: str | None, normalized: dict[str, Any], validation: dict[str, Any], provider: dict[str, Any], failure: dict[str, Any], latency: float, started_at: str, run_id: str) -> dict[str, Any]:
    metadata = sanitize_provider_metadata(provider.get("metadata") or {})
    return {
        "schema_version": "phase6g4b_claude_attempt_v1",
        "run_id": run_id,
        "request_id": request_ref["request_id"],
        "prediction_id": prediction_id(request_ref),
        "rendered_prompt_id": request_ref["rendered_prompt_id"],
        "prediction_example_id": request_ref["prediction_example_id"],
        "condition": request_ref["condition"],
        "model_key": MODEL_KEY,
        "shard_model_key": request_ref["model_key"],
        "exact_requested_model": REQUEST_MODEL,
        "actual_returned_model": metadata.get("model"),
        "prompt_hash": prompt_hash,
        "inference_config_hash": inference_config_hash(),
        "attempt_type": attempt_type,
        "attempt_number": attempt_number,
        "transport_attempt_number": transport_attempt,
        "request_status": request_status,
        "raw_response_text": raw_text,
        "normalized_response_text": normalized["normalized_response_text"],
        "response_normalization": normalized["response_normalization"],
        "response_normalizer_version": NORMALIZER_VERSION,
        "validation_status": validation["status"],
        "response_schema_valid": validation["valid"],
        "validation_errors": validation["errors"],
        "token_usage": normalize_usage(provider.get("usage")),
        "latency_seconds": latency,
        "started_at": started_at,
        "ended_at": iso_now(),
        "provider_response_metadata": metadata,
        "incomplete_details": provider.get("incomplete_details"),
        "failure_code": failure["failure_code"],
        "failure_category": failure["failure_category"],
        "retryable": failure["retryable"],
        "max_tokens": MAX_TOKENS,
        "thinking_disabled_sent": True,
        "temperature_sent": False,
        "top_p_sent": False,
        "top_k_sent": False,
        "seed_sent": False,
        "assistant_prefill_sent": False,
    }


def finalize_prediction(request_ref: dict[str, Any], attempts: list[dict[str, Any]], run_id: str) -> dict[str, Any]:
    successful = next((row for row in attempts if row["response_schema_valid"]), None)
    primary_valid = next((row for row in attempts if row["attempt_type"] == "primary" and row["response_schema_valid"]), None)
    repair_attempted = any(row["attempt_type"] == "format_repair" for row in attempts)
    formatting_repair_count = 0 if primary_valid else sum(1 for row in attempts if row["attempt_type"] == "format_repair")
    if primary_valid:
        status = "valid_primary"
    elif successful:
        status = "valid_after_repair"
    elif any(row.get("failure_code") == "quota_exhausted" for row in attempts):
        status = "quota_exhausted"
    elif any(row.get("failure_code") == "output_budget_exhausted" for row in attempts):
        status = "output_budget_exhausted"
    elif any(row.get("failure_code") == "refusal" for row in attempts):
        status = "refusal"
    elif any(row["request_status"] != "completed" for row in attempts):
        status = "backend_failed"
    elif repair_attempted:
        status = "invalid_after_repair"
    else:
        status = "invalid_after_repair"
    return {
        "schema_version": "phase6g4b_claude_prediction_v1",
        "run_id": run_id,
        "request_id": request_ref["request_id"],
        "prediction_id": prediction_id(request_ref),
        "rendered_prompt_id": request_ref["rendered_prompt_id"],
        "prediction_example_id": request_ref["prediction_example_id"],
        "condition": request_ref["condition"],
        "model_key": MODEL_KEY,
        "shard_model_key": request_ref["model_key"],
        "exact_requested_model": REQUEST_MODEL,
        "actual_returned_model": (successful or attempts[-1]).get("actual_returned_model"),
        "prompt_hash": request_ref["prompt_hash"],
        "final_status": status,
        "terminal": status in TERMINAL_STATUSES,
        "attempt_count": len(attempts),
        "transport_retry_count": sum(1 for row in attempts if row["transport_attempt_number"] > 1),
        "formatting_repair_count": formatting_repair_count,
        "response_schema_valid": bool(successful),
        "raw_final_response_text": (successful or attempts[-1]).get("raw_response_text"),
        "normalized_final_response_text": (successful or attempts[-1]).get("normalized_response_text"),
        "token_usage_totals": sum_usage(attempts),
    }


def normalize_claude_response_text(raw_text: str | None) -> dict[str, str | None]:
    if raw_text is None:
        return {"normalized_response_text": None, "response_normalization": "none"}
    stripped = raw_text.strip()
    if not stripped.startswith("```"):
        return {"normalized_response_text": stripped, "response_normalization": "none" if stripped == raw_text else "leading_trailing_whitespace_removed"}
    lines = stripped.splitlines()
    if len(lines) < 3:
        return {"normalized_response_text": stripped, "response_normalization": "none"}
    opening = lines[0].strip()
    closing = lines[-1].strip()
    if opening not in {"```", "```json"} or closing != "```":
        return {"normalized_response_text": stripped, "response_normalization": "none"}
    if any(line.strip().startswith("```") for line in lines[1:-1]):
        return {"normalized_response_text": stripped, "response_normalization": "none"}
    inner = "\n".join(lines[1:-1]).strip()
    return {
        "normalized_response_text": inner,
        "response_normalization": "markdown_json_fence_removed" if opening == "```json" else "markdown_generic_fence_removed",
    }


def build_execution_summary(run_manifest: dict[str, Any], attempts: list[dict[str, Any]], predictions: list[dict[str, Any]], preflight: dict[str, Any], executed_this_invocation: int, stopped_after_guarded_batch: bool, halted_due_quota: bool) -> dict[str, Any]:
    statuses = Counter(row["final_status"] for row in predictions)
    conditions = Counter(row["condition"] for row in predictions)
    actual_models = sorted({row.get("actual_returned_model") for row in attempts if row.get("actual_returned_model")})
    terminal_count = sum(1 for row in predictions if row["terminal"])
    unexpected_models = [model for model in actual_models if model != REQUEST_MODEL]
    return {
        "schema_version": "phase6g4b_claude_execution_summary_v1",
        "run_id": run_manifest["run_id"],
        "preflight_passed": preflight["passed"],
        "exact_requested_model": REQUEST_MODEL,
        "actual_returned_models": actual_models,
        "expected_predictions": len(run_manifest["preflight"].get("duplicate_request_ids", [])) + 396,
        "guarded_batch_requested": True,
        "guarded_batch_limit": run_manifest["guarded_batch_limit"],
        "predictions_executed_this_invocation": executed_this_invocation,
        "remaining_predictions": 396 - terminal_count,
        "stopped_after_guarded_batch": stopped_after_guarded_batch,
        "halted_due_quota_exhaustion": halted_due_quota,
        "attempted_prediction_count": len(predictions),
        "terminal_prediction_count": terminal_count,
        "non_history_count": conditions.get("non_history", 0),
        "personalised_history_count": conditions.get("personalised_history", 0),
        "valid_primary_count": statuses.get("valid_primary", 0),
        "valid_after_repair_count": statuses.get("valid_after_repair", 0),
        "invalid_count": statuses.get("invalid_after_repair", 0),
        "backend_failure_count": statuses.get("backend_failed", 0),
        "quota_exhausted_count": statuses.get("quota_exhausted", 0),
        "output_budget_exhausted_count": statuses.get("output_budget_exhausted", 0),
        "refusal_count": statuses.get("refusal", 0),
        "transport_retry_count": sum(row.get("transport_retry_count", 0) for row in predictions),
        "formatting_repair_count": sum(row.get("formatting_repair_count", 0) for row in predictions),
        "prompt_hash_mismatch_count": len(preflight["prompt_hash_mismatches"]),
        "duplicate_prediction_count": len(duplicate_values([row["prediction_id"] for row in predictions])),
        "unexpected_model_identity_changes": len(unexpected_models),
        "ground_truth_dependency": False,
        "token_usage_totals": sum_usage(attempts),
        "total_api_calls": len(attempts),
        "CLAUDE_PRODUCTION_INFERENCE_COMPLETE": len(predictions) == 396 and terminal_count == 396,
        "ALL_CLAUDE_PREDICTIONS_VALID": len(predictions) == 396 and all(row["response_schema_valid"] for row in predictions),
    }


def build_blocked_summary(run_manifest: dict[str, Any], preflight: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "phase6g4b_claude_execution_summary_v1",
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
        "halted_due_quota_exhaustion": False,
        "attempted_prediction_count": 0,
        "terminal_prediction_count": 0,
        "non_history_count": 0,
        "personalised_history_count": 0,
        "valid_primary_count": 0,
        "valid_after_repair_count": 0,
        "invalid_count": 0,
        "backend_failure_count": 0,
        "quota_exhausted_count": 0,
        "output_budget_exhausted_count": 0,
        "refusal_count": 0,
        "transport_retry_count": 0,
        "formatting_repair_count": 0,
        "prompt_hash_mismatch_count": len(preflight["prompt_hash_mismatches"]),
        "duplicate_prediction_count": 0,
        "unexpected_model_identity_changes": 0,
        "ground_truth_dependency": False,
        "token_usage_totals": {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0},
        "total_api_calls": 0,
        "CLAUDE_PRODUCTION_INFERENCE_COMPLETE": False,
        "ALL_CLAUDE_PREDICTIONS_VALID": False,
    }


def build_run_manifest(repo_root: Path, preflight: dict[str, Any], guarded_batch_size: int, output_dir: Path, run_id: str) -> dict[str, Any]:
    shard = load_json(repo_root / CLAUDE_SHARD)
    return {
        "schema_version": "phase6g4b_claude_run_manifest_v1",
        "run_id": run_id,
        "created_at_utc": iso_now(),
        "run_type": "final_real_claude_sonnet_5_production_inference",
        "model_key": MODEL_KEY,
        "shard_model_key": SHARD_MODEL_KEY,
        "exact_requested_model": REQUEST_MODEL,
        "backend": "Anthropic Messages API",
        "rendered_prompt_dataset": str(RENDERED_PROMPTS).replace("\\", "/"),
        "rendered_prompt_dataset_sha256": sha256_file(repo_root / RENDERED_PROMPTS),
        "claude_shard_manifest": str(CLAUDE_SHARD).replace("\\", "/"),
        "claude_shard_sha256": sha256_file(repo_root / CLAUDE_SHARD),
        "expected_request_count": 396,
        "shard_request_count": len(shard.get("requests", [])),
        "output_dir": str(output_dir).replace("\\", "/"),
        "guarded_batch_requested": True,
        "guarded_batch_limit": guarded_batch_size,
        "guarded_batch_semantics": "execute at most N unresolved Claude prediction units during this invocation",
        "preflight": preflight,
        "max_tokens": MAX_TOKENS,
        "thinking_disabled_sent": True,
        "temperature_sent": False,
        "top_p_sent": False,
        "top_k_sent": False,
        "seed_sent": False,
        "assistant_prefill_sent": False,
        "contains_hidden_ground_truth": False,
    }


def build_failure_summary(attempts: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "phase6g4b_claude_failure_summary_v1",
        "blocked_by_preflight": False,
        "failure_codes": dict(Counter(row.get("failure_code") for row in attempts if row.get("failure_code"))),
        "final_statuses": dict(Counter(row["final_status"] for row in predictions)),
        "backend_failures": [row for row in predictions if row["final_status"] == "backend_failed"],
        "invalid_predictions": [row for row in predictions if row["final_status"] == "invalid_after_repair"],
        "output_budget_exhausted_predictions": [row for row in predictions if row["final_status"] == "output_budget_exhausted"],
    }


def write_report(path: Path, summary: dict[str, Any], preflight: dict[str, Any]) -> None:
    lines = [
        "# Phase 6G.4B Claude Sonnet 5 Production QC Report",
        "",
        f"- Preflight passed: `{str(preflight['passed']).lower()}`",
        f"- Preflight failures: `{preflight['failures']}`",
        f"- Exact requested model: `{REQUEST_MODEL}`",
        f"- Actual returned models: `{summary['actual_returned_models']}`",
        f"- Max tokens: `{MAX_TOKENS}`",
        f"- Thinking disabled sent: `true`",
        f"- Sampling parameters sent: `false`",
        f"- Attempted predictions: `{summary['attempted_prediction_count']}`",
        f"- Terminal predictions: `{summary['terminal_prediction_count']}`",
        f"- Guarded batch limit: `{summary['guarded_batch_limit']}`",
        f"- Predictions executed this invocation: `{summary['predictions_executed_this_invocation']}`",
        f"- Remaining predictions: `{summary['remaining_predictions']}`",
        f"- Valid primary: `{summary['valid_primary_count']}`",
        f"- Valid after repair: `{summary['valid_after_repair_count']}`",
        f"- Invalid: `{summary['invalid_count']}`",
        f"- Backend failures: `{summary['backend_failure_count']}`",
        f"- Output-budget exhausted: `{summary['output_budget_exhausted_count']}`",
        f"- Formatting repairs: `{summary['formatting_repair_count']}`",
        f"- `CLAUDE_PRODUCTION_INFERENCE_COMPLETE`: `{str(summary['CLAUDE_PRODUCTION_INFERENCE_COMPLETE']).lower()}`",
        f"- `ALL_CLAUDE_PREDICTIONS_VALID`: `{str(summary['ALL_CLAUDE_PREDICTIONS_VALID']).lower()}`",
        "",
        "No accuracy, scoring, hidden ground truth, GPT rerun, Llama, or Centaur execution is included.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def prediction_id(request_ref: dict[str, Any]) -> str:
    stable = "::".join([request_ref["rendered_prompt_id"], MODEL_KEY, "phase6g4b_claude_production"])
    return f"phase6g4b_claude_pred_{hashlib.sha256(stable.encode('utf-8')).hexdigest()[:32]}"


def inference_config_hash() -> str:
    return sha256_json({"model": REQUEST_MODEL, "max_tokens": MAX_TOKENS, "thinking": "disabled", "temperature": "omitted", "top_p": "omitted", "top_k": "omitted", "seed": "omitted"})


def normalize_usage(usage: dict[str, Any] | None) -> dict[str, Any]:
    usage = usage or {}
    return {"input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"), "reasoning_tokens": None, "total_tokens": usage.get("total_tokens") or sum(v for v in [usage.get("input_tokens"), usage.get("output_tokens")] if isinstance(v, int))}


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


def duplicate_values(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


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
