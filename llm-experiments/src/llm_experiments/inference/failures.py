"""Phase 6E.4 deterministic failure taxonomy and classification."""

from __future__ import annotations

from typing import Any


FAILURE_HANDLING_VERSION = "phase6e_failure_handling_v1"

PRE_FLIGHT_FAILURES = {
    "prompt_package_invalid",
    "model_config_not_frozen",
    "backend_not_verified",
    "schema_missing",
}
TRANSPORT_FAILURES = {
    "timeout",
    "connection_error",
    "http_client_error",
    "http_server_error",
    "backend_unavailable",
    "rate_limited",
    "bad_credentials",
    "unsupported_model",
}
RESPONSE_EXTRACTION_FAILURES = {
    "empty_response",
    "missing_text_field",
    "malformed_provider_response",
}
STRUCTURAL_VALIDATION_FAILURES = {"invalid_json", "schema_invalid"}
INTERNAL_FAILURES = {
    "logging_conflict",
    "duplicate_request_conflict",
    "unexpected_internal_error",
}

RETRYABLE_FAILURES = {
    "timeout",
    "connection_error",
    "http_server_error",
    "backend_unavailable",
    "rate_limited",
    "empty_response",
}
NON_RETRYABLE_FAILURES = (
    PRE_FLIGHT_FAILURES
    | {"http_client_error", "bad_credentials", "unsupported_model"}
    | {"missing_text_field", "malformed_provider_response"}
    | STRUCTURAL_VALIDATION_FAILURES
    | INTERNAL_FAILURES
)
REPAIRABLE_VALIDATION_STATUSES = {"invalid_json", "schema_invalid"}


def failure_category(code: str | None) -> str | None:
    if code is None:
        return None
    if code in PRE_FLIGHT_FAILURES:
        return "preflight"
    if code in TRANSPORT_FAILURES:
        return "transport"
    if code in RESPONSE_EXTRACTION_FAILURES:
        return "response_extraction"
    if code in STRUCTURAL_VALIDATION_FAILURES:
        return "structural_validation"
    if code in INTERNAL_FAILURES:
        return "internal"
    return "unknown"


def is_retryable(code: str | None, retryable_codes: set[str] | None = None) -> bool:
    if code is None:
        return False
    return code in (retryable_codes or RETRYABLE_FAILURES)


def should_repair(validation_status: str | None, request_status: str = "completed", raw_response_text: str | None = None) -> bool:
    return request_status == "completed" and bool(raw_response_text) and validation_status in REPAIRABLE_VALIDATION_STATUSES


def classify_failure(
    provider_response: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    extraction_error: Exception | None = None,
) -> dict[str, Any]:
    provider_response = provider_response or {}
    validation = validation or {}
    error = provider_response.get("error") or {}
    status = provider_response.get("status")
    http_status = error.get("http_status_code") or provider_response.get("http_status_code")
    code = error.get("type") or error.get("code")

    if extraction_error is not None:
        message = str(extraction_error)
        if "missing text" in message.lower():
            code = "missing_text_field"
        else:
            code = "malformed_provider_response"
    elif status == "timeout":
        code = "timeout"
    elif status == "backend_unavailable":
        code = "backend_unavailable"
    elif http_status == 429:
        code = "rate_limited"
    elif isinstance(http_status, int) and 500 <= http_status <= 599:
        code = "http_server_error"
    elif isinstance(http_status, int) and 400 <= http_status <= 499:
        code = "bad_credentials" if http_status in {401, 403} else "http_client_error"
    elif code == "auth_failure":
        code = "bad_credentials"
    elif validation.get("status") == "missing_response" and status == "completed":
        code = "empty_response"
    elif validation.get("status") in STRUCTURAL_VALIDATION_FAILURES:
        code = validation["status"]
    elif status in {"error", "connection_error"} and code is None:
        code = "connection_error"

    return {
        "failure_code": code,
        "failure_category": failure_category(code),
        "retryable": is_retryable(code),
        "http_status_code": http_status,
        "retry_after_seconds": error.get("retry_after_seconds") or provider_response.get("retry_after_seconds"),
    }
