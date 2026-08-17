from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.inference.phase6g2 import (  # noqa: E402
    MODEL_KEYS,
    build_model_deployment_plan,
    validate_remote_artifact,
)
from llm_experiments.prompts.freeze_package import verify_prompt_package  # noqa: E402


OUTPUT_DIR = REPO_ROOT / "llm-experiments" / "outputs" / "real" / "phase6g2a"
REAL_OUTPUT_DIR = REPO_ROOT / "llm-experiments" / "outputs" / "real"
REMOTE_SCRIPTS = [
    REPO_ROOT / "llm-experiments" / "scripts" / "remote" / "verify_qmul_models.py",
    REPO_ROOT / "llm-experiments" / "scripts" / "remote" / "verify_runpod_centaur.py",
]
SCHEMAS = [
    REPO_ROOT / "llm-experiments" / "schema" / "phase6g_qmul_verification_v1.json",
    REPO_ROOT / "llm-experiments" / "schema" / "phase6g_runpod_centaur_verification_v1.json",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_four_intended_scientific_identities_selected() -> None:
    plan = load_json(OUTPUT_DIR / "phase6g2a_model_deployment_plan_v1.json")
    models = {row["model_key"]: row for row in plan["models"]}

    assert list(models) == MODEL_KEYS
    assert models["gpt"]["scientific_model_name"] == "GPT-5.5"
    assert models["claude_sonnet"]["scientific_model_name"] == "Claude Sonnet 5"
    assert models["llama_3_1_70b_instruct"]["scientific_model_name"] == "Llama 3.1 70B Instruct"
    assert models["llama_3_1_70b_instruct"]["preferred_canonical_checkpoint"] == "meta-llama/Llama-3.1-70B-Instruct"
    assert models["centaur"]["scientific_model_name"] == "Centaur"
    assert models["centaur"]["expected_source_family"] == "Llama-3.1-based Centaur 70B"


def test_exact_deployment_identities_remain_unverified_locally() -> None:
    plan = build_model_deployment_plan()
    for model in plan["models"]:
        assert model["scientific_model_identity_known"] is True
        assert model["exact_served_id_verified"] is False
        assert model["revision_verified"] is False
        assert model["quantisation_verified"] is False
        assert model["serving_framework_verified"] is False
        assert model["backend_contract_verified"] is False


def test_remote_scripts_and_schemas_exist_and_are_portable() -> None:
    for path in REMOTE_SCRIPTS + SCHEMAS:
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "C:\\Users" not in text
        assert "\\Users\\" not in text
    for script in REMOTE_SCRIPTS:
        text = script.read_text(encoding="utf-8")
        assert "participant data" in text.lower()
        assert "final_prompt_data_objects" not in text
        assert "study prompt" in text.lower()


def test_remote_schemas_are_machine_readable_and_expected() -> None:
    qmul, runpod = [load_json(path) for path in SCHEMAS]
    assert qmul["schema_version"] == "phase6g_qmul_verification_v1"
    assert qmul["environment"] == "QMUL"
    assert set(qmul["required_model_keys"]) == {"gpt", "claude_sonnet", "llama_3_1_70b_instruct"}
    assert runpod["schema_version"] == "phase6g_runpod_centaur_verification_v1"
    assert runpod["environment"] == "RunPod"
    assert runpod["required_model_key"] == "centaur"


def test_import_validator_rejects_malformed_and_secret_artifacts(tmp_path: Path) -> None:
    malformed = tmp_path / "bad.json"
    malformed.write_text(json.dumps({"schema_version": "wrong", "api_key": "abc123"}), encoding="utf-8")

    result = validate_remote_artifact(malformed, "qmul")
    assert result["valid"] is False
    assert any("schema_version" in error for error in result["errors"])
    assert any("credentials" in error for error in result["errors"])


def test_import_validator_accepts_controlled_valid_fixtures(tmp_path: Path) -> None:
    qmul = tmp_path / "qmul.json"
    runpod = tmp_path / "runpod.json"
    qmul.write_text(json.dumps(valid_qmul_fixture()), encoding="utf-8")
    runpod.write_text(json.dumps(valid_runpod_fixture()), encoding="utf-8")

    assert validate_remote_artifact(qmul, "qmul")["valid"] is True
    assert validate_remote_artifact(runpod, "runpod")["valid"] is True


def test_local_readiness_gates_keep_production_blocked() -> None:
    readiness = load_json(REAL_OUTPUT_DIR / "phase6g2a_local_preparation_readiness.json")

    assert readiness["local_preparation_ready"] is True
    assert readiness["SCIENTIFIC_MODEL_IDENTITIES_SELECTED"] is True
    assert readiness["EXACT_DEPLOYMENT_IDENTITIES_VERIFIED"] is False
    assert readiness["QMUL_BACKENDS_VERIFIED"] is False
    assert readiness["RUNPOD_CENTAUR_VERIFIED"] is False
    assert readiness["PRIMARY_INFERENCE_CONFIG_FROZEN"] is False
    assert readiness["PRODUCTION_INFERENCE_READY"] is False
    assert readiness["remote_scripts_ready"] is True
    assert readiness["import_validator_ready"] is True


def test_phase6g1_readiness_and_phase6d_prompt_package_unchanged() -> None:
    phase6g1 = load_json(REPO_ROOT / "llm-experiments" / "outputs" / "real" / "phase6b" / "production_readiness_gate.json")
    readiness = load_json(REAL_OUTPUT_DIR / "phase6g2a_local_preparation_readiness.json")

    assert phase6g1["REAL_PHASE6B_READY"] is True
    assert readiness["phase6g1_real_phase6b_ready"] is True
    assert verify_prompt_package(REPO_ROOT)["PHASE6D_PROMPT_PACKAGE_FROZEN"] is True


def test_planning_manifest_count_and_non_executable_status() -> None:
    manifest = load_json(OUTPUT_DIR / "phase6g2a_planning_request_manifest.json")

    assert manifest["prompt_source_object_count"] == 396
    assert manifest["model_count"] == 4
    assert manifest["expected_primary_request_count"] == 1584
    assert manifest["status"] == "awaiting_remote_verification"
    assert manifest["contains_rendered_prompts"] is False
    assert manifest["contains_llm_requests"] is False
    assert manifest["contains_llm_predictions"] is False


def test_new_artifacts_have_no_user_specific_absolute_paths_or_credentials() -> None:
    paths = [
        OUTPUT_DIR / "phase6g2a_model_deployment_plan_v1.json",
        OUTPUT_DIR / "phase6g2a_planning_request_manifest.json",
        OUTPUT_DIR / "phase6g2a_local_preparation_readiness.json",
        OUTPUT_DIR / "phase6g2a_local_preparation_report.md",
        REAL_OUTPUT_DIR / "phase6g2a_local_preparation_readiness.json",
        REAL_OUTPUT_DIR / "phase6g2a_local_preparation_report.md",
    ]
    forbidden = ["C:\\Users", "/home/", "bearer ", "sk-", "api_key", "token_value", "password"]
    for path in paths:
        text = path.read_text(encoding="utf-8").lower()
        assert all(token.lower() not in text for token in forbidden)


def valid_qmul_fixture() -> dict:
    records = []
    names = {
        "gpt": "GPT-5.5",
        "claude_sonnet": "Claude Sonnet 5",
        "llama_3_1_70b_instruct": "Llama 3.1 70B Instruct",
    }
    for key, name in names.items():
        records.append(
            {
                "model_key": key,
                "scientific_model_name": name,
                "exact_served_id": f"served::{key}",
                "response_extraction_contract": "choices[0].message.content",
                "health_check": {"healthy": True},
            }
        )
    return {
        "schema_version": "phase6g_qmul_verification_v1",
        "environment": "QMUL",
        "model_records": records,
        "overall_qmul_backend_verified": True,
    }


def valid_runpod_fixture() -> dict:
    return {
        "schema_version": "phase6g_runpod_centaur_verification_v1",
        "environment": "RunPod",
        "model_record": {
            "model_key": "centaur",
            "deployed_model_source": "marcelbinz/Llama-3.1-Centaur-70B",
            "deployment_form": "merged",
            "exact_served_id": "served::centaur",
            "response_extraction_contract": "text",
            "centaur_choice_convention_audit": {
                "recommendation_exists": True,
                "technically_required": "unknown",
                "evidence_source_note": "controlled fixture",
            },
        },
        "overall_runpod_centaur_verified": True,
    }
