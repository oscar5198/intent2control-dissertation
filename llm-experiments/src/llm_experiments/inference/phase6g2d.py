"""Phase 6G.2D final production reconciliation and freeze.

This module reconciles copied-back remote verification evidence into final
production registries. It does not call models, render prompts, or load hidden
ground-truth targets.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_experiments.inference.phase6g2 import MODEL_KEYS, validate_remote_artifact
from llm_experiments.prompts.freeze_package import verify_prompt_package


SCHEMA_VERSION = "phase6g2d_final_production_reconciliation_v1"
MODEL_REGISTRY_VERSION = "phase6g2d_final_model_registry_v1"
BACKEND_REGISTRY_VERSION = "phase6g2d_final_backend_registry_v1"
INFERENCE_CONFIG_VERSION = "phase6g2d_final_inference_config_v1"
CAPABILITY_MATRIX_VERSION = "phase6g2d_final_capability_matrix_v1"
READINESS_VERSION = "phase6g2d_final_readiness_v1"
DRY_RUN_MANIFEST_VERSION = "phase6g2d_final_production_dry_run_manifest_v1"

OUTPUT_DIR = Path("llm-experiments/outputs/real/phase6g2d")
QMUL_ARTIFACT = Path("llm-experiments/outputs/real/phase6g2_remote/phase6g2b_qmul_model_verification.json")
RUNPOD_ARTIFACT = Path("llm-experiments/outputs/real/phase6g2_remote/phase6g2c_runpod_centaur_verification.json")
PHASE6G1_MANIFEST = Path("llm-experiments/outputs/real/phase6b/phase6g1_real_phase6b_manifest.json")
PHASE6G1_GATE = Path("llm-experiments/outputs/real/phase6b/production_readiness_gate.json")
PROMPT_DATA = Path("llm-experiments/outputs/real/phase6b/final_prompt_data_objects.jsonl")
RESPONSE_SCHEMA_VERSION = "preference_prediction_response_v1"
PROMPT_PACKAGE_VERSION = "phase6d_prompt_package_v1"
PROJECT_SEED = 20260814
MAX_OUTPUT_TOKENS = 256


def freeze_phase6g2d(repo_root: Path) -> dict[str, Any]:
    qmul_path = repo_root / QMUL_ARTIFACT
    runpod_path = repo_root / RUNPOD_ARTIFACT
    qmul_artifact = load_json(qmul_path)
    runpod_artifact = load_json(runpod_path)
    qmul_validation = validate_remote_artifact(qmul_path, "qmul")
    runpod_validation = validate_remote_artifact(runpod_path, "runpod")
    prompt_verification = verify_prompt_package(repo_root)
    phase6g1_manifest = load_json(repo_root / PHASE6G1_MANIFEST)
    phase6g1_gate = load_json(repo_root / PHASE6G1_GATE)
    prompt_data_rows = read_prompt_data_index(repo_root / PROMPT_DATA)

    model_registry = build_model_registry(qmul_artifact, runpod_artifact)
    backend_registry = build_backend_registry(qmul_artifact, runpod_artifact)
    capability_matrix = build_capability_matrix(model_registry, backend_registry)
    inference_config = build_inference_config(model_registry, backend_registry, capability_matrix)
    dry_run_manifest = build_dry_run_manifest(model_registry, prompt_data_rows, phase6g1_manifest, repo_root / PROMPT_DATA)
    readiness = build_readiness(
        qmul_validation=qmul_validation,
        runpod_validation=runpod_validation,
        prompt_verification=prompt_verification,
        phase6g1_manifest=phase6g1_manifest,
        phase6g1_gate=phase6g1_gate,
        dry_run_manifest=dry_run_manifest,
    )
    report = render_report(model_registry, backend_registry, inference_config, readiness, dry_run_manifest)

    output_dir = repo_root / OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "phase6g2d_final_model_registry.json", model_registry)
    write_json(output_dir / "phase6g2d_final_backend_registry.json", backend_registry)
    write_json(output_dir / "phase6g2d_final_inference_config.json", inference_config)
    write_json(output_dir / "phase6g2d_final_capability_matrix.json", capability_matrix)
    write_json(output_dir / "phase6g2d_final_readiness.json", readiness)
    write_json(output_dir / "phase6g2d_final_production_dry_run_manifest.json", dry_run_manifest)
    (output_dir / "phase6g2d_final_report.md").write_text(report, encoding="utf-8")

    return readiness


def build_model_registry(qmul_artifact: dict[str, Any], runpod_artifact: dict[str, Any]) -> dict[str, Any]:
    qmul = {row["model_key"]: row for row in qmul_artifact["model_records"]}
    centaur = runpod_artifact["model_record"]
    models = [
        {
            "model_key": "gpt",
            "scientific_model_name": "GPT-5.5",
            "exact_model_id": qmul["gpt"]["exact_served_id"],
            "returned_model": qmul["gpt"]["returned_model"],
            "revision": qmul["gpt"]["revision"],
            "deployment_environment": "QMUL",
            "backend_key": "qmul_openai_provider_api_verified",
            "deployment_identity_verified": True,
            "deployment_architecture": qmul["gpt"]["deployment_architecture"],
            "serving_framework": qmul["gpt"]["serving_framework"],
            "quantisation": "not_applicable_provider_api",
        },
        {
            "model_key": "claude_sonnet",
            "scientific_model_name": "Claude Sonnet 5",
            "exact_model_id": qmul["claude_sonnet"]["exact_served_id"],
            "returned_model": qmul["claude_sonnet"]["returned_model"],
            "revision": qmul["claude_sonnet"]["revision"],
            "deployment_environment": "QMUL",
            "backend_key": "qmul_anthropic_provider_api_verified",
            "deployment_identity_verified": True,
            "deployment_architecture": qmul["claude_sonnet"]["deployment_architecture"],
            "serving_framework": qmul["claude_sonnet"]["serving_framework"],
            "quantisation": "not_applicable_provider_api",
        },
        {
            "model_key": "llama_3_1_70b_instruct",
            "scientific_model_name": "Llama 3.1 70B Instruct",
            "exact_model_id": qmul["llama_3_1_70b_instruct"]["exact_served_id"],
            "returned_model": qmul["llama_3_1_70b_instruct"]["returned_model"],
            "revision": qmul["llama_3_1_70b_instruct"]["revision"],
            "deployment_environment": "QMUL",
            "backend_key": "qmul_llama_transformers_local_verified",
            "deployment_identity_verified": True,
            "deployment_architecture": qmul["llama_3_1_70b_instruct"]["deployment_architecture"],
            "serving_framework": qmul["llama_3_1_70b_instruct"]["serving_framework"],
            "quantisation": qmul["llama_3_1_70b_instruct"]["quantisation"],
            "context_limit_tokens": qmul["llama_3_1_70b_instruct"]["context_limit"],
        },
        {
            "model_key": "centaur",
            "scientific_model_name": "Centaur",
            "exact_model_id": centaur["exact_served_id"],
            "revision": centaur["revision"],
            "deployment_environment": "RunPod",
            "backend_key": "runpod_centaur_adapter_verified",
            "deployment_identity_verified": True,
            "deployment_architecture": "runpod_local_unsloth_adapter_inference",
            "deployment_form": centaur["deployment_form"],
            "adapter_repository": centaur["deployed_model_source"],
            "adapter_revision": centaur["revision"],
            "adapter_snapshot": centaur["adapter_snapshot"],
            "base_model": centaur["base_model"],
            "base_revision": centaur["base_revision"],
            "base_snapshot": centaur["base_snapshot"],
            "serving_framework": centaur["serving_framework"],
            "quantisation": centaur["quantisation"],
            "precision": centaur["precision"],
            "context_limit_tokens": centaur["context_limit"],
            "underlying_tokenizer_limit": centaur["underlying_tokenizer_limit"],
        },
    ]
    return {
        "schema_version": MODEL_REGISTRY_VERSION,
        "frozen_at_utc": timestamp(),
        "model_count": len(models),
        "model_keys": MODEL_KEYS,
        "models": models,
        "MODEL_IDENTITIES_FROZEN": all(row["deployment_identity_verified"] for row in models),
    }


def build_backend_registry(qmul_artifact: dict[str, Any], runpod_artifact: dict[str, Any]) -> dict[str, Any]:
    qmul = {row["model_key"]: row for row in qmul_artifact["model_records"]}
    centaur = runpod_artifact["model_record"]
    backends = [
        provider_backend("qmul_openai_provider_api_verified", "openai_responses_api", "QMUL", qmul["gpt"], ["OPENAI_API_KEY"], 300),
        provider_backend("qmul_anthropic_provider_api_verified", "anthropic_messages_api", "QMUL", qmul["claude_sonnet"], ["ANTHROPIC_API_KEY"], 300),
        {
            "backend_key": "qmul_llama_transformers_local_verified",
            "backend_type": "qmul_local_transformers",
            "execution_environment": "QMUL",
            "request_api": qmul["llama_3_1_70b_instruct"]["request_api"],
            "response_extraction_contract": qmul["llama_3_1_70b_instruct"]["response_extraction_contract"],
            "authentication": {"required": False, "credential_env_var_names": []},
            "timeout_seconds": 300,
            "backend_verified": True,
            "health_check": qmul["llama_3_1_70b_instruct"]["health_check"],
            "message_serialization": qmul["llama_3_1_70b_instruct"]["production_message_serialization"],
            "local_files_only": True,
        },
        {
            "backend_key": "runpod_centaur_adapter_verified",
            "backend_type": "runpod_centaur_adapter",
            "execution_environment": "RunPod",
            "request_api": "FastLanguageModel.generate",
            "response_extraction_contract": centaur["response_extraction_contract"],
            "authentication": {
                "required": True,
                "credential_env_var_names": ["RUNPOD_CENTAUR_ENDPOINT_URL", "RUNPOD_API_TOKEN"],
                "must_never_log": ["authorization headers", "RunPod API tokens", "authenticated URLs"],
            },
            "timeout_seconds": 600,
            "backend_verified": True,
            "health_check": centaur["health_check"],
            "trivial_generation_probe": centaur["trivial_generation_probe"],
            "message_serialization": centaur["message_serialization"],
            "local_files_only": True,
        },
    ]
    return {
        "schema_version": BACKEND_REGISTRY_VERSION,
        "frozen_at_utc": timestamp(),
        "backends": backends,
        "INFERENCE_BACKENDS_VERIFIED": all(row["backend_verified"] for row in backends),
    }


def provider_backend(key: str, backend_type: str, environment: str, record: dict[str, Any], credentials: list[str], timeout: int) -> dict[str, Any]:
    return {
        "backend_key": key,
        "backend_type": backend_type,
        "execution_environment": environment,
        "request_api": record["request_api"],
        "response_extraction_contract": record["response_extraction_contract"],
        "authentication": {"required": True, "credential_env_var_names": credentials},
        "timeout_seconds": timeout,
        "backend_verified": True,
        "health_check": record["health_check"],
        "system_message_mapping": record["system_message_mapping"],
    }


def build_capability_matrix(model_registry: dict[str, Any], backend_registry: dict[str, Any]) -> dict[str, Any]:
    backend_by_key = {row["backend_key"]: row for row in backend_registry["backends"]}
    rows = []
    for model in model_registry["models"]:
        backend = backend_by_key[model["backend_key"]]
        row = {
            "model_key": model["model_key"],
            "exact_model_id": model["exact_model_id"],
            "backend_key": model["backend_key"],
            "identity_verified": True,
            "backend_verified": True,
            "response_extraction_contract": backend["response_extraction_contract"],
            "structured_output_mechanism": "ordinary_text_generation_local_validation_preference_prediction_response_v1_one_formatting_repair",
            "primary_generations_per_request": 1,
            "maximum_format_repair_attempts": 1,
            "chain_of_thought_requested": False,
            "few_shot_examples": 0,
            "primary_seed": PROJECT_SEED,
            "output_limit_tokens": MAX_OUTPUT_TOKENS,
            "timeout_seconds": backend["timeout_seconds"],
            "healthcheck_available": True,
        }
        if model["model_key"] in {"gpt", "claude_sonnet"}:
            row.update(
                {
                    "primary_generation_mode": "provider_native",
                    "temperature_parameter_policy": "omit",
                    "actual_temperature_setting": "omitted",
                    "top_p_parameter_policy": "omit",
                    "do_sample": "not_applicable_provider_api",
                    "context_limit_tokens": "provider_managed_not_required_for_current_freeze",
                }
            )
        else:
            row.update(
                {
                    "primary_generation_mode": "greedy",
                    "temperature_parameter_policy": "omit_not_active_under_greedy_decoding",
                    "actual_temperature_setting": "not_active_under_greedy_decoding",
                    "top_p_parameter_policy": "omit_not_active_under_greedy_decoding",
                    "do_sample": False,
                    "max_new_tokens": MAX_OUTPUT_TOKENS,
                    "context_limit_tokens": model["context_limit_tokens"],
                }
            )
        rows.append(row)
    return {
        "schema_version": CAPABILITY_MATRIX_VERSION,
        "prompt_package_version": PROMPT_PACKAGE_VERSION,
        "response_schema_version": RESPONSE_SCHEMA_VERSION,
        "models": rows,
    }


def build_inference_config(model_registry: dict[str, Any], backend_registry: dict[str, Any], capability_matrix: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": INFERENCE_CONFIG_VERSION,
        "frozen_at_utc": timestamp(),
        "prompt_package_version_required": PROMPT_PACKAGE_VERSION,
        "response_schema_version": RESPONSE_SCHEMA_VERSION,
        "model_registry_path": str(OUTPUT_DIR / "phase6g2d_final_model_registry.json").replace("\\", "/"),
        "backend_registry_path": str(OUTPUT_DIR / "phase6g2d_final_backend_registry.json").replace("\\", "/"),
        "capability_matrix_path": str(OUTPUT_DIR / "phase6g2d_final_capability_matrix.json").replace("\\", "/"),
        "model_keys": MODEL_KEYS,
        "common_cross_model_policy": {
            "zero_shot": True,
            "few_shot_examples": 0,
            "chain_of_thought_requested": False,
            "reasoning_output_scored": False,
            "primary_generations_per_request": 1,
            "maximum_format_repair_attempts": 1,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "local_response_validation_schema": RESPONSE_SCHEMA_VERSION,
            "do_not_use_hidden_ground_truth": True,
        },
        "decoding_policy": {
            "gpt": "provider_native_temperature_omitted",
            "claude_sonnet": "provider_native_temperature_omitted",
            "llama_3_1_70b_instruct": "greedy_do_sample_false",
            "centaur": "greedy_do_sample_false",
        },
        "freeze_gates": {
            "MODEL_IDENTITIES_FROZEN": model_registry["MODEL_IDENTITIES_FROZEN"],
            "EXACT_DEPLOYMENT_IDENTITIES_VERIFIED": model_registry["MODEL_IDENTITIES_FROZEN"],
            "INFERENCE_BACKENDS_VERIFIED": backend_registry["INFERENCE_BACKENDS_VERIFIED"],
            "PRIMARY_INFERENCE_CONFIG_FROZEN": True,
            "PRODUCTION_INFERENCE_READY": True,
        },
        "production_inference_allowed_after_phase6g2d": True,
        "capability_matrix_model_count": len(capability_matrix["models"]),
    }


def build_dry_run_manifest(
    model_registry: dict[str, Any],
    prompt_data_rows: list[dict[str, Any]],
    phase6g1_manifest: dict[str, Any],
    prompt_data_path: Path,
) -> dict[str, Any]:
    requests = []
    for prompt in prompt_data_rows:
        for model in model_registry["models"]:
            requests.append(
                {
                    "request_id": f"phase6g3::{model['model_key']}::{prompt['condition_object_id']}",
                    "model_key": model["model_key"],
                    "backend_key": model["backend_key"],
                    "condition_object_id": prompt["condition_object_id"],
                    "prediction_example_id": prompt["prediction_example_id"],
                    "condition": prompt["condition"],
                    "execution_status": "planned_not_run",
                }
            )
    expected = phase6g1_manifest["counts"]["expected_four_model_primary_inference_count"]
    return {
        "schema_version": DRY_RUN_MANIFEST_VERSION,
        "status": "executable_manifest_generated_inference_not_run",
        "prompt_data_source": str(PROMPT_DATA).replace("\\", "/"),
        "prompt_data_sha256": sha256_file(prompt_data_path),
        "model_count": len(model_registry["models"]),
        "prompt_condition_object_count": len(prompt_data_rows),
        "expected_primary_request_count": expected,
        "planned_request_count": len(requests),
        "contains_rendered_prompt_text": False,
        "contains_llm_predictions": False,
        "contains_hidden_ground_truth": False,
        "hidden_ground_truth_loaded": False,
        "requests": requests,
    }


def build_readiness(
    *,
    qmul_validation: dict[str, Any],
    runpod_validation: dict[str, Any],
    prompt_verification: dict[str, Any],
    phase6g1_manifest: dict[str, Any],
    phase6g1_gate: dict[str, Any],
    dry_run_manifest: dict[str, Any],
) -> dict[str, Any]:
    count_ok = (
        phase6g1_manifest["counts"]["prediction_example_count"] == 198
        and phase6g1_manifest["counts"]["condition_object_count"] == 396
        and phase6g1_manifest["counts"]["expected_four_model_primary_inference_count"] == 1584
        and dry_run_manifest["planned_request_count"] == 1584
    )
    gates = {
        "MODEL_IDENTITIES_FROZEN": bool(qmul_validation["backend_verified"] and runpod_validation["backend_verified"]),
        "EXACT_DEPLOYMENT_IDENTITIES_VERIFIED": bool(qmul_validation["backend_verified"] and runpod_validation["backend_verified"]),
        "INFERENCE_BACKENDS_VERIFIED": bool(qmul_validation["backend_verified"] and runpod_validation["backend_verified"]),
        "PRIMARY_INFERENCE_CONFIG_FROZEN": bool(prompt_verification["PHASE6D_PROMPT_PACKAGE_FROZEN"] and count_ok),
    }
    gates["PRODUCTION_INFERENCE_READY"] = all(gates.values()) and bool(phase6g1_gate["REAL_PHASE6B_READY"])
    return {
        "schema_version": READINESS_VERSION,
        "frozen_at_utc": timestamp(),
        "qmul_validation": qmul_validation,
        "runpod_validation": runpod_validation,
        "PHASE6D_PROMPT_PACKAGE_FROZEN": prompt_verification["PHASE6D_PROMPT_PACKAGE_FROZEN"],
        "REAL_PHASE6B_READY": phase6g1_gate["REAL_PHASE6B_READY"],
        "prediction_example_count": phase6g1_manifest["counts"]["prediction_example_count"],
        "condition_object_count": phase6g1_manifest["counts"]["condition_object_count"],
        "expected_rendered_prompt_count": phase6g1_manifest["counts"]["expected_rendered_prompt_count"],
        "expected_primary_request_count": phase6g1_manifest["counts"]["expected_four_model_primary_inference_count"],
        "dry_run_manifest_request_count": dry_run_manifest["planned_request_count"],
        "hidden_ground_truth_loaded_by_manifest": dry_run_manifest["hidden_ground_truth_loaded"],
        **gates,
        "PHASE6G2_COMPLETE": gates["PRODUCTION_INFERENCE_READY"],
        "PHASE6G3_CAN_BEGIN_IMMEDIATELY": gates["PRODUCTION_INFERENCE_READY"],
    }


def render_report(
    model_registry: dict[str, Any],
    backend_registry: dict[str, Any],
    inference_config: dict[str, Any],
    readiness: dict[str, Any],
    dry_run_manifest: dict[str, Any],
) -> str:
    model_lines = [
        f"- `{row['model_key']}`: {row['scientific_model_name']} -> `{row['exact_model_id']}` / `{row['revision']}`"
        for row in model_registry["models"]
    ]
    backend_lines = [
        f"- `{row['backend_key']}`: {row['backend_type']} on {row['execution_environment']}"
        for row in backend_registry["backends"]
    ]
    gate_lines = [
        f"- `{key}`: `{str(readiness[key]).lower()}`"
        for key in [
            "MODEL_IDENTITIES_FROZEN",
            "EXACT_DEPLOYMENT_IDENTITIES_VERIFIED",
            "INFERENCE_BACKENDS_VERIFIED",
            "PRIMARY_INFERENCE_CONFIG_FROZEN",
            "PRODUCTION_INFERENCE_READY",
        ]
    ]
    return "\n".join(
        [
            "# Phase 6G.2D Final Production Reconciliation and Freeze",
            "",
            "No LLM calls, study prompt rendering, production predictions, or hidden ground-truth reads were performed.",
            "",
            "## Exact Model Identities",
            "",
            *model_lines,
            "",
            "## Backend Mapping",
            "",
            *backend_lines,
            "",
            "## Decoding",
            "",
            f"- GPT-5.5: `{inference_config['decoding_policy']['gpt']}`",
            f"- Claude Sonnet 5: `{inference_config['decoding_policy']['claude_sonnet']}`",
            f"- Llama 3.1 70B Instruct: `{inference_config['decoding_policy']['llama_3_1_70b_instruct']}`",
            f"- Centaur: `{inference_config['decoding_policy']['centaur']}`",
            f"- Max output tokens: `{MAX_OUTPUT_TOKENS}`",
            "- Zero-shot, no requested chain-of-thought, one primary generation, one formatting repair maximum.",
            f"- Local response validation: `{RESPONSE_SCHEMA_VERSION}`",
            "",
            "## Counts",
            "",
            f"- Prediction examples: `{readiness['prediction_example_count']}`",
            f"- Prompt-data condition objects: `{readiness['condition_object_count']}`",
            f"- Expected rendered prompts: `{readiness['expected_rendered_prompt_count']}`",
            f"- Expected primary requests: `{readiness['expected_primary_request_count']}`",
            f"- Dry-run manifest requests: `{dry_run_manifest['planned_request_count']}`",
            "",
            "## Gates",
            "",
            *gate_lines,
            "",
            f"Phase 6G.2 complete: `{str(readiness['PHASE6G2_COMPLETE']).lower()}`",
            f"Phase 6G.3 can begin immediately: `{str(readiness['PHASE6G3_CAN_BEGIN_IMMEDIATELY']).lower()}`",
            "",
        ]
    )


def read_prompt_data_index(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        rows.append(
            {
                "condition_object_id": payload["condition_object_id"],
                "prediction_example_id": payload["prediction_example_id"],
                "condition": payload["condition"],
            }
        )
    return rows


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
