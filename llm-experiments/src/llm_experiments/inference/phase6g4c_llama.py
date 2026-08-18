"""Phase 6G.4C Llama 3.1 70B Instruct production inference runner."""

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
from llm_experiments.prompts.prompt_spec import write_json


SCHEMA_VERSION = "phase6g4c_llama_production_inference_v1"
OUTPUT_DIR = Path("llm-experiments/outputs/real/phase6g4/llama")
RENDERED_PROMPTS = Path("llm-experiments/outputs/real/phase6g3/phase6g3_real_rendered_prompts.jsonl")
LLAMA_SHARD = Path("llm-experiments/outputs/real/phase6g3/phase6g3_qmul_llama_shard_manifest.json")
PROMPT_HASH_MANIFEST = Path("llm-experiments/outputs/real/phase6g3/phase6g3_prompt_hash_manifest.json")
PHASE6G3_FREEZE = Path("llm-experiments/outputs/real/phase6g3/phase6g3_freeze_manifest.json")
PHASE6G2D_READINESS = Path("llm-experiments/outputs/real/phase6g2d/phase6g2d_final_readiness.json")
PHASE6G2D_MODEL_REGISTRY = Path("llm-experiments/outputs/real/phase6g2d/phase6g2d_final_model_registry.json")
PHASE6G2D_BACKEND_REGISTRY = Path("llm-experiments/outputs/real/phase6g2d/phase6g2d_final_backend_registry.json")
PHASE6G2D_INFERENCE_CONFIG = Path("llm-experiments/outputs/real/phase6g2d/phase6g2d_final_inference_config.json")
PHASE6E_MODEL_REGISTRY = Path("llm-experiments/config/phase6e_model_registry_v1.json")
PHASE6E_BACKEND_REGISTRY = Path("llm-experiments/config/phase6e_backend_registry_v1.json")
PHASE6G1_GATE = Path("llm-experiments/outputs/real/phase6b/production_readiness_gate.json")
RESPONSE_SCHEMA = Path("llm-experiments/schema/preference_prediction_response_v1.json")
RUN_ID = "phase6g4c_llama_production_run_01"
MODEL_KEY = "llama_3_1_70b_instruct"
EXPERIMENT_MODEL_LABEL = "Llama 3.1 70B Instruct"
REQUEST_MODEL = "meta-llama/Llama-3.1-70B-Instruct"
EXPECTED_RETURNED_MODEL = "meta-llama/Llama-3.1-70B-Instruct"
REVISION = "1605565b47bb9346c5515c34102e054115b4f98b"
BACKEND_KEY = "qmul_llama_transformers_local_verified"
BACKEND_TYPE = "qmul_local_transformers"
REQUEST_API = "AutoModelForCausalLM.generate"
HF_HOME_FROZEN = "/home/jovyan/huggingface"
MAX_NEW_TOKENS = 256
MAX_TRANSPORT_RETRIES = 2
MAX_FORMAT_REPAIRS = 1
TERMINAL_STATUSES = {"valid_primary", "valid_after_repair", "invalid_after_repair", "backend_failed", "output_budget_exhausted", "quota_exhausted", "refusal", "model_mismatch"}
NORMALIZER_VERSION = "phase6g4c_llama_response_normalizer_v1"
_TOKENIZER: Any = None
_MODEL: Any = None


def run_llama_production(repo_root: Path, guarded_batch_size: int = 5, output_dir: Path = OUTPUT_DIR, run_id: str = RUN_ID) -> dict[str, Any]:
    if guarded_batch_size < 1:
        raise ValueError("--guarded-batch-size must be at least 1")
    out = repo_root / output_dir
    out.mkdir(parents=True, exist_ok=True)
    preflight = run_preflight(repo_root, output_dir)
    run_manifest = build_run_manifest(repo_root, preflight, guarded_batch_size, output_dir, run_id)
    write_json(out / "run_manifest.json", run_manifest)
    if not preflight["passed"]:
        summary = build_blocked_summary(run_manifest, preflight)
        write_json(out / "preflight_report.json", preflight)
        write_json(out / "execution_summary.json", summary)
        write_json(out / "failure_summary.json", {"schema_version": "phase6g4c_llama_failure_summary_v1", "blocked_by_preflight": True, "failures": preflight["failures"]})
        write_report(out / "llama_production_qc_report.md", summary, preflight)
        return summary

    response_schema = load_response_schema(repo_root / RESPONSE_SCHEMA)
    rendered = {row["rendered_prompt_id"]: row for row in load_jsonl(repo_root / RENDERED_PROMPTS)}
    shard = load_json(repo_root / LLAMA_SHARD)
    prompt_hashes = {row["rendered_prompt_id"]: row["message_payload_sha256"] for row in load_json(repo_root / PROMPT_HASH_MANIFEST)["records"]}
    existing_predictions = load_jsonl(out / "predictions.jsonl")
    terminal_ids = {row["request_id"] for row in existing_predictions if row.get("final_status") in TERMINAL_STATUSES}
    attempts = load_jsonl(out / "attempt_log.jsonl")
    actual_models = {row.get("actual_returned_model") for row in attempts if row.get("actual_returned_model")}
    executed_this_invocation = 0
    stopped_after_guarded_batch = False

    for request_ref in shard["requests"]:
        if request_ref["request_id"] in terminal_ids:
            continue
        if executed_this_invocation >= guarded_batch_size:
            stopped_after_guarded_batch = True
            break
        if actual_models and actual_models != {EXPECTED_RETURNED_MODEL}:
            break
        prediction_attempts = execute_prediction(request_ref, rendered[request_ref["rendered_prompt_id"]], prompt_hashes[request_ref["rendered_prompt_id"]], response_schema, run_id)
        attempts.extend(prediction_attempts)
        append_jsonl(out / "attempt_log.jsonl", prediction_attempts)
        prediction = finalize_prediction(request_ref, prediction_attempts, run_id)
        append_jsonl(out / "predictions.jsonl", [prediction])
        terminal_ids.add(request_ref["request_id"])
        executed_this_invocation += 1
        actual_models.update(row.get("actual_returned_model") for row in prediction_attempts if row.get("actual_returned_model"))

    predictions = load_jsonl(out / "predictions.jsonl")
    summary = build_execution_summary(run_manifest, attempts, predictions, preflight, executed_this_invocation, stopped_after_guarded_batch)
    write_json(out / "execution_summary.json", summary)
    write_json(out / "failure_summary.json", build_failure_summary(attempts, predictions))
    write_report(out / "llama_production_qc_report.md", summary, preflight)
    return summary


def run_preflight(repo_root: Path, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    prompt_verification = verify_prompt_package(repo_root)
    phase6g1 = load_json(repo_root / PHASE6G1_GATE)
    phase6g2d = load_json(repo_root / PHASE6G2D_READINESS)
    phase6g3 = load_json(repo_root / PHASE6G3_FREEZE)
    inference_config = load_json(repo_root / PHASE6G2D_INFERENCE_CONFIG)
    model_record = llama_model_record(repo_root)
    backend_record = llama_backend_record(repo_root)
    shard = load_json(repo_root / LLAMA_SHARD)
    rendered = {row["rendered_prompt_id"]: row for row in load_jsonl(repo_root / RENDERED_PROMPTS)}
    prompt_hashes = {row["rendered_prompt_id"]: row["message_payload_sha256"] for row in load_json(repo_root / PROMPT_HASH_MANIFEST)["records"]}
    requests = shard.get("requests", [])
    condition_counts = Counter(row["condition"] for row in requests)
    hash_mismatches = []
    for row in requests:
        rendered_prompt = rendered.get(row["rendered_prompt_id"])
        expected_hash = prompt_hashes.get(row["rendered_prompt_id"])
        if rendered_prompt is None or expected_hash != sha256_json(rendered_prompt["messages"]) or row.get("prompt_hash") != expected_hash:
            hash_mismatches.append(row["request_id"])
    cache_path = Path(os.environ.get("HF_HOME", HF_HOME_FROZEN))
    dependency_names = ["torch", "transformers", "bitsandbytes", "accelerate"]
    checks = {
        "phase6d_prompt_package_frozen": bool(prompt_verification.get("PHASE6D_PROMPT_PACKAGE_FROZEN")),
        "phase6g1_real_data_ready": bool(phase6g1.get("REAL_PHASE6B_READY")),
        "phase6g2d_production_ready": bool(phase6g2d.get("PRODUCTION_INFERENCE_READY")),
        "phase6g3_prompt_freeze_ready": bool(phase6g3.get("REAL_PRODUCTION_PROMPTS_FROZEN")),
        "llama_shard_manifest_exists": (repo_root / LLAMA_SHARD).exists(),
        "llama_shard_count_valid": len(requests) == 396 and condition_counts.get("non_history") == 198 and condition_counts.get("personalised_history") == 198,
        "llama_request_ids_unique": not duplicate_values([row["request_id"] for row in requests]),
        "llama_model_ids_valid": {row.get("exact_model_id") for row in requests} == {REQUEST_MODEL} and {row.get("model_key") for row in requests} == {MODEL_KEY},
        "prompt_hashes_valid": not hash_mismatches,
        "backend_type_frozen": backend_record.get("backend_type") == BACKEND_TYPE and backend_record.get("backend_verified") is True,
        "model_identity_frozen": model_record.get("exact_model_id") == REQUEST_MODEL and model_record.get("revision") == REVISION and model_record.get("backend_key") == BACKEND_KEY,
        "endpoint_configuration_available": backend_record.get("request_api") == REQUEST_API and backend_record.get("local_files_only") is True,
        "authentication_configuration_valid": backend_record.get("authentication", {}).get("required") is False,
        "frozen_decoding_policy_valid": inference_config.get("decoding_policy", {}).get(MODEL_KEY) == "greedy_do_sample_false",
        "frozen_max_output_tokens_valid": inference_config.get("common_cross_model_policy", {}).get("max_output_tokens") == MAX_NEW_TOKENS,
        "frozen_schema_valid": inference_config.get("common_cross_model_policy", {}).get("local_response_validation_schema") == "preference_prediction_response_v1",
        "frozen_zero_shot_policy_valid": inference_config.get("common_cross_model_policy", {}).get("zero_shot") is True and inference_config.get("common_cross_model_policy", {}).get("chain_of_thought_requested") is False,
        "local_hf_cache_available": cache_path.exists(),
        "runtime_dependencies_available": all(util.find_spec(name) for name in dependency_names),
        "output_directory_production_llama_namespace": str(output_dir).replace("\\", "/").endswith("phase6g4/llama"),
        "no_hidden_ground_truth_loaded": not shard.get("contains_hidden_ground_truth", False),
    }
    failures = [key for key, value in checks.items() if not value]
    return {
        "schema_version": "phase6g4c_llama_preflight_v1",
        "checked_at_utc": iso_now(),
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "llama_shard_request_count": len(requests),
        "condition_counts": dict(sorted(condition_counts.items())),
        "prompt_hash_mismatches": hash_mismatches,
        "duplicate_request_ids": duplicate_values([row["request_id"] for row in requests]),
        "dependency_policy": "Requires local QMUL runtime dependencies torch, transformers, bitsandbytes, accelerate; no network downloads.",
        "cache_policy": f"Uses local Hugging Face cache only; HF_HOME defaults to {HF_HOME_FROZEN}.",
        "credential_policy": "No API credential is required for the frozen local QMUL Transformers backend.",
        "ground_truth_dependency": False,
    }


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
            provider = invoke_llama(rendered_prompt["messages"], attempt_type)
            raw_text = provider.get("decoded_text")
            normalized = normalize_llama_response_text(raw_text)
            validation = validate_response_text(normalized["normalized_response_text"], response_schema)
            request_status = provider.get("status", "completed")
            error = provider.get("error")
        except Exception as exc:  # pragma: no cover - live local runtime errors only
            raw_text = None
            normalized = normalize_llama_response_text(raw_text)
            validation = validate_response_text(None, response_schema)
            request_status = "error"
            error = {"type": "connection_error", "message": str(exc)}
            provider = {"metadata": {}, "usage": None, "incomplete_details": None, "error": error}
        failure = classify_failure({"status": request_status, "error": error, "incomplete_details": provider.get("incomplete_details")}, validation)
        attempt = build_attempt_record(request_ref, prompt_hash, attempt_type, attempt_number, transport_attempt, request_status, raw_text, normalized, validation, provider, failure, time.perf_counter() - started, started_at, run_id)
        attempts.append(attempt)
        if request_status == "completed" or failure["failure_code"] not in RETRYABLE_FAILURES or transport_attempt > MAX_TRANSPORT_RETRIES:
            return attempts
    return attempts


def invoke_llama(messages: list[dict[str, str]], attempt_type: str) -> dict[str, Any]:
    global _MODEL, _TOKENIZER
    import torch  # type: ignore[import-not-found]
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig  # type: ignore[import-not-found]

    if _TOKENIZER is None or _MODEL is None:
        quant_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
        _TOKENIZER = AutoTokenizer.from_pretrained(REQUEST_MODEL, revision=REVISION, local_files_only=True)
        _MODEL = AutoModelForCausalLM.from_pretrained(REQUEST_MODEL, revision=REVISION, quantization_config=quant_config, device_map="auto", max_memory={0: "43GiB"}, torch_dtype=torch.bfloat16, low_cpu_mem_usage=True, local_files_only=True)
        _MODEL.eval()
    started = time.perf_counter()
    inputs = _TOKENIZER.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt")
    if hasattr(inputs, "to"):
        inputs = inputs.to("cuda")
    with torch.inference_mode():
        outputs = _MODEL.generate(inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False, pad_token_id=_TOKENIZER.eos_token_id)
    generated = outputs[0][inputs.shape[-1]:]
    decoded = _TOKENIZER.decode(generated, skip_special_tokens=True)
    generated_token_count = len(generated) if hasattr(generated, "__len__") else None
    status = "incomplete" if generated_token_count == MAX_NEW_TOKENS else "completed"
    incomplete_details = {"reason": "max_output_tokens"} if status == "incomplete" else None
    return {
        "status": status,
        "decoded_text": decoded,
        "metadata": {"model": REQUEST_MODEL, "revision": REVISION, "request_api": REQUEST_API, "attempt_type": attempt_type, "latency_seconds": time.perf_counter() - started, "device_map": getattr(_MODEL, "hf_device_map", None), "backend_type": BACKEND_TYPE, "generated_token_count": generated_token_count},
        "usage": {"output_tokens": generated_token_count} if generated_token_count is not None else None,
        "incomplete_details": incomplete_details,
    }


def build_attempt_record(request_ref: dict[str, Any], prompt_hash: str, attempt_type: str, attempt_number: int, transport_attempt: int, request_status: str, raw_text: str | None, normalized: dict[str, Any], validation: dict[str, Any], provider: dict[str, Any], failure: dict[str, Any], latency: float, started_at: str, run_id: str) -> dict[str, Any]:
    metadata = sanitize_provider_metadata(provider.get("metadata") or {})
    actual_model = metadata.get("model")
    if actual_model and actual_model != EXPECTED_RETURNED_MODEL:
        failure = {"failure_code": "model_mismatch", "failure_category": "internal", "retryable": False}
    return {
        "schema_version": "phase6g4c_llama_attempt_v1",
        "run_id": run_id,
        "request_id": request_ref["request_id"],
        "prediction_id": prediction_id(request_ref),
        "rendered_prompt_id": request_ref["rendered_prompt_id"],
        "prediction_example_id": request_ref["prediction_example_id"],
        "condition": request_ref["condition"],
        "model_key": MODEL_KEY,
        "experiment_model_label": EXPERIMENT_MODEL_LABEL,
        "exact_requested_backend_model": REQUEST_MODEL,
        "actual_returned_model": actual_model,
        "backend_key": BACKEND_KEY,
        "backend_type": BACKEND_TYPE,
        "endpoint_base_url": None,
        "endpoint_identifier": "local_qmul_transformers_cache",
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
        "max_new_tokens": MAX_NEW_TOKENS,
        "do_sample": False,
        "temperature_sent": False,
        "top_p_sent": False,
        "top_k_sent": False,
        "seed_sent": False,
        "repetition_penalty_sent": False,
        "response_format_sent": False,
        "stop_sequences_sent": False,
        "chat_template_handling": "tokenizer.apply_chat_template(add_generation_prompt=True)",
    }


def finalize_prediction(request_ref: dict[str, Any], attempts: list[dict[str, Any]], run_id: str) -> dict[str, Any]:
    successful = next((row for row in attempts if row["response_schema_valid"]), None)
    primary_valid = next((row for row in attempts if row["attempt_type"] == "primary" and row["response_schema_valid"]), None)
    repair_attempted = any(row["attempt_type"] == "format_repair" for row in attempts)
    if any(row.get("failure_code") == "model_mismatch" for row in attempts):
        status = "model_mismatch"
    elif primary_valid:
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
        "schema_version": "phase6g4c_llama_prediction_v1",
        "run_id": run_id,
        "request_id": request_ref["request_id"],
        "prediction_id": prediction_id(request_ref),
        "rendered_prompt_id": request_ref["rendered_prompt_id"],
        "prediction_example_id": request_ref["prediction_example_id"],
        "condition": request_ref["condition"],
        "model_key": MODEL_KEY,
        "experiment_model_label": EXPERIMENT_MODEL_LABEL,
        "exact_requested_backend_model": REQUEST_MODEL,
        "actual_returned_model": (successful or attempts[-1]).get("actual_returned_model"),
        "prompt_hash": request_ref["prompt_hash"],
        "final_status": status,
        "terminal": status in TERMINAL_STATUSES,
        "attempt_count": len(attempts),
        "transport_retry_count": sum(1 for row in attempts if row["transport_attempt_number"] > 1),
        "formatting_repair_count": sum(1 for row in attempts if row["attempt_type"] == "format_repair"),
        "response_schema_valid": bool(successful),
        "raw_final_response_text": (successful or attempts[-1]).get("raw_response_text"),
        "normalized_final_response_text": (successful or attempts[-1]).get("normalized_response_text"),
        "token_usage_totals": sum_usage(attempts),
    }


def build_execution_summary(run_manifest: dict[str, Any], attempts: list[dict[str, Any]], predictions: list[dict[str, Any]], preflight: dict[str, Any], executed_this_invocation: int, stopped_after_guarded_batch: bool) -> dict[str, Any]:
    statuses = Counter(row["final_status"] for row in predictions)
    conditions = Counter(row["condition"] for row in predictions)
    terminal_count = sum(1 for row in predictions if row["terminal"])
    actual_models = sorted({row.get("actual_returned_model") for row in attempts if row.get("actual_returned_model")})
    return {
        "schema_version": "phase6g4c_llama_execution_summary_v1",
        "run_id": run_manifest["run_id"],
        "preflight_passed": preflight["passed"],
        "exact_requested_backend_model": REQUEST_MODEL,
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
        "model_mismatch_count": statuses.get("model_mismatch", 0),
        "transport_retry_count": sum(row.get("transport_retry_count", 0) for row in predictions),
        "formatting_repair_count": sum(row.get("formatting_repair_count", 0) for row in predictions),
        "prompt_hash_mismatch_count": len(preflight["prompt_hash_mismatches"]),
        "duplicate_prediction_count": len(duplicate_values([row["prediction_id"] for row in predictions])),
        "model_identity_mismatch_count": sum(1 for model in actual_models if model != EXPECTED_RETURNED_MODEL),
        "ground_truth_dependency": False,
        "token_usage_totals": sum_usage(attempts),
        "total_api_calls": len(attempts),
        "LLAMA_PRODUCTION_INFERENCE_COMPLETE": len(predictions) == 396 and terminal_count == 396,
        "ALL_LLAMA_PREDICTIONS_VALID": len(predictions) == 396 and all(row["response_schema_valid"] for row in predictions),
    }


def build_blocked_summary(run_manifest: dict[str, Any], preflight: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "phase6g4c_llama_execution_summary_v1",
        "run_id": run_manifest["run_id"],
        "preflight_passed": False,
        "preflight_failures": preflight["failures"],
        "exact_requested_backend_model": REQUEST_MODEL,
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
        "model_mismatch_count": 0,
        "transport_retry_count": 0,
        "formatting_repair_count": 0,
        "prompt_hash_mismatch_count": len(preflight["prompt_hash_mismatches"]),
        "duplicate_prediction_count": 0,
        "model_identity_mismatch_count": 0,
        "ground_truth_dependency": False,
        "token_usage_totals": {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0},
        "total_api_calls": 0,
        "LLAMA_PRODUCTION_INFERENCE_COMPLETE": False,
        "ALL_LLAMA_PREDICTIONS_VALID": False,
    }


def build_run_manifest(repo_root: Path, preflight: dict[str, Any], guarded_batch_size: int, output_dir: Path, run_id: str) -> dict[str, Any]:
    shard = load_json(repo_root / LLAMA_SHARD)
    return {
        "schema_version": "phase6g4c_llama_run_manifest_v1",
        "run_id": run_id,
        "created_at_utc": iso_now(),
        "run_type": "final_real_llama_3_1_70b_instruct_production_inference",
        "model_key": MODEL_KEY,
        "experiment_model_label": EXPERIMENT_MODEL_LABEL,
        "exact_backend_model_id": REQUEST_MODEL,
        "expected_returned_model": EXPECTED_RETURNED_MODEL,
        "revision": REVISION,
        "backend_key": BACKEND_KEY,
        "backend_type": BACKEND_TYPE,
        "request_api": REQUEST_API,
        "endpoint_base_url": None,
        "endpoint_shape": "in_process_tokenizer_apply_chat_template_then_AutoModelForCausalLM_generate",
        "openai_compatible_http": False,
        "serving_framework": "transformers",
        "authentication_required": False,
        "credential_env_var_names": [],
        "hf_home": os.environ.get("HF_HOME", HF_HOME_FROZEN),
        "rendered_prompt_dataset": str(RENDERED_PROMPTS).replace("\\", "/"),
        "rendered_prompt_dataset_sha256": sha256_file(repo_root / RENDERED_PROMPTS),
        "llama_shard_manifest": str(LLAMA_SHARD).replace("\\", "/"),
        "llama_shard_sha256": sha256_file(repo_root / LLAMA_SHARD),
        "expected_request_count": 396,
        "shard_request_count": len(shard.get("requests", [])),
        "output_dir": str(output_dir).replace("\\", "/"),
        "guarded_batch_requested": True,
        "guarded_batch_limit": guarded_batch_size,
        "preflight": preflight,
        "inference_parameters": inference_parameters(),
        "native_json_schema_support": False,
        "contains_hidden_ground_truth": False,
    }


def build_failure_summary(attempts: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "phase6g4c_llama_failure_summary_v1",
        "blocked_by_preflight": False,
        "failure_codes": dict(Counter(row.get("failure_code") for row in attempts if row.get("failure_code"))),
        "final_statuses": dict(Counter(row["final_status"] for row in predictions)),
        "backend_failures": [row for row in predictions if row["final_status"] == "backend_failed"],
        "invalid_predictions": [row for row in predictions if row["final_status"] == "invalid_after_repair"],
    }


def write_report(path: Path, summary: dict[str, Any], preflight: dict[str, Any]) -> None:
    lines = [
        "# Phase 6G.4C Llama 3.1 70B Instruct Production QC Report",
        "",
        f"- Preflight passed: `{str(preflight['passed']).lower()}`",
        f"- Preflight failures: `{preflight['failures']}`",
        f"- Exact backend model: `{REQUEST_MODEL}`",
        f"- Backend type: `{BACKEND_TYPE}`",
        f"- Max new tokens: `{MAX_NEW_TOKENS}`",
        f"- Do sample: `false`",
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
        f"- Formatting repairs: `{summary['formatting_repair_count']}`",
        f"- `LLAMA_PRODUCTION_INFERENCE_COMPLETE`: `{str(summary['LLAMA_PRODUCTION_INFERENCE_COMPLETE']).lower()}`",
        f"- `ALL_LLAMA_PREDICTIONS_VALID`: `{str(summary['ALL_LLAMA_PREDICTIONS_VALID']).lower()}`",
        "",
        "No accuracy, scoring, hidden ground truth, GPT, Claude, or Centaur execution is included.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def normalize_llama_response_text(raw_text: str | None) -> dict[str, str | None]:
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
    return {"normalized_response_text": "\n".join(lines[1:-1]).strip(), "response_normalization": "markdown_json_fence_removed" if opening == "```json" else "markdown_generic_fence_removed"}


def llama_model_record(repo_root: Path) -> dict[str, Any]:
    registry = load_json(repo_root / PHASE6G2D_MODEL_REGISTRY)
    return next(row for row in registry["models"] if row["model_key"] == MODEL_KEY)


def llama_backend_record(repo_root: Path) -> dict[str, Any]:
    registry = load_json(repo_root / PHASE6G2D_BACKEND_REGISTRY)
    return next(row for row in registry["backends"] if row["backend_key"] == BACKEND_KEY)


def inference_parameters() -> dict[str, Any]:
    return {"max_new_tokens": MAX_NEW_TOKENS, "do_sample": False, "temperature_sent": False, "top_p_sent": False, "top_k_sent": False, "seed_sent": False, "repetition_penalty_sent": False, "response_format_sent": False, "stop_sequences_sent": False, "pad_token_id_policy": "tokenizer.eos_token_id", "local_files_only": True, "revision": REVISION}


def prediction_id(request_ref: dict[str, Any]) -> str:
    stable = "::".join([request_ref["rendered_prompt_id"], MODEL_KEY, "phase6g4c_llama_production"])
    return f"phase6g4c_llama_pred_{hashlib.sha256(stable.encode('utf-8')).hexdigest()[:32]}"


def inference_config_hash() -> str:
    return sha256_json({"model": REQUEST_MODEL, **inference_parameters()})


def normalize_usage(usage: dict[str, Any] | None) -> dict[str, Any]:
    usage = usage or {}
    return {"input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"), "reasoning_tokens": None, "total_tokens": usage.get("total_tokens")}


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


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()
