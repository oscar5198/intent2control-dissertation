"""Common adapter interface for Phase 6E.1 inference backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ModelAdapter(ABC):
    """Backend adapter contract.

    Adapters may transform messages into transport envelopes, but they must not
    reconstruct or modify rendered prompts.
    """

    def __init__(self, backend_config: dict[str, Any]):
        self.backend_config = backend_config

    @property
    def backend_key(self) -> str:
        return str(self.backend_config["backend_key"])

    @property
    def backend_type(self) -> str:
        return str(self.backend_config["backend_type"])

    def prepare_request(self, inference_request: dict[str, Any]) -> dict[str, Any]:
        self._assert_canonical_request(inference_request)
        return {
            "backend_key": self.backend_key,
            "backend_type": self.backend_type,
            "inference_request_id": inference_request["inference_request_id"],
            "messages": inference_request["messages"],
            "response_schema_version": inference_request["response_schema_version"],
        }

    @abstractmethod
    def invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        """Invoke a backend and return a provider-shaped response."""

    @abstractmethod
    def extract_raw_response(self, provider_response: dict[str, Any]) -> str | None:
        """Extract raw model text without fixing malformed predictions."""

    def extract_usage(self, provider_response: dict[str, Any]) -> dict[str, Any] | None:
        return provider_response.get("usage")

    def healthcheck(self) -> dict[str, Any]:
        return {"backend_key": self.backend_key, "available": False, "status": "not_checked"}

    def describe_backend(self) -> dict[str, Any]:
        return {
            "backend_key": self.backend_key,
            "backend_type": self.backend_type,
            "execution_environment": self.backend_config.get("execution_environment"),
            "transport": self.backend_config.get("transport"),
            "capabilities": self.backend_config.get("capabilities", {}),
            "context_window": self.backend_config.get("context_window", {}),
        }

    def supports_capability(self, capability: str) -> bool:
        return self.backend_config.get("capabilities", {}).get(capability) is True

    def require_capability(self, capability: str) -> None:
        if not self.supports_capability(capability):
            raise RuntimeError(f"Backend {self.backend_key} does not declare required capability {capability!r}.")

    def _assert_canonical_request(self, inference_request: dict[str, Any]) -> None:
        if not inference_request.get("rendered_prompt_id"):
            raise ValueError("Adapter requires a frozen rendered_prompt_id.")
        if "messages" not in inference_request:
            raise ValueError("Adapter requires rendered messages.")
        messages = inference_request["messages"]
        if len(messages) != 2 or messages[0].get("role") != "system" or messages[1].get("role") != "user":
            raise ValueError("Adapter received malformed rendered messages.")
