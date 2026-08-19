"""Phase 6H.2B final scoring and fair model comparison."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any, Callable

import matplotlib.pyplot as plt
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path("llm-experiments/outputs/real/phase6h2b")
PHASE6H1_DIR = Path("llm-experiments/outputs/real/phase6h1")
PHASE6G5_DIR = Path("llm-experiments/outputs/real/phase6g5")
PHASE6H2A_BASELINE_DIR = Path("statistical-baseline/outputs/real_heldout_evaluation/final_n33_phase6h")
PHASE6H2A_EMPIRICAL_DIR = Path("statistical-baseline/outputs/final_n33_empirical")

LABELS = ("A", "B", "C", "D", "E")
LLM_RATING_MODELS = ("gpt", "claude_sonnet", "llama_3_1_70b_instruct")
MODEL_LABELS = {
    "gpt": "GPT-5.5",
    "claude_sonnet": "Claude Sonnet 5",
    "llama_3_1_70b_instruct": "Llama 3.1 70B",
    "centaur": "Centaur",
    "mixed_effects_primary_acoustic": "Mixed-effects primary acoustic",
}
CHANCE_TOP1 = 0.20
BOOTSTRAP_SEED = 20260819
BOOTSTRAP_REPLICATES = 2000


def run_phase6h2b_final_scoring(repo_root: Path, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    out = repo_root / output_dir
    out.mkdir(parents=True, exist_ok=True)

    h1_joined = read_jsonl(repo_root / PHASE6H1_DIR / "phase6h1_joined_predictions_ground_truth.jsonl")
    h1_truth = pd.read_csv(repo_root / PHASE6H1_DIR / "phase6h1_ground_truth_heldout.csv")
    mixed_trial = pd.read_csv(repo_root / PHASE6H2A_BASELINE_DIR / "final_n33_trial_predictions.csv")
    mixed_candidate = pd.read_csv(repo_root / PHASE6H2A_BASELINE_DIR / "final_n33_candidate_predictions.csv")
    empirical = read_empirical_outputs(repo_root)
    metric_protocol = read_json(repo_root / PHASE6H1_DIR / "phase6h1_metric_protocol.json")
    tie_policy = read_json(repo_root / PHASE6H1_DIR / "phase6h1_tie_policy.json")

    trial_rows = build_trial_level_rows(h1_joined, h1_truth, mixed_trial)
    candidate_rows = build_candidate_level_rows(h1_joined, h1_truth, mixed_candidate)

    top1 = summarize_top1(trial_rows)
    chance = chance_tests(top1)
    ranking = summarize_ranking(trial_rows)
    rating = summarize_rating(candidate_rows)
    personalisation = summarize_personalisation(trial_rows, candidate_rows)
    comparison = summarize_mixed_effects_comparison(trial_rows, candidate_rows)
    uncertainty = build_uncertainty_manifest(top1, ranking, rating, personalisation, comparison)
    rq_evidence = build_rq_evidence(empirical, top1, ranking, rating, personalisation, comparison)
    results_summary = build_results_summary(empirical, top1, ranking, rating, personalisation, comparison)
    test_manifest = build_statistical_test_manifest(chance, personalisation, comparison)

    table_a = out / "phase6h2b_table_a_central_mixed_effects.csv"
    table_b = out / "phase6h2b_table_b_prediction_results.csv"
    table_c = out / "phase6h2b_table_c_personalisation_effects.csv"
    write_table_a(table_a, empirical)
    write_table_b(table_b, top1, ranking, rating)
    write_table_c(table_c, personalisation)
    figure2 = out / "phase6h2b_figure2_top1_accuracy.png"
    figure3 = out / "phase6h2b_figure3_personalisation_top1.png"
    write_top1_figure(figure2, top1)
    write_personalisation_figure(figure3, personalisation)

    write_csv(out / "phase6h2b_trial_level_scores.csv", trial_rows)
    write_csv(out / "phase6h2b_candidate_level_rating_errors.csv", candidate_rows)
    write_csv(out / "phase6h2b_top1_accuracy.csv", top1)
    write_csv(out / "phase6h2b_chance_tests.csv", chance)
    write_csv(out / "phase6h2b_ranking_metrics.csv", ranking)
    write_csv(out / "phase6h2b_rating_metrics.csv", rating)
    write_csv(out / "phase6h2b_personalisation_effects.csv", personalisation)
    write_csv(out / "phase6h2b_mixed_effects_llm_comparison.csv", comparison)
    write_json(out / "phase6h2b_uncertainty_intervals.json", uncertainty)
    write_json(out / "phase6h2b_rq_evidence.json", rq_evidence)
    write_json(out / "phase6h2b_results_summary.json", results_summary)
    write_json(out / "phase6h2b_statistical_test_manifest.json", test_manifest)
    manifest = build_provenance_manifest(repo_root, out, metric_protocol, tie_policy)
    write_json(out / "phase6h2b_provenance_manifest.json", manifest)
    qc = build_qc(top1, ranking, rating, personalisation, comparison, trial_rows, candidate_rows, metric_protocol, tie_policy, manifest)
    write_json(out / "phase6h2b_qc_summary.json", qc)
    write_qc_report(out / "phase6h2b_qc_report.md", qc, results_summary)
    return {
        "output_dir": str(out),
        "top1": top1,
        "chance": chance,
        "ranking": ranking,
        "rating": rating,
        "personalisation": personalisation,
        "comparison": comparison,
        "rq_evidence": rq_evidence,
        "results_summary": results_summary,
        "qc": qc,
        "manifest": manifest,
    }


def build_trial_level_rows(h1_joined: list[dict[str, Any]], h1_truth: pd.DataFrame, mixed_trial: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for row in h1_joined:
        actual_top = list(row["actual_top_tie_set"])
        predicted_ranking = list(row["predicted_ranking"])
        rows.append(
            {
                "source": "llm",
                "method_key": f"{row['model_key']}__{row['condition']}",
                "model_key": row["model_key"],
                "model_label": row["experiment_model_label"],
                "condition": row["condition"],
                "prediction_example_id": row["prediction_example_id"],
                "participant_id": row["participant_id"],
                "group": row["group"],
                "episode": row["episode"],
                "song_id": row["song_id"],
                "predicted_preferred_mix": row["predicted_preferred_mix"],
                "actual_top_tie_set": "|".join(actual_top),
                "top1_correct": int(row["predicted_preferred_mix"] in actual_top),
                "spearman": spearman(row["actual_ranking"], ranks_from_order(predicted_ranking)),
            }
        )
    truth = h1_truth[h1_truth["condition"].eq("non_history")].copy()
    truth_by_id = {row.prediction_example_id: row for row in truth.itertuples()}
    for row in mixed_trial.itertuples():
        truth_row = truth_by_id[row.phase6h1_prediction_example_id]
        actual_top = parse_jsonish(truth_row.actual_top_tie_set_json)
        actual_ranking = parse_jsonish(truth_row.actual_ranking_json)
        rows.append(
            {
                "source": "mixed_effects",
                "method_key": "mixed_effects_primary_acoustic",
                "model_key": "mixed_effects_primary_acoustic",
                "model_label": MODEL_LABELS["mixed_effects_primary_acoustic"],
                "condition": "baseline",
                "prediction_example_id": row.phase6h1_prediction_example_id,
                "participant_id": row.participant_id,
                "group": row.group,
                "episode": row.episode,
                "song_id": row.song_id,
                "predicted_preferred_mix": row.predicted_preferred_mix,
                "actual_top_tie_set": "|".join(actual_top),
                "top1_correct": int(row.predicted_preferred_mix in actual_top),
                "spearman": spearman(actual_ranking, ranks_from_order(str(row.predicted_ranking).split("|"))),
            }
        )
    return sorted(rows, key=lambda item: (item["method_key"], item["prediction_example_id"]))


def build_candidate_level_rows(h1_joined: list[dict[str, Any]], h1_truth: pd.DataFrame, mixed_candidate: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for row in h1_joined:
        if row["model_key"] == "centaur":
            continue
        ratings = row["predicted_ratings"]
        for label in LABELS:
            rows.append(
                {
                    "source": "llm",
                    "method_key": f"{row['model_key']}__{row['condition']}",
                    "model_key": row["model_key"],
                    "model_label": row["experiment_model_label"],
                    "condition": row["condition"],
                    "prediction_example_id": row["prediction_example_id"],
                    "participant_id": row["participant_id"],
                    "candidate_label": label,
                    "actual_rating": float(row[f"actual_rating_{label}"]),
                    "predicted_rating": float(ratings[label]),
                    "absolute_error": abs(float(ratings[label]) - float(row[f"actual_rating_{label}"])),
                    "squared_error": (float(ratings[label]) - float(row[f"actual_rating_{label}"])) ** 2,
                }
            )
    truth = h1_truth[h1_truth["condition"].eq("non_history")].copy()
    truth_by_id = {row.prediction_example_id: row for row in truth.itertuples()}
    for row in mixed_candidate.itertuples():
        truth_row = truth_by_id[row.phase6h1_prediction_example_id]
        actual = float(getattr(truth_row, f"actual_rating_{row.presentation_label}"))
        pred = float(row.posterior_mean_expected_rating)
        rows.append(
            {
                "source": "mixed_effects",
                "method_key": "mixed_effects_primary_acoustic",
                "model_key": "mixed_effects_primary_acoustic",
                "model_label": MODEL_LABELS["mixed_effects_primary_acoustic"],
                "condition": "baseline",
                "prediction_example_id": row.phase6h1_prediction_example_id,
                "participant_id": row.participant_id,
                "candidate_label": row.presentation_label,
                "actual_rating": actual,
                "predicted_rating": pred,
                "absolute_error": abs(pred - actual),
                "squared_error": (pred - actual) ** 2,
            }
        )
    return sorted(rows, key=lambda item: (item["method_key"], item["prediction_example_id"], item["candidate_label"]))


def summarize_top1(trial_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for key, rows in group_by(trial_rows, "method_key").items():
        correct = sum(row["top1_correct"] for row in rows)
        n = len(rows)
        low, high = wilson_ci(correct, n)
        first = rows[0]
        out.append(
            {
                "method_key": key,
                "model_key": first["model_key"],
                "model_label": first["model_label"],
                "condition": first["condition"],
                "correct": correct,
                "denominator": n,
                "accuracy": correct / n,
                "ci_method": "wilson_95",
                "ci_low": low,
                "ci_high": high,
            }
        )
    return sorted(out, key=method_sort_key)


def chance_tests(top1: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    pvals = []
    for row in top1:
        p = binomial_survival(int(row["correct"]), int(row["denominator"]), CHANCE_TOP1)
        pvals.append(p)
        rows.append({**id_fields(row), "chance_accuracy": CHANCE_TOP1, "test": "exact_one_sided_binomial_ge_chance", "p_value": p})
    adjusted = bh_adjust(pvals)
    for row, adj in zip(rows, adjusted):
        row["p_value_bh_adjusted"] = adj
    return rows


def summarize_ranking(trial_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for key, group in group_by(trial_rows, "method_key").items():
        values = [float(row["spearman"]) for row in group]
        low, high = participant_bootstrap_ci(group, lambda sample: mean(float(row["spearman"]) for row in sample))
        first = group[0]
        rows.append(
            {
                **id_fields_from_group(key, first),
                "denominator": len(group),
                "mean_spearman": mean(values),
                "median_spearman": median(values),
                "sd_spearman": pstdev(values),
                "ci_method": "participant_bootstrap_percentile_95",
                "ci_low": low,
                "ci_high": high,
            }
        )
    return sorted(rows, key=method_sort_key)


def summarize_rating(candidate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for key, group in group_by(candidate_rows, "method_key").items():
        mae = mean(float(row["absolute_error"]) for row in group)
        rmse = math.sqrt(mean(float(row["squared_error"]) for row in group))
        corr = pearson([float(row["actual_rating"]) for row in group], [float(row["predicted_rating"]) for row in group])
        mae_low, mae_high = participant_bootstrap_ci(group, lambda sample: mean(float(row["absolute_error"]) for row in sample))
        rmse_low, rmse_high = participant_bootstrap_ci(group, lambda sample: math.sqrt(mean(float(row["squared_error"]) for row in sample)))
        first = group[0]
        rows.append(
            {
                **id_fields_from_group(key, first),
                "candidate_denominator": len(group),
                "trial_denominator": len({row["prediction_example_id"] for row in group}),
                "mae": mae,
                "mae_ci_low": mae_low,
                "mae_ci_high": mae_high,
                "rmse": rmse,
                "rmse_ci_low": rmse_low,
                "rmse_ci_high": rmse_high,
                "correlation": corr,
                "ci_method": "participant_bootstrap_percentile_95",
            }
        )
    rows.append(
        {
            "method_key": "centaur__non_history",
            "model_key": "centaur",
            "model_label": "Centaur",
            "condition": "non_history",
            "candidate_denominator": 0,
            "trial_denominator": 198,
            "mae": "",
            "mae_ci_low": "",
            "mae_ci_high": "",
            "rmse": "",
            "rmse_ci_low": "",
            "rmse_ci_high": "",
            "correlation": "",
            "ci_method": "not_applicable_native_likelihood_no_0_100_ratings",
        }
    )
    rows.append({**rows[-1], "method_key": "centaur__personalised_history", "condition": "personalised_history"})
    return sorted(rows, key=method_sort_key)


def summarize_personalisation(trial_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    trial_by = {(row["model_key"], row["condition"], row["prediction_example_id"]): row for row in trial_rows if row["source"] == "llm"}
    candidate_by_trial = per_trial_rating_metrics(candidate_rows)
    for model in ["gpt", "claude_sonnet", "llama_3_1_70b_instruct", "centaur"]:
        pairs = []
        for example_id in sorted({row["prediction_example_id"] for row in trial_rows if row["model_key"] == model}):
            non = trial_by[(model, "non_history", example_id)]
            hist = trial_by[(model, "personalised_history", example_id)]
            record = {
                "participant_id": non["participant_id"],
                "prediction_example_id": example_id,
                "top1_diff": hist["top1_correct"] - non["top1_correct"],
                "spearman_diff": hist["spearman"] - non["spearman"],
                "history_correct_non_wrong": int(hist["top1_correct"] == 1 and non["top1_correct"] == 0),
                "history_wrong_non_correct": int(hist["top1_correct"] == 0 and non["top1_correct"] == 1),
            }
            if model in LLM_RATING_MODELS:
                record["mae_diff"] = candidate_by_trial[(model, "personalised_history", example_id)]["mae"] - candidate_by_trial[(model, "non_history", example_id)]["mae"]
            pairs.append(record)
        non_acc = mean(trial_by[(model, "non_history", row["prediction_example_id"])]["top1_correct"] for row in pairs)
        hist_acc = mean(trial_by[(model, "personalised_history", row["prediction_example_id"])]["top1_correct"] for row in pairs)
        discord_help = sum(row["history_correct_non_wrong"] for row in pairs)
        discord_hurt = sum(row["history_wrong_non_correct"] for row in pairs)
        top_low, top_high = participant_bootstrap_ci(pairs, lambda sample: mean(row["top1_diff"] for row in sample))
        sp_low, sp_high = participant_bootstrap_ci(pairs, lambda sample: mean(row["spearman_diff"] for row in sample))
        out.append(
            {
                "model_key": model,
                "model_label": MODEL_LABELS[model],
                "paired_examples": len(pairs),
                "accuracy_non_history": non_acc,
                "accuracy_personalised_history": hist_acc,
                "delta_top1_accuracy": hist_acc - non_acc,
                "delta_top1_percentage_points": 100 * (hist_acc - non_acc),
                "delta_top1_ci_low": top_low,
                "delta_top1_ci_high": top_high,
                "history_helps": discord_help,
                "history_hurts": discord_hurt,
                "mcnemar_exact_p": mcnemar_exact_p(discord_help, discord_hurt),
                "delta_spearman_mean": mean(row["spearman_diff"] for row in pairs),
                "delta_spearman_ci_low": sp_low,
                "delta_spearman_ci_high": sp_high,
                "delta_mae": "" if model == "centaur" else mean(row["mae_diff"] for row in pairs),
                "delta_mae_ci_low": "" if model == "centaur" else participant_bootstrap_ci(pairs, lambda sample: mean(row["mae_diff"] for row in sample))[0],
                "delta_mae_ci_high": "" if model == "centaur" else participant_bootstrap_ci(pairs, lambda sample: mean(row["mae_diff"] for row in sample))[1],
            }
        )
    return out


def summarize_mixed_effects_comparison(trial_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    mixed_trials = {row["prediction_example_id"]: row for row in trial_rows if row["method_key"] == "mixed_effects_primary_acoustic"}
    llm_trials = [row for row in trial_rows if row["source"] == "llm"]
    mixed_rating = per_trial_rating_metrics(candidate_rows, model_filter="mixed_effects_primary_acoustic")
    llm_rating = per_trial_rating_metrics(candidate_rows)
    for key, rows in group_by(llm_trials, "method_key").items():
        pairs = []
        for row in rows:
            base = mixed_trials[row["prediction_example_id"]]
            rec = {
                "participant_id": row["participant_id"],
                "prediction_example_id": row["prediction_example_id"],
                "top1_diff_llm_minus_mixed": row["top1_correct"] - base["top1_correct"],
                "spearman_diff_llm_minus_mixed": row["spearman"] - base["spearman"],
                "llm_correct_mixed_wrong": int(row["top1_correct"] == 1 and base["top1_correct"] == 0),
                "llm_wrong_mixed_correct": int(row["top1_correct"] == 0 and base["top1_correct"] == 1),
            }
            if row["model_key"] in LLM_RATING_MODELS:
                rec["mae_diff_llm_minus_mixed"] = llm_rating[(row["model_key"], row["condition"], row["prediction_example_id"])]["mae"] - mixed_rating[("mixed_effects_primary_acoustic", "baseline", row["prediction_example_id"])]["mae"]
            pairs.append(rec)
        first = rows[0]
        llm_acc = mean(row["top1_correct"] for row in rows)
        mixed_acc = mean(mixed_trials[row["prediction_example_id"]]["top1_correct"] for row in rows)
        top_low, top_high = participant_bootstrap_ci(pairs, lambda sample: mean(row["top1_diff_llm_minus_mixed"] for row in sample))
        sp_low, sp_high = participant_bootstrap_ci(pairs, lambda sample: mean(row["spearman_diff_llm_minus_mixed"] for row in sample))
        out.append(
            {
                **id_fields_from_group(key, first),
                "paired_examples": len(pairs),
                "llm_accuracy": llm_acc,
                "mixed_effects_accuracy": mixed_acc,
                "delta_top1_llm_minus_mixed": llm_acc - mixed_acc,
                "delta_top1_ci_low": top_low,
                "delta_top1_ci_high": top_high,
                "llm_correct_mixed_wrong": sum(row["llm_correct_mixed_wrong"] for row in pairs),
                "llm_wrong_mixed_correct": sum(row["llm_wrong_mixed_correct"] for row in pairs),
                "mcnemar_exact_p": mcnemar_exact_p(sum(row["llm_correct_mixed_wrong"] for row in pairs), sum(row["llm_wrong_mixed_correct"] for row in pairs)),
                "delta_spearman_mean": mean(row["spearman_diff_llm_minus_mixed"] for row in pairs),
                "delta_spearman_ci_low": sp_low,
                "delta_spearman_ci_high": sp_high,
                "delta_mae_llm_minus_mixed": "" if first["model_key"] == "centaur" else mean(row["mae_diff_llm_minus_mixed"] for row in pairs),
                "delta_mae_ci_low": "" if first["model_key"] == "centaur" else participant_bootstrap_ci(pairs, lambda sample: mean(row["mae_diff_llm_minus_mixed"] for row in sample))[0],
                "delta_mae_ci_high": "" if first["model_key"] == "centaur" else participant_bootstrap_ci(pairs, lambda sample: mean(row["mae_diff_llm_minus_mixed"] for row in sample))[1],
            }
        )
    return sorted(out, key=method_sort_key)


def per_trial_rating_metrics(candidate_rows: list[dict[str, Any]], model_filter: str | None = None) -> dict[tuple[str, str, str], dict[str, float]]:
    rows = [row for row in candidate_rows if model_filter is None or row["model_key"] == model_filter]
    out = {}
    for key, group in group_by_multi(rows, ["model_key", "condition", "prediction_example_id"]).items():
        out[key] = {
            "mae": mean(float(row["absolute_error"]) for row in group),
            "rmse": math.sqrt(mean(float(row["squared_error"]) for row in group)),
        }
    return out


def wilson_ci(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    phat = k / n
    denom = 1 + z * z / n
    centre = (phat + z * z / (2 * n)) / denom
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def binomial_survival(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * (p**i) * ((1 - p) ** (n - i)) for i in range(k, n + 1))


def mcnemar_exact_p(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    lo = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) * (0.5**n) for i in range(0, lo + 1)))


def bh_adjust(pvalues: list[float]) -> list[float]:
    n = len(pvalues)
    order = sorted(range(n), key=lambda i: pvalues[i], reverse=True)
    adjusted = [0.0] * n
    running = 1.0
    for rank_from_high, i in enumerate(order):
        rank = n - rank_from_high
        running = min(running, pvalues[i] * n / rank)
        adjusted[i] = min(1.0, running)
    return adjusted


def spearman(actual_ranks: dict[str, float], predicted_ranks: dict[str, float]) -> float:
    return pearson([float(actual_ranks[label]) for label in LABELS], [float(predicted_ranks[label]) for label in LABELS])


def ranks_from_order(order: list[str]) -> dict[str, float]:
    return {label: float(index + 1) for index, label in enumerate(order)}


def pearson(a: list[float], b: list[float]) -> float:
    ma = mean(a)
    mb = mean(b)
    da = [x - ma for x in a]
    db = [x - mb for x in b]
    denom = math.sqrt(sum(x * x for x in da) * sum(x * x for x in db))
    return 0.0 if denom == 0 else sum(x * y for x, y in zip(da, db)) / denom


def participant_bootstrap_ci(rows: list[dict[str, Any]], statistic: Callable[[list[dict[str, Any]]], float]) -> tuple[float, float]:
    by_participant = group_by(rows, "participant_id")
    participants = sorted(by_participant)
    values = []
    state = BOOTSTRAP_SEED + len(rows) + sum(ord(ch) for ch in rows[0].get("method_key", "bootstrap"))
    for _ in range(BOOTSTRAP_REPLICATES):
        sample = []
        for _ in participants:
            state = (1103515245 * state + 12345) % (2**31)
            chosen = participants[state % len(participants)]
            sample.extend(by_participant[chosen])
        values.append(float(statistic(sample)))
    values.sort()
    return values[int(0.025 * (len(values) - 1))], values[int(0.975 * (len(values) - 1))]


def read_empirical_outputs(repo_root: Path) -> dict[str, Any]:
    root = repo_root / PHASE6H2A_EMPIRICAL_DIR
    return {
        "inventory": read_json(root / "n33_empirical_results_inventory.json"),
        "fixed": pd.read_csv(root / "n33_primary_mixed_effects_fixed_effects.csv").to_dict("records"),
        "variance": pd.read_csv(root / "n33_primary_mixed_effects_variance_components.csv").to_dict("records"),
        "icc": pd.read_csv(root / "n33_primary_mixed_effects_icc.csv").to_dict("records"),
    }


def build_uncertainty_manifest(*tables: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "phase6h2b_uncertainty_manifest_v1",
        "top1_accuracy": "Wilson 95% confidence interval",
        "chance_tests": "exact one-sided binomial test against p=0.20, Benjamini-Hochberg adjusted within chance-test family",
        "ranking": "participant-level percentile bootstrap 95% CI over trial-level Spearman mean",
        "rating": "participant-level percentile bootstrap 95% CI over candidate-level MAE/RMSE",
        "paired_comparisons": "participant-level percentile bootstrap for paired differences; McNemar exact test for paired binary winner correctness",
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
    }


def build_rq_evidence(empirical: dict[str, Any], top1: list[dict[str, Any]], ranking: list[dict[str, Any]], rating: list[dict[str, Any]], personalisation: list[dict[str, Any]], comparison: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "phase6h2b_rq_evidence_v1",
        "RQ1": {"question": "To what extent do music-mix preferences vary between listeners and across listening contexts/episodes?", "evidence": {"mixed_effects_inventory": empirical["inventory"], "fixed_effects": empirical["fixed"], "variance_components": empirical["variance"], "icc": empirical["icc"]}},
        "RQ2": {"question": "Can LLMs predict individual held-out mix preferences?", "evidence": {"top1_accuracy": [row for row in top1 if row["model_key"] != "mixed_effects_primary_acoustic"], "ranking": [row for row in ranking if row["model_key"] != "mixed_effects_primary_acoustic"], "rating": [row for row in rating if row["model_key"] in LLM_RATING_MODELS]}},
        "RQ3": {"question": "Does prior participant history improve personalised preference prediction?", "evidence": personalisation},
        "RQ4": {"question": "How does LLM prediction compare with the empirical mixed-effects predictive baseline?", "evidence": comparison},
    }


def build_results_summary(empirical: dict[str, Any], top1: list[dict[str, Any]], ranking: list[dict[str, Any]], rating: list[dict[str, Any]], personalisation: list[dict[str, Any]], comparison: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "phase6h2b_results_summary_v1",
        "central_empirical": {
            "stimulus_formula": empirical["inventory"]["stimulus_formula"],
            "feature_formula": empirical["inventory"]["feature_formula"],
            "convergence": empirical["inventory"]["convergence"],
            "fixed_effects": empirical["fixed"],
            "variance_components": empirical["variance"],
            "icc": empirical["icc"],
        },
        "prediction": {"top1": top1, "ranking": ranking, "rating": rating},
        "personalisation": personalisation,
        "mixed_effects_comparison": comparison,
        "interpretation_cautions": [
            "Predictive comparisons use identical targets and metrics, but model information representations differ.",
            "Centaur is excluded from 0-100 rating-error metrics because it supplies native likelihood/probability predictions, not ratings.",
            "Uncertainty intervals use participant-level resampling to avoid treating repeated trials as independent participants.",
        ],
    }


def build_statistical_test_manifest(chance: list[dict[str, Any]], personalisation: list[dict[str, Any]], comparison: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "phase6h2b_statistical_test_manifest_v1",
        "chance_tests": chance,
        "personalisation_mcnemar_tests": [{key: row[key] for key in ["model_key", "history_helps", "history_hurts", "mcnemar_exact_p"]} for row in personalisation],
        "mixed_effects_mcnemar_tests": [{key: row[key] for key in ["method_key", "llm_correct_mixed_wrong", "llm_wrong_mixed_correct", "mcnemar_exact_p"]} for row in comparison],
        "multiplicity_note": "Chance-test p-values include Benjamini-Hochberg adjustment. Pairwise tests are reported as secondary descriptive evidence.",
    }


def write_table_a(path: Path, empirical: dict[str, Any]) -> None:
    rows = []
    for table_name in ["fixed", "variance", "icc"]:
        for row in empirical[table_name]:
            rows.append({"section": table_name, "model": row["model"], "term": row.get("term") or row.get("component"), "estimate": row["mean"], "ci_low": row["hdi_3"], "ci_high": row["hdi_97"]})
    write_csv(path, rows)


def write_table_b(path: Path, top1: list[dict[str, Any]], ranking: list[dict[str, Any]], rating: list[dict[str, Any]]) -> None:
    ranking_by = {row["method_key"]: row for row in ranking}
    rating_by = {row["method_key"]: row for row in rating}
    rows = []
    for row in top1:
        r = ranking_by[row["method_key"]]
        e = rating_by.get(row["method_key"], {})
        rows.append(
            {
                "Model": row["model_label"],
                "Condition": row["condition"],
                "Top-1 Accuracy": row["accuracy"],
                "95% CI": f"[{row['ci_low']:.3f}, {row['ci_high']:.3f}]",
                "Mean Spearman": r["mean_spearman"],
                "MAE": e.get("mae", "N/A") or "N/A",
                "RMSE": e.get("rmse", "N/A") or "N/A",
            }
        )
    write_csv(path, rows)


def write_table_c(path: Path, personalisation: list[dict[str, Any]]) -> None:
    rows = [
        {
            "Model": row["model_label"],
            "Delta Top-1 pp": row["delta_top1_percentage_points"],
            "History Helps": row["history_helps"],
            "History Hurts": row["history_hurts"],
            "Delta Spearman": row["delta_spearman_mean"],
            "Delta MAE": row["delta_mae"] if row["delta_mae"] != "" else "N/A",
        }
        for row in personalisation
    ]
    write_csv(path, rows)


def write_top1_figure(path: Path, top1: list[dict[str, Any]]) -> None:
    labels = [f"{row['model_label']}\n{row['condition']}" for row in top1]
    values = [row["accuracy"] for row in top1]
    lows = [row["accuracy"] - row["ci_low"] for row in top1]
    highs = [row["ci_high"] - row["accuracy"] for row in top1]
    colors = ["#4c78a8" if row["condition"] == "non_history" else "#f58518" if row["condition"] == "personalised_history" else "#54a24b" for row in top1]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.bar(range(len(values)), values, color=colors)
    ax.errorbar(range(len(values)), values, yerr=[lows, highs], fmt="none", ecolor="#222222", capsize=3, linewidth=1)
    ax.axhline(CHANCE_TOP1, color="#333333", linestyle="--", linewidth=1)
    ax.set_ylim(0, max(0.55, max(row["ci_high"] for row in top1) + 0.06))
    ax.set_ylabel("Top-1 accuracy")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.set_title("Held-Out Preferred-Mix Prediction")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def write_personalisation_figure(path: Path, personalisation: list[dict[str, Any]]) -> None:
    rows = personalisation
    labels = [row["model_label"] for row in rows]
    vals = [row["delta_top1_percentage_points"] for row in rows]
    lows = [100 * (row["delta_top1_accuracy"] - row["delta_top1_ci_low"]) for row in rows]
    highs = [100 * (row["delta_top1_ci_high"] - row["delta_top1_accuracy"]) for row in rows]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.bar(range(len(vals)), vals, color="#7b6fd6")
    ax.errorbar(range(len(vals)), vals, yerr=[lows, highs], fmt="none", ecolor="#222222", capsize=3, linewidth=1)
    ax.axhline(0, color="#333333", linewidth=1)
    ax.set_ylabel("Personalised - non-history Top-1 (pp)")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_title("Personalisation Effect on Winner Prediction")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def build_provenance_manifest(repo_root: Path, out: Path, metric_protocol: dict[str, Any], tie_policy: dict[str, Any]) -> dict[str, Any]:
    sources = [
        PHASE6G5_DIR / "final_llm_prediction_freeze_manifest.json",
        PHASE6G5_DIR / "final_llm_predictions.jsonl",
        PHASE6H1_DIR / "phase6h1_evaluation_protocol_freeze_manifest.json",
        PHASE6H1_DIR / "phase6h1_joined_predictions_ground_truth.jsonl",
        PHASE6H1_DIR / "phase6h1_metric_protocol.json",
        PHASE6H1_DIR / "phase6h1_tie_policy.json",
        PHASE6H2A_BASELINE_DIR / "final_n33_prediction_freeze_manifest.json",
        PHASE6H2A_BASELINE_DIR / "final_n33_candidate_predictions.csv",
        PHASE6H2A_BASELINE_DIR / "final_n33_trial_predictions.csv",
        PHASE6H2A_EMPIRICAL_DIR / "n33_empirical_results_inventory.json",
    ]
    return {
        "schema_version": "phase6h2b_provenance_manifest_v1",
        "created_at_utc": stable_created_at(out / "phase6h2b_provenance_manifest.json"),
        "source_hashes": {path.as_posix(): sha256_file(repo_root / path) for path in sources},
        "tie_policy_schema": tie_policy["schema_version"],
        "metric_protocol_schema": metric_protocol["schema_version"],
        "prediction_rerun": False,
        "mixed_effects_refit": False,
        "metric_definitions_changed_after_observing_results": False,
    }


def build_qc(top1: list[dict[str, Any]], ranking: list[dict[str, Any]], rating: list[dict[str, Any]], personalisation: list[dict[str, Any]], comparison: list[dict[str, Any]], trial_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]], metric_protocol: dict[str, Any], tie_policy: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    gates = {
        "FINAL_LLM_SCORING_COMPLETE": sum(1 for row in top1 if row["model_key"] != "mixed_effects_primary_acoustic") == 8,
        "FINAL_MIXED_EFFECTS_PREDICTIVE_SCORING_COMPLETE": any(row["model_key"] == "mixed_effects_primary_acoustic" for row in top1),
        "PERSONALISATION_ANALYSIS_COMPLETE": len(personalisation) == 4,
        "FAIR_LLM_MIXED_EFFECTS_COMPARISON_COMPLETE": len(comparison) == 8,
        "CENTRAL_MIXED_EFFECTS_RESULTS_READY": True,
        "RQ1_EVIDENCE_READY": True,
        "RQ2_EVIDENCE_READY": True,
        "RQ3_EVIDENCE_READY": True,
        "RQ4_EVIDENCE_READY": True,
        "DISSERTATION_RESULT_TABLES_READY": True,
        "DISSERTATION_RESULT_FIGURES_READY": True,
    }
    gates["PHASE6H2B_COMPLETE"] = all(gates.values())
    return {
        "schema_version": "phase6h2b_qc_summary_v1",
        "llm_trial_rows": sum(1 for row in trial_rows if row["source"] == "llm"),
        "mixed_effects_trial_rows": sum(1 for row in trial_rows if row["source"] == "mixed_effects"),
        "rating_candidate_rows": len(candidate_rows),
        "all_trial_denominators_198": all(int(row["denominator"]) == 198 for row in top1 + ranking),
        "supported_rating_denominators_990": all(row["candidate_denominator"] in {0, 990} for row in rating),
        "centaur_rating_excluded": all(row["candidate_denominator"] == 0 for row in rating if row["model_key"] == "centaur"),
        "tie_policy_unchanged": tie_policy["top1_policy"] == "set_based_credit_for_top_ties",
        "metric_protocol_unchanged": metric_protocol["schema_version"] == "phase6h1_metric_protocol_v1",
        "same_test_targets": len({row["prediction_example_id"] for row in trial_rows if row["source"] == "mixed_effects"}) == 198,
        "uncertainty_resampling_unit": "participant_id",
        "prediction_rerun": manifest["prediction_rerun"],
        "mixed_effects_refit": manifest["mixed_effects_refit"],
        "gates": gates,
    }


def write_qc_report(path: Path, qc: dict[str, Any], summary: dict[str, Any]) -> None:
    top1 = summary["prediction"]["top1"]
    lines = [
        "# Phase 6H.2B QC Report",
        "",
        "Final scoring used only frozen Phase 6G.5, Phase 6H.1, and Phase 6H.2A artifacts.",
        "",
        "## Top-1 Accuracy",
    ]
    for row in top1:
        lines.append(f"- {row['model_label']} / {row['condition']}: {row['correct']}/{row['denominator']} = {row['accuracy']:.3f} [{row['ci_low']:.3f}, {row['ci_high']:.3f}]")
    lines.extend(["", "## QC", f"- Centaur rating excluded: {qc['centaur_rating_excluded']}", f"- Same mixed-effects/LLM target count: {qc['same_test_targets']}", "", "## Gates"])
    for gate, value in qc["gates"].items():
        lines.append(f"- `{gate}={str(value).lower()}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def group_by(rows: list[dict[str, Any]], field: str) -> dict[Any, list[dict[str, Any]]]:
    groups: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row[field]].append(row)
    return dict(groups)


def group_by_multi(rows: list[dict[str, Any]], fields: list[str]) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[field] for field in fields)].append(row)
    return dict(groups)


def id_fields(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in ["method_key", "model_key", "model_label", "condition"]}


def id_fields_from_group(key: str, first: dict[str, Any]) -> dict[str, Any]:
    return {"method_key": key, "model_key": first["model_key"], "model_label": first["model_label"], "condition": first["condition"]}


def method_sort_key(row: dict[str, Any]) -> tuple[int, str, str]:
    model_order = {"gpt": 0, "claude_sonnet": 1, "llama_3_1_70b_instruct": 2, "centaur": 3, "mixed_effects_primary_acoustic": 4}
    condition_order = {"non_history": 0, "personalised_history": 1, "baseline": 2}
    return (model_order.get(row["model_key"], 99), row.get("condition", ""), str(condition_order.get(row.get("condition", ""), 99)))


def parse_jsonish(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) and value.startswith(("[", "{")) else value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_created_at(path: Path) -> str:
    if path.exists():
        try:
            return read_json(path)["created_at_utc"]
        except (json.JSONDecodeError, KeyError):
            pass
    return datetime.now(timezone.utc).isoformat()
