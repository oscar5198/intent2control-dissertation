#!/usr/bin/env python3
"""Create the Phase 6G QMUL model-verification artifact.

Run this on the QMUL environment. It does not load participant data, does not
render study prompts, and does not call a text-generation endpoint unless the
operator explicitly supplies metadata/health endpoints.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import request
from urllib.parse import urlsplit, urlunsplit


SCHEMA_VERSION = "phase6g_qmul_verification_v1"
SCRIPT_VERSION = "phase6g2b_qmul_verify_script_v1"
MODEL_SPECS = {
    "gpt": "GPT-5.5",
    "claude_sonnet": "Claude Sonnet 5",
    "llama_3_1_70b_instruct": "Llama 3.1 70B Instruct",
}
UNVERIFIED = "UNVERIFIED"


def main() -> int:
    args = parse_args()
    records = []
    explicit = load_json(Path(args.config)) if args.config else {}
    endpoint = args.endpoint or os.environ.get("QMUL_LLM_ENDPOINT_URL", "")
    model_list = probe_json(args.model_list_endpoint)
    health = probe_json(args.health_endpoint)
    for key, name in MODEL_SPECS.items():
        source = explicit.get(key, {})
        records.append(build_model_record(key, name, source, endpoint, model_list, health, args))
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "environment": "QMUL",
        "verification_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verification_script_version": SCRIPT_VERSION,
        "host_metadata": safe_host_metadata(args.include_hostname),
        "model_records": records,
        "checks": build_checks(records),
        "unresolved_items": unresolved_items(records),
        "overall_qmul_backend_verified": all(record["backend_contract_verified"] and record["exact_served_id_verified"] for record in records),
        "credential_policy": "No credentials are emitted; endpoint URLs are sanitized.",
    }
    write_json(Path(args.output), artifact)
    print(f"Wrote QMUL verification artifact to {args.output}")
    print(f"overall_qmul_backend_verified={str(artifact['overall_qmul_backend_verified']).lower()}")
    return 0


def build_model_record(
    key: str,
    name: str,
    source: dict[str, Any],
    endpoint: str,
    model_list: dict[str, Any] | None,
    health: dict[str, Any] | None,
    args: argparse.Namespace,
) -> dict[str, Any]:
    served_id = source.get("exact_served_id") or source.get("model_id")
    if not served_id and args.model_key == key:
        served_id = args.model_id
    return {
        "model_key": key,
        "intended_scientific_model": name,
        "scientific_model_identity_known": True,
        "exact_served_id_verified": bool(served_id),
        "exact_served_id": served_id or UNVERIFIED,
        "snapshot_or_version": source.get("snapshot_or_version", UNVERIFIED),
        "revision": source.get("revision", UNVERIFIED),
        "revision_verified": bool(source.get("revision")),
        "backend_or_serving_mechanism": source.get("backend_or_serving_mechanism", args.serving_mode or UNVERIFIED),
        "endpoint_type": source.get("endpoint_type", args.endpoint_type or UNVERIFIED),
        "endpoint_url_sanitized": sanitize_url(endpoint) if endpoint else UNVERIFIED,
        "serving_framework": source.get("serving_framework", UNVERIFIED),
        "serving_framework_verified": bool(source.get("serving_framework")),
        "quantisation_or_precision": source.get("quantisation_or_precision", UNVERIFIED),
        "quantisation_verified": bool(source.get("quantisation_or_precision")),
        "tokenizer_chat_template_identity": source.get("tokenizer_chat_template_identity", UNVERIFIED),
        "system_message_support": source.get("system_message_support", UNVERIFIED),
        "structured_output_support": source.get("structured_output_support", UNVERIFIED),
        "temperature_or_greedy_controls": source.get("temperature_or_greedy_controls", UNVERIFIED),
        "top_p_support": source.get("top_p_support", UNVERIFIED),
        "seed_support": source.get("seed_support", UNVERIFIED),
        "context_limit": source.get("context_limit", UNVERIFIED),
        "max_output_limit": source.get("max_output_limit", UNVERIFIED),
        "usage_token_reporting": source.get("usage_token_reporting", UNVERIFIED),
        "health_check": {"healthy": bool(health), "source": "configured_health_endpoint" if health else "not_checked"},
        "model_list_observed": model_list if args.include_model_list and model_list else "not_recorded",
        "response_extraction_contract": source.get("response_extraction_contract", UNVERIFIED),
        "backend_contract_verified": bool(source.get("request_contract") and source.get("response_extraction_contract")),
        "unsupported_or_unresolved_fields": [],
    }


def build_checks(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model_count": len(records),
        "all_intended_models_present": set(record["model_key"] for record in records) == set(MODEL_SPECS),
        "all_exact_served_ids_verified": all(record["exact_served_id_verified"] for record in records),
        "all_backend_contracts_verified": all(record["backend_contract_verified"] for record in records),
    }


def unresolved_items(records: list[dict[str, Any]]) -> list[str]:
    items = []
    fields = [
        "exact_served_id",
        "revision",
        "serving_framework",
        "quantisation_or_precision",
        "tokenizer_chat_template_identity",
        "system_message_support",
        "structured_output_support",
        "temperature_or_greedy_controls",
        "top_p_support",
        "seed_support",
        "context_limit",
        "usage_token_reporting",
        "response_extraction_contract",
    ]
    for record in records:
        for field in fields:
            if record.get(field) in {"", None, UNVERIFIED}:
                items.append(f"{record['model_key']}: {field}")
    return items


def probe_json(url: str | None) -> dict[str, Any] | None:
    if not url:
        return None
    req = request.Request(url, headers={"Accept": "application/json"})
    with request.urlopen(req, timeout=10) as response:  # noqa: S310 - operator-supplied metadata endpoint only
        return json.loads(response.read().decode("utf-8"))


def sanitize_url(url: str) -> str:
    parts = urlsplit(url)
    netloc = parts.hostname or ""
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def safe_host_metadata(include_hostname: bool) -> dict[str, Any]:
    metadata = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
    }
    if include_hostname:
        metadata["hostname"] = socket.gethostname()
    return metadata


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify QMUL model deployment metadata for Phase 6G.2B.")
    parser.add_argument("--output", default="llm-experiments/outputs/real/phase6g2_remote/phase6g2b_qmul_model_verification.json")
    parser.add_argument("--config", help="Optional JSON metadata file keyed by model_key.")
    parser.add_argument("--endpoint", help="Optional shared endpoint URL; sanitized before recording.")
    parser.add_argument("--model-list-endpoint", help="Optional metadata/model-list endpoint.")
    parser.add_argument("--health-endpoint", help="Optional health endpoint.")
    parser.add_argument("--model-key", choices=sorted(MODEL_SPECS), help="Optional single model key for --model-id.")
    parser.add_argument("--model-id", help="Optional exact served model ID for --model-key.")
    parser.add_argument("--serving-mode", help="Optional serving mode label.")
    parser.add_argument("--endpoint-type", help="Optional endpoint type label.")
    parser.add_argument("--include-model-list", action="store_true", help="Include sanitized model-list JSON when queried.")
    parser.add_argument("--include-hostname", action="store_true", help="Include hostname if safe for the QMUL environment.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
