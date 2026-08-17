import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.inference.configuration import (  # noqa: E402
    PLANNED_MODEL_KEYS,
    PRIMARY_INFERENCE_CONFIG_VERSION,
    UNVERIFIED,
    build_configured_request_matrix,
    build_context_compatibility_audit,
    production_preflight,
    validate_primary_configuration,
)
from llm_experiments.inference.registry import assert_no_secrets  # noqa: E402
from llm_experiments.inference.runner import build_execution_manifest  # noqa: E402
from llm_experiments.prompts.freeze_package import verify_prompt_package  # noqa: E402
from llm_experiments.prompts.prompt_spec import load_jsonl  # noqa: E402


MODEL_REGISTRY = REPO_ROOT / "llm-experiments" / "config" / "phase6e_model_registry_v1.json"
BACKEND_REGISTRY = REPO_ROOT / "llm-experiments" / "config" / "phase6e_backend_registry_v1.json"
PRIMARY_CONFIG = REPO_ROOT / "llm-experiments" / "config" / "phase6e_primary_inference_config_v1.json"
CAPABILITY_MATRIX = REPO_ROOT / "llm-experiments" / "config" / "phase6e_capability_matrix_v1.json"
RENDERED_PROMPTS = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6d2_rendered_prompts" / "rendered_prompts.jsonl"


def test_four_scientific_model_keys_retained():
    assert [row["model_key"] for row in model_registry()["models"]] == PLANNED_MODEL_KEYS


def test_exact_model_identity_fields_required_and_unverified():
    for model in model_registry()["models"]:
        assert "exact_model_id" in model
        assert "checkpoint_or_revision" in model
        assert model["exact_model_id"] == UNVERIFIED
        assert model["checkpoint_or_revision"] == UNVERIFIED
        assert model["identity_verification_status"] == "unverified"


def test_placeholder_ids_prevent_freeze_gates():
    validation = validate_primary_configuration(REPO_ROOT)
    assert validation["freeze_gates"]["MODEL_IDENTITIES_FROZEN"] is False
    assert validation["freeze_gates"]["PRIMARY_INFERENCE_CONFIG_FROZEN"] is False
    assert any("identity remains unverified" in warning for warning in validation["warnings"])


def test_centaur_maps_to_runpod_and_qmul_models_map_to_qmul():
    models = {row["model_key"]: row for row in model_registry()["models"]}
    backends = {row["backend_key"]: row for row in backend_registry()["backends"]}
    assert backends[models["centaur"]["backend_key"]]["execution_environment"] == "RunPod"
    for key in ["gpt", "claude_sonnet", "llama_3_1_70b_instruct"]:
        assert backends[models[key]["backend_key"]]["execution_environment"] == "QMUL"


def test_prompt_package_and_response_schema_versions_frozen():
    config = primary_config()
    assert config["config_version"] == PRIMARY_INFERENCE_CONFIG_VERSION
    assert config["prompt_package_version_required"] == "phase6d_prompt_package_v1"
    assert config["response_schema_version"] == "preference_prediction_response_v1"


def test_one_generation_reasoning_and_few_shot_policies():
    settings = primary_config()["shared_scientific_settings"]
    assert settings["primary_generations_per_request"] == 1
    assert settings["best_of_n"] == 1
    assert settings["self_consistency_voting"] is False
    assert settings["chain_of_thought_requested"] is False
    assert settings["few_shot_examples"] == 0


def test_temperature_top_p_seed_and_output_policies_valid():
    settings = primary_config()["shared_scientific_settings"]
    assert settings["canonical_temperature_policy"]["preferred_temperature"] == 0
    assert settings["canonical_temperature_policy"]["chosen_for_quality"] is False
    assert settings["top_p_policy"]["canonical_policy"] == "backend_default_with_temperature_zero"
    assert settings["top_p_policy"]["explicit_value_if_required"] == 1
    assert settings["seed_policy"]["project_level_seed"] == 20260814
    assert settings["max_output_tokens"] == 256


def test_seed_support_recorded_per_model_and_capabilities_explicit():
    for row in capability_matrix()["models"]:
        assert row["seed_support"] == UNVERIFIED
        assert row["primary_seed"] == 20260814
        assert row["structured_output_mechanism"] == UNVERIFIED
        assert row["system_role_support"] == UNVERIFIED
        assert row["healthcheck_available"] == UNVERIFIED


def test_context_compatibility_calculation_passes_with_verified_numbers():
    prompts = load_jsonl(RENDERED_PROMPTS)
    matrix = {
        "models": [
            {
                "model_key": "toy",
                "maximum_synthetic_prompt_tokens": 2000,
                "context_limit_tokens": 4096,
            }
        ]
    }
    audit = build_context_compatibility_audit(prompts, matrix, max_output_tokens=256)
    assert audit["models"][0]["remaining_token_margin"] == 1840
    assert audit["models"][0]["compatibility_status"] == "PASS"


def test_context_compatibility_unverified_when_tokenizers_unavailable():
    validation = validate_primary_configuration(REPO_ROOT)
    for row in validation["context_compatibility_audit"]["models"]:
        assert row["maximum_synthetic_prompt_tokens"] == UNVERIFIED
        assert row["context_limit_tokens"] == UNVERIFIED
        assert row["compatibility_status"] == UNVERIFIED


def test_z_si_and_prompt_changes_cannot_enter_model_config():
    text = MODEL_REGISTRY.read_text(encoding="utf-8") + BACKEND_REGISTRY.read_text(encoding="utf-8") + PRIMARY_CONFIG.read_text(encoding="utf-8")
    assert "z_SI" not in text
    assert "system_instruction" not in text
    assert "user_message" not in text
    assert "Previous listening evidence from this participant" not in text


def test_structured_output_and_system_message_handling_recorded():
    settings = primary_config()["shared_scientific_settings"]
    assert settings["structured_output_policy"].startswith("Every output is validated locally")
    assert "native system role" in settings["system_message_policy"]


def test_secrets_absent_and_environment_variable_references_supported():
    for payload in [model_registry(), backend_registry(), primary_config(), capability_matrix()]:
        assert_no_secrets(payload)
    backend_text = BACKEND_REGISTRY.read_text(encoding="utf-8")
    assert "QMUL_LLM_ENDPOINT_URL" in backend_text
    assert "RUNPOD_CENTAUR_ENDPOINT_URL" in backend_text
    assert "RUNPOD_API_TOKEN" in backend_text
    assert "C:\\Users\\oscar" not in backend_text


def test_synthetic_88_request_matrix_resolves_phase6e2_config(tmp_path):
    matrix = build_configured_request_matrix(REPO_ROOT, output_dir=tmp_path)
    assert matrix["config_version"] == PRIMARY_INFERENCE_CONFIG_VERSION
    assert matrix["rendered_prompts_read"] == 22
    assert matrix["selected_model_count"] == 4
    assert matrix["expected_request_count"] == 88
    assert matrix["requests_created"] == 88
    assert matrix["model_condition_coverage"]["complete"] is True
    assert {row["exact_model_id"] for row in matrix["requests"]} == {UNVERIFIED}


def test_messages_identical_across_models_for_same_rendered_prompt():
    matrix = build_configured_request_matrix(REPO_ROOT)
    first_prompt_id = matrix["requests"][0]["rendered_prompt_id"]
    rows = [row for row in matrix["requests"] if row["rendered_prompt_id"] == first_prompt_id]
    assert len(rows) == 4
    assert all(row["messages"] == rows[0]["messages"] for row in rows)
    assert {row["model_key"] for row in rows} == set(PLANNED_MODEL_KEYS)


def test_incompatible_unfrozen_config_blocks_production_preflight():
    result = production_preflight(REPO_ROOT)
    assert result["production_inference_allowed"] is False
    assert result["freeze_gates"]["MODEL_IDENTITIES_FROZEN"] is False
    assert result["freeze_gates"]["INFERENCE_BACKENDS_VERIFIED"] is False
    assert result["freeze_gates"]["PRIMARY_INFERENCE_CONFIG_FROZEN"] is False


def test_runner_blocks_real_backend_execution_when_phase6e2_gates_false():
    try:
        build_execution_manifest(REPO_ROOT, allow_real_backends=True)
    except RuntimeError as exc:
        assert "production preflight failed" in str(exc)
    else:
        raise AssertionError("Expected production preflight to block real inference.")


def test_phase6d_package_verification_still_passes():
    assert verify_prompt_package(REPO_ROOT)["PHASE6D_PROMPT_PACKAGE_FROZEN"] is True


def model_registry():
    return json.loads(MODEL_REGISTRY.read_text(encoding="utf-8"))


def backend_registry():
    return json.loads(BACKEND_REGISTRY.read_text(encoding="utf-8"))


def primary_config():
    return json.loads(PRIMARY_CONFIG.read_text(encoding="utf-8"))


def capability_matrix():
    return json.loads(CAPABILITY_MATRIX.read_text(encoding="utf-8"))
