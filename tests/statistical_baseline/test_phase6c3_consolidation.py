import csv
import json
import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_SRC = REPO_ROOT / "statistical-baseline" / "src"
if str(BASELINE_SRC) not in sys.path:
    sys.path.insert(0, str(BASELINE_SRC))

from statistical_baseline.consolidate import (  # noqa: E402
    CANONICAL_CANDIDATE_COLUMNS,
    CANONICAL_TRIAL_COLUMNS,
    COMPLETION_MANIFEST_COLUMNS,
    EVALUATION_READY_COLUMNS,
    FORBIDDEN_OUTCOME_FIELDS,
    consolidate_outputs,
)
from statistical_baseline.heldout import EXPECTED_LABELS, load_csv  # noqa: E402


SMOKE_DIR = REPO_ROOT / "statistical-baseline" / "outputs" / "phase6c2_synthetic_smoke_test"
PREDICTION_EXAMPLES = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6b5" / "final_prediction_examples.jsonl"
CONFIG = REPO_ROOT / "statistical-baseline" / "config" / "phase6c_baseline_models.json"


def test_candidate_outputs_consolidate_correctly(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    summary = run_consolidation(fit_dir, tmp_path / "out")
    rows = load_csv(tmp_path / "out" / "phase6c_canonical_candidate_predictions.csv")
    assert summary["candidate_prediction_rows"] == 10
    assert rows[0].keys() == set(CANONICAL_CANDIDATE_COLUMNS)
    assert [row["presentation_label"] for row in rows[:5]] == EXPECTED_LABELS
    assert {row["model_role"] for row in rows} == {"primary"}


def test_trial_summaries_consolidate_correctly(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    run_consolidation(fit_dir, tmp_path / "out")
    rows = load_csv(tmp_path / "out" / "phase6c_canonical_trial_predictions.csv")
    assert len(rows) == 2
    assert rows[0].keys() == set(CANONICAL_TRIAL_COLUMNS)
    assert [row["baseline_model"] for row in rows] == ["categorical_design", "primary_acoustic"]


def test_fit_diagnostics_and_manifest_counts_consolidate_correctly(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    summary = run_consolidation(fit_dir, tmp_path / "out")
    diagnostics = load_csv(tmp_path / "out" / "phase6c_consolidated_fit_diagnostics.csv")
    manifest = load_csv(tmp_path / "out" / "phase6c_completion_manifest.csv")
    assert len(diagnostics) == 2
    assert len(manifest) == 2
    assert manifest[0].keys() == set(COMPLETION_MANIFEST_COLUMNS)
    assert summary["expected_primary_fits"] == 2
    assert summary["completed_primary_fits"] == 2


def test_exactly_five_a_to_e_rows_required_per_completed_fit(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    rows = read_csv(fit_dir / "candidate_predictions.csv")
    write_csv(fit_dir / "candidate_predictions.csv", rows[:-1])
    summary = run_consolidation(fit_dir, tmp_path / "out")
    assert summary["a_e_completeness_failures"] >= 1
    assert summary["BASELINE_PRIMARY_OUTPUTS_COMPLETE"] is False


def test_duplicate_candidate_label_detected(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    rows = read_csv(fit_dir / "candidate_predictions.csv")
    duplicate = dict(rows[0])
    rows.insert(1, duplicate)
    write_csv(fit_dir / "candidate_predictions.csv", rows)
    summary = run_consolidation(fit_dir, tmp_path / "out")
    assert summary["duplicate_rows"] >= 1
    assert summary["a_e_completeness_failures"] >= 1


def test_winning_probabilities_sum_to_one(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    rows = read_csv(fit_dir / "candidate_predictions.csv")
    rows[0]["posterior_winning_probability"] = "0.9"
    write_csv(fit_dir / "candidate_predictions.csv", rows)
    summary = run_consolidation(fit_dir, tmp_path / "out")
    assert summary["probability_sum_failures"] >= 1


def test_invalid_probability_range_detected(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    rows = read_csv(fit_dir / "candidate_predictions.csv")
    rows[0]["posterior_winning_probability"] = "1.2"
    write_csv(fit_dir / "candidate_predictions.csv", rows)
    summary = run_consolidation(fit_dir, tmp_path / "out")
    assert summary["probability_sum_failures"] >= 1
    assert any("outside [0, 1]" in message for messages in summary["failures"].values() for message in messages)


def test_preferred_mix_matches_highest_posterior_mean(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    rows = read_csv(fit_dir / "trial_prediction_summary.csv")
    rows[0]["predicted_preferred_mix"] = "A"
    write_csv(fit_dir / "trial_prediction_summary.csv", rows)
    summary = run_consolidation(fit_dir, tmp_path / "out")
    assert summary["preferred_mix_consistency_failures"] >= 1


def test_exact_predicted_tie_preserved(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    candidates = read_csv(fit_dir / "candidate_predictions.csv")
    for row in candidates:
        if row["baseline_model"] == "categorical_design" and row["presentation_label"] in {"A", "B"}:
            row["predicted_mean_rating"] = "50"
            row["posterior_predictive_mean"] = "50"
        elif row["baseline_model"] == "categorical_design":
            row["predicted_mean_rating"] = "40"
            row["posterior_predictive_mean"] = "40"
    write_csv(fit_dir / "candidate_predictions.csv", candidates)
    trials = read_csv(fit_dir / "trial_prediction_summary.csv")
    trials[0].update(
        {
            "predicted_rating_A": "50",
            "predicted_rating_B": "50",
            "predicted_rating_C": "40",
            "predicted_rating_D": "40",
            "predicted_rating_E": "40",
            "predicted_preferred_mix": "",
            "is_predicted_tie": "True",
            "predicted_tied_labels": "[\"A\",\"B\"]",
        }
    )
    write_csv(fit_dir / "trial_prediction_summary.csv", trials)
    summary = run_consolidation(fit_dir, tmp_path / "out")
    rows = load_csv(tmp_path / "out" / "phase6f_evaluation_ready_baseline_predictions.csv")
    assert summary["preferred_mix_consistency_failures"] == 0
    assert rows[0]["predicted_tie"] == "True"
    assert rows[0]["predicted_preferred_mix"] == ""


def test_candidate_trial_prediction_values_must_match(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    rows = read_csv(fit_dir / "trial_prediction_summary.csv")
    rows[0]["predicted_rating_A"] = "999"
    write_csv(fit_dir / "trial_prediction_summary.csv", rows)
    summary = run_consolidation(fit_dir, tmp_path / "out")
    assert summary["candidate_trial_consistency_failures"] >= 1


def test_phase6b_target_alignment_validated(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    rows = read_csv(fit_dir / "candidate_predictions.csv")
    rows[0]["stimulus_id"] = "wrong_stimulus"
    write_csv(fit_dir / "candidate_predictions.csv", rows)
    summary = run_consolidation(fit_dir, tmp_path / "out")
    assert summary["phase6b_alignment_failures"] >= 1


def test_forbidden_observed_outcome_field_detected(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    rows = read_csv(fit_dir / "candidate_predictions.csv")
    for row in rows:
        row["human_rating"] = ""
    write_csv(fit_dir / "candidate_predictions.csv", rows)
    summary = run_consolidation(fit_dir, tmp_path / "out")
    assert summary["leakage_failures"] >= 1


def test_deterministic_ordering_and_repeated_consolidation(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    rows = list(reversed(read_csv(fit_dir / "candidate_predictions.csv")))
    write_csv(fit_dir / "candidate_predictions.csv", rows)
    run_consolidation(fit_dir, tmp_path / "out1")
    run_consolidation(fit_dir, tmp_path / "out2")
    first = (tmp_path / "out1" / "phase6f_evaluation_ready_baseline_predictions.csv").read_text(encoding="utf-8")
    second = (tmp_path / "out2" / "phase6f_evaluation_ready_baseline_predictions.csv").read_text(encoding="utf-8")
    assert first == second
    rows = load_csv(tmp_path / "out1" / "phase6c_canonical_candidate_predictions.csv")
    assert [row["presentation_label"] for row in rows[:5]] == EXPECTED_LABELS


def test_warning_fit_retained(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    summary = run_consolidation(fit_dir, tmp_path / "out")
    eval_rows = load_csv(tmp_path / "out" / "phase6f_evaluation_ready_baseline_predictions.csv")
    assert summary["warning_primary_fits"] == 2
    assert len(eval_rows) == 2
    assert {row["fit_status"] for row in eval_rows} == {"convergence_warning"}


def test_failed_fit_handled_without_fabricated_evaluation_row(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    diagnostics = read_csv(fit_dir / "fit_diagnostics.csv")
    diagnostics[0]["fit_status"] = "fit_failed"
    write_csv(fit_dir / "fit_diagnostics.csv", diagnostics)
    summary = run_consolidation(fit_dir, tmp_path / "out")
    eval_rows = load_csv(tmp_path / "out" / "phase6f_evaluation_ready_baseline_predictions.csv")
    assert summary["failed_primary_fits"] == 1
    assert len(eval_rows) == 1


def test_partial_mode_permits_incomplete_qc_output(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    (fit_dir / "trial_prediction_summary.csv").unlink()
    summary = run_consolidation(fit_dir, tmp_path / "out", mode="partial")
    assert summary["exit_code"] == 0
    assert summary["BASELINE_PRIMARY_OUTPUTS_COMPLETE"] is False
    assert (tmp_path / "out" / "phase6c_completion_manifest.csv").exists()


def test_final_mode_fails_on_missing_primary_fit(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    (fit_dir / "trial_prediction_summary.csv").unlink()
    summary = run_consolidation(fit_dir, tmp_path / "out", mode="final")
    assert summary["exit_code"] == 1
    assert summary["BASELINE_PRIMARY_OUTPUTS_COMPLETE"] is False


def test_run_configuration_mismatch_detected(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    diagnostics = read_csv(fit_dir / "fit_diagnostics.csv")
    diagnostics[0]["draws"] = "6"
    write_csv(fit_dir / "fit_diagnostics.csv", diagnostics)
    summary = run_consolidation(fit_dir, tmp_path / "out")
    assert summary["configuration_failures"] >= 1


def test_smoke_production_mixing_rejected(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    summary = run_consolidation(fit_dir, tmp_path / "out", mode="final", run_type="production")
    assert summary["exit_code"] == 1
    assert summary["BASELINE_PRIMARY_OUTPUTS_COMPLETE"] is False


def test_evaluation_ready_output_contains_predictions_only(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    run_consolidation(fit_dir, tmp_path / "out")
    rows = load_csv(tmp_path / "out" / "phase6f_evaluation_ready_baseline_predictions.csv")
    assert set(rows[0]) == set(EVALUATION_READY_COLUMNS)
    assert not (set(rows[0]) & FORBIDDEN_OUTCOME_FIELDS)


def test_missing_manifest_fit_detected(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    manifest = read_csv(fit_dir / "fit_manifest.csv")
    write_csv(fit_dir / "fit_manifest.csv", manifest[:1])
    summary = run_consolidation(fit_dir, tmp_path / "out")
    assert summary["BASELINE_PRIMARY_OUTPUTS_COMPLETE"] is False
    assert any("absent from fit manifest" in message for messages in summary["failures"].values() for message in messages)


def test_duplicate_fit_output_detected(tmp_path):
    fit_dir = copy_smoke_outputs(tmp_path)
    trials = read_csv(fit_dir / "trial_prediction_summary.csv")
    trials.append(dict(trials[0]))
    write_csv(fit_dir / "trial_prediction_summary.csv", trials)
    summary = run_consolidation(fit_dir, tmp_path / "out")
    assert summary["duplicate_rows"] >= 1
    assert summary["BASELINE_PRIMARY_OUTPUTS_COMPLETE"] is False


def test_evaluation_ready_schema_documents_predictions_only():
    schema = load_csv(REPO_ROOT / "statistical-baseline" / "schema" / "phase6f_evaluation_ready_baseline_prediction_schema.csv")
    assert [row["column_name"] for row in schema] == EVALUATION_READY_COLUMNS
    assert all(row["protocol_version"] == "phase6c_baseline_prediction_v1" for row in schema)
    assert "observed_preferred_mix" not in [row["column_name"] for row in schema]


def copy_smoke_outputs(tmp_path):
    target = tmp_path / "fit_outputs"
    shutil.copytree(SMOKE_DIR, target)
    return target


def run_consolidation(fit_dir, output_dir, mode="partial", run_type="synthetic_smoke"):
    return consolidate_outputs(
        fit_output_dir=fit_dir,
        fit_manifest_csv=fit_dir / "fit_manifest.csv",
        prediction_examples_jsonl=PREDICTION_EXAMPLES,
        output_dir=output_dir,
        mode=mode,
        run_type=run_type,
        config_path=CONFIG,
    )


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows):
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
