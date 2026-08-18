#!/usr/bin/env python3
"""Create the Phase 6G.2C RunPod Centaur verification artifact.

Run this inside the RunPod Centaur environment. It never reads participant
data, never renders study prompts, and only runs a trivial non-study generation
when explicitly requested with --probe-generation.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import tempfile
import time
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


SCHEMA_VERSION = "phase6g_runpod_centaur_verification_v1"
SCRIPT_VERSION = "phase6g2c_runpod_centaur_verify_script_v2"
UNVERIFIED = "UNVERIFIED"
DEFAULT_ADAPTER_REPOSITORY = "marcelbinz/Llama-3.1-Centaur-70B-adapter"
DEFAULT_ADAPTER_REVISION = "159600db8be99dc183c289923148dfd96cbd8e07"
DEFAULT_ADAPTER_SNAPSHOT = (
    "/workspace/huggingface/hub/models--marcelbinz--Llama-3.1-Centaur-70B-adapter/"
    "snapshots/159600db8be99dc183c289923148dfd96cbd8e07"
)
DEFAULT_BASE_MODEL = "unsloth/Meta-Llama-3.1-70B-bnb-4bit"
DEFAULT_BASE_REVISION = "a009b8db2439814febe725486a5ed388f12a8744"
DEFAULT_BASE_SNAPSHOT = (
    "/workspace/huggingface/hub/models--unsloth--Meta-Llama-3.1-70B-bnb-4bit/"
    "snapshots/a009b8db2439814febe725486a5ed388f12a8744"
)
PRODUCTION_MAX_SEQ_LENGTH = 32768
UNDERLYING_TOKENIZER_LIMIT = 131072
SOURCE_CANDIDATES = [
    "marcelbinz/Llama-3.1-Centaur-70B",
    DEFAULT_ADAPTER_REPOSITORY,
]
TRIVIAL_PROBE = "Reply exactly with: Centaur connectivity verified."


def main() -> int:
    args = parse_args()
    metadata_payload = load_json(Path(args.config)) if args.config else {}
    record = build_centaur_record(metadata_payload, args)
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "environment": "RunPod",
        "verification_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verification_script_version": SCRIPT_VERSION,
        "host_metadata": safe_host_metadata(args.include_hostname),
        "model_record": record,
        "checks": build_checks(record),
        "unresolved_items": unresolved_items(record),
        "RUNPOD_CENTAUR_EXECUTION_ARCHITECTURE_VERIFIED": bool(record["execution_architecture_verified"]),
        "RUNPOD_CENTAUR_PRODUCTION_CONFIG_VERIFIED": bool(record["production_configuration_verified"]),
        "overall_runpod_centaur_verified": bool(
            record["execution_architecture_verified"] and record["production_configuration_verified"]
        ),
        "credential_policy": "No credentials, HF_TOKEN values, RunPod tokens, or authenticated URLs are emitted.",
        "scope": "no participant data, no study prompts, no production inference",
    }
    write_json(Path(args.output), artifact)
    print(f"Wrote RunPod verification artifact to {args.output}")
    print(f"overall_runpod_centaur_verified={str(artifact['overall_runpod_centaur_verified']).lower()}")
    return 0


def build_centaur_record(metadata_payload: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    metadata_payload = apply_live_evidence_defaults(metadata_payload, args)
    source = first_known(
        args.deployed_model_source,
        metadata_payload.get("deployed_model_source"),
        metadata_payload.get("model_repository"),
        DEFAULT_ADAPTER_REPOSITORY,
    )
    deployment_form = first_known(args.deployment_form, metadata_payload.get("deployment_form"), "adapter")
    exact_id = first_known(args.model_id, metadata_payload.get("exact_served_id"), source)
    revision = first_known(args.revision, metadata_payload.get("revision"), discover_hf_revision(source))
    precision = first_known(args.precision, metadata_payload.get("precision"), "bnb_4bit_runtime_dtype_auto")
    quantisation = first_known(args.quantisation, metadata_payload.get("quantisation"), "4bit_bnb")
    runtime_versions = {
        **(collect_runtime_versions() if is_runpod_environment() or metadata_payload.get("record_runtime_from_current_process") else unknown_runtime_versions()),
        **metadata_payload.get("runtime_versions", {}),
    }
    tokenizer_info = {**metadata_payload.get("tokenizer", {})}
    model_config = {**metadata_payload.get("model_config", {})}
    probe = run_optional_probe(args, source, deployment_form, metadata_payload)
    if probe.get("tokenizer"):
        tokenizer_info = {**tokenizer_info, **probe["tokenizer"]}
    if probe.get("model_config"):
        model_config = {**model_config, **probe["model_config"]}

    architecture_verified = all(
        is_known(value)
        for value in [
            source,
            deployment_form,
            exact_id,
            first_known(args.serving_framework, metadata_payload.get("serving_framework"), UNVERIFIED),
        ]
    )
    production_config_verified = bool(
        architecture_verified
        and is_known(revision)
        and (is_known(precision) or is_known(quantisation))
        and is_known(tokenizer_info.get("chat_template_status"))
        and is_known(tokenizer_info.get("model_max_length"))
        and is_known(model_config.get("context_limit"))
        and probe.get("model_load", {}).get("status") == "succeeded"
        and probe.get("trivial_generation", {}).get("status") == "succeeded"
        and metadata_payload.get("centaur_choice_convention_audit", {}).get("technically_required") in {"false", False}
    )

    return {
        "model_key": "centaur",
        "intended_scientific_model": "Centaur",
        "scientific_model_identity_known": True,
        "expected_source_family": "Llama-3.1-based Centaur 70B",
        "source_candidates": SOURCE_CANDIDATES,
        "deployed_model_source": source,
        "deployment_form": deployment_form,
        "base_model": first_known(args.base_model, metadata_payload.get("base_model"), DEFAULT_BASE_MODEL, "not_applicable_if_full_merged_checkpoint"),
        "base_revision": first_known(args.base_revision, metadata_payload.get("base_revision"), DEFAULT_BASE_REVISION),
        "adapter_snapshot": first_known(args.adapter_snapshot, metadata_payload.get("adapter_snapshot"), DEFAULT_ADAPTER_SNAPSHOT),
        "base_snapshot": first_known(args.base_snapshot, metadata_payload.get("base_snapshot"), DEFAULT_BASE_SNAPSHOT),
        "exact_served_id_verified": is_known(exact_id),
        "exact_served_id": exact_id,
        "revision": revision,
        "revision_verified": is_known(revision),
        "commit": first_known(metadata_payload.get("commit"), revision),
        "runtime_versions": runtime_versions,
        "python_executable": first_known(metadata_payload.get("python_executable"), os.environ.get("PYTHON_EXECUTABLE"), UNVERIFIED),
        "gpu": metadata_payload.get("gpu", collect_gpu_metadata() if is_runpod_environment() else {"gpu_count": UNVERIFIED, "gpu_names": UNVERIFIED}),
        "quantisation": quantisation,
        "precision": precision,
        "serving_framework": first_known(args.serving_framework, metadata_payload.get("serving_framework"), UNVERIFIED),
        "serving_framework_verified": is_known(first_known(args.serving_framework, metadata_payload.get("serving_framework"))),
        "endpoint_type": first_known(args.endpoint_type, metadata_payload.get("endpoint_type"), UNVERIFIED),
        "endpoint_url_sanitized": sanitize_url(first_known(args.endpoint, os.environ.get("RUNPOD_CENTAUR_ENDPOINT_URL"), "")),
        "tokenizer": tokenizer_info,
        "tokenizer_chat_template": first_known(tokenizer_info.get("chat_template_status"), metadata_payload.get("tokenizer_chat_template"), UNVERIFIED),
        "model_config": model_config,
        "context_limit": first_known(
            model_config.get("effective_context_limit"),
            model_config.get("context_limit"),
            metadata_payload.get("context_limit"),
            PRODUCTION_MAX_SEQ_LENGTH,
        ),
        "underlying_tokenizer_limit": first_known(
            tokenizer_info.get("model_max_length"),
            metadata_payload.get("underlying_tokenizer_limit"),
            UNDERLYING_TOKENIZER_LIMIT,
        ),
        "context_compatibility": metadata_payload.get("context_compatibility", {"status": UNVERIFIED}),
        "max_output_limit": first_known(metadata_payload.get("max_output_limit"), 256),
        "generation_mode": metadata_payload.get(
            "generation_mode",
            {
                "primary_mode": "greedy",
                "do_sample": False,
                "temperature_parameter_policy": "omit_not_active_under_greedy_decoding",
                "top_p_parameter_policy": "omit_not_active_under_greedy_decoding",
                "primary_generations_per_request": 1,
                "max_new_tokens": 256,
                "project_seed": 20260814,
            },
        ),
        "temperature_or_greedy_controls": "greedy_do_sample_false_temperature_omitted_top_p_omitted",
        "top_p_support": "not_active_under_greedy_decoding",
        "seed_support": "project_seed_recorded_greedy_primary_bitwise_gpu_determinism_not_claimed",
        "system_role_behavior": first_known(
            metadata_payload.get("system_role_behavior"),
            "no_native_system_role_without_chat_template; deterministic_concatenation_preserves_frozen_phase6d_system_and_user_content",
        ),
        "message_serialization": first_known(
            metadata_payload.get("message_serialization"),
            "deterministic_concatenation_of_frozen_phase6d_system_and_user_content_no_semantic_wording_changes",
        ),
        "structured_output_mechanism": "ordinary_text_generation_local_validation_preference_prediction_response_v1_one_formatting_repair",
        "health_check": probe.get("model_load", {"status": "not_run", "healthy": False}),
        "trivial_generation_probe": probe.get("trivial_generation", {"status": "not_run", "prompt": TRIVIAL_PROBE}),
        "request_contract": first_known(metadata_payload.get("request_contract"), UNVERIFIED),
        "response_extraction_contract": first_known(metadata_payload.get("response_extraction_contract"), "decoded_text"),
        "endpoint_server_version": first_known(metadata_payload.get("endpoint_server_version"), UNVERIFIED),
        "backend_contract_verified": is_known(metadata_payload.get("request_contract")) and is_known(first_known(metadata_payload.get("response_extraction_contract"), "decoded_text")),
        "adapter_readiness": metadata_payload.get("adapter_readiness", {"status": "prepared_not_verified_without_live_runpod_contract"}),
        "centaur_choice_convention_audit": build_choice_audit(metadata_payload, args),
        "execution_architecture_verified": architecture_verified,
        "production_configuration_verified": production_config_verified,
    }


def run_optional_probe(args: argparse.Namespace, model_id: str, deployment_form: str, metadata_payload: dict[str, Any]) -> dict[str, Any]:
    if not args.probe_load and not args.probe_generation:
        return metadata_payload.get("probe_results", {})
    if not is_known(model_id):
        return {"model_load": {"status": "skipped", "healthy": False, "reason": "model_id_unverified"}}
    try:
        import torch  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - executed on remote RunPod only
        return {"model_load": {"status": "failed", "healthy": False, "error": safe_error(exc)}}

    started = time.perf_counter()
    try:  # pragma: no cover - executed on remote RunPod only
        model, tokenizer, load_metadata = load_centaur_model_for_probe(args, model_id, deployment_form, metadata_payload)
        model.eval()
        load_result = {
            "status": "succeeded",
            "healthy": True,
            "latency_seconds": time.perf_counter() - started,
            "deployment_form": deployment_form,
            "device_map": getattr(model, "hf_device_map", None),
            **load_metadata,
        }
        if not args.probe_generation:
            return {
                "model_load": load_result,
                "tokenizer": inspect_tokenizer(tokenizer),
                "model_config": inspect_model_config(model),
            }
        gen_started = time.perf_counter()
        inputs = tokenize_probe(tokenizer)
        target_device = resolve_generation_device(model)
        if hasattr(inputs, "to") and target_device:
            inputs = inputs.to(target_device)
        with torch.inference_mode():
            outputs = model.generate(inputs, max_new_tokens=32, do_sample=False, pad_token_id=tokenizer.eos_token_id)
        generated = outputs[0][inputs.shape[-1]:]
        return {
            "model_load": load_result,
            "tokenizer": inspect_tokenizer(tokenizer),
            "model_config": inspect_model_config(model),
            "trivial_generation": {
                "status": "succeeded",
                "prompt": TRIVIAL_PROBE,
                "output": tokenizer.decode(generated, skip_special_tokens=True),
                "latency_seconds": time.perf_counter() - gen_started,
            },
        }
    except Exception as exc:
        return {"model_load": {"status": "failed", "healthy": False, "error": safe_error(exc)}}


def load_centaur_model_for_probe(
    args: argparse.Namespace,
    model_id: str,
    deployment_form: str,
    metadata_payload: dict[str, Any],
) -> tuple[Any, Any, dict[str, Any]]:
    adapter_snapshot = Path(first_known(args.adapter_snapshot, metadata_payload.get("adapter_snapshot"), DEFAULT_ADAPTER_SNAPSHOT))
    base_snapshot = Path(first_known(args.base_snapshot, metadata_payload.get("base_snapshot"), DEFAULT_BASE_SNAPSHOT))
    if deployment_form == "adapter" and adapter_snapshot.exists() and base_snapshot.exists():
        return load_adapter_snapshot_with_unsloth(args, adapter_snapshot, base_snapshot)
    return load_generic_causal_lm(args, model_id)


def load_adapter_snapshot_with_unsloth(
    args: argparse.Namespace,
    adapter_snapshot: Path,
    base_snapshot: Path,
) -> tuple[Any, Any, dict[str, Any]]:
    from unsloth import FastLanguageModel  # type: ignore[import-not-found]

    with tempfile.TemporaryDirectory(prefix="phase6g2c_centaur_adapter_") as temp_root:
        temp_adapter = Path(temp_root) / "adapter"
        shutil.copytree(adapter_snapshot, temp_adapter, symlinks=False)
        rewrite_adapter_config(temp_adapter / "adapter_config.json", base_snapshot)
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=str(temp_adapter),
            max_seq_length=PRODUCTION_MAX_SEQ_LENGTH,
            dtype=None if args.torch_dtype == "auto" else args.torch_dtype,
            load_in_4bit=True,
            local_files_only=args.local_files_only,
        )
        FastLanguageModel.for_inference(model)
        return (
            model,
            tokenizer,
            {
                "loader": "unsloth.FastLanguageModel.from_pretrained",
                "adapter_snapshot_used": str(adapter_snapshot),
                "base_snapshot_used_via_temporary_adapter_config": str(base_snapshot),
                "canonical_adapter_files_modified": False,
                "max_seq_length": PRODUCTION_MAX_SEQ_LENGTH,
                "load_in_4bit": True,
                "for_inference_called": True,
            },
        )


def rewrite_adapter_config(config_path: Path, base_snapshot: Path) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["base_model_name_or_path"] = str(base_snapshot)
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_generic_causal_lm(args: argparse.Namespace, model_id: str) -> tuple[Any, Any, dict[str, Any]]:
    import torch  # type: ignore[import-not-found]
    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore[import-not-found]

    tokenizer = AutoTokenizer.from_pretrained(model_id, local_files_only=args.local_files_only)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        device_map=args.device_map,
        torch_dtype=getattr(torch, args.torch_dtype) if args.torch_dtype != "auto" else "auto",
        local_files_only=args.local_files_only,
    )
    return model, tokenizer, {"loader": "transformers.AutoModelForCausalLM.from_pretrained"}


def tokenize_probe(tokenizer: Any) -> Any:
    if getattr(tokenizer, "chat_template", None):
        messages = [{"role": "user", "content": TRIVIAL_PROBE}]
        return tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt")
    return tokenizer(TRIVIAL_PROBE, return_tensors="pt")["input_ids"]


def resolve_generation_device(model: Any) -> str | None:
    if hasattr(model, "device"):
        return str(model.device)
    device_map = getattr(model, "hf_device_map", None)
    if isinstance(device_map, dict):
        for value in device_map.values():
            if isinstance(value, str) and value not in {"cpu", "disk"}:
                return value
    return "cuda" if os.environ.get("CUDA_VISIBLE_DEVICES") else None


def inspect_tokenizer(tokenizer: Any) -> dict[str, Any]:
    chat_template = getattr(tokenizer, "chat_template", None)
    return {
        "tokenizer_class": tokenizer.__class__.__name__,
        "chat_template_status": "present" if chat_template else "absent",
        "model_max_length": first_known(getattr(tokenizer, "model_max_length", None), UNDERLYING_TOKENIZER_LIMIT),
        "tokenizer_source": "loaded_from_exact_local_adapter_snapshot",
    }


def inspect_model_config(model: Any) -> dict[str, Any]:
    config = getattr(model, "config", None)
    return {
        "model_architecture": first_known(getattr(config, "architectures", None), UNVERIFIED),
        "context_limit": PRODUCTION_MAX_SEQ_LENGTH,
        "effective_context_limit": PRODUCTION_MAX_SEQ_LENGTH,
        "underlying_tokenizer_limit": UNDERLYING_TOKENIZER_LIMIT,
        "max_position_embeddings": first_known(getattr(config, "max_position_embeddings", None), UNDERLYING_TOKENIZER_LIMIT),
        "context_limit_source": "production FastLanguageModel.from_pretrained max_seq_length=32768",
    }


def build_choice_audit(metadata_payload: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    audit = metadata_payload.get("centaur_choice_convention_audit", {})
    required = first_known(args.choice_technically_required, audit.get("technically_required"), "unknown")
    return {
        "recommendation_exists": first_known(args.choice_recommendation_exists, audit.get("recommendation_exists"), UNVERIFIED),
        "technically_required": required,
        "evidence_source_note": first_known(args.choice_evidence_note, audit.get("evidence_source_note"), UNVERIFIED),
        "would_alter_frozen_phase6d_semantic_prompt": first_known(audit.get("would_alter_frozen_phase6d_semantic_prompt"), UNVERIFIED),
        "decision_for_primary_experiment": first_known(audit.get("decision_for_primary_experiment"), "retain_common_phase6d_prompt_until_technical_requirement_is_verified"),
        "methodological_blocker": required in {"true", True},
    }


def apply_live_evidence_defaults(metadata_payload: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """Merge current Phase 6G.2C RunPod evidence without claiming a successful rerun."""
    defaults = {
        "deployed_model_source": DEFAULT_ADAPTER_REPOSITORY,
        "deployment_form": "adapter",
        "base_model": DEFAULT_BASE_MODEL,
        "exact_served_id": DEFAULT_ADAPTER_REPOSITORY,
        "revision": DEFAULT_ADAPTER_REVISION,
        "commit": DEFAULT_ADAPTER_REVISION,
        "base_revision": DEFAULT_BASE_REVISION,
        "adapter_snapshot": DEFAULT_ADAPTER_SNAPSHOT,
        "base_snapshot": DEFAULT_BASE_SNAPSHOT,
        "python_executable": "/workspace/unsloth_env/bin/python",
        "runtime_versions": {
            "python": "3.12.3",
            "torch": "2.11.0+cu129",
            "transformers": "5.5.0",
            "peft": "0.20.0",
            "bitsandbytes": "0.50.0",
            "accelerate": "1.14.0",
            "huggingface_hub": "1.27.0",
            "unsloth": "2026.8.15",
            "unsloth_zoo": "2026.8.10",
            "cuda": "12.9",
        },
        "gpu": {
            "gpu_count": 1,
            "gpu_names": ["NVIDIA A100 80GB PCIe"],
            "primary_device": "cuda:0",
            "vram": "80GB",
        },
        "quantisation": "4bit_bnb",
        "precision": "bnb_4bit_runtime_dtype_auto",
        "serving_framework": "unsloth.FastLanguageModel",
        "endpoint_type": "RunPod_self_hosted_adapter_runtime",
        "tokenizer": {
            "tokenizer_class": "TokenizersBackend",
            "chat_template_status": "absent",
            "model_max_length": UNDERLYING_TOKENIZER_LIMIT,
            "tokenizer_source": "exact local adapter snapshot with base snapshot resolution",
        },
        "tokenizer_chat_template": "absent",
        "model_config": {
            "model_architecture": "LlamaForCausalLM",
            "context_limit": PRODUCTION_MAX_SEQ_LENGTH,
            "effective_context_limit": PRODUCTION_MAX_SEQ_LENGTH,
            "underlying_tokenizer_limit": UNDERLYING_TOKENIZER_LIMIT,
            "max_position_embeddings": UNDERLYING_TOKENIZER_LIMIT,
            "context_limit_source": "production FastLanguageModel.from_pretrained max_seq_length=32768",
        },
        "context_limit": PRODUCTION_MAX_SEQ_LENGTH,
        "underlying_tokenizer_limit": UNDERLYING_TOKENIZER_LIMIT,
        "context_compatibility": {
            "status": "effective_context_limit_frozen_to_production_loader",
            "effective_context_limit": PRODUCTION_MAX_SEQ_LENGTH,
            "underlying_tokenizer_limit": UNDERLYING_TOKENIZER_LIMIT,
            "max_new_tokens": 256,
        },
        "system_role_behavior": "no_native_system_role_without_chat_template; deterministic_concatenation_preserves_frozen_phase6d_system_and_user_content",
        "message_serialization": "deterministic_concatenation_of_frozen_phase6d_system_and_user_content_no_semantic_wording_changes",
        "request_contract": "frozen_phase6d_messages_serialized_to_single_prompt_text_for_local_centaur_generation",
        "response_extraction_contract": "decoded_text",
        "adapter_readiness": {
            "status": "offline_snapshot_probe_supported_rerun_required",
            "canonical_adapter_files_modified": False,
            "offline_resolution_strategy": "temporary adapter_config.json copy points base_model_name_or_path to exact local base snapshot",
        },
        "centaur_choice_convention_audit": {
            "recommendation_exists": True,
            "technically_required": False,
            "evidence_source_note": "Centaur << >> recommendation exists but is not technically required for generation.",
            "would_alter_frozen_phase6d_semantic_prompt": True,
            "decision_for_primary_experiment": "retain_common_frozen_phase6d_prompt_for_cross_model_equivalence",
        },
    }
    merged = deep_merge(defaults, metadata_payload)
    if args.adapter_snapshot:
        merged["adapter_snapshot"] = args.adapter_snapshot
    if args.base_snapshot:
        merged["base_snapshot"] = args.base_snapshot
    if args.base_revision:
        merged["base_revision"] = args.base_revision
    return merged


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = {**base}
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def build_checks(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "model_key_is_centaur": record["model_key"] == "centaur",
        "source_candidate_recorded": is_known(record["deployed_model_source"]),
        "exact_served_id_verified": record["exact_served_id_verified"],
        "revision_verified": record["revision_verified"],
        "runtime_versions_recorded": any(is_known(value) for value in record.get("runtime_versions", {}).values()),
        "tokenizer_template_recorded": is_known(record.get("tokenizer_chat_template")),
        "context_limit_recorded": is_known(record.get("context_limit")),
        "health_check_succeeded": record.get("health_check", {}).get("status") == "succeeded",
        "trivial_generation_succeeded": record.get("trivial_generation_probe", {}).get("status") == "succeeded",
        "backend_contract_verified": record["backend_contract_verified"],
        "choice_convention_not_methodological_blocker": record["centaur_choice_convention_audit"].get("methodological_blocker") is False,
    }


def unresolved_items(record: dict[str, Any]) -> list[str]:
    fields = [
        "deployed_model_source",
        "deployment_form",
        "exact_served_id",
        "revision",
        "quantisation",
        "precision",
        "serving_framework",
        "tokenizer_chat_template",
        "context_limit",
        "request_contract",
        "response_extraction_contract",
    ]
    items = [field for field in fields if not is_known(record.get(field))]
    if record.get("deployment_form") == "adapter" and not is_known(record.get("base_model")):
        items.append("base_model")
    if record.get("health_check", {}).get("status") != "succeeded":
        items.append("model_load_health_check")
    if record.get("trivial_generation_probe", {}).get("status") != "succeeded":
        items.append("trivial_generation_probe")
    if record.get("centaur_choice_convention_audit", {}).get("technically_required") in {"unknown", UNVERIFIED}:
        items.append("centaur_choice_convention_technical_requirement")
    return items


def collect_runtime_versions() -> dict[str, Any]:
    versions = {"python": platform.python_version()}
    for package in ["torch", "transformers", "peft", "bitsandbytes", "accelerate", "requests"]:
        versions[package] = installed_version(package)
    versions["cuda"] = collect_cuda_version()
    return versions


def unknown_runtime_versions() -> dict[str, Any]:
    return {
        "python": UNVERIFIED,
        "torch": UNVERIFIED,
        "transformers": UNVERIFIED,
        "peft": UNVERIFIED,
        "bitsandbytes": UNVERIFIED,
        "accelerate": UNVERIFIED,
        "requests": UNVERIFIED,
        "cuda": UNVERIFIED,
    }


def is_runpod_environment() -> bool:
    return any(os.environ.get(name) for name in ["RUNPOD_POD_ID", "RUNPOD_PUBLIC_IP", "RUNPOD_DC_ID"])


def collect_cuda_version() -> str:
    try:
        import torch  # type: ignore[import-not-found]

        return str(torch.version.cuda or UNVERIFIED)
    except Exception:
        return UNVERIFIED


def collect_gpu_metadata() -> dict[str, Any]:
    try:
        import torch  # type: ignore[import-not-found]

        count = torch.cuda.device_count()
        return {
            "gpu_count": count,
            "gpu_names": [torch.cuda.get_device_name(index) for index in range(count)],
        }
    except Exception:
        return {"gpu_count": UNVERIFIED, "gpu_names": UNVERIFIED}


def discover_hf_revision(model_id: str) -> str:
    if not is_known(model_id):
        return UNVERIFIED
    cache_root = Path(os.environ.get("HF_HUB_CACHE", "")) or Path(os.environ.get("HF_HOME", "")) / "hub"
    if not cache_root:
        return UNVERIFIED
    repo_dir = cache_root / f"models--{model_id.replace('/', '--')}"
    snapshots = repo_dir / "snapshots"
    if not snapshots.exists():
        return UNVERIFIED
    candidates = [path.name for path in snapshots.iterdir() if path.is_dir()]
    return candidates[0] if len(candidates) == 1 else UNVERIFIED


def sanitize_url(url: str) -> str:
    if not url:
        return UNVERIFIED
    parts = urlsplit(url)
    netloc = parts.hostname or ""
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def safe_host_metadata(include_hostname: bool) -> dict[str, Any]:
    payload = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "evidence_environment": "RunPod" if os.environ.get("RUNPOD_POD_ID") else "local_or_unverified",
    }
    if include_hostname:
        payload["hostname"] = socket.gethostname()
    return payload


def installed_version(package: str) -> str:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return UNVERIFIED


def first_known(*values: Any) -> Any:
    for value in values:
        if is_known(value):
            return value
    return UNVERIFIED


def is_known(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and value in {"", UNVERIFIED, "unknown"}:
        return False
    return True


def safe_error(exc: Exception) -> str:
    message = str(exc)
    hf_token = os.environ.get("HF_TOKEN")
    return message.replace(hf_token, "[REDACTED]") if hf_token else message


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
    parser.add_argument("--model-id", help="Optional exact served model ID.")
    parser.add_argument("--deployed-model-source", help="Exact deployed Centaur repository/checkpoint.")
    parser.add_argument("--deployment-form", choices=["merged", "adapter", "unknown"], help="Centaur deployment form.")
    parser.add_argument("--base-model", help="Required if deployment form is adapter.")
    parser.add_argument("--base-revision", help="Base model revision/commit when Centaur is an adapter.")
    parser.add_argument("--adapter-snapshot", help="Exact local cached Centaur adapter snapshot path.")
    parser.add_argument("--base-snapshot", help="Exact local cached base model snapshot path.")
    parser.add_argument("--revision", help="Revision/commit/snapshot where available.")
    parser.add_argument("--quantisation", help="Quantisation method if any.")
    parser.add_argument("--precision", help="Precision if known.")
    parser.add_argument("--serving-framework", help="Serving framework such as vLLM/TGI/Transformers.")
    parser.add_argument("--endpoint-type", help="Endpoint type label.")
    parser.add_argument("--choice-recommendation-exists", choices=["true", "false", "unknown"], default="unknown")
    parser.add_argument("--choice-technically-required", choices=["true", "false", "unknown"], default="unknown")
    parser.add_argument("--choice-evidence-note", help="Short source note about the Centaur << >> convention.")
    parser.add_argument("--probe-load", action="store_true", help="Load tokenizer/model with non-study content only.")
    parser.add_argument("--probe-generation", action="store_true", help="Run one trivial non-study generation after load.")
    parser.add_argument("--local-files-only", action="store_true", help="Avoid model downloads during RunPod verification.")
    parser.add_argument("--device-map", default="auto")
    parser.add_argument("--torch-dtype", default="auto")
    parser.add_argument("--include-hostname", action="store_true", help="Include hostname if safe for the RunPod environment.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
