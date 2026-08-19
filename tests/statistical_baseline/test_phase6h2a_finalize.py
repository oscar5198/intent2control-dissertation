from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_SRC = REPO_ROOT / "statistical-baseline" / "src"
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
for path in [BASELINE_SRC, LLM_SRC]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from statistical_baseline import phase6h2a_finalize as phase6h2a  # noqa: E402


def build_tmp(tmp_path: Path) -> dict:
    phase6h2a.EMPIRICAL_OUT = tmp_path / "final_n33_empirical"
    phase6h2a.PREDICTIVE_OUT = tmp_path / "final_n33_phase6h"
    return phase6h2a.finalize_phase6h2a(REPO_ROOT)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_authoritative_n33_empirical_models_and_formulas(tmp_path: Path) -> None:
    result = build_tmp(tmp_path)
    empirical = result["empirical"]

    assert empirical["stimulus_model_location"] == "statistical-baseline/outputs/real_stimulus_model"
    assert empirical["feature_model_location"] == "statistical-baseline/outputs/real_feature_model"
    assert empirical["stimulus_formula"] == "rating ~ episode + group + (1 | participant_id) + (1 | stimulus_id)"
    assert empirical["feature_formula"] == "rating ~ episode + group + z_RMS + z_CF + z_SW + (1 | participant_id) + (1 | stimulus_id)"
    assert empirical["participant_count"] == 33
    assert empirical["rating_count"] == 990


def test_n33_group_split_and_convergence_extraction(tmp_path: Path) -> None:
    result = build_tmp(tmp_path)
    convergence = result["empirical"]["convergence"]
    split = result["predictive"]["split_manifest"]

    assert split["group_counts"] == {"group_01": 17, "group_02": 16}
    assert convergence["participant_count"] == 33
    assert convergence["observation_count"] == 990
    assert convergence["chains"] == 4
    assert convergence["posterior_draws_per_chain"] == 1000
    assert convergence["stimulus"]["divergences"] == 0
    assert convergence["feature"]["divergences"] == 0
    assert convergence["stimulus_converged"] is True
    assert convergence["feature_converged"] is True


def test_incomplete_markers_are_classified_stale_not_deleted(tmp_path: Path) -> None:
    result = build_tmp(tmp_path)
    audit = result["empirical"]["incomplete_marker_audit"]

    assert audit["bookkeeping_action"] == "Markers are classified as stale in this audit; they were not deleted."
    assert len(audit["markers"]) == 2
    assert all(marker["exists"] for marker in audit["markers"])
    assert all(marker["classification"] == "STALE" for marker in audit["markers"])


def test_fixed_effect_variance_and_icc_outputs_exist(tmp_path: Path) -> None:
    result = build_tmp(tmp_path)
    empirical_dir = tmp_path / "final_n33_empirical"
    fixed = pd.read_csv(empirical_dir / "n33_primary_mixed_effects_fixed_effects.csv")
    variance = pd.read_csv(empirical_dir / "n33_primary_mixed_effects_variance_components.csv")
    icc = pd.read_csv(empirical_dir / "n33_primary_mixed_effects_icc.csv")

    assert result["empirical"]["fixed_effects_available"] is True
    assert {"episode[FM-1]", "group[group_02]", "z_RMS", "z_CF", "z_SW"}.issubset(set(fixed["term"]))
    assert {"1|participant_id_sigma", "1|stimulus_id_sigma", "sigma"}.issubset(set(variance["component"]))
    assert {"participant_ICC", "stimulus_ICC", "residual_share"}.issubset(set(icc["component"]))
    assert (empirical_dir / "n33_primary_mixed_effects_table.md").exists()
    assert (empirical_dir / "n33_primary_feature_coefficient_plot.png").exists()


def test_phase6h1_alignment_and_training_heldout_separation(tmp_path: Path) -> None:
    result = build_tmp(tmp_path)
    split = result["predictive"]["split_manifest"]
    leakage = result["predictive"]["leakage_audit"]

    assert split["participant_count"] == 33
    assert split["heldout_trial_count"] == 198
    assert split["candidate_count"] == 990
    assert split["phase6h1_alignment_exact"] is True
    assert all(len(row["training_trial_ids"]) == 5 for row in split["rows"])
    assert all(row["heldout_trial_id"] not in row["training_trial_ids"] for row in split["rows"])
    assert leakage["target_leakage_absent"] is True
    assert leakage["target_rows_in_training_max"] == 0
    assert leakage["target_trial_training_rows_max"] == 0


def test_prediction_files_have_990_candidates_198_trials_and_no_scores(tmp_path: Path) -> None:
    result = build_tmp(tmp_path)
    predictive_dir = tmp_path / "final_n33_phase6h"
    candidate = pd.read_csv(predictive_dir / "final_n33_candidate_predictions.csv")
    trial = pd.read_csv(predictive_dir / "final_n33_trial_predictions.csv")

    assert len(candidate) == 990
    assert len(trial) == 198
    assert "observed_rating" not in candidate.columns
    assert "mae" not in trial.columns
    assert "strict_unique_winner_correct" not in trial.columns
    assert set(candidate["presentation_label"]) == set(phase6h2a.LABELS)
    assert result["predictive"]["prediction_qc"]["evaluation_metrics_computed"] is False


def test_winner_and_ranking_are_derived_from_predicted_ratings(tmp_path: Path) -> None:
    build_tmp(tmp_path)
    candidate = pd.read_csv(tmp_path / "final_n33_phase6h" / "final_n33_candidate_predictions.csv")
    trial = pd.read_csv(tmp_path / "final_n33_phase6h" / "final_n33_trial_predictions.csv")

    for row in trial.itertuples():
        group = candidate[candidate["phase6h1_prediction_example_id"].eq(row.phase6h1_prediction_example_id)]
        ordered = group.sort_values(["posterior_mean_expected_rating", "presentation_label"], ascending=[False, True])
        assert row.predicted_preferred_mix == ordered.iloc[0]["presentation_label"]
        assert row.predicted_ranking == "|".join(ordered["presentation_label"].tolist())


def test_freeze_manifest_hashes_and_metric_protocol_reference(tmp_path: Path) -> None:
    result = build_tmp(tmp_path)
    freeze = load_json(tmp_path / "final_n33_phase6h" / "final_n33_prediction_freeze_manifest.json")
    config = load_json(tmp_path / "final_n33_phase6h" / "final_n33_model_config.json")

    assert freeze["evaluation_metrics_not_computed"] is True
    assert freeze["prediction_content_frozen"] is True
    assert all(freeze["gates"].values())
    assert freeze["prediction_hashes"]
    assert config["metric_protocol_reference"] == "llm-experiments/outputs/real/phase6h1/phase6h1_metric_protocol.json"
    assert config["metric_protocol_hash"] == phase6h2a.sha256_file(REPO_ROOT / "llm-experiments/outputs/real/phase6h1/phase6h1_metric_protocol.json")
    assert result["gates"]["MIXED_EFFECTS_LLM_FAIR_COMPARISON_READY"] is True


def test_old_n30_baseline_is_not_primary(tmp_path: Path) -> None:
    result = build_tmp(tmp_path)
    old = result["manifest"]["old_n30_baseline"]

    assert old["n_participants"] == 30
    assert old["n_trials"] == 180
    assert old["classification"] == "historical_superseded_for_primary_final_comparison"
    assert result["predictive"]["model_config"]["primary_predictive_baseline_model"] == "primary_acoustic"
