"""Phase 6G.4D Centaur production inference runner."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import tempfile
import time
import traceback
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


SCHEMA_VERSION = "phase6g4d_centaur_production_inference_v1"
OUTPUT_DIR = Path("llm-experiments/outputs/final/model-predictions/source/centaur")
CENTAUR_NATIVE_OUTPUT_DIR = OUTPUT_DIR
DIAGNOSTIC_OUTPUT_DIR = OUTPUT_DIR / "diagnostics"
RENDERED_PROMPTS = Path("llm-experiments/outputs/final/rendered-prompts/rendered_final_prompts.jsonl")
CENTAUR_SHARD = Path("llm-experiments/outputs/final/rendered-prompts/centaur_request_shard_manifest.json")
PROMPT_HASH_MANIFEST = Path("llm-experiments/outputs/final/rendered-prompts/prompt_hash_manifest.json")
PHASE6G3_FREEZE = Path("llm-experiments/outputs/final/rendered-prompts/prompt_freeze_manifest.json")
PHASE6G2D_READINESS = Path("llm-experiments/outputs/final/inference-config/readiness.json")
PHASE6G2D_MODEL_REGISTRY = Path("llm-experiments/outputs/final/inference-config/model_registry.json")
PHASE6G2D_BACKEND_REGISTRY = Path("llm-experiments/outputs/final/inference-config/backend_registry.json")
PHASE6G2D_CAPABILITY_MATRIX = Path("llm-experiments/outputs/final/inference-config/capability_matrix.json")
PHASE6G2D_INFERENCE_CONFIG = Path("llm-experiments/outputs/final/inference-config/inference_config.json")
PHASE6G1_GATE = Path("llm-experiments/outputs/final/prompt-data/readiness_gate.json")
RESPONSE_SCHEMA = Path("llm-experiments/schema/preference_prediction_response_v1.json")

RUN_ID = "phase6g4d_centaur_production_run_01"
CENTAUR_NATIVE_RUN_ID = "phase6g4d_centaur_native_run_02"
MODEL_KEY = "centaur"
EXPERIMENT_MODEL_LABEL = "Centaur"
REQUEST_MODEL = "marcelbinz/Llama-3.1-Centaur-70B-adapter"
EXPECTED_RETURNED_MODEL = REQUEST_MODEL
REVISION = "159600db8be99dc183c289923148dfd96cbd8e07"
BASE_MODEL = "unsloth/Meta-Llama-3.1-70B-bnb-4bit"
BASE_REVISION = "a009b8db2439814febe725486a5ed388f12a8744"
ADAPTER_SNAPSHOT = Path("/workspace/huggingface/hub/models--marcelbinz--Llama-3.1-Centaur-70B-adapter/snapshots/159600db8be99dc183c289923148dfd96cbd8e07")
BASE_SNAPSHOT = Path("/workspace/huggingface/hub/models--unsloth--Meta-Llama-3.1-70B-bnb-4bit/snapshots/a009b8db2439814febe725486a5ed388f12a8744")
BACKEND_KEY = "runpod_centaur_adapter_verified"
BACKEND_TYPE = "runpod_centaur_adapter"
REQUEST_API = "FastLanguageModel.generate"
PYTHON_EXECUTABLE = "/workspace/unsloth_env/bin/python"
MAX_SEQ_LENGTH = 32768
UNDERLYING_TOKENIZER_LIMIT = 131072
MAX_NEW_TOKENS = 256
MAX_TRANSPORT_RETRIES = 2
MAX_FORMAT_REPAIRS = 1
TERMINAL_STATUSES = {"valid_primary", "valid_after_repair", "invalid_after_repair", "backend_failed", "output_budget_exhausted", "quota_exhausted", "refusal", "model_mismatch"}
NORMALIZER_VERSION = "phase6g4d_centaur_response_normalizer_v1"
CENTAUR_RECOVERY_OUTPUT_DIR = OUTPUT_DIR / "recovery"
CENTAUR_NATIVE_DIAGNOSTIC_OUTPUT_DIR = OUTPUT_DIR / "native-choice-diagnostics"
VERIFIED_PROMPT_SERIALIZATION_STRATEGY = "phase6g2c_verified_raw_prompt_text_no_chat_template"
VERIFIED_TOKENIZER_INVOCATION = "tokenizer(prompt_text, return_tensors='pt')['input_ids']"
VERIFIED_GENERATION_INVOCATION = "model.generate(input_ids, max_new_tokens=N, do_sample=False, pad_token_id=tokenizer.eos_token_id)"
MESSAGE_SERIALIZATION_CONTRACT = "deterministic_concatenation_of_frozen_phase6d_system_and_user_content_no_semantic_wording_changes"
CENTAUR_LEFT_CHOICE_MARKER = " <<"
CENTAUR_RIGHT_CHOICE_MARKER = ">>"
CENTAUR_NATIVE_CANDIDATES = ("A", "B", "C", "D", "E")
CENTAUR_NATIVE_INTERFACE_EVIDENCE = {
    "model_card": "Centaur model card says human choices are encapsulated by << and >> and recommends adapting prompts accordingly.",
    "test_adapter": "Official test_adapter.py computes tokenizer(' <<').input_ids[1:] and tokenizer('>>').input_ids[1:] for DataCollatorForCompletionOnlyLM boundaries.",
    "test_adapter_full_log_likelihoods": "Official full-log-likelihood script evaluates completion-only losses over marker-delimited response spans.",
}

_TOKENIZER: Any = None
_MODEL: Any = None
_TEMP_ADAPTER_DIR: tempfile.TemporaryDirectory[str] | None = None


class CentaurRuntimeError(RuntimeError):
    def __init__(self, stage: str, original: BaseException):
        super().__init__(str(original))
        self.stage = stage
        self.original = original


def run_centaur_production(repo_root: Path, guarded_batch_size: int = 5, output_dir: Path = OUTPUT_DIR, run_id: str = RUN_ID) -> dict[str, Any]:
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
        write_json(out / "failure_summary.json", {"schema_version": "phase6g4d_centaur_failure_summary_v1", "blocked_by_preflight": True, "failures": preflight["failures"]})
        write_report(out / "centaur_production_qc_report.md", summary, preflight)
        return summary

    response_schema = load_response_schema(repo_root / RESPONSE_SCHEMA)
    rendered = {row["rendered_prompt_id"]: row for row in load_jsonl(repo_root / RENDERED_PROMPTS)}
    shard = load_json(repo_root / CENTAUR_SHARD)
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
    write_report(out / "centaur_production_qc_report.md", summary, preflight)
    return summary


def run_centaur_native_likelihood_production(
    repo_root: Path,
    guarded_batch_size: int = 5,
    output_dir: Path = CENTAUR_NATIVE_OUTPUT_DIR,
    run_id: str = CENTAUR_NATIVE_RUN_ID,
) -> dict[str, Any]:
    if guarded_batch_size < 1:
        raise ValueError("--guarded-batch-size must be at least 1")
    out = repo_root / output_dir
    out.mkdir(parents=True, exist_ok=True)
    preflight = run_native_preflight(repo_root, output_dir)
    run_manifest = build_native_run_manifest(repo_root, preflight, guarded_batch_size, output_dir, run_id)
    write_json(out / "run_manifest.json", run_manifest)
    if not preflight["passed"]:
        summary = build_native_blocked_summary(run_manifest, preflight)
        write_json(out / "preflight_report.json", preflight)
        write_json(out / "execution_summary.json", summary)
        write_json(out / "capability_matrix.json", final_model_capability_matrix())
        write_native_report(out / "centaur_native_production_qc_report.md", summary, preflight)
        return summary

    rendered = {row["rendered_prompt_id"]: row for row in load_jsonl(repo_root / RENDERED_PROMPTS)}
    shard = load_json(repo_root / CENTAUR_SHARD)
    existing_predictions = load_jsonl(out / "native_predictions.jsonl")
    completed_ids = {
        row["request_id"]
        for row in existing_predictions
        if row.get("native_status") == "valid_native_likelihood_prediction"
    }
    executed_this_invocation = 0
    stopped_after_guarded_batch = False
    cumulative_forward_passes = 0
    cumulative_candidate_evaluations = 0

    for request_ref in shard["requests"]:
        if request_ref["request_id"] in completed_ids:
            continue
        if executed_this_invocation >= guarded_batch_size:
            stopped_after_guarded_batch = True
            break
        started = time.perf_counter()
        scoring = invoke_centaur_native_likelihood(rendered[request_ref["rendered_prompt_id"]]["messages"])
        latency = time.perf_counter() - started
        prediction = build_native_prediction_record(request_ref, scoring, run_id, latency)
        if not validate_native_prediction_record(prediction)["valid"]:
            raise RuntimeError(f"invalid native Centaur prediction for {request_ref['request_id']}")
        append_jsonl(out / "native_predictions.jsonl", [prediction])
        append_jsonl(out / "candidate_score_log.jsonl", native_candidate_score_rows(prediction))
        completed_ids.add(request_ref["request_id"])
        executed_this_invocation += 1
        cumulative_forward_passes += scoring.get("model_forward_passes", 0)
        cumulative_candidate_evaluations += scoring.get("candidate_evaluations", 0)

    predictions = load_jsonl(out / "native_predictions.jsonl")
    summary = build_native_execution_summary(
        run_manifest,
        predictions,
        preflight,
        executed_this_invocation,
        stopped_after_guarded_batch,
        cumulative_candidate_evaluations,
        cumulative_forward_passes,
    )
    write_json(out / "execution_summary.json", summary)
    write_json(out / "capability_matrix.json", final_model_capability_matrix())
    write_native_report(out / "centaur_native_production_qc_report.md", summary, preflight)
    return summary


def run_preflight(repo_root: Path, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    prompt_verification = verify_prompt_package(repo_root)
    phase6g1 = load_json(repo_root / PHASE6G1_GATE)
    phase6g2d = load_json(repo_root / PHASE6G2D_READINESS)
    phase6g3 = load_json(repo_root / PHASE6G3_FREEZE)
    inference_config = load_json(repo_root / PHASE6G2D_INFERENCE_CONFIG)
    model_record = centaur_model_record(repo_root)
    backend_record = centaur_backend_record(repo_root)
    capability = centaur_capability_record(repo_root)
    shard = load_json(repo_root / CENTAUR_SHARD)
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
    dependency_names = ["torch", "transformers", "peft", "bitsandbytes", "accelerate", "unsloth"]
    cuda_available = cuda_is_available()
    checks = {
        "phase6d_prompt_package_frozen": bool(prompt_verification.get("PHASE6D_PROMPT_PACKAGE_FROZEN")),
        "phase6g1_real_data_ready": bool(phase6g1.get("REAL_PHASE6B_READY")),
        "phase6g2d_production_ready": bool(phase6g2d.get("PRODUCTION_INFERENCE_READY")),
        "phase6g3_prompt_freeze_ready": bool(phase6g3.get("REAL_PRODUCTION_PROMPTS_FROZEN")),
        "centaur_shard_manifest_exists": (repo_root / CENTAUR_SHARD).exists(),
        "centaur_shard_count_valid": len(requests) == 396 and condition_counts.get("non_history") == 198 and condition_counts.get("personalised_history") == 198,
        "centaur_request_ids_unique": not duplicate_values([row["request_id"] for row in requests]),
        "centaur_model_ids_valid": {row.get("exact_model_id") for row in requests} == {REQUEST_MODEL} and {row.get("model_key") for row in requests} == {MODEL_KEY},
        "prompt_hashes_valid": not hash_mismatches,
        "model_identity_frozen": model_record.get("exact_model_id") == REQUEST_MODEL and model_record.get("revision") == REVISION and model_record.get("adapter_snapshot") == ADAPTER_SNAPSHOT.as_posix() and model_record.get("base_snapshot") == BASE_SNAPSHOT.as_posix(),
        "backend_configuration_frozen": backend_record.get("backend_key") == BACKEND_KEY and backend_record.get("backend_type") == BACKEND_TYPE and backend_record.get("request_api") == REQUEST_API and backend_record.get("backend_verified") is True,
        "runpod_auth_contract_frozen": backend_record.get("authentication", {}).get("required") is True and backend_record.get("authentication", {}).get("credential_env_var_names") == ["RUNPOD_CENTAUR_ENDPOINT_URL", "RUNPOD_API_TOKEN"],
        "loader_configuration_frozen": backend_record.get("health_check", {}).get("loader") == "unsloth.FastLanguageModel.from_pretrained" and backend_record.get("health_check", {}).get("max_seq_length") == MAX_SEQ_LENGTH and backend_record.get("health_check", {}).get("load_in_4bit") is True,
        "local_adapter_snapshot_exists": ADAPTER_SNAPSHOT.exists(),
        "local_base_snapshot_exists": BASE_SNAPSHOT.exists(),
        "runtime_dependencies_available": all(util.find_spec(name) for name in dependency_names),
        "cuda_available": cuda_available,
        "frozen_decoding_policy_valid": inference_config.get("decoding_policy", {}).get(MODEL_KEY) == "greedy_do_sample_false" and capability.get("do_sample") is False,
        "frozen_max_output_tokens_valid": capability.get("max_new_tokens") == MAX_NEW_TOKENS and inference_config.get("common_cross_model_policy", {}).get("max_output_tokens") == MAX_NEW_TOKENS,
        "frozen_schema_valid": inference_config.get("common_cross_model_policy", {}).get("local_response_validation_schema") == "preference_prediction_response_v1",
        "output_directory_production_centaur_namespace": repo_relative_output_path(repo_root, output_dir) == OUTPUT_DIR.as_posix(),
        "no_hidden_ground_truth_loaded": not shard.get("contains_hidden_ground_truth", False),
    }
    failures = [key for key, value in checks.items() if not value]
    return {
        "schema_version": "phase6g4d_centaur_preflight_v1",
        "checked_at_utc": iso_now(),
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "centaur_shard_request_count": len(requests),
        "condition_counts": dict(sorted(condition_counts.items())),
        "prompt_hash_mismatches": hash_mismatches,
        "duplicate_request_ids": duplicate_values([row["request_id"] for row in requests]),
        "runtime_policy": "Run inside verified RunPod /workspace/unsloth_env with local cached adapter/base snapshots only.",
        "credential_policy": "Frozen backend records RunPod endpoint/token env vars, but local in-pod FastLanguageModel.generate does not serialize credential values.",
        "ground_truth_dependency": False,
        "deployment_summary": deployment_summary(repo_root),
    }


def run_native_preflight(repo_root: Path, output_dir: Path = CENTAUR_NATIVE_OUTPUT_DIR) -> dict[str, Any]:
    base = run_preflight(repo_root, OUTPUT_DIR)
    shard = load_json(repo_root / CENTAUR_SHARD)
    requests = shard.get("requests", [])
    condition_counts = Counter(row["condition"] for row in requests)
    marker_tokenization = native_marker_tokenization_probe()
    gpu_metadata = collect_gpu_metadata()
    checks = {
        key: value
        for key, value in base["checks"].items()
        if key != "output_directory_production_centaur_namespace"
    }
    checks.update({
        "output_directory_native_centaur_namespace": repo_relative_output_path(repo_root, output_dir) == CENTAUR_NATIVE_OUTPUT_DIR.as_posix(),
        "original_run01_namespace_separate": CENTAUR_NATIVE_OUTPUT_DIR.as_posix() != OUTPUT_DIR.as_posix(),
        "native_left_marker_exact": CENTAUR_LEFT_CHOICE_MARKER == " <<",
        "native_right_marker_exact": CENTAUR_RIGHT_CHOICE_MARKER == ">>",
        "native_candidate_set_exact": CENTAUR_NATIVE_CANDIDATES == ("A", "B", "C", "D", "E"),
        "native_marker_tokenization_available": marker_tokenization["available"],
        "native_marker_tokenization_valid": marker_tokenization["valid"],
        "a100_deployment_expectation": any("A100" in str(name) for name in gpu_metadata.get("gpu_names", [])),
        "native_ratings_explicitly_unsupported": centaur_protocol_compatibility_record()["rating_error_metrics_comparable"] is False,
        "no_hidden_ground_truth_loaded": not shard.get("contains_hidden_ground_truth", False),
    })
    failures = [key for key, value in checks.items() if not value]
    return {
        "schema_version": "phase6g4d_centaur_native_preflight_v1",
        "checked_at_utc": iso_now(),
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "centaur_shard_request_count": len(requests),
        "condition_counts": dict(sorted(condition_counts.items())),
        "prompt_hash_mismatches": base["prompt_hash_mismatches"],
        "duplicate_request_ids": base["duplicate_request_ids"],
        "native_marker_tokenization": marker_tokenization,
        "gpu": gpu_metadata,
        "native_candidate_set": list(CENTAUR_NATIVE_CANDIDATES),
        "expected_candidate_evaluations": len(requests) * len(CENTAUR_NATIVE_CANDIDATES),
        "expected_request_count": 396,
        "expected_condition_counts": {"non_history": 198, "personalised_history": 198},
        "runtime_policy": "Run inside verified RunPod /workspace/unsloth_env with local cached adapter/base snapshots only.",
        "native_output_namespace": CENTAUR_NATIVE_OUTPUT_DIR.as_posix(),
        "source_json_run01_namespace": OUTPUT_DIR.as_posix(),
        "run01_preservation_policy": "Original generic-JSON Run 01 remains immutable historical interface-failure evidence.",
        "ground_truth_dependency": False,
        "protocol_compatibility": centaur_protocol_compatibility_record(),
        "capability_matrix": final_model_capability_matrix(),
    }


def execute_prediction(request_ref: dict[str, Any], rendered_prompt: dict[str, Any], prompt_hash: str, response_schema: dict[str, Any], run_id: str) -> list[dict[str, Any]]:
    attempts = []
    primary = call_with_transport_retries(request_ref, rendered_prompt["messages"], prompt_hash, response_schema, "primary", 1, run_id)
    attempts.extend(primary)
    final_primary = primary[-1]
    if should_repair(final_primary["validation_status"], final_primary["request_status"], final_primary.get("raw_response_text")):
        repair_messages = render_format_repair(final_primary["raw_response_text"], response_schema)["messages"]
        repair = call_with_transport_retries(request_ref, repair_messages, prompt_hash, response_schema, "format_repair", 2, run_id)
        attempts.extend(repair[: MAX_FORMAT_REPAIRS + MAX_TRANSPORT_RETRIES])
    return attempts


def call_with_transport_retries(request_ref: dict[str, Any], messages: list[dict[str, str]], prompt_hash: str, response_schema: dict[str, Any], attempt_type: str, attempt_number: int, run_id: str) -> list[dict[str, Any]]:
    attempts = []
    for transport_attempt in range(1, MAX_TRANSPORT_RETRIES + 2):
        started = time.perf_counter()
        started_at = iso_now()
        try:
            provider = invoke_centaur(messages, attempt_type)
            raw_text = provider.get("decoded_text")
            normalized = normalize_centaur_response_text(raw_text)
            validation = validate_response_text(normalized["normalized_response_text"], response_schema)
            request_status = provider.get("status", "completed")
            error = provider.get("error")
        except Exception as exc:  # pragma: no cover - live RunPod runtime only
            diagnostics = centaur_exception_diagnostics(exc)
            raw_text = None
            normalized = normalize_centaur_response_text(raw_text)
            validation = validate_response_text(None, response_schema)
            request_status = "error"
            error = {"type": diagnostics["runtime_error_category"], "message": diagnostics["exception_message"], "backend_stage": diagnostics["backend_stage"]}
            provider = {"metadata": {"local_runtime_diagnostic": diagnostics}, "usage": None, "incomplete_details": None, "error": error, "runtime_diagnostic": diagnostics}
        failure = classify_failure({"status": request_status, "error": error, "incomplete_details": provider.get("incomplete_details")}, validation)
        attempt = build_attempt_record(request_ref, prompt_hash, attempt_type, attempt_number, transport_attempt, request_status, raw_text, normalized, validation, provider, failure, time.perf_counter() - started, started_at, run_id)
        attempts.append(attempt)
        if request_status == "completed" or failure["failure_code"] not in RETRYABLE_FAILURES or transport_attempt > MAX_TRANSPORT_RETRIES:
            return attempts
    return attempts


def invoke_centaur(messages: list[dict[str, str]], attempt_type: str, max_new_tokens: int = MAX_NEW_TOKENS) -> dict[str, Any]:
    global _MODEL, _TOKENIZER
    try:
        import torch  # type: ignore[import-not-found]
        from unsloth import FastLanguageModel  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover
        raise CentaurRuntimeError("runtime_import", exc) from exc
    if _TOKENIZER is None or _MODEL is None:
        try:
            adapter_path = prepare_offline_adapter_copy()
        except Exception as exc:  # pragma: no cover
            raise CentaurRuntimeError("adapter_config_prepare", exc) from exc
        try:
            _MODEL, _TOKENIZER = FastLanguageModel.from_pretrained(model_name=adapter_path, max_seq_length=MAX_SEQ_LENGTH, dtype=None, load_in_4bit=True)
            FastLanguageModel.for_inference(_MODEL)
        except Exception as exc:  # pragma: no cover
            raise CentaurRuntimeError("model_load", exc) from exc
    started = time.perf_counter()
    try:
        prompt_text = serialize_centaur_messages(messages)
        input_ids = tokenize_centaur_prompt(_TOKENIZER, prompt_text)
    except Exception as exc:  # pragma: no cover
        raise CentaurRuntimeError("tokenizer", exc) from exc
    try:
        input_ids = move_tensor_to_device(input_ids, "cuda")
    except Exception as exc:  # pragma: no cover
        raise CentaurRuntimeError("device_transfer", exc) from exc
    try:
        with torch.inference_mode():
            outputs = _MODEL.generate(input_ids, max_new_tokens=max_new_tokens, do_sample=False, pad_token_id=_TOKENIZER.eos_token_id)
    except Exception as exc:  # pragma: no cover
        raise CentaurRuntimeError("generation", exc) from exc
    try:
        prompt_length = input_ids.shape[-1]
        generated = outputs[0][prompt_length:]
        decoded = _TOKENIZER.decode(generated, skip_special_tokens=True)
        decoded_with_special_tokens = _TOKENIZER.decode(generated, skip_special_tokens=False)
    except Exception as exc:  # pragma: no cover
        raise CentaurRuntimeError("decode", exc) from exc
    generated_token_count = len(generated) if hasattr(generated, "__len__") else None
    status = "incomplete" if generated_token_count == max_new_tokens else "completed"
    token_diagnostics = build_token_diagnostics(
        _TOKENIZER,
        input_ids,
        generated,
        decoded,
        decoded_with_special_tokens,
        max_new_tokens,
    )
    return {
        "status": status,
        "decoded_text": decoded,
        "metadata": {
            "model": REQUEST_MODEL,
            "revision": REVISION,
            "base_model": BASE_MODEL,
            "base_revision": BASE_REVISION,
            "request_api": REQUEST_API,
            "attempt_type": attempt_type,
            "latency_seconds": time.perf_counter() - started,
            "backend_type": BACKEND_TYPE,
            "generated_token_count": generated_token_count,
            "diagnostic_max_new_tokens": max_new_tokens if max_new_tokens != MAX_NEW_TOKENS else None,
            **token_diagnostics,
        },
        "usage": {"input_tokens": token_diagnostics["prompt_token_count"], "output_tokens": generated_token_count, "total_tokens": token_diagnostics["prompt_token_count"] + generated_token_count} if generated_token_count is not None else None,
        "incomplete_details": {"reason": "max_output_tokens"} if status == "incomplete" else None,
    }


def run_centaur_runtime_diagnostic(repo_root: Path, output_dir: Path = DIAGNOSTIC_OUTPUT_DIR, max_new_tokens: int = 8) -> dict[str, Any]:
    if max_new_tokens < 1:
        raise ValueError("--diagnostic-max-new-tokens must be at least 1")
    out = repo_root / output_dir
    out.mkdir(parents=True, exist_ok=True)
    preflight = run_preflight(repo_root, OUTPUT_DIR)
    messages = [
        {"role": "system", "content": "You are a diagnostic runtime checker. Return only a tiny JSON object."},
        {"role": "user", "content": '{"diagnostic":"ok"}'},
    ]
    manifest = {
        "schema_version": "phase6g4d_centaur_runtime_diagnostic_v1",
        "created_at_utc": iso_now(),
        "diagnostic_only": True,
        "appends_production_predictions": False,
        "appends_production_attempt_log": False,
        "ground_truth_dependency": False,
        "prompt_source": "synthetic_non_study_minimal_prompt",
        "exact_backend_model_id": REQUEST_MODEL,
        "revision": REVISION,
        "base_model": BASE_MODEL,
        "base_revision": BASE_REVISION,
        "adapter_snapshot": ADAPTER_SNAPSHOT.as_posix(),
        "base_snapshot": BASE_SNAPSHOT.as_posix(),
        "backend_type": BACKEND_TYPE,
        "request_api": REQUEST_API,
        "production_max_new_tokens": MAX_NEW_TOKENS,
        "diagnostic_max_new_tokens": max_new_tokens,
        "preflight_passed": preflight["passed"],
        "preflight_failures": preflight["failures"],
        "runtime_success": False,
        "runtime_diagnostic": None,
        "provider_metadata": None,
        "transport_comparison": {
            "verified_path": VERIFIED_PROMPT_SERIALIZATION_STRATEGY,
            "raw_concatenation_path": "same semantic message concatenation; production transport now matches verified Phase 6G.2C tokenization/generation invocation",
            "diagnostic_only": True,
            "uses_study_prompts": False,
        },
    }
    if not preflight["passed"]:
        manifest["runtime_diagnostic"] = {"runtime_error_category": "preflight_blocked", "preflight_failures": preflight["failures"]}
        write_json(out / "runtime_diagnostic.json", manifest)
        return manifest
    try:
        provider = invoke_centaur(messages, "runtime_diagnostic", max_new_tokens=max_new_tokens)
        manifest["runtime_success"] = provider.get("status") == "completed"
        manifest["provider_metadata"] = sanitize_provider_metadata(provider.get("metadata") or {})
        metadata = provider.get("metadata") or {}
        manifest["runtime_diagnostic"] = {
            "status": provider.get("status"),
            "incomplete_details": provider.get("incomplete_details"),
            "decoded_text_preview": truncate_text(provider.get("decoded_text"), 400),
            "decoded_text_with_special_tokens_preview": truncate_text(metadata.get("decoded_text_with_special_tokens"), 400),
            "prompt_serialization_strategy": metadata.get("prompt_serialization_strategy"),
            "tokenizer_invocation": metadata.get("tokenizer_invocation"),
            "generation_invocation": metadata.get("generation_invocation"),
            "prompt_token_count": metadata.get("prompt_token_count"),
            "first_input_token_ids": metadata.get("first_input_token_ids"),
            "last_input_token_ids": metadata.get("last_input_token_ids"),
            "generated_token_ids": metadata.get("generated_token_ids"),
            "generated_token_count": metadata.get("generated_token_count"),
            "eos_token_id": metadata.get("eos_token_id"),
            "bos_token_id": metadata.get("bos_token_id"),
            "pad_token_id": metadata.get("pad_token_id"),
            "eot_token_id": metadata.get("eot_token_id"),
            "first_generated_token_equals_eos_or_eot": metadata.get("first_generated_token_equals_eos_or_eot"),
            "tokenizer_chat_template_available": metadata.get("tokenizer_chat_template_available"),
            "special_tokens_map": metadata.get("special_tokens_map"),
            "generation_stop_interpretation": metadata.get("generation_stop_interpretation"),
        }
    except Exception as exc:  # pragma: no cover - live RunPod diagnostic only
        manifest["runtime_diagnostic"] = centaur_exception_diagnostics(exc)
    write_json(out / "runtime_diagnostic.json", manifest)
    return manifest


def run_centaur_native_choice_diagnostic(
    repo_root: Path,
    output_dir: Path = CENTAUR_NATIVE_DIAGNOSTIC_OUTPUT_DIR,
    max_new_tokens: int = 8,
) -> dict[str, Any]:
    if max_new_tokens < 1:
        raise ValueError("--diagnostic-max-new-tokens must be at least 1")
    out = repo_root / output_dir
    out.mkdir(parents=True, exist_ok=True)
    preflight = run_preflight(repo_root, OUTPUT_DIR)
    messages = synthetic_native_choice_messages()
    prompt_text = build_centaur_native_choice_prompt(messages)
    manifest = {
        "schema_version": "phase6g4d_centaur_native_choice_diagnostic_v1",
        "created_at_utc": iso_now(),
        "diagnostic_only": True,
        "appends_production_predictions": False,
        "appends_production_attempt_log": False,
        "modifies_failed_run01": False,
        "ground_truth_dependency": False,
        "prompt_source": "synthetic_non_study_behavioral_choice_prompt",
        "native_interface": centaur_native_interface_record(),
        "protocol_compatibility": centaur_protocol_compatibility_record(),
        "preflight_passed": preflight["passed"],
        "preflight_failures": preflight["failures"],
        "runtime_success": False,
        "runtime_diagnostic": None,
        "provider_metadata": None,
    }
    if not preflight["passed"]:
        manifest["runtime_diagnostic"] = {"runtime_error_category": "preflight_blocked", "preflight_failures": preflight["failures"]}
        write_json(out / "native_choice_diagnostic.json", manifest)
        return manifest
    try:
        provider = invoke_centaur_native_choice_prompt(prompt_text, "native_choice_diagnostic", max_new_tokens=max_new_tokens)
        metadata = provider.get("metadata") or {}
        native_completion = parse_native_choice_completion(provider.get("decoded_text") or "")
        manifest["provider_metadata"] = sanitize_provider_metadata(metadata)
        manifest["runtime_diagnostic"] = {
            "status": provider.get("status"),
            "incomplete_details": provider.get("incomplete_details"),
            "decoded_text_preview": truncate_text(provider.get("decoded_text"), 400),
            "decoded_text_with_special_tokens_preview": truncate_text(metadata.get("decoded_text_with_special_tokens"), 400),
            "input_suffix_token_ids": metadata.get("last_input_token_ids"),
            "left_choice_marker_token_ids": metadata.get("left_choice_marker_token_ids"),
            "right_choice_marker_token_ids": metadata.get("right_choice_marker_token_ids"),
            "generated_token_ids": metadata.get("generated_token_ids"),
            "generated_token_count": metadata.get("generated_token_count"),
            "first_generated_token_equals_eos_or_eot": metadata.get("first_generated_token_equals_eos_or_eot"),
            "closing_marker_observed": native_completion["closing_marker_observed"],
            "native_choice_completion_text": native_completion["completion_text"],
            "valid_native_choice_completion": native_completion["valid_native_choice_completion"],
            "generation_stop_interpretation": metadata.get("generation_stop_interpretation"),
        }
        manifest["runtime_success"] = native_generation_diagnostic_success(manifest["runtime_diagnostic"])
    except Exception as exc:  # pragma: no cover - live RunPod diagnostic only
        manifest["runtime_diagnostic"] = centaur_exception_diagnostics(exc)
    write_json(out / "native_choice_diagnostic.json", manifest)
    return manifest


def prepare_offline_adapter_copy() -> str:
    global _TEMP_ADAPTER_DIR
    if _TEMP_ADAPTER_DIR is not None:
        return _TEMP_ADAPTER_DIR.name
    _TEMP_ADAPTER_DIR = tempfile.TemporaryDirectory(prefix="phase6g4d_centaur_adapter_")
    dst = Path(_TEMP_ADAPTER_DIR.name)
    shutil.copytree(ADAPTER_SNAPSHOT, dst, dirs_exist_ok=True)
    config_path = dst / "adapter_config.json"
    config = load_json(config_path)
    config["base_model_name_or_path"] = BASE_SNAPSHOT.as_posix()
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return dst.as_posix()


def serialize_centaur_messages(messages: list[dict[str, str]]) -> str:
    parts = []
    for message in messages:
        role = message.get("role")
        content = message.get("content", "")
        if role == "system":
            parts.append(content)
        elif role == "user":
            parts.append(content)
        else:
            parts.append(content)
    return "\n\n".join(part for part in parts if part).strip()


def synthetic_native_choice_messages() -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "Synthetic diagnostic only. Predict a human choice from the listed options.",
        },
        {
            "role": "user",
            "content": "A participant sees two unlabeled boxes. Option A gives one point. Option B gives two points. Which option is the human choice?",
        },
    ]


def build_centaur_native_choice_prompt(messages: list[dict[str, str]]) -> str:
    return serialize_centaur_messages(messages).rstrip() + CENTAUR_LEFT_CHOICE_MARKER


def parse_native_choice_completion(decoded_text: str) -> dict[str, Any]:
    closing_marker_observed = CENTAUR_RIGHT_CHOICE_MARKER in decoded_text
    completion_text = decoded_text.split(CENTAUR_RIGHT_CHOICE_MARKER, 1)[0].strip()
    return {
        "completion_text": completion_text,
        "closing_marker_observed": closing_marker_observed,
        "valid_native_choice_completion": completion_text in CENTAUR_NATIVE_CANDIDATES,
    }


def native_generation_diagnostic_success(runtime_diagnostic: dict[str, Any]) -> bool:
    return bool(
        runtime_diagnostic.get("valid_native_choice_completion") is True
        and runtime_diagnostic.get("closing_marker_observed") is True
    )


def centaur_native_interface_record() -> dict[str, Any]:
    return {
        "left_choice_marker": CENTAUR_LEFT_CHOICE_MARKER,
        "right_choice_marker": CENTAUR_RIGHT_CHOICE_MARKER,
        "prompt_ends_with_left_marker": True,
        "expected_completion": "model generates candidate choice content after left marker, optionally followed by right marker",
        "closing_marker_stop_condition_recommended": True,
        "eos_after_closing_marker": "not established locally; diagnostic records generated token sequence",
        "typical_choice_values": "task-defined human choice labels or strings; Phase 6 candidate probe uses A-E labels",
        "faithful_inference_method": "candidate_completion_log_likelihood_preferred_over_unconstrained_json_generation",
        "evidence": CENTAUR_NATIVE_INTERFACE_EVIDENCE,
    }


def centaur_protocol_compatibility_record() -> dict[str, Any]:
    return {
        "winner_accuracy_comparable": True,
        "winner_accuracy_basis": "A-E candidate completion likelihoods can select one preferred mix without inspecting ground truth.",
        "ranking_metrics_comparable": True,
        "ranking_metrics_basis": "A-E candidate completion likelihoods provide deterministic descending candidate ranking.",
        "rating_error_metrics_comparable": False,
        "rating_error_basis": "No frozen, scientifically justified mapping from Centaur choice likelihoods to 0-100 ratings exists in the Phase 6 protocol.",
        "ratings_output_policy": "unsupported_for_centaur_until_user_approves_protocol_amendment_or_pre_registered_mapping",
        "schema_equality_warning": "Forcing JSON ratings from Centaur free generation would be scientifically misleading after immediate-EOS evidence.",
        "ground_truth_dependency": False,
    }


def invoke_centaur_native_choice_prompt(prompt_text: str, attempt_type: str, max_new_tokens: int = 8) -> dict[str, Any]:
    global _MODEL, _TOKENIZER
    try:
        import torch  # type: ignore[import-not-found]
        from unsloth import FastLanguageModel  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover
        raise CentaurRuntimeError("runtime_import", exc) from exc
    if _TOKENIZER is None or _MODEL is None:
        try:
            adapter_path = prepare_offline_adapter_copy()
        except Exception as exc:  # pragma: no cover
            raise CentaurRuntimeError("adapter_config_prepare", exc) from exc
        try:
            _MODEL, _TOKENIZER = FastLanguageModel.from_pretrained(model_name=adapter_path, max_seq_length=MAX_SEQ_LENGTH, dtype=None, load_in_4bit=True)
            FastLanguageModel.for_inference(_MODEL)
        except Exception as exc:  # pragma: no cover
            raise CentaurRuntimeError("model_load", exc) from exc
    started = time.perf_counter()
    try:
        input_ids = tokenize_centaur_prompt(_TOKENIZER, prompt_text)
        left_marker_ids, right_marker_ids = centaur_choice_marker_token_ids(_TOKENIZER)
    except Exception as exc:  # pragma: no cover
        raise CentaurRuntimeError("tokenizer", exc) from exc
    try:
        input_ids = move_tensor_to_device(input_ids, "cuda")
    except Exception as exc:  # pragma: no cover
        raise CentaurRuntimeError("device_transfer", exc) from exc
    try:
        with torch.inference_mode():
            outputs = _MODEL.generate(input_ids, max_new_tokens=max_new_tokens, do_sample=False, pad_token_id=_TOKENIZER.eos_token_id)
    except Exception as exc:  # pragma: no cover
        raise CentaurRuntimeError("generation", exc) from exc
    try:
        prompt_length = input_ids.shape[-1]
        generated = outputs[0][prompt_length:]
        decoded = _TOKENIZER.decode(generated, skip_special_tokens=True)
        decoded_with_special_tokens = _TOKENIZER.decode(generated, skip_special_tokens=False)
    except Exception as exc:  # pragma: no cover
        raise CentaurRuntimeError("decode", exc) from exc
    generated_token_count = len(generated) if hasattr(generated, "__len__") else None
    status = "incomplete" if generated_token_count == max_new_tokens else "completed"
    token_diagnostics = build_token_diagnostics(_TOKENIZER, input_ids, generated, decoded, decoded_with_special_tokens, max_new_tokens)
    return {
        "status": status,
        "decoded_text": decoded,
        "metadata": {
            "model": REQUEST_MODEL,
            "revision": REVISION,
            "base_model": BASE_MODEL,
            "base_revision": BASE_REVISION,
            "request_api": REQUEST_API,
            "attempt_type": attempt_type,
            "latency_seconds": time.perf_counter() - started,
            "backend_type": BACKEND_TYPE,
            "native_interface": centaur_native_interface_record(),
            "left_choice_marker_token_ids": left_marker_ids,
            "right_choice_marker_token_ids": right_marker_ids,
            **token_diagnostics,
        },
        "usage": {"input_tokens": token_diagnostics["prompt_token_count"], "output_tokens": generated_token_count, "total_tokens": token_diagnostics["prompt_token_count"] + generated_token_count} if generated_token_count is not None else None,
        "incomplete_details": {"reason": "max_output_tokens"} if status == "incomplete" else None,
    }


def tokenize_centaur_prompt(tokenizer: Any, prompt_text: str) -> Any:
    """Mirror the verified Phase 6G.2C RunPod probe transport exactly."""
    return tokenizer(prompt_text, return_tensors="pt")["input_ids"]


def tokenizer_input_ids(tokenizer: Any, text: str) -> list[int]:
    encoded = tokenizer(text)
    if hasattr(encoded, "input_ids"):
        return [int(value) for value in encoded.input_ids]
    if isinstance(encoded, dict) and "input_ids" in encoded:
        return token_ids_to_list(encoded["input_ids"])
    raise TypeError("tokenizer did not return input_ids")


def centaur_choice_marker_token_ids(tokenizer: Any) -> tuple[list[int], list[int]]:
    return (
        tokenizer_input_ids(tokenizer, CENTAUR_LEFT_CHOICE_MARKER)[1:],
        tokenizer_input_ids(tokenizer, CENTAUR_RIGHT_CHOICE_MARKER)[1:],
    )


def centaur_candidate_completion_token_ids(tokenizer: Any, candidate: str) -> dict[str, Any]:
    if candidate not in CENTAUR_NATIVE_CANDIDATES:
        raise ValueError(f"unsupported Centaur native candidate: {candidate}")
    candidate_only = tokenizer_input_ids(tokenizer, candidate)[1:]
    with_closing = tokenizer_input_ids(tokenizer, candidate + CENTAUR_RIGHT_CHOICE_MARKER)[1:]
    return {
        "candidate": candidate,
        "candidate_token_ids": candidate_only,
        "closing_marker_token_ids": with_closing[len(candidate_only):],
        "scored_token_count": len(candidate_only),
        "closing_marker_scored": False,
    }


def centaur_candidate_scoring_plan(tokenizer: Any, prompt_prefix: str, candidate: str) -> dict[str, Any]:
    token_info = centaur_candidate_completion_token_ids(tokenizer, candidate)
    prefix_ids = tokenizer_input_ids(tokenizer, prompt_prefix)
    full_ids = tokenizer_input_ids(tokenizer, prompt_prefix + candidate + CENTAUR_RIGHT_CHOICE_MARKER)
    scored_start = len(prefix_ids)
    scored_end = scored_start + len(token_info["candidate_token_ids"])
    return {
        "candidate": candidate,
        "prefix_token_ids": prefix_ids,
        "full_token_ids": full_ids,
        "candidate_token_ids": token_info["candidate_token_ids"],
        "closing_marker_token_ids": token_info["closing_marker_token_ids"],
        "scored_start": scored_start,
        "scored_end": scored_end,
        "scored_token_indices": list(range(scored_start, scored_end)),
        "closing_marker_scored": False,
    }


def build_centaur_candidate_scoring_prompts(
    messages: list[dict[str, str]],
    candidates: tuple[str, ...] = CENTAUR_NATIVE_CANDIDATES,
) -> list[dict[str, str]]:
    prompt_prefix = build_centaur_native_choice_prompt(messages)
    return [
        {
            "candidate": candidate,
            "prompt_prefix": prompt_prefix,
            "completion_text": candidate + CENTAUR_RIGHT_CHOICE_MARKER,
            "full_text": prompt_prefix + candidate + CENTAUR_RIGHT_CHOICE_MARKER,
            "scored_span": "candidate_content_only_between_left_and_right_markers",
            "ground_truth_dependency": False,
        }
        for candidate in candidates
    ]


def rank_centaur_candidate_scores(candidate_scores: dict[str, float]) -> dict[str, Any]:
    ranking = sorted(candidate_scores, key=lambda candidate: (-candidate_scores[candidate], candidate))
    probabilities = softmax_probabilities(candidate_scores)
    return {
        "predicted_preferred_mix": ranking[0] if ranking else None,
        "predicted_ranking": ranking,
        "candidate_log_likelihoods": {candidate: candidate_scores[candidate] for candidate in ranking},
        "candidate_probabilities": {candidate: probabilities[candidate] for candidate in ranking},
        "predicted_ratings": None,
        "predicted_ratings_supported": False,
        "ratings_policy": centaur_protocol_compatibility_record()["ratings_output_policy"],
        "ground_truth_dependency": False,
    }


def softmax_probabilities(candidate_scores: dict[str, float]) -> dict[str, float]:
    if not candidate_scores:
        return {}
    max_score = max(candidate_scores.values())
    exp_scores = {candidate: math.exp(score - max_score) for candidate, score in candidate_scores.items()}
    denominator = sum(exp_scores.values())
    return {candidate: value / denominator for candidate, value in exp_scores.items()}


def score_centaur_choice_candidates(
    model: Any,
    tokenizer: Any,
    messages: list[dict[str, str]],
    candidates: tuple[str, ...] = CENTAUR_NATIVE_CANDIDATES,
) -> dict[str, Any]:
    try:
        import torch  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover
        raise CentaurRuntimeError("runtime_import", exc) from exc

    prompt_prefix = build_centaur_native_choice_prompt(messages)
    plans = [centaur_candidate_scoring_plan(tokenizer, prompt_prefix, candidate) for candidate in candidates]
    full_id_rows = [plan["full_token_ids"] for plan in plans]
    max_len = max(len(row) for row in full_id_rows)
    pad_token_id = safe_int(getattr(tokenizer, "pad_token_id", None))
    if pad_token_id is None:
        pad_token_id = safe_int(getattr(tokenizer, "eos_token_id", None)) or 0
    padded_rows = [row + [pad_token_id] * (max_len - len(row)) for row in full_id_rows]
    attention_rows = [[1] * len(row) + [0] * (max_len - len(row)) for row in full_id_rows]
    device = resolve_model_device(model)
    input_ids = torch.tensor(padded_rows, device=device)
    attention_mask = torch.tensor(attention_rows, device=device)
    with torch.inference_mode():
        outputs = model(input_ids=input_ids, attention_mask=attention_mask)
    logits = outputs.logits
    scores: dict[str, float] = {}
    details = []
    for row_index, plan in enumerate(plans):
        candidate = plan["candidate"]
        full_ids = plan["full_token_ids"]
        scored_start = plan["scored_start"]
        scored_end = plan["scored_end"]
        log_probs = torch.nn.functional.log_softmax(logits[row_index].float(), dim=-1)
        token_log_likelihoods = []
        for token_position in range(scored_start, scored_end):
            target_token_id = full_ids[token_position]
            token_log_likelihoods.append(float(log_probs[token_position - 1, target_token_id].detach().cpu()))
        score = sum(token_log_likelihoods)
        scores[candidate] = score
        details.append({
            "candidate": candidate,
            "candidate_token_ids": plan["candidate_token_ids"],
            "closing_marker_token_ids": plan["closing_marker_token_ids"],
            "scored_token_indices": plan["scored_token_indices"],
            "closing_marker_scored": False,
            "token_log_likelihoods": token_log_likelihoods,
            "log_likelihood": score,
            "mean_token_log_likelihood": score / len(token_log_likelihoods) if token_log_likelihoods else None,
        })
    ranked = rank_centaur_candidate_scores(scores)
    probabilities = ranked["candidate_probabilities"]
    for detail in details:
        detail["probability"] = probabilities[detail["candidate"]]
    return {
        "schema_version": "phase6g4d_centaur_candidate_likelihood_scores_v1",
        "native_interface": centaur_native_interface_record(),
        "protocol_compatibility": centaur_protocol_compatibility_record(),
        "prompt_prefix_sha256": hashlib.sha256(prompt_prefix.encode("utf-8")).hexdigest(),
        "candidate_scores": details,
        "candidate_evaluations": len(details),
        "model_forward_passes": 1,
        "batched_candidates_per_forward_pass": len(details),
        "scoring_definition": "conditional_log_likelihood_of_candidate_label_tokens_after_exact_left_marker_excluding_prompt_and_closing_marker_tokens",
        "tie_breaking": "descending_summed_log_likelihood_then_A_to_E_lexical_order",
        **ranked,
    }


def resolve_model_device(model: Any) -> str:
    if hasattr(model, "device"):
        return str(model.device)
    device_map = getattr(model, "hf_device_map", None)
    if isinstance(device_map, dict):
        for value in device_map.values():
            if isinstance(value, str) and value not in {"cpu", "disk"}:
                return value
    return "cuda"


def move_tensor_to_device(value: Any, device: str) -> Any:
    return value.to(device) if hasattr(value, "to") else value


def build_token_diagnostics(
    tokenizer: Any,
    input_ids: Any,
    generated: Any,
    decoded_skip_special_tokens: str,
    decoded_with_special_tokens: str,
    max_new_tokens: int,
) -> dict[str, Any]:
    input_token_ids = token_ids_to_list(input_ids)
    generated_token_ids = token_ids_to_list(generated)
    eot_token_id = token_to_id(tokenizer, "<|eot_id|>")
    eos_token_id = safe_int(getattr(tokenizer, "eos_token_id", None))
    bos_token_id = safe_int(getattr(tokenizer, "bos_token_id", None))
    pad_token_id = safe_int(getattr(tokenizer, "pad_token_id", None))
    first_generated = generated_token_ids[0] if generated_token_ids else None
    terminal_ids = {value for value in [eos_token_id, eot_token_id] if value is not None}
    first_is_terminal_special = first_generated in terminal_ids if first_generated is not None else False
    return {
        "prompt_serialization_strategy": VERIFIED_PROMPT_SERIALIZATION_STRATEGY,
        "message_serialization": MESSAGE_SERIALIZATION_CONTRACT,
        "tokenizer_invocation": VERIFIED_TOKENIZER_INVOCATION,
        "generation_invocation": VERIFIED_GENERATION_INVOCATION,
        "uses_tokenizer_chat_template": False,
        "manual_llama3_chat_headers_used": False,
        "assistant_generation_header_appended": False,
        "bos_handling": "tokenizer_default_for_raw_prompt_text",
        "eos_eot_handling": "pad_token_id_set_to_tokenizer_eos_token_id_no_explicit_stop_sequences",
        "prompt_token_count": len(input_token_ids),
        "first_input_token_ids": input_token_ids[:8],
        "last_input_token_ids": input_token_ids[-8:],
        "generated_token_ids": generated_token_ids,
        "generated_token_count": len(generated_token_ids),
        "eos_token_id": eos_token_id,
        "bos_token_id": bos_token_id,
        "pad_token_id": pad_token_id,
        "eot_token_id": eot_token_id,
        "first_generated_token_equals_eos_or_eot": first_is_terminal_special,
        "tokenizer_chat_template_available": bool(getattr(tokenizer, "chat_template", None)),
        "special_tokens_map": dict(getattr(tokenizer, "special_tokens_map", {}) or {}),
        "decoded_text_skip_special_tokens": decoded_skip_special_tokens,
        "decoded_text_with_special_tokens": decoded_with_special_tokens,
        "generation_stop_interpretation": interpret_generation_stop(generated_token_ids, terminal_ids, max_new_tokens),
    }


def interpret_generation_stop(generated_token_ids: list[int], terminal_ids: set[int], max_new_tokens: int) -> str:
    if not generated_token_ids:
        return "no_tokens_generated"
    if generated_token_ids[0] in terminal_ids:
        return "immediate_eos_or_eot_special_token"
    if len(generated_token_ids) >= max_new_tokens:
        return "max_new_tokens_reached"
    return "completed_before_max_new_tokens"


def token_to_id(tokenizer: Any, token: str) -> int | None:
    converter = getattr(tokenizer, "convert_tokens_to_ids", None)
    if not callable(converter):
        return None
    try:
        value = converter(token)
    except Exception:
        return None
    if value in {None, getattr(tokenizer, "unk_token_id", None)}:
        return None
    return safe_int(value)


def token_ids_to_list(value: Any) -> list[int]:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list) and value and isinstance(value[0], list):
        value = value[0]
    if isinstance(value, list):
        return [int(item) for item in value]
    try:
        return [int(item) for item in value]
    except TypeError:
        return []


def safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def centaur_empty_response_recovery_eligible_request_ids(
    predictions: list[dict[str, Any]],
    attempts: list[dict[str, Any]] | None = None,
) -> list[str]:
    attempts_by_request: dict[str, list[dict[str, Any]]] = {}
    for attempt in attempts or []:
        attempts_by_request.setdefault(attempt.get("request_id"), []).append(attempt)
    eligible = []
    for prediction in predictions:
        if prediction.get("final_status") != "invalid_after_repair":
            continue
        if prediction.get("response_schema_valid"):
            continue
        if (prediction.get("raw_final_response_text") or "") != "":
            continue
        request_attempts = attempts_by_request.get(prediction.get("request_id"), [])
        if request_attempts and not any(
            row.get("failure_code") == "empty_response"
            and row.get("request_status") == "completed"
            and (row.get("raw_response_text") or "") == ""
            for row in request_attempts
        ):
            continue
        eligible.append(prediction["request_id"])
    return sorted(eligible)


def build_empty_response_recovery_manifest(
    source_output_dir: Path,
    predictions: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    recovery_output_dir: Path = CENTAUR_RECOVERY_OUTPUT_DIR,
) -> dict[str, Any]:
    eligible_request_ids = centaur_empty_response_recovery_eligible_request_ids(predictions, attempts)
    return {
        "schema_version": "phase6g4d_centaur_empty_response_recovery_manifest_v1",
        "created_at_utc": iso_now(),
        "recovery_run_id": "phase6g4d_centaur_recovery_run_02",
        "recovery_reason": "operational_empty_response_after_verified_transport_defect",
        "source_run_id": RUN_ID,
        "source_output_dir": str(source_output_dir).replace("\\", "/"),
        "recovery_output_dir": str(recovery_output_dir).replace("\\", "/"),
        "source_failure_records_preserved": True,
        "writes_to_separate_namespace": True,
        "eligibility_rule": "final_status=invalid_after_repair AND failure_code=empty_response AND empty raw response; no correctness or ground truth used",
        "eligible_request_count": len(eligible_request_ids),
        "eligible_request_ids": eligible_request_ids,
        "valid_predictions_recovery_eligible": False,
        "ground_truth_dependency": False,
        "execute_recovery_now": False,
    }


def invoke_centaur_native_likelihood(messages: list[dict[str, str]]) -> dict[str, Any]:
    global _MODEL, _TOKENIZER
    try:
        from unsloth import FastLanguageModel  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover
        raise CentaurRuntimeError("runtime_import", exc) from exc
    if _TOKENIZER is None or _MODEL is None:
        try:
            adapter_path = prepare_offline_adapter_copy()
        except Exception as exc:  # pragma: no cover
            raise CentaurRuntimeError("adapter_config_prepare", exc) from exc
        try:
            _MODEL, _TOKENIZER = FastLanguageModel.from_pretrained(model_name=adapter_path, max_seq_length=MAX_SEQ_LENGTH, dtype=None, load_in_4bit=True)
            FastLanguageModel.for_inference(_MODEL)
        except Exception as exc:  # pragma: no cover
            raise CentaurRuntimeError("model_load", exc) from exc
    try:
        return score_centaur_choice_candidates(_MODEL, _TOKENIZER, messages)
    except CentaurRuntimeError:
        raise
    except Exception as exc:  # pragma: no cover
        raise CentaurRuntimeError("native_likelihood_scoring", exc) from exc


def build_native_prediction_record(
    request_ref: dict[str, Any],
    scoring: dict[str, Any],
    run_id: str,
    latency_seconds: float,
) -> dict[str, Any]:
    return {
        "schema_version": "phase6g4d_centaur_native_prediction_v1",
        "run_id": run_id,
        "request_id": request_ref["request_id"],
        "prediction_id": native_prediction_id(request_ref),
        "rendered_prompt_id": request_ref["rendered_prompt_id"],
        "prediction_example_id": request_ref["prediction_example_id"],
        "condition": request_ref["condition"],
        "model_key": MODEL_KEY,
        "experiment_model_label": EXPERIMENT_MODEL_LABEL,
        "exact_requested_backend_model": REQUEST_MODEL,
        "actual_returned_model": REQUEST_MODEL,
        "model_revision": REVISION,
        "base_model": BASE_MODEL,
        "base_revision": BASE_REVISION,
        "backend_key": BACKEND_KEY,
        "backend_type": BACKEND_TYPE,
        "prompt_hash": request_ref["prompt_hash"],
        "inference_config_hash": native_inference_config_hash(),
        "native_status": "valid_native_likelihood_prediction",
        "terminal": True,
        "predicted_preferred_mix": scoring["predicted_preferred_mix"],
        "predicted_ranking": scoring["predicted_ranking"],
        "candidate_scores": native_candidate_scores_by_label(scoring["candidate_scores"]),
        "candidate_log_likelihoods": scoring["candidate_log_likelihoods"],
        "candidate_probabilities": scoring["candidate_probabilities"],
        "predicted_ratings_supported": False,
        "predicted_ratings": None,
        "ratings_policy": scoring["ratings_policy"],
        "native_interface": scoring["native_interface"],
        "protocol_compatibility": scoring["protocol_compatibility"],
        "scoring_definition": scoring["scoring_definition"],
        "tie_breaking": scoring["tie_breaking"],
        "candidate_evaluations": scoring["candidate_evaluations"],
        "model_forward_passes": scoring["model_forward_passes"],
        "batched_candidates_per_forward_pass": scoring["batched_candidates_per_forward_pass"],
        "latency_seconds": latency_seconds,
        "ground_truth_dependency": False,
    }


def native_candidate_scores_by_label(candidate_scores: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        row["candidate"]: {
            "candidate_completion_text": row["candidate"] + CENTAUR_RIGHT_CHOICE_MARKER,
            "candidate_token_ids": row["candidate_token_ids"],
            "token_log_probabilities": row["token_log_likelihoods"],
            "log_likelihood": row["log_likelihood"],
            "mean_token_log_likelihood": row["mean_token_log_likelihood"],
            "scored_candidate_token_count": len(row["candidate_token_ids"]),
            "closing_marker_token_ids": row["closing_marker_token_ids"],
            "closing_marker_scored": row["closing_marker_scored"],
            "probability": row["probability"],
        }
        for row in candidate_scores
    }


def native_candidate_score_rows(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for candidate, score in prediction["candidate_scores"].items():
        rows.append({
            "schema_version": "phase6g4d_centaur_native_candidate_score_v1",
            "run_id": prediction["run_id"],
            "request_id": prediction["request_id"],
            "prediction_id": prediction["prediction_id"],
            "rendered_prompt_id": prediction["rendered_prompt_id"],
            "condition": prediction["condition"],
            "candidate": candidate,
            **score,
            "ground_truth_dependency": False,
        })
    return rows


def validate_native_prediction_record(prediction: dict[str, Any]) -> dict[str, Any]:
    errors = []
    if prediction.get("predicted_preferred_mix") not in CENTAUR_NATIVE_CANDIDATES:
        errors.append("preferred_mix_not_in_A_E")
    ranking = prediction.get("predicted_ranking")
    if sorted(ranking or []) != list(CENTAUR_NATIVE_CANDIDATES):
        errors.append("ranking_not_complete_A_E")
    scores = prediction.get("candidate_scores") or {}
    if set(scores) != set(CENTAUR_NATIVE_CANDIDATES):
        errors.append("candidate_scores_not_complete_A_E")
    probabilities = []
    for candidate in CENTAUR_NATIVE_CANDIDATES:
        score = scores.get(candidate) or {}
        if not math.isfinite(float(score.get("log_likelihood", float("nan")))):
            errors.append(f"{candidate}_log_likelihood_not_finite")
        probability = score.get("probability")
        if probability is None or not math.isfinite(float(probability)):
            errors.append(f"{candidate}_probability_not_finite")
        else:
            probabilities.append(float(probability))
        if score.get("scored_candidate_token_count", 0) < 1:
            errors.append(f"{candidate}_missing_scored_tokens")
    if probabilities and not math.isclose(sum(probabilities), 1.0, rel_tol=1e-6, abs_tol=1e-6):
        errors.append("candidate_probabilities_do_not_sum_to_one")
    if prediction.get("predicted_ratings_supported") is not False or prediction.get("predicted_ratings") is not None:
        errors.append("ratings_fabricated_or_not_marked_unsupported")
    return {"valid": not errors, "errors": errors}


def build_native_run_manifest(
    repo_root: Path,
    preflight: dict[str, Any],
    guarded_batch_size: int,
    output_dir: Path,
    run_id: str,
) -> dict[str, Any]:
    shard = load_json(repo_root / CENTAUR_SHARD)
    return {
        "schema_version": "phase6g4d_centaur_native_run_manifest_v1",
        "run_id": run_id,
        "created_at_utc": iso_now(),
        "run_type": "final_real_centaur_native_likelihood_production_inference",
        "source_json_run01_namespace": OUTPUT_DIR.as_posix(),
        "source_json_run01_preserved_as_historical_interface_failure": True,
        "native_output_namespace": str(output_dir).replace("\\", "/"),
        "model_key": MODEL_KEY,
        "experiment_model_label": EXPERIMENT_MODEL_LABEL,
        "exact_backend_model_id": REQUEST_MODEL,
        "revision": REVISION,
        "adapter_snapshot": ADAPTER_SNAPSHOT.as_posix(),
        "base_model": BASE_MODEL,
        "base_revision": BASE_REVISION,
        "base_snapshot": BASE_SNAPSHOT.as_posix(),
        "backend_key": BACKEND_KEY,
        "backend_type": BACKEND_TYPE,
        "request_api": "FastLanguageModel.forward_logits",
        "python_executable": PYTHON_EXECUTABLE,
        "rendered_prompt_dataset": str(RENDERED_PROMPTS).replace("\\", "/"),
        "rendered_prompt_dataset_sha256": sha256_file(repo_root / RENDERED_PROMPTS),
        "centaur_shard_manifest": str(CENTAUR_SHARD).replace("\\", "/"),
        "centaur_shard_sha256": sha256_file(repo_root / CENTAUR_SHARD),
        "expected_request_count": 396,
        "shard_request_count": len(shard.get("requests", [])),
        "expected_candidate_evaluations": len(shard.get("requests", [])) * len(CENTAUR_NATIVE_CANDIDATES),
        "guarded_batch_requested": True,
        "guarded_batch_limit": guarded_batch_size,
        "preflight": preflight,
        "native_interface": centaur_native_interface_record(),
        "protocol_compatibility": centaur_protocol_compatibility_record(),
        "candidate_set": list(CENTAUR_NATIVE_CANDIDATES),
        "candidate_completion_syntax": {candidate: candidate + CENTAUR_RIGHT_CHOICE_MARKER for candidate in CENTAUR_NATIVE_CANDIDATES},
        "scoring_definition": "conditional_log_likelihood_of_candidate_label_tokens_after_exact_left_marker_excluding_prompt_and_closing_marker_tokens",
        "scoring_batching": "five_A_E_candidates_for_one_request_in_one_forward_pass",
        "tie_breaking": "descending_summed_log_likelihood_then_A_to_E_lexical_order",
        "contains_hidden_ground_truth": False,
    }


def build_native_execution_summary(
    run_manifest: dict[str, Any],
    predictions: list[dict[str, Any]],
    preflight: dict[str, Any],
    executed_this_invocation: int,
    stopped_after_guarded_batch: bool,
    candidate_evaluations_this_invocation: int,
    model_forward_passes_this_invocation: int,
) -> dict[str, Any]:
    conditions = Counter(row["condition"] for row in predictions)
    validations = [validate_native_prediction_record(row) for row in predictions]
    valid_count = sum(1 for row in validations if row["valid"])
    duplicate_prediction_count = len(duplicate_values([row["prediction_id"] for row in predictions]))
    terminal_count = sum(1 for row in predictions if row.get("terminal"))
    remaining = max(0, 396 - valid_count)
    total_candidate_evaluations = sum(row.get("candidate_evaluations", 0) for row in predictions)
    total_forward_passes = sum(row.get("model_forward_passes", 0) for row in predictions)
    return {
        "schema_version": "phase6g4d_centaur_native_execution_summary_v1",
        "run_id": run_manifest["run_id"],
        "preflight_passed": preflight["passed"],
        "expected_predictions": 396,
        "guarded_batch_requested": True,
        "guarded_batch_limit": run_manifest["guarded_batch_limit"],
        "predictions_executed_this_invocation": executed_this_invocation,
        "remaining_predictions": remaining,
        "stopped_after_guarded_batch": stopped_after_guarded_batch,
        "attempted_prediction_count": len(predictions),
        "terminal_prediction_count": terminal_count,
        "valid_native_prediction_count": valid_count,
        "non_history_count": conditions.get("non_history", 0),
        "personalised_history_count": conditions.get("personalised_history", 0),
        "duplicate_prediction_count": duplicate_prediction_count,
        "candidate_evaluations_this_invocation": candidate_evaluations_this_invocation,
        "model_forward_passes_this_invocation": model_forward_passes_this_invocation,
        "total_candidate_evaluations": total_candidate_evaluations,
        "total_model_forward_passes": total_forward_passes,
        "expected_total_candidate_evaluations": 396 * len(CENTAUR_NATIVE_CANDIDATES),
        "predicted_ratings_supported": False,
        "ground_truth_dependency": False,
        "protocol_compatibility": centaur_protocol_compatibility_record(),
        "CENTAUR_NATIVE_PRODUCTION_INFERENCE_COMPLETE": len(predictions) == 396 and valid_count == 396 and duplicate_prediction_count == 0,
        "ALL_CENTAUR_NATIVE_PREDICTIONS_VALID": len(predictions) == 396 and valid_count == 396 and duplicate_prediction_count == 0,
    }


def build_native_blocked_summary(run_manifest: dict[str, Any], preflight: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "phase6g4d_centaur_native_execution_summary_v1",
        "run_id": run_manifest["run_id"],
        "preflight_passed": False,
        "preflight_failures": preflight["failures"],
        "expected_predictions": 396,
        "guarded_batch_requested": True,
        "guarded_batch_limit": run_manifest["guarded_batch_limit"],
        "predictions_executed_this_invocation": 0,
        "remaining_predictions": 396,
        "stopped_after_guarded_batch": False,
        "attempted_prediction_count": 0,
        "terminal_prediction_count": 0,
        "valid_native_prediction_count": 0,
        "non_history_count": 0,
        "personalised_history_count": 0,
        "duplicate_prediction_count": 0,
        "candidate_evaluations_this_invocation": 0,
        "model_forward_passes_this_invocation": 0,
        "total_candidate_evaluations": 0,
        "total_model_forward_passes": 0,
        "expected_total_candidate_evaluations": 396 * len(CENTAUR_NATIVE_CANDIDATES),
        "predicted_ratings_supported": False,
        "ground_truth_dependency": False,
        "protocol_compatibility": centaur_protocol_compatibility_record(),
        "CENTAUR_NATIVE_PRODUCTION_INFERENCE_COMPLETE": False,
        "ALL_CENTAUR_NATIVE_PREDICTIONS_VALID": False,
    }


def final_model_capability_matrix() -> dict[str, Any]:
    return {
        "schema_version": "phase6g4d_model_capability_matrix_v1",
        "models": {
            "gpt": {"winner": "supported", "ranking": "supported", "rating": "supported"},
            "claude_sonnet": {"winner": "supported", "ranking": "supported", "rating": "supported"},
            "llama_3_1_70b_instruct": {"winner": "supported", "ranking": "supported", "rating": "supported"},
            "centaur": {
                "winner": "supported_native_candidate_likelihood",
                "ranking": "supported_native_candidate_likelihood",
                "rating": "unsupported",
            },
        },
        "evaluation_policy": {
            "winner_metrics": "all_four_models",
            "ranking_metrics": "all_four_models",
            "rating_error_metrics": "models_with_genuine_rating_predictions_only_exclude_centaur",
        },
        "ground_truth_dependency": False,
    }


def write_native_report(path: Path, summary: dict[str, Any], preflight: dict[str, Any]) -> None:
    lines = [
        "# Phase 6G.4D Centaur Native Production QC Report",
        "",
        f"- Preflight passed: `{str(preflight['passed']).lower()}`",
        f"- Preflight failures: `{preflight['failures']}`",
        f"- Native output namespace: `{CENTAUR_NATIVE_OUTPUT_DIR.as_posix()}`",
        f"- Source Run 01 preserved: `{OUTPUT_DIR.as_posix()}`",
        f"- Candidate syntax: `A>>`, `B>>`, `C>>`, `D>>`, `E>>` after prompt suffix ` <<`",
        f"- Scoring: `{summary.get('protocol_compatibility', {}).get('winner_accuracy_basis', '')}`",
        f"- Attempted predictions: `{summary['attempted_prediction_count']}`",
        f"- Remaining predictions: `{summary['remaining_predictions']}`",
        f"- Valid native predictions: `{summary['valid_native_prediction_count']}`",
        f"- Rating predictions supported: `{str(summary['predicted_ratings_supported']).lower()}`",
        f"- `CENTAUR_NATIVE_PRODUCTION_INFERENCE_COMPLETE`: `{str(summary['CENTAUR_NATIVE_PRODUCTION_INFERENCE_COMPLETE']).lower()}`",
        f"- `ALL_CENTAUR_NATIVE_PREDICTIONS_VALID`: `{str(summary['ALL_CENTAUR_NATIVE_PREDICTIONS_VALID']).lower()}`",
        "",
        "No accuracy, scoring against human ground truth, GPT, Claude, or Llama execution is included.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def build_attempt_record(request_ref: dict[str, Any], prompt_hash: str, attempt_type: str, attempt_number: int, transport_attempt: int, request_status: str, raw_text: str | None, normalized: dict[str, Any], validation: dict[str, Any], provider: dict[str, Any], failure: dict[str, Any], latency: float, started_at: str, run_id: str) -> dict[str, Any]:
    metadata = sanitize_provider_metadata(provider.get("metadata") or {})
    diagnostic = provider.get("runtime_diagnostic") or metadata.get("local_runtime_diagnostic") or {}
    actual_model = metadata.get("model")
    if actual_model and actual_model != EXPECTED_RETURNED_MODEL:
        failure = {"failure_code": "model_mismatch", "failure_category": "internal", "retryable": False}
    return {
        "schema_version": "phase6g4d_centaur_attempt_v1",
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
        "model_revision": REVISION,
        "base_model": BASE_MODEL,
        "base_revision": BASE_REVISION,
        "backend_key": BACKEND_KEY,
        "backend_type": BACKEND_TYPE,
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
        "exception_type": diagnostic.get("exception_type"),
        "exception_message": diagnostic.get("exception_message"),
        "backend_stage": diagnostic.get("backend_stage"),
        "runtime_error_category": diagnostic.get("runtime_error_category"),
        "cuda_oom_detected": diagnostic.get("cuda_oom_detected", False),
        "host_oom_detected": diagnostic.get("host_oom_detected", False),
        "traceback_tail": diagnostic.get("traceback_tail"),
        "failure_code": failure["failure_code"],
        "failure_category": failure["failure_category"],
        "retryable": failure["retryable"],
        **inference_parameters(),
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
    else:
        status = "invalid_after_repair" if repair_attempted else "invalid_after_repair"
    final = successful or attempts[-1]
    return {
        "schema_version": "phase6g4d_centaur_prediction_v1",
        "run_id": run_id,
        "request_id": request_ref["request_id"],
        "prediction_id": prediction_id(request_ref),
        "rendered_prompt_id": request_ref["rendered_prompt_id"],
        "prediction_example_id": request_ref["prediction_example_id"],
        "condition": request_ref["condition"],
        "model_key": MODEL_KEY,
        "experiment_model_label": EXPERIMENT_MODEL_LABEL,
        "exact_requested_backend_model": REQUEST_MODEL,
        "actual_returned_model": final.get("actual_returned_model"),
        "prompt_hash": request_ref["prompt_hash"],
        "final_status": status,
        "terminal": status in TERMINAL_STATUSES,
        "attempt_count": len(attempts),
        "transport_retry_count": sum(1 for row in attempts if row["transport_attempt_number"] > 1),
        "formatting_repair_count": sum(1 for row in attempts if row["attempt_type"] == "format_repair"),
        "response_schema_valid": bool(successful),
        "raw_final_response_text": final.get("raw_response_text"),
        "normalized_final_response_text": final.get("normalized_response_text"),
        "token_usage_totals": sum_usage(attempts),
    }


def build_execution_summary(run_manifest: dict[str, Any], attempts: list[dict[str, Any]], predictions: list[dict[str, Any]], preflight: dict[str, Any], executed_this_invocation: int, stopped_after_guarded_batch: bool) -> dict[str, Any]:
    statuses = Counter(row["final_status"] for row in predictions)
    conditions = Counter(row["condition"] for row in predictions)
    terminal_count = sum(1 for row in predictions if row["terminal"])
    actual_models = sorted({row.get("actual_returned_model") for row in attempts if row.get("actual_returned_model")})
    remaining = max(0, 396 - terminal_count)
    return {
        "schema_version": "phase6g4d_centaur_execution_summary_v1",
        "run_id": run_manifest["run_id"],
        "preflight_passed": preflight["passed"],
        "exact_requested_backend_model": REQUEST_MODEL,
        "actual_returned_models": actual_models,
        "expected_predictions": 396,
        "guarded_batch_requested": True,
        "guarded_batch_limit": run_manifest["guarded_batch_limit"],
        "predictions_executed_this_invocation": executed_this_invocation,
        "remaining_predictions": remaining,
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
        "duplicate_prediction_count": len(duplicate_values([row["prediction_id"] for row in predictions])),
        "ground_truth_dependency": False,
        "token_usage_totals": sum_usage(attempts),
        "total_api_calls": len(attempts),
        "CENTAUR_PRODUCTION_INFERENCE_COMPLETE": len(predictions) == 396 and terminal_count == 396,
        "ALL_CENTAUR_PREDICTIONS_VALID": len(predictions) == 396 and all(row["response_schema_valid"] for row in predictions),
    }


def build_blocked_summary(run_manifest: dict[str, Any], preflight: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "phase6g4d_centaur_execution_summary_v1",
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
        "duplicate_prediction_count": 0,
        "ground_truth_dependency": False,
        "token_usage_totals": {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0},
        "total_api_calls": 0,
        "CENTAUR_PRODUCTION_INFERENCE_COMPLETE": False,
        "ALL_CENTAUR_PREDICTIONS_VALID": False,
    }


def build_run_manifest(repo_root: Path, preflight: dict[str, Any], guarded_batch_size: int, output_dir: Path, run_id: str) -> dict[str, Any]:
    shard = load_json(repo_root / CENTAUR_SHARD)
    return {
        "schema_version": "phase6g4d_centaur_run_manifest_v1",
        "run_id": run_id,
        "created_at_utc": iso_now(),
        "run_type": "final_real_centaur_production_inference",
        "model_key": MODEL_KEY,
        "experiment_model_label": EXPERIMENT_MODEL_LABEL,
        "exact_backend_model_id": REQUEST_MODEL,
        "expected_returned_model": EXPECTED_RETURNED_MODEL,
        "revision": REVISION,
        "adapter_snapshot": ADAPTER_SNAPSHOT.as_posix(),
        "base_model": BASE_MODEL,
        "base_revision": BASE_REVISION,
        "base_snapshot": BASE_SNAPSHOT.as_posix(),
        "backend_key": BACKEND_KEY,
        "backend_type": BACKEND_TYPE,
        "request_api": REQUEST_API,
        "serving_framework": "unsloth",
        "python_executable": PYTHON_EXECUTABLE,
        "rendered_prompt_dataset": str(RENDERED_PROMPTS).replace("\\", "/"),
        "rendered_prompt_dataset_sha256": sha256_file(repo_root / RENDERED_PROMPTS),
        "centaur_shard_manifest": str(CENTAUR_SHARD).replace("\\", "/"),
        "centaur_shard_sha256": sha256_file(repo_root / CENTAUR_SHARD),
        "expected_request_count": 396,
        "shard_request_count": len(shard.get("requests", [])),
        "output_dir": str(output_dir).replace("\\", "/"),
        "guarded_batch_requested": True,
        "guarded_batch_limit": guarded_batch_size,
        "preflight": preflight,
        "inference_parameters": inference_parameters(),
        "message_serialization": MESSAGE_SERIALIZATION_CONTRACT,
        "prompt_transport": {
            "prompt_serialization_strategy": VERIFIED_PROMPT_SERIALIZATION_STRATEGY,
            "tokenizer_chat_template_available": False,
            "apply_chat_template_used": False,
            "manual_llama3_chat_headers_used": False,
            "assistant_generation_header_appended": False,
            "tokenizer_invocation": VERIFIED_TOKENIZER_INVOCATION,
            "generation_invocation": VERIFIED_GENERATION_INVOCATION,
            "verified_source": "llm-experiments/scripts/remote/verify_runpod_centaur.py::tokenize_probe and run_optional_probe",
        },
        "native_json_schema_support": False,
        "contains_hidden_ground_truth": False,
    }


def build_failure_summary(attempts: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "phase6g4d_centaur_failure_summary_v1",
        "blocked_by_preflight": False,
        "failure_codes": dict(Counter(row.get("failure_code") for row in attempts if row.get("failure_code"))),
        "final_statuses": dict(Counter(row["final_status"] for row in predictions)),
        "backend_failures": [row for row in predictions if row["final_status"] == "backend_failed"],
        "invalid_predictions": [row for row in predictions if row["final_status"] == "invalid_after_repair"],
    }


def write_report(path: Path, summary: dict[str, Any], preflight: dict[str, Any]) -> None:
    lines = [
        "# Phase 6G.4D Centaur Production QC Report",
        "",
        f"- Preflight passed: `{str(preflight['passed']).lower()}`",
        f"- Preflight failures: `{preflight['failures']}`",
        f"- Exact backend model: `{REQUEST_MODEL}`",
        f"- Backend type: `{BACKEND_TYPE}`",
        f"- Max new tokens: `{MAX_NEW_TOKENS}`",
        f"- Do sample: `false`",
        f"- Attempted predictions: `{summary['attempted_prediction_count']}`",
        f"- Remaining predictions: `{summary['remaining_predictions']}`",
        f"- Valid primary: `{summary['valid_primary_count']}`",
        f"- Valid after repair: `{summary['valid_after_repair_count']}`",
        f"- `CENTAUR_PRODUCTION_INFERENCE_COMPLETE`: `{str(summary['CENTAUR_PRODUCTION_INFERENCE_COMPLETE']).lower()}`",
        f"- `ALL_CENTAUR_PREDICTIONS_VALID`: `{str(summary['ALL_CENTAUR_PREDICTIONS_VALID']).lower()}`",
        "",
        "No accuracy, scoring, hidden ground truth, GPT, Claude, or Llama execution is included.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def normalize_centaur_response_text(raw_text: str | None) -> dict[str, str | None]:
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


def centaur_exception_diagnostics(exc: BaseException, fallback_stage: str = "local_backend") -> dict[str, Any]:
    stage = getattr(exc, "stage", fallback_stage)
    original = getattr(exc, "original", exc)
    message = sanitize_exception_message(str(original))
    category = classify_centaur_runtime_error(original, stage)
    return {
        "exception_type": type(original).__name__,
        "exception_message": message,
        "backend_stage": stage,
        "runtime_error_category": category,
        "cuda_oom_detected": is_cuda_oom(original),
        "host_oom_detected": is_host_oom(original),
        "traceback_tail": safe_traceback_tail(original),
    }


def classify_centaur_runtime_error(exc: BaseException, stage: str) -> str:
    message = str(exc).lower()
    if is_cuda_oom(exc):
        return "cuda_out_of_memory"
    if is_host_oom(exc):
        return "host_out_of_memory"
    if "bitsandbytes" in message or stage in {"adapter_config_prepare", "model_load"} and "4bit" in message:
        return "quantization_runtime_error"
    if stage in {"tokenizer", "decode"}:
        return "tokenizer_error"
    if stage == "model_load":
        return "model_load_error"
    if stage == "device_transfer":
        return "device_placement_error"
    if stage == "generation":
        return "generation_error"
    return "local_backend_error"


def deployment_summary(repo_root: Path) -> dict[str, Any]:
    model = centaur_model_record(repo_root)
    backend = centaur_backend_record(repo_root)
    capability = centaur_capability_record(repo_root)
    return {
        "model": model,
        "backend": backend,
        "capability": capability,
    }


def centaur_model_record(repo_root: Path) -> dict[str, Any]:
    registry = load_json(repo_root / PHASE6G2D_MODEL_REGISTRY)
    return next(row for row in registry["models"] if row["model_key"] == MODEL_KEY)


def centaur_backend_record(repo_root: Path) -> dict[str, Any]:
    registry = load_json(repo_root / PHASE6G2D_BACKEND_REGISTRY)
    return next(row for row in registry["backends"] if row["backend_key"] == BACKEND_KEY)


def centaur_capability_record(repo_root: Path) -> dict[str, Any]:
    matrix = load_json(repo_root / PHASE6G2D_CAPABILITY_MATRIX)
    return next(row for row in matrix["models"] if row["model_key"] == MODEL_KEY)


def inference_parameters() -> dict[str, Any]:
    return {"max_new_tokens": MAX_NEW_TOKENS, "max_seq_length": MAX_SEQ_LENGTH, "do_sample": False, "temperature_sent": False, "top_p_sent": False, "top_k_sent": False, "seed_sent": False, "response_format_sent": False, "stop_sequences_sent": False, "load_in_4bit": True, "dtype": None, "local_files_only": True, "adapter_revision": REVISION, "base_revision": BASE_REVISION}


def prediction_id(request_ref: dict[str, Any]) -> str:
    stable = "::".join([request_ref["rendered_prompt_id"], MODEL_KEY, "phase6g4d_centaur_production"])
    return f"phase6g4d_centaur_pred_{hashlib.sha256(stable.encode('utf-8')).hexdigest()[:32]}"


def inference_config_hash() -> str:
    return sha256_json({"model": REQUEST_MODEL, **inference_parameters()})


def native_prediction_id(request_ref: dict[str, Any]) -> str:
    stable = "::".join([request_ref["rendered_prompt_id"], MODEL_KEY, "phase6g4d_centaur_native_likelihood"])
    return f"phase6g4d_centaur_native_pred_{hashlib.sha256(stable.encode('utf-8')).hexdigest()[:32]}"


def native_inference_config_hash() -> str:
    return sha256_json({
        "model": REQUEST_MODEL,
        "adapter_revision": REVISION,
        "base_revision": BASE_REVISION,
        "native_left_marker": CENTAUR_LEFT_CHOICE_MARKER,
        "native_right_marker": CENTAUR_RIGHT_CHOICE_MARKER,
        "candidate_set": list(CENTAUR_NATIVE_CANDIDATES),
        "scoring_definition": "conditional_log_likelihood_candidate_label_tokens_only",
        "predicted_ratings_supported": False,
    })


def native_marker_tokenization_probe() -> dict[str, Any]:
    global _MODEL, _TOKENIZER
    if not (ADAPTER_SNAPSHOT.exists() and BASE_SNAPSHOT.exists()):
        return {
            "available": False,
            "valid": False,
            "reason": "local_adapter_or_base_snapshot_missing",
            "left_marker": CENTAUR_LEFT_CHOICE_MARKER,
            "right_marker": CENTAUR_RIGHT_CHOICE_MARKER,
        }
    try:
        from unsloth import FastLanguageModel  # type: ignore[import-not-found]

        if _TOKENIZER is None or _MODEL is None:
            adapter_path = prepare_offline_adapter_copy()
            _MODEL, _TOKENIZER = FastLanguageModel.from_pretrained(model_name=adapter_path, max_seq_length=MAX_SEQ_LENGTH, dtype=None, load_in_4bit=True)
            FastLanguageModel.for_inference(_MODEL)
        left_ids, right_ids = centaur_choice_marker_token_ids(_TOKENIZER)
        return {
            "available": True,
            "valid": bool(left_ids and right_ids),
            "left_marker": CENTAUR_LEFT_CHOICE_MARKER,
            "right_marker": CENTAUR_RIGHT_CHOICE_MARKER,
            "left_marker_token_ids": left_ids,
            "right_marker_token_ids": right_ids,
            "candidate_set": list(CENTAUR_NATIVE_CANDIDATES),
        }
    except Exception as exc:  # pragma: no cover - live RunPod preflight only
        return {
            "available": False,
            "valid": False,
            "reason": sanitize_exception_message(str(exc)),
            "left_marker": CENTAUR_LEFT_CHOICE_MARKER,
            "right_marker": CENTAUR_RIGHT_CHOICE_MARKER,
        }


def ensure_named_model_inputs(model_inputs: Any) -> dict[str, Any]:
    if not hasattr(model_inputs, "keys"):
        raise TypeError("tokenizer output did not return a mapping of named model inputs")
    named = {key: model_inputs[key] for key in model_inputs.keys()}
    if "input_ids" not in named:
        raise TypeError("tokenized Centaur prompt is missing input_ids")
    return named


def move_model_inputs_to_device(model_inputs: dict[str, Any], device: str) -> dict[str, Any]:
    return {key: value.to(device) if hasattr(value, "to") else value for key, value in model_inputs.items()}


def cuda_is_available() -> bool:
    try:
        import torch  # type: ignore[import-not-found]

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def collect_gpu_metadata() -> dict[str, Any]:
    try:
        import torch  # type: ignore[import-not-found]

        count = torch.cuda.device_count()
        return {
            "gpu_count": count,
            "gpu_names": [torch.cuda.get_device_name(index) for index in range(count)],
        }
    except Exception:
        return {"gpu_count": 0, "gpu_names": []}


def is_cuda_oom(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "cuda out of memory" in message or ("outofmemoryerror" in type(exc).__name__.lower() and "cuda" in message)


def is_host_oom(exc: BaseException) -> bool:
    message = str(exc).lower()
    if is_cuda_oom(exc):
        return False
    return any(marker in message for marker in ("cannot allocate memory", "std::bad_alloc", "defaultcpuallocator", "out of memory", "killed"))


def safe_traceback_tail(exc: BaseException, max_lines: int = 6) -> list[str]:
    lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
    return [sanitize_exception_message(line.rstrip()) for line in lines[-max_lines:]]


def sanitize_exception_message(message: str, limit: int = 1000) -> str:
    cleaned = message.replace("\r", "\\r").replace("\n", "\\n")
    cleaned = re.sub(r"(?i)(api[_-]?key|token|authorization|bearer)\s*[:=]\s*\S+", r"\1=<redacted>", cleaned)
    cleaned = re.sub(r"sk-[A-Za-z0-9_\-]{8,}", "sk-<redacted>", cleaned)
    return cleaned[:limit]


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


def repo_relative_output_path(repo_root: Path, output_dir: Path) -> str:
    output_path = Path(output_dir)
    if output_path.is_absolute():
        try:
            output_path = output_path.resolve().relative_to(repo_root.resolve())
        except ValueError:
            return output_path.as_posix()
    return output_path.as_posix()


def truncate_text(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value[:limit]


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
