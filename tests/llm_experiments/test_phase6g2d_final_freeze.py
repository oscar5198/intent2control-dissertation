from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.inference.phase6g2 import validate_remote_artifact  # noqa: E402
from llm_experiments.inference.registry import assert_no_secrets  # noqa: E402
from llm_experiments.prompts.freeze_package import verify_prompt_package  # noqa: E402


OUT = REPO_ROOT / "llm-experiments" / "outputs" / "real" / "phase6g2d"
MODEL_REGISTRY = OUT / "phase6g2d_final_model_registry.json"
BACKEND_REGISTRY = OUT / "phase6g2d_final_backend_registry.json"
INFERENCE_CONFIG = OUT / "phase6g2d_final_inference_config.json"
CAPABILITY_MATRIX = OUT / "phase6g2d_final_capability_matrix.json"
READINESS = OUT / "phase6g2d_final_readiness.json"
DRY_RUN_MANIFEST = OUT / "phase6g2d_final_production_dry_run_manifest.json"
QMUL_ARTIFACT = REPO_ROOT / "llm-experiments" / "outputs" / "real" / "phase6g2_remote" / "phase6g2b_qmul_model_verification.json"
RUNPOD_ARTIFACT = REPO_ROOT / "llm-experiments" / "outputs" / "real" / "phase6g2_remote" / "phase6g2c_runpod_centaur_verification.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_phase6g2d_remote_artifacts_validate_as_verified() -> None:
    qmul = validate_remote_artifact(QMUL_ARTIFACT, "qmul")
    runpod = validate_remote_artifact(RUNPOD_ARTIFACT, "runpod")

    assert qmul["valid"] is True
    assert qmul["backend_verified"] is True
    assert qmul["execution_architectures_verified"] is True
    assert qmul["production_config_verified"] is True
    assert runpod["valid"] is True
    assert runpod["backend_verified"] is True
    assert runpod["execution_architectures_verified"] is True
    assert runpod["production_config_verified"] is True


def test_final_model_registry_reconciles_exact_four_identities() -> None:
    models = {row["model_key"]: row for row in load_json(MODEL_REGISTRY)["models"]}

    assert list(models) == ["gpt", "claude_sonnet", "llama_3_1_70b_instruct", "centaur"]
    assert models["gpt"]["exact_model_id"] == "gpt-5.5"
    assert models["gpt"]["revision"] == "gpt-5.5-2026-04-23"
    assert models["claude_sonnet"]["exact_model_id"] == "claude-sonnet-5"
    assert models["llama_3_1_70b_instruct"]["exact_model_id"] == "meta-llama/Llama-3.1-70B-Instruct"
    assert models["llama_3_1_70b_instruct"]["revision"] == "1605565b47bb9346c5515c34102e054115b4f98b"
    assert models["centaur"]["adapter_repository"] == "marcelbinz/Llama-3.1-Centaur-70B-adapter"
    assert models["centaur"]["adapter_revision"] == "159600db8be99dc183c289923148dfd96cbd8e07"
    assert models["centaur"]["base_model"] == "unsloth/Meta-Llama-3.1-70B-bnb-4bit"
    assert models["centaur"]["base_revision"] == "a009b8db2439814febe725486a5ed388f12a8744"
    assert models["centaur"]["context_limit_tokens"] == 32768
    assert models["centaur"]["underlying_tokenizer_limit"] == 131072


def test_final_backend_mapping_and_decoding_policy_are_frozen() -> None:
    backends = {row["backend_key"]: row for row in load_json(BACKEND_REGISTRY)["backends"]}
    config = load_json(INFERENCE_CONFIG)
    capabilities = {row["model_key"]: row for row in load_json(CAPABILITY_MATRIX)["models"]}

    assert backends["qmul_openai_provider_api_verified"]["execution_environment"] == "QMUL"
    assert backends["qmul_anthropic_provider_api_verified"]["execution_environment"] == "QMUL"
    assert backends["qmul_llama_transformers_local_verified"]["execution_environment"] == "QMUL"
    assert backends["runpod_centaur_adapter_verified"]["execution_environment"] == "RunPod"
    assert config["decoding_policy"] == {
        "gpt": "provider_native_temperature_omitted",
        "claude_sonnet": "provider_native_temperature_omitted",
        "llama_3_1_70b_instruct": "greedy_do_sample_false",
        "centaur": "greedy_do_sample_false",
    }
    assert capabilities["gpt"]["output_limit_tokens"] == 256
    assert capabilities["claude_sonnet"]["output_limit_tokens"] == 256
    assert capabilities["llama_3_1_70b_instruct"]["do_sample"] is False
    assert capabilities["centaur"]["do_sample"] is False
    assert capabilities["centaur"]["max_new_tokens"] == 256


def test_final_manifest_counts_and_ground_truth_separation() -> None:
    manifest = load_json(DRY_RUN_MANIFEST)

    assert manifest["prompt_condition_object_count"] == 396
    assert manifest["model_count"] == 4
    assert manifest["expected_primary_request_count"] == 1584
    assert manifest["planned_request_count"] == 1584
    assert manifest["contains_rendered_prompt_text"] is False
    assert manifest["contains_llm_predictions"] is False
    assert manifest["contains_hidden_ground_truth"] is False
    assert manifest["hidden_ground_truth_loaded"] is False
    assert "final_trial_ground_truth" not in json.dumps(manifest).lower()
    assert "final_candidate_ground_truth" not in json.dumps(manifest).lower()
    assert "Previous listening evidence from this participant" not in json.dumps(manifest)


def test_final_readiness_gates_are_all_true_from_evidence() -> None:
    readiness = load_json(READINESS)

    assert readiness["PHASE6D_PROMPT_PACKAGE_FROZEN"] is True
    assert readiness["REAL_PHASE6B_READY"] is True
    assert readiness["MODEL_IDENTITIES_FROZEN"] is True
    assert readiness["EXACT_DEPLOYMENT_IDENTITIES_VERIFIED"] is True
    assert readiness["INFERENCE_BACKENDS_VERIFIED"] is True
    assert readiness["PRIMARY_INFERENCE_CONFIG_FROZEN"] is True
    assert readiness["PRODUCTION_INFERENCE_READY"] is True
    assert readiness["PHASE6G2_COMPLETE"] is True
    assert readiness["PHASE6G3_CAN_BEGIN_IMMEDIATELY"] is True
    assert verify_prompt_package(REPO_ROOT)["PHASE6D_PROMPT_PACKAGE_FROZEN"] is True


def test_final_artifacts_have_no_secrets() -> None:
    for path in [MODEL_REGISTRY, BACKEND_REGISTRY, INFERENCE_CONFIG, CAPABILITY_MATRIX, READINESS, DRY_RUN_MANIFEST]:
        assert_no_secrets(load_json(path))
