"""Canonical Phase 6E.1 raw inference result objects."""

from __future__ import annotations

from typing import Any

from llm_experiments.inference.requests import INFERENCE_INTERFACE_VERSION


def make_raw_result(
    request: dict[str, Any],
    backend_type: str,
    request_status: str,
    raw_response_text: str | None = None,
    provider_response_metadata: dict[str, Any] | None = None,
    usage: dict[str, Any] | None = None,
    latency: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "phase6e_raw_inference_result_v1",
        "inference_interface_version": INFERENCE_INTERFACE_VERSION,
        "inference_request_id": request["inference_request_id"],
        "rendered_prompt_id": request["rendered_prompt_id"],
        "prediction_example_id": request["prediction_example_id"],
        "condition": request["condition"],
        "model_key": request["model_key"],
        "backend_key": request["backend_key"],
        "backend_type": backend_type,
        "prompt_package_version": request["prompt_package_version"],
        "response_schema_version": request["response_schema_version"],
        "attempt_type": request["attempt_type"],
        "attempt_number": request["attempt_number"],
        "request_status": request_status,
        "raw_response_text": raw_response_text,
        "provider_response_metadata": provider_response_metadata,
        "usage": usage,
        "latency": latency,
        "error": error,
    }
