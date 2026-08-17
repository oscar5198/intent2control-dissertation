"""Phase 6E.4 bounded transport retry policy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llm_experiments.inference.failures import FAILURE_HANDLING_VERSION, is_retryable


DEFAULT_FAILURE_POLICY_PATH = Path("llm-experiments/config/phase6e_failure_policy_v1.json")


def load_failure_policy(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def default_failure_policy(repo_root: Path) -> dict[str, Any]:
    return load_failure_policy(repo_root / DEFAULT_FAILURE_POLICY_PATH)


def remaining_transport_attempts(policy: dict[str, Any]) -> int:
    return int(policy["max_transport_retries"]) + 1


def should_retry_transport(failure_code: str | None, transport_attempt_number: int, policy: dict[str, Any]) -> bool:
    retryable = set(policy.get("retryable_error_codes", []))
    return is_retryable(failure_code, retryable) and transport_attempt_number <= int(policy["max_transport_retries"])


def backoff_seconds(transport_attempt_number: int, policy: dict[str, Any]) -> float:
    backoff = policy.get("backoff", {})
    initial = float(backoff.get("initial_delay_seconds", 0))
    multiplier = float(backoff.get("multiplier", 1))
    maximum = float(backoff.get("maximum_delay_seconds", initial))
    delay = initial * (multiplier ** max(0, transport_attempt_number - 1))
    return min(delay, maximum)


def policy_summary(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "failure_handling_version": policy.get("failure_handling_version", FAILURE_HANDLING_VERSION),
        "max_primary_generations": policy["max_primary_generations"],
        "max_format_repair_generations": policy["max_format_repair_generations"],
        "max_transport_retries": policy["max_transport_retries"],
        "retryable_error_codes": policy["retryable_error_codes"],
        "non_retryable_error_codes": policy["non_retryable_error_codes"],
    }
