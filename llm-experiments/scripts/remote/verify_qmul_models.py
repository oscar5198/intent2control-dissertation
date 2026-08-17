#!/usr/bin/env python3
"""Create the Phase 6G QMUL model-verification artifact.

Run this on the QMUL environment. It does not load participant data, does not
render study prompts, and does not call a text-generation endpoint unless the
operator explicitly supplies metadata/health endpoints.
"""

from __future__ import annotations

import argparse
import json
import platform
import socket
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any
from urllib import request
from urllib.parse import urlsplit, urlunsplit


SCHEMA_VERSION = "phase6g_qmul_verification_v1"
SCRIPT_VERSION = "phase6g2b_qmul_verify_script_v1"
UNVERIFIED = "UNVERIFIED"
MODEL_SPECS: dict[str, dict[str, Any]] = {
    "gpt": {
        "name": "GPT-5.5",
        "deployment_architecture": "provider_api_invoked_from_qmul_runtime",
        "backend_provider": "OpenAI API",
        "client_sdk": "openai",
        "client_sdk_version": "2.53.0",
        "request_api": "OpenAI.responses.create",
        "credential_env_var": "OPENAI_API_KEY",
        "exact_served_id": "gpt-5.5",
        "endpoint_type": "provider_api_responses",
        "serving_framework": "provider_api",
        "response_extraction_contract": "response.output_text",
        "evidence_source": "user_provided_qmul_notebook_gpt55_sonnet5",
    },
    "claude_sonnet": {
        "name": "Claude Sonnet 5",
        "deployment_architecture": "provider_api_invoked_from_qmul_runtime",
        "backend_provider": "Anthropic API",
        "client_sdk": "anthropic",
        "client_sdk_version": "0.121.0",
        "request_api": "Anthropic.messages.create",
        "credential_env_var": "ANTHROPIC_API_KEY",
        "exact_served_id": "claude-sonnet-5",
        "endpoint_type": "provider_api_messages",
        "serving_framework": "provider_api",
        "response_extraction_contract": "message.content[0].text",
        "evidence_source": "user_provided_qmul_notebook_gpt55_sonnet5",
    },
    "llama_3_1_70b_instruct": {
        "name": "Llama 3.1 70B Instruct",
        "deployment_architecture": "local_huggingface_transformers_inference_from_qmul_runtime",
        "backend_provider": "local Hugging Face Transformers",
        "client_sdk": "transformers",
        "model_class": "AutoModelForCausalLM",
        "tokenizer_class": "AutoTokenizer",
        "model_source": "local_persistent_huggingface_cache",
        "local_files_only": True,
        "request_api": "AutoModelForCausalLM.generate",
        "credential_env_var": "none_required_for_local_files_only_cached_inference",
        "exact_served_id": "meta-llama/Llama-3.1-70B-Instruct",
        "endpoint_type": "not_http_local_transformers",
        "serving_framework": "transformers",
        "quantisation_or_precision": "4bit_bitsandbytes_nf4_double_quant_bfloat16",
        "quantisation": {
            "load_in_4bit": True,
            "library": "bitsandbytes",
            "bnb_4bit_quant_type": "nf4",
            "bnb_4bit_compute_dtype": "torch.bfloat16",
            "bnb_4bit_use_double_quant": True,
            "torch_dtype": "torch.bfloat16",
        },
        "device_configuration": {
            "device_map": "auto",
            "max_memory": {"0": "43GiB"},
            "low_cpu_mem_usage": True,
            "observed_hf_device_map": {"": 0},
        },
        "cache_configuration": {
            "HF_HOME": "/home/jovyan/huggingface",
            "HF_HUB_CACHE": "/home/jovyan/huggingface/hub",
        },
        "generation_mode": {
            "primary_mode": "greedy",
            "do_sample": False,
            "temperature": "not_active_under_greedy_decoding",
            "top_p": "not_active_under_greedy_decoding",
            "primary_generations_per_request": 1,
            "max_new_tokens": 256,
            "pad_token_id_policy": "tokenizer.eos_token_id",
            "project_seed": 20260814,
            "determinism_note": "greedy_decoding_is_primary_determinism_source; bitwise_gpu_determinism_not_verified",
        },
        "python_version": "3.11.7",
        "runtime_versions": {
            "python": "3.11.7",
            "torch": UNVERIFIED,
            "transformers": UNVERIFIED,
            "bitsandbytes": UNVERIFIED,
            "accelerate": UNVERIFIED,
            "cuda": UNVERIFIED,
            "source": "not_printed_in_user_provided_qmul_notebook",
        },
        "smoke_test_status": "tokenizer_loaded_model_loaded_model_eval_succeeded_generate_succeeded_from_notebook",
        "response_extraction_contract": "tokenizer.decode(generated, skip_special_tokens=True)",
        "evidence_source": "user_provided_qmul_notebook_llama_3_1_70b",
    },
}


def main() -> int:
    args = parse_args()
    records = []
    explicit = load_json(Path(args.config)) if args.config else {}
    endpoint = args.endpoint or ""
    model_list = probe_json(args.model_list_endpoint)
    health = probe_json(args.health_endpoint)
    for key, spec in MODEL_SPECS.items():
        source = explicit.get(key, {})
        records.append(build_model_record(key, spec, source, endpoint, model_list, health, args))
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "environment": "QMUL",
        "verification_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verification_script_version": SCRIPT_VERSION,
        "host_metadata": safe_host_metadata(args.include_hostname),
        "model_records": records,
        "checks": build_checks(records),
        "unresolved_items": unresolved_items(records),
        "QMUL_EXECUTION_ARCHITECTURES_VERIFIED": all(record["execution_architecture_verified"] for record in records),
        "QMUL_PRODUCTION_CONFIG_VERIFIED": all(record["production_configuration_verified"] for record in records),
        "overall_qmul_backend_verified": all(record["production_configuration_verified"] for record in records),
        "credential_policy": "No credentials are emitted; endpoint URLs are sanitized.",
    }
    write_json(Path(args.output), artifact)
    print(f"Wrote QMUL verification artifact to {args.output}")
    print(f"overall_qmul_backend_verified={str(artifact['overall_qmul_backend_verified']).lower()}")
    return 0


def build_model_record(
    key: str,
    spec: dict[str, Any],
    source: dict[str, Any],
    endpoint: str,
    model_list: dict[str, Any] | None,
    health: dict[str, Any] | None,
    args: argparse.Namespace,
) -> dict[str, Any]:
    served_id = source.get("exact_served_id") or source.get("model_id") or spec.get("exact_served_id")
    if not served_id and args.model_key == key:
        served_id = args.model_id
    request_api = source.get("request_api", spec.get("request_api", UNVERIFIED))
    response_contract = source.get("response_extraction_contract", spec.get("response_extraction_contract", UNVERIFIED))
    sdk_name = source.get("client_sdk", spec.get("client_sdk", UNVERIFIED))
    deployment_status = source.get(
        "deployment_verification_status",
        "verified_from_user_provided_qmul_notebook_evidence" if key in {"gpt", "claude_sonnet"} else "unresolved",
    )
    backend_contract_verified = bool(
        request_api not in {"", None, UNVERIFIED}
        and response_contract not in {"", None, UNVERIFIED}
        and deployment_status != "unresolved"
    )
    architecture_verified = bool(
        source.get("deployment_architecture", spec.get("deployment_architecture", UNVERIFIED)) not in {"", None, UNVERIFIED}
        and source.get("backend_provider", spec.get("backend_provider", UNVERIFIED)) not in {"", None, UNVERIFIED}
        and served_id not in {"", None, UNVERIFIED}
        and request_api not in {"", None, UNVERIFIED}
    )
    production_configuration_verified = bool(
        architecture_verified
        and backend_contract_verified
        and source.get("revision", UNVERIFIED) not in {"", None, UNVERIFIED}
        and source.get("context_limit", UNVERIFIED) not in {"", None, UNVERIFIED}
        and source.get("system_message_support", UNVERIFIED) not in {"", None, UNVERIFIED}
    )
    return {
        "model_key": key,
        "intended_scientific_model": spec["name"],
        "scientific_model_name": spec["name"],
        "scientific_model_identity_known": True,
        "exact_served_id_verified": bool(served_id not in {"", None, UNVERIFIED}),
        "exact_served_id": served_id or UNVERIFIED,
        "deployment_verification_status": deployment_status,
        "execution_architecture_verified": architecture_verified,
        "production_configuration_verified": production_configuration_verified,
        "deployment_architecture": source.get("deployment_architecture", spec.get("deployment_architecture", UNVERIFIED)),
        "backend_provider": source.get("backend_provider", spec.get("backend_provider", UNVERIFIED)),
        "client_sdk": sdk_name,
        "client_sdk_version": source.get("client_sdk_version", spec.get("client_sdk_version", installed_version(sdk_name))),
        "request_api": request_api,
        "credential_env_var": source.get("credential_env_var", spec.get("credential_env_var", UNVERIFIED)),
        "connectivity_probe": source.get("connectivity_probe", "not_run_by_this_metadata_script"),
        "python_version": source.get("python_version", spec.get("python_version", UNVERIFIED)),
        "runtime_versions": source.get("runtime_versions", spec.get("runtime_versions", build_runtime_versions(spec))),
        "snapshot_or_version": source.get("snapshot_or_version", UNVERIFIED),
        "immutable_provider_snapshot": source.get("immutable_provider_snapshot", UNVERIFIED),
        "immutable_provider_snapshot_verified": bool(source.get("immutable_provider_snapshot")),
        "revision": source.get("revision", UNVERIFIED),
        "revision_verified": bool(source.get("revision")),
        "backend_or_serving_mechanism": source.get(
            "backend_or_serving_mechanism",
            source.get("deployment_architecture", spec.get("deployment_architecture", args.serving_mode or UNVERIFIED)),
        ),
        "endpoint_type": source.get("endpoint_type", spec.get("endpoint_type", args.endpoint_type or UNVERIFIED)),
        "endpoint_url_sanitized": sanitize_url(endpoint) if endpoint else UNVERIFIED,
        "model_class": source.get("model_class", spec.get("model_class", UNVERIFIED)),
        "tokenizer_class": source.get("tokenizer_class", spec.get("tokenizer_class", UNVERIFIED)),
        "model_source": source.get("model_source", spec.get("model_source", UNVERIFIED)),
        "local_files_only": source.get("local_files_only", spec.get("local_files_only", UNVERIFIED)),
        "cache_configuration": source.get("cache_configuration", spec.get("cache_configuration", UNVERIFIED)),
        "serving_framework": source.get("serving_framework", spec.get("serving_framework", UNVERIFIED)),
        "serving_framework_verified": bool(source.get("serving_framework", spec.get("serving_framework")) not in {"", None, UNVERIFIED}),
        "quantisation_or_precision": source.get("quantisation_or_precision", spec.get("quantisation_or_precision", UNVERIFIED)),
        "quantisation": source.get("quantisation", spec.get("quantisation", UNVERIFIED)),
        "quantisation_verified": bool(source.get("quantisation_or_precision", spec.get("quantisation_or_precision")) not in {"", None, UNVERIFIED}),
        "device_configuration": source.get("device_configuration", spec.get("device_configuration", UNVERIFIED)),
        "tokenizer_chat_template_identity": source.get("tokenizer_chat_template_identity", UNVERIFIED),
        "system_message_support": source.get("system_message_support", UNVERIFIED),
        "production_message_serialization": source.get(
            "production_message_serialization",
            "tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True) if tokenizer.chat_template is verified"
            if key == "llama_3_1_70b_instruct"
            else UNVERIFIED,
        ),
        "structured_output_support": source.get("structured_output_support", UNVERIFIED),
        "structured_output_strategy": source.get(
            "structured_output_strategy",
            "ordinary_text_generation_local_validation_preference_prediction_response_v1_one_formatting_repair"
            if key == "llama_3_1_70b_instruct"
            else UNVERIFIED,
        ),
        "temperature_or_greedy_controls": source.get("temperature_or_greedy_controls", UNVERIFIED),
        "top_p_support": source.get("top_p_support", UNVERIFIED),
        "seed_support": source.get("seed_support", UNVERIFIED),
        "generation_mode": source.get("generation_mode", spec.get("generation_mode", UNVERIFIED)),
        "context_limit": source.get("context_limit", UNVERIFIED),
        "context_limit_source": source.get("context_limit_source", UNVERIFIED),
        "max_output_limit": source.get("max_output_limit", UNVERIFIED),
        "usage_token_reporting": source.get("usage_token_reporting", UNVERIFIED),
        "health_check": source.get(
            "health_check",
            {
                "healthy": key == "llama_3_1_70b_instruct",
                "source": "notebook_smoke_test" if key == "llama_3_1_70b_instruct" else ("configured_health_endpoint" if health else "not_checked"),
            },
        ),
        "model_list_observed": model_list if args.include_model_list and model_list else "not_recorded",
        "response_extraction_contract": response_contract,
        "backend_contract_verified": backend_contract_verified,
        "evidence_source": source.get("evidence_source", spec.get("evidence_source", UNVERIFIED)),
        "unsupported_or_unresolved_fields": [],
    }


def build_checks(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model_count": len(records),
        "all_intended_models_present": set(record["model_key"] for record in records) == set(MODEL_SPECS),
        "all_exact_served_ids_verified": all(record["exact_served_id_verified"] for record in records),
        "all_backend_contracts_verified": all(record["backend_contract_verified"] for record in records),
        "all_execution_architectures_verified": all(record["execution_architecture_verified"] for record in records),
        "all_production_configurations_verified": all(record["production_configuration_verified"] for record in records),
    }


def unresolved_items(records: list[dict[str, Any]]) -> list[str]:
    items = []
    fields = [
        "exact_served_id",
        "revision",
        "immutable_provider_snapshot",
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


def installed_version(package: str) -> str:
    if package in {"", None, UNVERIFIED}:
        return UNVERIFIED
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return "NOT_INSTALLED_IN_CURRENT_RUNTIME"


def build_runtime_versions(spec: dict[str, Any]) -> dict[str, Any]:
    if spec.get("client_sdk") != "transformers":
        return {}
    return {
        "python": spec.get("python_version", UNVERIFIED),
        "torch": installed_version("torch"),
        "transformers": installed_version("transformers"),
        "bitsandbytes": installed_version("bitsandbytes"),
        "accelerate": installed_version("accelerate"),
        "cuda": UNVERIFIED,
    }


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
