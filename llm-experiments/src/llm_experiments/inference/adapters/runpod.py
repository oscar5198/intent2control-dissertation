"""RunPod backend adapter scaffold for Phase 6E.1."""

from __future__ import annotations

from typing import Any

from llm_experiments.inference.base import ModelAdapter


class RunPodAdapter(ModelAdapter):
    """Scaffold for future Centaur RunPod HTTP/serverless execution."""

    def invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("RunPod real inference is not enabled in Phase 6E.1.")

    def extract_raw_response(self, provider_response: dict[str, Any]) -> str | None:
        if "text" not in provider_response:
            raise ValueError("Malformed RunPod provider response missing text field.")
        return provider_response.get("text")
