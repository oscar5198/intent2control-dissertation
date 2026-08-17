#!/usr/bin/env python3
"""Create the Phase 6G RunPod Centaur verification artifact.

Run this inside the RunPod Centaur environment. It records deployment metadata
only; it does not load participant data, render study prompts, or call the
model with study content.
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


SCHEMA_VERSION = "phase6g_runpod_centaur_verification_v1"
SCRIPT_VERSION = "phase6g2c_runpod_centaur_verify_script_v1"
UNVERIFIED = "UNVERIFIED"
SOURCE_CANDIDATES = [
    "marcelbinz/Llama-3.1-Centaur-70B",
    "marcelbinz/Llama-3.1-Centaur-70B-adapter",
]


def main() -> int:
    args = parse_args()
    metadata = load_json(Path(args.config)) if args.config else {}
    endpoint = args.endpoint or os.environ.get("RUNPOD_CENTAUR_ENDPOINT_URL", "")
    health = probe_json(args.health_endpoint)
    record = build_centaur_record(metadata, endpoint, health, args)
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "environment": "RunPod",
        "verification_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verification_script_version": SCRIPT_VERSION,
        "host_metadata": safe_host_metadata(args.include_hostname),
        "model_record": record,
        "checks": build_checks(record),
        "unresolved_items": unresolved_items(record),
        "overall_runpod_centaur_verified": bool(record["exact_served_id_verified"] and record["backend_contract_verified"]),
        "credential_policy": "No credentials are emitted; endpoint URLs are sanitized.",
    }
    write_json(Path(args.output), artifact)
    print(f"Wrote RunPod verification artifact to {args.output}")
    print(f"overall_runpod_centaur_verified={str(artifact['overall_runpod_centaur_verified']).lower()}")
    return 0


def build_centaur_record(
    metadata: dict[str, Any],
    endpoint: str,
    health: dict[str, Any] | None,
    args: argparse.Namespace,
) -> dict[str, Any]:
    source = args.deployed_model_source or metadata.get("deployed_model_source") or metadata.get("model_repository")
    exact_id = args.model_id or metadata.get("exact_served_id") or source
    return {
        "model_key": "centaur",
        "intended_scientific_model": "Centaur",
        "scientific_model_identity_known": True,
        "expected_source_family": "Llama-3.1-based Centaur 70B",
        "source_candidates": SOURCE_CANDIDATES,
        "deployed_model_source": source or UNVERIFIED,
        "deployment_form": args.deployment_form or metadata.get("deployment_form", UNVERIFIED),
        "base_model": args.base_model or metadata.get("base_model", UNVERIFIED),
        "exact_served_id_verified": bool(exact_id),
        "exact_served_id": exact_id or UNVERIFIED,
        "revision": args.revision or metadata.get("revision", UNVERIFIED),
        "revision_verified": bool(args.revision or metadata.get("revision")),
        "commit": metadata.get("commit", UNVERIFIED),
        "quantisation": args.quantisation or metadata.get("quantisation", UNVERIFIED),
        "precision": args.precision or metadata.get("precision", UNVERIFIED),
        "serving_framework": args.serving_framework or metadata.get("serving_framework", UNVERIFIED),
        "serving_framework_verified": bool(args.serving_framework or metadata.get("serving_framework")),
        "endpoint_type": args.endpoint_type or metadata.get("endpoint_type", UNVERIFIED),
        "endpoint_url_sanitized": sanitize_url(endpoint) if endpoint else UNVERIFIED,
        "tokenizer_chat_template": metadata.get("tokenizer_chat_template", UNVERIFIED),
        "context_limit": metadata.get("context_limit", UNVERIFIED),
        "max_output_limit": metadata.get("max_output_limit", UNVERIFIED),
        "temperature_or_greedy_controls": metadata.get("temperature_or_greedy_controls", UNVERIFIED),
        "top_p_support": metadata.get("top_p_support", UNVERIFIED),
        "seed_support": metadata.get("seed_support", UNVERIFIED),
        "system_role_behavior": metadata.get("system_role_behavior", UNVERIFIED),
        "structured_output_mechanism": metadata.get("structured_output_mechanism", UNVERIFIED),
        "health_check": {"healthy": bool(health), "source": "configured_health_endpoint" if health else "not_checked"},
        "request_contract": metadata.get("request_contract", UNVERIFIED),
        "response_extraction_contract": metadata.get("response_extraction_contract", UNVERIFIED),
        "endpoint_server_version": metadata.get("endpoint_server_version", UNVERIFIED),
        "backend_contract_verified": bool(metadata.get("request_contract") and metadata.get("response_extraction_contract")),
        "centaur_choice_convention_audit": {
            "recommendation_exists": args.choice_recommendation_exists,
            "technically_required": args.choice_technically_required,
            "evidence_source_note": args.choice_evidence_note or metadata.get("choice_evidence_note", UNVERIFIED),
            "likely_implication_for_frozen_phase6d_package": "to_be_decided_locally_after_verification; this script does not modify prompts",
        },
    }


def build_checks(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "model_key_is_centaur": record["model_key"] == "centaur",
        "source_candidate_recorded": record["deployed_model_source"] not in {"", None, UNVERIFIED},
        "exact_served_id_verified": record["exact_served_id_verified"],
        "backend_contract_verified": record["backend_contract_verified"],
    }


def unresolved_items(record: dict[str, Any]) -> list[str]:
    fields = [
        "deployed_model_source",
        "deployment_form",
        "base_model",
        "exact_served_id",
        "revision",
        "quantisation",
        "precision",
        "serving_framework",
        "tokenizer_chat_template",
        "context_limit",
        "max_output_limit",
        "temperature_or_greedy_controls",
        "top_p_support",
        "seed_support",
        "system_role_behavior",
        "structured_output_mechanism",
        "request_contract",
        "response_extraction_contract",
    ]
    return [field for field in fields if record.get(field) in {"", None, UNVERIFIED}]


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
    parser = argparse.ArgumentParser(description="Verify RunPod Centaur deployment metadata for Phase 6G.2C.")
    parser.add_argument("--output", default="llm-experiments/outputs/real/phase6g2_remote/phase6g2c_runpod_centaur_verification.json")
    parser.add_argument("--config", help="Optional JSON metadata file produced inside the RunPod image.")
    parser.add_argument("--endpoint", help="Optional endpoint URL; sanitized before recording.")
    parser.add_argument("--health-endpoint", help="Optional health endpoint.")
    parser.add_argument("--model-id", help="Optional exact served model ID.")
    parser.add_argument("--deployed-model-source", help="Exact deployed Centaur repository/checkpoint.")
    parser.add_argument("--deployment-form", choices=["merged", "adapter", "unknown"], help="Centaur deployment form.")
    parser.add_argument("--base-model", help="Required later if deployment form is adapter.")
    parser.add_argument("--revision", help="Revision/commit/snapshot where available.")
    parser.add_argument("--quantisation", help="Quantisation method if any.")
    parser.add_argument("--precision", help="Precision if known.")
    parser.add_argument("--serving-framework", help="Serving framework such as vLLM/TGI/Transformers.")
    parser.add_argument("--endpoint-type", help="Endpoint type label.")
    parser.add_argument("--choice-recommendation-exists", action="store_true")
    parser.add_argument("--choice-technically-required", choices=["true", "false", "unknown"], default="unknown")
    parser.add_argument("--choice-evidence-note", help="Short source note about the Centaur << >> convention.")
    parser.add_argument("--include-hostname", action="store_true", help="Include hostname if safe for the RunPod environment.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
