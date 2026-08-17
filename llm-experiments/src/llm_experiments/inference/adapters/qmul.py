"""QMUL backend adapter scaffolds for provider and local execution paths."""

from __future__ import annotations

from typing import Any

from llm_experiments.inference.base import ModelAdapter


class QMULAdapter(ModelAdapter):
    """Generic QMUL scaffold kept for unresolved legacy placeholders."""

    def invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("QMUL real inference is not enabled in Phase 6E.1.")

    def extract_raw_response(self, provider_response: dict[str, Any]) -> str | None:
        if "text" not in provider_response:
            raise ValueError("Malformed QMUL provider response missing text field.")
        return provider_response.get("text")


class OpenAIResponsesQMULAdapter(ModelAdapter):
    """Transport envelope for GPT provider API calls launched from QMUL."""

    def prepare_request(self, inference_request: dict[str, Any]) -> dict[str, Any]:
        prepared = super().prepare_request(inference_request)
        return {
            **prepared,
            "provider": "OpenAI API",
            "request_api": "OpenAI.responses.create",
            "model": "gpt-5.5",
            "input": inference_request["messages"],
            "max_output_tokens": 256,
            "temperature_policy": "greedy_or_temperature_zero_where_supported",
        }

    def invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("OpenAI provider API inference from QMUL is not enabled until Phase 6 production gates pass.")

    def extract_raw_response(self, provider_response: dict[str, Any]) -> str | None:
        if "output_text" not in provider_response:
            raise ValueError("Malformed OpenAI Responses API fixture missing output_text field.")
        return provider_response.get("output_text")


class AnthropicMessagesQMULAdapter(ModelAdapter):
    """Transport envelope for Claude provider API calls launched from QMUL."""

    def prepare_request(self, inference_request: dict[str, Any]) -> dict[str, Any]:
        prepared = super().prepare_request(inference_request)
        messages = inference_request["messages"]
        return {
            **prepared,
            "provider": "Anthropic API",
            "request_api": "Anthropic.messages.create",
            "model": "claude-sonnet-5",
            "system": messages[0]["content"],
            "messages": [messages[1]],
            "max_tokens": 256,
            "temperature_policy": "greedy_or_temperature_zero_where_supported",
        }

    def invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("Anthropic provider API inference from QMUL is not enabled until Phase 6 production gates pass.")

    def extract_raw_response(self, provider_response: dict[str, Any]) -> str | None:
        content = provider_response.get("content")
        if not isinstance(content, list) or not content or "text" not in content[0]:
            raise ValueError("Malformed Anthropic Messages API fixture missing content[0].text field.")
        return content[0].get("text")


class LocalTransformersLlamaQMULAdapter(ModelAdapter):
    """Transport envelope for local cached Llama Transformers generation."""

    def prepare_request(self, inference_request: dict[str, Any]) -> dict[str, Any]:
        prepared = super().prepare_request(inference_request)
        return {
            **prepared,
            "provider": "local Hugging Face Transformers",
            "request_api": "AutoModelForCausalLM.generate",
            "model": "meta-llama/Llama-3.1-70B-Instruct",
            "serialization_method": "tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)",
            "messages": inference_request["messages"],
            "generation_config": {
                "max_new_tokens": 256,
                "do_sample": False,
                "pad_token_id_policy": "tokenizer.eos_token_id",
            },
            "model_load_config": {
                "local_files_only": True,
                "device_map": "auto",
                "max_memory": {"0": "43GiB"},
                "low_cpu_mem_usage": True,
                "torch_dtype": "torch.bfloat16",
                "quantization": {
                    "load_in_4bit": True,
                    "bnb_4bit_quant_type": "nf4",
                    "bnb_4bit_compute_dtype": "torch.bfloat16",
                    "bnb_4bit_use_double_quant": True,
                },
            },
        }

    def invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("Local Llama Transformers inference on QMUL is not enabled until Phase 6 production gates pass.")

    def extract_raw_response(self, provider_response: dict[str, Any]) -> str | None:
        if "decoded_text" not in provider_response:
            raise ValueError("Malformed local Transformers fixture missing decoded_text field.")
        return provider_response.get("decoded_text")
