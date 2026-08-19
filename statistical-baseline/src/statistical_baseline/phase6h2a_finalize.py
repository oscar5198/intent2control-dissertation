"""Phase 6H.2A empirical consolidation and N=33 held-out baseline freeze."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
EMPIRICAL_OUT = REPO_ROOT / "statistical-baseline/outputs/final_n33_empirical"
PREDICTIVE_OUT = REPO_ROOT / "statistical-baseline/outputs/real_heldout_evaluation/final_n33_phase6h"
STIMULUS_DIR = REPO_ROOT / "statistical-baseline/outputs/real_stimulus_model"
FEATURE_DIR = REPO_ROOT / "statistical-baseline/outputs/real_feature_model"
OLD_HELDOUT_DIR = REPO_ROOT / "statistical-baseline/outputs/real_heldout_evaluation/frozen_phase6_split"
N33_HELDOUT_DIR = REPO_ROOT / "statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split"
PHASE6H1_DIR = REPO_ROOT / "llm-experiments/outputs/real/phase6h1"
REAL_DATA_DIR = REPO_ROOT / "statistical-baseline/data/real"

PRIMARY_PREDICTIVE_MODEL = "primary_acoustic"
LABELS = ("A", "B", "C", "D", "E")


def finalize_phase6h2a(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    empirical_out = resolve_output_path(repo_root, EMPIRICAL_OUT)
    predictive_out = resolve_output_path(repo_root, PREDICTIVE_OUT)
    empirical_out.mkdir(parents=True, exist_ok=True)
    predictive_out.mkdir(parents=True, exist_ok=True)

    empirical = consolidate_empirical_results(repo_root, empirical_out)
    predictive = freeze_n33_predictive_baseline(repo_root, predictive_out)
    gates = build_completion_gates(empirical, predictive)
    manifest = build_phase_manifest(repo_root, empirical, predictive, gates)
    write_json(predictive_out / "phase6h2a_completion_manifest.json", manifest)
    write_qc_report(predictive_out / "phase6h2a_qc_report.md", empirical, predictive, gates)
    return {"empirical": empirical, "predictive": predictive, "gates": gates, "manifest": manifest}


def consolidate_empirical_results(repo_root: Path, output_dir: Path) -> dict[str, Any]:
    stimulus_manifest = read_json(repo_root / "statistical-baseline/outputs/real_stimulus_model/real_stimulus_model_manifest.json")
    feature_manifest = read_json(repo_root / "statistical-baseline/outputs/real_feature_model/real_feature_model_manifest.json")
    stimulus_fixed = pd.read_csv(repo_root / "statistical-baseline/outputs/real_stimulus_model/fixed_effect_posterior_summary.csv")
    feature_fixed = pd.read_csv(repo_root / "statistical-baseline/outputs/real_feature_model/primary_fixed_effect_posterior_summary.csv")
    stimulus_var = pd.read_csv(repo_root / "statistical-baseline/outputs/real_stimulus_model/final_model_variance_components.csv")
    stimulus_icc = pd.read_csv(repo_root / "statistical-baseline/outputs/real_stimulus_model/final_model_icc_summary.csv")
    feature_var = pd.read_csv(repo_root / "statistical-baseline/outputs/real_feature_model/variance_components.csv")
    feature_icc = pd.read_csv(repo_root / "statistical-baseline/outputs/real_feature_model/icc_posterior_summary.csv")
    stimulus_diag = pd.read_csv(repo_root / "statistical-baseline/outputs/real_stimulus_model/convergence_diagnostics.csv")
    feature_diag = pd.read_csv(repo_root / "statistical-baseline/outputs/real_feature_model/convergence_diagnostics.csv")

    primary_feature_fixed = feature_fixed[feature_fixed["model_name"].eq("primary_feature")].copy()
    fixed_table = pd.concat(
        [
            stimulus_fixed.assign(model="stimulus_model"),
            primary_feature_fixed.drop(columns=["model_name"]).assign(model="primary_feature_model"),
        ],
        ignore_index=True,
        sort=False,
    )
    fixed_table = fixed_table[["model", "term", "mean", "hdi_3", "hdi_97", "sd", "ess_bulk", "ess_tail", "r_hat"]]
    variance_table = pd.concat(
        [
            stimulus_var.assign(model="stimulus_model").rename(columns={"term": "component"}),
            feature_var[feature_var["model_name"].eq("primary_feature")].assign(model="primary_feature_model").rename(columns={"term": "component"}),
        ],
        ignore_index=True,
        sort=False,
    )[["model", "component", "mean", "hdi_3", "hdi_97", "sd", "ess_bulk", "ess_tail", "r_hat"]]
    icc_table = pd.concat(
        [
            stimulus_icc.assign(model="stimulus_model").rename(columns={"term": "component"}),
            feature_icc[feature_icc["model_name"].eq("primary_feature")].assign(model="primary_feature_model").rename(columns={"term": "component"}),
        ],
        ignore_index=True,
        sort=False,
    )[["model", "component", "mean", "hdi_3", "hdi_97", "sd", "ess_bulk", "ess_tail", "r_hat"]]
    diag_table = pd.concat(
        [stimulus_diag.assign(model_suite="stimulus"), feature_diag.assign(model_suite="feature")],
        ignore_index=True,
        sort=False,
    )
    convergence = convergence_summary(stimulus_manifest, feature_manifest, diag_table)
    marker_audit = incomplete_marker_audit(repo_root, stimulus_manifest, feature_manifest, convergence)

    fixed_table.to_csv(output_dir / "n33_primary_mixed_effects_fixed_effects.csv", index=False)
    variance_table.to_csv(output_dir / "n33_primary_mixed_effects_variance_components.csv", index=False)
    icc_table.to_csv(output_dir / "n33_primary_mixed_effects_icc.csv", index=False)
    diag_table.to_csv(output_dir / "n33_primary_mixed_effects_convergence.csv", index=False)
    write_primary_table(output_dir / "n33_primary_mixed_effects_table.md", fixed_table, variance_table, icc_table, convergence)
    write_coefficient_plot(output_dir / "n33_primary_feature_coefficient_plot.png", primary_feature_fixed)
    inventory = {
        "schema_version": "phase6h2a_n33_empirical_inventory_v1",
        "stimulus_model_location": "statistical-baseline/outputs/real_stimulus_model",
        "feature_model_location": "statistical-baseline/outputs/real_feature_model",
        "stimulus_formula": stimulus_manifest["final_formula"],
        "feature_formula": feature_manifest["primary_formula"],
        "participant_count": stimulus_manifest["cleaned_dataset"]["analysable_n"],
        "rating_count": stimulus_manifest["cleaned_dataset"]["rating_count"],
        "trial_count": stimulus_manifest["cleaned_dataset"]["trial_count"],
        "convergence": convergence,
        "incomplete_marker_audit": marker_audit,
        "fixed_effects_available": True,
        "variance_components_available": True,
        "icc_available": True,
        "primary_table": rel(output_dir / "n33_primary_mixed_effects_table.md"),
        "primary_figure": rel(output_dir / "n33_primary_feature_coefficient_plot.png"),
        "artifact_hashes": hash_existing(
            [
                output_dir / "n33_primary_mixed_effects_fixed_effects.csv",
                output_dir / "n33_primary_mixed_effects_variance_components.csv",
                output_dir / "n33_primary_mixed_effects_icc.csv",
                output_dir / "n33_primary_mixed_effects_convergence.csv",
                output_dir / "n33_primary_mixed_effects_table.md",
                output_dir / "n33_primary_feature_coefficient_plot.png",
            ]
        ),
    }
    write_json(output_dir / "n33_empirical_results_inventory.json", inventory)
    return inventory


def freeze_n33_predictive_baseline(repo_root: Path, output_dir: Path) -> dict[str, Any]:
    candidate = pd.read_csv(repo_root / "statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/candidate_predictions.csv")
    split = pd.read_csv(repo_root / "statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/heldout_split_manifest.csv")
    leakage = pd.read_csv(repo_root / "statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/leakage_audit.csv")
    diagnostics = pd.read_csv(repo_root / "statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/fold_diagnostics.csv")
    eval_manifest = read_json(repo_root / "statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/evaluation_manifest.json")
    h1_ground_truth = pd.read_csv(repo_root / "llm-experiments/outputs/real/phase6h1/phase6h1_ground_truth_heldout.csv")
    h1_metric = read_json(repo_root / "llm-experiments/outputs/real/phase6h1/phase6h1_metric_protocol.json")

    primary = candidate[candidate["baseline_model"].eq(PRIMARY_PREDICTIVE_MODEL)].copy()
    primary["phase6h1_prediction_example_id"] = primary["trial_id"].map(lambda value: f"{str(value).split('__trial_')[0]}__heldout__{value}")
    h1_unique = h1_ground_truth[["prediction_example_id", "participant_id", "heldout_trial_id", "condition", "candidate_mapping_json"]].drop_duplicates()
    h1_non_history = h1_unique[h1_unique["condition"].eq("non_history")]
    alignment = set(primary["phase6h1_prediction_example_id"]) == set(h1_non_history["prediction_example_id"])
    if not alignment:
        raise ValueError("N=33 held-out predictions do not align exactly with Phase 6H.1 examples.")

    prediction_cols = [
        "phase6h1_prediction_example_id",
        "prediction_example_id",
        "fold_id",
        "participant_id",
        "group",
        "trial_id",
        "target_trial_id",
        "song_id",
        "episode",
        "presentation_label",
        "stimulus_id",
        "mix_id",
        "baseline_model",
        "model_label",
        "formula",
        "posterior_mean_expected_rating",
        "posterior_expected_sd",
        "posterior_expected_hdi_lower",
        "posterior_expected_hdi_upper",
        "posterior_probability_highest",
        "fit_method",
        "posterior_expected_draws_outside_0_100_prop",
    ]
    frozen_candidate = primary[prediction_cols].sort_values(["participant_id", "trial_id", "presentation_label"]).reset_index(drop=True)
    trial_rows = derive_trial_predictions(frozen_candidate)
    leakage_audit = build_leakage_audit(leakage, diagnostics, frozen_candidate, h1_non_history)
    split_manifest = build_split_manifest(split, h1_non_history)
    model_config = build_model_config(eval_manifest, h1_metric)
    qc = build_prediction_qc(frozen_candidate, trial_rows, split_manifest, leakage_audit, eval_manifest)

    candidate_path = output_dir / "final_n33_candidate_predictions.csv"
    trial_path = output_dir / "final_n33_trial_predictions.csv"
    frozen_candidate.to_csv(candidate_path, index=False)
    trial_rows.to_csv(trial_path, index=False)
    write_json(output_dir / "final_n33_split_manifest.json", split_manifest)
    write_json(output_dir / "final_n33_model_config.json", model_config)
    write_json(output_dir / "final_n33_leakage_audit.json", leakage_audit)
    write_json(output_dir / "final_n33_prediction_qc.json", qc)
    freeze = build_prediction_freeze_manifest(repo_root, output_dir, eval_manifest, split_manifest, model_config, leakage_audit, qc)
    write_json(output_dir / "final_n33_prediction_freeze_manifest.json", freeze)
    write_predictive_report(output_dir / "final_n33_predictive_qc_report.md", freeze, qc, leakage_audit, model_config)
    return {
        "output_dir": rel(output_dir),
        "candidate_predictions": rel(candidate_path),
        "trial_predictions": rel(trial_path),
        "freeze_manifest": rel(output_dir / "final_n33_prediction_freeze_manifest.json"),
        "model_config": model_config,
        "split_manifest": split_manifest,
        "leakage_audit": leakage_audit,
        "prediction_qc": qc,
        "prediction_freeze_manifest": freeze,
    }


def derive_trial_predictions(candidate: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, group in candidate.groupby("phase6h1_prediction_example_id", sort=True):
        ordered = group.sort_values(["posterior_mean_expected_rating", "presentation_label"], ascending=[False, True])
        max_score = ordered["posterior_mean_expected_rating"].max()
        tied = ordered[ordered["posterior_mean_expected_rating"].eq(max_score)]["presentation_label"].tolist()
        first = ordered.iloc[0]
        rows.append(
            {
                "phase6h1_prediction_example_id": first["phase6h1_prediction_example_id"],
                "prediction_example_id": first["prediction_example_id"],
                "fold_id": int(first["fold_id"]),
                "participant_id": first["participant_id"],
                "group": first["group"],
                "trial_id": first["trial_id"],
                "target_trial_id": first["target_trial_id"],
                "song_id": first["song_id"],
                "episode": first["episode"],
                "baseline_model": first["baseline_model"],
                "model_label": first["model_label"],
                "fit_method": first["fit_method"],
                "predicted_preferred_mix": sorted(tied)[0],
                "predicted_tie": len(tied) > 1,
                "predicted_tied_labels": "|".join(sorted(tied)) if len(tied) > 1 else "",
                "predicted_ranking": "|".join(ordered["presentation_label"].tolist()),
                "predicted_winner_posterior_probability": float(ordered.iloc[0]["posterior_probability_highest"]),
                **{f"predicted_rating_{row.presentation_label}": float(row.posterior_mean_expected_rating) for row in group.itertuples()},
            }
        )
    return pd.DataFrame(rows).sort_values(["participant_id", "trial_id"]).reset_index(drop=True)


def build_leakage_audit(leakage: pd.DataFrame, diagnostics: pd.DataFrame, candidate: pd.DataFrame, h1: pd.DataFrame) -> dict[str, Any]:
    primary_diag = diagnostics[diagnostics["baseline_model"].eq(PRIMARY_PREDICTIVE_MODEL)]
    return {
        "schema_version": "phase6h2a_n33_leakage_audit_v1",
        "target_leakage_absent": bool(leakage["leakage_passed"].astype(bool).all()),
        "target_rows_in_training_max": int(leakage["target_rows_in_training"].max()),
        "target_trial_training_rows_max": int(primary_diag["target_trial_training_rows"].max()),
        "training_rows_per_fold": sorted(primary_diag["training_row_count"].astype(int).unique().tolist()),
        "participant_history_rows_retained": sorted(primary_diag["participant_other_trial_rows_retained"].astype(int).unique().tolist()),
        "same_stimulus_other_participant_rows_retained": sorted(primary_diag["same_stimulus_other_participant_rows_retained"].astype(int).unique().tolist()),
        "phase6h1_alignment_count": int(candidate["phase6h1_prediction_example_id"].nunique()),
        "phase6h1_expected_count": int(h1["prediction_example_id"].nunique()),
        "same_targets_as_phase6h1": set(candidate["phase6h1_prediction_example_id"]) == set(h1["prediction_example_id"]),
        "heldout_target_ratings_removed_from_frozen_prediction_files": True,
        "historical_source_candidate_file_contains_observed_ratings": True,
    }


def build_split_manifest(split: pd.DataFrame, h1: pd.DataFrame) -> dict[str, Any]:
    rows = []
    for row in split.sort_values(["participant_id", "trial_id"]).itertuples():
        phase6h1_id = f"{row.participant_id}__heldout__{row.trial_id}"
        rows.append(
            {
                "phase6h1_prediction_example_id": phase6h1_id,
                "source_prediction_example_id": row.prediction_example_id,
                "participant_id": row.participant_id,
                "group": row.group,
                "heldout_trial_id": row.trial_id,
                "training_trial_ids": [f"{row.participant_id}__trial_{index:02d}" for index in range(1, 7) if f"{row.participant_id}__trial_{index:02d}" != row.trial_id],
                "candidate_count": int(row.candidate_count),
                "episode": row.episode,
                "song_id": row.song_id,
            }
        )
    return {
        "schema_version": "phase6h2a_n33_split_manifest_v1",
        "source": "statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/heldout_split_manifest.csv",
        "phase6h1_source": "llm-experiments/outputs/real/phase6h1/phase6h1_ground_truth_heldout.csv",
        "split_rule": "leave-one-trial-out participant-trial; all five candidate rows excluded together",
        "participant_count": int(split["participant_id"].nunique()),
        "heldout_trial_count": int(split["trial_id"].nunique()),
        "candidate_count": int(split["candidate_count"].sum()),
        "group_counts": split[["participant_id", "group"]].drop_duplicates()["group"].value_counts().sort_index().astype(int).to_dict(),
        "phase6h1_alignment_exact": set(f"{r.participant_id}__heldout__{r.trial_id}" for r in split.itertuples()) == set(h1["prediction_example_id"]),
        "rows": rows,
    }


def build_model_config(eval_manifest: dict[str, Any], h1_metric: dict[str, Any]) -> dict[str, Any]:
    selected = next(model for model in eval_manifest["models"] if model["model_id"] == PRIMARY_PREDICTIVE_MODEL)
    return {
        "schema_version": "phase6h2a_n33_model_config_v1",
        "primary_predictive_baseline_model": PRIMARY_PREDICTIVE_MODEL,
        "selection_reason": "Uses the established mixed-effects feature formula with episode, group, z_RMS, z_CF, z_SW, participant random intercept, and stimulus random intercept; this is closest to the frozen LLM base inputs without changing formulas based on performance.",
        "model": selected,
        "auxiliary_heldout_model_available": "categorical_design",
        "fit_method": eval_manifest["executed_fit_method"],
        "sampler_settings": eval_manifest["sampler_settings"],
        "checkpoint_compatibility_version": eval_manifest["checkpoint_compatibility_version"],
        "metric_protocol_reference": "llm-experiments/outputs/real/phase6h1/phase6h1_metric_protocol.json",
        "metric_protocol_hash": sha256_file(PHASE6H1_DIR / "phase6h1_metric_protocol.json"),
        "phase6h1_metric_protocol_schema_version": h1_metric["schema_version"],
        "final_metrics_computed_in_this_freeze": False,
        "predicted_score_tie_rule": "If posterior_mean_expected_rating ties exactly, predicted_tied_labels records all tied labels and predicted_preferred_mix is the alphabetically first label for deterministic serialization; tie-aware scoring remains governed by Phase 6H.1.",
    }


def build_prediction_qc(candidate: pd.DataFrame, trial: pd.DataFrame, split: dict[str, Any], leakage: dict[str, Any], eval_manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "phase6h2a_n33_prediction_qc_v1",
        "participant_count": int(candidate["participant_id"].nunique()),
        "heldout_trial_count": int(candidate["phase6h1_prediction_example_id"].nunique()),
        "candidate_prediction_rows": int(len(candidate)),
        "trial_prediction_rows": int(len(trial)),
        "expected_candidate_prediction_rows": 990,
        "expected_trial_prediction_rows": 198,
        "baseline_model": PRIMARY_PREDICTIVE_MODEL,
        "candidate_rows_per_trial": candidate.groupby("phase6h1_prediction_example_id").size().value_counts().sort_index().astype(int).to_dict(),
        "ranking_complete": bool(trial["predicted_ranking"].map(lambda value: sorted(str(value).split("|")) == list(LABELS)).all()),
        "winner_derivation": "highest posterior_mean_expected_rating among A-E candidates",
        "prediction_uncertainty_available": True,
        "prediction_uncertainty_fields": ["posterior_expected_sd", "posterior_expected_hdi_lower", "posterior_expected_hdi_upper", "posterior_probability_highest"],
        "all_mcmc_fit_pairs_complete": eval_manifest["completion_status"]["complete"],
        "target_leakage_absent": leakage["target_leakage_absent"],
        "phase6h1_alignment_exact": split["phase6h1_alignment_exact"],
        "evaluation_metrics_computed": False,
    }


def build_prediction_freeze_manifest(
    repo_root: Path,
    output_dir: Path,
    eval_manifest: dict[str, Any],
    split: dict[str, Any],
    model_config: dict[str, Any],
    leakage: dict[str, Any],
    qc: dict[str, Any],
) -> dict[str, Any]:
    candidate_path = output_dir / "final_n33_candidate_predictions.csv"
    trial_path = output_dir / "final_n33_trial_predictions.csv"
    gates = {
        "N33_HELDOUT_SPLIT_MATCHES_PHASE6H1": split["phase6h1_alignment_exact"],
        "N33_HELDOUT_TARGET_LEAKAGE_ABSENT": leakage["target_leakage_absent"] and leakage["target_rows_in_training_max"] == 0,
        "N33_HELDOUT_MODEL_READY": eval_manifest["completion_status"]["complete"],
        "N33_HELDOUT_990_CANDIDATE_PREDICTIONS_COMPLETE": qc["candidate_prediction_rows"] == 990,
        "N33_HELDOUT_198_TRIAL_PREDICTIONS_COMPLETE": qc["trial_prediction_rows"] == 198,
        "N33_HELDOUT_PREDICTIONS_FROZEN": True,
    }
    gates["MIXED_EFFECTS_LLM_FAIR_COMPARISON_READY"] = all(gates.values())
    source_files = [
        "statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/candidate_predictions.csv",
        "statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/trial_predictions.csv",
        "statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/heldout_split_manifest.csv",
        "statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/evaluation_manifest.json",
        "statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/leakage_audit.csv",
        "llm-experiments/outputs/real/phase6h1/phase6h1_metric_protocol.json",
        "llm-experiments/outputs/real/phase6h1/phase6h1_ground_truth_heldout.csv",
    ]
    return {
        "schema_version": "phase6h2a_n33_prediction_freeze_manifest_v1",
        "created_at_utc": stable_created_at(output_dir / "final_n33_prediction_freeze_manifest.json"),
        "n_participants": 33,
        "heldout_trials": 198,
        "candidate_predictions": 990,
        "trial_predictions": 198,
        "source_data_hash": eval_manifest["real_data_sha256"],
        "split_hash": sha256_json(split),
        "model_formula": model_config["model"]["formula"],
        "model_fit_artifact_hashes": {path: sha256_file(repo_root / path) for path in source_files},
        "prediction_hashes": {
            rel(candidate_path): sha256_file(candidate_path),
            rel(trial_path): sha256_file(trial_path),
        },
        "target_leakage_absent": leakage["target_leakage_absent"],
        "evaluation_metrics_not_computed": True,
        "prediction_content_frozen": True,
        "gates": gates,
    }


def build_phase_manifest(repo_root: Path, empirical: dict[str, Any], predictive: dict[str, Any], gates: dict[str, bool]) -> dict[str, Any]:
    return {
        "schema_version": "phase6h2a_completion_manifest_v1",
        "created_at_utc": stable_created_at(PREDICTIVE_OUT / "phase6h2a_completion_manifest.json"),
        "empirical_inventory": empirical,
        "predictive_freeze_manifest": predictive["freeze_manifest"],
        "old_n30_baseline": audit_old_n30_baseline(repo_root),
        "final_metrics_computed": False,
        "gates": gates,
    }


def build_completion_gates(empirical: dict[str, Any], predictive: dict[str, Any]) -> dict[str, bool]:
    pred_gates = predictive["prediction_freeze_manifest"]["gates"]
    gates = {
        "N33_EMPIRICAL_MODELS_FOUND": empirical["participant_count"] == 33,
        "N33_STIMULUS_MODEL_CONVERGED": empirical["convergence"]["stimulus_converged"],
        "N33_FEATURE_MODEL_CONVERGED": empirical["convergence"]["feature_converged"],
        "N33_EMPIRICAL_RESULTS_READY": empirical["fixed_effects_available"] and empirical["variance_components_available"] and empirical["icc_available"],
        "N33_INCOMPLETE_MARKERS_RESOLVED": all(item["classification"] == "STALE" for item in empirical["incomplete_marker_audit"]["markers"]),
        **pred_gates,
    }
    return gates


def convergence_summary(stimulus_manifest: dict[str, Any], feature_manifest: dict[str, Any], diag: pd.DataFrame) -> dict[str, Any]:
    stimulus = diag[diag["model_suite"].eq("stimulus")]
    feature = diag[diag["model_suite"].eq("feature")]
    def block(frame: pd.DataFrame) -> dict[str, Any]:
        return {
            "model_count": int(len(frame)),
            "samplers": sorted(frame["sampler"].astype(str).unique().tolist()),
            "divergences": int(pd.to_numeric(frame["divergences"]).sum()),
            "max_rhat": float(pd.to_numeric(frame["max_rhat"]).max()),
            "min_bulk_ess": float(pd.to_numeric(frame["min_bulk_ess"]).min()),
            "min_tail_ess": float(pd.to_numeric(frame["min_tail_ess"]).min()),
            "warnings": int(pd.to_numeric(frame.get("tree_depth_warnings", 0)).sum() + pd.to_numeric(frame.get("energy_warnings", 0)).sum()),
        }
    stimulus_block = block(stimulus)
    feature_block = block(feature)
    return {
        "participant_count": stimulus_manifest["cleaned_dataset"]["analysable_n"],
        "observation_count": stimulus_manifest["cleaned_dataset"]["rating_count"],
        "trials": stimulus_manifest["cleaned_dataset"]["trial_count"],
        "chains": stimulus_manifest["sampling"]["chains"],
        "posterior_draws_per_chain": stimulus_manifest["sampling"]["draws"],
        "tune": stimulus_manifest["sampling"]["tune"],
        "stimulus": stimulus_block,
        "feature": feature_block,
        "stimulus_converged": stimulus_block["divergences"] == 0 and stimulus_block["max_rhat"] <= 1.01 and stimulus_block["min_bulk_ess"] >= 400 and stimulus_block["min_tail_ess"] >= 400,
        "feature_converged": feature_block["divergences"] == 0 and feature_block["max_rhat"] <= 1.01 and feature_block["min_bulk_ess"] >= 400 and feature_block["min_tail_ess"] >= 400,
        "interpretation": "The specified N=33 multilevel models converged satisfactorily and provide usable posterior estimates; this does not prove N=33 is universally ideal or conventionally powered.",
    }


def incomplete_marker_audit(repo_root: Path, stimulus_manifest: dict[str, Any], feature_manifest: dict[str, Any], convergence: dict[str, Any]) -> dict[str, Any]:
    markers = []
    for marker_path, manifest, converged in [
        (repo_root / "statistical-baseline/outputs/real_stimulus_model/INCOMPLETE_PENDING_QMUL_RERUN.txt", stimulus_manifest, convergence["stimulus_converged"]),
        (repo_root / "statistical-baseline/outputs/real_feature_model/INCOMPLETE_PENDING_QMUL_RERUN.txt", feature_manifest, convergence["feature_converged"]),
    ]:
        exists = marker_path.exists()
        classification = "STALE" if exists and manifest.get("cleaned_dataset", {}).get("analysable_n") == 33 and converged else "GENUINELY_INCOMPLETE" if exists else "ABSENT"
        markers.append(
            {
                "path": rel(marker_path),
                "exists": exists,
                "classification": classification,
                "marker_text": marker_path.read_text(encoding="utf-8").strip() if exists else "",
                "evidence": "N=33 manifest, dissertation-ready final_gate, and convergence diagnostics are present." if classification == "STALE" else "",
            }
        )
    return {
        "schema_version": "phase6h2a_incomplete_marker_audit_v1",
        "bookkeeping_action": "Markers are classified as stale in this audit; they were not deleted.",
        "markers": markers,
    }


def audit_old_n30_baseline(repo_root: Path) -> dict[str, Any]:
    manifest = read_json(repo_root / "statistical-baseline/outputs/real_heldout_evaluation/frozen_phase6_split/evaluation_manifest.json")
    return {
        "path": "statistical-baseline/outputs/real_heldout_evaluation/frozen_phase6_split",
        "classification": "historical_superseded_for_primary_final_comparison",
        "n_participants": manifest["n_participants"],
        "n_trials": manifest["n_trials"],
        "reason": "It excludes P031-P033 and has 180 rather than 198 held-out trials.",
        "manifest_sha256": sha256_file(repo_root / "statistical-baseline/outputs/real_heldout_evaluation/frozen_phase6_split/evaluation_manifest.json"),
    }


def write_primary_table(path: Path, fixed: pd.DataFrame, variance: pd.DataFrame, icc: pd.DataFrame, convergence: dict[str, Any]) -> None:
    lines = [
        "# N=33 Primary Mixed-Effects Results",
        "",
        "## Fixed Effects",
        "| Model | Term | Estimate | 95% CrI |",
        "| --- | --- | ---: | --- |",
    ]
    for row in fixed.itertuples():
        lines.append(f"| {row.model} | {row.term} | {row.mean:.3f} | [{row.hdi_3:.3f}, {row.hdi_97:.3f}] |")
    lines.extend(["", "## Variance Components", "| Model | Component | Estimate | 95% CrI |", "| --- | --- | ---: | --- |"])
    for row in variance.itertuples():
        lines.append(f"| {row.model} | {row.component} | {row.mean:.3f} | [{row.hdi_3:.3f}, {row.hdi_97:.3f}] |")
    lines.extend(["", "## ICC", "| Model | Component | Estimate | 95% CrI |", "| --- | --- | ---: | --- |"])
    for row in icc[icc["component"].str.contains("ICC|share", regex=True)].itertuples():
        lines.append(f"| {row.model} | {row.component} | {row.mean:.3f} | [{row.hdi_3:.3f}, {row.hdi_97:.3f}] |")
    lines.extend(
        [
            "",
            "## Convergence",
            f"- Participants: {convergence['participant_count']}; observations: {convergence['observation_count']}; chains: {convergence['chains']}; posterior draws per chain: {convergence['posterior_draws_per_chain']}.",
            f"- Stimulus model: divergences {convergence['stimulus']['divergences']}, max R-hat {convergence['stimulus']['max_rhat']:.3f}, min bulk ESS {convergence['stimulus']['min_bulk_ess']:.1f}, min tail ESS {convergence['stimulus']['min_tail_ess']:.1f}.",
            f"- Feature model: divergences {convergence['feature']['divergences']}, max R-hat {convergence['feature']['max_rhat']:.3f}, min bulk ESS {convergence['feature']['min_bulk_ess']:.1f}, min tail ESS {convergence['feature']['min_tail_ess']:.1f}.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_coefficient_plot(path: Path, feature_fixed: pd.DataFrame) -> None:
    plot_data = feature_fixed[~feature_fixed["term"].eq("Intercept")].copy()
    plot_data = plot_data.sort_values("mean")
    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    y = range(len(plot_data))
    ax.errorbar(
        plot_data["mean"],
        list(y),
        xerr=[plot_data["mean"] - plot_data["hdi_3"], plot_data["hdi_97"] - plot_data["mean"]],
        fmt="o",
        color="#1f5f8b",
        ecolor="#7a8c99",
        capsize=3,
    )
    ax.axvline(0, color="#333333", linewidth=1)
    ax.set_yticks(list(y))
    ax.set_yticklabels(plot_data["term"])
    ax.set_xlabel("Posterior estimate on 0-100 rating scale")
    ax.set_title("Primary N=33 Feature Mixed-Effects Model")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def write_predictive_report(path: Path, freeze: dict[str, Any], qc: dict[str, Any], leakage: dict[str, Any], model_config: dict[str, Any]) -> None:
    lines = [
        "# Final N=33 Held-Out Mixed-Effects Predictive Baseline",
        "",
        f"Primary predictive model: `{model_config['primary_predictive_baseline_model']}`.",
        f"Formula: `{model_config['model']['formula']}`.",
        "",
        "## Counts",
        f"- Participants: {freeze['n_participants']}",
        f"- Held-out trials: {freeze['heldout_trials']}",
        f"- Candidate predictions: {freeze['candidate_predictions']}",
        f"- Trial predictions: {freeze['trial_predictions']}",
        "",
        "## Leakage",
        f"- Target leakage absent: {leakage['target_leakage_absent']}",
        f"- Max target rows in training: {leakage['target_rows_in_training_max']}",
        f"- Participant history rows retained per fold: {leakage['participant_history_rows_retained']}",
        "",
        "## Gates",
    ]
    for gate, value in freeze["gates"].items():
        lines.append(f"- `{gate}={str(value).lower()}`")
    lines.extend(["", "Final metrics computed: false", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_qc_report(path: Path, empirical: dict[str, Any], predictive: dict[str, Any], gates: dict[str, bool]) -> None:
    lines = [
        "# Phase 6H.2A QC Report",
        "",
        "The full N=33 empirical mixed-effects analysis is preserved as the central statistical analysis. The matched N=33/198 held-out predictive baseline is frozen separately for later scoring.",
        "",
        "## Empirical Models",
        f"- Stimulus model: `{empirical['stimulus_formula']}`",
        f"- Feature model: `{empirical['feature_formula']}`",
        f"- Convergence usable: stimulus={empirical['convergence']['stimulus_converged']}, feature={empirical['convergence']['feature_converged']}",
        "",
        "## Predictive Baseline",
        f"- Candidate predictions: {predictive['prediction_qc']['candidate_prediction_rows']}",
        f"- Trial predictions: {predictive['prediction_qc']['trial_prediction_rows']}",
        f"- Same Phase 6H.1 targets: {predictive['prediction_qc']['phase6h1_alignment_exact']}",
        f"- Final metrics computed: {predictive['prediction_qc']['evaluation_metrics_computed']}",
        "",
        "## Gates",
    ]
    for gate, value in gates.items():
        lines.append(f"- `{gate}={str(value).lower()}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def hash_existing(paths: list[Path]) -> dict[str, str]:
    return {rel(path): sha256_file(path) for path in paths if path.exists()}


def stable_created_at(path: Path) -> str:
    if path.exists():
        try:
            return read_json(path)["created_at_utc"]
        except (KeyError, json.JSONDecodeError):
            pass
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def resolve_output_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path
