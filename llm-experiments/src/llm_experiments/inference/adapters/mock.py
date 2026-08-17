"""Deterministic mock adapter for Phase 6E.1 tests."""

from __future__ import annotations

import json
from typing import Any

from llm_experiments.inference.base import ModelAdapter


MOCK_VALID_RESPONSE = {
    "predicted_preferred_mix": "C",
    "predicted_ratings": {"A": 60, "B": 45, "C": 80, "D": 70, "E": 55},
    "predicted_ranking": ["C", "D", "A", "E", "B"],
}


class MockAdapter(ModelAdapter):
    """Infrastructure-only adapter. It never represents a real model."""

    def __init__(self, backend_config: dict[str, Any]):
        super().__init__(backend_config)
        self._invocations = 0

    def invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        mode = self._next_mode(request)
        if mode == "valid_response":
            return {"status": "completed", "text": json.dumps(MOCK_VALID_RESPONSE, sort_keys=True), "usage": None, "metadata": {"mock_mode": mode}}
        if mode == "invalid_json":
            return {"status": "completed", "text": "This is not JSON", "usage": None, "metadata": {"mock_mode": mode}}
        if mode == "schema_invalid":
            return {
                "status": "completed",
                "text": json.dumps({"predicted_preferred_mix": "F", "predicted_ratings": {"A": 1}, "predicted_ranking": ["A"]}),
                "usage": None,
                "metadata": {"mock_mode": mode},
            }
        if mode == "timeout":
            return {"status": "timeout", "text": None, "usage": None, "metadata": {"mock_mode": mode}, "error": {"type": "timeout"}}
        if mode == "connection_error":
            return {"status": "error", "text": None, "usage": None, "metadata": {"mock_mode": mode}, "error": {"type": "connection_error"}}
        if mode == "http_500":
            return {"status": "error", "text": None, "usage": None, "metadata": {"mock_mode": mode}, "error": {"type": "http_error", "http_status_code": 500}}
        if mode == "http_400":
            return {"status": "error", "text": None, "usage": None, "metadata": {"mock_mode": mode}, "error": {"type": "http_error", "http_status_code": 400}}
        if mode == "rate_limited":
            return {"status": "error", "text": None, "usage": None, "metadata": {"mock_mode": mode}, "error": {"type": "rate_limited", "http_status_code": 429, "retry_after_seconds": 1}}
        if mode == "auth_failure":
            return {"status": "error", "text": None, "usage": None, "metadata": {"mock_mode": mode}, "error": {"type": "auth_failure", "http_status_code": 401, "message": "Authorization failed for Bearer sk-test"}}
        if mode == "backend_unavailable":
            return {"status": "backend_unavailable", "text": None, "usage": None, "metadata": {"mock_mode": mode}, "error": {"type": "backend_unavailable"}}
        if mode == "missing_text_field":
            return {"status": "completed", "usage": None, "metadata": {"mock_mode": mode}}
        if mode == "empty_response":
            return {"status": "completed", "text": "", "usage": None, "metadata": {"mock_mode": mode}}
        raise ValueError(f"Unknown mock mode: {mode}")

    def extract_raw_response(self, provider_response: dict[str, Any]) -> str | None:
        if "text" not in provider_response:
            raise ValueError("Malformed mock provider response missing text field.")
        return provider_response.get("text")

    def healthcheck(self) -> dict[str, Any]:
        return {"backend_key": self.backend_key, "available": True, "status": "mock_only"}

    def _next_mode(self, request: dict[str, Any]) -> str:
        repair_modes = self.backend_config.get("mock_repair_modes", {})
        if request.get("attempt_type") == "format_repair":
            mode = repair_modes.get(request.get("parent_inference_request_id")) or self.backend_config.get("mock_repair_mode")
            if mode:
                return mode
        sequence = self.backend_config.get("mock_sequence")
        if sequence:
            index = min(self._invocations, len(sequence) - 1)
            self._invocations += 1
            return sequence[index]
        self._invocations += 1
        return self.backend_config.get("mock_mode", "valid_response")
