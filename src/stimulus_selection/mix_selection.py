from __future__ import annotations

"""Stage 4 mix selection from validated Diff-MST features.

All preprocessing and distance calculations are performed independently within
each song. Raw feature magnitudes are never compared across songs.
"""

import csv
import itertools
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import soundfile as sf
from sklearn.decomposition import PCA

from stimulus_selection.audio_decode import decode_audio, ensure_sample_rate
from stimulus_selection.config import SelectionConfig
from stimulus_selection.feature_extraction import BARK_COLUMNS, EXPECTED_SAMPLE_RATE, EXPECTED_SECONDS, SCALAR_COLUMNS, extract_exact_excerpt
from stimulus_selection.naming import get_original_dataset_filename, get_original_mix_name, safe_original_mix_filename
from stimulus_selection.output_layout import first_existing, stage3_tables, stage4_diagnostics, stage4_previews, stage4_reports, stage4_tables
from stimulus_selection.paths import ensure_output_root


PRIMARY_SCALARS = ["rms_mean", "crest_factor_mean", "stereo_width", "stereo_imbalance"]
LEFT_RIGHT_DIAGNOSTIC_SCALARS = [c for c in SCALAR_COLUMNS if c not in PRIMARY_SCALARS]
SEED = 42
EPS = 1e-12
NEAR_ZERO_IQR = 1e-10


@dataclass(frozen=True)
class SongSelection:
    artist: str
    song: str
    retained_count: int
    medoid_mix_id: str
    bark_components: int
    bark_variance: float
    recommended_mix_ids: tuple[str, str, str]
    min_distance: float
    mean_distance: float
    unique_institutions: int
    stability_score: float
    manual_listening_required: bool


@dataclass(frozen=True)
class MixSelectionResult:
    output_root: Path
    processed_features_path: Path
    recommended_triplets_path: Path
    summary_path: Path
    report_path: Path
    preview_manifest_path: Path
    preview_root: Path
    song_selections: list[SongSelection]
    preview_files: list[Path]


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


def _song_label(artist: str, song: str) -> str:
    return f"{artist} - {song}"


def _song_slug(song: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", song)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Iterable[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: _fmt(row.get(col, "")) for col in columns})


def robust_parameters(matrix: np.ndarray, columns: list[str], near_zero_iqr: float = NEAR_ZERO_IQR) -> tuple[np.ndarray, list[dict[str, object]]]:
    median = np.median(matrix, axis=0)
    q25, q75 = np.percentile(matrix, [25, 75], axis=0)
    iqr = q75 - q25
    keep = iqr > near_zero_iqr
    scaled = np.zeros_like(matrix, dtype=np.float64)
    if np.any(keep):
        scaled[:, keep] = (matrix[:, keep] - median[keep]) / iqr[keep]
    rows = []
    for idx, column in enumerate(columns):
        rows.append({
            "feature": column,
            "median": median[idx],
            "q25": q25[idx],
            "q75": q75[idx],
            "iqr": iqr[idx],
            "near_zero_iqr": bool(iqr[idx] <= near_zero_iqr),
            "retained": bool(keep[idx]),
            "scale_formula": "(value - median) / IQR; zero/near-zero IQR dimensions are retained as all-zero only when division is mathematically unsafe",
        })
    return scaled, rows


def select_bark_pca(scaled_bark: np.ndarray, variance_threshold: float = 0.95) -> tuple[PCA, np.ndarray, int]:
    nonconstant = np.var(scaled_bark, axis=0) > EPS
    if not np.any(nonconstant):
        raise ValueError("No nonconstant Bark dimensions available for PCA.")
    matrix = scaled_bark[:, nonconstant]
    max_components = min(matrix.shape[0] - 1, matrix.shape[1])
    pca = PCA(n_components=max_components, svd_solver="full", random_state=SEED)
    scores_all = pca.fit_transform(matrix)
    cumulative = np.cumsum(pca.explained_variance_ratio_)
    retained = int(np.searchsorted(cumulative, variance_threshold, side="left") + 1)
    retained = max(1, min(retained, max_components))
    return pca, scores_all[:, :retained], retained


def equal_block_weight(scaled_block: np.ndarray) -> np.ndarray:
    if scaled_block.size == 0:
        return scaled_block
    expected_squared = float(np.mean(np.sum(np.square(scaled_block), axis=1)))
    if expected_squared <= EPS:
        return np.zeros_like(scaled_block, dtype=np.float64)
    return scaled_block / math.sqrt(expected_squared)


def pairwise_matrix(coords: np.ndarray, metric: str = "euclidean") -> np.ndarray:
    diff = coords[:, None, :] - coords[None, :, :]
    if metric == "manhattan":
        return np.sum(np.abs(diff), axis=2)
    return np.sqrt(np.sum(np.square(diff), axis=2))


def medoid_index(distance_matrix: np.ndarray) -> int:
    totals = distance_matrix.sum(axis=1)
    return int(np.lexsort((np.arange(totals.size), totals))[0])


def triplet_stats(indices: tuple[int, int, int], distance_matrix: np.ndarray) -> tuple[float, float, float, tuple[float, float, float]]:
    pairs = (
        float(distance_matrix[indices[0], indices[1]]),
        float(distance_matrix[indices[0], indices[2]]),
        float(distance_matrix[indices[1], indices[2]]),
    )
    return min(pairs), float(np.mean(pairs)), max(pairs), pairs


def best_triplet(distance_matrix: np.ndarray, required_index: int | None = None, eligible: Iterable[tuple[int, int, int]] | None = None) -> tuple[int, int, int]:
    combos = eligible if eligible is not None else itertools.combinations(range(distance_matrix.shape[0]), 3)
    best: tuple[float, float, tuple[int, int, int]] | None = None
    for combo in combos:
        combo = tuple(sorted(combo))
        if required_index is not None and required_index not in combo:
            continue
        mn, mean, _, _ = triplet_stats(combo, distance_matrix)
        score = (mn, mean, tuple(-i for i in combo))
        if best is None or score > (best[0], best[1], tuple(-i for i in best[2])):
            best = (mn, mean, combo)
    if best is None:
        raise ValueError("No eligible triplet found.")
    return best[2]


def exact_k_medoids(distance_matrix: np.ndarray, k: int = 3) -> tuple[int, ...]:
    best: tuple[float, float, tuple[int, ...]] | None = None
    for combo in itertools.combinations(range(distance_matrix.shape[0]), k):
        nearest = np.min(distance_matrix[:, combo], axis=1)
        inertia = float(np.sum(nearest))
        spread = triplet_stats(tuple(combo), distance_matrix)[1] if k == 3 else 0.0
        score = (-inertia, spread, tuple(-i for i in combo))
        if best is None or score > (-best[0], best[1], tuple(-i for i in best[2])):
            best = (inertia, spread, combo)
    if best is None:
        raise ValueError("No k-medoids solution.")
    return best[2]


def _qc_warnings_by_song(output_root: Path) -> dict[str, int]:
    path = first_existing(output_root, "03_feature_extraction/tables/feature_quality_checks.csv", "feature_quality_checks.csv")
    warnings: dict[str, int] = {}
    if not path.exists():
        return warnings
    for row in _read_csv(path):
        if row.get("passed") != "true":
            warnings[row["song"]] = warnings.get(row["song"], 0) + 1
    return warnings


def _near_duplicate_pairs(output_root: Path) -> set[frozenset[str]]:
    path = first_existing(output_root, "03_feature_extraction/tables/feature_quality_checks.csv", "feature_quality_checks.csv")
    pairs: set[frozenset[str]] = set()
    if not path.exists():
        return pairs
    for row in _read_csv(path):
        if row.get("check") != "duplicate_or_near_duplicate_feature_vectors" or row.get("passed") == "true":
            continue
        for piece in row.get("details", "").split(";"):
            ids = [p.strip() for p in piece.split("~") if p.strip()]
            if len(ids) == 2:
                pairs.add(frozenset(ids))
    return pairs


def _outlier_scores(scalar_scaled: np.ndarray, bark_scores: np.ndarray, combined_dist: np.ndarray, medoid: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    scalar_abs = np.max(np.abs(scalar_scaled), axis=1)
    centre = np.median(bark_scores, axis=0)
    bark_dist = np.sqrt(np.sum(np.square(bark_scores - centre), axis=1))
    medoid_dist = combined_dist[:, medoid]
    robust = scalar_abs + bark_dist / (np.median(bark_dist) + EPS) + medoid_dist / (np.median(medoid_dist[medoid_dist > 0]) + EPS)
    nearest = np.partition(combined_dist + np.eye(combined_dist.shape[0]) * 1e9, 1, axis=1)[:, 0]
    return robust, medoid_dist, nearest


def _rank_triplet(row: dict[str, object]) -> tuple[float, float, float, float, int]:
    return (
        float(row["minimum_pairwise_distance"]),
        float(row["mean_pairwise_distance"]),
        -float(row["maximum_robust_outlier_score"]),
        -float(row["QC_warning_count"]),
        int(row["unique_institution_count"]),
    )


def _save_figures(
    figure_root: Path,
    song_slug: str,
    ids: list[str],
    display_labels: list[str],
    institutions: list[str],
    scalar_values: np.ndarray,
    bark_raw: np.ndarray,
    scalar_columns: list[str],
    bark_columns: list[str],
    combined: np.ndarray,
    bark_scores: np.ndarray,
    distances: np.ndarray,
    selected: tuple[int, int, int],
    method_counts: dict[str, int],
    medoid_dist: np.ndarray,
    outlier_score: np.ndarray,
) -> None:
    out = figure_root / song_slug
    out.mkdir(parents=True, exist_ok=True)
    reduced = PCA(n_components=2, random_state=SEED).fit_transform(combined) if combined.shape[1] > 1 else np.column_stack([combined[:, 0], np.zeros(combined.shape[0])])
    sel = np.zeros(len(ids), dtype=bool)
    sel[list(selected)] = True
    for name, highlight in (("processed_pca_all.png", np.ones(len(ids), dtype=bool)), ("processed_pca_recommended_triplet.png", sel)):
        plt.figure(figsize=(7, 5))
        plt.scatter(reduced[:, 0], reduced[:, 1], c=np.where(highlight, "#1f77b4", "#bbbbbb"))
        for i, mix_id in enumerate(ids):
            if highlight[i]:
                plt.text(reduced[i, 0], reduced[i, 1], display_labels[i], fontsize=7)
        plt.title("2-D PCA view of processed mixes")
        plt.tight_layout()
        plt.savefig(out / name, dpi=160)
        plt.close()
    plt.figure(figsize=(7, 6))
    plt.imshow(distances, cmap="magma")
    plt.colorbar(label="combined Euclidean distance")
    plt.title("Pairwise distance heatmap")
    plt.tight_layout()
    plt.savefig(out / "pairwise_distance_heatmap.png", dpi=160)
    plt.close()
    angles = np.linspace(0, 2 * np.pi, len(scalar_columns), endpoint=False)
    angles = np.r_[angles, angles[0]]
    plt.figure(figsize=(6, 6))
    ax = plt.subplot(111, polar=True)
    for idx in selected:
        vals = np.r_[scalar_values[idx], scalar_values[idx, 0]]
        ax.plot(angles, vals, label=display_labels[idx])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(scalar_columns, fontsize=7)
    ax.legend(fontsize=7)
    plt.tight_layout()
    plt.savefig(out / "selected_scalar_radar.png", dpi=160)
    plt.close()
    bands = np.arange(1, 25)
    plt.figure(figsize=(8, 4))
    for idx in selected:
        plt.plot(bands, bark_raw[idx, :24], label=f"{display_labels[idx]} mid")
    plt.title("Selected Bark mid profiles")
    plt.tight_layout()
    plt.legend(fontsize=7)
    plt.savefig(out / "selected_bark_profile_comparison.png", dpi=160)
    plt.close()
    components = ["scalar", "bark"]
    plt.figure(figsize=(7, 4))
    for idx in selected:
        plt.bar([x + 0.25 * list(selected).index(idx) for x in range(2)], [np.linalg.norm(scalar_values[idx]), np.linalg.norm(bark_scores[idx])], width=0.22, label=display_labels[idx])
    plt.xticks(range(2), components)
    plt.title("Distance contribution scale")
    plt.legend(fontsize=7)
    plt.tight_layout()
    plt.savefig(out / "distance_decomposition.png", dpi=160)
    plt.close()
    plt.figure(figsize=(7, 4))
    plt.scatter(medoid_dist, outlier_score, c=np.where(sel, "#d62728", "#777777"))
    plt.xlabel("distance from medoid")
    plt.ylabel("robust outlier score")
    plt.tight_layout()
    plt.savefig(out / "outlier_diagnostics.png", dpi=160)
    plt.close()
    plt.figure(figsize=(max(7, len(ids) * 0.25), 4))
    plt.bar(range(len(ids)), [method_counts.get(m, 0) for m in ids])
    plt.xticks(range(len(ids)), display_labels, rotation=90, fontsize=6)
    plt.ylabel("selection count")
    plt.title("Sensitivity and method selection frequency")
    plt.tight_layout()
    plt.savefig(out / "sensitivity_selection_frequency.png", dpi=160)
    plt.close()
    order = np.argsort(medoid_dist)
    plt.figure(figsize=(max(7, len(ids) * 0.25), 4))
    plt.bar(range(len(ids)), medoid_dist[order])
    plt.xticks(range(len(ids)), [display_labels[i] for i in order], rotation=90, fontsize=6)
    plt.ylabel("distance")
    plt.title("Medoid-distance ranking")
    plt.tight_layout()
    plt.savefig(out / "medoid_distance_ranking.png", dpi=160)
    plt.close()


def _write_preview(row: pd.Series, role: str, config: SelectionConfig, output: Path) -> Path:
    decoded = decode_audio(Path(str(row["source_path"])))
    start = float(row["actual_source_start_seconds"])
    excerpt = extract_exact_excerpt(decoded.samples, decoded.sample_rate, start, EXPECTED_SECONDS)
    excerpt = ensure_sample_rate(excerpt, decoded.sample_rate, EXPECTED_SAMPLE_RATE)
    fade_len = int(round(float(config.fade_seconds) * EXPECTED_SAMPLE_RATE))
    if fade_len > 0:
        fade_in = np.linspace(0.0, 1.0, fade_len, endpoint=True, dtype=np.float32)
        fade_out = np.linspace(1.0, 0.0, fade_len, endpoint=True, dtype=np.float32)
        excerpt = excerpt.copy()
        excerpt[:fade_len] *= fade_in[:, None]
        excerpt[-fade_len:] *= fade_out[:, None]
    original_name = safe_original_mix_filename(str(row.get("original_mix_name") or get_original_mix_name(row["source_path"])))
    filename = f"{original_name}_28sec.wav"
    path = output / str(row["song"]) / role / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), excerpt.astype(np.float32, copy=False), EXPECTED_SAMPLE_RATE, subtype="PCM_16")
    return path


def run_mix_selection(config: SelectionConfig) -> MixSelectionResult:
    output_root = ensure_output_root(config)
    raw_path = first_existing(output_root, "03_feature_extraction/tables/raw_diffmst_features.csv", "raw_diffmst_features.csv")
    if not raw_path.exists():
        raise FileNotFoundError(raw_path)
    raw = pd.read_csv(raw_path).sort_values(["artist", "song", "mix_id"]).reset_index(drop=True)
    approved = {(_song_label(item["artist"], item["song"])) for item in config.approved_excerpts}
    raw = raw[raw.apply(lambda r: _song_label(r["artist"], r["song"]) in approved, axis=1)].copy()
    raw = raw[raw["feature_extraction_status"].eq("ok")].copy()
    raw["original_dataset_filename"] = raw["source_path"].map(get_original_dataset_filename)
    raw["original_mix_name"] = raw["source_path"].map(get_original_mix_name)
    numeric_cols = PRIMARY_SCALARS + BARK_COLUMNS
    if raw[numeric_cols].isna().any().any() or not np.isfinite(raw[numeric_cols].to_numpy(dtype=np.float64)).all():
        raise ValueError("Stage 4 input contains missing, NaN or Inf feature values.")

    qc_warning_counts = _qc_warnings_by_song(output_root)
    near_pairs = _near_duplicate_pairs(output_root)
    processed_rows: list[dict[str, object]] = []
    scalar_param_rows: list[dict[str, object]] = []
    bark_param_rows: list[dict[str, object]] = []
    pca_var_rows: list[dict[str, object]] = []
    pca_loading_rows: list[dict[str, object]] = []
    pca_score_rows: list[dict[str, object]] = []
    pair_rows: list[dict[str, object]] = []
    triplet_rows: list[dict[str, object]] = []
    method_rows: list[dict[str, object]] = []
    recommendation_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    report_lines = [
        "# Stage 4 Final Mix Selection Report",
        "",
        "Formula: within each song, scalar and Bark dimensions are robust-scaled as `(x - median) / IQR`. Bark-only PCA is fitted to robust-scaled Bark bins and the minimum number of PCs explaining at least 95% variance is retained. The scalar block and retained Bark-PC block are each divided by `sqrt(mean(row_squared_norm))`, then concatenated so each block has expected squared contribution 1.",
        "",
    ]
    selections: list[SongSelection] = []
    preview_manifest: list[dict[str, object]] = []
    preview_files: list[Path] = []
    tables = stage4_tables(output_root)
    reports = stage4_reports(output_root)
    figure_root = stage4_diagnostics(output_root)
    preview_root = stage4_previews(output_root)

    for (artist, song), group in raw.groupby(["artist", "song"], sort=True):
        group = group.sort_values("mix_id").reset_index(drop=True)
        ids = group["mix_id"].tolist()
        display_labels = group["original_mix_name"].tolist()
        institutions = group["institution_code"].fillna("").tolist()
        label = _song_label(str(artist), str(song))
        scalar_raw = group[PRIMARY_SCALARS].to_numpy(dtype=np.float64)
        bark_raw = group[BARK_COLUMNS].to_numpy(dtype=np.float64)
        scalar_scaled, scalar_params = robust_parameters(scalar_raw, PRIMARY_SCALARS)
        bark_scaled, bark_params = robust_parameters(bark_raw, BARK_COLUMNS)
        pca, bark_scores_all, retained = select_bark_pca(bark_scaled, 0.95)
        bark_scores = bark_scores_all[:, :retained]
        scalar_weighted = equal_block_weight(scalar_scaled)
        bark_weighted = equal_block_weight(bark_scores)
        combined = np.hstack([scalar_weighted, bark_weighted])
        rms_excluded = np.hstack([equal_block_weight(scalar_scaled[:, 1:]), bark_weighted])
        combined_dist = pairwise_matrix(combined)
        scalar_dist = pairwise_matrix(scalar_weighted)
        bark_dist = pairwise_matrix(bark_weighted)
        rms_excluded_dist = pairwise_matrix(rms_excluded)
        manhattan_dist = pairwise_matrix(combined, "manhattan")
        medoid = medoid_index(combined_dist)
        outlier_score, medoid_dist, nearest_dist = _outlier_scores(scalar_scaled, bark_scores, combined_dist, medoid)
        centre_dist = np.sqrt(np.sum(np.square(combined), axis=1))
        near_feature_threshold = max(1e-9, float(np.percentile(combined_dist[combined_dist > 0], 2)) if np.any(combined_dist > 0) else 1e-9)
        method_triplets: dict[str, tuple[int, int, int]] = {}
        method_triplets["A_representative_plus_maximum_contrasts"] = best_triplet(combined_dist, required_index=medoid)
        method_triplets["B_unconstrained_maximum_dispersion"] = best_triplet(combined_dist)
        method_triplets["C_exact_k_medoids_k3"] = tuple(sorted(exact_k_medoids(combined_dist, 3)))
        institutional_combos = [combo for combo in itertools.combinations(range(len(ids)), 3) if medoid in combo and len({institutions[i] for i in combo}) >= min(2, len(set(institutions)))]
        method_triplets["D_institution_aware_representative_plus_contrasts"] = best_triplet(combined_dist, eligible=institutional_combos) if institutional_combos else method_triplets["A_representative_plus_maximum_contrasts"]
        sensitivity_mats = {
            "primary_combined": combined_dist,
            "rms_excluded": rms_excluded_dist,
            "scalar_only": scalar_dist,
            "bark_only": bark_dist,
            "manhattan": manhattan_dist,
            "equal_dimension_weighting": pairwise_matrix(np.hstack([scalar_scaled, bark_scores])),
            "paper_weight_inspired_secondary": pairwise_matrix(np.hstack([scalar_scaled * np.array([10.0, 0.1, 1.0, 1.0]), bark_scores])),
        }
        for name, matrix in sensitivity_mats.items():
            method_triplets[f"sensitivity_{name}"] = best_triplet(matrix, required_index=medoid if name != "scalar_only" else None)

        selection_counts = {mix_id: 0 for mix_id in ids}
        for combo in method_triplets.values():
            for idx in combo:
                selection_counts[ids[idx]] += 1

        for params, dest in ((scalar_params, scalar_param_rows), (bark_params, bark_param_rows)):
            for row in params:
                row.update({"artist": artist, "song": song})
                dest.append(row)
        for pc_idx, ratio in enumerate(pca.explained_variance_ratio_, 1):
            pca_var_rows.append({"artist": artist, "song": song, "component": f"bark_pc_{pc_idx:02d}", "explained_variance_ratio": ratio, "cumulative_explained_variance": np.sum(pca.explained_variance_ratio_[:pc_idx]), "retained": pc_idx <= retained})
        nonconstant_cols = [col for col, var in zip(BARK_COLUMNS, np.var(bark_scaled, axis=0)) if var > EPS]
        for pc_idx in range(pca.components_.shape[0]):
            for col, loading in zip(nonconstant_cols, pca.components_[pc_idx]):
                pca_loading_rows.append({"artist": artist, "song": song, "component": f"bark_pc_{pc_idx + 1:02d}", "feature": col, "loading": loading, "retained": pc_idx < retained})
        for i, mix_id in enumerate(ids):
            row_base = {col: group.loc[i, col] for col in group.columns}
            out_flags = []
            if abs(scalar_scaled[i, 0]) > 3.5:
                out_flags.append("extreme_rms")
            if abs(scalar_scaled[i, 1]) > 3.5:
                out_flags.append("extreme_crest_factor")
            if abs(scalar_scaled[i, 2]) > 3.5:
                out_flags.append("extreme_stereo_width")
            if abs(scalar_scaled[i, 3]) > 3.5:
                out_flags.append("large_stereo_imbalance")
            if nearest_dist[i] <= near_feature_threshold:
                out_flags.append("near_duplicate_feature_vector")
            proc = dict(row_base)
            proc.update({"distance_from_medoid": medoid_dist[i], "nearest_neighbor_distance": nearest_dist[i], "outlier_score": outlier_score[i], "QC_warning_count": qc_warning_counts.get(label, 0), "QC_flags": ";".join(out_flags)})
            for j, col in enumerate(PRIMARY_SCALARS):
                proc[f"scaled_{col}"] = scalar_scaled[i, j]
                proc[f"combined_scalar_{col}"] = scalar_weighted[i, j]
            for j in range(retained):
                proc[f"bark_pc_{j + 1:02d}"] = bark_scores[i, j]
                proc[f"combined_bark_pc_{j + 1:02d}"] = bark_weighted[i, j]
            processed_rows.append(proc)
            score = {"artist": artist, "song": song, "original_dataset_filename": group.loc[i, "original_dataset_filename"], "original_mix_name": group.loc[i, "original_mix_name"], "mix_id": mix_id}
            for j in range(bark_scores.shape[1]):
                score[f"bark_pc_{j + 1:02d}"] = bark_scores[i, j]
            pca_score_rows.append(score)

        for i, j in itertools.combinations(range(len(ids)), 2):
            pair_rows.append({"artist": artist, "song": song, "mix_i": ids[i], "mix_i_original_name": display_labels[i], "mix_j": ids[j], "mix_j_original_name": display_labels[j], "combined_euclidean_distance": combined_dist[i, j], "scalar_only_distance": scalar_dist[i, j], "bark_only_distance": bark_dist[i, j], "rms_excluded_distance": rms_excluded_dist[i, j], "manhattan_distance": manhattan_dist[i, j], "near_duplicate_flag": frozenset([ids[i], ids[j]]) in near_pairs or combined_dist[i, j] <= near_feature_threshold})

        for t_num, combo in enumerate(itertools.combinations(range(len(ids)), 3), 1):
            mn, mean, mx, pairs = triplet_stats(combo, combined_dist)
            near_dup = any(frozenset([ids[a], ids[b]]) in near_pairs or combined_dist[a, b] <= near_feature_threshold for a, b in itertools.combinations(combo, 2))
            row = {
                "artist": artist, "song": song, "triplet_id": f"{_song_slug(str(song))}_{t_num:05d}",
                "mix_1": ids[combo[0]], "mix_1_original_name": display_labels[combo[0]], "mix_2": ids[combo[1]], "mix_2_original_name": display_labels[combo[1]], "mix_3": ids[combo[2]], "mix_3_original_name": display_labels[combo[2]],
                "institution_1": institutions[combo[0]], "institution_2": institutions[combo[1]], "institution_3": institutions[combo[2]],
                "unique_institution_count": len({institutions[i] for i in combo}), "contains_medoid": medoid in combo,
                "pairwise_distance_1": pairs[0], "pairwise_distance_2": pairs[1], "pairwise_distance_3": pairs[2],
                "minimum_pairwise_distance": mn, "mean_pairwise_distance": mean, "maximum_pairwise_distance": mx,
                "scalar_only_minimum_distance": triplet_stats(combo, scalar_dist)[0],
                "bark_only_minimum_distance": triplet_stats(combo, bark_dist)[0],
                "rms_excluded_minimum_distance": triplet_stats(combo, rms_excluded_dist)[0],
                "manhattan_minimum_distance": triplet_stats(combo, manhattan_dist)[0],
                "average_distance_to_song_centre": float(np.mean(centre_dist[list(combo)])),
                "maximum_distance_to_song_centre": float(np.max(centre_dist[list(combo)])),
                "average_robust_outlier_score": float(np.mean(outlier_score[list(combo)])),
                "maximum_robust_outlier_score": float(np.max(outlier_score[list(combo)])),
                "QC_warning_count": qc_warning_counts.get(label, 0),
                "near_duplicate_flag": near_dup,
                "algorithm_eligibility": not near_dup,
                "technical_rejection_reason": "near_duplicate_pair" if near_dup else "",
            }
            triplet_rows.append(row)

        for method, combo in method_triplets.items():
            mn, mean, mx, _ = triplet_stats(combo, combined_dist)
            method_rows.append({"artist": artist, "song": song, "method": method, "original_mix_names": "|".join(display_labels[i] for i in combo), "mix_ids": "|".join(ids[i] for i in combo), "contains_medoid": medoid in combo, "minimum_pairwise_distance": mn, "mean_pairwise_distance": mean, "maximum_pairwise_distance": mx, "unique_institution_count": len({institutions[i] for i in combo})})

        song_triplets = [row for row in triplet_rows if row["artist"] == artist and row["song"] == song and row["contains_medoid"] and not row["near_duplicate_flag"]]
        recommended_row = max(song_triplets, key=_rank_triplet)
        selected_ids = [recommended_row["mix_1"], recommended_row["mix_2"], recommended_row["mix_3"]]
        selected = tuple(ids.index(mix_id) for mix_id in selected_ids)
        selected = tuple([medoid] + [i for i in selected if i != medoid])
        roles = ["representative", "contrast_1", "contrast_2"]
        min_dist, mean_dist, _, _ = triplet_stats(selected, combined_dist)
        stability = float(np.mean([idx in selected for combo in method_triplets.values() for idx in combo]))
        outlier_selected = [ids[i] for i in selected if outlier_score[i] > np.percentile(outlier_score, 90)]
        for role, idx in zip(roles, selected):
            selected_by_primary = ids[idx] in [ids[i] for i in method_triplets["A_representative_plus_maximum_contrasts"]]
            row = group.loc[idx]
            rationale = "Medoid representative in full combined space." if role == "representative" else "Contrast selected for high full-space separation while avoiding Stage 3 near-duplicate pairs."
            if outlier_selected and ids[idx] in outlier_selected:
                rationale += " Flagged for manual listening as a high robust-outlier-score mix."
            recommendation_rows.append({"artist": artist, "song": song, "role": role, "institution_code": row["institution_code"], "institution_name": row["institution_name"], "original_dataset_filename": row["original_dataset_filename"], "original_mix_name": row["original_mix_name"], "mix_id": ids[idx], "source_path": row["source_path"], "selected_by_primary_method": selected_by_primary, "selection_frequency_across_methods": selection_counts[ids[idx]], "distance_from_medoid": medoid_dist[idx], "outlier_score": outlier_score[idx], "QC_warning_count": qc_warning_counts.get(label, 0), "rationale": rationale})
            preview = _write_preview(row, role, config, preview_root)
            preview_files.append(preview)
            preview_manifest.append({"artist": artist, "song": song, "role": role, "institution": row["institution_name"], "original_dataset_filename": row["original_dataset_filename"], "original_mix_name": row["original_mix_name"], "mix_id": ids[idx], "source_path": row["source_path"], "preview_filename": str(preview.relative_to(preview_root)), "raw_loudness_RMS": row["rms_mean"], "purpose": "Stage 4 sanity listening; no loudness normalisation, limiting or compression"})
        summary_rows.append({"artist": artist, "song": song, "representative_original_mix_name": display_labels[selected[0]], "representative_mix_id": ids[selected[0]], "contrast_1_original_mix_name": display_labels[selected[1]], "contrast_1_mix_id": ids[selected[1]], "contrast_2_original_mix_name": display_labels[selected[2]], "contrast_2_mix_id": ids[selected[2]], "minimum_pairwise_distance": min_dist, "mean_pairwise_distance": mean_dist, "unique_institution_count": len({institutions[i] for i in selected}), "stability_score": stability, "manual_listening_required": bool(outlier_selected), "notes": "; ".join(outlier_selected) if outlier_selected else "No selected pathological outlier detected by robust diagnostics."})
        selections.append(SongSelection(str(artist), str(song), len(group), ids[medoid], retained, float(np.sum(pca.explained_variance_ratio_[:retained])), tuple(ids[i] for i in selected), min_dist, mean_dist, len({institutions[i] for i in selected}), stability, bool(outlier_selected)))
        _save_figures(figure_root, _song_slug(str(song)), ids, display_labels, institutions, scalar_scaled, bark_raw, PRIMARY_SCALARS, BARK_COLUMNS, combined, bark_scores, combined_dist, selected, selection_counts, medoid_dist, outlier_score)
        report_lines.extend([
            f"## {artist} - {song}",
            "",
            f"- Retained mix count: {len(group)}",
            f"- Medoid: {display_labels[medoid]}",
            f"- Selected representative: {display_labels[selected[0]]}",
            f"- Selected contrasts: {display_labels[selected[1]]}, {display_labels[selected[2]]}",
            f"- Pairwise distances: minimum {min_dist:.4f}, mean {mean_dist:.4f}",
            f"- Bark PCA: {retained} components, {np.sum(pca.explained_variance_ratio_[:retained]):.2%} variance explained",
            f"- Institutions represented: {', '.join(sorted({institutions[i] for i in selected}))}",
            f"- Sensitivity stability: {stability:.3f}",
            f"- QC and outlier review: {qc_warning_counts.get(label, 0)} song-level warnings; selected high-outlier mixes: {', '.join(display_labels[ids.index(m)] for m in outlier_selected) if outlier_selected else 'none'}",
            "- Alternatives not selected: higher-dispersion alternatives were rejected when they omitted the medoid or contained Stage 3 near-duplicate pairs; institution diversity was used only as a secondary advantage.",
            "",
        ])

    processed_columns = list(raw.columns) + ["distance_from_medoid", "nearest_neighbor_distance", "outlier_score", "QC_warning_count", "QC_flags"] + [f"scaled_{c}" for c in PRIMARY_SCALARS] + [f"combined_scalar_{c}" for c in PRIMARY_SCALARS] + [f"bark_pc_{i:02d}" for i in range(1, 38)] + [f"combined_bark_pc_{i:02d}" for i in range(1, 38)]
    processed_path = tables / "processed_features.csv"
    _write_csv(processed_path, processed_rows, processed_columns)
    _write_csv(tables / "scalar_preprocessing_parameters.csv", scalar_param_rows, ["artist", "song", "feature", "median", "q25", "q75", "iqr", "near_zero_iqr", "retained", "scale_formula"])
    _write_csv(tables / "bark_preprocessing_parameters.csv", bark_param_rows, ["artist", "song", "feature", "median", "q25", "q75", "iqr", "near_zero_iqr", "retained", "scale_formula"])
    _write_csv(tables / "bark_pca_explained_variance.csv", pca_var_rows, ["artist", "song", "component", "explained_variance_ratio", "cumulative_explained_variance", "retained"])
    _write_csv(tables / "bark_pca_loadings.csv", pca_loading_rows, ["artist", "song", "component", "feature", "loading", "retained"])
    _write_csv(tables / "bark_pca_scores.csv", pca_score_rows, ["artist", "song", "original_dataset_filename", "original_mix_name", "mix_id"] + [f"bark_pc_{i:02d}" for i in range(1, 38)])
    _write_csv(tables / "pairwise_distances.csv", pair_rows, ["artist", "song", "mix_i", "mix_i_original_name", "mix_j", "mix_j_original_name", "combined_euclidean_distance", "scalar_only_distance", "bark_only_distance", "rms_excluded_distance", "manhattan_distance", "near_duplicate_flag"])
    _write_csv(tables / "all_triplet_scores.csv", triplet_rows, ["artist", "song", "triplet_id", "mix_1", "mix_1_original_name", "mix_2", "mix_2_original_name", "mix_3", "mix_3_original_name", "institution_1", "institution_2", "institution_3", "unique_institution_count", "contains_medoid", "pairwise_distance_1", "pairwise_distance_2", "pairwise_distance_3", "minimum_pairwise_distance", "mean_pairwise_distance", "maximum_pairwise_distance", "scalar_only_minimum_distance", "bark_only_minimum_distance", "rms_excluded_minimum_distance", "manhattan_minimum_distance", "average_distance_to_song_centre", "maximum_distance_to_song_centre", "average_robust_outlier_score", "maximum_robust_outlier_score", "QC_warning_count", "near_duplicate_flag", "algorithm_eligibility", "technical_rejection_reason"])
    _write_csv(tables / "selection_method_comparison.csv", method_rows, ["artist", "song", "method", "original_mix_names", "mix_ids", "contains_medoid", "minimum_pairwise_distance", "mean_pairwise_distance", "maximum_pairwise_distance", "unique_institution_count"])
    recommended_path = tables / "recommended_triplets.csv"
    _write_csv(recommended_path, recommendation_rows, ["artist", "song", "role", "institution_code", "institution_name", "original_dataset_filename", "original_mix_name", "mix_id", "source_path", "selected_by_primary_method", "selection_frequency_across_methods", "distance_from_medoid", "outlier_score", "QC_warning_count", "rationale"])
    summary_path = tables / "final_mix_selection_summary.csv"
    _write_csv(summary_path, summary_rows, ["artist", "song", "representative_original_mix_name", "representative_mix_id", "contrast_1_original_mix_name", "contrast_1_mix_id", "contrast_2_original_mix_name", "contrast_2_mix_id", "minimum_pairwise_distance", "mean_pairwise_distance", "unique_institution_count", "stability_score", "manual_listening_required", "notes"])
    manifest_path = tables / "selected_mix_review_manifest.csv"
    _write_csv(manifest_path, preview_manifest, ["artist", "song", "role", "institution", "original_dataset_filename", "original_mix_name", "mix_id", "source_path", "preview_filename", "raw_loudness_RMS", "purpose"])
    report_path = reports / "final_mix_selection_report.md"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return MixSelectionResult(output_root, processed_path, recommended_path, summary_path, report_path, manifest_path, preview_root, selections, preview_files)
