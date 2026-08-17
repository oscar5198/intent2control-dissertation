"""Phase 6G.2A local deployment-preparation helpers.

This module creates local planning artifacts and validates future remote
verification results. It never calls a live model and never requires
participant-level ground truth.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PLAN_SCHEMA_VERSION = "phase6g2a_model_deployment_plan_v1"
QMUL_SCHEMA_VERSION = "phase6g_qmul_verification_v1"
RUNPOD_SCHEMA_VERSION = "phase6g_runpod_centaur_verification_v1"
READINESS_SCHEMA_VERSION = "phase6g2a_local_preparation_readiness_v1"
PLANNING_MANIFEST_SCHEMA_VERSION = "phase6g2a_planning_request_manifest_v1"
FINAL_REGISTRY_SCAFFOLD_VERSION = "phase6g2d_production_registry_scaffold_v1"

MODEL_KEYS = ["gpt", "claude_sonnet", "llama_3_1_70b_instruct", "centaur"]
QMUL_MODEL_KEYS = ["gpt", "claude_sonnet", "llama_3_1_70b_instruct"]
RUNPOD_MODEL_KEYS = ["centaur"]
UNVERIFIED = "UNVERIFIED"
REPO_REL_OUTPUT_DIR = Path("llm-experiments/outputs/real/phase6g2a")
REMOTE_RESULT_DIR = Path("llm-experiments/outputs/real/phase6g2_remote")
REAL_OUTPUT_DIR = Path("llm-experiments/outputs/real")
PROMPT_DATA = Path("llm-experiments/outputs/real/phase6b/final_prompt_data_objects.jsonl")
PHASE6G1_READINESS = Path("llm-experiments/outputs/real/phase6b/production_readiness_gate.json")


SCIENTIFIC_MODELS: list[dict[str, Any]] = [
    {
        "model_key": "gpt",
        "scientific_model_name": "GPT-5.5",
        "expected_deployment_environment": "QMUL",
        "intended_family_status": "known",
        "preferred_canonical_checkpoint": None,
        "expected_source_family": "GPT",
    },
    {
        "model_key": "claude_sonnet",
        "scientific_model_name": "Claude Sonnet 5",
        "expected_deployment_environment": "QMUL",
        "intended_family_status": "known",
        "preferred_canonical_checkpoint": None,
        "expected_source_family": "Claude Sonnet",
    },
    {
        "model_key": "llama_3_1_70b_instruct",
        "scientific_model_name": "Llama 3.1 70B Instruct",
        "expected_deployment_environment": "QMUL",
        "intended_family_status": "known",
        "preferred_canonical_checkpoint": "meta-llama/Llama-3.1-70B-Instruct",
        "expected_source_family": "Llama 3.1",
    },
    {
        "model_key": "centaur",
        "scientific_model_name": "Centaur",
        "expected_deployment_environment": "RunPod",
        "intended_family_status": "known",
        "preferred_canonical_checkpoint": None,
        "expected_source_family": "Llama-3.1-based Centaur 70B",
        "source_candidates": [
            "marcelbinz/Llama-3.1-Centaur-70B",
            "marcelbinz/Llama-3.1-Centaur-70B-adapter",
        ],
    },
]

COMMON_INFERENCE_POLICIES = {
    "prompt_package_version": "phase6d_prompt_package_v1",
    "response_schema_version": "preference_prediction_response_v1",
    "primary_generations_per_request": 1,
    "maximum_format_repair_attempts": 1,
    "maximum_transport_retries": 2,
    "few_shot_examples": 0,
    "chain_of_thought_requested": False,
    "project_seed": 20260814,
    "max_output_tokens": 256,
    "temperature_policy": "greedy or temperature 0 where supported; effective per-backend setting unresolved until remote verification",
}

DEPLOYMENT_FIELDS = [
    "exact_served_id",
    "revision",
    "quantisation",
    "precision",
    "serving_framework",
    "system_role_strategy",
    "schema_strategy",
    "greedy_or_temperature_setting",
    "top_p",
    "seed",
    "max_output",
    "context",
    "timeout",
    "health_check",
    "tokenizer_chat_template",
    "response_extraction_contract",
]

FORBIDDEN_SECRET_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"bearer\s+[a-z0-9._\-]+",
        r"sk-[a-z0-9]{8,}",
        r"api[_-]?key['\"]?\s*[:=]\s*['\"][^'\"]+",
        r"token[_-]?value['\"]?\s*[:=]\s*['\"][^'\"]+",
        r"password['\"]?\s*[:=]\s*['\"][^'\"]+",
    ]
]


def build_model_deployment_plan() -> dict[str, Any]:
    models = []
    for model in SCIENTIFIC_MODELS:
        record = {
            **model,
            "scientific_model_identity_known": True,
            "exact_served_id_verified": False,
            "revision_verified": False,
            "quantisation_verified": False,
            "serving_framework_verified": False,
            "backend_contract_verified": False,
            "unresolved_exact_deployment_fields": {
                field: UNVERIFIED for field in DEPLOYMENT_FIELDS
            },
            "remote_verification_requirements": [
                "exact served/model ID",
                "snapshot/version/revision",
                "quantisation or precision",
                "serving framework",
                "tokenizer/chat template",
                "system-message support",
                "structured-output support",
                "greedy/temperature/top-p/seed controls",
                "context and output limits",
                "usage/token reporting",
                "health-check and request/response contract",
            ],
            "expected_verification_artifact": (
                "phase6g2b_qmul_model_verification.json"
                if model["expected_deployment_environment"] == "QMUL"
                else "phase6g2c_runpod_centaur_verification.json"
            ),
        }
        models.append(record)
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "artifact_role": "local_preparation_only_not_final_production_registry",
        "models": models,
        "common_inference_policies": COMMON_INFERENCE_POLICIES,
        "remote_result_destination": str(REMOTE_RESULT_DIR).replace("\\", "/"),
        "production_gate_semantics": build_gate_semantics(
            qmul_artifact_present=False,
            runpod_artifact_present=False,
            qmul_verified=False,
            runpod_verified=False,
        ),
    }


def build_planning_request_manifest(repo_root: Path) -> dict[str, Any]:
    prompt_path = repo_root / PROMPT_DATA
    prompt_records = read_jsonl(prompt_path) if prompt_path.exists() else []
    source_objects = [
        {
            "condition_object_id": row["condition_object_id"],
            "prediction_example_id": row["prediction_example_id"],
            "condition": row["condition"],
            "status": "prompt_source_available_not_rendered_in_phase6g2a",
        }
        for row in prompt_records
    ]
    expected_requests = [
        {
            "model_key": model["model_key"],
            "condition_object_id": row["condition_object_id"],
            "prediction_example_id": row["prediction_example_id"],
            "condition": row["condition"],
            "execution_status": "awaiting_remote_verification",
        }
        for model in SCIENTIFIC_MODELS
        for row in source_objects
    ]
    return {
        "schema_version": PLANNING_MANIFEST_SCHEMA_VERSION,
        "status": "awaiting_remote_verification",
        "prompt_data_source": str(PROMPT_DATA).replace("\\", "/"),
        "prompt_source_object_count": len(source_objects),
        "model_count": len(SCIENTIFIC_MODELS),
        "expected_primary_request_count": len(expected_requests),
        "expected_rendered_prompt_count": len(source_objects),
        "contains_rendered_prompts": False,
        "contains_llm_requests": False,
        "contains_llm_predictions": False,
        "source_objects": source_objects,
        "planned_requests": expected_requests,
    }


def build_gate_semantics(
    *,
    qmul_artifact_present: bool,
    runpod_artifact_present: bool,
    qmul_verified: bool,
    runpod_verified: bool,
) -> dict[str, bool]:
    exact_verified = qmul_verified and runpod_verified
    return {
        "SCIENTIFIC_MODEL_IDENTITIES_SELECTED": True,
        "EXACT_DEPLOYMENT_IDENTITIES_VERIFIED": exact_verified,
        "QMUL_BACKENDS_VERIFIED": qmul_verified,
        "RUNPOD_CENTAUR_VERIFIED": runpod_verified,
        "PRIMARY_INFERENCE_CONFIG_FROZEN": False,
        "PRODUCTION_INFERENCE_READY": False,
        "qmul_verification_artifact_present": qmul_artifact_present,
        "runpod_verification_artifact_present": runpod_artifact_present,
    }


def build_readiness(repo_root: Path) -> dict[str, Any]:
    qmul_path = repo_root / REMOTE_RESULT_DIR / "phase6g2b_qmul_model_verification.json"
    runpod_path = repo_root / REMOTE_RESULT_DIR / "phase6g2c_runpod_centaur_verification.json"
    qmul_present = qmul_path.exists()
    runpod_present = runpod_path.exists()
    qmul_verified = validate_remote_artifact(qmul_path, "qmul")["valid"] if qmul_present else False
    runpod_verified = validate_remote_artifact(runpod_path, "runpod")["valid"] if runpod_present else False
    phase6g1 = load_json(repo_root / PHASE6G1_READINESS) if (repo_root / PHASE6G1_READINESS).exists() else {}
    gates = build_gate_semantics(
        qmul_artifact_present=qmul_present,
        runpod_artifact_present=runpod_present,
        qmul_verified=qmul_verified,
        runpod_verified=runpod_verified,
    )
    return {
        "schema_version": READINESS_SCHEMA_VERSION,
        "local_preparation_ready": True,
        **gates,
        "remote_scripts_ready": True,
        "import_validator_ready": True,
        "phase6g1_real_phase6b_ready": bool(phase6g1.get("REAL_PHASE6B_READY")),
        "expected_qmul_artifact": str(REMOTE_RESULT_DIR / "phase6g2b_qmul_model_verification.json").replace("\\", "/"),
        "expected_runpod_artifact": str(REMOTE_RESULT_DIR / "phase6g2c_runpod_centaur_verification.json").replace("\\", "/"),
        "next_required_action": "Run Phase 6G.2B on QMUL and Phase 6G.2C inside RunPod, then import both verification JSON artifacts locally.",
    }


def build_final_registry_scaffold(repo_root: Path) -> dict[str, Any]:
    plan = load_json(repo_root / REPO_REL_OUTPUT_DIR / "phase6g2a_model_deployment_plan_v1.json")
    qmul_path = repo_root / REMOTE_RESULT_DIR / "phase6g2b_qmul_model_verification.json"
    runpod_path = repo_root / REMOTE_RESULT_DIR / "phase6g2c_runpod_centaur_verification.json"
    qmul_validation = validate_remote_artifact(qmul_path, "qmul") if qmul_path.exists() else {"valid": False, "errors": ["QMUL artifact not present"]}
    runpod_validation = validate_remote_artifact(runpod_path, "runpod") if runpod_path.exists() else {"valid": False, "errors": ["RunPod artifact not present"]}
    return {
        "schema_version": FINAL_REGISTRY_SCAFFOLD_VERSION,
        "status": "blocked_pending_remote_verification",
        "deployment_plan_schema_version": plan["schema_version"],
        "qmul_validation": qmul_validation,
        "runpod_validation": runpod_validation,
        "can_freeze_final_production_registry": False,
        "PRODUCTION_INFERENCE_READY": False,
        "real_prompt_context_audit_hook": {
            "status": "interface_prepared_token_counts_pending_remote_tokenizers",
            "prompt_data_source": str(PROMPT_DATA).replace("\\", "/"),
            "requires_verified_fields": ["tokenizer_chat_template", "context", "max_output"],
        },
    }


def validate_remote_artifact(path: Path, artifact_type: str) -> dict[str, Any]:
    if not path.exists():
        return {"valid": False, "errors": [f"{artifact_type} artifact does not exist"], "warnings": []}
    try:
        artifact = load_json(path)
    except json.JSONDecodeError as exc:
        return {"valid": False, "errors": [f"invalid JSON: {exc}"], "warnings": []}
    errors: list[str] = []
    warnings: list[str] = []
    check_no_secrets(artifact, errors)
    if artifact_type == "qmul":
        validate_qmul_artifact(artifact, errors, warnings)
    elif artifact_type == "runpod":
        validate_runpod_artifact(artifact, errors, warnings)
    else:
        errors.append(f"unknown artifact type: {artifact_type}")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def validate_qmul_artifact(artifact: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    if artifact.get("schema_version") != QMUL_SCHEMA_VERSION:
        errors.append("QMUL schema_version mismatch")
    if artifact.get("environment") != "QMUL":
        errors.append("QMUL environment must be QMUL")
    records = {row.get("model_key"): row for row in artifact.get("model_records", [])}
    if set(records) != set(QMUL_MODEL_KEYS):
        errors.append("QMUL artifact must contain exactly the three QMUL model keys")
    for key in QMUL_MODEL_KEYS:
        record = records.get(key, {})
        require(record, "scientific_model_name", errors, f"{key} missing scientific_model_name")
        require(record, "exact_served_id", errors, f"{key} missing exact_served_id")
        require(record, "response_extraction_contract", errors, f"{key} missing response_extraction_contract")
        if not record.get("health_check", {}).get("healthy"):
            warnings.append(f"{key} health check is not reported healthy")
    if artifact.get("overall_qmul_backend_verified") is not True:
        errors.append("overall_qmul_backend_verified must be true for import acceptance")


def validate_runpod_artifact(artifact: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    if artifact.get("schema_version") != RUNPOD_SCHEMA_VERSION:
        errors.append("RunPod schema_version mismatch")
    if artifact.get("environment") != "RunPod":
        errors.append("RunPod environment must be RunPod")
    record = artifact.get("model_record", {})
    if record.get("model_key") != "centaur":
        errors.append("RunPod artifact must describe centaur")
    require(record, "deployed_model_source", errors, "centaur missing deployed_model_source")
    require(record, "exact_served_id", errors, "centaur missing exact_served_id")
    require(record, "response_extraction_contract", errors, "centaur missing response_extraction_contract")
    convention = record.get("centaur_choice_convention_audit", {})
    if "recommendation_exists" not in convention or "technically_required" not in convention:
        errors.append("centaur choice convention audit incomplete")
    if artifact.get("overall_runpod_centaur_verified") is not True:
        errors.append("overall_runpod_centaur_verified must be true for import acceptance")
    if record.get("deployment_form") == "adapter" and not record.get("base_model"):
        warnings.append("adapter deployment should record base_model")


def write_phase6g2a_outputs(repo_root: Path) -> dict[str, Any]:
    output_dir = repo_root / REPO_REL_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    plan = build_model_deployment_plan()
    planning = build_planning_request_manifest(repo_root)
    readiness = build_readiness(repo_root)
    scaffold = {
        "schema_version": FINAL_REGISTRY_SCAFFOLD_VERSION,
        "status": "blocked_pending_remote_verification",
        "deployment_plan_schema_version": plan["schema_version"],
        "can_freeze_final_production_registry": False,
        "PRODUCTION_INFERENCE_READY": False,
        "real_prompt_context_audit_hook": {
            "status": "interface_prepared_token_counts_pending_remote_tokenizers",
            "prompt_data_source": str(PROMPT_DATA).replace("\\", "/"),
            "requires_verified_fields": ["tokenizer_chat_template", "context", "max_output"],
        },
    }
    write_json(output_dir / "phase6g2a_model_deployment_plan_v1.json", plan)
    write_json(output_dir / "phase6g2a_planning_request_manifest.json", planning)
    write_json(output_dir / "phase6g2a_local_preparation_readiness.json", readiness)
    write_json(output_dir / "phase6g2d_production_registry_scaffold.json", scaffold)
    write_report(output_dir / "phase6g2a_local_preparation_report.md", plan, planning, readiness)
    write_json(repo_root / REAL_OUTPUT_DIR / "phase6g2a_local_preparation_readiness.json", readiness)
    write_report(repo_root / REAL_OUTPUT_DIR / "phase6g2a_local_preparation_report.md", plan, planning, readiness)
    return readiness


def write_report(path: Path, plan: dict[str, Any], planning: dict[str, Any], readiness: dict[str, Any]) -> None:
    model_lines = [
        f"- `{row['model_key']}`: {row['scientific_model_name']} -> {row['expected_deployment_environment']}"
        for row in plan["models"]
    ]
    lines = [
        "# Phase 6G.2A Local Production Configuration Preparation",
        "",
        "Scope: local preparation only. No QMUL or RunPod deployment was contacted, no LLM was called, no study prompt was rendered or sent, and no Phase 6D prompt artifact was modified.",
        "",
        "## Intended Models",
        "",
        *model_lines,
        "",
        "## Known Locally",
        "",
        "- Scientific model identities are selected at the intended model-name level.",
        "- Exact served IDs, revisions, quantisation, serving frameworks, tokenizers, request contracts, and health checks remain unverified.",
        "- Production inference remains blocked.",
        "",
        "## Remote Commands",
        "",
        "QMUL:",
        "",
        "```bash",
        "python llm-experiments/scripts/remote/verify_qmul_models.py --output llm-experiments/outputs/real/phase6g2_remote/phase6g2b_qmul_model_verification.json",
        "```",
        "",
        "RunPod:",
        "",
        "```bash",
        "python llm-experiments/scripts/remote/verify_runpod_centaur.py --output llm-experiments/outputs/real/phase6g2_remote/phase6g2c_runpod_centaur_verification.json",
        "```",
        "",
        "## Copy-Back Destinations",
        "",
        f"- QMUL result: `{readiness['expected_qmul_artifact']}`",
        f"- RunPod result: `{readiness['expected_runpod_artifact']}`",
        "",
        "## Local Import/Reconciliation",
        "",
        "```bash",
        "python llm-experiments/scripts/import_phase6g2_remote_verification.py --qmul llm-experiments/outputs/real/phase6g2_remote/phase6g2b_qmul_model_verification.json --runpod llm-experiments/outputs/real/phase6g2_remote/phase6g2c_runpod_centaur_verification.json --output llm-experiments/outputs/real/phase6g2a/phase6g2d_production_registry_scaffold.json",
        "```",
        "",
        "## Planning Count",
        "",
        f"- Prompt source objects: `{planning['prompt_source_object_count']}`",
        f"- Intended scientific models: `{planning['model_count']}`",
        f"- Expected primary requests after verification: `{planning['expected_primary_request_count']}`",
        "",
        "## Gates",
        "",
        f"- `SCIENTIFIC_MODEL_IDENTITIES_SELECTED`: `{str(readiness['SCIENTIFIC_MODEL_IDENTITIES_SELECTED']).lower()}`",
        f"- `EXACT_DEPLOYMENT_IDENTITIES_VERIFIED`: `{str(readiness['EXACT_DEPLOYMENT_IDENTITIES_VERIFIED']).lower()}`",
        f"- `QMUL_BACKENDS_VERIFIED`: `{str(readiness['QMUL_BACKENDS_VERIFIED']).lower()}`",
        f"- `RUNPOD_CENTAUR_VERIFIED`: `{str(readiness['RUNPOD_CENTAUR_VERIFIED']).lower()}`",
        f"- `PRODUCTION_INFERENCE_READY`: `{str(readiness['PRODUCTION_INFERENCE_READY']).lower()}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def require(record: dict[str, Any], field: str, errors: list[str], message: str) -> None:
    if record.get(field) in {"", None, UNVERIFIED}:
        errors.append(message)


def check_no_secrets(payload: Any, errors: list[str]) -> None:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    for pattern in FORBIDDEN_SECRET_PATTERNS:
        if pattern.search(text):
            errors.append("artifact appears to contain credentials or secret values")
            break
