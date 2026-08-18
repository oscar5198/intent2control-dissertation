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


def test_runpod_artifact_has_verified_live_metadata_and_production_probe() -> None:
    artifact = load_json(ARTIFACT)
    validation = validate_remote_artifact(ARTIFACT, "runpod")

    assert validation["valid"] is True
    assert validation["backend_verified"] is True
    assert validation["execution_architectures_verified"] is True
    assert validation["production_config_verified"] is True
    assert artifact["RUNPOD_CENTAUR_EXECUTION_ARCHITECTURE_VERIFIED"] is True
    assert artifact["RUNPOD_CENTAUR_PRODUCTION_CONFIG_VERIFIED"] is True
    assert artifact["overall_runpod_centaur_verified"] is True


def test_centaur_identity_runtime_and_context_match_live_evidence() -> None:
    record = load_json(ARTIFACT)["model_record"]

    assert record["model_key"] == "centaur"
    assert record["deployed_model_source"] == "marcelbinz/Llama-3.1-Centaur-70B-adapter"
    assert record["exact_served_id"] == "marcelbinz/Llama-3.1-Centaur-70B-adapter"
    assert record["revision"] == "159600db8be99dc183c289923148dfd96cbd8e07"
    assert record["base_model"] == "unsloth/Meta-Llama-3.1-70B-bnb-4bit"
    assert record["base_revision"] == "a009b8db2439814febe725486a5ed388f12a8744"
    assert record["deployment_form"] == "adapter"
    assert record["runtime_versions"]["torch"] == "2.11.0+cu129"
    assert record["runtime_versions"]["transformers"] == "5.5.0"
    assert record["gpu"]["gpu_names"] == ["NVIDIA A100 80GB PCIe"]
    assert record["tokenizer_chat_template"] == "absent"
    assert record["tokenizer"]["model_max_length"] == 131072
    assert record["context_limit"] == 32768
    assert record["underlying_tokenizer_limit"] == 131072
    assert record["health_check"]["status"] == "succeeded"
    assert record["trivial_generation_probe"]["status"] == "succeeded"
    assert load_json(ARTIFACT)["unresolved_items"] == []


def test_centaur_generation_policy_and_common_output_contract_are_prepared() -> None:
    record = load_json(ARTIFACT)["model_record"]

    assert record["generation_mode"]["primary_generations_per_request"] == 1
    assert record["generation_mode"]["do_sample"] is False
    assert record["generation_mode"]["max_new_tokens"] == 256
    assert record["structured_output_mechanism"] == "ordinary_text_generation_local_validation_preference_prediction_response_v1_one_formatting_repair"
    assert record["message_serialization"] == "deterministic_concatenation_of_frozen_phase6d_system_and_user_content_no_semantic_wording_changes"
    assert record["centaur_choice_convention_audit"]["recommendation_exists"] is True
    assert record["centaur_choice_convention_audit"]["technically_required"] is False
    assert record["centaur_choice_convention_audit"]["decision_for_primary_experiment"] == "retain_common_frozen_phase6d_prompt_for_cross_model_equivalence"


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
    assert "adapter_config.json" in text
    assert "FastLanguageModel.from_pretrained" in text
    assert "local_files_only=args.local_files_only" in text
    assert "symlinks=False" in text
    assert_no_secrets(load_json(ARTIFACT))
    assert verify_prompt_package(REPO_ROOT)["PHASE6D_PROMPT_PACKAGE_FROZEN"] is True
