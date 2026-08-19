from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.evaluation import phase6h2b_final_scoring as phase6h2b  # noqa: E402


@pytest.fixture(scope="module")
def scored(tmp_path_factory: pytest.TempPathFactory) -> dict:
    out = tmp_path_factory.mktemp("phase6h2b")
    return phase6h2b.run_phase6h2b_final_scoring(REPO_ROOT, output_dir=out)


def test_top1_set_credit_and_chance_reference() -> None:
    assert phase6h2b.CHANCE_TOP1 == 0.20
    rows = [
        {
            "source": "llm",
            "method_key": "fixture__non_history",
            "model_key": "fixture",
            "model_label": "Fixture",
            "condition": "non_history",
            "prediction_example_id": "ex1",
            "participant_id": "P001",
            "top1_correct": int("B" in ["A", "B"]),
            "spearman": 0.0,
        }
    ]
    summary = phase6h2b.summarize_top1(rows)[0]
    assert summary["correct"] == 1
    assert summary["denominator"] == 1
    assert summary["accuracy"] == 1.0


def test_wilson_interval_is_used(scored: dict) -> None:
    gpt = next(row for row in scored["top1"] if row["method_key"] == "gpt__non_history")
    low, high = phase6h2b.wilson_ci(gpt["correct"], gpt["denominator"])

    assert gpt["ci_method"] == "wilson_95"
    assert gpt["ci_low"] == low
    assert gpt["ci_high"] == high


def test_trial_level_spearman_and_average_rank_ties() -> None:
    actual = {"A": 1.5, "B": 1.5, "C": 3.0, "D": 4.5, "E": 4.5}
    predicted = phase6h2b.ranks_from_order(["A", "B", "C", "D", "E"])

    assert predicted == {"A": 1.0, "B": 2.0, "C": 3.0, "D": 4.0, "E": 5.0}
    assert phase6h2b.spearman(actual, predicted) > 0.9


def test_mae_and_rmse_candidate_level(scored: dict) -> None:
    candidate = pd.read_csv(Path(scored["output_dir"]) / "phase6h2b_candidate_level_rating_errors.csv")
    row = candidate[candidate["method_key"].eq("gpt__non_history")].iloc[0]

    assert row["absolute_error"] == abs(row["predicted_rating"] - row["actual_rating"])
    assert row["squared_error"] == (row["predicted_rating"] - row["actual_rating"]) ** 2


def test_exact_denominators_and_centaur_rating_exclusion(scored: dict) -> None:
    assert all(row["denominator"] == 198 for row in scored["top1"])
    assert all(row["denominator"] == 198 for row in scored["ranking"])
    assert all(row["candidate_denominator"] in {0, 990} for row in scored["rating"])
    assert all(row["candidate_denominator"] == 0 for row in scored["rating"] if row["model_key"] == "centaur")
    assert all(row["mae"] == "" for row in scored["rating"] if row["model_key"] == "centaur")


def test_paired_personalisation_matching_and_mcnemar_counts(scored: dict) -> None:
    assert len(scored["personalisation"]) == 4
    for row in scored["personalisation"]:
        assert row["paired_examples"] == 198
        assert row["history_helps"] >= 0
        assert row["history_hurts"] >= 0
        assert row["mcnemar_exact_p"] == phase6h2b.mcnemar_exact_p(row["history_helps"], row["history_hurts"])


def test_mixed_effects_llm_target_matching(scored: dict) -> None:
    assert len(scored["comparison"]) == 8
    assert all(row["paired_examples"] == 198 for row in scored["comparison"])
    assert all(row["mixed_effects_accuracy"] == next(t["accuracy"] for t in scored["top1"] if t["model_key"] == "mixed_effects_primary_acoustic") for row in scored["comparison"])


def test_participant_bootstrap_reproducibility(scored: dict) -> None:
    rows = [
        {"participant_id": "P001", "method_key": "fixture", "value": 1.0},
        {"participant_id": "P001", "method_key": "fixture", "value": 3.0},
        {"participant_id": "P002", "method_key": "fixture", "value": 5.0},
        {"participant_id": "P003", "method_key": "fixture", "value": 7.0},
    ]
    first = phase6h2b.participant_bootstrap_ci(rows, lambda sample: sum(row["value"] for row in sample) / len(sample))
    second = phase6h2b.participant_bootstrap_ci(rows, lambda sample: sum(row["value"] for row in sample) / len(sample))

    assert first == second


def test_frozen_input_hashes_and_no_prediction_mutation(scored: dict) -> None:
    manifest = scored["manifest"]
    assert manifest["prediction_rerun"] is False
    assert manifest["mixed_effects_refit"] is False
    assert manifest["source_hashes"]["llm-experiments/outputs/real/phase6g5/final_llm_predictions.jsonl"] == phase6h2b.sha256_file(REPO_ROOT / "llm-experiments/outputs/real/phase6g5/final_llm_predictions.jsonl")
    assert manifest["source_hashes"]["statistical-baseline/outputs/real_heldout_evaluation/final_n33_phase6h/final_n33_candidate_predictions.csv"] == phase6h2b.sha256_file(REPO_ROOT / "statistical-baseline/outputs/real_heldout_evaluation/final_n33_phase6h/final_n33_candidate_predictions.csv")


def test_rq_evidence_mapping_and_qc_gates(scored: dict) -> None:
    assert set(scored["rq_evidence"]) == {"schema_version", "RQ1", "RQ2", "RQ3", "RQ4"}
    assert scored["qc"]["gates"]["RQ1_EVIDENCE_READY"] is True
    assert scored["qc"]["gates"]["RQ2_EVIDENCE_READY"] is True
    assert scored["qc"]["gates"]["RQ3_EVIDENCE_READY"] is True
    assert scored["qc"]["gates"]["RQ4_EVIDENCE_READY"] is True
    assert scored["qc"]["gates"]["PHASE6H2B_COMPLETE"] is True


def test_table_and_figure_outputs_exist(scored: dict) -> None:
    out = Path(scored["output_dir"])
    for name in [
        "phase6h2b_table_a_central_mixed_effects.csv",
        "phase6h2b_table_b_prediction_results.csv",
        "phase6h2b_table_c_personalisation_effects.csv",
        "phase6h2b_figure2_top1_accuracy.png",
        "phase6h2b_figure3_personalisation_top1.png",
    ]:
        assert (out / name).exists()
        assert (out / name).stat().st_size > 0


def test_chance_tests_and_adjustment(scored: dict) -> None:
    assert len(scored["chance"]) == 9
    for row in scored["chance"]:
        assert row["test"] == "exact_one_sided_binomial_ge_chance"
        assert 0 <= row["p_value"] <= 1
        assert 0 <= row["p_value_bh_adjusted"] <= 1
