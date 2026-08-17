"""Phase 6F.2 deterministic scoring and metric validation."""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

from llm_experiments.inference.records import sha256_file, write_json_atomic, write_jsonl


PHASE6F_METRIC_PROTOCOL_VERSION = "phase6f_metric_protocol_v1"
DEFAULT_PHASE6F1_DIR = Path("llm-experiments/outputs/synthetic/phase6f1_e2e")
DEFAULT_OUTPUT_DIR = Path("llm-experiments/outputs/synthetic/phase6f2_metrics")
LABELS = ["A", "B", "C", "D", "E"]
VALID_LLM_STATUSES = {"valid_primary", "valid_after_repair"}
SCORABLE_BASELINE_FIT_STATUSES = {"fit_ok", "convergence_warning"}
FAILED_BASELINE_FIT_STATUSES = {"fit_failed"}
NOMINAL_SINGLE_WINNER_CHANCE = 0.20
NON_SCIENTIFIC_NOTICE = "Synthetic/mock metric values are pipeline-validation outputs only and must not be interpreted as model performance."
PROHIBITED_INFERENCE_TERMS = ["confidence interval", "bootstrap", "p-value", "statistical significance", "bayesian comparison"]


def run_phase6f2_metrics(
    repo_root: Path,
    input_dir: Path = DEFAULT_PHASE6F1_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    input_dir = repo_path(repo_root, input_dir)
    output_dir = repo_path(repo_root, output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    llm_rows = read_csv(input_dir / "llm_predictions_for_evaluation.csv")
    baseline_rows = read_csv(input_dir / "baseline_predictions_for_evaluation.csv")
    ground_truth_rows = read_csv(input_dir / "ground_truth_for_evaluation.csv")
    alignment_rows = read_jsonl(input_dir / "prediction_alignment_manifest.jsonl")

    scored_llm = score_llm_predictions(llm_rows, ground_truth_rows, alignment_rows)
    scored_baseline = score_baseline_predictions(baseline_rows, ground_truth_rows, alignment_rows)
    llm_summary = aggregate_metrics(scored_llm, ["model_key", "condition"])
    baseline_summary = aggregate_metrics(scored_baseline, ["baseline_model"])
    participant_llm = aggregate_metrics(scored_llm, ["participant_id", "model_key", "condition"], participant_level=True)
    participant_baseline = aggregate_metrics(scored_baseline, ["participant_id", "baseline_model"], participant_level=True)
    coverage = build_coverage_summary(scored_llm, scored_baseline, ground_truth_rows)
    validation = controlled_metric_validation()
    audit = build_metric_audit(scored_llm, scored_baseline, ground_truth_rows, alignment_rows, validation)

    write_csv(output_dir / "scored_llm_predictions.csv", scored_llm)
    write_csv(output_dir / "scored_baseline_predictions.csv", scored_baseline)
    write_csv(output_dir / "llm_metric_summary.csv", llm_summary)
    write_csv(output_dir / "baseline_metric_summary.csv", baseline_summary)
    write_csv(output_dir / "participant_llm_metrics.csv", participant_llm)
    write_csv(output_dir / "participant_baseline_metrics.csv", participant_baseline)
    write_json_atomic(output_dir / "metric_coverage_summary.json", coverage)
    write_json_atomic(output_dir / "phase6f2_metric_audit.json", audit)
    write_report(output_dir / "phase6f2_metric_validation_report.md", audit, coverage)
    write_json_atomic(output_dir / "phase6f2_hash_manifest.json", build_hash_manifest(repo_root, input_dir, output_dir))
    return audit


def derive_canonical_prediction(row: dict[str, Any]) -> dict[str, Any]:
    ratings = rating_vector(row, "predicted_rating_")
    explicit_ranking = parse_ranking(row.get("predicted_ranking", "[]"))
    max_rating = max(ratings.values())
    tied_maxima = [label for label in LABELS if ratings[label] == max_rating]
    predicted_rating_tie = len(tied_maxima) > 1
    if len(tied_maxima) == 1:
        canonical = tied_maxima[0]
    else:
        canonical = next(label for label in explicit_ranking if label in tied_maxima)
    explicit_preferred = clean_label(row.get("predicted_preferred_mix", ""))
    return {
        "canonical_predicted_preferred_mix": canonical,
        "predicted_rating_tie": predicted_rating_tie,
        "explicit_preferred_matches_canonical": explicit_preferred == canonical,
        "ranking_top_matches_canonical": bool(explicit_ranking and explicit_ranking[0] == canonical),
    }


def score_top1(canonical_predicted_preferred_mix: str | None, observed_preferred_set: list[str]) -> bool:
    return bool(canonical_predicted_preferred_mix and canonical_predicted_preferred_mix in observed_preferred_set)


def score_rating_errors(predicted: dict[str, float], observed: dict[str, float]) -> dict[str, float]:
    absolute_errors = [abs(predicted[label] - observed[label]) for label in LABELS]
    squared_errors = [(predicted[label] - observed[label]) ** 2 for label in LABELS]
    return {
        "mae": sum(absolute_errors) / len(LABELS),
        "rmse": math.sqrt(sum(squared_errors) / len(LABELS)),
    }


def derive_tie_aware_ranks(values: dict[str, float], higher_is_better: bool = True) -> dict[str, float]:
    ordered = sorted(LABELS, key=lambda label: values[label], reverse=higher_is_better)
    ranks: dict[str, float] = {}
    position = 1
    index = 0
    while index < len(ordered):
        tied = [ordered[index]]
        while index + len(tied) < len(ordered) and values[ordered[index + len(tied)]] == values[ordered[index]]:
            tied.append(ordered[index + len(tied)])
        first = position
        last = position + len(tied) - 1
        mid_rank = (first + last) / 2
        for label in tied:
            ranks[label] = mid_rank
        position += len(tied)
        index += len(tied)
    return ranks


def score_spearman(observed_ranks: dict[str, float], predicted_ranks: dict[str, float]) -> dict[str, Any]:
    observed = [observed_ranks[label] for label in LABELS]
    predicted = [predicted_ranks[label] for label in LABELS]
    if is_constant(observed):
        return {"spearman": None, "spearman_defined": False, "spearman_undefined_reason": "observed_rank_constant"}
    if is_constant(predicted):
        return {"spearman": None, "spearman_defined": False, "spearman_undefined_reason": "predicted_rank_constant"}
    return {"spearman": pearson(observed, predicted), "spearman_defined": True, "spearman_undefined_reason": ""}


def score_llm_predictions(
    prediction_rows: list[dict[str, Any]],
    ground_truth_rows: list[dict[str, Any]],
    alignment_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    truth_by_id = validate_ground_truth(ground_truth_rows)
    rows_by_key = {(row["prediction_example_id"], row["model_key"], row["condition"]): row for row in prediction_rows}
    duplicate_keys = duplicates((row["prediction_example_id"], row["model_key"], row["condition"]) for row in prediction_rows)
    if duplicate_keys:
        raise ValueError(f"Duplicate LLM prediction keys: {duplicate_keys[:3]}")

    expected_keys = sorted(expected_llm_keys(alignment_rows) | set(rows_by_key))
    scored = []
    for prediction_example_id, model_key, condition in expected_keys:
        row = rows_by_key.get((prediction_example_id, model_key, condition))
        truth = truth_by_id.get(prediction_example_id)
        if truth is None:
            scored.append(missing_truth_row(prediction_example_id, model_key, condition, "llm"))
            continue
        if row is None:
            scored.append(score_missing_llm(prediction_example_id, model_key, condition, truth))
            continue
        scored.append(score_one_llm(row, truth))
    return sorted(scored, key=lambda row: (row["prediction_example_id"], row["model_key"], row["condition"]))


def score_baseline_predictions(
    prediction_rows: list[dict[str, Any]],
    ground_truth_rows: list[dict[str, Any]],
    alignment_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    truth_by_id = validate_ground_truth(ground_truth_rows)
    rows_by_key = {(row["prediction_example_id"], row["baseline_model"]): row for row in prediction_rows}
    duplicate_keys = duplicates((row["prediction_example_id"], row["baseline_model"]) for row in prediction_rows)
    if duplicate_keys:
        raise ValueError(f"Duplicate baseline prediction keys: {duplicate_keys[:3]}")

    expected_keys = sorted(expected_baseline_keys(alignment_rows) | set(rows_by_key))
    scored = []
    for prediction_example_id, baseline_model in expected_keys:
        row = rows_by_key.get((prediction_example_id, baseline_model))
        truth = truth_by_id.get(prediction_example_id)
        if truth is None:
            scored.append(missing_truth_row(prediction_example_id, baseline_model, "", "baseline"))
            continue
        if row is None:
            scored.append(score_missing_baseline(prediction_example_id, baseline_model, truth))
            continue
        scored.append(score_one_baseline(row, truth))
    return sorted(scored, key=lambda row: (row["prediction_example_id"], row["baseline_model"]))


def aggregate_metrics(rows: list[dict[str, Any]], group_fields: list[str], participant_level: bool = False) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(field, "") for field in group_fields)].append(row)
    output = []
    for key in sorted(groups):
        group = groups[key]
        expected = len(group)
        valid = [row for row in group if row["scorable_prediction"] == "true"]
        strict_correct = sum(1 for row in group if row["top1_correct"] == "true")
        defined_spearman = [float(row["spearman"]) for row in valid if row["spearman_defined"] == "true"]
        record = {field: key[index] for index, field in enumerate(group_fields)}
        record.update(
            {
                "metric_protocol_version": PHASE6F_METRIC_PROTOCOL_VERSION,
                "synthetic_metric_notice": NON_SCIENTIFIC_NOTICE,
                "expected_predictions": expected,
                "valid_predictions": len(valid),
                "strict_correct_count": strict_correct,
                "strict_top1_accuracy": divide(strict_correct, expected),
                "valid_only_diagnostic_accuracy": divide(sum(1 for row in valid if row["top1_correct"] == "true"), len(valid)),
                "mean_per_trial_mae": mean_or_blank(float(row["mae"]) for row in valid if row["mae"] != ""),
                "mean_per_trial_rmse": mean_or_blank(float(row["rmse"]) for row in valid if row["rmse"] != ""),
                "mean_spearman_defined": mean_or_blank(defined_spearman),
                "median_spearman_defined": median_or_blank(defined_spearman),
                "continuous_metric_coverage": divide(len([row for row in valid if row["mae"] != "" and row["rmse"] != ""]), expected),
                "ranking_metric_coverage": divide(len(defined_spearman), expected),
                "invalid_count": sum(1 for row in group if row["invalid_failure_category"] in {"invalid_after_repair", "fit_failed"}),
                "backend_failure_count": sum(1 for row in group if row["invalid_failure_category"] == "backend_failed"),
                "missing_count": sum(1 for row in group if row["invalid_failure_category"] == "missing_not_run"),
                "undefined_observed_rank_count": sum(1 for row in valid if row["spearman_undefined_reason"] == "observed_rank_constant"),
                "undefined_predicted_rank_count": sum(1 for row in valid if row["spearman_undefined_reason"] == "predicted_rank_constant"),
            }
        )
        if participant_level:
            record["target_trials"] = expected
        output.append(record)
    return output


def score_one_llm(row: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    status = row["final_inference_status"]
    base = base_scored_row(row, truth, "llm")
    category = llm_failure_category(status)
    base["invalid_failure_category"] = category
    base["scorable_prediction"] = str(status in VALID_LLM_STATUSES).lower()
    if status not in VALID_LLM_STATUSES:
        return base
    canonical = derive_canonical_prediction(row)
    return score_structured_prediction(base, row, truth, canonical)


def score_one_baseline(row: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    fit_status = row["fit_status"]
    base = base_scored_row(row, truth, "baseline")
    base["fit_status"] = fit_status
    base["invalid_failure_category"] = "valid" if fit_status in SCORABLE_BASELINE_FIT_STATUSES else fit_status
    base["scorable_prediction"] = str(fit_status in SCORABLE_BASELINE_FIT_STATUSES).lower()
    if fit_status not in SCORABLE_BASELINE_FIT_STATUSES:
        return base
    canonical = {
        "canonical_predicted_preferred_mix": clean_label(row["predicted_preferred_mix"]),
        "predicted_rating_tie": str(row.get("predicted_tie", "")).lower() == "true",
        "explicit_preferred_matches_canonical": True,
        "ranking_top_matches_canonical": "",
    }
    return score_structured_prediction(base, row, truth, canonical)


def score_structured_prediction(base: dict[str, Any], row: dict[str, Any], truth: dict[str, Any], canonical: dict[str, Any]) -> dict[str, Any]:
    predicted = rating_vector(row, "predicted_rating_")
    observed = rating_vector(truth, "human_rating_")
    observed_ranks = rating_vector(truth, "observed_rank_")
    predicted_ranks = derive_tie_aware_ranks(predicted)
    errors = score_rating_errors(predicted, observed)
    spearman = score_spearman(observed_ranks, predicted_ranks)
    top1 = score_top1(canonical["canonical_predicted_preferred_mix"], parse_label_set(truth["observed_preferred_set"]))
    base.update(
        {
            "canonical_predicted_preferred_mix": canonical["canonical_predicted_preferred_mix"],
            "predicted_rating_tie": str(canonical["predicted_rating_tie"]).lower(),
            "explicit_preferred_matches_canonical": str(canonical["explicit_preferred_matches_canonical"]).lower(),
            "ranking_top_matches_canonical": str(canonical["ranking_top_matches_canonical"]).lower() if canonical["ranking_top_matches_canonical"] != "" else "",
            "top1_correct": str(top1).lower(),
            "mae": format_float(errors["mae"]),
            "rmse": format_float(errors["rmse"]),
            "spearman": format_float(spearman["spearman"]) if spearman["spearman"] is not None else "",
            "spearman_defined": str(spearman["spearman_defined"]).lower(),
            "spearman_undefined_reason": spearman["spearman_undefined_reason"],
            "predicted_rank_A": format_float(predicted_ranks["A"]),
            "predicted_rank_B": format_float(predicted_ranks["B"]),
            "predicted_rank_C": format_float(predicted_ranks["C"]),
            "predicted_rank_D": format_float(predicted_ranks["D"]),
            "predicted_rank_E": format_float(predicted_ranks["E"]),
        }
    )
    return base


def base_scored_row(row: dict[str, Any], truth: dict[str, Any], source: str) -> dict[str, Any]:
    output = {
        "metric_protocol_version": PHASE6F_METRIC_PROTOCOL_VERSION,
        "synthetic_metric_notice": NON_SCIENTIFIC_NOTICE,
        "prediction_source": source,
        "prediction_record_id": row.get("prediction_record_id", ""),
        "prediction_example_id": row["prediction_example_id"],
        "participant_id": row["participant_id"],
        "trial_id": row["trial_id"],
        "model_key": row.get("model_key", ""),
        "condition": row.get("condition", ""),
        "baseline_model": row.get("baseline_model", ""),
        "final_inference_status": row.get("final_inference_status", ""),
        "fit_status": row.get("fit_status", ""),
        "canonical_predicted_preferred_mix": "",
        "observed_preferred_set": truth["observed_preferred_set"],
        "top1_correct": "false",
        "mae": "",
        "rmse": "",
        "spearman": "",
        "spearman_defined": "false",
        "spearman_undefined_reason": "not_scorable",
        "invalid_failure_category": "",
        "scorable_prediction": "false",
        "predicted_rating_tie": "",
        "explicit_preferred_matches_canonical": "",
        "ranking_top_matches_canonical": "",
        "predicted_rank_A": "",
        "predicted_rank_B": "",
        "predicted_rank_C": "",
        "predicted_rank_D": "",
        "predicted_rank_E": "",
        "nominal_single_winner_chance_reference": NOMINAL_SINGLE_WINNER_CHANCE,
        "strict_denominator_includes_record": "true",
    }
    for label in LABELS:
        output[f"predicted_rating_{label}"] = row.get(f"predicted_rating_{label}", "")
        output[f"human_rating_{label}"] = truth.get(f"human_rating_{label}", "")
        output[f"observed_rank_{label}"] = truth.get(f"observed_rank_{label}", "")
    return output


def score_missing_llm(prediction_example_id: str, model_key: str, condition: str, truth: dict[str, Any]) -> dict[str, Any]:
    row = {
        "prediction_example_id": prediction_example_id,
        "participant_id": truth["participant_id"],
        "trial_id": truth["trial_id"],
        "model_key": model_key,
        "condition": condition,
        "final_inference_status": "missing_not_run",
    }
    scored = base_scored_row(row, truth, "llm")
    scored["invalid_failure_category"] = "missing_not_run"
    return scored


def score_missing_baseline(prediction_example_id: str, baseline_model: str, truth: dict[str, Any]) -> dict[str, Any]:
    row = {
        "prediction_example_id": prediction_example_id,
        "participant_id": truth["participant_id"],
        "trial_id": truth["trial_id"],
        "baseline_model": baseline_model,
        "fit_status": "missing_not_run",
    }
    scored = base_scored_row(row, truth, "baseline")
    scored["invalid_failure_category"] = "missing_not_run"
    return scored


def missing_truth_row(prediction_example_id: str, model: str, condition: str, source: str) -> dict[str, Any]:
    row = {
        "metric_protocol_version": PHASE6F_METRIC_PROTOCOL_VERSION,
        "synthetic_metric_notice": NON_SCIENTIFIC_NOTICE,
        "prediction_source": source,
        "prediction_record_id": "",
        "prediction_example_id": prediction_example_id,
        "participant_id": "",
        "trial_id": "",
        "model_key": model if source == "llm" else "",
        "condition": condition,
        "baseline_model": model if source == "baseline" else "",
        "final_inference_status": "missing_ground_truth" if source == "llm" else "",
        "fit_status": "missing_ground_truth" if source == "baseline" else "",
        "canonical_predicted_preferred_mix": "",
        "observed_preferred_set": "",
        "top1_correct": "false",
        "mae": "",
        "rmse": "",
        "spearman": "",
        "spearman_defined": "false",
        "spearman_undefined_reason": "missing_ground_truth",
        "invalid_failure_category": "missing_ground_truth",
        "scorable_prediction": "false",
        "predicted_rating_tie": "",
        "explicit_preferred_matches_canonical": "",
        "ranking_top_matches_canonical": "",
        "predicted_rank_A": "",
        "predicted_rank_B": "",
        "predicted_rank_C": "",
        "predicted_rank_D": "",
        "predicted_rank_E": "",
        "nominal_single_winner_chance_reference": NOMINAL_SINGLE_WINNER_CHANCE,
        "strict_denominator_includes_record": "true",
    }
    for label in LABELS:
        row[f"predicted_rating_{label}"] = ""
        row[f"human_rating_{label}"] = ""
        row[f"observed_rank_{label}"] = ""
    return row


def build_coverage_summary(scored_llm: list[dict[str, Any]], scored_baseline: list[dict[str, Any]], ground_truth_rows: list[dict[str, Any]]) -> dict[str, Any]:
    def coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
        expected = len(rows)
        valid = sum(1 for row in rows if row["scorable_prediction"] == "true")
        defined_rank = sum(1 for row in rows if row["spearman_defined"] == "true")
        return {
            "expected_predictions": expected,
            "valid_numeric_predictions": valid,
            "continuous_metric_coverage": divide(valid, expected),
            "rank_correlations_defined": defined_rank,
            "ranking_metric_coverage": divide(defined_rank, expected),
            "undefined_observed_rank_count": sum(1 for row in rows if row["spearman_undefined_reason"] == "observed_rank_constant"),
            "undefined_predicted_rank_count": sum(1 for row in rows if row["spearman_undefined_reason"] == "predicted_rank_constant"),
            "backend_failure_count": sum(1 for row in rows if row["invalid_failure_category"] == "backend_failed"),
            "invalid_count": sum(1 for row in rows if row["invalid_failure_category"] in {"invalid_after_repair", "fit_failed"}),
            "missing_not_run_count": sum(1 for row in rows if row["invalid_failure_category"] == "missing_not_run"),
        }

    return {
        "metric_protocol_version": PHASE6F_METRIC_PROTOCOL_VERSION,
        "synthetic_metric_notice": NON_SCIENTIFIC_NOTICE,
        "ground_truth_targets": len(ground_truth_rows),
        "nominal_single_winner_chance_reference": NOMINAL_SINGLE_WINNER_CHANCE,
        "llm": coverage(scored_llm),
        "baseline": coverage(scored_baseline),
        "baseline_smoke_subset_caveat": "Phase 6C synthetic smoke baseline currently covers only available aligned smoke rows, not all 11 targets.",
        "no_inferential_statistics_emitted": True,
    }


def build_metric_audit(
    scored_llm: list[dict[str, Any]],
    scored_baseline: list[dict[str, Any]],
    ground_truth_rows: list[dict[str, Any]],
    alignment_rows: list[dict[str, Any]],
    validation: dict[str, Any],
) -> dict[str, Any]:
    missing_truth = [row for row in scored_llm + scored_baseline if row["invalid_failure_category"] == "missing_ground_truth"]
    audit = {
        "schema_version": "phase6f2_metric_audit_v1",
        "metric_protocol_version": PHASE6F_METRIC_PROTOCOL_VERSION,
        "synthetic_metric_notice": NON_SCIENTIFIC_NOTICE,
        "top1_preferred_set_rule": "canonical predicted top label is correct when it belongs to the observed preferred set",
        "strict_denominator_rule": "all expected prediction records for a model/condition or baseline subset are included; invalid, failed, and missing expected records are non-successes",
        "continuous_metric_rule": "MAE/RMSE are mean per-trial values across A-E and are reported only for structurally produced numeric predictions with coverage",
        "rank_rule": "predicted ranks are tie-aware mid-ranks derived from predicted numeric ratings; explicit ranking is used only to resolve predicted-rating top ties",
        "undefined_spearman_rule": "constant observed or predicted rank vectors produce null Spearman with a reason",
        "baseline_scoring_rule": "use Phase 6C predicted_preferred_mix and predicted ratings; winning probabilities are not primary categorical predictions",
        "ground_truth_join_valid": not missing_truth,
        "preferred_set_membership_valid": validation["preferred_set_membership_valid"],
        "canonical_prediction_derivation_valid": validation["canonical_prediction_derivation_valid"],
        "strict_denominator_valid": validation["strict_denominator_valid"],
        "mae_validated": validation["mae_validated"],
        "rmse_validated": validation["rmse_validated"],
        "tie_aware_rank_validated": validation["tie_aware_rank_validated"],
        "spearman_validated": validation["spearman_validated"],
        "invalid_output_handling_valid": validation["invalid_output_handling_valid"],
        "llm_scoring_complete": len(scored_llm) > 0 and not missing_truth,
        "baseline_scoring_complete_for_available_smoke_subset": len(scored_baseline) > 0 and not any(row["invalid_failure_category"] == "missing_ground_truth" for row in scored_baseline),
        "no_inferential_statistics_emitted": True,
        "contains_scientific_plots": False,
        "synthetic_llm_scored_rows": len(scored_llm),
        "synthetic_baseline_scored_rows": len(scored_baseline),
        "ground_truth_targets": len(ground_truth_rows),
        "alignment_manifest_rows": len(alignment_rows),
        "controlled_validation": validation,
    }
    return audit


def controlled_metric_validation() -> dict[str, Any]:
    observed = dict(zip(LABELS, [0, 25, 50, 75, 100], strict=True))
    predicted = dict(zip(LABELS, [10, 20, 40, 80, 90], strict=True))
    errors = score_rating_errors(predicted, observed)
    perfect = score_spearman(derive_tie_aware_ranks(observed), derive_tie_aware_ranks(observed))
    reverse_values = dict(zip(LABELS, [100, 75, 50, 25, 0], strict=True))
    reverse = score_spearman(derive_tie_aware_ranks(observed), derive_tie_aware_ranks(reverse_values))
    tied = score_spearman(
        {"A": 1.0, "B": 2.5, "C": 2.5, "D": 4.0, "E": 5.0},
        {"A": 1.5, "B": 1.5, "C": 3.0, "D": 4.0, "E": 5.0},
    )
    constant_observed = score_spearman({label: 3.0 for label in LABELS}, derive_tie_aware_ranks(predicted))
    constant_predicted = score_spearman(derive_tie_aware_ranks(observed), {label: 3.0 for label in LABELS})
    tie_row = {
        "predicted_rating_A": "80",
        "predicted_rating_B": "20",
        "predicted_rating_C": "80",
        "predicted_rating_D": "10",
        "predicted_rating_E": "5",
        "predicted_ranking": json.dumps(["C", "A", "B", "D", "E"]),
        "predicted_preferred_mix": "A",
    }
    canonical = derive_canonical_prediction(tie_row)
    strict_fixture = aggregate_metrics(
        [
            {"model_key": "m", "condition": "c", "scorable_prediction": "true", "top1_correct": "true", "mae": "1", "rmse": "1", "spearman_defined": "true", "spearman": "1", "spearman_undefined_reason": "", "invalid_failure_category": ""},
            {"model_key": "m", "condition": "c", "scorable_prediction": "true", "top1_correct": "false", "mae": "2", "rmse": "2", "spearman_defined": "true", "spearman": "-1", "spearman_undefined_reason": "", "invalid_failure_category": ""},
            {"model_key": "m", "condition": "c", "scorable_prediction": "false", "top1_correct": "false", "mae": "", "rmse": "", "spearman_defined": "false", "spearman": "", "spearman_undefined_reason": "not_scorable", "invalid_failure_category": "invalid_after_repair"},
            {"model_key": "m", "condition": "c", "scorable_prediction": "false", "top1_correct": "false", "mae": "", "rmse": "", "spearman_defined": "false", "spearman": "", "spearman_undefined_reason": "not_scorable", "invalid_failure_category": "backend_failed"},
        ],
        ["model_key", "condition"],
    )[0]
    return {
        "preferred_set_membership_valid": score_top1("A", ["A", "C"]) and score_top1("C", ["A", "C"]) and not score_top1("B", ["A", "C"]) and all(score_top1(label, LABELS) for label in LABELS),
        "canonical_prediction_derivation_valid": canonical["canonical_predicted_preferred_mix"] == "C",
        "strict_denominator_valid": float(strict_fixture["strict_top1_accuracy"]) == 0.25 and float(strict_fixture["valid_only_diagnostic_accuracy"]) == 0.5,
        "mae_validated": math.isclose(errors["mae"], 8.0),
        "rmse_validated": math.isclose(errors["rmse"], math.sqrt(70.0)),
        "tie_aware_rank_validated": derive_tie_aware_ranks({"A": 5, "B": 4, "C": 4, "D": 2, "E": 1}) == {"A": 1.0, "B": 2.5, "C": 2.5, "D": 4.0, "E": 5.0},
        "spearman_validated": math.isclose(float(perfect["spearman"]), 1.0) and math.isclose(float(reverse["spearman"]), -1.0) and tied["spearman_defined"],
        "invalid_output_handling_valid": strict_fixture["invalid_count"] == 1 and strict_fixture["backend_failure_count"] == 1,
        "constant_observed_rank_reason": constant_observed["spearman_undefined_reason"],
        "constant_predicted_rank_reason": constant_predicted["spearman_undefined_reason"],
        "tie_aware_spearman_reference": tied["spearman"],
    }


def expected_llm_keys(alignment_rows: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    keys = set()
    for row in alignment_rows:
        for field, value in row.items():
            if not field.endswith("_available") or field in {"ground_truth_available", "categorical_baseline_available", "acoustic_baseline_available"}:
                continue
            if str(value).lower() == "true":
                suffix = "_personalised_history_available" if field.endswith("_personalised_history_available") else "_non_history_available"
                condition = suffix.removeprefix("_").removesuffix("_available")
                model_key = field.removesuffix(suffix)
                keys.add((row["prediction_example_id"], model_key, condition))
    return keys


def expected_baseline_keys(alignment_rows: list[dict[str, Any]]) -> set[tuple[str, str]]:
    keys = set()
    for row in alignment_rows:
        if str(row.get("categorical_baseline_available")).lower() == "true":
            keys.add((row["prediction_example_id"], "categorical_design"))
        if str(row.get("acoustic_baseline_available")).lower() == "true":
            keys.add((row["prediction_example_id"], "primary_acoustic"))
    return keys


def validate_ground_truth(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    counts = Counter(row["prediction_example_id"] for row in rows)
    duplicates_found = [key for key, count in counts.items() if count > 1]
    if duplicates_found:
        raise ValueError(f"Duplicate ground truth prediction_example_id values: {duplicates_found[:3]}")
    truth_by_id = {row["prediction_example_id"]: row for row in rows}
    for row in rows:
        preferred = parse_label_set(row["observed_preferred_set"])
        if not preferred or any(label not in LABELS for label in preferred):
            raise ValueError(f"Invalid observed preferred set for {row['prediction_example_id']}")
    return truth_by_id


def llm_failure_category(status: str) -> str:
    if status in VALID_LLM_STATUSES:
        return "valid"
    if status == "invalid_after_repair":
        return "invalid_after_repair"
    if status in {"backend_failed", "transport_failed", "non_retryable_backend_error"}:
        return "backend_failed"
    if status in {"missing_not_run", "missing"}:
        return "missing_not_run"
    return status or "missing_not_run"


def parse_label_set(value: Any) -> list[str]:
    if isinstance(value, list):
        return [clean_label(label) for label in value]
    text = str(value).strip()
    if text.startswith("["):
        return [clean_label(label) for label in json.loads(text)]
    return [clean_label(part) for part in text.split("|") if part.strip()]


def parse_ranking(value: Any) -> list[str]:
    if isinstance(value, list):
        ranking = value
    else:
        ranking = json.loads(str(value))
    cleaned = [clean_label(label) for label in ranking]
    if sorted(cleaned) != LABELS:
        raise ValueError(f"Invalid predicted ranking: {value}")
    return cleaned


def rating_vector(row: dict[str, Any], prefix: str) -> dict[str, float]:
    return {label: float(row[f"{prefix}{label}"]) for label in LABELS}


def pearson(x: list[float], y: list[float]) -> float:
    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)
    numerator = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y, strict=True))
    denominator_x = math.sqrt(sum((a - mean_x) ** 2 for a in x))
    denominator_y = math.sqrt(sum((b - mean_y) ** 2 for b in y))
    return numerator / (denominator_x * denominator_y)


def is_constant(values: list[float]) -> bool:
    return all(value == values[0] for value in values)


def mean_or_blank(values: Any) -> str:
    items = list(values)
    if not items:
        return ""
    return format_float(sum(items) / len(items))


def median_or_blank(values: list[float]) -> str:
    if not values:
        return ""
    return format_float(float(median(values)))


def divide(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return ""
    return format_float(numerator / denominator)


def format_float(value: float) -> str:
    return f"{value:.12g}"


def clean_label(label: Any) -> str:
    return str(label).strip().upper()


def duplicates(values: Any) -> list[Any]:
    counts = Counter(values)
    return sorted([value for value, count in counts.items() if count > 1])


def build_hash_manifest(repo_root: Path, input_dir: Path, output_dir: Path) -> dict[str, Any]:
    paths = {
        "phase6f1_llm_predictions": input_dir / "llm_predictions_for_evaluation.csv",
        "phase6f1_baseline_predictions": input_dir / "baseline_predictions_for_evaluation.csv",
        "phase6f1_ground_truth": input_dir / "ground_truth_for_evaluation.csv",
        "phase6f1_alignment_manifest": input_dir / "prediction_alignment_manifest.jsonl",
        "scored_llm_predictions": output_dir / "scored_llm_predictions.csv",
        "scored_baseline_predictions": output_dir / "scored_baseline_predictions.csv",
        "llm_metric_summary": output_dir / "llm_metric_summary.csv",
        "baseline_metric_summary": output_dir / "baseline_metric_summary.csv",
        "participant_llm_metrics": output_dir / "participant_llm_metrics.csv",
        "participant_baseline_metrics": output_dir / "participant_baseline_metrics.csv",
        "metric_coverage_summary": output_dir / "metric_coverage_summary.json",
        "phase6f2_metric_audit": output_dir / "phase6f2_metric_audit.json",
        "phase6f2_metric_validation_report": output_dir / "phase6f2_metric_validation_report.md",
    }
    return {
        "schema_version": "phase6f2_hash_manifest_v1",
        "metric_protocol_version": PHASE6F_METRIC_PROTOCOL_VERSION,
        "hash_algorithm": "sha256",
        "artifacts": {name: {"path": repo_relative(repo_root, path), "sha256": sha256_file(path)} for name, path in paths.items()},
    }


def write_report(path: Path, audit: dict[str, Any], coverage: dict[str, Any]) -> None:
    lines = [
        "# Phase 6F.2 Synthetic Metric Validation Report",
        "",
        NON_SCIENTIFIC_NOTICE,
        "",
        f"- Metric protocol version: `{PHASE6F_METRIC_PROTOCOL_VERSION}`",
        f"- Nominal single-winner chance reference: `{NOMINAL_SINGLE_WINNER_CHANCE}`",
        f"- Ground-truth join valid: `{str(audit['ground_truth_join_valid']).lower()}`",
        f"- Strict denominator valid: `{str(audit['strict_denominator_valid']).lower()}`",
        f"- LLM scored rows: `{audit['synthetic_llm_scored_rows']}`",
        f"- Baseline scored rows: `{audit['synthetic_baseline_scored_rows']}`",
        f"- LLM continuous coverage: `{coverage['llm']['continuous_metric_coverage']}`",
        f"- LLM ranking coverage: `{coverage['llm']['ranking_metric_coverage']}`",
        f"- Baseline continuous coverage: `{coverage['baseline']['continuous_metric_coverage']}`",
        f"- Baseline ranking coverage: `{coverage['baseline']['ranking_metric_coverage']}`",
        "",
        "## Denominator Rule",
        "",
        "Strict top-1 accuracy includes every expected prediction record for the evaluated subset. Invalid outputs, backend failures, and missing/not-run expected records remain in the denominator and count as non-successes. Valid-only accuracy is diagnostic only.",
        "",
        "## Continuous Metrics",
        "",
        "MAE and RMSE are computed per valid trial across A-E and aggregated as the mean of per-trial values. They are always reported with valid-output coverage.",
        "",
        "## Rank Metrics",
        "",
        "Predicted ranks are tie-aware mid-ranks derived from predicted numeric ratings. Explicit ranking is used only to resolve predicted-rating ties for the canonical top label. Spearman is null when observed or predicted rank vectors are constant.",
        "",
        "## Baseline Caveat",
        "",
        coverage["baseline_smoke_subset_caveat"],
        "",
        "No confidence intervals, bootstrap distributions, p-values, hypothesis tests, Bayesian comparisons, scientific plots, or model-ranking claims are emitted in Phase 6F.2.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def repo_relative(repo_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 6F.2 deterministic synthetic metric scoring.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_PHASE6F1_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    audit = run_phase6f2_metrics(args.repo_root, args.input_dir, args.output_dir)
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
