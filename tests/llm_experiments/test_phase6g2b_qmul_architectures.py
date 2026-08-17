from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.inference.adapters import (  # noqa: E402
    AnthropicMessagesQMULAdapter,
    LocalTransformersLlamaQMULAdapter,
    OpenAIResponsesQMULAdapter,
)
from llm_experiments.inference.phase6g2 import validate_remote_artifact  # noqa: E402
from llm_experiments.inference.registry import assert_no_secrets  # noqa: E402
from llm_experiments.prompts.freeze_package import verify_prompt_package  # noqa: E402


ARTIFACT = REPO_ROOT / "llm-experiments" / "outputs" / "real" / "phase6g2_remote" / "phase6g2b_qmul_model_verification.json"
MODEL_REGISTRY = REPO_ROOT / "llm-experiments" / "config" / "phase6e_model_registry_v1.json"
BACKEND_REGISTRY = REPO_ROOT / "llm-experiments" / "config" / "phase6e_backend_registry_v1.json"
CAPABILITY_MATRIX = REPO_ROOT / "llm-experiments" / "config" / "phase6e_capability_matrix_v1.json"
VERIFY_SCRIPT = REPO_ROOT / "llm-experiments" / "scripts" / "remote" / "verify_qmul_models.py"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_qmul_artifact_distinguishes_architecture_from_production_freeze() -> None:
    artifact = load_json(ARTIFACT)
    validation = validate_remote_artifact(ARTIFACT, "qmul")

    assert validation["valid"] is True
    assert validation["execution_architectures_verified"] is True
    assert validation["production_config_verified"] is False
    assert validation["backend_verified"] is False
    assert artifact["QMUL_EXECUTION_ARCHITECTURES_VERIFIED"] is True
    assert artifact["QMUL_PRODUCTION_CONFIG_VERIFIED"] is False
    assert artifact["overall_qmul_backend_verified"] is False


def test_llama_local_transformers_quantized_deployment_recorded() -> None:
    records = {row["model_key"]: row for row in load_json(ARTIFACT)["model_records"]}
    llama = records["llama_3_1_70b_instruct"]

    assert llama["exact_served_id"] == "meta-llama/Llama-3.1-70B-Instruct"
    assert llama["deployment_architecture"] == "local_huggingface_transformers_inference_from_qmul_runtime"
    assert llama["backend_provider"] == "local Hugging Face Transformers"
    assert llama["model_class"] == "AutoModelForCausalLM"
    assert llama["tokenizer_class"] == "AutoTokenizer"
    assert llama["local_files_only"] is True
    assert llama["quantisation"]["load_in_4bit"] is True
    assert llama["quantisation"]["bnb_4bit_quant_type"] == "nf4"
    assert llama["quantisation"]["bnb_4bit_use_double_quant"] is True
    assert llama["quantisation"]["bnb_4bit_compute_dtype"] == "torch.bfloat16"
    assert llama["generation_mode"]["do_sample"] is False
    assert llama["generation_mode"]["primary_mode"] == "greedy"
    assert llama["generation_mode"]["max_new_tokens"] == 256


def test_llama_unresolved_fields_remain_explicit() -> None:
    llama = {row["model_key"]: row for row in load_json(ARTIFACT)["model_records"]}["llama_3_1_70b_instruct"]

    assert llama["revision_verified"] is False
    assert llama["revision"] == "UNVERIFIED"
    assert llama["tokenizer_chat_template_identity"] == "UNVERIFIED"
    assert llama["context_limit"] == "UNVERIFIED"
    assert "apply_chat_template" in llama["production_message_serialization"]
    assert llama["structured_output_strategy"] == "ordinary_text_generation_local_validation_preference_prediction_response_v1_one_formatting_repair"


def test_gpt_and_claude_provider_architectures_remain_intact() -> None:
    records = {row["model_key"]: row for row in load_json(ARTIFACT)["model_records"]}

    assert records["gpt"]["deployment_architecture"] == "provider_api_invoked_from_qmul_runtime"
    assert records["gpt"]["backend_provider"] == "OpenAI API"
    assert records["gpt"]["request_api"] == "OpenAI.responses.create"
    assert records["gpt"]["credential_env_var"] == "OPENAI_API_KEY"
    assert records["claude_sonnet"]["deployment_architecture"] == "provider_api_invoked_from_qmul_runtime"
    assert records["claude_sonnet"]["backend_provider"] == "Anthropic API"
    assert records["claude_sonnet"]["request_api"] == "Anthropic.messages.create"
    assert records["claude_sonnet"]["credential_env_var"] == "ANTHROPIC_API_KEY"


def test_concrete_qmul_adapter_scaffolds_prepare_requests_but_do_not_invoke() -> None:
    sample = {
        "inference_request_id": "req_test",
        "rendered_prompt_id": "prompt_test",
        "response_schema_version": "preference_prediction_response_v1",
        "messages": [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ],
    }
    adapters = [
        OpenAIResponsesQMULAdapter({"backend_key": "gpt", "backend_type": "openai_responses_api"}),
        AnthropicMessagesQMULAdapter({"backend_key": "claude", "backend_type": "anthropic_messages_api"}),
        LocalTransformersLlamaQMULAdapter({"backend_key": "llama", "backend_type": "qmul_local_transformers"}),
    ]

    prepared = [adapter.prepare_request(sample) for adapter in adapters]
    assert prepared[0]["request_api"] == "OpenAI.responses.create"
    assert prepared[1]["request_api"] == "Anthropic.messages.create"
    assert prepared[2]["request_api"] == "AutoModelForCausalLM.generate"
    assert prepared[2]["generation_config"]["do_sample"] is False
    assert prepared[2]["generation_config"]["max_new_tokens"] == 256
    for adapter, request in zip(adapters, prepared, strict=True):
        try:
            adapter.invoke(request)
        except RuntimeError as exc:
            assert "not enabled" in str(exc)
        else:
            raise AssertionError("QMUL production adapter scaffold must not invoke real models in tests")


def test_no_secrets_and_no_study_prompt_execution_paths_added() -> None:
    for payload in [load_json(MODEL_REGISTRY), load_json(BACKEND_REGISTRY), load_json(CAPABILITY_MATRIX), load_json(ARTIFACT)]:
        assert_no_secrets(payload)
    script_text = VERIFY_SCRIPT.read_text(encoding="utf-8")
    assert "final_prompt_data_objects" not in script_text
    assert "Previous listening evidence from this participant" not in script_text
    assert verify_prompt_package(REPO_ROOT)["PHASE6D_PROMPT_PACKAGE_FROZEN"] is True
