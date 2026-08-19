"""Phase 6H.1 ground-truth join and evaluation protocol freeze."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_experiments.inference.records import canonical_json, portable_artifact_path, sha256_file, write_json_atomic, write_jsonl


OUTPUT_DIR = Path("llm-experiments/outputs/real/phase6h1")
PHASE6B_DIR = Path("llm-experiments/outputs/real/phase6b")
PHASE6G3_DIR = Path("llm-experiments/outputs/real/phase6g3")
PHASE6G5_DIR = Path("llm-experiments/outputs/real/phase6g5")
REAL_DATA_DIR = Path("statistical-baseline/data/real")
REAL_STIMULUS_MODEL_DIR = Path("statistical-baseline/outputs/real_stimulus_model")
REAL_FEATURE_MODEL_DIR = Path("statistical-baseline/outputs/real_feature_model")
REAL_HELDOUT_DIR = Path("statistical-baseline/outputs/real_heldout_evaluation/frozen_phase6_split")

PREDICTION_EXAMPLES = PHASE6B_DIR / "final_prediction_examples.jsonl"
PROMPT_DATA_OBJECTS = PHASE6B_DIR / "final_prompt_data_objects.jsonl"
TRIAL_GROUND_TRUTH = PHASE6B_DIR / "final_trial_ground_truth_targets.csv"
PHASE6B_MANIFEST = PHASE6B_DIR / "phase6g1_real_phase6b_manifest.json"
PHASE6G3_FREEZE = PHASE6G3_DIR / "phase6g3_freeze_manifest.json"
PHASE6G5_PREDICTIONS = PHASE6G5_DIR / "final_llm_predictions.jsonl"
PHASE6G5_FREEZE = PHASE6G5_DIR / "final_llm_prediction_freeze_manifest.json"
REAL_DATA_SUMMARY = REAL_DATA_DIR / "real_data_summary.csv"
REAL_RATINGS = REAL_DATA_DIR / "real_ratings_clean.csv"
REAL_PARTICIPANTS = REAL_DATA_DIR / "real_participants_clean.csv"

LABELS = ("A", "B", "C", "D", "E")
CONDITIONS = ("non_history", "personalised_history")
MODELS = ("gpt", "claude_sonnet", "llama_3_1_70b_instruct", "centaur")
RATING_MODELS = ("gpt", "claude_sonnet", "llama_3_1_70b_instruct")


def build_phase6h1_protocol_freeze(repo_root: Path, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    out = repo_root / output_dir
    out.mkdir(parents=True, exist_ok=True)

    examples = read_jsonl(repo_root / PREDICTION_EXAMPLES)
    prompt_objects = read_jsonl(repo_root / PROMPT_DATA_OBJECTS)
    predictions = read_jsonl(repo_root / PHASE6G5_PREDICTIONS)
    phase6b_manifest = load_json(repo_root / PHASE6B_MANIFEST)
    phase6g3_freeze = load_json(repo_root / PHASE6G3_FREEZE)
    phase6g5_freeze = load_json(repo_root / PHASE6G5_FREEZE)

    example_by_id = {row["prediction_example_id"]: row for row in examples}
    ground_truth = build_ground_truth_rows(examples, prompt_objects)
    joined = build_joined_rows(predictions, ground_truth)
    pairs = build_pair_manifest(ground_truth)
    tie_policy = build_tie_policy(ground_truth)
    metric_protocol = build_metric_protocol()
    fairness_audit = build_fairness_audit(repo_root, ground_truth, phase6b_manifest)
    mixed_status = build_mixed_effects_status(repo_root)
    data_summary = build_data_collection_summary(repo_root, ground_truth, phase6b_manifest)
    qc = build_qc_report_data(repo_root, ground_truth, joined, pairs, tie_policy, metric_protocol, fairness_audit, phase6b_manifest, phase6g3_freeze, phase6g5_freeze)

    paths = {
        "ground_truth_jsonl": out / "phase6h1_ground_truth_heldout.jsonl",
        "ground_truth_csv": out / "phase6h1_ground_truth_heldout.csv",
        "joined_jsonl": out / "phase6h1_joined_predictions_ground_truth.jsonl",
        "joined_csv": out / "phase6h1_joined_predictions_ground_truth.csv",
        "pair_manifest": out / "phase6h1_personalisation_pair_manifest.json",
        "tie_policy": out / "phase6h1_tie_policy.json",
        "metric_protocol": out / "phase6h1_metric_protocol.json",
        "fairness_audit": out / "phase6h1_mixed_effects_fairness_audit.json",
        "mixed_status": out / "phase6h1_mixed_effects_status.json",
        "data_summary": out / "phase6h1_data_collection_summary.json",
        "freeze_manifest": out / "phase6h1_evaluation_protocol_freeze_manifest.json",
        "qc_report": out / "phase6h1_qc_report.md",
    }

    write_jsonl(paths["ground_truth_jsonl"], ground_truth)
    write_ground_truth_csv(paths["ground_truth_csv"], ground_truth)
    write_jsonl(paths["joined_jsonl"], joined)
    write_joined_csv(paths["joined_csv"], joined)
    write_json_atomic(paths["pair_manifest"], pairs)
    write_json_atomic(paths["tie_policy"], tie_policy)
    write_json_atomic(paths["metric_protocol"], metric_protocol)
    write_json_atomic(paths["fairness_audit"], fairness_audit)
    write_json_atomic(paths["mixed_status"], mixed_status)
    write_json_atomic(paths["data_summary"], data_summary)

    manifest = build_freeze_manifest(repo_root, output_dir, paths, qc, phase6b_manifest, phase6g3_freeze, phase6g5_freeze)
    write_json_atomic(paths["freeze_manifest"], manifest)
    write_qc_markdown(paths["qc_report"], qc, tie_policy, metric_protocol, fairness_audit, mixed_status, data_summary, manifest)

    return {
        "ground_truth": ground_truth,
        "joined": joined,
        "pair_manifest": pairs,
        "tie_policy": tie_policy,
        "metric_protocol": metric_protocol,
        "fairness_audit": fairness_audit,
        "mixed_effects_status": mixed_status,
        "data_collection_summary": data_summary,
        "qc": qc,
        "freeze_manifest": manifest,
        "paths": {key: portable_artifact_path(path) for key, path in paths.items()},
        "example_by_id_count": len(example_by_id),
    }


def build_ground_truth_rows(examples: list[dict[str, Any]], prompt_objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prompt_keys = {(row["prediction_example_id"], row["condition"]): row for row in prompt_objects}
    rows: list[dict[str, Any]] = []
    for example in sorted(examples, key=lambda row: row["prediction_example_id"]):
        prediction_example_id = example["prediction_example_id"]
        target = example["input_data"]["target"]
        truth = example["ground_truth"]
        ratings = {label: numeric(truth["human_ratings"][label]) for label in LABELS}
        ranks = rank_with_ties(ratings)
        max_rating = max(ratings.values())
        winners = [label for label in LABELS if ratings[label] == max_rating]
        any_ties = any(count > 1 for count in Counter(ratings.values()).values())
        candidates = {
            candidate["presentation_label"]: {
                "presentation_label": candidate["presentation_label"],
                "stimulus_id": candidate["stimulus_id"],
                "actual_mix_id": candidate["actual_mix_id"],
                "audio_path": candidate.get("audio_path"),
                "z_RMS": candidate.get("z_RMS"),
                "z_CF": candidate.get("z_CF"),
                "z_SW": candidate.get("z_SW"),
            }
            for candidate in target["candidates"]
        }
        for condition in CONDITIONS:
            prompt = prompt_keys[(prediction_example_id, condition)]
            canonical_request_key = f"{prompt['condition_object_id']}__phase6d_prompt_spec_v1"
            rows.append(
                {
                    "schema_version": "phase6h1_ground_truth_heldout_v1",
                    "canonical_request_key": canonical_request_key,
                    "paired_example_id": prediction_example_id,
                    "prediction_example_id": prediction_example_id,
                    "participant_id": example["participant_id"],
                    "group": target["song"]["excerpt_id"].split("_song_", 1)[0],
                    "trial_id": target["trial_id"],
                    "heldout_trial_id": target["trial_id"],
                    "trial_order": target["trial_order"],
                    "trial_index": target["trial_index"],
                    "episode": target["episode"]["episode_id"],
                    "episode_context_title": target["episode"]["context_title"],
                    "episode_context_label": target["episode"]["context_label"],
                    "episode_context_dominant_function": target["episode"]["context_dominant_function"],
                    "song_id": target["song"]["song_id"],
                    "excerpt_id": target["song"]["excerpt_id"],
                    "condition": condition,
                    "candidate_mapping": candidates,
                    **{f"actual_rating_{label}": ratings[label] for label in LABELS},
                    "actual_preferred_mix": winners[0] if len(winners) == 1 else None,
                    "actual_top_tie_set": winners,
                    "actual_ranking": ranks,
                    "tie_status": "top_rating_tie" if len(winners) > 1 else ("non_top_tie" if any_ties else "no_ties"),
                    "top_tie_count": len(winners),
                    "tie_count": sum(1 for count in Counter(ratings.values()).values() if count > 1),
                    "has_any_rating_tie": any_ties,
                    "winner_set_if_tied": winners if len(winners) > 1 else [],
                    "source_prediction_examples_path": PREDICTION_EXAMPLES.as_posix(),
                    "source_trial_ground_truth_path": TRIAL_GROUND_TRUTH.as_posix(),
                }
            )
    return rows


def build_joined_rows(predictions: list[dict[str, Any]], ground_truth: list[dict[str, Any]]) -> list[dict[str, Any]]:
    truth_by_key = {row["canonical_request_key"]: row for row in ground_truth}
    joined = []
    for prediction in sorted(predictions, key=lambda row: (row["model_key"], row["canonical_request_key"])):
        truth = truth_by_key[prediction["canonical_request_key"]]
        ratings = prediction.get("predicted_ratings") if isinstance(prediction.get("predicted_ratings"), dict) else {}
        row = {
            "schema_version": "phase6h1_joined_prediction_ground_truth_v1",
            "model_key": prediction["model_key"],
            "experiment_model_label": prediction["experiment_model_label"],
            "canonical_request_key": prediction["canonical_request_key"],
            "request_id": prediction["request_id"],
            "prediction_example_id": prediction["prediction_example_id"],
            "paired_example_id": truth["paired_example_id"],
            "participant_id": truth["participant_id"],
            "group": truth["group"],
            "episode": truth["episode"],
            "song_id": truth["song_id"],
            "condition": prediction["condition"],
            "heldout_trial_id": truth["heldout_trial_id"],
            "candidate_mapping": truth["candidate_mapping"],
            **{f"actual_rating_{label}": truth[f"actual_rating_{label}"] for label in LABELS},
            "actual_preferred_mix": truth["actual_preferred_mix"],
            "actual_top_tie_set": truth["actual_top_tie_set"],
            "actual_ranking": truth["actual_ranking"],
            "tie_status": truth["tie_status"],
            "predicted_preferred_mix": prediction["predicted_preferred_mix"],
            "predicted_ranking": prediction["predicted_ranking"],
            "predicted_ratings": prediction["predicted_ratings"],
            "predicted_ratings_supported": prediction["predicted_ratings_supported"],
            **{f"predicted_rating_{label}": ratings.get(label) for label in LABELS},
            "centaur_candidate_probabilities": prediction.get("centaur_candidate_probabilities"),
            "centaur_candidate_log_likelihoods": prediction.get("centaur_candidate_log_likelihoods"),
            "centaur_scoring_definition": prediction.get("centaur_scoring_definition"),
            "source_prediction_prompt_hash": prediction["prompt_hash"],
        }
        joined.append(row)
    return joined


def build_pair_manifest(ground_truth: list[dict[str, Any]]) -> dict[str, Any]:
    by_example: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ground_truth:
        by_example[row["paired_example_id"]].append(row)
    pairs = []
    failures = []
    for example_id in sorted(by_example):
        rows = sorted(by_example[example_id], key=lambda row: row["condition"])
        conditions = sorted(row["condition"] for row in rows)
        target_hashes = {ground_truth_target_hash(row) for row in rows}
        valid = conditions == sorted(CONDITIONS) and len(target_hashes) == 1
        if not valid:
            failures.append({"paired_example_id": example_id, "conditions": conditions, "target_hash_count": len(target_hashes)})
        pairs.append(
            {
                "paired_example_id": example_id,
                "prediction_example_id": example_id,
                "conditions": conditions,
                "canonical_request_keys": [row["canonical_request_key"] for row in rows],
                "same_target_human_outcome": len(target_hashes) == 1,
                "valid_pair": valid,
            }
        )
    return {
        "schema_version": "phase6h1_personalisation_pair_manifest_v1",
        "underlying_heldout_examples": len(by_example),
        "expected_underlying_heldout_examples": 198,
        "request_condition_targets": len(ground_truth),
        "expected_request_condition_targets": 396,
        "pairing_rule": "paired_example_id = prediction_example_id; exactly one non_history and one personalised_history request-condition target per held-out example",
        "pairs": pairs,
        "failures": failures,
        "PERSONALISATION_PAIRING_VALID": len(failures) == 0 and len(by_example) == 198 and len(ground_truth) == 396,
    }


def build_tie_policy(ground_truth: list[dict[str, Any]]) -> dict[str, Any]:
    unique_examples = unique_by_pair(ground_truth)
    top_ties = [row for row in unique_examples if row["top_tie_count"] > 1]
    non_top_ties = [row for row in unique_examples if row["has_any_rating_tie"] and row["top_tie_count"] == 1]
    return {
        "schema_version": "phase6h1_tie_policy_v1",
        "defined_before_final_scoring": True,
        "unique_highest_rated_mix_trials": len(unique_examples) - len(top_ties),
        "top_rating_tie_trials": len(top_ties),
        "non_top_rating_tie_trials": len(non_top_ties),
        "any_rating_tie_trials": sum(1 for row in unique_examples if row["has_any_rating_tie"]),
        "top1_policy": "set_based_credit_for_top_ties",
        "top1_numerator": "prediction is correct when predicted_preferred_mix is a member of actual_top_tie_set",
        "top1_denominator": "all target examples with a valid prediction and reconstructed ground truth; tied-top examples are retained",
        "ranking_policy": "human rankings use average ranks for tied 0-100 ratings; predicted explicit rankings map to ordinal ranks 1..5 unless a model exposes tied predicted scores, in which case tied predicted scores may also use average ranks for rating-derived diagnostics",
        "applies_identically_to": [*MODELS, "mixed_effects_predictive_baseline"],
        "alphabetic_tiebreak_for_human_truth": False,
        "TIE_POLICY_FROZEN": True,
    }


def build_metric_protocol() -> dict[str, Any]:
    return {
        "schema_version": "phase6h1_metric_protocol_v1",
        "final_metrics_computed": False,
        "primary_prediction_metric": {
            "name": "preferred_mix_top1_accuracy",
            "chance_level": 0.20,
            "winner_definition": "human actual_top_tie_set derived from maximum A-E rating",
            "tie_handling": "set_based_credit_for_top_ties",
            "numerator": "count of scorable predictions whose predicted_preferred_mix is in actual_top_tie_set",
            "denominator": "count of scorable joined rows for the method/condition under analysis",
        },
        "primary_ranking_metric": {
            "name": "spearman_rank_correlation",
            "human_rank_handling": "average ranks for tied human ratings",
            "predicted_rank_handling": "explicit prediction order A-E to ranks 1..5; rating-derived predicted ties may use average ranks as a diagnostic",
        },
        "rating_prediction_metrics": {
            "primary": "MAE over candidate A-E ratings",
            "secondary": "RMSE over candidate A-E ratings",
            "descriptive": "candidate-level correlation",
            "applicable_models": list(RATING_MODELS) + ["mixed_effects_predictive_baseline"],
            "excluded_models": {"centaur": "native likelihood/probability outputs are not 0-100 ratings and must not be converted into fake ratings"},
        },
        "personalisation_metric": {
            "comparison": "personalised_history vs non_history",
            "unit": "paired held-out prediction_example_id within each model",
            "statistical_design_for_later_phase": "paired within-example comparison; no significance testing in Phase 6H.1",
        },
        "METRIC_PROTOCOL_FROZEN": True,
    }


def build_fairness_audit(repo_root: Path, ground_truth: list[dict[str, Any]], phase6b_manifest: dict[str, Any]) -> dict[str, Any]:
    llm_examples = {row["paired_example_id"] for row in ground_truth}
    old_manifest_path = repo_root / REAL_HELDOUT_DIR / "evaluation_manifest.json"
    old_manifest = load_json(old_manifest_path) if old_manifest_path.exists() else {}
    old_split_path = repo_root / REAL_HELDOUT_DIR / "heldout_split_manifest.csv"
    old_split = read_csv(old_split_path) if old_split_path.exists() else []
    old_examples = {f"{row['participant_id']}__heldout__{row['trial_id']}" for row in old_split}
    matched_old = sorted(llm_examples & old_examples)
    missing_old = sorted(llm_examples - old_examples)
    return {
        "schema_version": "phase6h1_mixed_effects_fairness_audit_v1",
        "training_test_alignment": {
            "llm_frozen_underlying_examples": len(llm_examples),
            "existing_heldout_baseline_underlying_examples": len(old_examples),
            "same_heldout_targets": llm_examples == old_examples,
            "matched_existing_baseline_examples": len(matched_old),
            "llm_examples_missing_from_existing_baseline": len(missing_old),
            "assessment": "The frozen LLM evaluation uses the current N=33 Phase 6B universe (198 trials). The existing frozen_phase6_split mixed-effects heldout baseline uses an older N=30 universe (180 trials), so it is not a complete direct baseline for final LLM comparison.",
            "corrected_matched_evaluation_available": "A matched N=30 subset can be constructed from the existing heldout baseline, but the fair final comparison should refit or rebuild the mixed-effects predictive baseline on the same N=33/198 held-out targets.",
        },
        "information_alignment": {
            "mixed_effects_model": [
                "training participant observations excluding the held-out participant-trial target",
                "episode/context and group predictors",
                "stimulus random effect when stimulus is represented in training",
                "participant random effect when participant has other training trials",
                "acoustic predictors for the primary acoustic baseline where applicable",
            ],
            "llm_non_history": [
                "frozen target context",
                "participant metadata",
                "candidate A-E acoustic features",
                "no prior participant trial ratings or comments",
            ],
            "llm_personalised_history": [
                "same base information as non_history",
                "five prior/non-target participant trials with ratings and comments",
            ],
            "information_parity_claimed": False,
        },
        "fairness_principle": {
            "same_test_targets_required": True,
            "same_winner_definition_required": True,
            "same_ranking_target_required": True,
            "same_rating_targets_where_supported": True,
            "no_mixed_effects_training_on_heldout_target": True,
            "no_llm_access_to_heldout_outcomes": True,
            "document_information_set_differences": True,
        },
        "existing_baseline_artifacts": {
            "path": REAL_HELDOUT_DIR.as_posix(),
            "evaluation_manifest_sha256": sha256_file(old_manifest_path) if old_manifest_path.exists() else None,
            "real_data_source": old_manifest.get("real_data_source"),
            "real_data_sha256": old_manifest.get("real_data_sha256"),
            "n_participants": old_manifest.get("n_participants"),
            "n_trials": old_manifest.get("n_trials"),
            "models": old_manifest.get("models", []),
            "validation_passed": old_manifest.get("validation_passed"),
        },
        "MIXED_EFFECTS_COMPARISON_FAIRNESS_AUDITED": True,
        "same_heldout_examples_as_llm": llm_examples == old_examples,
        "mixed_effects_refit_required_before_final_comparison": llm_examples != old_examples,
    }


def build_mixed_effects_status(repo_root: Path) -> dict[str, Any]:
    stimulus_manifest_path = repo_root / REAL_STIMULUS_MODEL_DIR / "real_stimulus_model_manifest.json"
    feature_manifest_path = repo_root / REAL_FEATURE_MODEL_DIR / "real_feature_model_manifest.json"
    stimulus_diag_path = repo_root / REAL_STIMULUS_MODEL_DIR / "convergence_diagnostics.csv"
    feature_diag_path = repo_root / REAL_FEATURE_MODEL_DIR / "convergence_diagnostics.csv"
    stimulus_manifest = load_json(stimulus_manifest_path) if stimulus_manifest_path.exists() else {}
    feature_manifest = load_json(feature_manifest_path) if feature_manifest_path.exists() else {}
    stimulus_diag = read_csv(stimulus_diag_path) if stimulus_diag_path.exists() else []
    feature_diag = read_csv(feature_diag_path) if feature_diag_path.exists() else []
    incomplete_markers = [
        portable_artifact_path(path)
        for path in [repo_root / REAL_STIMULUS_MODEL_DIR / "INCOMPLETE_PENDING_QMUL_RERUN.txt", repo_root / REAL_FEATURE_MODEL_DIR / "INCOMPLETE_PENDING_QMUL_RERUN.txt"]
        if path.exists()
    ]
    diagnostics = stimulus_diag + feature_diag
    convergence_ok = bool(diagnostics) and all(
        int(float(row.get("divergences", 999))) == 0
        and float(row.get("max_rhat", 999)) <= 1.01
        and float(row.get("min_bulk_ess", 0)) >= 400
        and float(row.get("min_tail_ess", 0)) >= 400
        for row in diagnostics
    )
    return {
        "schema_version": "phase6h1_mixed_effects_status_v1",
        "central_empirical_role": "primary evidence for listener/context/stimulus preference variation, not a secondary ML baseline",
        "stimulus_model": {
            "manifest_path": REAL_STIMULUS_MODEL_DIR.joinpath("real_stimulus_model_manifest.json").as_posix(),
            "formula": stimulus_manifest.get("final_formula"),
            "analysable_n": stimulus_manifest.get("cleaned_dataset", {}).get("analysable_n"),
            "rating_count": stimulus_manifest.get("cleaned_dataset", {}).get("rating_count"),
            "trial_count": stimulus_manifest.get("cleaned_dataset", {}).get("trial_count"),
            "final_gate": stimulus_manifest.get("final_gate"),
            "diagnostics": stimulus_diag,
        },
        "feature_model": {
            "manifest_path": REAL_FEATURE_MODEL_DIR.joinpath("real_feature_model_manifest.json").as_posix(),
            "primary_formula": feature_manifest.get("primary_formula"),
            "si_formula": feature_manifest.get("si_formula"),
            "bounded_sensitivity_formula": feature_manifest.get("bounded_sensitivity_formula"),
            "analysable_n": feature_manifest.get("cleaned_dataset", {}).get("analysable_n"),
            "rating_count": feature_manifest.get("cleaned_dataset", {}).get("rating_count"),
            "trial_count": feature_manifest.get("cleaned_dataset", {}).get("trial_count"),
            "final_gate": feature_manifest.get("final_gate"),
            "diagnostics": feature_diag,
        },
        "convergence_qc_status": {
            "n33_model_artifacts_present": bool(stimulus_manifest and feature_manifest),
            "diagnostics_indicate_satisfactory_convergence": convergence_ok,
            "incomplete_pending_qmul_rerun_markers_present": bool(incomplete_markers),
            "incomplete_marker_paths": incomplete_markers,
            "phase6h1_assessment": "N=33 empirical model manifests and diagnostics are present and diagnostics look satisfactory, but stale/inconsistent INCOMPLETE_PENDING_QMUL_RERUN marker files remain and should be resolved before final dissertation conclusions.",
        },
        "mixed_effects_refit_required_before_final_conclusions": bool(incomplete_markers),
    }


def build_data_collection_summary(repo_root: Path, ground_truth: list[dict[str, Any]], phase6b_manifest: dict[str, Any]) -> dict[str, Any]:
    summary_rows = read_csv(repo_root / REAL_DATA_SUMMARY)
    summary = summary_rows[0] if summary_rows else {}
    participants = read_csv(repo_root / REAL_PARTICIPANTS)
    unique_examples = unique_by_pair(ground_truth)
    participant_groups = {row["participant_id"]: row["group"] for row in unique_examples}
    groups = Counter(participant_groups.values())
    return {
        "schema_version": "phase6h1_data_collection_summary_v1",
        "dataset_contribution_statement": "The real listening-study dataset is a core empirical contribution: it supplies participant-specific, randomized five-mix ratings and comments for modelling listener/context preference variation.",
        "participant_count": int(summary.get("final_recommended_analysable_n") or phase6b_manifest["counts"]["participant_count"]),
        "participant_ids": sorted({row["participant_id"] for row in unique_examples}),
        "group_counts": dict(sorted(groups.items())),
        "study_design": "Each analysable participant rated five randomized candidate mixes across six participant-song-episode trials.",
        "ratings_per_participant": 30,
        "total_individual_mix_ratings": int(summary.get("final_analysable_rating_rows") or phase6b_manifest["counts"]["candidate_row_count"]),
        "total_trials": int(summary.get("participant_song_episode_trials") or phase6b_manifest["counts"]["trial_count"]),
        "songs": sorted({row["song_id"] for row in unique_examples}),
        "episodes": sorted({row["episode"] for row in unique_examples}),
        "stimuli": int(summary.get("stimuli_found") or 0),
        "randomisation": "A-E presentation labels are trial-specific and reconstructed from the frozen Phase 6B candidate mappings.",
        "mandatory_comments": {
            "expected_trial_comments": int(summary.get("expected_comments_if_all_valid") or 0),
            "actual_trial_comments": int(summary.get("actual_trial_comments") or 0),
            "missing_blank_rating_row_comments": int(summary.get("missing_blank_rating_row_comments") or 0),
        },
        "final_usable_observations": {
            "participants": phase6b_manifest["counts"]["participant_count"],
            "trials": phase6b_manifest["counts"]["trial_count"],
            "candidate_rating_rows": phase6b_manifest["counts"]["candidate_row_count"],
        },
        "heldout_prediction_examples": len(unique_examples),
        "request_condition_targets": len(ground_truth),
        "post_freeze_additional_responses_detected": len(participants) > phase6b_manifest["counts"]["participant_count"] if participants else False,
    }


def build_qc_report_data(
    repo_root: Path,
    ground_truth: list[dict[str, Any]],
    joined: list[dict[str, Any]],
    pairs: dict[str, Any],
    tie_policy: dict[str, Any],
    metric_protocol: dict[str, Any],
    fairness_audit: dict[str, Any],
    phase6b_manifest: dict[str, Any],
    phase6g3_freeze: dict[str, Any],
    phase6g5_freeze: dict[str, Any],
) -> dict[str, Any]:
    unique_examples = unique_by_pair(ground_truth)
    participant_groups = {row["participant_id"]: row["group"] for row in unique_examples}
    model_counts = Counter(row["model_key"] for row in joined)
    condition_by_model: dict[str, Counter] = defaultdict(Counter)
    for row in joined:
        condition_by_model[row["model_key"]][row["condition"]] += 1
    duplicate_model_request = duplicate_count((row["model_key"], row["canonical_request_key"]) for row in joined)
    gates = {
        "GROUND_TRUTH_HELDOUT_JOIN_VALID": len(ground_truth) == 396 and len(unique_examples) == 198,
        "ALL_396_TARGETS_RECONSTRUCTED": len(ground_truth) == 396,
        "ALL_1584_MODEL_ROWS_JOINED": len(joined) == 1584,
        "PERSONALISATION_PAIRING_VALID": pairs["PERSONALISATION_PAIRING_VALID"],
        "TIE_POLICY_FROZEN": tie_policy["TIE_POLICY_FROZEN"],
        "METRIC_PROTOCOL_FROZEN": metric_protocol["METRIC_PROTOCOL_FROZEN"],
        "MIXED_EFFECTS_COMPARISON_FAIRNESS_AUDITED": fairness_audit["MIXED_EFFECTS_COMPARISON_FAIRNESS_AUDITED"],
    }
    gates["PHASE6H1_EVALUATION_PROTOCOL_FROZEN"] = all(gates.values())
    return {
        "schema_version": "phase6h1_qc_summary_v1",
        "participant_count": len({row["participant_id"] for row in unique_examples}),
        "participant_ids": sorted({row["participant_id"] for row in unique_examples}),
        "group_counts": dict(sorted(Counter(participant_groups.values()).items())),
        "total_trials": len(unique_examples),
        "total_individual_mix_ratings": len(unique_examples) * len(LABELS),
        "heldout_prediction_examples": len(unique_examples),
        "request_condition_targets": len(ground_truth),
        "joined_model_rows": len(joined),
        "rows_per_model": dict(sorted(model_counts.items())),
        "condition_counts_by_model": {model: dict(sorted(counter.items())) for model, counter in sorted(condition_by_model.items())},
        "duplicate_model_request_keys": duplicate_model_request,
        "candidate_mapping_valid": all(sorted(row["candidate_mapping"]) == list(LABELS) for row in ground_truth),
        "ground_truth_source_matches_phase6b": phase6b_manifest["counts"]["prediction_example_count"] == len(unique_examples),
        "phase6g3_rendered_prompt_count": phase6g3_freeze["rendered_prompt_count"],
        "phase6g5_total_predictions": phase6g5_freeze["total_predictions"],
        "prediction_hashes_preserved": sha256_file(repo_root / PHASE6G5_PREDICTIONS) == phase6g5_freeze["final_jsonl_hash"],
        "no_target_leakage_in_inference_artifacts": phase6g3_freeze["leakage_status"]["contains_hidden_ground_truth"] is False
        and phase6g5_freeze["hidden_ground_truth_loaded"] is False,
        "final_metrics_computed": False,
        "gates": gates,
    }


def build_freeze_manifest(
    repo_root: Path,
    output_dir: Path,
    paths: dict[str, Path],
    qc: dict[str, Any],
    phase6b_manifest: dict[str, Any],
    phase6g3_freeze: dict[str, Any],
    phase6g5_freeze: dict[str, Any],
) -> dict[str, Any]:
    existing = repo_root / output_dir / "phase6h1_evaluation_protocol_freeze_manifest.json"
    created_at = load_json(existing).get("created_at_utc") if existing.exists() else datetime.now(timezone.utc).isoformat()
    source_paths = [
        PREDICTION_EXAMPLES,
        PROMPT_DATA_OBJECTS,
        TRIAL_GROUND_TRUTH,
        PHASE6B_MANIFEST,
        PHASE6G3_FREEZE,
        PHASE6G5_PREDICTIONS,
        PHASE6G5_FREEZE,
        REAL_DATA_SUMMARY,
        REAL_RATINGS,
        REAL_PARTICIPANTS,
    ]
    return {
        "schema_version": "phase6h1_evaluation_protocol_freeze_manifest_v1",
        "created_at_utc": created_at,
        "phase": "6H.1",
        "statement": "Ground truth has been joined after Phase 6G.5 prediction freeze; final comparative metrics remain uncomputed.",
        "source_hashes": {path.as_posix(): sha256_file(repo_root / path) for path in source_paths if (repo_root / path).exists()},
        "phase6g5_prediction_hashes": {
            "final_jsonl_hash": phase6g5_freeze["final_jsonl_hash"],
            "final_csv_hash": phase6g5_freeze["final_csv_hash"],
            "source_hashes": phase6g5_freeze["source_hashes"],
        },
        "ground_truth_source": {
            "authoritative_prediction_examples": PREDICTION_EXAMPLES.as_posix(),
            "authoritative_trial_ground_truth": TRIAL_GROUND_TRUTH.as_posix(),
            "locked_raw_dataset": phase6b_manifest["locked_dataset_path"],
            "locked_raw_dataset_sha256": phase6b_manifest["locked_dataset_sha256"],
        },
        "canonical_request_alignment": {
            "phase6g3_rendered_prompt_count": phase6g3_freeze["rendered_prompt_count"],
            "phase6g5_prediction_count": phase6g5_freeze["total_predictions"],
            "phase6h1_ground_truth_request_condition_targets": qc["request_condition_targets"],
            "phase6h1_joined_prediction_rows": qc["joined_model_rows"],
        },
        "tie_policy": portable_artifact_path(paths["tie_policy"]),
        "metric_protocol": portable_artifact_path(paths["metric_protocol"]),
        "personalisation_pairing_rule": "prediction_example_id is the paired-example identifier; condition varies within pair",
        "mixed_effects_comparison_rule": "Final direct comparison requires the same N=33/198 held-out target examples or an explicitly labelled matched subset.",
        "excluded_unsupported_metrics_by_model": {"centaur": ["0-100 rating MAE", "0-100 rating RMSE", "rating correlation"]},
        "ground_truth_join_performed": True,
        "final_metrics_computed": False,
        "evaluation_protocol_frozen": qc["gates"]["PHASE6H1_EVALUATION_PROTOCOL_FROZEN"],
        "artifact_hashes": {
            portable_artifact_path(path): sha256_file(path)
            for path in paths.values()
            if path.name not in {"phase6h1_evaluation_protocol_freeze_manifest.json", "phase6h1_qc_report.md"} and path.exists()
        },
        "gates": qc["gates"],
    }


def rank_with_ties(values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(LABELS, key=lambda label: values[label], reverse=True)
    ranks: dict[str, float] = {}
    pos = 1
    index = 0
    while index < len(ordered):
        tied = [ordered[index]]
        while index + len(tied) < len(ordered) and values[ordered[index + len(tied)]] == values[ordered[index]]:
            tied.append(ordered[index + len(tied)])
        average = (pos + pos + len(tied) - 1) / 2
        for label in tied:
            ranks[label] = average
        pos += len(tied)
        index += len(tied)
    return ranks


def ground_truth_target_hash(row: dict[str, Any]) -> str:
    return canonical_json({key: row[key] for key in ["participant_id", "heldout_trial_id", "actual_top_tie_set", "actual_ranking", *[f"actual_rating_{label}" for label in LABELS]]})


def unique_by_pair(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = {}
    for row in rows:
        seen.setdefault(row["paired_example_id"], row)
    return [seen[key] for key in sorted(seen)]


def duplicate_count(keys: Any) -> int:
    counts = Counter(keys)
    return sum(count - 1 for count in counts.values() if count > 1)


def numeric(value: Any) -> int | float:
    return int(value) if float(value).is_integer() else float(value)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_ground_truth_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "canonical_request_key",
        "prediction_example_id",
        "participant_id",
        "group",
        "heldout_trial_id",
        "episode",
        "song_id",
        "condition",
        *[f"actual_rating_{label}" for label in LABELS],
        "actual_preferred_mix",
        "actual_top_tie_set_json",
        "actual_ranking_json",
        "tie_status",
        "top_tie_count",
        "candidate_mapping_json",
    ]
    write_rows_csv(path, rows, fieldnames)


def write_joined_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "model_key",
        "experiment_model_label",
        "canonical_request_key",
        "request_id",
        "prediction_example_id",
        "participant_id",
        "group",
        "episode",
        "song_id",
        "condition",
        *[f"actual_rating_{label}" for label in LABELS],
        "actual_preferred_mix",
        "actual_top_tie_set_json",
        "actual_ranking_json",
        "predicted_preferred_mix",
        "predicted_ranking_json",
        "predicted_ratings_supported",
        *[f"predicted_rating_{label}" for label in LABELS],
        "centaur_candidate_probabilities_json",
        "centaur_candidate_log_likelihoods_json",
        "candidate_mapping_json",
    ]
    write_rows_csv(path, rows, fieldnames)


def write_rows_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            output = {}
            for field in fieldnames:
                source = field[:-5] if field.endswith("_json") else field
                value = row.get(source)
                output[field] = canonical_json(value) if field.endswith("_json") and value is not None else value
            writer.writerow(output)


def write_qc_markdown(
    path: Path,
    qc: dict[str, Any],
    tie_policy: dict[str, Any],
    metric_protocol: dict[str, Any],
    fairness_audit: dict[str, Any],
    mixed_status: dict[str, Any],
    data_summary: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    lines = [
        "# Phase 6H.1 QC Report",
        "",
        "Phase 6H.1 joins the frozen Phase 6G.5 prediction package to the frozen Phase 6B held-out human outcomes and freezes the evaluation protocol. Final model metrics are not computed here.",
        "",
        "## Reconstruction",
        f"- Participants: {qc['participant_count']} ({qc['group_counts']})",
        f"- Held-out examples: {qc['heldout_prediction_examples']}",
        f"- Request-condition targets: {qc['request_condition_targets']}",
        f"- Joined model rows: {qc['joined_model_rows']}",
        f"- Rows per model: {qc['rows_per_model']}",
        f"- Condition counts by model: {qc['condition_counts_by_model']}",
        "",
        "## Ties",
        f"- Unique highest-rated trials: {tie_policy['unique_highest_rated_mix_trials']}",
        f"- Top-rating tie trials: {tie_policy['top_rating_tie_trials']}",
        f"- Non-top tie trials: {tie_policy['non_top_rating_tie_trials']}",
        f"- Top-1 policy: {tie_policy['top1_policy']}",
        "",
        "## Metrics",
        f"- Primary metric: {metric_protocol['primary_prediction_metric']['name']} at nominal chance {metric_protocol['primary_prediction_metric']['chance_level']}",
        f"- Ranking metric: {metric_protocol['primary_ranking_metric']['name']}",
        f"- Rating metrics: {metric_protocol['rating_prediction_metrics']['primary']} and {metric_protocol['rating_prediction_metrics']['secondary']}",
        "- Centaur is excluded from rating-error metrics.",
        "",
        "## Mixed-Effects Fairness",
        f"- Same held-out examples as LLMs: {fairness_audit['same_heldout_examples_as_llm']}",
        f"- Existing baseline examples: {fairness_audit['training_test_alignment']['existing_heldout_baseline_underlying_examples']}",
        f"- Frozen LLM examples: {fairness_audit['training_test_alignment']['llm_frozen_underlying_examples']}",
        f"- Refit required before final comparison: {fairness_audit['mixed_effects_refit_required_before_final_comparison']}",
        f"- N=33 convergence diagnostics satisfactory: {mixed_status['convergence_qc_status']['diagnostics_indicate_satisfactory_convergence']}",
        f"- Incomplete rerun markers present: {mixed_status['convergence_qc_status']['incomplete_pending_qmul_rerun_markers_present']}",
        "",
        "## Data Collection",
        f"- Total ratings: {data_summary['total_individual_mix_ratings']}",
        f"- Trials: {data_summary['total_trials']}",
        f"- Songs: {data_summary['songs']}",
        f"- Episodes: {data_summary['episodes']}",
        "",
        "## Gates",
    ]
    for gate, value in manifest["gates"].items():
        lines.append(f"- `{gate}={str(value).lower()}`")
    lines.extend(["", f"Final metrics computed: {manifest['final_metrics_computed']}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")
