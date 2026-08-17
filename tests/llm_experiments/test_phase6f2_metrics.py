import csv
import json
import math
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.evaluation.metrics import (  # noqa: E402
    DEFAULT_OUTPUT_DIR,
    NON_SCIENTIFIC_NOTICE,
    PHASE6F_METRIC_PROTOCOL_VERSION,
    aggregate_metrics,
    controlled_metric_validation,
    derive_canonical_prediction,
    derive_tie_aware_ranks,
    run_phase6f2_metrics,
    score_baseline_predictions,
    score_llm_predictions,
    score_rating_errors,
    score_spearman,
    score_top1,
    validate_ground_truth,
)
from llm_experiments.inference.records import sha256_file  # noqa: E402


OUT = REPO_ROOT / DEFAULT_OUTPUT_DIR


def test_prediction_to_ground_truth_join_by_id():
    scored = score_llm_predictions([llm_row("ex1", "A")], [truth_row("ex1", ["A"])], [alignment_row("ex1")])
    assert scored[0]["prediction_example_id"] == "ex1"
    assert scored[0]["observed_preferred_set"] == '["A"]'


def test_duplicate_ground_truth_rejected():
    try:
        validate_ground_truth([truth_row("ex1", ["A"]), truth_row("ex1", ["B"])])
    except ValueError as exc:
        assert "Duplicate ground truth" in str(exc)
    else:
        raise AssertionError("duplicate ground truth was accepted")


def test_missing_ground_truth_detected():
    scored = score_llm_predictions([llm_row("ex_missing", "A")], [], [])
    assert scored[0]["invalid_failure_category"] == "missing_ground_truth"
    assert scored[0]["scorable_prediction"] == "false"


def test_unique_winner_top1_correctness():
    assert score_top1("C", ["C"])
    assert not score_top1("B", ["C"])


def test_two_way_human_tie_membership():
    assert score_top1("A", ["A", "C"])
    assert score_top1("C", ["A", "C"])
    assert not score_top1("B", ["A", "C"])


def test_multi_way_tie_membership():
    assert score_top1("A", ["A", "C", "E"])
    assert score_top1("E", ["A", "C", "E"])
    assert not score_top1("D", ["A", "C", "E"])


def test_all_five_tie_behavior():
    assert all(score_top1(label, ["A", "B", "C", "D", "E"]) for label in ["A", "B", "C", "D", "E"])


def test_canonical_predicted_winner_from_highest_rating():
    canonical = derive_canonical_prediction(llm_row("ex1", "B", ratings=[1, 90, 3, 4, 5], ranking=["B", "E", "D", "C", "A"]))
    assert canonical["canonical_predicted_preferred_mix"] == "B"
    assert canonical["predicted_rating_tie"] is False


def test_predicted_rating_tie_resolved_by_explicit_ranking():
    canonical = derive_canonical_prediction(llm_row("ex1", "A", ratings=[80, 2, 80, 1, 0], ranking=["C", "A", "B", "D", "E"]))
    assert canonical["canonical_predicted_preferred_mix"] == "C"
    assert canonical["predicted_rating_tie"] is True


def test_no_ground_truth_tiebreak_used_for_prediction_ties():
    prediction = llm_row("ex1", "A", ratings=[80, 2, 80, 1, 0], ranking=["C", "A", "B", "D", "E"])
    scored = score_llm_predictions([prediction], [truth_row("ex1", ["A"])], [alignment_row("ex1")])
    assert scored[0]["canonical_predicted_preferred_mix"] == "C"
    assert scored[0]["top1_correct"] == "false"


def test_valid_primary_scoring():
    scored = score_llm_predictions([llm_row("ex1", "A", status="valid_primary")], [truth_row("ex1", ["A"])], [alignment_row("ex1")])
    assert scored[0]["scorable_prediction"] == "true"


def test_valid_after_repair_scoring():
    scored = score_llm_predictions([llm_row("ex1", "A", status="valid_after_repair")], [truth_row("ex1", ["A"])], [alignment_row("ex1")])
    assert scored[0]["scorable_prediction"] == "true"


def test_invalid_after_repair_strict_denominator_handling():
    scored = score_llm_predictions([llm_row("ex1", "A", status="invalid_after_repair")], [truth_row("ex1", ["A"])], [alignment_row("ex1")])
    summary = aggregate_metrics(scored, ["model_key", "condition"])[0]
    assert scored[0]["scorable_prediction"] == "false"
    assert summary["expected_predictions"] == 1
    assert float(summary["strict_top1_accuracy"]) == 0


def test_backend_failed_strict_denominator_handling():
    scored = score_llm_predictions([llm_row("ex1", "A", status="backend_failed")], [truth_row("ex1", ["A"])], [alignment_row("ex1")])
    summary = aggregate_metrics(scored, ["model_key", "condition"])[0]
    assert scored[0]["invalid_failure_category"] == "backend_failed"
    assert summary["backend_failure_count"] == 1
    assert float(summary["strict_top1_accuracy"]) == 0


def test_missing_expected_prediction_handling():
    scored = score_llm_predictions([], [truth_row("ex1", ["A"])], [alignment_row("ex1")])
    assert scored[0]["invalid_failure_category"] == "missing_not_run"
    assert scored[0]["strict_denominator_includes_record"] == "true"


def test_valid_only_diagnostic_denominator():
    scored = score_llm_predictions(
        [
            llm_row("ex1", "A"),
            llm_row("ex2", "B", ratings=[10, 100, 60, 40, 20], ranking=["B", "C", "D", "E", "A"]),
            llm_row("ex3", "A", status="invalid_after_repair"),
        ],
        [truth_row("ex1", ["A"]), truth_row("ex2", ["A"]), truth_row("ex3", ["A"])],
        [alignment_row("ex1"), alignment_row("ex2"), alignment_row("ex3")],
    )
    summary = aggregate_metrics(scored, ["model_key", "condition"])[0]
    assert math.isclose(float(summary["strict_top1_accuracy"]), 1 / 3)
    assert math.isclose(float(summary["valid_only_diagnostic_accuracy"]), 1 / 2)


def test_mae_exact_fixture():
    observed = dict(zip(["A", "B", "C", "D", "E"], [0, 25, 50, 75, 100], strict=True))
    predicted = dict(zip(["A", "B", "C", "D", "E"], [10, 20, 40, 80, 90], strict=True))
    assert score_rating_errors(predicted, observed)["mae"] == 8


def test_rmse_exact_fixture():
    observed = dict(zip(["A", "B", "C", "D", "E"], [0, 25, 50, 75, 100], strict=True))
    predicted = dict(zip(["A", "B", "C", "D", "E"], [10, 20, 40, 80, 90], strict=True))
    assert math.isclose(score_rating_errors(predicted, observed)["rmse"], math.sqrt(70))


def test_perfect_spearman():
    ranks = derive_tie_aware_ranks({"A": 5, "B": 4, "C": 3, "D": 2, "E": 1})
    assert math.isclose(score_spearman(ranks, ranks)["spearman"], 1)


def test_reverse_spearman():
    observed = derive_tie_aware_ranks({"A": 5, "B": 4, "C": 3, "D": 2, "E": 1})
    predicted = derive_tie_aware_ranks({"A": 1, "B": 2, "C": 3, "D": 4, "E": 5})
    assert math.isclose(score_spearman(observed, predicted)["spearman"], -1)


def test_tie_aware_spearman():
    observed = {"A": 1.0, "B": 2.5, "C": 2.5, "D": 4.0, "E": 5.0}
    predicted = {"A": 1.5, "B": 1.5, "C": 3.0, "D": 4.0, "E": 5.0}
    assert math.isclose(score_spearman(observed, predicted)["spearman"], 0.9210526315789473)


def test_constant_human_rank_undefined():
    result = score_spearman({"A": 3, "B": 3, "C": 3, "D": 3, "E": 3}, derive_tie_aware_ranks({"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}))
    assert result["spearman"] is None
    assert result["spearman_undefined_reason"] == "observed_rank_constant"


def test_constant_predicted_rank_undefined():
    result = score_spearman(derive_tie_aware_ranks({"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}), {"A": 3, "B": 3, "C": 3, "D": 3, "E": 3})
    assert result["spearman"] is None
    assert result["spearman_undefined_reason"] == "predicted_rank_constant"


def test_continuous_coverage_counts():
    scored = score_llm_predictions(
        [llm_row("ex1", "A"), llm_row("ex2", "A", status="invalid_after_repair")],
        [truth_row("ex1", ["A"]), truth_row("ex2", ["A"])],
        [alignment_row("ex1"), alignment_row("ex2")],
    )
    summary = aggregate_metrics(scored, ["model_key", "condition"])[0]
    assert summary["valid_predictions"] == 1
    assert math.isclose(float(summary["continuous_metric_coverage"]), 0.5)


def test_ranking_coverage_counts():
    scored = score_llm_predictions(
        [llm_row("ex1", "A"), llm_row("ex2", "A", ratings=[1, 1, 1, 1, 1])],
        [truth_row("ex1", ["A"]), truth_row("ex2", ["A"])],
        [alignment_row("ex1"), alignment_row("ex2")],
    )
    summary = aggregate_metrics(scored, ["model_key", "condition"])[0]
    assert summary["undefined_predicted_rank_count"] == 1
    assert math.isclose(float(summary["ranking_metric_coverage"]), 0.5)


def test_baseline_winner_scoring():
    scored = score_baseline_predictions([baseline_row("ex1", "A")], [truth_row("ex1", ["A"])], [alignment_row("ex1", baseline=True)])
    assert scored[0]["top1_correct"] == "true"


def test_convergence_warning_baseline_prediction_retained():
    scored = score_baseline_predictions([baseline_row("ex1", "A", fit_status="convergence_warning")], [truth_row("ex1", ["A"])], [alignment_row("ex1", baseline=True)])
    assert scored[0]["scorable_prediction"] == "true"
    assert scored[0]["fit_status"] == "convergence_warning"


def test_failed_baseline_fit_not_given_fabricated_metric():
    scored = score_baseline_predictions([baseline_row("ex1", "A", fit_status="fit_failed")], [truth_row("ex1", ["A"])], [alignment_row("ex1", baseline=True)])
    assert scored[0]["scorable_prediction"] == "false"
    assert scored[0]["mae"] == ""


def test_participant_level_aggregation_correct():
    scored = score_llm_predictions(
        [
            llm_row("ex1", "A", participant_id="p1"),
            llm_row("ex2", "B", participant_id="p1", ratings=[10, 100, 60, 40, 20], ranking=["B", "C", "D", "E", "A"]),
        ],
        [truth_row("ex1", ["A"], participant_id="p1"), truth_row("ex2", ["A"], participant_id="p1")],
        [alignment_row("ex1"), alignment_row("ex2")],
    )
    participant = aggregate_metrics(scored, ["participant_id", "model_key", "condition"], participant_level=True)[0]
    assert participant["target_trials"] == 2
    assert math.isclose(float(participant["strict_top1_accuracy"]), 0.5)


def test_deterministic_scoring_rerun():
    run_phase6f2_metrics(REPO_ROOT)
    first = {path.name: sha256_file(path) for path in sorted(OUT.glob("*")) if path.is_file()}
    run_phase6f2_metrics(REPO_ROOT)
    second = {path.name: sha256_file(path) for path in sorted(OUT.glob("*")) if path.is_file()}
    assert first == second


def test_synthetic_report_marked_non_scientific():
    run_phase6f2_metrics(REPO_ROOT)
    text = (OUT / "phase6f2_metric_validation_report.md").read_text(encoding="utf-8")
    assert NON_SCIENTIFIC_NOTICE in text
    for prohibited in ["best", "outperform", "superior", "strongest"]:
        assert prohibited not in text.lower()


def test_no_inferential_statistics_produced():
    audit = run_phase6f2_metrics(REPO_ROOT)
    text = (OUT / "phase6f2_metric_validation_report.md").read_text(encoding="utf-8").lower()
    assert audit["no_inferential_statistics_emitted"] is True
    for prohibited in ["confidence interval", "bootstrap distribution", "p-value", "hypothesis test", "bayesian comparison"]:
        assert prohibited in text


def test_phase6f2_pipeline_outputs_and_audit():
    audit = run_phase6f2_metrics(REPO_ROOT)
    assert audit["metric_protocol_version"] == PHASE6F_METRIC_PROTOCOL_VERSION
    assert audit["llm_scoring_complete"] is True
    assert audit["baseline_scoring_complete_for_available_smoke_subset"] is True
    for filename in [
        "scored_llm_predictions.csv",
        "scored_baseline_predictions.csv",
        "llm_metric_summary.csv",
        "baseline_metric_summary.csv",
        "participant_llm_metrics.csv",
        "participant_baseline_metrics.csv",
        "metric_coverage_summary.json",
        "phase6f2_metric_audit.json",
        "phase6f2_metric_validation_report.md",
    ]:
        assert (OUT / filename).exists()


def test_controlled_validation_flags_true():
    validation = controlled_metric_validation()
    for key in [
        "preferred_set_membership_valid",
        "canonical_prediction_derivation_valid",
        "strict_denominator_valid",
        "mae_validated",
        "rmse_validated",
        "tie_aware_rank_validated",
        "spearman_validated",
        "invalid_output_handling_valid",
    ]:
        assert validation[key] is True


def read_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def truth_row(example_id, preferred_set, participant_id="p1", trial_id=None, ratings=None, ranks=None):
    ratings = ratings or [100, 80, 60, 40, 20]
    ranks = ranks or [1, 2, 3, 4, 5]
    trial_id = trial_id or f"{example_id}_trial"
    row = {
        "evaluation_only": "EVALUATION_ONLY_NEVER_MODEL_FACING",
        "prediction_example_id": example_id,
        "participant_id": participant_id,
        "trial_id": trial_id,
        "observed_preferred_mix": preferred_set[0] if len(preferred_set) == 1 else "",
        "observed_preferred_set": json.dumps(preferred_set),
        "is_single_winner": str(len(preferred_set) == 1).lower(),
        "n_preferred_tied": len(preferred_set),
    }
    for label, rating, rank in zip(["A", "B", "C", "D", "E"], ratings, ranks, strict=True):
        row[f"human_rating_{label}"] = rating
        row[f"observed_rank_{label}"] = rank
    return row


def llm_row(example_id, preferred, status="valid_primary", participant_id="p1", trial_id=None, ratings=None, ranking=None):
    ratings = ratings or [100, 80, 60, 40, 20]
    ranking = ranking or ["A", "B", "C", "D", "E"]
    trial_id = trial_id or f"{example_id}_trial"
    row = {
        "prediction_record_id": f"pred_{example_id}",
        "prediction_example_id": example_id,
        "participant_id": participant_id,
        "trial_id": trial_id,
        "condition": "non_history",
        "model_key": "mock_model",
        "exact_model_id": "mock",
        "inference_config_version": "phase6e_primary_inference_config_v1",
        "prompt_package_version": "phase6d_prompt_package_v1",
        "response_schema_version": "preference_prediction_response_v1",
        "predicted_preferred_mix": preferred,
        "predicted_ranking": json.dumps(ranking),
        "final_inference_status": status,
        "repair_used": "false",
    }
    for label, rating in zip(["A", "B", "C", "D", "E"], ratings, strict=True):
        row[f"predicted_rating_{label}"] = rating
    return row


def baseline_row(example_id, preferred, fit_status="fit_ok", participant_id="p1", trial_id=None, ratings=None):
    ratings = ratings or [100, 80, 60, 40, 20]
    trial_id = trial_id or f"{example_id}_trial"
    row = {
        "prediction_example_id": example_id,
        "participant_id": participant_id,
        "trial_id": trial_id,
        "baseline_model": "categorical_design",
        "model_role": "primary",
        "predicted_preferred_mix": preferred,
        "predicted_tie": "False",
        "fit_status": fit_status,
        "protocol_version": "phase6c_baseline_prediction_v1",
    }
    for label, rating in zip(["A", "B", "C", "D", "E"], ratings, strict=True):
        row[f"predicted_rating_{label}"] = rating
        row[f"winning_probability_{label}"] = "0.2"
    return row


def alignment_row(example_id, baseline=False):
    row = {
        "schema_version": "phase6f1_prediction_alignment_manifest_v1",
        "prediction_example_id": example_id,
        "participant_id": "p1",
        "trial_id": f"{example_id}_trial",
        "ground_truth_available": True,
        "categorical_baseline_available": baseline,
        "acoustic_baseline_available": False,
        "mock_model_non_history_available": not baseline,
        "alignment_complete": False,
    }
    return row
