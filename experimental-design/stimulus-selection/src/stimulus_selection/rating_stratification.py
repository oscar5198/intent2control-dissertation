from __future__ import annotations

"""Phase 2B rating-stratified recommendation sets for supervisor review."""

import csv
import itertools
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from sklearn.decomposition import PCA

from stimulus_selection.config import SelectionConfig
from stimulus_selection.output_layout import (
    first_existing,
    rating_stratification_audio,
    rating_stratification_diagnostics,
    rating_stratification_reports,
    rating_stratification_root,
    rating_stratification_tables,
)
from stimulus_selection.paths import ensure_output_root


CONDITIONS = ("Similar Ratings", "Wide Ratings")


@dataclass(frozen=True)
class RatingStratificationResult:
    output_root: Path
    supervisor_shortlist_path: Path
    report_path: Path
    recommended_rows: int
    audio_files: int


def _fmt(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return str(value).lower()
    try:
        number = float(value)
    except Exception:
        return str(value)
    if not math.isfinite(number):
        return ""
    return f"{number:.12g}"


def _write_csv(path: Path, rows: Iterable[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: _fmt(row.get(col, "")) for col in columns})


def _load_config(config_path: str | Path) -> dict[str, object]:
    raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    cfg = raw.get("rating_stratification")
    if not isinstance(cfg, dict):
        raise ValueError("experimental-design/stimulus-selection/config/stimulus_selection.yaml is missing rating_stratification.")
    return cfg


def triplet_pair_distances(triplet: Sequence[str], distance_lookup: dict[frozenset[str], float]) -> list[float]:
    return [float(distance_lookup[frozenset(pair)]) for pair in itertools.combinations(triplet, 2)]


def qc_status(row: pd.Series) -> str:
    if str(row.get("stereo_imbalance_qc_flag", "")).lower() == "true":
        return "review"
    if str(row.get("low_count_warning", "")).lower() == "true" or str(row.get("aggregation_status", "")) != "ok":
        return "caution"
    return "clear"


def rating_bin(value: float, tertiles: tuple[float, float]) -> str:
    if value <= tertiles[0]:
        return "low"
    if value >= tertiles[1]:
        return "high"
    return "medium"


def score_triplets(
    candidates: pd.DataFrame,
    distance_lookup: dict[frozenset[str], float],
    condition: str,
    acoustic_weight: float,
    rating_weight: float,
    qc_review_penalty: float,
    qc_caution_penalty: float,
) -> list[dict[str, object]]:
    combos = list(itertools.combinations(candidates["mix_id"].tolist(), 3))
    prelim = []
    for combo in combos:
        rows = candidates.set_index("mix_id").loc[list(combo)]
        distances = triplet_pair_distances(combo, distance_lookup)
        means = rows["mean_preference"].astype(float).to_numpy()
        spread = float(np.max(means) - np.min(means))
        prelim.append({"combo": combo, "min_dist": min(distances), "mean_dist": float(np.mean(distances)), "spread": spread})
    min_vals = np.asarray([p["min_dist"] for p in prelim], dtype=float)
    mean_vals = np.asarray([p["mean_dist"] for p in prelim], dtype=float)
    spreads = np.asarray([p["spread"] for p in prelim], dtype=float)
    def norm(values: np.ndarray, value: float) -> float:
        lo, hi = float(np.min(values)), float(np.max(values))
        return 0.0 if hi <= lo else (value - lo) / (hi - lo)
    tertiles = tuple(np.quantile(candidates["mean_preference"].astype(float).to_numpy(), [1 / 3, 2 / 3]))
    scored = []
    for item in prelim:
        combo = item["combo"]
        rows = candidates.set_index("mix_id").loc[list(combo)]
        means = rows["mean_preference"].astype(float).to_numpy()
        acoustic_score = 0.7 * norm(min_vals, item["min_dist"]) + 0.3 * norm(mean_vals, item["mean_dist"])
        spread_norm = norm(spreads, item["spread"])
        rating_score = 1.0 - spread_norm if condition == "Similar Ratings" else spread_norm
        bins = [rating_bin(float(v), tertiles) for v in means]
        coverage_bonus = 0.03 if condition == "Wide Ratings" and len(set(bins)) == 3 else 0.0
        statuses = [qc_status(row) for _, row in rows.iterrows()]
        qc_penalty = statuses.count("review") * qc_review_penalty + statuses.count("caution") * qc_caution_penalty
        objective = acoustic_weight * acoustic_score + rating_weight * rating_score + coverage_bonus - qc_penalty
        names = rows["original_mix_name"].tolist()
        scored.append({
            "song": rows["song"].iloc[0],
            "condition": condition,
            "triplet_id": f"{rows['song'].iloc[0].replace(' ', '').replace('-', '')}_{condition.replace(' ', '')}_{len(scored) + 1:05d}",
            "mix_ids": "|".join(combo),
            "original_mix_names": "|".join(names),
            "mean_ratings": "|".join(f"{v:.6f}" for v in means),
            "rating_bins": "|".join(bins),
            "rating_spread": item["spread"],
            "minimum_acoustic_distance": item["min_dist"],
            "mean_acoustic_distance": item["mean_dist"],
            "acoustic_score": acoustic_score,
            "rating_score": rating_score,
            "coverage_bonus": coverage_bonus,
            "qc_penalty": qc_penalty,
            "objective_score": objective,
            "qc_statuses": "|".join(statuses),
            "qc_flags": "|".join(rows["stereo_imbalance_qc_flag"].astype(str).tolist()),
            "rating_counts": "|".join(rows["rating_count"].astype(str).tolist()),
            "overlap_count": "",
            "overlap_original_mix_names": "",
            "selection_notes": "Acoustic diversity weighted 0.8; rating stratification weighted 0.2; ratings did not modify acoustic distances.",
        })
    scored.sort(key=lambda r: (float(r["objective_score"]), float(r["minimum_acoustic_distance"]), float(r["mean_acoustic_distance"]), r["original_mix_names"]), reverse=True)
    for rank, row in enumerate(scored, 1):
        row["rank"] = rank
    return scored


def _distance_lookup(pairwise: pd.DataFrame) -> dict[frozenset[str], float]:
    lookup: dict[frozenset[str], float] = {}
    for _, row in pairwise.iterrows():
        lookup[frozenset([row["mix_i_id"], row["mix_j_id"]])] = float(row["combined_euclidean_distance"])
    return lookup


def _copy_review_audio(preview_root: Path, audio_root: Path, shortlist_rows: list[dict[str, object]]) -> list[Path]:
    copied: list[Path] = []
    for row in shortlist_rows:
        song = str(row["song"])
        condition = str(row["condition"])
        for name in str(row["original_mix_names"]).split("|"):
            source = preview_root / song / f"{name}_28sec.wav"
            if not source.exists():
                raise FileNotFoundError(source)
            dest = audio_root / song / condition / source.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            copied.append(dest)
    return copied


def _plot_bar(path: Path, labels: Sequence[str], values: Sequence[float], title: str, ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(max(8, len(labels) * 0.3), 4))
    plt.bar(range(len(labels)), values)
    plt.xticks(range(len(labels)), labels, rotation=90, fontsize=6)
    plt.title(title)
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def _save_diagnostics(diag: Path, song: str, candidates: pd.DataFrame, processed: pd.DataFrame, similar: dict[str, object], wide: dict[str, object], top_rows: list[dict[str, object]]) -> None:
    out = diag / "".join(ch for ch in song if ch.isalnum())
    out.mkdir(parents=True, exist_ok=True)
    labels = candidates["original_mix_name"].tolist()
    means = candidates["mean_preference"].astype(float).tolist()
    _plot_bar(out / "rating_distribution.png", labels, means, "Mean prior preference by candidate", "mean preference")
    coord_cols = [c for c in processed.columns if c.startswith("combined_")]
    merged = candidates.merge(processed[["mix_id"] + coord_cols], on="mix_id", how="left")
    coords = merged[coord_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy()
    xy = PCA(n_components=2, random_state=42).fit_transform(coords) if coords.shape[1] > 1 else np.column_stack([coords[:, 0], np.zeros(coords.shape[0])])
    sim_ids = set(str(similar["mix_ids"]).split("|"))
    wide_ids = set(str(wide["mix_ids"]).split("|"))
    colors = []
    for mix_id in merged["mix_id"]:
        if mix_id in sim_ids and mix_id in wide_ids:
            colors.append("#9467bd")
        elif mix_id in sim_ids:
            colors.append("#1f77b4")
        elif mix_id in wide_ids:
            colors.append("#d62728")
        else:
            colors.append("#bbbbbb")
    plt.figure(figsize=(7, 5))
    plt.scatter(xy[:, 0], xy[:, 1], c=colors)
    for i, label in enumerate(labels):
        if merged["mix_id"].iloc[i] in sim_ids or merged["mix_id"].iloc[i] in wide_ids:
            plt.text(xy[i, 0], xy[i, 1], label, fontsize=7)
    plt.title("Corrected acoustic space: recommended triplets")
    plt.tight_layout()
    plt.savefig(out / "acoustic_space_recommended_triplets.png", dpi=160)
    plt.close()
    plt.figure(figsize=(6, 4))
    plt.scatter(pd.to_numeric(candidates["distance_from_medoid"], errors="coerce"), candidates["mean_preference"].astype(float))
    plt.xlabel("distance from acoustic medoid")
    plt.ylabel("mean preference")
    plt.title("Rating versus acoustic position")
    plt.tight_layout()
    plt.savefig(out / "rating_vs_acoustic_scatter.png", dpi=160)
    plt.close()
    _plot_bar(out / "rating_spread_comparison.png", ["Similar Ratings", "Wide Ratings"], [float(similar["rating_spread"]), float(wide["rating_spread"])], "Recommended rating spread", "spread")
    _plot_bar(out / "triplet_objective_ranking.png", [f"{r['condition']} {r['rank']}" for r in top_rows], [float(r["objective_score"]) for r in top_rows], "Triplet objective ranking", "objective")
    overlap = len(sim_ids & wide_ids)
    _plot_bar(out / "triplet_overlap_visualisation.png", ["overlap", "unique"], [overlap, len(sim_ids | wide_ids)], "Recommended triplet overlap", "count")
    qc_labels = ["clear", "caution", "review"]
    statuses = "|".join([str(similar["qc_statuses"]), str(wide["qc_statuses"])]).split("|")
    _plot_bar(out / "qc_summary.png", qc_labels, [statuses.count(s) for s in qc_labels], "QC status summary", "mix count")


def run_rating_stratification(config: SelectionConfig, config_path: str | Path) -> RatingStratificationResult:
    cfg = _load_config(config_path)
    acoustic_weight = float(cfg.get("acoustic_weight", 0.8))
    rating_weight = float(cfg.get("rating_weight", 0.2))
    top_n = int(cfg.get("top_n_per_condition", 10))
    output_root = ensure_output_root(config)
    tables = rating_stratification_tables(output_root)
    reports = rating_stratification_reports(output_root)
    diag = rating_stratification_diagnostics(output_root)
    audio_root = rating_stratification_audio(output_root)
    root = rating_stratification_root(output_root)
    for folder in (tables, reports, diag, audio_root):
        folder.mkdir(parents=True, exist_ok=True)

    pool = pd.read_csv(first_existing(output_root, "04_mix_selection_v2/tables/acoustic_candidate_pool.csv"), dtype=str, keep_default_na=False)
    processed = pd.read_csv(first_existing(output_root, "04_mix_selection_v2/tables/processed_features_v2.csv"), dtype=str, keep_default_na=False)
    pairwise = pd.read_csv(first_existing(output_root, "04_mix_selection_v2/tables/pairwise_distances_v2.csv"), dtype=str, keep_default_na=False)
    ratings = pd.read_csv(first_existing(output_root, "05_ratings_integration/tables/mix_preference_rating_summary_within_song.csv"), dtype=str, keep_default_na=False)
    preview_root = first_existing(output_root, "04_mix_selection_v2/candidate_pool_previews")
    lookup = _distance_lookup(pairwise)
    pool_hash_before = pd.util.hash_pandas_object(pool, index=True).sum()
    rating_hash_before = pd.util.hash_pandas_object(ratings, index=True).sum()

    merged = pool.merge(ratings, on=["artist", "song", "mix_id", "original_mix_name", "original_dataset_filename"], how="left", suffixes=("_pool", ""))
    eligible = merged[(merged["mean_preference"].astype(str) != "") & (merged["aggregation_status"].astype(str) != "unrated")].copy()
    eligible["mean_preference"] = eligible["mean_preference"].astype(float)
    all_triplets: list[dict[str, object]] = []
    similar_rows: list[dict[str, object]] = []
    wide_rows: list[dict[str, object]] = []
    recommended_rows: list[dict[str, object]] = []
    overlap_rows: list[dict[str, object]] = []
    rating_stat_rows: list[dict[str, object]] = []
    acoustic_stat_rows: list[dict[str, object]] = []

    for song, song_candidates in eligible.groupby("song", sort=True):
        if len(song_candidates) < 3:
            raise ValueError(f"Not enough rated candidate-pool mixes for {song}.")
        sim_scored = score_triplets(song_candidates, lookup, "Similar Ratings", acoustic_weight, rating_weight, float(cfg.get("qc_review_penalty", 0.05)), float(cfg.get("qc_caution_penalty", 0.025)))
        wide_scored = score_triplets(song_candidates, lookup, "Wide Ratings", acoustic_weight, rating_weight, float(cfg.get("qc_review_penalty", 0.05)), float(cfg.get("qc_caution_penalty", 0.025)))
        similar_top = sim_scored[:top_n]
        wide_top = wide_scored[:top_n]
        similar_rows.extend(similar_top)
        wide_rows.extend(wide_top)
        all_triplets.extend(similar_top + wide_top)
        best_sim = similar_top[0]
        sim_ids = set(str(best_sim["mix_ids"]).split("|"))
        wide_choice = sorted(wide_scored, key=lambda r: (len(sim_ids & set(str(r["mix_ids"]).split("|"))), -float(r["objective_score"]), -float(r["minimum_acoustic_distance"]), r["original_mix_names"]))[0]
        best_wide = dict(wide_choice)
        best_wide["rank"] = wide_choice["rank"]
        best_wide["selection_notes"] = str(best_wide["selection_notes"]) + " Wide recommendation chosen with overlap minimisation against the best similar-rating triplet."
        recommended_rows.extend([best_sim, best_wide])
        wide_ids = set(str(best_wide["mix_ids"]).split("|"))
        sim_names = set(str(best_sim["original_mix_names"]).split("|"))
        wide_names = set(str(best_wide["original_mix_names"]).split("|"))
        best_sim["overlap_count"] = len(sim_ids & wide_ids)
        best_sim["overlap_original_mix_names"] = "|".join(sorted(sim_names & wide_names))
        best_wide["overlap_count"] = len(sim_ids & wide_ids)
        best_wide["overlap_original_mix_names"] = "|".join(sorted(sim_names & wide_names))
        for row in similar_top:
            row_ids = set(str(row["mix_ids"]).split("|"))
            row_names = set(str(row["original_mix_names"]).split("|"))
            row["overlap_count"] = len(row_ids & wide_ids)
            row["overlap_original_mix_names"] = "|".join(sorted(row_names & wide_names))
        for row in wide_top:
            row_ids = set(str(row["mix_ids"]).split("|"))
            row_names = set(str(row["original_mix_names"]).split("|"))
            row["overlap_count"] = len(row_ids & sim_ids)
            row["overlap_original_mix_names"] = "|".join(sorted(row_names & sim_names))
        overlap_rows.append({
            "song": song,
            "similar_triplet_id": best_sim["triplet_id"],
            "wide_triplet_id": best_wide["triplet_id"],
            "overlap_count": len(sim_ids & wide_ids),
            "overlap_original_mix_names": "|".join(sorted(set(str(best_sim["original_mix_names"]).split("|")) & set(str(best_wide["original_mix_names"]).split("|")))),
            "unique_mix_count": len(sim_ids | wide_ids),
            "overlap_notes": "Six unique mixes achieved." if not (sim_ids & wide_ids) else "Overlap retained because it scored best after overlap minimisation.",
        })
        for row in similar_top + wide_top:
            vals = [float(v) for v in str(row["mean_ratings"]).split("|")]
            rating_stat_rows.append({"song": song, "triplet_id": row["triplet_id"], "condition": row["condition"], "mean_rating": float(np.mean(vals)), "minimum_rating": min(vals), "maximum_rating": max(vals), "rating_spread": row["rating_spread"], "rating_bins": row["rating_bins"], "rating_counts": row["rating_counts"]})
            acoustic_stat_rows.append({"song": song, "triplet_id": row["triplet_id"], "condition": row["condition"], "minimum_acoustic_distance": row["minimum_acoustic_distance"], "mean_acoustic_distance": row["mean_acoustic_distance"], "acoustic_score": row["acoustic_score"]})
        _save_diagnostics(diag, song, song_candidates, processed[processed["song"] == song], best_sim, best_wide, similar_top + wide_top)

    columns = ["song", "condition", "triplet_id", "rank", "objective_score", "original_mix_names", "mix_ids", "mean_ratings", "rating_bins", "rating_spread", "minimum_acoustic_distance", "mean_acoustic_distance", "acoustic_score", "rating_score", "coverage_bonus", "qc_penalty", "qc_statuses", "qc_flags", "rating_counts", "overlap_count", "overlap_original_mix_names", "selection_notes"]
    _write_csv(tables / "similar_rating_triplets.csv", similar_rows, columns)
    _write_csv(tables / "wide_rating_triplets.csv", wide_rows, columns)
    _write_csv(tables / "triplet_scores.csv", all_triplets, columns)
    _write_csv(tables / "recommended_triplets_for_review.csv", recommended_rows, columns)
    _write_csv(tables / "supervisor_shortlist.csv", recommended_rows, columns)
    _write_csv(tables / "triplet_overlap_analysis.csv", overlap_rows, ["song", "similar_triplet_id", "wide_triplet_id", "overlap_count", "overlap_original_mix_names", "unique_mix_count", "overlap_notes"])
    _write_csv(tables / "triplet_rating_statistics.csv", rating_stat_rows, ["song", "triplet_id", "condition", "mean_rating", "minimum_rating", "maximum_rating", "rating_spread", "rating_bins", "rating_counts"])
    _write_csv(tables / "triplet_acoustic_statistics.csv", acoustic_stat_rows, ["song", "triplet_id", "condition", "minimum_acoustic_distance", "mean_acoustic_distance", "acoustic_score"])
    copied = _copy_review_audio(preview_root, audio_root, recommended_rows)
    root.joinpath("README.md").write_text(
        "\n".join([
            "# Phase 2B Rating Stratification",
            "",
            "This folder contains recommendation triplets for supervisor review only.",
            "",
            "- The corrected acoustic candidate pools are unchanged.",
            "- Ratings stratify already-diverse candidate mixes.",
            "- No final study stimuli have been selected or generated.",
            "- Supervisor approval is required before final stimuli are regenerated.",
            "",
        ]),
        encoding="utf-8",
    )
    _write_report(reports, recommended_rows, overlap_rows, pool, ratings)
    if pool_hash_before != pd.util.hash_pandas_object(pool, index=True).sum() or rating_hash_before != pd.util.hash_pandas_object(ratings, index=True).sum():
        raise AssertionError("Input data frames were modified in memory.")
    return RatingStratificationResult(output_root, tables / "supervisor_shortlist.csv", reports / "rating_stratification_report.md", len(recommended_rows), len(copied))


def _write_report(reports: Path, recommended_rows: list[dict[str, object]], overlap_rows: list[dict[str, object]], pool: pd.DataFrame, ratings: pd.DataFrame) -> None:
    lines = [
        "# Rating Stratification Report",
        "",
        "Phase 2B combines fixed corrected acoustic candidate pools with Phase 2A prior preference ratings to recommend supervisor-review triplets. Acoustic distances are read from `pairwise_distances_v2.csv` and are not recomputed or modified.",
        "",
        "Objective weighting: 0.8 acoustic diversity and 0.2 rating stratification. Similar-rating triplets minimise rating spread within acoustically diverse combinations; wide-rating triplets maximise rating spread while retaining acoustic diversity. QC review/caution statuses are penalised lightly and reported, not automatically excluded.",
        "",
        "Unrated candidate-pool mixes are documented in Phase 2A but excluded from rating-based recommendation sets because no mean preference is available.",
        "",
        "## Recommendations",
        "",
        "| Song | Condition | Mixes | Rating spread | Minimum acoustic distance | QC statuses |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in recommended_rows:
        lines.append(f"| {row['song']} | {row['condition']} | {row['original_mix_names']} | {float(row['rating_spread']):.3f} | {float(row['minimum_acoustic_distance']):.3f} | {row['qc_statuses']} |")
    lines.extend(["", "## Overlap", ""])
    for row in overlap_rows:
        lines.append(f"- {row['song']}: overlap {row['overlap_count']}; unique mix count {row['unique_mix_count']}. {row['overlap_notes']}")
    lines.extend([
        "",
        "## Status",
        "",
        "No final selection has been made. No participant stimuli, manual approvals, frontend files, or final-stimulus outputs were generated or modified.",
        "",
    ])
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "rating_stratification_report.md").write_text("\n".join(lines), encoding="utf-8")
