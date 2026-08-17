"""QMUL backend adapter scaffolds for provider and local execution paths."""

from __future__ import annotations

import os
import time
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
            "instructions": inference_request["messages"][0]["content"],
            "input": inference_request["messages"][1]["content"],
            "max_output_tokens": 256,
            "temperature_parameter_policy": "omit_verified_unsupported",
            "top_p_parameter_policy": "omit_optional_sampling_controls",
        }

    def invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI provider API inference.")
        from openai import OpenAI  # type: ignore[import-not-found]

        client = OpenAI()
        started = time.perf_counter()
        response = client.responses.create(
            model=request["model"],
            instructions=request["instructions"],
            input=request["input"],
            max_output_tokens=request["max_output_tokens"],
        )
        latency = time.perf_counter() - started
        return {
            "status": getattr(response, "status", "completed"),
            "output_text": response.output_text,
            "metadata": {
                "model": getattr(response, "model", request["model"]),
                "request_api": request["request_api"],
                "latency_seconds": latency,
            },
            "usage": usage_to_dict(getattr(response, "usage", None)),
        }

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
            "temperature_parameter_policy": "omit_verified_deprecated",
            "top_p_parameter_policy": "omit_optional_sampling_controls",
        }

    def invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is required for Anthropic provider API inference.")
        from anthropic import Anthropic  # type: ignore[import-not-found]

        client = Anthropic()
        started = time.perf_counter()
        message = client.messages.create(
            model=request["model"],
            system=request["system"],
            messages=request["messages"],
            max_tokens=request["max_tokens"],
        )
        latency = time.perf_counter() - started
        return {
            "status": "completed",
            "content": [{"text": message.content[0].text}],
            "metadata": {
                "model": getattr(message, "model", request["model"]),
                "stop_reason": getattr(message, "stop_reason", None),
                "request_api": request["request_api"],
                "latency_seconds": latency,
            },
            "usage": usage_to_dict(getattr(message, "usage", None)),
        }

    def extract_raw_response(self, provider_response: dict[str, Any]) -> str | None:
        content = provider_response.get("content")
        if not isinstance(content, list) or not content or "text" not in content[0]:
            raise ValueError("Malformed Anthropic Messages API fixture missing content[0].text field.")
        return content[0].get("text")


class LocalTransformersLlamaQMULAdapter(ModelAdapter):
    """Transport envelope for local cached Llama Transformers generation."""

    _tokenizer: Any = None
    _model: Any = None

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
                "temperature_parameter_policy": "omit_not_active_under_greedy_decoding",
                "top_p_parameter_policy": "omit_not_active_under_greedy_decoding",
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
        import torch  # type: ignore[import-not-found]
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig  # type: ignore[import-not-found]

        if self._tokenizer is None or self._model is None:
            quant_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
            )
            self._tokenizer = AutoTokenizer.from_pretrained(request["model"], local_files_only=True)
            self._model = AutoModelForCausalLM.from_pretrained(
                request["model"],
                quantization_config=quant_config,
                device_map="auto",
                max_memory={0: "43GiB"},
                torch_dtype=torch.bfloat16,
                low_cpu_mem_usage=True,
                local_files_only=True,
            )
            self._model.eval()
        started = time.perf_counter()
        inputs = self._tokenizer.apply_chat_template(
            request["messages"],
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
        )
        if hasattr(inputs, "to"):
            inputs = inputs.to("cuda")
        with torch.inference_mode():
            outputs = self._model.generate(
                inputs,
                max_new_tokens=request["generation_config"]["max_new_tokens"],
                do_sample=False,
                pad_token_id=self._tokenizer.eos_token_id,
            )
        generated = outputs[0][inputs.shape[-1]:]
        latency = time.perf_counter() - started
        return {
            "status": "completed",
            "decoded_text": self._tokenizer.decode(generated, skip_special_tokens=True),
            "metadata": {
                "model": request["model"],
                "request_api": request["request_api"],
                "latency_seconds": latency,
                "device_map": getattr(self._model, "hf_device_map", None),
            },
            "usage": None,
        }

    def extract_raw_response(self, provider_response: dict[str, Any]) -> str | None:
        if "decoded_text" not in provider_response:
            raise ValueError("Malformed local Transformers fixture missing decoded_text field.")
        return provider_response.get("decoded_text")


def usage_to_dict(usage: Any) -> dict[str, Any] | None:
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if hasattr(usage, "dict"):
        return usage.dict()
    if isinstance(usage, dict):
        return usage
    return {name: getattr(usage, name) for name in dir(usage) if not name.startswith("_") and isinstance(getattr(usage, name), (int, float, str, bool, type(None)))}
