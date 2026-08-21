"""Phase 6G.5 final LLM prediction merge, QC, and freeze."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_experiments.inference.records import canonical_json, portable_artifact_path, sha256_file, write_json_atomic, write_jsonl


SCHEMA_VERSION = "phase6g5_final_llm_prediction_package_v1"
OUTPUT_DIR = Path("llm-experiments/outputs/final/model-predictions")
RENDERED_PROMPTS_DIR = Path("llm-experiments/outputs/final/rendered-prompts")
PROMPT_HASH_MANIFEST = RENDERED_PROMPTS_DIR / "prompt_hash_manifest.json"
PHASE6G3_FREEZE_MANIFEST = RENDERED_PROMPTS_DIR / "prompt_freeze_manifest.json"
PHASE6G3_REQUEST_MANIFEST = RENDERED_PROMPTS_DIR / "request_manifest.json"

EXPECTED_MODELS = ("gpt", "claude_sonnet", "llama_3_1_70b_instruct", "centaur")
EXPECTED_MODEL_COUNT = 396
EXPECTED_CONDITION_COUNTS = {"non_history": 198, "personalised_history": 198}
MIXES = ("A", "B", "C", "D", "E")
PROBABILITY_TOLERANCE = 1e-6


FINAL_SOURCES: dict[str, dict[str, Any]] = {
    "gpt": {
        "experiment_model_label": "GPT-5.5",
        "exact_model_identifier": "gpt-5.5",
        "deployment_revision": "gpt-5.5-2026-04-23",
        "prediction_file": Path("llm-experiments/outputs/final/model-predictions/source/gpt-5-5/predictions.jsonl"),
        "summary_file": Path("llm-experiments/outputs/final/model-predictions/source/gpt-5-5/execution_summary.json"),
        "source_run_ids": ["phase6g4a_gpt_corrected_run_03", "phase6g4a_gpt_recovery_run_04"],
        "recovery_or_canonicalization": "run03_valid_predictions_plus_run04_recovery_merge",
        "ratings_supported": True,
        "source_status": "final_authoritative_if_qc_valid",
    },
    "claude_sonnet": {
        "experiment_model_label": "Claude Sonnet 5",
        "exact_model_identifier": "claude-sonnet-5",
        "deployment_revision": "claude-sonnet-5",
        "prediction_file": Path("llm-experiments/outputs/final/model-predictions/source/claude-sonnet-5/predictions.jsonl"),
        "summary_file": Path("llm-experiments/outputs/final/model-predictions/source/claude-sonnet-5/execution_summary.json"),
        "source_run_ids": ["phase6g4b_claude_production_run_01"],
        "recovery_or_canonicalization": "offline_revalidation_preserved_primary_and_repair_provenance",
        "ratings_supported": True,
        "source_status": "final_authoritative",
    },
    "llama_3_1_70b_instruct": {
        "experiment_model_label": "Llama 3.1 70B Instruct",
        "exact_model_identifier": "meta-llama/Llama-3.1-70B-Instruct",
        "deployment_revision": "1605565b47bb9346c5515c34102e054115b4f98b",
        "prediction_file": Path("llm-experiments/outputs/final/model-predictions/source/llama-3-1-70b-instruct/predictions.jsonl"),
        "summary_file": Path("llm-experiments/outputs/final/model-predictions/source/llama-3-1-70b-instruct/execution_summary.json"),
        "source_run_ids": ["phase6g4c_llama_backend_failed_recovery_run_02", "phase6g4c_llama_resume_after_recovery_run_03"],
        "recovery_or_canonicalization": "canonical_merge_from_recovery_run02_and_resume_run03",
        "ratings_supported": True,
        "source_status": "final_authoritative",
    },
    "centaur": {
        "experiment_model_label": "Centaur",
        "exact_model_identifier": "marcelbinz/Llama-3.1-Centaur-70B-adapter",
        "deployment_revision": "159600db8be99dc183c289923148dfd96cbd8e07",
        "base_model": "unsloth/Meta-Llama-3.1-70B-bnb-4bit",
        "base_revision": "a009b8db2439814febe725486a5ed388f12a8744",
        "prediction_file": Path("llm-experiments/outputs/final/model-predictions/source/centaur/predictions.jsonl"),
        "summary_file": Path("llm-experiments/outputs/final/model-predictions/source/centaur/execution_summary.json"),
        "source_run_ids": ["phase6g4d_centaur_native_run_02"],
        "recovery_or_canonicalization": "native_candidate_likelihood_run02_supersedes_generic_json_run01",
        "ratings_supported": False,
        "source_status": "final_authoritative",
    },
}

GPT_TARGETED_RUN05_SOURCE = {
    "experiment_model_label": "GPT-5.5",
    "exact_model_identifier": "gpt-5.5",
    "deployment_revision": "gpt-5.5-2026-04-23",
    "prediction_file": Path("llm-experiments/outputs/final/model-predictions/source/gpt-5-5/predictions.jsonl"),
    "summary_file": Path("llm-experiments/outputs/final/model-predictions/source/gpt-5-5/execution_summary.json"),
    "source_run_ids": ["phase6g4a_gpt_recovery_run_04", "phase6g4a_gpt_targeted_recovery_run_05"],
    "recovery_or_canonicalization": "run04_final_predictions_plus_run05_single_slot_targeted_recovery",
    "ratings_supported": True,
    "source_status": "final_authoritative_after_targeted_run05",
}


def build_phase6g5_final_predictions(repo_root: Path, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    out = repo_root / output_dir
    out.mkdir(parents=True, exist_ok=True)
    prompt_manifest = load_json(repo_root / PROMPT_HASH_MANIFEST)
    request_manifest = load_json(repo_root / PHASE6G3_REQUEST_MANIFEST)
    prompt_hashes = {row["rendered_prompt_id"]: row["message_payload_sha256"] for row in prompt_manifest["records"]}
    expected_keys = set(prompt_hashes)
    rows_by_model: dict[str, list[dict[str, Any]]] = {}
    inventory_sources: dict[str, dict[str, Any]] = {}
    qc_errors: list[dict[str, Any]] = []

    final_sources = resolve_final_sources(repo_root)
    for model_key, source in final_sources.items():
        prediction_path = repo_root / source["prediction_file"]
        summary_path = repo_root / source["summary_file"]
        source_rows = read_jsonl(prediction_path)
        normalized_rows: list[dict[str, Any]] = []
        for row in source_rows:
            normalized, errors = normalize_prediction_row(model_key, row, source, prompt_hashes)
            normalized_rows.append(normalized)
            qc_errors.extend(errors)
        rows_by_model[model_key] = sorted(normalized_rows, key=lambda item: item["canonical_request_key"])
        inventory_sources[model_key] = inventory_record(repo_root, model_key, source, source_rows, summary_path)

        missing = sorted(expected_keys - {row["canonical_request_key"] for row in normalized_rows})
        extra = sorted({row["canonical_request_key"] for row in normalized_rows} - expected_keys)
        if missing:
            qc_errors.append({"check": "model_request_coverage", "model_key": model_key, "error": "missing_canonical_request_keys", "count": len(missing), "examples": missing[:5]})
        if extra:
            qc_errors.append({"check": "model_request_coverage", "model_key": model_key, "error": "unexpected_canonical_request_keys", "count": len(extra), "examples": extra[:5]})

    merged_rows = [row for model_key in EXPECTED_MODELS for row in rows_by_model.get(model_key, [])]
    qc_summary = run_cross_model_qc(merged_rows, rows_by_model, expected_keys, prompt_hashes, qc_errors)
    qc_summary["prompt_hash_manifest_sha256"] = sha256_file(repo_root / PROMPT_HASH_MANIFEST)
    capability_matrix = build_capability_matrix()
    inventory = build_inventory(inventory_sources, qc_summary)

    prediction_path = out / "llm_heldout_predictions.jsonl"
    csv_path = out / "llm_heldout_predictions.csv"
    capability_path = out / "capability_matrix.json"
    inventory_path = out / "prediction_inventory.json"
    qc_json_path = out / "prediction_qc_summary.json"
    manifest_path = out / "prediction_freeze_manifest.json"
    report_path = out / "prediction_qc_report.md"

    write_jsonl(prediction_path, merged_rows)
    write_predictions_csv(csv_path, merged_rows)
    write_json_atomic(capability_path, capability_matrix)
    write_json_atomic(inventory_path, inventory)
    write_json_atomic(qc_json_path, qc_summary)

    manifest = build_freeze_manifest(
        repo_root=repo_root,
        output_dir=output_dir,
        prediction_path=prediction_path,
        csv_path=csv_path,
        capability_path=capability_path,
        inventory_path=inventory_path,
        qc_json_path=qc_json_path,
        qc_summary=qc_summary,
        request_manifest=request_manifest,
    )
    write_json_atomic(manifest_path, manifest)
    write_report(report_path, inventory, qc_summary, manifest)
    return {
        "inventory": inventory,
        "qc_summary": qc_summary,
        "freeze_manifest": manifest,
        "paths": {
            "inventory": portable_artifact_path(inventory_path),
            "predictions_jsonl": portable_artifact_path(prediction_path),
            "predictions_csv": portable_artifact_path(csv_path),
            "capability_matrix": portable_artifact_path(capability_path),
            "freeze_manifest": portable_artifact_path(manifest_path),
            "qc_report": portable_artifact_path(report_path),
            "qc_summary": portable_artifact_path(qc_json_path),
        },
    }


def normalize_prediction_row(model_key: str, row: dict[str, Any], source: dict[str, Any], prompt_hashes: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    canonical_key = row.get("rendered_prompt_id") or canonical_key_from_row(row)
    parsed = None if model_key == "centaur" else parse_response_payload(row)
    if model_key != "centaur" and parsed is None:
        errors.append({"check": "prediction_payload_parse", "model_key": model_key, "canonical_request_key": canonical_key, "error": "missing_or_invalid_json_response", "final_status": row.get("final_status")})

    predicted_preferred = row.get("predicted_preferred_mix") if model_key == "centaur" else (parsed or {}).get("predicted_preferred_mix")
    predicted_ranking = row.get("predicted_ranking") if model_key == "centaur" else (parsed or {}).get("predicted_ranking")
    predicted_ratings = None if model_key == "centaur" else (parsed or {}).get("predicted_ratings")
    ratings_supported = bool(source["ratings_supported"])
    prompt_hash = row.get("prompt_hash")
    expected_hash = prompt_hashes.get(canonical_key)

    normalized = {
        "schema_version": "phase6g5_final_llm_prediction_row_v1",
        "model_key": model_key,
        "experiment_model_label": source["experiment_model_label"],
        "exact_model_identifier": source["exact_model_identifier"],
        "deployment_revision": source["deployment_revision"],
        "request_id": row.get("request_id"),
        "canonical_request_key": canonical_key,
        "prediction_example_id": row.get("prediction_example_id"),
        "rendered_prompt_id": row.get("rendered_prompt_id"),
        "prompt_hash": prompt_hash,
        "condition": row.get("condition"),
        "source_run_id": row.get("run_id") or row.get("canonical_selected_run_id"),
        "source_prediction_id": row.get("prediction_id"),
        "source_provenance": provenance_for_row(model_key, row),
        "source_final_status": row.get("final_status") or row.get("native_status"),
        "source_response_schema_valid": row.get("response_schema_valid") if model_key != "centaur" else None,
        "predicted_preferred_mix": predicted_preferred,
        "predicted_ranking": predicted_ranking,
        "predicted_ratings": predicted_ratings,
        "predicted_ratings_supported": ratings_supported,
        "centaur_candidate_log_likelihoods": row.get("candidate_log_likelihoods") if model_key == "centaur" else None,
        "centaur_candidate_probabilities": row.get("candidate_probabilities") if model_key == "centaur" else None,
        "centaur_scoring_definition": row.get("scoring_definition") if model_key == "centaur" else None,
        "centaur_native_interface": row.get("native_interface") if model_key == "centaur" else None,
        "ground_truth_dependency": bool(row.get("ground_truth_dependency") or row.get("canonical_ground_truth_dependency") or False),
    }
    errors.extend(validate_normalized_prediction(normalized, expected_hash))
    return normalized, errors


def validate_normalized_prediction(row: dict[str, Any], expected_hash: str | None) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    model_key = row["model_key"]
    key = row["canonical_request_key"]
    if expected_hash is None or row["prompt_hash"] != expected_hash:
        errors.append({"check": "prompt_hash_integrity", "model_key": model_key, "canonical_request_key": key, "error": "prompt_hash_mismatch"})
    if row["condition"] not in EXPECTED_CONDITION_COUNTS:
        errors.append({"check": "condition_validity", "model_key": model_key, "canonical_request_key": key, "error": "unexpected_condition"})
    if row["ground_truth_dependency"]:
        errors.append({"check": "ground_truth_isolation", "model_key": model_key, "canonical_request_key": key, "error": "ground_truth_dependency_true"})
    preferred = row["predicted_preferred_mix"]
    ranking = row["predicted_ranking"]
    if preferred not in MIXES:
        errors.append({"check": "preferred_mix_validity", "model_key": model_key, "canonical_request_key": key, "error": "invalid_preferred_mix", "value": preferred})
    if not isinstance(ranking, list) or sorted(ranking) != list(MIXES):
        errors.append({"check": "ranking_validity", "model_key": model_key, "canonical_request_key": key, "error": "ranking_not_a_to_e_permutation", "value": ranking})
    if model_key == "centaur":
        if row["predicted_ratings_supported"] is not False or row["predicted_ratings"] is not None:
            errors.append({"check": "centaur_ratings_policy", "model_key": model_key, "canonical_request_key": key, "error": "centaur_ratings_must_be_null_unsupported"})
        errors.extend(validate_centaur_native_fields(row))
    else:
        ratings = row["predicted_ratings"]
        if row["predicted_ratings_supported"] is not True:
            errors.append({"check": "rating_capability", "model_key": model_key, "canonical_request_key": key, "error": "ratings_should_be_supported"})
        if not isinstance(ratings, dict) or sorted(ratings) != list(MIXES):
            errors.append({"check": "rating_validity", "model_key": model_key, "canonical_request_key": key, "error": "ratings_not_complete_a_to_e", "value": ratings})
        else:
            for mix, value in ratings.items():
                if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 100:
                    errors.append({"check": "rating_validity", "model_key": model_key, "canonical_request_key": key, "error": "rating_out_of_range", "mix": mix, "value": value})
        if row["source_final_status"] not in {"valid_primary", "valid_after_repair"} or row["source_response_schema_valid"] is not True:
            errors.append({"check": "source_terminal_status", "model_key": model_key, "canonical_request_key": key, "error": "source_prediction_not_valid", "final_status": row["source_final_status"]})
    return errors


def validate_centaur_native_fields(row: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    key = row["canonical_request_key"]
    likelihoods = row["centaur_candidate_log_likelihoods"]
    probabilities = row["centaur_candidate_probabilities"]
    if row["source_final_status"] != "valid_native_likelihood_prediction":
        errors.append({"check": "centaur_native_status", "model_key": "centaur", "canonical_request_key": key, "error": "invalid_native_status", "status": row["source_final_status"]})
    for field_name, values in [("candidate_log_likelihoods", likelihoods), ("candidate_probabilities", probabilities)]:
        if not isinstance(values, dict) or sorted(values) != list(MIXES):
            errors.append({"check": "centaur_native_fields", "model_key": "centaur", "canonical_request_key": key, "error": f"{field_name}_not_complete_a_to_e"})
        elif not all(isinstance(value, (int, float)) and math.isfinite(value) for value in values.values()):
            errors.append({"check": "centaur_native_fields", "model_key": "centaur", "canonical_request_key": key, "error": f"{field_name}_contains_non_finite"})
    if isinstance(probabilities, dict) and sorted(probabilities) == list(MIXES):
        total = sum(probabilities.values())
        if abs(total - 1.0) > PROBABILITY_TOLERANCE:
            errors.append({"check": "centaur_probability_normalization", "model_key": "centaur", "canonical_request_key": key, "error": "probabilities_do_not_sum_to_one", "sum": total})
    return errors


def run_cross_model_qc(
    merged_rows: list[dict[str, Any]],
    rows_by_model: dict[str, list[dict[str, Any]]],
    expected_keys: set[str],
    prompt_hashes: dict[str, str],
    row_errors: list[dict[str, Any]],
) -> dict[str, Any]:
    errors = list(row_errors)
    model_counts = {model: len(rows_by_model.get(model, [])) for model in EXPECTED_MODELS}
    condition_counts = {model: dict(Counter(row["condition"] for row in rows_by_model.get(model, []))) for model in EXPECTED_MODELS}
    duplicate_pairs = duplicate_model_keys(merged_rows)
    if len(merged_rows) != EXPECTED_MODEL_COUNT * len(EXPECTED_MODELS):
        errors.append({"check": "global_count", "error": "unexpected_total_rows", "expected": EXPECTED_MODEL_COUNT * len(EXPECTED_MODELS), "actual": len(merged_rows)})
    for model, count in model_counts.items():
        if count != EXPECTED_MODEL_COUNT:
            errors.append({"check": "per_model_count", "model_key": model, "error": "unexpected_model_count", "expected": EXPECTED_MODEL_COUNT, "actual": count})
        if condition_counts[model] != EXPECTED_CONDITION_COUNTS:
            errors.append({"check": "condition_balance", "model_key": model, "error": "unexpected_condition_counts", "expected": EXPECTED_CONDITION_COUNTS, "actual": condition_counts[model]})
    if duplicate_pairs:
        errors.append({"check": "duplicate_model_canonical_request_key", "error": "duplicates_found", "count": len(duplicate_pairs), "examples": duplicate_pairs[:5]})
    request_sets = {model: {row["canonical_request_key"] for row in rows_by_model.get(model, [])} for model in EXPECTED_MODELS}
    request_alignment = all(keys == expected_keys for keys in request_sets.values())
    if not request_alignment:
        errors.append({"check": "cross_model_request_alignment", "error": "model_request_sets_not_identical"})
    source_traceability_failures = [
        {"model_key": row["model_key"], "canonical_request_key": row["canonical_request_key"]}
        for row in merged_rows
        if not row.get("source_prediction_id") or not row.get("source_run_id")
    ]
    if source_traceability_failures:
        errors.append({"check": "source_traceability", "error": "missing_source_trace", "count": len(source_traceability_failures), "examples": source_traceability_failures[:5]})
    ground_truth_dependency = any(row.get("ground_truth_dependency") for row in merged_rows)
    if ground_truth_dependency:
        errors.append({"check": "ground_truth_isolation", "error": "row_ground_truth_dependency_detected"})
    return {
        "schema_version": "phase6g5_final_llm_qc_summary_v1",
        "canonical_request_key_rule": "rendered_prompt_id from the frozen Phase 6G.3 prompt hash manifest; model-prefixed request_id is retained only as model-specific provenance.",
        "expected_total_rows": EXPECTED_MODEL_COUNT * len(EXPECTED_MODELS),
        "actual_total_rows": len(merged_rows),
        "expected_model_count": EXPECTED_MODEL_COUNT,
        "model_counts": model_counts,
        "expected_condition_counts_per_model": EXPECTED_CONDITION_COUNTS,
        "condition_counts_by_model": condition_counts,
        "expected_canonical_request_count": len(expected_keys),
        "cross_model_request_alignment": request_alignment,
        "duplicate_model_canonical_request_key_count": len(duplicate_pairs),
        "duplicate_model_canonical_request_key_examples": duplicate_pairs[:10],
        "prompt_hash_manifest": portable_artifact_path(PROMPT_HASH_MANIFEST),
        "prompt_hash_manifest_sha256": None,
        "prompt_hash_mismatch_count": sum(1 for error in errors if error["check"] == "prompt_hash_integrity"),
        "source_traceability_failure_count": len(source_traceability_failures),
        "ground_truth_dependency": ground_truth_dependency,
        "hidden_ground_truth_loaded": False,
        "evaluation_metrics_computed": False,
        "row_qc_error_count": len(errors),
        "errors": errors,
        "FINAL_LLM_PREDICTIONS_MERGED": len(merged_rows) == EXPECTED_MODEL_COUNT * len(EXPECTED_MODELS),
        "FINAL_LLM_PREDICTIONS_QC_PASSED": len(errors) == 0,
        "GROUND_TRUTH_NOT_LOADED_FOR_PHASE6G5": not ground_truth_dependency,
    }


def build_inventory(sources: dict[str, dict[str, Any]], qc_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "phase6g5_final_llm_prediction_inventory_v1",
        "phase": "6G.5",
        "authoritative_sources": sources,
        "excluded_superseded_sources": [
            "superseded GPT failed, corrected, and recovery batches removed after final GPT-5.5 predictions were frozen",
            "superseded Llama backend-failed and resume batches removed after canonical final predictions were frozen",
            "superseded Centaur generic JSON run removed after native final predictions were frozen",
        ],
        "ground_truth_dependency": False,
        "evaluation_not_yet_performed": True,
        "qc_passed": qc_summary["FINAL_LLM_PREDICTIONS_QC_PASSED"],
    }


def inventory_record(repo_root: Path, model_key: str, source: dict[str, Any], rows: list[dict[str, Any]], summary_path: Path) -> dict[str, Any]:
    prediction_path = repo_root / source["prediction_file"]
    condition_counts = dict(Counter(row.get("condition") for row in rows))
    summary = load_json(summary_path) if (repo_root / summary_path).exists() else {}
    return {
        "model_key": model_key,
        "experiment_model_label": source["experiment_model_label"],
        "exact_model_identifier": source["exact_model_identifier"],
        "deployment_revision": source["deployment_revision"],
        "base_model": source.get("base_model"),
        "base_revision": source.get("base_revision"),
        "authoritative_prediction_file": portable_artifact_path(prediction_path),
        "authoritative_summary_file": portable_artifact_path(repo_root / summary_path),
        "source_run_ids": source["source_run_ids"],
        "prediction_count": len(rows),
        "condition_counts": condition_counts,
        "recovery_or_canonicalization": source["recovery_or_canonicalization"],
        "ratings_supported": source["ratings_supported"],
        "source_status": source["source_status"],
        "source_file_sha256": sha256_file(prediction_path),
        "summary_file_sha256": sha256_file(repo_root / summary_path) if (repo_root / summary_path).exists() else None,
        "source_summary_status_counts": summary.get("status_counts"),
        "source_summary_ground_truth_dependency": summary.get("ground_truth_dependency"),
    }


def build_capability_matrix() -> dict[str, Any]:
    return {
        "schema_version": "phase6g5_final_llm_capability_matrix_v1",
        "phase": "6G.5",
        "capabilities": {
            "gpt": {"experiment_model_label": "GPT-5.5", "winner": "supported", "ranking": "supported", "rating_0_100": "supported"},
            "claude_sonnet": {"experiment_model_label": "Claude Sonnet 5", "winner": "supported", "ranking": "supported", "rating_0_100": "supported"},
            "llama_3_1_70b_instruct": {"experiment_model_label": "Llama 3.1 70B Instruct", "winner": "supported", "ranking": "supported", "rating_0_100": "supported"},
            "centaur": {"experiment_model_label": "Centaur", "winner": "supported_native_likelihood", "ranking": "supported_native_likelihood", "rating_0_100": "unsupported"},
        },
        "evaluation_policy": {
            "winner_metrics": list(EXPECTED_MODELS),
            "ranking_metrics": list(EXPECTED_MODELS),
            "rating_error_metrics": ["gpt", "claude_sonnet", "llama_3_1_70b_instruct"],
            "centaur_rating_error_exclusion_reason": "Centaur native likelihood produces winner/ranking over A-E candidates; no frozen scientifically justified mapping to 0-100 ratings exists. Exclusion is methodological and not performance-based.",
            "ground_truth_consulted_for_capability_decision": False,
        },
    }


def build_freeze_manifest(
    repo_root: Path,
    output_dir: Path,
    prediction_path: Path,
    csv_path: Path,
    capability_path: Path,
    inventory_path: Path,
    qc_json_path: Path,
    qc_summary: dict[str, Any],
    request_manifest: dict[str, Any],
) -> dict[str, Any]:
    existing_path = repo_root / output_dir / "prediction_freeze_manifest.json"
    created_at = None
    if existing_path.exists():
        try:
            created_at = load_json(existing_path).get("created_at_utc")
        except json.JSONDecodeError:
            created_at = None
    created_at = created_at or datetime.now(timezone.utc).isoformat()
    qc_passed = qc_summary["FINAL_LLM_PREDICTIONS_QC_PASSED"]
    return {
        "schema_version": "phase6g5_final_llm_prediction_freeze_manifest_v1",
        "created_at_utc": created_at,
        "phase": "6G.5",
        "statement": "These prediction artifacts were frozen before joining held-out human outcomes or computing evaluation metrics.",
        "total_predictions": qc_summary["actual_total_rows"],
        "expected_total_predictions": qc_summary["expected_total_rows"],
        "predictions_per_model": qc_summary["model_counts"],
        "condition_counts_by_model": qc_summary["condition_counts_by_model"],
        "authoritative_source_files": {model: source["prediction_file"].as_posix() for model, source in resolve_final_sources(repo_root).items()},
        "source_hashes": {model: sha256_file(repo_root / source["prediction_file"]) for model, source in resolve_final_sources(repo_root).items()},
        "final_jsonl_hash": sha256_file(prediction_path),
        "final_csv_hash": sha256_file(csv_path),
        "capability_matrix_hash": sha256_file(capability_path),
        "inventory_hash": sha256_file(inventory_path),
        "qc_summary_hash": sha256_file(qc_json_path),
        "prompt_freeze_manifest": portable_artifact_path(repo_root / PHASE6G3_FREEZE_MANIFEST),
        "prompt_freeze_manifest_sha256": sha256_file(repo_root / PHASE6G3_FREEZE_MANIFEST),
        "prompt_hash_manifest": portable_artifact_path(repo_root / PROMPT_HASH_MANIFEST),
        "prompt_hash_manifest_sha256": sha256_file(repo_root / PROMPT_HASH_MANIFEST),
        "phase6g3_final_request_manifest": portable_artifact_path(repo_root / PHASE6G3_REQUEST_MANIFEST),
        "phase6g3_expected_request_count": request_manifest.get("request_count"),
        "ground_truth_dependency": False,
        "hidden_ground_truth_loaded": False,
        "evaluation_not_yet_performed": True,
        "prediction_content_frozen": qc_passed,
        "freeze_blockers": qc_summary["errors"],
        "gates": {
            "FINAL_LLM_PREDICTIONS_MERGED": qc_summary["FINAL_LLM_PREDICTIONS_MERGED"],
            "FINAL_LLM_PREDICTIONS_QC_PASSED": qc_passed,
            "FINAL_LLM_PREDICTIONS_FROZEN": qc_passed,
            "GROUND_TRUTH_NOT_LOADED_FOR_PHASE6G5": qc_summary["GROUND_TRUTH_NOT_LOADED_FOR_PHASE6G5"],
        },
    }


def write_predictions_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "model_key",
        "experiment_model_label",
        "exact_model_identifier",
        "deployment_revision",
        "canonical_request_key",
        "request_id",
        "prediction_example_id",
        "rendered_prompt_id",
        "prompt_hash",
        "condition",
        "source_run_id",
        "source_prediction_id",
        "source_provenance",
        "source_final_status",
        "predicted_preferred_mix",
        "predicted_ratings_supported",
        "predicted_ranking_json",
        "predicted_rank_1",
        "predicted_rank_2",
        "predicted_rank_3",
        "predicted_rank_4",
        "predicted_rank_5",
        "predicted_ratings_json",
        "predicted_rating_A",
        "predicted_rating_B",
        "predicted_rating_C",
        "predicted_rating_D",
        "predicted_rating_E",
        "centaur_loglik_A",
        "centaur_loglik_B",
        "centaur_loglik_C",
        "centaur_loglik_D",
        "centaur_loglik_E",
        "centaur_probability_A",
        "centaur_probability_B",
        "centaur_probability_C",
        "centaur_probability_D",
        "centaur_probability_E",
        "centaur_scoring_definition",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            ranking = row.get("predicted_ranking") if isinstance(row.get("predicted_ranking"), list) else []
            ratings = row.get("predicted_ratings") if isinstance(row.get("predicted_ratings"), dict) else {}
            likelihoods = row.get("centaur_candidate_log_likelihoods") if isinstance(row.get("centaur_candidate_log_likelihoods"), dict) else {}
            probabilities = row.get("centaur_candidate_probabilities") if isinstance(row.get("centaur_candidate_probabilities"), dict) else {}
            writer.writerow({
                "model_key": row["model_key"],
                "experiment_model_label": row["experiment_model_label"],
                "exact_model_identifier": row["exact_model_identifier"],
                "deployment_revision": row["deployment_revision"],
                "canonical_request_key": row["canonical_request_key"],
                "request_id": row["request_id"],
                "prediction_example_id": row["prediction_example_id"],
                "rendered_prompt_id": row["rendered_prompt_id"],
                "prompt_hash": row["prompt_hash"],
                "condition": row["condition"],
                "source_run_id": row["source_run_id"],
                "source_prediction_id": row["source_prediction_id"],
                "source_provenance": row["source_provenance"],
                "source_final_status": row["source_final_status"],
                "predicted_preferred_mix": row["predicted_preferred_mix"],
                "predicted_ratings_supported": row["predicted_ratings_supported"],
                "predicted_ranking_json": compact_json_or_empty(row.get("predicted_ranking")),
                **{f"predicted_rank_{index + 1}": ranking[index] if index < len(ranking) else None for index in range(5)},
                "predicted_ratings_json": compact_json_or_empty(row.get("predicted_ratings")),
                **{f"predicted_rating_{mix}": ratings.get(mix) for mix in MIXES},
                **{f"centaur_loglik_{mix}": likelihoods.get(mix) for mix in MIXES},
                **{f"centaur_probability_{mix}": probabilities.get(mix) for mix in MIXES},
                "centaur_scoring_definition": row.get("centaur_scoring_definition"),
            })


def resolve_final_sources(repo_root: Path) -> dict[str, dict[str, Any]]:
    sources = {model_key: dict(source) for model_key, source in FINAL_SOURCES.items()}
    run05_prediction_file = repo_root / GPT_TARGETED_RUN05_SOURCE["prediction_file"]
    run05_summary_file = repo_root / GPT_TARGETED_RUN05_SOURCE["summary_file"]
    if run05_prediction_file.exists() and run05_summary_file.exists():
        sources["gpt"] = dict(GPT_TARGETED_RUN05_SOURCE)
    return sources


def write_report(path: Path, inventory: dict[str, Any], qc_summary: dict[str, Any], manifest: dict[str, Any]) -> None:
    lines = [
        "# Phase 6G.5 Final LLM Prediction QC Report",
        "",
        "Phase 6G.5 constructs the ground-truth-free prediction package that will be evaluated in Phase 6H.",
        "",
        "## Authoritative final sources",
    ]
    for model_key in EXPECTED_MODELS:
        source = inventory["authoritative_sources"][model_key]
        lines.extend([
            f"- {source['experiment_model_label']} (`{model_key}`): `{source['authoritative_prediction_file']}`",
            f"  - rows: {source['prediction_count']}; conditions: {source['condition_counts']}; status: {source['source_status']}",
        ])
    lines.extend([
        "",
        "## QC summary",
        f"- Total merged rows: {qc_summary['actual_total_rows']} / {qc_summary['expected_total_rows']}",
        f"- Per-model rows: `{qc_summary['model_counts']}`",
        f"- Condition counts per model: `{qc_summary['condition_counts_by_model']}`",
        f"- Cross-model request alignment: {qc_summary['cross_model_request_alignment']}",
        f"- Duplicate model/request pairs: {qc_summary['duplicate_model_canonical_request_key_count']}",
        f"- Prompt hash mismatches: {qc_summary['prompt_hash_mismatch_count']}",
        f"- Ground truth loaded: {not qc_summary['GROUND_TRUTH_NOT_LOADED_FOR_PHASE6G5']}",
        f"- Evaluation metrics computed: {qc_summary['evaluation_metrics_computed']}",
        "",
        "## Capability matrix",
        "- Winner metrics: GPT-5.5, Claude Sonnet 5, Llama 3.1 70B Instruct, Centaur.",
        "- Ranking metrics: GPT-5.5, Claude Sonnet 5, Llama 3.1 70B Instruct, Centaur.",
        "- Rating-error metrics: GPT-5.5, Claude Sonnet 5, and Llama 3.1 70B Instruct only.",
        "- Centaur ratings are unsupported/null because native likelihood inference supplies A-E winner/ranking without a frozen 0-100 rating mapping.",
        "",
        "## Gates",
    ])
    for gate, value in manifest["gates"].items():
        lines.append(f"- `{gate}={str(value).lower()}`")
    if qc_summary["errors"]:
        lines.extend(["", "## Freeze blockers"])
        for error in qc_summary["errors"][:25]:
            lines.append(f"- `{error['check']}`: `{error.get('model_key', 'global')}` `{error.get('canonical_request_key', '')}` {error.get('error')}")
        if len(qc_summary["errors"]) > 25:
            lines.append(f"- ... {len(qc_summary['errors']) - 25} additional errors recorded in `final_llm_qc_summary.json`.")
    lines.extend([
        "",
        "No held-out human outcomes were loaded, joined, inspected, or scored during this package build.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_response_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    text = row.get("normalized_final_response_text") or row.get("raw_final_response_text")
    if not isinstance(text, str) or not text.strip():
        return None
    text = strip_json_fence(text.strip())
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def strip_json_fence(text: str) -> str:
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text


def duplicate_model_keys(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    duplicates = []
    for row in rows:
        key = (row["model_key"], row["canonical_request_key"])
        if key in seen:
            duplicates.append({"model_key": key[0], "canonical_request_key": key[1]})
        seen.add(key)
    return duplicates


def canonical_key_from_row(row: dict[str, Any]) -> str:
    prediction_example_id = row.get("prediction_example_id")
    condition = row.get("condition")
    if prediction_example_id and condition:
        return f"{prediction_example_id}__{condition}__phase6d_prompt_spec_v1"
    return row.get("request_id", "")


def provenance_for_row(model_key: str, row: dict[str, Any]) -> str:
    if model_key == "llama_3_1_70b_instruct":
        return row.get("canonical_source") or "llama_canonical"
    if model_key == "centaur":
        return "centaur_native_likelihood_run02"
    return row.get("final_status") or "production_prediction"


def compact_json_or_empty(value: Any) -> str | None:
    if value is None:
        return None
    return canonical_json(value)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def artifact_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
