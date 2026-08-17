"""Model and backend registries for Phase 6E.1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MODEL_REGISTRY_VERSION = "phase6e1_model_registry_v1"
BACKEND_REGISTRY_VERSION = "phase6e1_backend_registry_v1"
PLACEHOLDER_MODEL_ID = "TO_FREEZE_IN_PHASE_6E_2"

DEFAULT_MODEL_REGISTRY_PATH = Path("llm-experiments/config/phase6e1_model_registry.json")
DEFAULT_BACKEND_REGISTRY_PATH = Path("llm-experiments/config/phase6e1_backend_registry.json")


def load_model_registry(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_backend_registry(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def model_specs_by_key(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["model_key"]: row for row in registry["models"]}


def backend_specs_by_key(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["backend_key"]: row for row in registry["backends"]}


def resolve_model(model_key: str, registry: dict[str, Any]) -> dict[str, Any]:
    specs = model_specs_by_key(registry)
    if model_key not in specs:
        raise KeyError(f"Unknown model key: {model_key}")
    return specs[model_key]


def resolve_backend(backend_key: str, registry: dict[str, Any]) -> dict[str, Any]:
    specs = backend_specs_by_key(registry)
    if backend_key not in specs:
        raise KeyError(f"Unknown backend key: {backend_key}")
    return specs[backend_key]


def assert_no_secrets(registry: dict[str, Any]) -> None:
    text = json.dumps(registry, sort_keys=True)
    forbidden = ["api_key", "secret", "bearer ", "sk-", "token_value", "password"]
    if any(token in text.lower() for token in forbidden):
        raise ValueError("Registry appears to contain credentials or secret values.")
