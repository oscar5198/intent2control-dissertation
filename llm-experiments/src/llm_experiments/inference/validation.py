"""Response parsing and schema validation primitives."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def load_response_schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_response_text(raw_response_text: str | None, response_schema: dict[str, Any]) -> dict[str, Any]:
    if raw_response_text is None or raw_response_text == "":
        return {"status": "missing_response", "valid": False, "parsed": None, "errors": ["missing response text"]}
    try:
        parsed = json.loads(raw_response_text)
    except json.JSONDecodeError as exc:
        return {"status": "invalid_json", "valid": False, "parsed": None, "errors": [str(exc)]}
    if not isinstance(parsed, dict):
        return {"status": "schema_invalid", "valid": False, "parsed": parsed, "errors": ["response is not a JSON object"]}
    errors = sorted(error.message for error in Draft202012Validator(response_schema).iter_errors(parsed))
    if errors:
        return {"status": "schema_invalid", "valid": False, "parsed": parsed, "errors": errors}
    return {
        "status": "valid",
        "valid": True,
        "parsed": {
            "predicted_preferred_mix": parsed["predicted_preferred_mix"],
            "predicted_ratings": parsed["predicted_ratings"],
            "predicted_ranking": parsed["predicted_ranking"],
        },
        "errors": [],
    }
