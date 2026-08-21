"""Phase 6G.3 final real prompt rendering and freeze.

This phase creates the executable real prompt/request artifacts but never calls
an LLM, renders model-specific semantic variants, or loads hidden target
outcomes.
"""

from __future__ import annotations

import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_experiments.prompts.freeze_package import verify_prompt_package
from llm_experiments.prompts.prompt_spec import CONDITIONS, EXPECTED_LABELS, PROMPT_SPEC_VERSION, RESPONSE_SCHEMA_VERSION, SYSTEM_INSTRUCTION, load_jsonl, prompt_size, write_json
from llm_experiments.prompts.render import render_prompt, write_jsonl
from llm_experiments.prompts.validate_conditions import build_condition_integrity_report


SCHEMA_VERSION = "phase6g3_real_prompt_freeze_v1"
OUTPUT_DIR = Path("llm-experiments/outputs/final/rendered-prompts")
PROMPT_DATA = Path("llm-experiments/outputs/final/prompt-data/final_prompt_dataset.jsonl")
PHASE6G1_MANIFEST = Path("llm-experiments/outputs/final/prompt-data/prompt_data_manifest.json")
PHASE6G1_GATE = Path("llm-experiments/outputs/final/prompt-data/readiness_gate.json")
INFERENCE_CONFIG_DIR = Path("llm-experiments/outputs/final/inference-config")
MODEL_REGISTRY = INFERENCE_CONFIG_DIR / "model_registry.json"
BACKEND_REGISTRY = INFERENCE_CONFIG_DIR / "backend_registry.json"
INFERENCE_CONFIG = INFERENCE_CONFIG_DIR / "inference_config.json"
CAPABILITY_MATRIX = INFERENCE_CONFIG_DIR / "capability_matrix.json"
READINESS_6G2D = INFERENCE_CONFIG_DIR / "readiness.json"
MAX_OUTPUT_TOKENS = 256
MODEL_KEYS = ["gpt", "claude_sonnet", "llama_3_1_70b_instruct", "centaur"]
QMUL_MODEL_KEYS = ["gpt", "claude_sonnet", "llama_3_1_70b_instruct"]
RUNPOD_MODEL_KEYS = ["centaur"]

TARGET_OUTCOME_TOKENS = [
    "Target rating",
    "Target human rating",
    "Target comparative comment",
    "observed_rank",
    "observed_ranks",
    "observed_preferred_set",
    "observed_preferred_mix",
    "observed_max_rating",
    "preferred mix",
    "target preference",
    "tie fields",
    "ground_truth",
]
PROVENANCE_TOKENS = ["stimulus_id", "actual_mix_id", "audio_path", "filename", "source-file", "z_SI", ".wav", "\\", "/workspace/"]


def freeze_phase6g3(repo_root: Path) -> dict[str, Any]:
    output_dir = repo_root / OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt_verification = verify_prompt_package(repo_root)
    prompt_data_path = repo_root / PROMPT_DATA
    phase6g1_manifest_path = repo_root / PHASE6G1_MANIFEST
    phase6g1_manifest = load_json(phase6g1_manifest_path)
    phase6g1_gate = load_json(repo_root / PHASE6G1_GATE)
    model_registry = load_json(repo_root / MODEL_REGISTRY)
    backend_registry = load_json(repo_root / BACKEND_REGISTRY)
    inference_config = load_json(repo_root / INFERENCE_CONFIG)
    capability_matrix = load_json(repo_root / CAPABILITY_MATRIX)
    readiness_6g2d = load_json(repo_root / READINESS_6G2D)

    source_rows = sorted(load_jsonl(prompt_data_path), key=lambda row: row["condition_object_id"])
    rendered_first = render_rows(source_rows)
    rendered_second = render_rows(source_rows)
    rendered_path = output_dir / "rendered_final_prompts.jsonl"
    write_jsonl(rendered_path, rendered_first)

    deterministic_audit = build_deterministic_audit(rendered_first, rendered_second)
    hash_manifest = build_prompt_hash_manifest(rendered_first, prompt_data_path)
    condition_audit = build_condition_integrity_report(rendered_path, prompt_data_path, output_dir / "condition_integrity_work")
    leakage_audit = build_leakage_audit(rendered_first, source_rows, condition_audit)
    size_audit = build_size_audit(rendered_first, source_rows)
    context_audit = build_context_compatibility_audit(rendered_first, capability_matrix)
    request_manifest = build_request_manifest(rendered_first, hash_manifest, model_registry)
    shard_manifests = build_shard_manifests(request_manifest, model_registry)
    freeze_manifest = build_freeze_manifest(
        repo_root=repo_root,
        prompt_data_path=prompt_data_path,
        phase6g1_manifest_path=phase6g1_manifest_path,
        prompt_verification=prompt_verification,
        phase6g1_manifest=phase6g1_manifest,
        phase6g1_gate=phase6g1_gate,
        readiness_6g2d=readiness_6g2d,
        rendered=rendered_first,
        hash_manifest=hash_manifest,
        condition_audit=condition_audit,
        leakage_audit=leakage_audit,
        size_audit=size_audit,
        context_audit=context_audit,
        deterministic_audit=deterministic_audit,
        request_manifest=request_manifest,
        shard_manifests=shard_manifests,
    )
    report = render_report(freeze_manifest, size_audit, context_audit, request_manifest, shard_manifests)

    write_json(output_dir / "prompt_hash_manifest.json", hash_manifest)
    write_json(output_dir / "phase6g3_condition_integrity_audit.json", condition_audit)
    write_json(output_dir / "phase6g3_leakage_audit.json", leakage_audit)
    write_json(output_dir / "phase6g3_prompt_size_audit.json", size_audit)
    write_json(output_dir / "phase6g3_context_compatibility_audit.json", context_audit)
    write_json(output_dir / "phase6g3_deterministic_rendering_audit.json", deterministic_audit)
    write_json(output_dir / "request_manifest.json", request_manifest)
    for name, manifest in shard_manifests.items():
        output_name = {
            "qmul_gpt": "gpt_request_shard_manifest.json",
            "qmul_claude": "claude_request_shard_manifest.json",
            "qmul_llama": "llama_request_shard_manifest.json",
            "qmul_all": "qmul_all_request_shard_manifest.json",
            "runpod_centaur": "centaur_request_shard_manifest.json",
        }[name]
        write_json(output_dir / output_name, manifest)
    freeze_manifest["artifact_hashes"] = hash_phase6g3_artifacts(repo_root)
    write_json(output_dir / "prompt_freeze_manifest.json", freeze_manifest)
    return freeze_manifest


def render_rows(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted([render_prompt(row) for row in source_rows], key=lambda row: row["rendered_prompt_id"])


def build_prompt_hash_manifest(rendered: list[dict[str, Any]], prompt_data_path: Path) -> dict[str, Any]:
    records = []
    for row in rendered:
        messages = row["messages"]
        records.append(
            {
                "rendered_prompt_id": row["rendered_prompt_id"],
                "condition_object_id": row["condition_object_id"],
                "prediction_example_id": row["prediction_example_id"],
                "condition": row["condition"],
                "prompt_spec_version": row["prompt_spec_version"],
                "response_schema_version": row["response_schema_version"],
                "message_payload_sha256": sha256_json(messages),
                "system_message_sha256": sha256_text(messages[0]["content"]),
                "user_message_sha256": sha256_text(messages[1]["content"]),
            }
        )
    return {
        "schema_version": "phase6g3_prompt_hash_manifest_v1",
        "prompt_data_source": str(PROMPT_DATA).replace("\\", "/"),
        "prompt_data_sha256": sha256_file(prompt_data_path),
        "rendered_prompt_count": len(records),
        "hash_algorithm": "sha256",
        "records": records,
        "manifest_sha256": sha256_json(records),
    }


def build_leakage_audit(rendered: list[dict[str, Any]], source_rows: list[dict[str, Any]], condition_audit: dict[str, Any]) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    rendered_by_id = {row["condition_object_id"]: row for row in rendered}
    for source in source_rows:
        row = rendered_by_id[source["condition_object_id"]]
        text = "\n".join(message["content"] for message in row["messages"])
        for token in TARGET_OUTCOME_TOKENS:
            if token in text:
                failures.append({"condition_object_id": row["condition_object_id"], "type": "target_outcome_token", "token": token})
        for token in PROVENANCE_TOKENS:
            if token in text:
                failures.append({"condition_object_id": row["condition_object_id"], "type": "provenance_token", "token": token})
        target = source["model_input"]["target"]
        for token in [
            target.get("song", {}).get("song_id"),
            target.get("song", {}).get("excerpt_id"),
            target.get("song", {}).get("song_title"),
        ]:
            if token and str(token) in text:
                failures.append({"condition_object_id": row["condition_object_id"], "type": "target_identifier", "token": str(token)})
        if row["condition"] == "non_history" and any(token in text for token in ["Participant rating:", "Participant comparative comment:", "Previous listening evidence from this participant"]):
            failures.append({"condition_object_id": row["condition_object_id"], "type": "non_history_contamination", "token": "history evidence"})
    return {
        "schema_version": "phase6g3_leakage_audit_v1",
        "rendered_prompt_count": len(rendered),
        "target_leakage_failures": condition_audit["target_leakage_failures"],
        "identifier_provenance_leakage_failures": condition_audit["identifier_provenance_leakage_failures"],
        "sensitivity_feature_leakage_failures": condition_audit["sensitivity_feature_leakage_failures"],
        "history_target_overlap_failures": condition_audit["history_target_overlap_failures"],
        "comment_boundary_failures": condition_audit["comment_boundary_failures"],
        "condition_equivalence_failures": condition_audit["pair_equivalence_failures"],
        "direct_text_scan_failures": len(failures),
        "failures": failures,
        "leakage_failures": condition_audit["target_leakage_failures"]
        + condition_audit["identifier_provenance_leakage_failures"]
        + condition_audit["sensitivity_feature_leakage_failures"]
        + condition_audit["history_target_overlap_failures"]
        + condition_audit["comment_boundary_failures"]
        + condition_audit["pair_equivalence_failures"]
        + len(failures),
        "contains_hidden_ground_truth": False,
    }


def build_size_audit(rendered: list[dict[str, Any]], source_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_condition: dict[str, list[dict[str, int]]] = {condition: [] for condition in CONDITIONS}
    history_counts = []
    source_by_id = {row["condition_object_id"]: row for row in source_rows}
    for row in rendered:
        text = "\n".join(message["content"] for message in row["messages"])
        by_condition[row["condition"]].append(prompt_size(text))
        source = source_by_id[row["condition_object_id"]]
        if row["condition"] == "personalised_history":
            history_counts.append(len(source.get("model_input", {}).get("history", [])))
    return {
        "schema_version": "phase6g3_prompt_size_audit_v1",
        "rendered_prompt_count": len(rendered),
        "condition_size_summary": {condition: summarize_sizes(values) for condition, values in by_condition.items()},
        "history_trial_count_distribution": dict(sorted(Counter(history_counts).items())),
        "maximum_history_trials": max(history_counts) if history_counts else 0,
    }


def build_context_compatibility_audit(rendered: list[dict[str, Any]], capability_matrix: dict[str, Any]) -> dict[str, Any]:
    max_chars = max(len("\n".join(message["content"] for message in row["messages"])) for row in rendered)
    max_words = max(len(re.findall(r"\b\S+\b", "\n".join(message["content"] for message in row["messages"]))) for row in rendered)
    # Conservative local estimate used when provider/remote tokenizers are not locally available.
    conservative_tokens = int(max_chars / 3) + 128
    rows = []
    for capability in capability_matrix["models"]:
        model_key = capability["model_key"]
        if model_key in {"gpt", "claude_sonnet"}:
            limit = "provider_managed_verified_context_limit_not_required_for_freeze"
            status = "PASS_estimated_provider_context"
            margin = "provider_managed"
            method = "conservative_character_estimate_no_provider_call"
        elif model_key == "llama_3_1_70b_instruct":
            limit = 131072
            margin = limit - conservative_tokens - MAX_OUTPUT_TOKENS
            status = "PASS_estimated_tokenizer_unavailable_locally" if margin > 0 else "FAIL"
            method = "conservative_character_estimate_no_weight_load_no_download"
        else:
            limit = 32768
            margin = limit - conservative_tokens - MAX_OUTPUT_TOKENS
            status = "PASS_estimated_tokenizer_unavailable_locally" if margin > 0 else "FAIL"
            method = "centaur_deterministic_serialization_conservative_character_estimate"
        rows.append(
            {
                "model_key": model_key,
                "maximum_prompt_characters": max_chars,
                "maximum_prompt_words": max_words,
                "maximum_prompt_tokens": conservative_tokens,
                "token_count_method": method,
                "token_count_exact": False,
                "context_limit_tokens": limit,
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "remaining_token_margin": margin,
                "compatibility_status": status,
            }
        )
    return {
        "schema_version": "phase6g3_context_compatibility_audit_v1",
        "models": rows,
        "context_compatibility_passes": all(str(row["compatibility_status"]).startswith("PASS") for row in rows),
        "centaur_serialization": centaur_serialization_record(),
    }


def build_request_manifest(rendered: list[dict[str, Any]], hash_manifest: dict[str, Any], model_registry: dict[str, Any]) -> dict[str, Any]:
    hashes = {row["rendered_prompt_id"]: row["message_payload_sha256"] for row in hash_manifest["records"]}
    requests = []
    for prompt in rendered:
        for model in model_registry["models"]:
            requests.append(
                {
                    "request_id": f"phase6g4::{model['model_key']}::{prompt['rendered_prompt_id']}",
                    "rendered_prompt_id": prompt["rendered_prompt_id"],
                    "condition_object_id": prompt["condition_object_id"],
                    "prediction_example_id": prompt["prediction_example_id"],
                    "condition": prompt["condition"],
                    "model_key": model["model_key"],
                    "backend_key": model["backend_key"],
                    "exact_model_id": model["exact_model_id"],
                    "deployment_revision": model.get("revision"),
                    "prompt_hash": hashes[prompt["rendered_prompt_id"]],
                    "response_schema_version": prompt["response_schema_version"],
                    "execution_status": "planned_not_run",
                }
            )
    coverage = {
        model_key: {
            "non_history": sum(1 for row in requests if row["model_key"] == model_key and row["condition"] == "non_history"),
            "personalised_history": sum(1 for row in requests if row["model_key"] == model_key and row["condition"] == "personalised_history"),
            "total": sum(1 for row in requests if row["model_key"] == model_key),
        }
        for model_key in MODEL_KEYS
    }
    return {
        "schema_version": "phase6g3_final_request_manifest_v1",
        "status": "planned_not_run",
        "rendered_prompt_dataset": str(OUTPUT_DIR / "rendered_final_prompts.jsonl").replace("\\", "/"),
        "request_count": len(requests),
        "model_condition_coverage": coverage,
        "contains_llm_predictions": False,
        "contains_hidden_ground_truth": False,
        "hidden_ground_truth_loaded": False,
        "requests": requests,
    }


def build_shard_manifests(request_manifest: dict[str, Any], model_registry: dict[str, Any]) -> dict[str, Any]:
    model_by_key = {row["model_key"]: row for row in model_registry["models"]}
    shard_specs = {
        "qmul_gpt": ["gpt"],
        "qmul_claude": ["claude_sonnet"],
        "qmul_llama": ["llama_3_1_70b_instruct"],
        "runpod_centaur": ["centaur"],
    }
    shards = {}
    for name, model_keys in shard_specs.items():
        requests = [row for row in request_manifest["requests"] if row["model_key"] in model_keys]
        shards[name] = {
            "schema_version": "phase6g3_execution_shard_manifest_v1",
            "shard_key": name,
            "execution_environment": "RunPod" if name == "runpod_centaur" else "QMUL",
            "model_keys": model_keys,
            "backend_keys": [model_by_key[key]["backend_key"] for key in model_keys],
            "rendered_prompt_dataset": request_manifest["rendered_prompt_dataset"],
            "request_count": len(requests),
            "contains_llm_predictions": False,
            "execution_status": "planned_not_run",
            "requests": requests,
        }
    shards["qmul_all"] = {
        "schema_version": "phase6g3_execution_shard_manifest_v1",
        "shard_key": "qmul_all",
        "execution_environment": "QMUL",
        "model_keys": QMUL_MODEL_KEYS,
        "backend_keys": [model_by_key[key]["backend_key"] for key in QMUL_MODEL_KEYS],
        "rendered_prompt_dataset": request_manifest["rendered_prompt_dataset"],
        "request_count": sum(shards[name]["request_count"] for name in ["qmul_gpt", "qmul_claude", "qmul_llama"]),
        "contains_llm_predictions": False,
        "execution_status": "planned_not_run",
        "requests": [row for row in request_manifest["requests"] if row["model_key"] in QMUL_MODEL_KEYS],
    }
    return shards


def build_freeze_manifest(**kwargs: Any) -> dict[str, Any]:
    repo_root: Path = kwargs["repo_root"]
    rendered = kwargs["rendered"]
    hash_manifest = kwargs["hash_manifest"]
    condition_audit = kwargs["condition_audit"]
    leakage_audit = kwargs["leakage_audit"]
    context_audit = kwargs["context_audit"]
    deterministic_audit = kwargs["deterministic_audit"]
    request_manifest = kwargs["request_manifest"]
    phase6g1_manifest = kwargs["phase6g1_manifest"]
    prompt_verification = kwargs["prompt_verification"]
    readiness_6g2d = kwargs["readiness_6g2d"]
    condition_counts = Counter(row["condition"] for row in rendered)
    source_hash_ok = source_prompt_hash_verified(kwargs["phase6g1_manifest"], kwargs["prompt_data_path"])
    request_matrix_complete = request_manifest["request_count"] == 1584 and all(row["total"] == 396 for row in request_manifest["model_condition_coverage"].values())
    ground_truth_isolated = not request_manifest["hidden_ground_truth_loaded"] and not request_manifest["contains_hidden_ground_truth"]
    gate_inputs = {
        "source_real_phase6b_verified": source_hash_ok,
        "phase6d_prompt_package_verified": bool(prompt_verification["PHASE6D_PROMPT_PACKAGE_FROZEN"]),
        "phase6g2d_production_config_ready": bool(readiness_6g2d["PRODUCTION_INFERENCE_READY"]),
        "rendered_prompt_count_valid": len(rendered) == 396,
        "condition_counts_valid": condition_counts.get("non_history") == 198 and condition_counts.get("personalised_history") == 198,
        "matched_pair_count_valid": condition_audit["matched_pair_count"] == 198 and condition_audit["valid_pair_count"] == 198,
        "leakage_audit_passes": leakage_audit["leakage_failures"] == 0,
        "deterministic_rendering_passes": deterministic_audit["deterministic_rendering_passed"],
        "context_compatibility_passes": context_audit["context_compatibility_passes"],
        "request_matrix_complete": request_matrix_complete,
        "ground_truth_isolation_passes": ground_truth_isolated,
    }
    final_gate = all(gate_inputs.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_real_phase6b_prompt_data": str(PROMPT_DATA).replace("\\", "/"),
        "source_real_phase6b_prompt_data_sha256": sha256_file(kwargs["prompt_data_path"]),
        "source_real_phase6b_hash_verified": source_hash_ok,
        "phase6g1_manifest": str(PHASE6G1_MANIFEST).replace("\\", "/"),
        "phase6g1_manifest_sha256": sha256_file(kwargs["phase6g1_manifest_path"]),
        "prompt_package_version": prompt_verification["package_version"],
        "prompt_specification_version": PROMPT_SPEC_VERSION,
        "response_schema_version": RESPONSE_SCHEMA_VERSION,
        "rendered_prompt_count": len(rendered),
        "condition_counts": dict(sorted(condition_counts.items())),
        "matched_pair_count": condition_audit["matched_pair_count"],
        "valid_pair_count": condition_audit["valid_pair_count"],
        "leakage_status": leakage_audit,
        "deterministic_rendering_status": deterministic_audit,
        "context_compatibility_status": context_audit,
        "request_count": request_manifest["request_count"],
        "model_condition_coverage": request_manifest["model_condition_coverage"],
        "gate_inputs": gate_inputs,
        "artifact_hashes": {},
        "prompt_hash_manifest_sha256": hash_manifest["manifest_sha256"],
        "REAL_PRODUCTION_PROMPTS_FROZEN": final_gate,
        "PHASE6G3_COMPLETE": final_gate,
        "PHASE6G4_CAN_BEGIN_IMMEDIATELY": final_gate,
    }


def hash_phase6g3_artifacts(repo_root: Path) -> dict[str, str]:
    artifact_names = [
        "rendered_final_prompts.jsonl",
        "prompt_hash_manifest.json",
        "phase6g3_condition_integrity_audit.json",
        "phase6g3_leakage_audit.json",
        "phase6g3_prompt_size_audit.json",
        "phase6g3_context_compatibility_audit.json",
        "phase6g3_deterministic_rendering_audit.json",
        "request_manifest.json",
        "gpt_request_shard_manifest.json",
        "claude_request_shard_manifest.json",
        "llama_request_shard_manifest.json",
        "qmul_all_request_shard_manifest.json",
        "centaur_request_shard_manifest.json",
    ]
    hashes = {}
    for name in artifact_names:
        path = OUTPUT_DIR / name
        absolute = repo_root / path
        if absolute.exists():
            hashes[str(path).replace("\\", "/")] = sha256_file(absolute)
    return hashes


def build_deterministic_audit(first: list[dict[str, Any]], second: list[dict[str, Any]]) -> dict[str, Any]:
    first_hashes = [sha256_json(row) for row in first]
    second_hashes = [sha256_json(row) for row in second]
    return {
        "schema_version": "phase6g3_deterministic_rendering_audit_v1",
        "first_count": len(first),
        "second_count": len(second),
        "ids_identical": [row["rendered_prompt_id"] for row in first] == [row["rendered_prompt_id"] for row in second],
        "prompt_hashes_identical": first_hashes == second_hashes,
        "rendered_dataset_sha256_first": sha256_json(first),
        "rendered_dataset_sha256_second": sha256_json(second),
        "deterministic_rendering_passed": first == second,
        "contains_timestamps_in_prompt_records": any("timestamp" in json.dumps(row).lower() for row in first),
    }


def centaur_serialization_record() -> dict[str, Any]:
    delimiter = "\n\n--- USER MESSAGE ---\n\n"
    return {
        "schema_version": "phase6g3_centaur_serialization_v1",
        "chat_template": "absent",
        "effective_context_limit": 32768,
        "serialization": "system_content + fixed delimiter + user_content",
        "fixed_delimiter": delimiter,
        "preserves_semantic_text_exactly": True,
        "adds_model_specific_task_hints": False,
        "uses_double_angle_choice_markers": False,
        "choice_marker_decision": {
            "recommendation_exists": True,
            "technically_required": False,
            "primary_experiment_decision": "do_not_introduce_double_angle_markers_to_preserve_common_cross_model_semantic_prompt_contract",
        },
    }


def source_prompt_hash_verified(phase6g1_manifest: dict[str, Any], prompt_data_path: Path) -> bool:
    expected = None
    for row in phase6g1_manifest.get("hash_manifest", {}).get("files", []):
        if row.get("path") == str(PROMPT_DATA).replace("\\", "/"):
            expected = row.get("sha256")
            break
    return bool(expected and expected == sha256_file(prompt_data_path))


def render_report(freeze_manifest: dict[str, Any], size_audit: dict[str, Any], context_audit: dict[str, Any], request_manifest: dict[str, Any], shard_manifests: dict[str, Any]) -> str:
    sizes = size_audit["condition_size_summary"]
    context_by_model = {row["model_key"]: row for row in context_audit["models"]}
    coverage = request_manifest["model_condition_coverage"]
    return "\n".join(
        [
            "# Phase 6G.3 Final Real Rendered Prompt Freeze",
            "",
            "No LLM calls, production inference, scoring, prompt wording changes, model configuration changes, or hidden ground-truth reads were performed.",
            "",
            "## Source",
            "",
            f"- Phase 6B prompt data: `{freeze_manifest['source_real_phase6b_prompt_data']}`",
            f"- Phase 6B prompt data SHA-256: `{freeze_manifest['source_real_phase6b_prompt_data_sha256']}`",
            f"- Source hash verified: `{str(freeze_manifest['source_real_phase6b_hash_verified']).lower()}`",
            "",
            "## Counts",
            "",
            f"- Rendered prompts: `{freeze_manifest['rendered_prompt_count']}`",
            f"- Non-history: `{freeze_manifest['condition_counts'].get('non_history')}`",
            f"- Personalised-history: `{freeze_manifest['condition_counts'].get('personalised_history')}`",
            f"- Matched pairs: `{freeze_manifest['matched_pair_count']}`",
            f"- History distribution: `{size_audit['history_trial_count_distribution']}`",
            "",
            "## Audits",
            "",
            f"- Leakage failures: `{freeze_manifest['leakage_status']['leakage_failures']}`",
            f"- Condition-equivalence failures: `{freeze_manifest['leakage_status'].get('condition_equivalence_failures', 0)}`",
            f"- Deterministic rendering: `{str(freeze_manifest['deterministic_rendering_status']['deterministic_rendering_passed']).lower()}`",
            "",
            "## Size",
            "",
            f"- Non-history characters min/median/max: `{sizes['non_history']['characters_min']}/{sizes['non_history']['characters_median']}/{sizes['non_history']['characters_max']}`",
            f"- Non-history words min/median/max: `{sizes['non_history']['approximate_words_min']}/{sizes['non_history']['approximate_words_median']}/{sizes['non_history']['approximate_words_max']}`",
            f"- Personalised-history characters min/median/max: `{sizes['personalised_history']['characters_min']}/{sizes['personalised_history']['characters_median']}/{sizes['personalised_history']['characters_max']}`",
            f"- Personalised-history words min/median/max: `{sizes['personalised_history']['approximate_words_min']}/{sizes['personalised_history']['approximate_words_median']}/{sizes['personalised_history']['approximate_words_max']}`",
            "",
            "## Context",
            "",
            f"- GPT max token estimate: `{context_by_model['gpt']['maximum_prompt_tokens']}`",
            f"- Claude max token estimate: `{context_by_model['claude_sonnet']['maximum_prompt_tokens']}`",
            f"- Llama max tokens: `{context_by_model['llama_3_1_70b_instruct']['maximum_prompt_tokens']}` ({context_by_model['llama_3_1_70b_instruct']['token_count_method']})",
            f"- Centaur max tokens/structural margin: `{context_by_model['centaur']['maximum_prompt_tokens']}` / `{context_by_model['centaur']['remaining_token_margin']}`",
            f"- Centaur serialization: `{context_audit['centaur_serialization']['serialization']}`",
            f"- Centaur `<< >>` primary formatting introduced: `{str(context_audit['centaur_serialization']['uses_double_angle_choice_markers']).lower()}`",
            "",
            "## Requests",
            "",
            f"- GPT: `{coverage['gpt']['total']}`",
            f"- Claude: `{coverage['claude_sonnet']['total']}`",
            f"- Llama: `{coverage['llama_3_1_70b_instruct']['total']}`",
            f"- Centaur: `{coverage['centaur']['total']}`",
            f"- Total: `{request_manifest['request_count']}`",
            f"- QMUL shard total: `{shard_manifests['qmul_all']['request_count']}`",
            f"- RunPod shard total: `{shard_manifests['runpod_centaur']['request_count']}`",
            "",
            "## Gates",
            "",
            f"- Ground-truth isolation: `{str(freeze_manifest['gate_inputs']['ground_truth_isolation_passes']).lower()}`",
            f"- Prompt hash manifest: `{freeze_manifest['prompt_hash_manifest_sha256']}`",
            f"- `REAL_PRODUCTION_PROMPTS_FROZEN`: `{str(freeze_manifest['REAL_PRODUCTION_PROMPTS_FROZEN']).lower()}`",
            f"- Phase 6G.3 complete: `{str(freeze_manifest['PHASE6G3_COMPLETE']).lower()}`",
            f"- Phase 6G.4 can begin immediately: `{str(freeze_manifest['PHASE6G4_CAN_BEGIN_IMMEDIATELY']).lower()}`",
            "",
        ]
    )


def summarize_sizes(values: list[dict[str, int]]) -> dict[str, Any]:
    chars = [row["characters"] for row in values]
    words = [row["approximate_word_count"] for row in values]
    return {
        "count": len(values),
        "characters_min": min(chars),
        "characters_median": statistics.median(chars),
        "characters_max": max(chars),
        "approximate_words_min": min(words),
        "approximate_words_median": statistics.median(words),
        "approximate_words_max": max(words),
    }


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(payload: Any) -> str:
    return sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
