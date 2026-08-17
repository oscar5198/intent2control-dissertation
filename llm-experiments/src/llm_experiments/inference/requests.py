"""Canonical Phase 6E.1 inference request objects."""

from __future__ import annotations

import hashlib
import json
from typing import Any


INFERENCE_INTERFACE_VERSION = "phase6e_inference_interface_v1"
DEFAULT_INFERENCE_CONFIG_VERSION = "phase6e1_inference_config_placeholder_v1"
DEFAULT_PROMPT_PACKAGE_VERSION = "phase6d_prompt_package_v1"
PRIMARY_ATTEMPT_TYPE = "primary"


def make_inference_request_id(
    rendered_prompt_id: str,
    model_key: str,
    inference_config_version: str,
    attempt_type: str = PRIMARY_ATTEMPT_TYPE,
    attempt_number: int = 1,
) -> str:
    stable = "::".join([rendered_prompt_id, model_key, inference_config_version, attempt_type, str(attempt_number)])
    return f"phase6e_req_{hashlib.sha256(stable.encode('utf-8')).hexdigest()[:32]}"


def make_inference_request(
    rendered_prompt: dict[str, Any],
    model_spec: dict[str, Any],
    inference_config_version: str = DEFAULT_INFERENCE_CONFIG_VERSION,
    prompt_package_version: str = DEFAULT_PROMPT_PACKAGE_VERSION,
    attempt_type: str = PRIMARY_ATTEMPT_TYPE,
    attempt_number: int = 1,
) -> dict[str, Any]:
    validate_rendered_prompt_for_request(rendered_prompt)
    model_key = model_spec["model_key"]
    request_id = make_inference_request_id(
        rendered_prompt["rendered_prompt_id"],
        model_key,
        inference_config_version,
        attempt_type,
        attempt_number,
    )
    return {
        "schema_version": "phase6e_inference_request_v1",
        "inference_interface_version": INFERENCE_INTERFACE_VERSION,
        "inference_request_id": request_id,
        "rendered_prompt_id": rendered_prompt["rendered_prompt_id"],
        "condition_object_id": rendered_prompt["condition_object_id"],
        "prediction_example_id": rendered_prompt["prediction_example_id"],
        "condition": rendered_prompt["condition"],
        "model_key": model_key,
        "backend_key": model_spec["default_backend_key"],
        "prompt_package_version": prompt_package_version,
        "messages": json.loads(json.dumps(rendered_prompt["messages"])),
        "response_schema_version": rendered_prompt["response_schema_version"],
        "inference_config_id": inference_config_version,
        "attempt_type": attempt_type,
        "attempt_number": attempt_number,
    }


def validate_rendered_prompt_for_request(rendered_prompt: dict[str, Any]) -> None:
    required = [
        "schema_version",
        "rendered_prompt_id",
        "condition_object_id",
        "prediction_example_id",
        "condition",
        "prompt_spec_version",
        "response_schema_version",
        "messages",
    ]
    missing = [field for field in required if field not in rendered_prompt]
    if missing:
        raise ValueError(f"Rendered prompt missing required request fields: {missing}")
    if rendered_prompt["condition"] not in {"non_history", "personalised_history"}:
        raise ValueError(f"Unsupported rendered prompt condition: {rendered_prompt['condition']}")
    messages = rendered_prompt["messages"]
    if not isinstance(messages, list) or len(messages) != 2:
        raise ValueError("Rendered prompt messages must contain exactly system and user messages.")
    if messages[0].get("role") != "system" or messages[1].get("role") != "user":
        raise ValueError("Rendered prompt messages must preserve system then user roles.")


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
