"""Phase 6F.1 synthetic end-to-end orchestration and alignment."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from llm_experiments.data.integration import READY_GATE_NAME, run_phase6b_synthetic_pipeline
from llm_experiments.inference.configuration import production_preflight
from llm_experiments.inference.failures import FAILURE_HANDLING_VERSION
from llm_experiments.inference.records import (
    PREDICTION_LOGGING_VERSION,
    read_jsonl,
    run_logged_synthetic_mock,
    sha256_file,
    sha256_json,
    write_json_atomic,
    write_jsonl,
)
from llm_experiments.prompts.freeze_package import PHASE6D_PROMPT_PACKAGE_FROZEN_GATE, PROMPT_PACKAGE_VERSION, verify_prompt_package
from llm_experiments.prompts.render import RENDERED_PROMPT_DATASET_VERSION, render_prompt_dataset
from llm_experiments.prompts.validate_conditions import build_condition_integrity_report


PHASE6F_RUN_VERSION = "phase6f_synthetic_e2e_v1"
DEFAULT_OUTPUT_DIR = Path("llm-experiments/outputs/synthetic/phase6f1_e2e")
DEFAULT_PHASE6B_DIR = Path("llm-experiments/outputs/synthetic/phase6b5")
DEFAULT_RENDERED_DIR = Path("llm-experiments/outputs/synthetic/phase6d2_rendered_prompts")
DEFAULT_CONDITION_DIR = Path("llm-experiments/outputs/synthetic/phase6d3_condition_validation")
DEFAULT_LLM_RUN_DIR = Path("llm-experiments/outputs/synthetic/phase6e3/phase6f1_synthetic_mock_llm_run")
DEFAULT_BASELINE_PREDICTIONS = Path("statistical-modeling/outputs/phase6c3_synthetic_smoke_consolidated/phase6f_evaluation_ready_baseline_predictions.csv")
DEFAULT_BASELINE_QC = Path("statistical-modeling/outputs/phase6c3_synthetic_smoke_consolidated/phase6c_baseline_output_qc_summary.json")
DEFAULT_BASELINE_CONFIG = Path("statistical-modeling/config/phase6c_baseline_models.json")
DEFAULT_RESPONSE_SCHEMA = Path("llm-experiments/schema/preference_prediction_response_v1.json")
MODEL_KEYS = ["gpt", "claude_sonnet", "llama_3_1_70b_instruct", "centaur"]
CONDITIONS = ["non_history", "personalised_history"]
PRIMARY_BASELINE_MODELS = ["categorical_design", "primary_acoustic"]
LABELS = ["A", "B", "C", "D", "E"]
PRIMARY_FEATURES = ["z_RMS", "z_CF", "z_SW"]
OUTCOME_TOKENS = [
    "observed_preferred_mix",
    "observed_preferred_set",
    "observed_rank",
    "observed_max_rating",
    "human_rating",
    "is_single_winner",
    "n_preferred_tied",
]


def run_phase6f_synthetic_pipeline(
    repo_root: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    rebuild: bool = True,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    output_dir = repo_path(repo_root, output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    phase6b_report = run_phase6b_synthetic_pipeline(repo_root, output_dir=DEFAULT_PHASE6B_DIR) if rebuild else load_json(repo_path(repo_root, DEFAULT_PHASE6B_DIR) / "phase6b_integration_audit.json")
    require(phase6b_report[READY_GATE_NAME]["ready"], "Phase 6B readiness gate failed.")

    phase6b_dir = repo_path(repo_root, DEFAULT_PHASE6B_DIR)
    prediction_examples_path = phase6b_dir / "final_prediction_examples.jsonl"
    prompt_data_path = phase6b_dir / "final_prompt_data_objects.jsonl"
    rendered_dir = repo_path(repo_root, DEFAULT_RENDERED_DIR)
    condition_dir = repo_path(repo_root, DEFAULT_CONDITION_DIR)
    response_schema_path = repo_path(repo_root, DEFAULT_RESPONSE_SCHEMA)

    render_audit = render_prompt_dataset(prompt_data_path, rendered_dir, response_schema_path)
    condition_audit = build_condition_integrity_report(
        rendered_dir / "rendered_prompts.jsonl",
        prompt_data_path,
        condition_dir,
        prediction_examples_path,
    )
    require(condition_audit["EXPERIMENTAL_CONDITION_INTEGRITY"], "Phase 6D condition-integrity gate failed.")
    prompt_preflight = verify_prompt_package(repo_root)
    require(prompt_preflight[PHASE6D_PROMPT_PACKAGE_FROZEN_GATE], "Phase 6D prompt package is not frozen.")

    llm_summary = run_logged_synthetic_mock(repo_root, run_id=DEFAULT_LLM_RUN_DIR.name, output_root=DEFAULT_LLM_RUN_DIR.parent)
    require(llm_summary["INFERENCE_RUN_COMPLETE"], "Phase 6E mock inference did not complete.")
    require(llm_summary["ALL_EXPECTED_PREDICTIONS_VALID"], "Phase 6E mock inference produced invalid predictions.")

    context = load_context(repo_root, phase6b_dir, rendered_dir, repo_path(repo_root, DEFAULT_LLM_RUN_DIR))
    baseline_rows = read_csv(repo_path(repo_root, DEFAULT_BASELINE_PREDICTIONS))
    baseline_qc = load_json(repo_path(repo_root, DEFAULT_BASELINE_QC))
    baseline_config = load_json(repo_path(repo_root, DEFAULT_BASELINE_CONFIG))

    mapping_audit = validate_mapping_and_leakage(context, baseline_rows)
    provenance_chain = validate_provenance_chain(context, baseline_rows)
    require(mapping_audit["target_leakage_free"], "Target leakage detected in inference-facing artifacts.")
    require(mapping_audit["ae_mapping_valid"], "A-E mapping validation failed.")
    require(mapping_audit["acoustic_mapping_valid"], "Acoustic mapping validation failed.")
    require(mapping_audit["history_selection_valid"], "History selection validation failed.")

    llm_eval_rows = build_llm_prediction_rows(context)
    baseline_eval_rows = build_baseline_prediction_rows(baseline_rows)
    ground_truth_rows = build_ground_truth_rows(context["examples"])
    alignment_rows = build_alignment_rows(context, llm_eval_rows, baseline_eval_rows, ground_truth_rows)
    alignment_audit = audit_alignment(alignment_rows, llm_eval_rows, baseline_eval_rows, ground_truth_rows, baseline_qc, baseline_config)

    write_csv(output_dir / "llm_predictions_for_evaluation.csv", llm_eval_rows)
    write_csv(output_dir / "baseline_predictions_for_evaluation.csv", baseline_eval_rows)
    write_csv(output_dir / "ground_truth_for_evaluation.csv", ground_truth_rows)
    write_jsonl(output_dir / "prediction_alignment_manifest.jsonl", alignment_rows)

    counts = structural_counts(context, baseline_eval_rows, ground_truth_rows, alignment_rows, llm_eval_rows)
    live_preflight = production_preflight(repo_root)
    hash_manifest = build_hash_manifest(repo_root, output_dir, phase6b_dir, rendered_dir)
    audit = {
        "schema_version": "phase6f1_end_to_end_audit_v1",
        "phase6f_run_version": PHASE6F_RUN_VERSION,
        "run_type": "synthetic_end_to_end",
        "phase6b_ready": phase6b_report[READY_GATE_NAME]["ready"],
        "prompt_package_verified": prompt_preflight[PHASE6D_PROMPT_PACKAGE_FROZEN_GATE],
        "experimental_condition_integrity": condition_audit["EXPERIMENTAL_CONDITION_INTEGRITY"],
        "target_leakage_free": mapping_audit["target_leakage_free"],
        "ae_mapping_valid": mapping_audit["ae_mapping_valid"],
        "acoustic_mapping_valid": mapping_audit["acoustic_mapping_valid"],
        "history_selection_valid": mapping_audit["history_selection_valid"],
        "provenance_chain_valid": provenance_chain["passed"],
        "mock_inference_complete": llm_summary["INFERENCE_RUN_COMPLETE"],
        "llm_prediction_schema_valid": llm_summary["ALL_EXPECTED_PREDICTIONS_VALID"],
        "baseline_alignment_valid": alignment_audit["baseline_alignment_valid"],
        "ground_truth_separated": mapping_audit["ground_truth_separated"],
        "evaluation_alignment_complete": alignment_audit["evaluation_alignment_complete"],
        "deterministic_rerun": None,
        "live_production_gates_resolved": bool(live_preflight.get("production_inference_allowed")),
        "phase6f_e2e_alignment_ready": False,
        "ground_truth_loaded_during_inference": False,
        "contains_metrics": False,
        "contains_scientific_plots": False,
        "counts": counts,
        "llm_summary": llm_summary,
        "phase6b_counts": phase6b_report["observed_structural_counts"],
        "phase6d_render_audit": render_audit,
        "phase6d_condition_audit": summarize_condition_audit(condition_audit),
        "phase6e_live_preflight": live_preflight,
        "baseline_qc": baseline_qc,
        "baseline_protocol_version": baseline_qc.get("protocol_version"),
        "mapping_audit": mapping_audit,
        "provenance_chain_audit": provenance_chain,
        "alignment_audit": alignment_audit,
        "hash_manifest": hash_manifest,
        "versions": version_manifest(baseline_qc),
    }
    audit["phase6f_e2e_alignment_ready"] = all(
        [
            audit["phase6b_ready"],
            audit["prompt_package_verified"],
            audit["experimental_condition_integrity"],
            audit["target_leakage_free"],
            audit["ae_mapping_valid"],
            audit["acoustic_mapping_valid"],
            audit["history_selection_valid"],
            audit["provenance_chain_valid"],
            audit["mock_inference_complete"],
            audit["llm_prediction_schema_valid"],
            audit["baseline_alignment_valid"],
            audit["ground_truth_separated"],
            audit["evaluation_alignment_complete"],
            not audit["ground_truth_loaded_during_inference"],
        ]
    )
    write_json_atomic(output_dir / "phase6f1_end_to_end_audit.json", audit)
    write_json_atomic(output_dir / "phase6f1_hash_manifest.json", hash_manifest)
    write_report(output_dir / "phase6f1_end_to_end_report.md", audit)
    return audit


def validate_phase6f_determinism(repo_root: Path, output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    first = run_phase6f_synthetic_pipeline(repo_root, output_dir, rebuild=True)
    first_hashes = scientific_output_hashes(repo_path(repo_root, output_dir))
    second = run_phase6f_synthetic_pipeline(repo_root, output_dir, rebuild=True)
    second_hashes = scientific_output_hashes(repo_path(repo_root, output_dir))
    deterministic = first_hashes == second_hashes and first["counts"] == second["counts"]
    audit = load_json(repo_path(repo_root, output_dir) / "phase6f1_end_to_end_audit.json")
    audit["deterministic_rerun"] = deterministic
    audit["determinism_hashes"] = {"first": first_hashes, "second": second_hashes}
    audit["phase6f_e2e_alignment_ready"] = bool(audit["phase6f_e2e_alignment_ready"] and deterministic)
    write_json_atomic(repo_path(repo_root, output_dir) / "phase6f1_end_to_end_audit.json", audit)
    write_report(repo_path(repo_root, output_dir) / "phase6f1_end_to_end_report.md", audit)
    return audit


def load_context(repo_root: Path, phase6b_dir: Path, rendered_dir: Path, llm_run_dir: Path) -> dict[str, Any]:
    examples = read_jsonl(phase6b_dir / "final_prediction_examples.jsonl")
    prompt_data = read_jsonl(phase6b_dir / "final_prompt_data_objects.jsonl")
    rendered = read_jsonl(rendered_dir / "rendered_prompts.jsonl")
    attempts = read_jsonl(llm_run_dir / "attempt_log.jsonl")
    predictions = read_jsonl(llm_run_dir / "predictions.jsonl")
    analysis_rows = read_csv(phase6b_dir / "final_analysis_ready_long.csv")
    trial_targets = read_csv(phase6b_dir / "final_trial_ground_truth_targets.csv")
    candidate_truth = read_csv(phase6b_dir / "final_candidate_ground_truth_enriched.csv")
    return {
        "repo_root": repo_root,
        "examples": examples,
        "prompt_data": prompt_data,
        "rendered": rendered,
        "attempts": attempts,
        "predictions": predictions,
        "analysis_rows": analysis_rows,
        "trial_targets": trial_targets,
        "candidate_truth": candidate_truth,
    }


def build_llm_prediction_rows(context: dict[str, Any]) -> list[dict[str, Any]]:
    prompt_meta = {row["prediction_example_id"]: row for row in context["examples"]}
    attempts_by_prediction = defaultdict(list)
    for attempt in context["attempts"]:
        attempts_by_prediction[attempt["prediction_record_id"]].append(attempt)
    rows = []
    for prediction in sorted(context["predictions"], key=lambda row: (row["prediction_example_id"], row["condition"], row["model_key"])):
        example = prompt_meta[prediction["prediction_example_id"]]
        first_attempt = sorted(attempts_by_prediction[prediction["prediction_record_id"]], key=lambda row: (row["attempt_number"], row["transport_attempt_number"]))[0]
        rows.append(
            {
                "prediction_record_id": prediction["prediction_record_id"],
                "prediction_example_id": prediction["prediction_example_id"],
                "participant_id": example["participant_id"],
                "trial_id": example["input_data"]["target"]["trial_id"],
                "condition": prediction["condition"],
                "model_key": prediction["model_key"],
                "exact_model_id": prediction["exact_model_id"],
                "inference_config_version": prediction["inference_config_version"],
                "prompt_package_version": prediction["prompt_package_version"],
                "response_schema_version": first_attempt["response_schema_version"],
                "predicted_preferred_mix": prediction["predicted_preferred_mix"],
                "predicted_rating_A": prediction["predicted_rating_A"],
                "predicted_rating_B": prediction["predicted_rating_B"],
                "predicted_rating_C": prediction["predicted_rating_C"],
                "predicted_rating_D": prediction["predicted_rating_D"],
                "predicted_rating_E": prediction["predicted_rating_E"],
                "predicted_ranking": json.dumps(prediction["predicted_ranking"], separators=(",", ":")),
                "final_inference_status": prediction["final_status"],
                "repair_used": str(bool(prediction["repair_attempt_id"])).lower(),
                "prompt_payload_sha256": first_attempt["prompt_payload_sha256"],
                "inference_config_sha256": first_attempt["inference_config_sha256"],
            }
        )
    return rows


def build_baseline_prediction_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (row["prediction_example_id"], row["baseline_model"]))


def build_ground_truth_rows(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for example in sorted(examples, key=lambda row: row["prediction_example_id"]):
        truth = example["ground_truth"]
        ratings = truth["human_ratings"]
        ranks = truth["observed_ranks"]
        rows.append(
            {
                "evaluation_only": "EVALUATION_ONLY_NEVER_MODEL_FACING",
                "prediction_example_id": example["prediction_example_id"],
                "participant_id": example["participant_id"],
                "trial_id": truth["target_trial_id"],
                "observed_preferred_mix": truth.get("observed_preferred_mix") or "",
                "observed_preferred_set": json.dumps(truth["observed_preferred_set"], separators=(",", ":")),
                "is_single_winner": str(bool(truth["is_single_winner"])).lower(),
                "n_preferred_tied": truth["n_preferred_tied"],
                "human_rating_A": ratings["A"],
                "human_rating_B": ratings["B"],
                "human_rating_C": ratings["C"],
                "human_rating_D": ratings["D"],
                "human_rating_E": ratings["E"],
                "observed_rank_A": ranks["A"],
                "observed_rank_B": ranks["B"],
                "observed_rank_C": ranks["C"],
                "observed_rank_D": ranks["D"],
                "observed_rank_E": ranks["E"],
            }
        )
    return rows


def build_alignment_rows(context: dict[str, Any], llm_rows: list[dict[str, Any]], baseline_rows: list[dict[str, Any]], ground_truth_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    llm_by_example = defaultdict(set)
    for row in llm_rows:
        llm_by_example[row["prediction_example_id"]].add((row["model_key"], row["condition"]))
    baseline_by_example = defaultdict(set)
    for row in baseline_rows:
        baseline_by_example[row["prediction_example_id"]].add(row["baseline_model"])
    ground_truth_by_example = {row["prediction_example_id"]: row for row in ground_truth_rows}
    rows = []
    for example in sorted(context["examples"], key=lambda row: row["prediction_example_id"]):
        prediction_example_id = example["prediction_example_id"]
        row = {
            "schema_version": "phase6f1_prediction_alignment_manifest_v1",
            "prediction_example_id": prediction_example_id,
            "participant_id": example["participant_id"],
            "trial_id": example["input_data"]["target"]["trial_id"],
            "ground_truth_available": prediction_example_id in ground_truth_by_example,
            "categorical_baseline_available": "categorical_design" in baseline_by_example[prediction_example_id],
            "acoustic_baseline_available": "primary_acoustic" in baseline_by_example[prediction_example_id],
        }
        for model_key in MODEL_KEYS:
            for condition in CONDITIONS:
                row[f"{model_key}_{condition}_available"] = (model_key, condition) in llm_by_example[prediction_example_id]
        row["alignment_complete"] = (
            row["ground_truth_available"]
            and all(row[f"{model_key}_{condition}_available"] for model_key in MODEL_KEYS for condition in CONDITIONS)
            and row["categorical_baseline_available"]
            and row["acoustic_baseline_available"]
        )
        rows.append(row)
    return rows


def audit_alignment(alignment_rows: list[dict[str, Any]], llm_rows: list[dict[str, Any]], baseline_rows: list[dict[str, Any]], ground_truth_rows: list[dict[str, Any]], baseline_qc: dict[str, Any], baseline_config: dict[str, Any]) -> dict[str, Any]:
    duplicate_llm = duplicates((row["prediction_example_id"], row["condition"], row["model_key"]) for row in llm_rows)
    duplicate_baseline = duplicates((row["prediction_example_id"], row["baseline_model"]) for row in baseline_rows)
    config_models = [model["model_id"] for model in baseline_config["models"] if model["role"] == "primary"]
    baseline_models = sorted({row["baseline_model"] for row in baseline_rows})
    protocol_ok = baseline_qc.get("protocol_version") == "phase6c_baseline_prediction_v1" and all(row["protocol_version"] == "phase6c_baseline_prediction_v1" for row in baseline_rows)
    baseline_alignment_valid = (
        not duplicate_baseline
        and protocol_ok
        and baseline_models == PRIMARY_BASELINE_MODELS
        and sorted(config_models) == PRIMARY_BASELINE_MODELS
        and bool({row["prediction_example_id"] for row in baseline_rows} <= {row["prediction_example_id"] for row in ground_truth_rows})
    )
    return {
        "duplicate_llm_predictions": duplicate_llm,
        "duplicate_baseline_predictions": duplicate_baseline,
        "baseline_protocol_valid": protocol_ok,
        "primary_baseline_models": baseline_models,
        "baseline_alignment_valid": baseline_alignment_valid,
        "fully_aligned_target_count": sum(1 for row in alignment_rows if row["alignment_complete"]),
        "evaluation_alignment_complete": not duplicate_llm and baseline_alignment_valid and sum(1 for row in alignment_rows if row["alignment_complete"]) > 0,
    }


def validate_mapping_and_leakage(context: dict[str, Any], baseline_rows: list[dict[str, Any]]) -> dict[str, Any]:
    examples_by_id = {row["prediction_example_id"]: row for row in context["examples"]}
    prompt_pairs = group_by_example_condition(context["prompt_data"])
    rendered_pairs = group_by_example_condition(context["rendered"])
    candidate_by_trial_label = {(row["trial_id"], row["presentation_label"]): row for row in context["candidate_truth"]}
    ae_failures = []
    acoustic_failures = []
    history_failures = []
    provenance_failures = []
    for example_id, example in examples_by_id.items():
        target_id = example["input_data"]["target"]["trial_id"]
        source_labels = [candidate["presentation_label"] for candidate in example["input_data"]["target"]["candidates"]]
        if source_labels != LABELS:
            ae_failures.append(f"{example_id}: prediction example labels")
        for condition in CONDITIONS:
            obj = prompt_pairs[example_id].get(condition)
            rendered = rendered_pairs[example_id].get(condition)
            if not obj or not rendered:
                ae_failures.append(f"{example_id}: missing {condition}")
                continue
            target = obj["model_input"]["target"]
            if [candidate["label"] for candidate in target["candidates"]] != LABELS:
                ae_failures.append(f"{example_id}: prompt-data labels {condition}")
            for candidate in target["candidates"]:
                source = candidate_by_trial_label[(target_id, candidate["label"])]
                expected = {field: round(float(source[field]), 4) for field in PRIMARY_FEATURES}
                if candidate["acoustic_features"] != expected:
                    acoustic_failures.append(f"{example_id} {condition} {candidate['label']}")
                if "z_SI" in candidate["acoustic_features"]:
                    acoustic_failures.append(f"{example_id} z_SI leaked")
            rendered_text = json.dumps(rendered, sort_keys=True)
            if any(token in rendered_text for token in OUTCOME_TOKENS) or "z_SI" in rendered_text:
                provenance_failures.append(example_id)
            if condition == "personalised_history":
                history_orders = [trial["trial_order"] for trial in obj["model_input"].get("history", [])]
                if target["trial_order"] in history_orders or history_orders != sorted(history_orders):
                    history_failures.append(example_id)
    llm_text = json.dumps(context["predictions"], sort_keys=True)
    baseline_text = json.dumps(baseline_rows, sort_keys=True)
    prediction_files_clean = not any(token in llm_text for token in OUTCOME_TOKENS)
    baseline_files_clean = not any(token in baseline_text for token in ["observed_", "human_rating"])
    return {
        "target_leakage_free": not provenance_failures and prediction_files_clean and baseline_files_clean,
        "ae_mapping_valid": not ae_failures,
        "acoustic_mapping_valid": not acoustic_failures,
        "history_selection_valid": not history_failures,
        "ground_truth_separated": prediction_files_clean and baseline_files_clean,
        "ae_failures": ae_failures[:20],
        "acoustic_failures": acoustic_failures[:20],
        "history_failures": history_failures[:20],
        "provenance_failures": provenance_failures[:20],
    }


def validate_provenance_chain(context: dict[str, Any], baseline_rows: list[dict[str, Any]]) -> dict[str, Any]:
    prompt_ids = {row["prediction_example_id"] for row in context["prompt_data"]}
    rendered_ids = {row["prediction_example_id"] for row in context["rendered"]}
    prediction_ids = {row["prediction_example_id"] for row in context["predictions"]}
    attempt_prediction_ids = {row["prediction_example_id"] for row in context["attempts"]}
    trial_ids = {row["trial_id"] for row in context["analysis_rows"]}
    baseline_ids = {row["prediction_example_id"] for row in baseline_rows}
    failures = []
    for example in context["examples"]:
        example_id = example["prediction_example_id"]
        target_id = example["input_data"]["target"]["trial_id"]
        if target_id not in trial_ids:
            failures.append(f"{example_id}: raw/canonical target trial missing")
        if example_id not in prompt_ids:
            failures.append(f"{example_id}: prompt-data missing")
        if example_id not in rendered_ids:
            failures.append(f"{example_id}: rendered prompt missing")
        if example_id not in attempt_prediction_ids:
            failures.append(f"{example_id}: inference attempt missing")
        if example_id not in prediction_ids:
            failures.append(f"{example_id}: canonical LLM prediction missing")
    for example_id in baseline_ids:
        if example_id not in prediction_ids:
            failures.append(f"{example_id}: baseline target lacks LLM prediction")
    return {
        "passed": not failures,
        "checked_prediction_examples": len(context["examples"]),
        "baseline_common_target_count": len(baseline_ids),
        "failure_count": len(failures),
        "failures": failures[:20],
    }


def structural_counts(context: dict[str, Any], baseline_rows: list[dict[str, Any]], ground_truth_rows: list[dict[str, Any]], alignment_rows: list[dict[str, Any]], llm_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "participants": len({row["participant_id"] for row in context["analysis_rows"]}),
        "trials": len({row["trial_id"] for row in context["analysis_rows"]}),
        "candidate_rows": len(context["analysis_rows"]),
        "target_eligible_trials": len(context["examples"]),
        "prediction_examples": len(context["examples"]),
        "prompt_data_objects": len(context["prompt_data"]),
        "rendered_prompts": len(context["rendered"]),
        "llm_model_count": len(MODEL_KEYS),
        "llm_requests": len(context["attempts"]),
        "llm_prediction_records": len(context["predictions"]),
        "llm_evaluation_rows": len(llm_rows),
        "baseline_prediction_records": len(baseline_rows),
        "baseline_target_count": len({row["prediction_example_id"] for row in baseline_rows}),
        "ground_truth_targets": len(ground_truth_rows),
        "fully_aligned_targets": sum(1 for row in alignment_rows if row["alignment_complete"]),
    }


def build_hash_manifest(repo_root: Path, output_dir: Path, phase6b_dir: Path, rendered_dir: Path) -> dict[str, Any]:
    paths = {
        "synthetic_raw_fixture": phase6b_dir / "phase6b5_integration_synthetic_raw_export.csv",
        "final_prediction_examples": phase6b_dir / "final_prediction_examples.jsonl",
        "rendered_prompts": rendered_dir / "rendered_prompts.jsonl",
        "llm_predictions": output_dir / "llm_predictions_for_evaluation.csv",
        "baseline_predictions": output_dir / "baseline_predictions_for_evaluation.csv",
        "ground_truth": output_dir / "ground_truth_for_evaluation.csv",
        "alignment_manifest": output_dir / "prediction_alignment_manifest.jsonl",
    }
    return {
        "schema_version": "phase6f1_hash_manifest_v1",
        "phase6f_run_version": PHASE6F_RUN_VERSION,
        "hash_algorithm": "sha256",
        "artifacts": {name: {"path": repo_relative(repo_root, path), "sha256": sha256_file(path)} for name, path in paths.items()},
    }


def scientific_output_hashes(output_dir: Path) -> dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in [
            output_dir / "llm_predictions_for_evaluation.csv",
            output_dir / "baseline_predictions_for_evaluation.csv",
            output_dir / "ground_truth_for_evaluation.csv",
            output_dir / "prediction_alignment_manifest.jsonl",
        ]
    }


def version_manifest(baseline_qc: dict[str, Any]) -> dict[str, Any]:
    return {
        "phase6f_run_version": PHASE6F_RUN_VERSION,
        "phase6b_schema_version": "phase6b3_prediction_examples_v1 / phase6b4_prompt_data_objects_v1",
        "phase6d_prompt_package_version": PROMPT_PACKAGE_VERSION,
        "phase6d_rendered_prompt_dataset_version": RENDERED_PROMPT_DATASET_VERSION,
        "phase6e_logging_version": PREDICTION_LOGGING_VERSION,
        "phase6e_failure_handling_version": FAILURE_HANDLING_VERSION,
        "phase6c_baseline_protocol_version": baseline_qc.get("protocol_version"),
        "mock_model_set": MODEL_KEYS,
    }


def write_report(path: Path, audit: dict[str, Any]) -> None:
    counts = audit["counts"]
    lines = [
        "# Phase 6F.1 Synthetic End-to-End Report",
        "",
        "This is synthetic/mock pipeline validation only. It contains no real LLM calls and no predictive performance metrics.",
        "",
        f"- Run version: `{audit['phase6f_run_version']}`",
        "- Run type: `synthetic_end_to_end`",
        f"- Phase 6B ready: `{str(audit['phase6b_ready']).lower()}`",
        f"- Prompt package verified: `{str(audit['prompt_package_verified']).lower()}`",
        f"- Experimental condition integrity: `{str(audit['experimental_condition_integrity']).lower()}`",
        f"- Mock inference complete: `{str(audit['mock_inference_complete']).lower()}`",
        f"- Baseline alignment valid: `{str(audit['baseline_alignment_valid']).lower()}`",
        f"- Ground truth separated: `{str(audit['ground_truth_separated']).lower()}`",
        f"- Deterministic rerun: `{str(audit['deterministic_rerun']).lower()}`",
        f"- `PHASE6F_E2E_ALIGNMENT_READY`: `{str(audit['phase6f_e2e_alignment_ready']).lower()}`",
        "",
        "## Counts",
        "",
        f"- Participants: {counts['participants']}",
        f"- Trials: {counts['trials']}",
        f"- Candidate rows: {counts['candidate_rows']}",
        f"- Target-eligible prediction examples: {counts['prediction_examples']}",
        f"- Prompt-data objects: {counts['prompt_data_objects']}",
        f"- Rendered prompts: {counts['rendered_prompts']}",
        f"- LLM models: {counts['llm_model_count']}",
        f"- LLM requests/attempts: {counts['llm_requests']}",
        f"- LLM prediction records: {counts['llm_prediction_records']}",
        f"- Baseline prediction rows: {counts['baseline_prediction_records']}",
        f"- Ground-truth targets: {counts['ground_truth_targets']}",
        f"- Fully aligned targets: {counts['fully_aligned_targets']}",
        "",
        "## Caveat",
        "",
        "Live exact model IDs and QMUL/RunPod backend details remain unverified from Phase 6E.2. Phase 6G production remains blocked until those gates are resolved.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def summarize_condition_audit(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "EXPERIMENTAL_CONDITION_INTEGRITY": audit["EXPERIMENTAL_CONDITION_INTEGRITY"],
        "matched_pair_count": audit.get("matched_pair_count"),
        "valid_pair_count": audit.get("valid_pair_count"),
        "failure_count": sum(value for key, value in audit.items() if key.endswith("_failures") and isinstance(value, int)),
    }


def group_by_example_condition(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        grouped[row["prediction_example_id"]][row["condition"]] = row
    return grouped


def duplicates(values: Any) -> list[Any]:
    counts = Counter(values)
    return sorted([value for value, count in counts.items() if count > 1])


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def repo_relative(repo_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 6F.1 synthetic end-to-end dry-run validation.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-rebuild", action="store_true", help="Reuse existing synthetic Phase 6B prerequisites instead of regenerating them.")
    parser.add_argument("--check-determinism", action="store_true", help="Run twice and verify deterministic scientific outputs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check_determinism:
        audit = validate_phase6f_determinism(args.repo_root, args.output_dir)
    else:
        audit = run_phase6f_synthetic_pipeline(args.repo_root, args.output_dir, rebuild=not args.no_rebuild)
    print(f"phase6f_run_version={audit['phase6f_run_version']}")
    print(f"PHASE6F_E2E_ALIGNMENT_READY={str(audit['phase6f_e2e_alignment_ready']).lower()}")
    print(f"llm_prediction_records={audit['counts']['llm_prediction_records']}")
    print(f"baseline_prediction_records={audit['counts']['baseline_prediction_records']}")
    print(f"ground_truth_targets={audit['counts']['ground_truth_targets']}")
    print(f"fully_aligned_targets={audit['counts']['fully_aligned_targets']}")
    return 0 if audit["phase6f_e2e_alignment_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
