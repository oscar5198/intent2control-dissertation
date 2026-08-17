import csv
import math
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.evaluation.comparisons import (  # noqa: E402
    COMPARISON_NOTICE,
    PHASE6F_COMPARISON_PROTOCOL_VERSION,
    PRODUCTION_BOOTSTRAP_CONFIG,
    TEST_BOOTSTRAP_CONFIG,
    align_history_pairs,
    align_two_systems,
    bootstrap_config,
    build_model_to_model_comparison,
    comparison_identifier,
    compute_paired_comparison,
    controlled_baseline_fixture,
    controlled_comparison_validation,
    controlled_full_coverage_fixture,
    filter_pairs_for_metric,
    participant_cluster_bootstrap,
    paired_difference,
    pooled_strict_accuracy,
    run_phase6f3_comparisons,
    scored_fixture_row,
)
from llm_experiments.inference.records import sha256_file  # noqa: E402


OUT = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6f3_comparisons"


def test_participant_is_bootstrap_cluster_unit():
    rows = fixture_rows_for_bootstrap()
    estimates = participant_cluster_bootstrap(rows, lambda sample: len({row["participant_id"] for row in sample}), 20, 1)
    assert all(estimate <= 2 for estimate in estimates)


def test_repeated_trials_remain_together():
    rows = fixture_rows_for_bootstrap()
    estimates = participant_cluster_bootstrap(rows, lambda sample: sum(1 for row in sample if row["participant_id"] == "P1"), 50, 2)
    assert all(estimate in {0, 2, 4} for estimate in estimates)


def test_repeated_sampled_participant_cluster_not_deduplicated():
    rows = [
        {"participant_id": "P1", "prediction_example_id": "P1_T1", "top1_correct": "true"},
        {"participant_id": "P1", "prediction_example_id": "P1_T2", "top1_correct": "true"},
        {"participant_id": "P2", "prediction_example_id": "P2_T1", "top1_correct": "false"},
    ]
    estimates = participant_cluster_bootstrap(rows, lambda sample: len(sample), 50, 3)
    assert any(estimate > len(rows) for estimate in estimates)


def test_bootstrap_deterministic_with_seed():
    rows = fixture_rows_for_bootstrap()
    first = participant_cluster_bootstrap(rows, pooled_strict_accuracy, 25, 99)
    second = participant_cluster_bootstrap(rows, pooled_strict_accuracy, 25, 99)
    assert first == second


def test_95_ci_produced_for_ok_comparison():
    comparison = full_coverage_accuracy_comparison()
    assert comparison["ci_level"] == 0.95
    assert comparison["ci_lower"] != ""
    assert comparison["ci_upper"] != ""


def test_production_test_bootstrap_modes_separate():
    assert bootstrap_config("production").replicates == 2000
    assert bootstrap_config("test").replicates == 200
    assert PRODUCTION_BOOTSTRAP_CONFIG.replicates != TEST_BOOTSTRAP_CONFIG.replicates


def test_pooled_strict_accuracy_estimand_correct():
    rows = fixture_rows_for_bootstrap()
    assert math.isclose(pooled_strict_accuracy(rows), 0.5)


def test_paired_history_alignment_by_target():
    rows = controlled_full_coverage_fixture()
    pairs = align_history_pairs([row for row in rows if row["model_key"] == "fixture_model"])
    assert len(pairs) == 6
    assert all(pair["a"]["condition"] == "personalised_history" for pair in pairs)
    assert all(pair["b"]["condition"] == "non_history" for pair in pairs)


def test_identical_condition_fixture_zero_effect():
    rows = [row for row in controlled_full_coverage_fixture() if row["model_key"] == "identical_model"]
    pairs = filter_pairs_for_metric(align_history_pairs(rows), "strict_top1_accuracy")
    assert paired_difference(pairs, "strict_top1_accuracy") == 0


def test_controlled_accuracy_improvement_positive_sign():
    comparison = full_coverage_accuracy_comparison()
    assert float(comparison["effect_estimate"]) > 0


def test_mae_difference_sign_convention_negative():
    rows = [row for row in controlled_full_coverage_fixture() if row["model_key"] == "fixture_model"]
    pairs = filter_pairs_for_metric(align_history_pairs(rows), "mae")
    assert paired_difference(pairs, "mae") < 0


def test_rmse_difference_sign_convention_negative():
    rows = [row for row in controlled_full_coverage_fixture() if row["model_key"] == "fixture_model"]
    pairs = filter_pairs_for_metric(align_history_pairs(rows), "rmse")
    assert paired_difference(pairs, "rmse") < 0


def test_ranking_comparison_handles_undefined_values():
    rows = [
        scored_fixture_row("P1", "P1_T1", "m", "non_history", True, 1, 1, None),
        scored_fixture_row("P1", "P1_T1", "m", "personalised_history", True, 1, 1, 0.5),
        scored_fixture_row("P2", "P2_T1", "m", "non_history", True, 1, 1, 0.2),
        scored_fixture_row("P2", "P2_T1", "m", "personalised_history", True, 1, 1, 0.7),
    ]
    pairs = filter_pairs_for_metric(align_history_pairs(rows), "spearman")
    assert len(pairs) == 1


def test_invalid_predictions_inherited_for_strict_accuracy():
    rows = [
        scored_fixture_row("P1", "P1_T1", "m", "non_history", True, 1, 1, 0.5),
        scored_fixture_row("P1", "P1_T1", "m", "personalised_history", False, 1, 1, 0.5),
    ]
    rows[1]["scorable_prediction"] = "false"
    rows[1]["invalid_failure_category"] = "backend_failed"
    pairs = filter_pairs_for_metric(align_history_pairs(rows), "strict_top1_accuracy")
    assert paired_difference(pairs, "strict_top1_accuracy") == -1


def test_coverage_differences_reported():
    rows = [
        scored_fixture_row("P1", "P1_T1", "m", "non_history", True, 1, 1, None),
        scored_fixture_row("P1", "P1_T1", "m", "personalised_history", True, 1, 1, None),
        scored_fixture_row("P2", "P2_T1", "m", "non_history", True, 1, 1, 0.2),
        scored_fixture_row("P2", "P2_T1", "m", "personalised_history", True, 1, 1, 0.7),
    ]
    result = compute_paired_comparison(filter_pairs_for_metric(align_history_pairs(rows), "spearman"), "spearman", TEST_BOOTSTRAP_CONFIG, "personalisation_history_vs_non_history", "m", "personalised_history", "m", "non_history", "", "personalised_history - non_history").result
    assert result["valid_pair_count"] == 1


def test_baseline_comparison_aligned_by_exact_target():
    fixture = controlled_full_coverage_fixture()
    baseline = controlled_baseline_fixture()
    pairs = align_two_systems([row for row in fixture if row["model_key"] == "fixture_model" and row["condition"] == "personalised_history"], baseline)
    assert len(pairs) == 6
    assert all(pair["a"]["prediction_example_id"] == pair["b"]["prediction_example_id"] for pair in pairs)


def test_missing_baseline_target_detected():
    fixture = [row for row in controlled_full_coverage_fixture() if row["model_key"] == "fixture_model" and row["condition"] == "personalised_history"]
    result = compute_paired_comparison([], "strict_top1_accuracy", TEST_BOOTSTRAP_CONFIG, "llm_vs_baseline", "fixture_model", "personalised_history", "mixed_effects_baseline", "", "missing_baseline", "LLM - baseline").result
    assert result["comparison_status"] == "missing_baseline_predictions"


def test_insufficient_participant_count_returns_no_ci():
    pairs = align_history_pairs(
        [
            scored_fixture_row("P1", "P1_T1", "m", "non_history", True, 1, 1, 0.5),
            scored_fixture_row("P1", "P1_T1", "m", "personalised_history", True, 1, 1, 0.7),
            scored_fixture_row("P1", "P1_T2", "m", "non_history", False, 1, 1, 0.5),
            scored_fixture_row("P1", "P1_T2", "m", "personalised_history", True, 1, 1, 0.7),
        ]
    )
    result = compute_paired_comparison(pairs, "strict_top1_accuracy", TEST_BOOTSTRAP_CONFIG, "personalisation_history_vs_non_history", "m", "personalised_history", "m", "non_history", "", "personalised_history - non_history").result
    assert result["comparison_status"] == "insufficient_participants"
    assert result["ci_lower"] == ""


def test_insufficient_aligned_targets_flagged():
    pairs = align_history_pairs(
        [
            scored_fixture_row("P1", "P1_T1", "m", "non_history", True, 1, 1, 0.5),
            scored_fixture_row("P1", "P1_T1", "m", "personalised_history", True, 1, 1, 0.7),
        ]
    )
    result = compute_paired_comparison(pairs, "strict_top1_accuracy", TEST_BOOTSTRAP_CONFIG, "personalisation_history_vs_non_history", "m", "personalised_history", "m", "non_history", "", "personalised_history - non_history").result
    assert result["comparison_status"] == "insufficient_aligned_targets"


def test_participant_level_summaries_correct():
    run_phase6f3_comparisons(REPO_ROOT)
    rows = read_csv(OUT / "participant_personalisation_differences.csv")
    assert rows
    assert all(int(row["matched_target_count"]) > 0 for row in rows)


def test_accuracy_transition_counts_correct():
    pairs = align_history_pairs(
        [
            scored_fixture_row("P1", "P1_T1", "m", "non_history", False, 1, 1, 0.5),
            scored_fixture_row("P1", "P1_T1", "m", "personalised_history", True, 1, 1, 0.7),
        ]
    )
    rows = run_participant_diffs(pairs)
    assert rows[0]["a_correct_b_wrong"] == 1


def test_no_trial_independent_bootstrap_marker():
    audit = run_phase6f3_comparisons(REPO_ROOT)
    assert audit["cluster_unit"] == "participant_id"
    assert audit["no_naive_independence_assumption"] is True


def test_no_naive_independent_t_test_output():
    run_phase6f3_comparisons(REPO_ROOT)
    text = (OUT / "phase6f3_comparison_validation_report.md").read_text(encoding="utf-8").lower()
    assert "independent-sample t-tests" in text


def test_no_p_values_emitted_by_default():
    run_phase6f3_comparisons(REPO_ROOT)
    rows = read_csv(OUT / "personalisation_comparisons.csv") + read_csv(OUT / "llm_vs_baseline_comparisons.csv")
    assert all(row["p_value"] == "" for row in rows)


def test_comparison_ids_deterministic():
    first = comparison_identifier("type", "a", "ca", "b", "cb", "", "mae")
    second = comparison_identifier("type", "a", "ca", "b", "cb", "", "mae")
    assert first == second


def test_protocol_version_recorded():
    result = full_coverage_accuracy_comparison()
    assert result["comparison_protocol_version"] == PHASE6F_COMPARISON_PROTOCOL_VERSION


def test_synthetic_output_labelled_non_scientific():
    run_phase6f3_comparisons(REPO_ROOT)
    rows = read_csv(OUT / "personalisation_comparisons.csv")
    assert all(row["synthetic_comparison_notice"] == COMPARISON_NOTICE for row in rows)
    text = (OUT / "phase6f3_comparison_validation_report.md").read_text(encoding="utf-8").lower()
    for prohibited in ["significantly better", "superior", "improves in the experiment", "outperforms"]:
        assert prohibited not in text


def test_current_one_target_baseline_smoke_subset_handled_safely():
    run_phase6f3_comparisons(REPO_ROOT)
    rows = read_csv(OUT / "llm_vs_baseline_comparisons.csv")
    assert rows
    assert all(row["comparison_status"] != "ok" for row in rows)


def test_controlled_full_coverage_fixture_exercises_baseline_comparison():
    comparison = full_coverage_baseline_comparison()
    assert comparison["comparison_status"] == "ok"
    assert comparison["ci_lower"] != ""


def test_deterministic_repeated_comparison_run():
    run_phase6f3_comparisons(REPO_ROOT)
    first = {path.name: sha256_file(path) for path in sorted(OUT.glob("*")) if path.is_file()}
    run_phase6f3_comparisons(REPO_ROOT)
    second = {path.name: sha256_file(path) for path in sorted(OUT.glob("*")) if path.is_file()}
    assert first == second


def test_model_to_model_scaffold_secondary():
    rows = controlled_full_coverage_fixture()
    result = build_model_to_model_comparison(rows, "fixture_model", "identical_model", "personalised_history", "strict_top1_accuracy", TEST_BOOTSTRAP_CONFIG)
    assert result["comparison_type"] == "secondary_model_to_model_same_condition"


def test_controlled_validation_flags_true():
    validation = controlled_comparison_validation(TEST_BOOTSTRAP_CONFIG)
    assert all(validation.values())


def full_coverage_accuracy_comparison():
    rows = [row for row in controlled_full_coverage_fixture() if row["model_key"] == "fixture_model"]
    pairs = filter_pairs_for_metric(align_history_pairs(rows), "strict_top1_accuracy")
    return compute_paired_comparison(pairs, "strict_top1_accuracy", TEST_BOOTSTRAP_CONFIG, "personalisation_history_vs_non_history", "fixture_model", "personalised_history", "fixture_model", "non_history", "", "personalised_history - non_history").result


def full_coverage_baseline_comparison():
    fixture = controlled_full_coverage_fixture()
    baseline = controlled_baseline_fixture()
    pairs = align_two_systems([row for row in fixture if row["model_key"] == "fixture_model" and row["condition"] == "personalised_history"], baseline)
    return compute_paired_comparison(pairs, "strict_top1_accuracy", TEST_BOOTSTRAP_CONFIG, "llm_vs_baseline", "fixture_model", "personalised_history", "mixed_effects_baseline", "", "fixture_baseline", "LLM - baseline").result


def fixture_rows_for_bootstrap():
    return [
        {"participant_id": "P1", "prediction_example_id": "P1_T1", "top1_correct": "true"},
        {"participant_id": "P1", "prediction_example_id": "P1_T2", "top1_correct": "true"},
        {"participant_id": "P2", "prediction_example_id": "P2_T1", "top1_correct": "false"},
        {"participant_id": "P2", "prediction_example_id": "P2_T2", "top1_correct": "false"},
    ]


def run_participant_diffs(pairs):
    from llm_experiments.evaluation.comparisons import participant_differences_for_pairs

    return participant_differences_for_pairs(pairs, "personalisation", "m", "personalised_history", "non_history", "")


def read_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))
