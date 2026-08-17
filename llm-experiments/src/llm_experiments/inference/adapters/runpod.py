"""RunPod backend adapter for Centaur production execution."""

from __future__ import annotations

import os
import time
from typing import Any
from urllib import request as urlrequest

from llm_experiments.inference.base import ModelAdapter


class RunPodAdapter(ModelAdapter):
    """Guarded HTTP adapter for verified RunPod Centaur endpoints."""

    def prepare_request(self, inference_request: dict[str, Any]) -> dict[str, Any]:
        prepared = super().prepare_request(inference_request)
        return {
            **prepared,
            "provider": "RunPod",
            "model_key": "centaur",
            "messages": inference_request["messages"],
            "response_schema_version": inference_request["response_schema_version"],
            "generation_config": {
                "primary_mode": "greedy",
                "do_sample": False,
                "max_new_tokens": 256,
                "temperature_parameter_policy": "omit_not_active_under_greedy_decoding",
                "top_p_parameter_policy": "omit_not_active_under_greedy_decoding",
            },
            "structured_output_strategy": "ordinary_text_generation_local_validation_preference_prediction_response_v1_one_formatting_repair",
        }

    def invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        endpoint = os.environ.get("RUNPOD_CENTAUR_ENDPOINT_URL")
        token = os.environ.get("RUNPOD_API_TOKEN")
        if not endpoint:
            raise RuntimeError("RUNPOD_CENTAUR_ENDPOINT_URL is required for RunPod Centaur inference.")
        if not token:
            raise RuntimeError("RUNPOD_API_TOKEN is required for RunPod Centaur inference.")
        payload = {
            "input": {
                "messages": request["messages"],
                "generation_config": request["generation_config"],
                "response_schema_version": request["response_schema_version"],
            }
        }
        started = time.perf_counter()
        req = urlrequest.Request(
            endpoint,
            data=json_bytes(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        with urlrequest.urlopen(req, timeout=int(self.backend_config.get("timeout_seconds") or 600)) as response:  # noqa: S310 - configured endpoint
            body = response.read().decode("utf-8")
        latency = time.perf_counter() - started
        provider_response = parse_json(body)
        return {
            "status": provider_response.get("status", "completed"),
            "text": extract_text(provider_response),
            "metadata": {
                "latency_seconds": latency,
                "endpoint_type": self.backend_config.get("endpoint_configuration", {}).get("endpoint_type"),
                "provider_status": provider_response.get("status"),
            },
            "usage": provider_response.get("usage"),
        }

    def extract_raw_response(self, provider_response: dict[str, Any]) -> str | None:
        if "text" not in provider_response:
            raise ValueError("Malformed RunPod provider response missing text field.")
        return provider_response.get("text")


def json_bytes(payload: dict[str, Any]) -> bytes:
    import json

    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def parse_json(text: str) -> dict[str, Any]:
    import json

    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("RunPod response must be a JSON object.")
    return payload


def extract_text(payload: dict[str, Any]) -> str | None:
    for key in ["text", "decoded_text", "output_text"]:
        if isinstance(payload.get(key), str):
            return payload[key]
    output = payload.get("output")
    if isinstance(output, dict):
        return extract_text(output)
    if isinstance(output, str):
        return output
    return None
