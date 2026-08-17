from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.inference.adapters import RunPodAdapter  # noqa: E402
from llm_experiments.inference.phase6g2 import validate_remote_artifact  # noqa: E402
from llm_experiments.inference.registry import assert_no_secrets  # noqa: E402
from llm_experiments.prompts.freeze_package import verify_prompt_package  # noqa: E402


ARTIFACT = REPO_ROOT / "llm-experiments" / "outputs" / "real" / "phase6g2_remote" / "phase6g2c_runpod_centaur_verification.json"
VERIFY_SCRIPT = REPO_ROOT / "llm-experiments" / "scripts" / "remote" / "verify_runpod_centaur.py"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_pending_runpod_artifact_is_valid_but_not_verified() -> None:
    artifact = load_json(ARTIFACT)
    validation = validate_remote_artifact(ARTIFACT, "runpod")

    assert validation["valid"] is True
    assert validation["backend_verified"] is False
    assert validation["execution_architectures_verified"] is False
    assert validation["production_config_verified"] is False
    assert artifact["RUNPOD_CENTAUR_EXECUTION_ARCHITECTURE_VERIFIED"] is False
    assert artifact["RUNPOD_CENTAUR_PRODUCTION_CONFIG_VERIFIED"] is False
    assert artifact["overall_runpod_centaur_verified"] is False


def test_pending_centaur_identity_and_runtime_are_not_invented() -> None:
    record = load_json(ARTIFACT)["model_record"]

    assert record["model_key"] == "centaur"
    assert record["deployed_model_source"] == "UNVERIFIED"
    assert record["exact_served_id"] == "UNVERIFIED"
    assert record["revision"] == "UNVERIFIED"
    assert record["deployment_form"] == "UNVERIFIED"
    assert record["runtime_versions"]["torch"] == "UNVERIFIED"
    assert record["gpu"]["gpu_count"] == "UNVERIFIED"
    assert "deployed_model_source" in load_json(ARTIFACT)["unresolved_items"]


def test_centaur_generation_policy_and_common_output_contract_are_prepared() -> None:
    record = load_json(ARTIFACT)["model_record"]

    assert record["generation_mode"]["primary_generations_per_request"] == 1
    assert record["generation_mode"]["do_sample"] is False
    assert record["generation_mode"]["max_new_tokens"] == 256
    assert record["structured_output_mechanism"] == "ordinary_text_generation_local_validation_preference_prediction_response_v1_one_formatting_repair"
    assert "apply_chat_template" in record["message_serialization"]


def test_runpod_adapter_prepares_canonical_request_and_is_guarded(monkeypatch) -> None:
    monkeypatch.delenv("RUNPOD_CENTAUR_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("RUNPOD_API_TOKEN", raising=False)
    adapter = RunPodAdapter({"backend_key": "runpod_centaur_unverified", "backend_type": "runpod_http", "timeout_seconds": 600})
    request = {
        "inference_request_id": "req_test",
        "rendered_prompt_id": "prompt_test",
        "response_schema_version": "preference_prediction_response_v1",
        "messages": [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ],
    }

    prepared = adapter.prepare_request(request)
    assert prepared["generation_config"]["do_sample"] is False
    assert prepared["generation_config"]["max_new_tokens"] == 256
    assert prepared["messages"] == request["messages"]
    try:
        adapter.invoke(prepared)
    except RuntimeError as exc:
        assert "RUNPOD_CENTAUR_ENDPOINT_URL" in str(exc)
    else:
        raise AssertionError("RunPod adapter must not invoke without configured endpoint/token")


def test_runpod_verifier_does_not_reference_study_data_or_secrets() -> None:
    text = VERIFY_SCRIPT.read_text(encoding="utf-8")
    assert "final_prompt_data_objects" not in text
    assert "Previous listening evidence from this participant" not in text
    assert "HF_TOKEN" in text
    assert_no_secrets(load_json(ARTIFACT))
    assert verify_prompt_package(REPO_ROOT)["PHASE6D_PROMPT_PACKAGE_FROZEN"] is True
