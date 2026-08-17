"""Phase 6C.3 held-out baseline output consolidation and QC."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from statistical_baseline.heldout import (
    BASELINE_PROTOCOL_VERSION,
    DEFAULT_CONFIG,
    DEFAULT_INTERVAL_LEVEL,
    EXPECTED_LABELS,
    FIT_DIAGNOSTIC_COLUMNS,
    PRIMARY_MODEL_IDS,
    derive_baseline_winner,
    load_csv,
    load_jsonl,
    load_model_config,
    write_csv,
    write_json,
)


PROBABILITY_TOLERANCE = 1e-6
RUN_TYPES = {"synthetic_smoke", "production"}
CONSOLIDATION_VERSION = "phase6c3_baseline_consolidation_v1"
PREDICTION_QUANTITY = "posterior_expected_mean_rating"
FORBIDDEN_OUTCOME_FIELDS = {
    "human_rating",
    "observed_rating",
    "observed_rating_A",
    "observed_rating_B",
    "observed_rating_C",
    "observed_rating_D",
    "observed_rating_E",
    "observed_preferred_set",
    "observed_preferred_mix",
    "observed_rank",
    "is_single_winner",
    "is_observed_preferred",
    "n_preferred_tied",
    "target_comparative_comment",
    "comparative_comment",
    "ground_truth",
}

CANONICAL_CANDIDATE_COLUMNS = [
    "prediction_example_id",
    "participant_id",
    "trial_id",
    "baseline_model",
    "model_role",
    "presentation_label",
    "stimulus_id",
    "predicted_mean_rating",
    "posterior_predictive_mean",
    "posterior_predictive_sd",
    "posterior_expected_ci_lower",
    "posterior_expected_ci_upper",
    "posterior_winning_probability",
    "fit_status",
    "protocol_version",
]

CANONICAL_TRIAL_COLUMNS = [
    "prediction_example_id",
    "participant_id",
    "trial_id",
    "baseline_model",
    "model_role",
    "predicted_preferred_mix",
    "predicted_tie",
    "predicted_tied_labels",
    "predicted_rating_A",
    "predicted_rating_B",
    "predicted_rating_C",
    "predicted_rating_D",
    "predicted_rating_E",
    "winning_probability_A",
    "winning_probability_B",
    "winning_probability_C",
    "winning_probability_D",
    "winning_probability_E",
    "fit_status",
    "protocol_version",
]

CONSOLIDATED_DIAGNOSTIC_COLUMNS = [
    "prediction_example_id",
    "baseline_model",
    "model_role",
    *FIT_DIAGNOSTIC_COLUMNS[2:],
]

COMPLETION_MANIFEST_COLUMNS = [
    "prediction_example_id",
    "participant_id",
    "trial_id",
    "baseline_model",
    "model_role",
    "expected",
    "completed",
    "missing",
    "warning",
    "failed",
    "candidate_rows",
    "trial_summary_rows",
    "diagnostic_rows",
    "output_validated",
    "validation_failures",
    "fit_status",
    "protocol_version",
    "inference_mode",
]

EVALUATION_READY_COLUMNS = [
    "prediction_example_id",
    "participant_id",
    "trial_id",
    "baseline_model",
    "model_role",
    "predicted_preferred_mix",
    "predicted_tie",
    "predicted_rating_A",
    "predicted_rating_B",
    "predicted_rating_C",
    "predicted_rating_D",
    "predicted_rating_E",
    "winning_probability_A",
    "winning_probability_B",
    "winning_probability_C",
    "winning_probability_D",
    "winning_probability_E",
    "fit_status",
    "protocol_version",
]


def consolidate_outputs(
    fit_output_dir: Path,
    fit_manifest_csv: Path,
    prediction_examples_jsonl: Path,
    output_dir: Path,
    mode: str = "partial",
    run_type: str = "synthetic_smoke",
    config_path: Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    if mode not in {"partial", "final"}:
        raise ValueError("mode must be partial or final")
    if run_type not in RUN_TYPES:
        raise ValueError(f"run_type must be one of {sorted(RUN_TYPES)}")

    config = load_model_config(config_path)
    model_roles = {row["model_id"]: row["role"] for row in config["models"]}
    model_formulas = {row["model_id"]: row["formula"] for row in config["models"]}
    expected_inference_mode = "smoke_test" if run_type == "synthetic_smoke" else "production"
    if mode == "final" and run_type == "production":
        expected_inference_mode = "production"

    candidate_rows = load_csv(fit_output_dir / "candidate_predictions.csv") if (fit_output_dir / "candidate_predictions.csv").exists() else []
    trial_rows = load_csv(fit_output_dir / "trial_prediction_summary.csv") if (fit_output_dir / "trial_prediction_summary.csv").exists() else []
    diagnostic_rows = load_csv(fit_output_dir / "fit_diagnostics.csv") if (fit_output_dir / "fit_diagnostics.csv").exists() else []
    manifest_rows = load_csv(fit_manifest_csv)
    prediction_examples = load_jsonl(prediction_examples_jsonl)

    failures: dict[str, list[str]] = defaultdict(list)
    warnings: dict[str, list[str]] = defaultdict(list)
    leakage_failures = detect_forbidden_fields(candidate_rows, "candidate_predictions", failures)
    leakage_failures += detect_forbidden_fields(trial_rows, "trial_prediction_summary", failures)
    leakage_failures += detect_forbidden_fields(diagnostic_rows, "fit_diagnostics", failures)

    example_lookup = build_prediction_example_lookup(prediction_examples)
    manifest_by_key = keyed_unique(manifest_rows, failures, "fit_manifest")
    candidates_by_key = group_rows(candidate_rows)
    trials_by_key = group_rows(trial_rows)
    diagnostics_by_key = group_rows(diagnostic_rows)
    output_keys = set(candidates_by_key) | set(trials_by_key) | set(diagnostics_by_key)
    for key in sorted(output_keys - set(manifest_by_key)):
        failures["manifest"].append(f"{format_key(key)} appears in outputs but is absent from fit manifest.")

    if mode == "final" and run_type == "production" and output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty final production output directory: {output_dir}")

    configuration_snapshot = fit_output_dir / "configuration_snapshot.json"
    configuration_hash = snapshot_hash(configuration_snapshot)
    if not configuration_snapshot.exists():
        failures["configuration"].append("Missing configuration_snapshot.json for consolidated run.")
    validate_configuration(
        config=config,
        manifest_rows=manifest_rows,
        diagnostic_rows=diagnostic_rows,
        expected_inference_mode=expected_inference_mode,
        model_formulas=model_formulas,
        failures=failures,
    )

    canonical_candidates: list[dict[str, Any]] = []
    canonical_trials: list[dict[str, Any]] = []
    consolidated_diagnostics: list[dict[str, Any]] = []
    completion_manifest: list[dict[str, Any]] = []

    duplicate_candidate_rows = count_duplicate_rows(candidate_rows, ["prediction_example_id", "baseline_model", "presentation_label"])
    duplicate_trial_rows = count_duplicate_rows(trial_rows, ["prediction_example_id", "baseline_model"])
    duplicate_diagnostic_rows = count_duplicate_rows(diagnostic_rows, ["prediction_example_id", "baseline_model"])

    for key, manifest in sorted(manifest_by_key.items()):
        prediction_example_id, baseline_model = key
        role = model_roles.get(baseline_model, manifest.get("role", ""))
        key_failures: list[str] = []
        key_warnings: list[str] = []
        key_candidates = sorted(candidates_by_key.get(key, []), key=lambda row: EXPECTED_LABELS.index(row["presentation_label"]) if row.get("presentation_label") in EXPECTED_LABELS else 99)
        key_trials = trials_by_key.get(key, [])
        key_diagnostics = diagnostics_by_key.get(key, [])
        diagnostic = key_diagnostics[0] if key_diagnostics else {}
        fit_status = diagnostic.get("fit_status", "")

        validate_phase6b_alignment(manifest, key_candidates, example_lookup, key_failures)
        if len(key_diagnostics) != 1:
            key_failures.append(f"Expected exactly one diagnostic row, found {len(key_diagnostics)}.")
        if len(key_trials) > 1:
            key_failures.append(f"Expected at most one trial summary row, found {len(key_trials)}.")
        if fit_status == "fit_failed":
            key_failures.append("Fit failed; no evaluation-ready prediction will be emitted.")
        if fit_status == "convergence_warning":
            key_warnings.append("Fit completed with convergence_warning; retained as structurally completed.")
        if not fit_status:
            key_failures.append("Missing diagnostic fit_status.")

        completed_status = fit_status in {"fit_ok", "convergence_warning"}
        if completed_status:
            validate_candidate_block(key_candidates, key_failures)
            if len(key_trials) != 1:
                key_failures.append(f"Expected exactly one trial summary for completed fit, found {len(key_trials)}.")
            else:
                validate_trial_consistency(key_candidates, key_trials[0], key_failures)
            if not key_failures:
                for row in key_candidates:
                    canonical_candidates.append(canonical_candidate_row(row, role, diagnostic, config))
                canonical_trial = canonical_trial_row(key_trials[0], role, diagnostic, config)
                canonical_trials.append(canonical_trial)
        elif fit_status != "fit_failed":
            key_failures.append("Fit output is missing or incomplete.")

        if diagnostic:
            consolidated_diagnostics.append(canonical_diagnostic_row(diagnostic, role))

        for failure in key_failures:
            failures[format_key(key)].append(failure)
        for warning in key_warnings:
            warnings[format_key(key)].append(warning)

        global_key_failures = list(failures.get(format_key(key), []))
        output_validated = completed_status and not key_failures and not global_key_failures
        completion_manifest.append(
            {
                "prediction_example_id": prediction_example_id,
                "participant_id": manifest.get("participant_id", ""),
                "trial_id": manifest.get("trial_id", ""),
                "baseline_model": baseline_model,
                "model_role": role,
                "expected": True,
                "completed": completed_status,
                "missing": not diagnostic,
                "warning": fit_status == "convergence_warning",
                "failed": fit_status == "fit_failed",
                "candidate_rows": len(key_candidates),
                "trial_summary_rows": len(key_trials),
                "diagnostic_rows": len(key_diagnostics),
                "output_validated": output_validated,
                "validation_failures": json.dumps(key_failures + global_key_failures, separators=(",", ":")),
                "fit_status": fit_status,
                "protocol_version": diagnostic.get("protocol_version", manifest.get("protocol_version", "")),
                "inference_mode": diagnostic.get("inference_mode", manifest.get("inference_mode", "")),
            }
        )

    canonical_candidates = sort_rows(canonical_candidates, candidate_sort_key)
    canonical_trials = sort_rows(canonical_trials, trial_sort_key)
    consolidated_diagnostics = sort_rows(consolidated_diagnostics, trial_sort_key)
    completion_manifest = sort_rows(completion_manifest, trial_sort_key)
    evaluation_ready = [
        {field: row.get(field, "") for field in EVALUATION_READY_COLUMNS}
        for row in canonical_trials
    ]

    leakage_failures += detect_forbidden_fields(canonical_candidates, "canonical_candidate_predictions", failures)
    leakage_failures += detect_forbidden_fields(canonical_trials, "canonical_trial_predictions", failures)
    leakage_failures += detect_forbidden_fields(evaluation_ready, "evaluation_ready_predictions", failures)

    primary_rows = [row for row in completion_manifest if row["model_role"] == "primary"]
    sensitivity_rows = [row for row in completion_manifest if row["model_role"] == "sensitivity"]
    primary_failures = [row for row in primary_rows if row["failed"] or row["missing"] or not row["output_validated"]]
    has_validation_failures = any(failures.values())
    baseline_primary_complete = bool(primary_rows) and not primary_failures and not leakage_failures and not has_validation_failures
    production_complete = bool(baseline_primary_complete and run_type == "production" and mode == "final")
    if mode == "final" and run_type == "production":
        smoke_modes = {row.get("inference_mode", "") for row in completion_manifest}
        if smoke_modes != {"production"}:
            failures["run_type"].append("Final production consolidation requires production inference-mode outputs only.")
            production_complete = False
            baseline_primary_complete = False

    qc_summary = {
        "schema_version": CONSOLIDATION_VERSION,
        "protocol_version": config["protocol_version"],
        "run_type": run_type,
        "mode": mode,
        "prediction_quantity": config.get("prediction_quantity", PREDICTION_QUANTITY),
        "credible_interval_level": config.get("credible_interval_level", DEFAULT_INTERVAL_LEVEL),
        "configuration_snapshot_hash": configuration_hash,
        "expected_primary_fits": len(primary_rows),
        "completed_primary_fits": sum(1 for row in primary_rows if row["completed"]),
        "warning_primary_fits": sum(1 for row in primary_rows if row["warning"]),
        "failed_primary_fits": sum(1 for row in primary_rows if row["failed"]),
        "missing_primary_fits": sum(1 for row in primary_rows if row["missing"]),
        "expected_sensitivity_fits": len(sensitivity_rows),
        "completed_sensitivity_fits": sum(1 for row in sensitivity_rows if row["completed"]),
        "candidate_prediction_rows": len(canonical_candidates),
        "trial_summary_rows": len(canonical_trials),
        "diagnostic_rows": len(consolidated_diagnostics),
        "duplicate_rows": duplicate_candidate_rows + duplicate_trial_rows + duplicate_diagnostic_rows,
        "a_e_completeness_failures": count_failures(failures, "A-E"),
        "probability_sum_failures": count_failures(failures, "probability"),
        "preferred_mix_consistency_failures": count_failures(failures, "preferred"),
        "candidate_trial_consistency_failures": count_failures(failures, "trial summary"),
        "phase6b_alignment_failures": count_failures(failures, "Phase 6B"),
        "leakage_failures": leakage_failures,
        "configuration_failures": count_failures(failures, "configuration") + count_failures(failures, "inference"),
        "validation_failure_count": sum(len(values) for values in failures.values()),
        "validation_warning_count": sum(len(values) for values in warnings.values()),
        "synthetic_structural_validation": "PASS" if run_type == "synthetic_smoke" and not primary_failures and not leakage_failures else "FAIL",
        "BASELINE_PRIMARY_OUTPUTS_COMPLETE": baseline_primary_complete,
        "production_complete": production_complete,
        "contains_final_performance": False,
        "failures": dict(sorted(failures.items())),
        "warnings": dict(sorted(warnings.items())),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "phase6c_canonical_candidate_predictions.csv", canonical_candidates, CANONICAL_CANDIDATE_COLUMNS)
    write_csv(output_dir / "phase6c_canonical_trial_predictions.csv", canonical_trials, CANONICAL_TRIAL_COLUMNS)
    write_csv(output_dir / "phase6c_consolidated_fit_diagnostics.csv", consolidated_diagnostics, CONSOLIDATED_DIAGNOSTIC_COLUMNS)
    write_csv(output_dir / "phase6c_completion_manifest.csv", completion_manifest, COMPLETION_MANIFEST_COLUMNS)
    write_csv(output_dir / "phase6f_evaluation_ready_baseline_predictions.csv", evaluation_ready, EVALUATION_READY_COLUMNS)
    write_json(output_dir / "phase6c_baseline_output_qc_summary.json", qc_summary)
    (output_dir / "phase6c_baseline_output_summary.md").write_text(render_markdown_summary(qc_summary, output_dir), encoding="utf-8")

    if mode == "final" and not baseline_primary_complete:
        qc_summary["exit_code"] = 1
    else:
        qc_summary["exit_code"] = 0
    return qc_summary


def validate_candidate_block(rows: list[dict[str, Any]], failures: list[str]) -> None:
    labels = [row.get("presentation_label", "") for row in rows]
    if labels != EXPECTED_LABELS:
        failures.append(f"A-E completeness failure: expected {EXPECTED_LABELS}, found {labels}.")
    if len(labels) != len(set(labels)):
        failures.append("Duplicate candidate label within completed fit.")
    if len(rows) != 5:
        failures.append(f"Expected exactly five candidate rows for completed fit, found {len(rows)}.")
        return
    parent_keys = {(row.get("prediction_example_id"), row.get("baseline_model"), row.get("participant_id"), row.get("trial_id")) for row in rows}
    if len(parent_keys) != 1:
        failures.append("Candidate predictions do not all link to the same target/model.")
    probabilities = [to_float(row.get("posterior_winning_probability")) for row in rows]
    if any(value is None for value in probabilities):
        failures.append("Candidate probability missing or non-numeric.")
        return
    numeric = [float(value) for value in probabilities if value is not None]
    if any(value < 0 or value > 1 for value in numeric):
        failures.append("Candidate probability outside [0, 1].")
    if abs(sum(numeric) - 1.0) > PROBABILITY_TOLERANCE:
        failures.append(f"Candidate winning probabilities sum to {sum(numeric)}, not 1.")


def validate_trial_consistency(candidates: list[dict[str, Any]], trial: dict[str, Any], failures: list[str]) -> None:
    if len(candidates) != 5:
        return
    for label in EXPECTED_LABELS:
        candidate = next(row for row in candidates if row["presentation_label"] == label)
        if not numeric_equal(candidate.get("predicted_mean_rating"), trial.get(f"predicted_rating_{label}")):
            failures.append(f"Candidate/trial summary rating mismatch for {label}.")
        if not numeric_equal(candidate.get("posterior_winning_probability"), trial.get(f"posterior_win_probability_{label}")):
            failures.append(f"Candidate/trial summary winning-probability mismatch for {label}.")
    ratings = {row["presentation_label"]: float(row["predicted_mean_rating"]) for row in candidates}
    expected_winner = derive_baseline_winner(ratings)
    trial_tie = parse_bool(trial.get("is_predicted_tie"))
    if str(trial.get("predicted_preferred_mix", "")) != str(expected_winner["predicted_preferred_mix"]):
        failures.append("Predicted preferred mix does not match highest posterior mean.")
    if trial_tie != bool(expected_winner["is_predicted_tie"]):
        failures.append("Predicted tie flag does not match posterior-mean tie rule.")
    if str(trial.get("predicted_tied_labels", "")) != str(expected_winner["predicted_tied_labels"]):
        failures.append("Predicted tied-label set does not match posterior-mean tie rule.")


def validate_phase6b_alignment(
    manifest: dict[str, Any],
    candidates: list[dict[str, Any]],
    example_lookup: dict[str, dict[str, Any]],
    failures: list[str],
) -> None:
    prediction_example_id = manifest["prediction_example_id"]
    if prediction_example_id not in example_lookup:
        failures.append("Phase 6B alignment failure: prediction_example_id not found.")
        return
    example = example_lookup[prediction_example_id]
    target = example["input_data"]["target"]
    if str(example.get("participant_id")) != str(manifest.get("participant_id")):
        failures.append("Phase 6B alignment failure: participant_id mismatch.")
    if str(target.get("trial_id")) != str(manifest.get("trial_id")):
        failures.append("Phase 6B alignment failure: trial_id mismatch.")
    expected_stimuli = {candidate["presentation_label"]: candidate.get("stimulus_id", "") for candidate in target.get("candidates", [])}
    for row in candidates:
        label = row.get("presentation_label", "")
        if label in expected_stimuli and str(row.get("stimulus_id", "")) != str(expected_stimuli[label]):
            failures.append(f"Phase 6B alignment failure: stimulus_id mismatch for {label}.")


def validate_configuration(
    config: dict[str, Any],
    manifest_rows: list[dict[str, Any]],
    diagnostic_rows: list[dict[str, Any]],
    expected_inference_mode: str,
    model_formulas: dict[str, str],
    failures: dict[str, list[str]],
) -> None:
    expected_settings = config["inference_modes"][expected_inference_mode]
    for row in manifest_rows:
        key = format_key((row.get("prediction_example_id", ""), row.get("baseline_model", "")))
        model_id = row.get("baseline_model", "")
        if row.get("protocol_version") != config.get("protocol_version"):
            failures[key].append("Run configuration mismatch: protocol_version differs from config.")
        if row.get("inference_mode") != expected_inference_mode:
            failures[key].append("Run inference mode does not match requested run type.")
        if model_id in model_formulas and row.get("formula") != model_formulas[model_id]:
            failures[key].append("Run configuration mismatch: formula differs from frozen config.")
    for row in diagnostic_rows:
        key = format_key((row.get("prediction_example_id", ""), row.get("baseline_model", "")))
        if row.get("protocol_version") != config.get("protocol_version"):
            failures[key].append("Run configuration mismatch: diagnostic protocol_version differs from config.")
        if row.get("inference_mode") != expected_inference_mode:
            failures[key].append("Run inference mode does not match requested run type.")
        for field in ["draws", "tune", "chains", "target_accept"]:
            if not numeric_equal(row.get(field), expected_settings[field]):
                failures[key].append(f"Run configuration mismatch: {field} differs from config.")
        if str(row.get("sampling_backend", "")) != str(expected_settings["inference_method"]):
            failures[key].append("Run configuration mismatch: sampling backend differs from config.")


def canonical_candidate_row(row: dict[str, Any], role: str, diagnostic: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    return {
        "prediction_example_id": row.get("prediction_example_id", ""),
        "participant_id": row.get("participant_id", ""),
        "trial_id": row.get("trial_id", ""),
        "baseline_model": row.get("baseline_model", ""),
        "model_role": role,
        "presentation_label": row.get("presentation_label", ""),
        "stimulus_id": row.get("stimulus_id", ""),
        "predicted_mean_rating": row.get("predicted_mean_rating", ""),
        "posterior_predictive_mean": row.get("posterior_predictive_mean", ""),
        "posterior_predictive_sd": row.get("posterior_predictive_sd", ""),
        "posterior_expected_ci_lower": row.get("posterior_expected_ci_lower", ""),
        "posterior_expected_ci_upper": row.get("posterior_expected_ci_upper", ""),
        "posterior_winning_probability": row.get("posterior_winning_probability", ""),
        "fit_status": diagnostic.get("fit_status", row.get("fit_status", "")),
        "protocol_version": diagnostic.get("protocol_version", config.get("protocol_version", "")),
    }


def canonical_trial_row(row: dict[str, Any], role: str, diagnostic: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    return {
        "prediction_example_id": row.get("prediction_example_id", ""),
        "participant_id": row.get("participant_id", ""),
        "trial_id": row.get("trial_id", ""),
        "baseline_model": row.get("baseline_model", ""),
        "model_role": role,
        "predicted_preferred_mix": row.get("predicted_preferred_mix", ""),
        "predicted_tie": parse_bool(row.get("is_predicted_tie")),
        "predicted_tied_labels": row.get("predicted_tied_labels", ""),
        "predicted_rating_A": row.get("predicted_rating_A", ""),
        "predicted_rating_B": row.get("predicted_rating_B", ""),
        "predicted_rating_C": row.get("predicted_rating_C", ""),
        "predicted_rating_D": row.get("predicted_rating_D", ""),
        "predicted_rating_E": row.get("predicted_rating_E", ""),
        "winning_probability_A": row.get("posterior_win_probability_A", ""),
        "winning_probability_B": row.get("posterior_win_probability_B", ""),
        "winning_probability_C": row.get("posterior_win_probability_C", ""),
        "winning_probability_D": row.get("posterior_win_probability_D", ""),
        "winning_probability_E": row.get("posterior_win_probability_E", ""),
        "fit_status": diagnostic.get("fit_status", row.get("fit_status", "")),
        "protocol_version": diagnostic.get("protocol_version", config.get("protocol_version", "")),
    }


def canonical_diagnostic_row(row: dict[str, Any], role: str) -> dict[str, Any]:
    result = {field: row.get(field, "") for field in FIT_DIAGNOSTIC_COLUMNS}
    result["model_role"] = role
    return {field: result.get(field, "") for field in CONSOLIDATED_DIAGNOSTIC_COLUMNS}


def keyed_unique(rows: list[dict[str, Any]], failures: dict[str, list[str]], name: str) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    counts = Counter((row.get("prediction_example_id", ""), row.get("baseline_model", "")) for row in rows)
    for key, count in counts.items():
        if count > 1:
            failures[name].append(f"Duplicate fit output for {format_key(key)}.")
    for row in rows:
        key = (row.get("prediction_example_id", ""), row.get("baseline_model", ""))
        if key not in result:
            result[key] = row
    return result


def group_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row.get("prediction_example_id", ""), row.get("baseline_model", ""))].append(row)
    return grouped


def build_prediction_example_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    counts = Counter(row["prediction_example_id"] for row in rows)
    duplicates = [key for key, count in counts.items() if count > 1]
    if duplicates:
        raise ValueError(f"Duplicate Phase 6B prediction examples: {duplicates}")
    return {row["prediction_example_id"]: row for row in rows}


def detect_forbidden_fields(rows: list[dict[str, Any]], source: str, failures: dict[str, list[str]]) -> int:
    if not rows:
        return 0
    fields = set().union(*(row.keys() for row in rows))
    forbidden = sorted(fields & FORBIDDEN_OUTCOME_FIELDS)
    if forbidden:
        failures["leakage"].append(f"{source} contains forbidden observed-outcome fields: {forbidden}.")
    return len(forbidden)


def count_duplicate_rows(rows: list[dict[str, Any]], fields: list[str]) -> int:
    counts = Counter(tuple(row.get(field, "") for field in fields) for row in rows)
    return sum(count - 1 for count in counts.values() if count > 1)


def count_failures(failures: dict[str, list[str]], token: str) -> int:
    token_lower = token.lower()
    return sum(1 for messages in failures.values() for message in messages if token_lower in message.lower())


def sort_rows(rows: list[dict[str, Any]], key_func: Any) -> list[dict[str, Any]]:
    return sorted(rows, key=key_func)


def candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    label = row.get("presentation_label", "")
    return (
        row.get("prediction_example_id", ""),
        row.get("baseline_model", ""),
        EXPECTED_LABELS.index(label) if label in EXPECTED_LABELS else 99,
    )


def trial_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (row.get("prediction_example_id", ""), row.get("baseline_model", ""))


def format_key(key: tuple[str, str]) -> str:
    return f"{key[0]} x {key[1]}"


def to_float(value: Any) -> float | None:
    try:
        if value == "" or value is None:
            return None
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def numeric_equal(left: Any, right: Any, tolerance: float = 1e-10) -> bool:
    left_float = to_float(left)
    right_float = to_float(right)
    if left_float is None or right_float is None:
        return str(left) == str(right)
    return abs(left_float - right_float) <= tolerance


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def snapshot_hash(path: Path) -> str:
    if not path.exists():
        return ""
    content = json.loads(path.read_text(encoding="utf-8"))
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def render_markdown_summary(summary: dict[str, Any], output_dir: Path) -> str:
    label = "Synthetic/test" if summary["run_type"] == "synthetic_smoke" else "Production"
    complete = "true" if summary["BASELINE_PRIMARY_OUTPUTS_COMPLETE"] else "false"
    return "\n".join(
        [
            "# Phase 6C Baseline Output Summary",
            "",
            f"Run class: {label}",
            f"Protocol version: `{summary['protocol_version']}`",
            f"Prediction quantity: `{summary['prediction_quantity']}`",
            f"Mode: `{summary['mode']}`",
            "",
            "## Fit Counts",
            "",
            f"- Expected primary fits: {summary['expected_primary_fits']}",
            f"- Completed primary fits: {summary['completed_primary_fits']}",
            f"- Warning primary fits: {summary['warning_primary_fits']}",
            f"- Failed primary fits: {summary['failed_primary_fits']}",
            f"- Missing primary fits: {summary['missing_primary_fits']}",
            f"- Expected sensitivity fits: {summary['expected_sensitivity_fits']}",
            f"- Completed sensitivity fits: {summary['completed_sensitivity_fits']}",
            "",
            "## Validation",
            "",
            f"- Candidate prediction rows: {summary['candidate_prediction_rows']}",
            f"- Trial summary rows: {summary['trial_summary_rows']}",
            f"- Duplicate rows: {summary['duplicate_rows']}",
            f"- A-E completeness failures: {summary['a_e_completeness_failures']}",
            f"- Probability validation failures: {summary['probability_sum_failures']}",
            f"- Preferred-mix consistency failures: {summary['preferred_mix_consistency_failures']}",
            f"- Candidate/trial consistency failures: {summary['candidate_trial_consistency_failures']}",
            f"- Phase 6B alignment failures: {summary['phase6b_alignment_failures']}",
            f"- Leakage failures: {summary['leakage_failures']}",
            f"- Synthetic structural validation: {summary['synthetic_structural_validation']}",
            f"- `BASELINE_PRIMARY_OUTPUTS_COMPLETE`: `{complete}`",
            "",
            "## Canonical Outputs",
            "",
            f"- `{output_dir / 'phase6c_canonical_candidate_predictions.csv'}`",
            f"- `{output_dir / 'phase6c_canonical_trial_predictions.csv'}`",
            f"- `{output_dir / 'phase6c_consolidated_fit_diagnostics.csv'}`",
            f"- `{output_dir / 'phase6c_completion_manifest.csv'}`",
            f"- `{output_dir / 'phase6f_evaluation_ready_baseline_predictions.csv'}`",
            "",
            "No accuracy, ground-truth scoring, LLM comparison, or dissertation performance metric is reported here.",
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consolidate and validate Phase 6C held-out baseline outputs.")
    parser.add_argument("--fit-output-dir", required=True, type=Path)
    parser.add_argument("--fit-manifest", type=Path, default=None)
    parser.add_argument("--prediction-examples", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--mode", choices=["partial", "final"], default="partial")
    parser.add_argument("--run-type", choices=sorted(RUN_TYPES), default="synthetic_smoke")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = args.fit_manifest or args.fit_output_dir / "fit_manifest.csv"
    summary = consolidate_outputs(
        fit_output_dir=args.fit_output_dir,
        fit_manifest_csv=manifest,
        prediction_examples_jsonl=args.prediction_examples,
        output_dir=args.output_dir,
        mode=args.mode,
        run_type=args.run_type,
        config_path=args.config,
    )
    print(f"Wrote Phase 6C.3 consolidated outputs to {args.output_dir}")
    print(f"expected_primary_fits={summary['expected_primary_fits']}")
    print(f"completed_primary_fits={summary['completed_primary_fits']}")
    print(f"warning_primary_fits={summary['warning_primary_fits']}")
    print(f"failed_primary_fits={summary['failed_primary_fits']}")
    print(f"missing_primary_fits={summary['missing_primary_fits']}")
    print(f"BASELINE_PRIMARY_OUTPUTS_COMPLETE={summary['BASELINE_PRIMARY_OUTPUTS_COMPLETE']}")
    return int(summary.get("exit_code", 0))


if __name__ == "__main__":
    raise SystemExit(main())
