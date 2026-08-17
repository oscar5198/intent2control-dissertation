"""Phase 6E.2 primary inference configuration validation."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from llm_experiments.inference.registry import assert_no_secrets
from llm_experiments.inference.requests import INFERENCE_INTERFACE_VERSION, make_inference_request
from llm_experiments.prompts.freeze_package import PHASE6D_PROMPT_PACKAGE_FROZEN_GATE, verify_prompt_package
from llm_experiments.prompts.prompt_spec import load_jsonl, write_json


PRIMARY_INFERENCE_CONFIG_VERSION = "phase6e_primary_inference_config_v1"
MODEL_REGISTRY_SCHEMA_VERSION = "phase6e_model_registry_v1"
BACKEND_REGISTRY_SCHEMA_VERSION = "phase6e_backend_registry_v1"
CAPABILITY_MATRIX_SCHEMA_VERSION = "phase6e_capability_matrix_v1"
UNVERIFIED = "UNVERIFIED"

DEFAULT_MODEL_REGISTRY_V1 = Path("llm-experiments/config/phase6e_model_registry_v1.json")
DEFAULT_BACKEND_REGISTRY_V1 = Path("llm-experiments/config/phase6e_backend_registry_v1.json")
DEFAULT_PRIMARY_CONFIG = Path("llm-experiments/config/phase6e_primary_inference_config_v1.json")
DEFAULT_CAPABILITY_MATRIX = Path("llm-experiments/config/phase6e_capability_matrix_v1.json")
DEFAULT_RENDERED_PROMPTS = Path("llm-experiments/outputs/synthetic/phase6d2_rendered_prompts/rendered_prompts.jsonl")
DEFAULT_OUTPUT_DIR = Path("llm-experiments/outputs/synthetic/phase6e2")

PLANNED_MODEL_KEYS = ["gpt", "claude_sonnet", "llama_3_1_70b_instruct", "centaur"]
QMUL_MODEL_KEYS = ["gpt", "claude_sonnet", "llama_3_1_70b_instruct"]
RUNPOD_MODEL_KEYS = ["centaur"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_primary_configuration(
    repo_root: Path,
    model_registry_path: Path = DEFAULT_MODEL_REGISTRY_V1,
    backend_registry_path: Path = DEFAULT_BACKEND_REGISTRY_V1,
    primary_config_path: Path = DEFAULT_PRIMARY_CONFIG,
    capability_matrix_path: Path = DEFAULT_CAPABILITY_MATRIX,
    rendered_prompts_path: Path = DEFAULT_RENDERED_PROMPTS,
) -> dict[str, Any]:
    model_registry = load_json(repo_root / model_registry_path)
    backend_registry = load_json(repo_root / backend_registry_path)
    primary_config = load_json(repo_root / primary_config_path)
    capability_matrix = load_json(repo_root / capability_matrix_path)
    rendered_prompts = load_jsonl(repo_root / rendered_prompts_path)
    prompt_preflight = verify_prompt_package(repo_root)
    errors: list[str] = []
    warnings: list[str] = []

    assert_no_secrets(model_registry)
    assert_no_secrets(backend_registry)
    assert_no_secrets(primary_config)
    assert_no_secrets(capability_matrix)

    if model_registry.get("schema_version") != MODEL_REGISTRY_SCHEMA_VERSION:
        errors.append("model registry schema version mismatch")
    if backend_registry.get("schema_version") != BACKEND_REGISTRY_SCHEMA_VERSION:
        errors.append("backend registry schema version mismatch")
    if primary_config.get("config_version") != PRIMARY_INFERENCE_CONFIG_VERSION:
        errors.append("primary inference config version mismatch")
    if capability_matrix.get("schema_version") != CAPABILITY_MATRIX_SCHEMA_VERSION:
        errors.append("capability matrix schema version mismatch")
    if primary_config.get("inference_interface_version") != INFERENCE_INTERFACE_VERSION:
        errors.append("inference interface version mismatch")
    if primary_config.get("prompt_package_version_required") != "phase6d_prompt_package_v1":
        errors.append("prompt package requirement mismatch")
    if primary_config.get("response_schema_version") != "preference_prediction_response_v1":
        errors.append("response schema version mismatch")

    models = {row["model_key"]: row for row in model_registry.get("models", [])}
    backends = {row["backend_key"]: row for row in backend_registry.get("backends", [])}
    if set(models) != set(PLANNED_MODEL_KEYS):
        errors.append(f"planned model keys mismatch: {sorted(models)}")
    for key in QMUL_MODEL_KEYS:
        model = models.get(key, {})
        backend = backends.get(model.get("backend_key"), {})
        if model.get("deployment_environment") != "QMUL":
            errors.append(f"{key} deployment must be QMUL")
        if backend.get("execution_environment") != "QMUL":
            errors.append(f"{key} backend execution environment must be QMUL")
    for key in RUNPOD_MODEL_KEYS:
        model = models.get(key, {})
        backend = backends.get(model.get("backend_key"), {})
        if model.get("deployment_environment") != "RunPod":
            errors.append(f"{key} deployment must be RunPod")
        if backend.get("execution_environment") != "RunPod":
            errors.append(f"{key} backend execution environment must be RunPod")

    for key, model in models.items():
        if not model.get("exact_model_id"):
            errors.append(f"{key} missing exact_model_id field")
        if model.get("scientific_model_identity_known") is not True:
            warnings.append(f"{key} scientific model identity is not selected")
        if not model.get("scientific_model_name"):
            errors.append(f"{key} missing scientific_model_name field")
        if model.get("exact_model_id") == UNVERIFIED or model.get("checkpoint_or_revision") == UNVERIFIED:
            warnings.append(f"{key} identity remains unverified")
        if model.get("identity_verification_status") != "verified":
            warnings.append(f"{key} identity verification status is not verified")

    settings = primary_config.get("shared_scientific_settings", {})
    if settings.get("primary_generations_per_request") != 1:
        errors.append("primary generation count must be one")
    if settings.get("few_shot_examples") != 0:
        errors.append("few-shot count must be zero")
    if settings.get("chain_of_thought_requested") is not False:
        errors.append("chain-of-thought must not be requested")
    if settings.get("canonical_temperature_policy", {}).get("preferred_temperature") != 0:
        errors.append("preferred temperature policy must be 0")
    top_p_policy = settings.get("top_p_policy", {})
    if top_p_policy.get("canonical_policy") not in {"backend_default_with_temperature_zero", "explicit_one_if_required"}:
        errors.append("top-p policy invalid")
    if int(settings.get("max_output_tokens", 0)) <= 0:
        errors.append("max output token budget must be positive")

    capability_rows = {row["model_key"]: row for row in capability_matrix.get("models", [])}
    if set(capability_rows) != set(PLANNED_MODEL_KEYS):
        errors.append("capability matrix model keys mismatch")
    for key, row in capability_rows.items():
        for field in [
            "system_role_support",
            "structured_output_mechanism",
            "temperature_support",
            "top_p_support",
            "seed_support",
            "context_limit_tokens",
            "tokenizer_available",
            "usage_reporting",
            "healthcheck_available",
        ]:
            if field not in row:
                errors.append(f"{key} capability missing {field}")

    context_audit = build_context_compatibility_audit(rendered_prompts, capability_matrix, settings.get("max_output_tokens", 0))
    if any(row["compatibility_status"] == "FAIL" for row in context_audit["models"]):
        errors.append("context compatibility failure")

    gates = compute_freeze_gates(model_registry, backend_registry, primary_config, capability_matrix, prompt_preflight, context_audit, errors)
    validation = {
        "schema_version": "phase6e2_primary_config_validation_v1",
        "config_version": PRIMARY_INFERENCE_CONFIG_VERSION,
        "prompt_package_preflight": prompt_preflight,
        "errors": errors,
        "warnings": warnings,
        "context_compatibility_audit": context_audit,
        "freeze_gates": gates,
        "production_preflight_passed": gates["PRIMARY_INFERENCE_CONFIG_FROZEN"],
    }
    return validation


def compute_freeze_gates(
    model_registry: dict[str, Any],
    backend_registry: dict[str, Any],
    primary_config: dict[str, Any],
    capability_matrix: dict[str, Any],
    prompt_preflight: dict[str, Any],
    context_audit: dict[str, Any],
    errors: list[str],
) -> dict[str, bool]:
    models = model_registry.get("models", [])
    backends = backend_registry.get("backends", [])
    capability_rows = capability_matrix.get("models", [])
    model_identities_frozen = all(
        row.get("identity_verification_status") == "verified"
        and row.get("exact_model_id") not in {"", UNVERIFIED, None}
        and row.get("checkpoint_or_revision") not in {"", UNVERIFIED, None}
        for row in models
    )
    scientific_model_identities_selected = all(
        row.get("scientific_model_identity_known") is True
        and row.get("scientific_model_name") not in {"", UNVERIFIED, None}
        for row in models
    )
    exact_deployment_identities_verified = all(
        row.get("exact_served_id_verified") is True
        and row.get("exact_served_id") not in {"", UNVERIFIED, None}
        and row.get("revision_verified") is True
        and row.get("revision") not in {"", UNVERIFIED, None}
        for row in models
    )
    qmul_backends_verified = all(
        row.get("backend_verification_status") == "verified"
        and row.get("request_contract_status") == "verified"
        and row.get("response_contract_status") == "verified"
        for row in backends
        if row.get("execution_environment") == "QMUL"
    )
    runpod_centaur_verified = all(
        row.get("backend_verification_status") == "verified"
        and row.get("request_contract_status") == "verified"
        and row.get("response_contract_status") == "verified"
        for row in backends
        if row.get("execution_environment") == "RunPod"
    )
    inference_backends_verified = all(
        row.get("backend_verification_status") == "verified"
        and row.get("request_contract_status") == "verified"
        and row.get("response_contract_status") == "verified"
        for row in backends
        if row.get("backend_key") != "mock"
    )
    structured_output_established = all(row.get("structured_output_mechanism") != UNVERIFIED for row in capability_rows)
    context_compatible = all(row["compatibility_status"] in {"PASS", "UNVERIFIED"} for row in context_audit["models"])
    return {
        "SCIENTIFIC_MODEL_IDENTITIES_SELECTED": scientific_model_identities_selected,
        "EXACT_DEPLOYMENT_IDENTITIES_VERIFIED": exact_deployment_identities_verified,
        "QMUL_BACKENDS_VERIFIED": qmul_backends_verified,
        "RUNPOD_CENTAUR_VERIFIED": runpod_centaur_verified,
        "MODEL_IDENTITIES_FROZEN": model_identities_frozen,
        "INFERENCE_BACKENDS_VERIFIED": inference_backends_verified,
        "PRIMARY_INFERENCE_CONFIG_FROZEN": (
            model_identities_frozen
            and inference_backends_verified
            and bool(prompt_preflight.get(PHASE6D_PROMPT_PACKAGE_FROZEN_GATE))
            and primary_config.get("config_version") == PRIMARY_INFERENCE_CONFIG_VERSION
            and structured_output_established
            and context_compatible
            and not errors
        ),
    }


def build_context_compatibility_audit(
    rendered_prompts: list[dict[str, Any]],
    capability_matrix: dict[str, Any],
    max_output_tokens: int,
) -> dict[str, Any]:
    largest_prompt = max(rendered_prompts, key=lambda row: sum(len(message["content"]) for message in row["messages"]))
    largest_characters = sum(len(message["content"]) for message in largest_prompt["messages"])
    rows = []
    for model in capability_matrix.get("models", []):
        token_count = model.get("maximum_synthetic_prompt_tokens")
        context_limit = model.get("context_limit_tokens")
        if isinstance(token_count, int) and isinstance(context_limit, int):
            remaining = context_limit - token_count - int(max_output_tokens)
            status = "PASS" if remaining > 0 else "FAIL"
        else:
            remaining = None
            status = UNVERIFIED
        rows.append(
            {
                "model_key": model["model_key"],
                "maximum_synthetic_prompt_tokens": token_count,
                "context_limit_tokens": context_limit,
                "max_output_tokens": max_output_tokens,
                "remaining_token_margin": remaining,
                "compatibility_status": status,
            }
        )
    return {
        "schema_version": "phase6e2_context_compatibility_audit_v1",
        "largest_rendered_prompt_id": largest_prompt["rendered_prompt_id"],
        "largest_rendered_prompt_characters": largest_characters,
        "models": rows,
    }


def build_configured_request_matrix(
    repo_root: Path,
    model_registry_path: Path = DEFAULT_MODEL_REGISTRY_V1,
    primary_config_path: Path = DEFAULT_PRIMARY_CONFIG,
    rendered_prompts_path: Path = DEFAULT_RENDERED_PROMPTS,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    model_registry = load_json(repo_root / model_registry_path)
    primary_config = load_json(repo_root / primary_config_path)
    rendered_prompts = load_jsonl(repo_root / rendered_prompts_path)
    models = model_registry["models"]
    rows = []
    for model in models:
        for prompt in rendered_prompts:
            request = make_inference_request(
                prompt,
                {
                    "model_key": model["model_key"],
                    "default_backend_key": model["backend_key"],
                    "inference_config_version": primary_config["config_version"],
                },
                inference_config_version=primary_config["config_version"],
                prompt_package_version=primary_config["prompt_package_version_required"],
            )
            rows.append(
                {
                    "inference_request_id": request["inference_request_id"],
                    "rendered_prompt_id": prompt["rendered_prompt_id"],
                    "prediction_example_id": prompt["prediction_example_id"],
                    "condition": prompt["condition"],
                    "model_key": model["model_key"],
                    "exact_model_id": model["exact_model_id"],
                    "checkpoint_or_revision": model["checkpoint_or_revision"],
                    "backend_key": model["backend_key"],
                    "prompt_package_version": primary_config["prompt_package_version_required"],
                    "response_schema_version": primary_config["response_schema_version"],
                    "inference_config_version": primary_config["config_version"],
                    "messages": request["messages"],
                    "execution_status": "blocked_pending_phase6e2_freeze",
                }
            )
    coverage = matrix_coverage(rows)
    payload = {
        "schema_version": "phase6e2_synthetic_request_matrix_v1",
        "config_version": primary_config["config_version"],
        "rendered_prompts_read": len(rendered_prompts),
        "selected_model_count": len(models),
        "expected_request_count": len(rendered_prompts) * len(models),
        "requests_created": len(rows),
        "model_condition_coverage": coverage,
        "requests": rows,
        "contains_ground_truth": False,
        "contains_real_model_responses": False,
    }
    output = repo_root / output_dir
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "phase6e2_synthetic_request_matrix.json", payload)
    return payload


def matrix_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_model: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        by_model[row["model_key"]].add(row["condition"])
    expected = {"non_history", "personalised_history"}
    missing = {model: sorted(expected - conditions) for model, conditions in by_model.items() if expected - conditions}
    return {
        "expected_conditions": sorted(expected),
        "conditions_by_model": {model: sorted(conditions) for model, conditions in sorted(by_model.items())},
        "missing_model_condition_combinations": missing,
        "complete": not missing,
    }


def write_phase6e2_validation_outputs(repo_root: Path, output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    validation = validate_primary_configuration(repo_root)
    matrix = build_configured_request_matrix(repo_root, output_dir=output_dir)
    output = repo_root / output_dir
    write_json(output / "phase6e2_primary_config_validation.json", validation)
    write_json(output / "phase6e2_context_compatibility_audit.json", validation["context_compatibility_audit"])
    write_json(output / "phase6e2_freeze_gates.json", validation["freeze_gates"])
    write_json(output / "phase6e2_summary.json", {"validation": validation, "request_matrix_summary": {k: v for k, v in matrix.items() if k != "requests"}})
    return validation


def production_preflight(repo_root: Path) -> dict[str, Any]:
    validation = validate_primary_configuration(repo_root)
    return {
        "schema_version": "phase6e2_production_preflight_v1",
        "config_version": PRIMARY_INFERENCE_CONFIG_VERSION,
        "phase6d_prompt_package_frozen": bool(validation["prompt_package_preflight"].get(PHASE6D_PROMPT_PACKAGE_FROZEN_GATE)),
        "freeze_gates": validation["freeze_gates"],
        "production_inference_allowed": validation["freeze_gates"]["PRIMARY_INFERENCE_CONFIG_FROZEN"],
        "blocking_errors": validation["errors"],
        "unresolved_warnings": validation["warnings"],
    }
