from __future__ import annotations

"""Stage 4 v2 acoustic candidate-pool generation.

This version removes stereo imbalance from all acoustic-diversity coordinates.
The raw stereo-imbalance descriptor is retained only for QC annotation.
"""

import csv
import hashlib
import itertools
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import soundfile as sf
import yaml
from sklearn.decomposition import PCA

from stimulus_selection.audio_decode import decode_audio, ensure_sample_rate
from stimulus_selection.config import SelectionConfig
from stimulus_selection.feature_extraction import BARK_COLUMNS, EXPECTED_SAMPLE_RATE, EXPECTED_SECONDS, extract_exact_excerpt
from stimulus_selection.mix_selection import equal_block_weight, medoid_index, pairwise_matrix, robust_parameters, select_bark_pca
from stimulus_selection.naming import get_original_dataset_filename, get_original_mix_name, safe_original_mix_filename
from stimulus_selection.output_layout import (
    first_existing,
    stage4_v2_diagnostics,
    stage4_v2_previews,
    stage4_v2_reports,
    stage4_v2_root,
    stage4_v2_tables,
    stage4_v2_validation,
)
from stimulus_selection.paths import ensure_output_root


V2_SCALARS = ["rms_mean", "crest_factor_mean", "stereo_width"]
QC_ONLY_FEATURES = ["stereo_imbalance"]
EPS = 1e-12
SEED = 42
EXPECTED_COUNTS = {
    "Lead Me": 37,
    "In The Meantime": 36,
    "Red To Blue": 10,
    "Pouring Room": 9,
}


@dataclass(frozen=True)
class V2SongSummary:
    artist: str
    song: str
    retained_count: int
    candidate_pool_target: str
    candidate_pool_actual: int
    bark_components: int
    bark_variance: float
    medoid_original_name: str
    minimum_pairwise_distance: float
    mean_pairwise_distance: float
    stereo_imbalance_flags: int
    unrated_mixes: int


@dataclass(frozen=True)
class MixSelectionV2Result:
    output_root: Path
    candidate_pool_path: Path
    report_path: Path
    preview_manifest_path: Path
    preview_root: Path
    song_summaries: list[V2SongSummary]
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


def _write_csv(path: Path, rows: Iterable[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: _fmt(row.get(col, "")) for col in columns})


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _song_label(artist: str, song: str) -> str:
    return f"{artist} - {song}"


def _song_slug(song: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", song)


def _load_v2_config(config_path: str | Path) -> dict[str, object]:
    raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    cfg = raw.get("mix_selection_v2")
    if not isinstance(cfg, dict):
        raise ValueError("configs/stimulus_selection.yaml is missing mix_selection_v2.")
    if list(cfg.get("scalar_features", [])) != V2_SCALARS:
        raise ValueError(f"mix_selection_v2.scalar_features must be {V2_SCALARS}.")
    if "stereo_imbalance" in cfg.get("scalar_features", []):
        raise AssertionError("stereo_imbalance must not be a v2 diversity scalar.")
    return cfg


def _rating_status_by_mix(config: SelectionConfig) -> dict[str, str]:
    path = config.relationship_tables_root / "data" / "evaluations.csv"
    if not path.exists():
        return {}
    rated = {row["mix_id"] for row in _read_csv(path) if row.get("mix_id")}
    return {mix_id: "previously_evaluated" for mix_id in rated}


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


def _pool_pair_stats(indices: Sequence[int], distance_matrix: np.ndarray) -> tuple[float, float]:
    if len(indices) < 2:
        return 0.0, 0.0
    vals = [float(distance_matrix[i, j]) for i, j in itertools.combinations(indices, 2)]
    return min(vals), float(np.mean(vals))


def _outlier_scores(scalar_scaled: np.ndarray, bark_scores: np.ndarray, combined_dist: np.ndarray, medoid: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    scalar_abs = np.max(np.abs(scalar_scaled), axis=1)
    centre = np.median(bark_scores, axis=0)
    bark_dist = np.sqrt(np.sum(np.square(bark_scores - centre), axis=1))
    positive_bark = bark_dist[bark_dist > 0]
    medoid_dist = combined_dist[:, medoid]
    positive_medoid = medoid_dist[medoid_dist > 0]
    robust = (
        scalar_abs
        + bark_dist / (float(np.median(positive_bark)) + EPS if positive_bark.size else 1.0)
        + medoid_dist / (float(np.median(positive_medoid)) + EPS if positive_medoid.size else 1.0)
    )
    nearest = np.partition(combined_dist + np.eye(combined_dist.shape[0]) * 1e9, 1, axis=1)[:, 0]
    return robust, medoid_dist, nearest


def stereo_imbalance_qc(group: pd.DataFrame) -> list[dict[str, object]]:
    values = group["stereo_imbalance"].to_numpy(dtype=np.float64)
    abs_values = np.abs(values)
    median = float(np.median(abs_values))
    mad = float(np.median(np.abs(abs_values - median)))
    q25, q75 = np.percentile(abs_values, [25, 75])
    iqr = float(q75 - q25)
    scale = max(1.4826 * mad, iqr / 1.349 if iqr > 0 else 0.0, 0.02)
    threshold = 3.5
    rows: list[dict[str, object]] = []
    for (_, row), signed, absolute in zip(group.iterrows(), values, abs_values):
        score = (absolute - median) / scale
        flag = bool(score >= threshold)
        rows.append({
            "artist": row["artist"],
            "song": row["song"],
            "original_mix_name": row["original_mix_name"],
            "original_dataset_filename": row["original_dataset_filename"],
            "mix_id": row["mix_id"],
            "stereo_imbalance": signed,
            "absolute_stereo_imbalance": absolute,
            "within_song_median_absolute_stereo_imbalance": median,
            "within_song_robust_scale": scale,
            "robust_qc_score": score,
            "qc_flag": flag,
            "qc_reason": f"absolute stereo imbalance robust score {score:.2f} >= {threshold:.1f}" if flag else "",
            "review_required": flag,
            "review_priority": "high" if flag and score >= 5.0 else ("medium" if flag else "normal"),
        })
    return rows


def assert_no_stereo_imbalance_in_diversity(feature_names: Sequence[str]) -> None:
    offenders = [name for name in feature_names if "stereo_imbalance" in name]
    if offenders:
        raise AssertionError(f"stereo_imbalance entered a v2 diversity matrix: {offenders}")


def farthest_point_pool(
    distance_matrix: np.ndarray,
    target: int,
    medoid: int,
    near_duplicate_pairs: set[frozenset[str]],
    ids: Sequence[str],
) -> tuple[list[int], list[float], list[str]]:
    selected = [medoid]
    selection_distances = [0.0]
    notes = ["acoustic medoid seed"]
    while len(selected) < min(target, distance_matrix.shape[0]):
        best: tuple[float, float, int, bool] | None = None
        for idx in range(distance_matrix.shape[0]):
            if idx in selected:
                continue
            has_near_duplicate = any(frozenset([ids[idx], ids[j]]) in near_duplicate_pairs for j in selected)
            min_dist = float(np.min(distance_matrix[idx, selected]))
            mean_dist = float(np.mean(distance_matrix[idx, selected]))
            score = (min_dist, mean_dist, -idx)
            if has_near_duplicate and len(selected) + 1 < target:
                score = (-1.0, mean_dist, -idx)
            if best is None or score > (best[0], best[1], -best[2]):
                best = (score[0], score[1], idx, has_near_duplicate)
        if best is None:
            break
        _, _, idx, has_near_duplicate = best
        selected.append(idx)
        selection_distances.append(float(np.min(distance_matrix[idx, selected[:-1]])))
        notes.append("selected by maximum minimum acoustic distance" + ("; near duplicate retained because target requires it" if has_near_duplicate else ""))
    return selected, selection_distances, notes


def greedy_kmedoids_pool(distance_matrix: np.ndarray, target: int, medoid: int) -> list[int]:
    selected, _, _ = farthest_point_pool(distance_matrix, target, medoid, set(), [str(i) for i in range(distance_matrix.shape[0])])
    selected = list(selected)
    changed = True
    while changed:
        changed = False
        current = float(np.sum(np.min(distance_matrix[:, selected], axis=1)))
        for pos, old in enumerate(list(selected)):
            for candidate in range(distance_matrix.shape[0]):
                if candidate in selected:
                    continue
                trial = list(selected)
                trial[pos] = candidate
                trial = sorted(trial)
                score = float(np.sum(np.min(distance_matrix[:, trial], axis=1)))
                if score + 1e-12 < current:
                    selected = trial
                    current = score
                    changed = True
                    break
            if changed:
                break
    return sorted(selected)


def _write_preview(row: pd.Series, config: SelectionConfig, output: Path) -> tuple[Path, str]:
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
    filename = f"{safe_original_mix_filename(str(row['original_mix_name']))}_28sec.wav"
    path = output / str(row["song"]) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), excerpt.astype(np.float32, copy=False), EXPECTED_SAMPLE_RATE, subtype="PCM_16")
    return path, _sha256(path)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _plot_bar(path: Path, labels: Sequence[str], values: Sequence[float], title: str, ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(max(8, len(labels) * 0.28), 4))
    plt.bar(range(len(labels)), values)
    plt.xticks(range(len(labels)), labels, rotation=90, fontsize=6)
    plt.title(title)
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def _save_figures(
    figure_root: Path,
    song: str,
    labels: Sequence[str],
    combined: np.ndarray,
    combined_dist: np.ndarray,
    scalar_scaled: np.ndarray,
    bark_raw: np.ndarray,
    medoid_dist: np.ndarray,
    nearest_dist: np.ndarray,
    outlier_score: np.ndarray,
    qc_rows: Sequence[dict[str, object]],
    pool_indices: Sequence[int],
    inclusion_counts: dict[str, int],
    v1_selected: set[str],
) -> None:
    out = figure_root / _song_slug(song)
    out.mkdir(parents=True, exist_ok=True)
    reduced = PCA(n_components=2, random_state=SEED).fit_transform(combined) if combined.shape[1] > 1 else np.column_stack([combined[:, 0], np.zeros(combined.shape[0])])
    pool = np.zeros(len(labels), dtype=bool)
    pool[list(pool_indices)] = True
    for name, mask, title in [
        ("corrected_acoustic_space_all.png", np.ones(len(labels), dtype=bool), "Corrected acoustic space: all mixes"),
        ("corrected_acoustic_space_candidate_pool.png", pool, "Corrected acoustic space: candidate pool"),
    ]:
        plt.figure(figsize=(7, 5))
        plt.scatter(reduced[:, 0], reduced[:, 1], c=np.where(mask, "#1f77b4", "#bbbbbb"))
        for i, label in enumerate(labels):
            if mask[i]:
                plt.text(reduced[i, 0], reduced[i, 1], label, fontsize=7)
        plt.title(title)
        plt.tight_layout()
        plt.savefig(out / name, dpi=160)
        plt.close()
    plt.figure(figsize=(7, 6))
    plt.imshow(combined_dist, cmap="magma")
    plt.colorbar(label="combined Euclidean distance")
    plt.title("Corrected pairwise acoustic distance")
    plt.tight_layout()
    plt.savefig(out / "pairwise_distance_heatmap.png", dpi=160)
    plt.close()
    for col_idx, feature in enumerate(V2_SCALARS):
        _plot_bar(out / f"scalar_{feature}.png", labels, scalar_scaled[:, col_idx], f"Scaled {feature}", feature)
    bands = np.arange(1, 25)
    plt.figure(figsize=(8, 4))
    plt.plot(bands, bark_raw[:, :24].mean(axis=0), label="mid mean")
    plt.plot(bands, bark_raw[:, 24:].mean(axis=0), label="side mean")
    plt.title("Bark profile overview")
    plt.xlabel("Bark band")
    plt.ylabel("log magnitude")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out / "bark_profile_overview.png", dpi=160)
    plt.close()
    _plot_bar(out / "medoid_distance_ranking.png", [labels[i] for i in np.argsort(medoid_dist)], medoid_dist[np.argsort(medoid_dist)], "Distance from acoustic medoid", "distance")
    _plot_bar(out / "nearest_neighbour_distance_ranking.png", [labels[i] for i in np.argsort(nearest_dist)], nearest_dist[np.argsort(nearest_dist)], "Nearest-neighbour distance", "distance")
    _plot_bar(out / "acoustic_outlier_diagnostic.png", [labels[i] for i in np.argsort(outlier_score)], outlier_score[np.argsort(outlier_score)], "Acoustic outlier score", "score")
    _plot_bar(out / "stereo_imbalance_qc_only.png", labels, [float(r["absolute_stereo_imbalance"]) for r in qc_rows], "Stereo imbalance QC only", "absolute imbalance")
    _plot_bar(out / "candidate_inclusion_frequency.png", labels, [inclusion_counts.get(label, 0) for label in labels], "Candidate inclusion frequency across sensitivity methods", "count")
    plt.figure(figsize=(max(8, len(labels) * 0.3), 3))
    x = np.arange(len(labels))
    plt.bar(x - 0.2, [1 if label in v1_selected else 0 for label in labels], width=0.4, label="v1 selected")
    plt.bar(x + 0.2, [1 if pool[i] else 0 for i in range(len(labels))], width=0.4, label="v2 pool")
    plt.xticks(x, labels, rotation=90, fontsize=6)
    plt.yticks([0, 1])
    plt.title("v1 selected mixes versus v2 candidate pool")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out / "v1_versus_v2_selected_mix_comparison.png", dpi=160)
    plt.close()


def _old_stage4_selected(output_root: Path) -> dict[str, set[str]]:
    path = first_existing(output_root, "04_mix_selection/tables/recommended_triplets.csv")
    if not path.exists():
        return {}
    selected: dict[str, set[str]] = {}
    for row in _read_csv(path):
        selected.setdefault(row["song"], set()).add(row["original_mix_name"])
    return selected


def run_mix_selection_v2(config: SelectionConfig, config_path: str | Path) -> MixSelectionV2Result:
    v2_cfg = _load_v2_config(config_path)
    output_root = ensure_output_root(config)
    raw_path = first_existing(output_root, "03_feature_extraction/tables/raw_diffmst_features.csv", "raw_diffmst_features.csv")
    if not raw_path.exists():
        raise FileNotFoundError(raw_path)
    raw = pd.read_csv(raw_path).sort_values(["artist", "song", "mix_id"]).reset_index(drop=True)
    approved = {_song_label(item["artist"], item["song"]) for item in config.approved_excerpts}
    raw = raw[raw.apply(lambda r: _song_label(r["artist"], r["song"]) in approved, axis=1)].copy()
    if not raw["feature_extraction_status"].eq("ok").all():
        raise ValueError("Not all retained Stage 3 rows have successful feature extraction.")
    raw["original_dataset_filename"] = raw["source_path"].map(get_original_dataset_filename)
    raw["original_mix_name"] = raw["source_path"].map(get_original_mix_name)
    required = V2_SCALARS + BARK_COLUMNS + ["stereo_imbalance"]
    if raw[required].isna().any().any() or not np.isfinite(raw[required].to_numpy(dtype=np.float64)).all():
        raise ValueError("Stage 4 v2 input contains missing, NaN or Inf required features.")
    counts = raw.groupby("song").size().to_dict()
    expected_counts = v2_cfg.get("expected_retained_counts", EXPECTED_COUNTS)
    if expected_counts:
        expected_counts = {str(k): int(v) for k, v in dict(expected_counts).items()}
        if counts != expected_counts:
            raise ValueError(f"Unexpected retained population: {counts}; expected {expected_counts}.")
    assert_no_stereo_imbalance_in_diversity(V2_SCALARS + BARK_COLUMNS)

    tables = stage4_v2_tables(output_root)
    reports = stage4_v2_reports(output_root)
    diagnostics = stage4_v2_diagnostics(output_root)
    previews = stage4_v2_previews(output_root)
    validation = stage4_v2_validation(output_root)
    root = stage4_v2_root(output_root)
    for folder in (tables, reports, diagnostics, previews, validation):
        folder.mkdir(parents=True, exist_ok=True)

    rating_status = _rating_status_by_mix(config)
    near_pairs = _near_duplicate_pairs(output_root)
    old_selected = _old_stage4_selected(output_root)
    candidate_targets = dict(v2_cfg.get("candidate_pool", {}))

    processed_rows: list[dict[str, object]] = []
    scalar_param_rows: list[dict[str, object]] = []
    bark_param_rows: list[dict[str, object]] = []
    pca_var_rows: list[dict[str, object]] = []
    pca_loading_rows: list[dict[str, object]] = []
    pca_score_rows: list[dict[str, object]] = []
    pair_rows: list[dict[str, object]] = []
    qc_rows_all: list[dict[str, object]] = []
    pool_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    sensitivity_rows: list[dict[str, object]] = []
    preview_rows: list[dict[str, object]] = []
    preview_files: list[Path] = []
    song_summaries: list[V2SongSummary] = []
    proof_rows: list[dict[str, object]] = []

    for (artist, song), group in raw.groupby(["artist", "song"], sort=True):
        group = group.sort_values("mix_id").reset_index(drop=True)
        ids = group["mix_id"].tolist()
        labels = group["original_mix_name"].tolist()
        scalar_raw = group[V2_SCALARS].to_numpy(dtype=np.float64)
        bark_raw = group[BARK_COLUMNS].to_numpy(dtype=np.float64)
        scalar_scaled, scalar_params = robust_parameters(scalar_raw, V2_SCALARS)
        bark_scaled, bark_params = robust_parameters(bark_raw, BARK_COLUMNS)
        pca, bark_scores_all, retained = select_bark_pca(bark_scaled, float(v2_cfg.get("bark_variance_threshold", 0.95)))
        bark_scores = bark_scores_all[:, :retained]
        scalar_weighted = equal_block_weight(scalar_scaled)
        bark_weighted = equal_block_weight(bark_scores)
        combined = np.hstack([scalar_weighted, bark_weighted])
        rms_excluded = np.hstack([equal_block_weight(scalar_scaled[:, 1:]), bark_weighted])
        feature_names = [f"combined_scalar_{c}" for c in V2_SCALARS] + [f"combined_bark_pc_{i:02d}" for i in range(1, retained + 1)]
        assert_no_stereo_imbalance_in_diversity(feature_names)
        combined_dist = pairwise_matrix(combined)
        scalar_dist = pairwise_matrix(scalar_weighted)
        bark_dist = pairwise_matrix(bark_weighted)
        rms_excluded_dist = pairwise_matrix(rms_excluded)
        manhattan_dist = pairwise_matrix(combined, "manhattan")
        medoid = medoid_index(combined_dist)
        outlier_score, medoid_dist, nearest_dist = _outlier_scores(scalar_scaled, bark_scores, combined_dist, medoid)
        threshold = max(1e-9, float(np.percentile(combined_dist[combined_dist > 0], 2)) if np.any(combined_dist > 0) else 1e-9)
        qc_rows = stereo_imbalance_qc(group)
        qc_by_id = {str(row["mix_id"]): row for row in qc_rows}
        qc_rows_all.extend(qc_rows)

        target_raw = candidate_targets.get(str(song), "all_valid")
        target = len(group) if target_raw == "all_valid" else int(target_raw)
        if target >= len(group):
            pool_indices = list(range(len(group)))
            selection_distances = [0.0 if i == medoid else float(np.min(combined_dist[i, [medoid]])) for i in pool_indices]
            notes = ["all retained valid mixes included"] * len(pool_indices)
            method_name = "all_valid_retained"
        else:
            pool_indices, selection_distances, notes = farthest_point_pool(combined_dist, target, medoid, near_pairs, ids)
            method_name = "farthest_point_acoustic"

        sensitivity_pools = {
            "farthest_point_acoustic": pool_indices,
            "clustering_k_medoids": greedy_kmedoids_pool(combined_dist, min(target, len(group)), medoid),
            "rms_excluded_pool": farthest_point_pool(rms_excluded_dist, min(target, len(group)), medoid, near_pairs, ids)[0],
            "manhattan_distance_pool": farthest_point_pool(manhattan_dist, min(target, len(group)), medoid, near_pairs, ids)[0],
        }
        inclusion_counts = {label: 0 for label in labels}
        for method, indices in sensitivity_pools.items():
            selected_names = [labels[i] for i in indices]
            mn, mean = _pool_pair_stats(indices, combined_dist)
            for name in selected_names:
                inclusion_counts[name] += 1
            sensitivity_rows.append({
                "artist": artist,
                "song": song,
                "method": method,
                "candidate_count": len(indices),
                "original_mix_names": "|".join(selected_names),
                "mix_ids": "|".join(ids[i] for i in indices),
                "minimum_pairwise_distance": mn,
                "mean_pairwise_distance": mean,
                "pool_stability_against_primary": len(set(indices) & set(pool_indices)) / max(1, len(set(pool_indices))),
            })

        for params, dest in ((scalar_params, scalar_param_rows), (bark_params, bark_param_rows)):
            for row in params:
                row.update({"artist": artist, "song": song})
                dest.append(row)
        for pc_idx, ratio in enumerate(pca.explained_variance_ratio_, 1):
            pca_var_rows.append({
                "artist": artist,
                "song": song,
                "component": f"bark_pc_{pc_idx:02d}",
                "explained_variance_ratio": ratio,
                "cumulative_explained_variance": np.sum(pca.explained_variance_ratio_[:pc_idx]),
                "retained": pc_idx <= retained,
            })
        nonconstant_cols = [col for col, var in zip(BARK_COLUMNS, np.var(bark_scaled, axis=0)) if var > EPS]
        for pc_idx in range(pca.components_.shape[0]):
            for col, loading in zip(nonconstant_cols, pca.components_[pc_idx]):
                pca_loading_rows.append({"artist": artist, "song": song, "component": f"bark_pc_{pc_idx + 1:02d}", "feature": col, "loading": loading, "retained": pc_idx < retained})
        for i, mix_id in enumerate(ids):
            row_base = {col: group.loc[i, col] for col in group.columns}
            proc = dict(row_base)
            proc.update({
                "distance_from_medoid": medoid_dist[i],
                "nearest_neighbour_distance": nearest_dist[i],
                "acoustic_outlier_score": outlier_score[i],
                "stereo_imbalance_qc_only": group.loc[i, "stereo_imbalance"],
                "stereo_imbalance_qc_flag": qc_by_id[mix_id]["qc_flag"],
                "candidate_pool_selected": i in pool_indices,
            })
            for j, col in enumerate(V2_SCALARS):
                proc[f"scaled_{col}"] = scalar_scaled[i, j]
                proc[f"combined_scalar_{col}"] = scalar_weighted[i, j]
            for j in range(retained):
                proc[f"bark_pc_{j + 1:02d}"] = bark_scores[i, j]
                proc[f"combined_bark_pc_{j + 1:02d}"] = bark_weighted[i, j]
            processed_rows.append(proc)
            score = {"artist": artist, "song": song, "original_dataset_filename": group.loc[i, "original_dataset_filename"], "original_mix_name": labels[i], "mix_id": mix_id}
            for j in range(retained):
                score[f"bark_pc_{j + 1:02d}"] = bark_scores[i, j]
            pca_score_rows.append(score)
        for i, j in itertools.combinations(range(len(ids)), 2):
            near = frozenset([ids[i], ids[j]]) in near_pairs or combined_dist[i, j] <= threshold
            pair_rows.append({
                "artist": artist,
                "song": song,
                "mix_i_original_name": labels[i],
                "mix_j_original_name": labels[j],
                "mix_i_id": ids[i],
                "mix_j_id": ids[j],
                "combined_euclidean_distance": combined_dist[i, j],
                "scalar_only_distance": scalar_dist[i, j],
                "bark_only_distance": bark_dist[i, j],
                "rms_excluded_distance": rms_excluded_dist[i, j],
                "combined_manhattan_distance": manhattan_dist[i, j],
                "near_duplicate_flag": near,
            })
        pool_order = {idx: order for order, idx in enumerate(pool_indices, 1)}
        pool_selection_distance = {idx: selection_distances[pos] for pos, idx in enumerate(pool_indices)}
        pool_selection_notes = {idx: notes[pos] for pos, idx in enumerate(pool_indices)}
        for idx in pool_indices:
            row = group.loc[idx]
            mix_id = ids[idx]
            qc = qc_by_id[mix_id]
            status = rating_status.get(mix_id, "not_yet_evaluated")
            manual = bool(qc["qc_flag"])
            pool_rows.append({
                "artist": artist,
                "song": song,
                "original_mix_name": labels[idx],
                "original_dataset_filename": row["original_dataset_filename"],
                "mix_id": mix_id,
                "institution_code": row["institution_code"],
                "pool_rank": pool_order[idx],
                "pool_selection_order": pool_order[idx],
                "pool_selection_method": method_name,
                "distance_to_existing_pool_at_selection": pool_selection_distance[idx],
                "distance_from_medoid": medoid_dist[idx],
                "nearest_neighbour_distance": nearest_dist[idx],
                "acoustic_outlier_score": outlier_score[idx],
                "stereo_imbalance": row["stereo_imbalance"],
                "stereo_imbalance_qc_flag": qc["qc_flag"],
                "rating_status": status,
                "technical_qc_status": "review_required" if manual else "ok",
                "manual_review_required": manual,
                "selection_notes": pool_selection_notes[idx],
            })
            preview_path, sha = _write_preview(row, config, previews)
            preview_files.append(preview_path)
            preview_rows.append({
                "artist": artist,
                "song": song,
                "original_mix_name": labels[idx],
                "original_dataset_filename": row["original_dataset_filename"],
                "mix_id": mix_id,
                "source_path": row["source_path"],
                "preview_path": str(preview_path.relative_to(previews)),
                "approved_aligned_start_seconds": row["approved_aligned_start_seconds"],
                "approved_aligned_end_seconds": row["approved_aligned_end_seconds"],
                "actual_source_start_seconds": row["actual_source_start_seconds"],
                "actual_source_end_seconds": row["actual_source_end_seconds"],
                "acoustic_pool_rank": pool_order[idx],
                "stereo_imbalance_qc_flag": qc["qc_flag"],
                "rating_status": status,
                "preview_loudness_policy": "raw level with review fade; no loudness normalisation, limiting or compression",
                "sha256_hash": sha,
            })

        mn, mean = _pool_pair_stats(pool_indices, combined_dist)
        flags_in_pool = sum(bool(qc_by_id[ids[i]]["qc_flag"]) for i in pool_indices)
        unrated_in_pool = sum(rating_status.get(ids[i], "not_yet_evaluated") == "not_yet_evaluated" for i in pool_indices)
        summary_rows.append({
            "artist": artist,
            "song": song,
            "retained_mix_count": len(group),
            "candidate_pool_target": target_raw,
            "candidate_pool_actual": len(pool_indices),
            "bark_pc_count": retained,
            "bark_variance_explained": np.sum(pca.explained_variance_ratio_[:retained]),
            "medoid_original_name": labels[medoid],
            "minimum_pairwise_distance_within_pool": mn,
            "mean_pairwise_distance_within_pool": mean,
            "stereo_imbalance_flags_in_pool": flags_in_pool,
            "unrated_mixes_in_pool": unrated_in_pool,
            "notes": "Candidate pool only; no preference ratings used for selection.",
        })
        song_summaries.append(V2SongSummary(str(artist), str(song), len(group), str(target_raw), len(pool_indices), retained, float(np.sum(pca.explained_variance_ratio_[:retained])), labels[medoid], mn, mean, flags_in_pool, unrated_in_pool))
        proof_rows.append({
            "artist": artist,
            "song": song,
            "diversity_scalar_features": "|".join(V2_SCALARS),
            "qc_only_features": "|".join(QC_ONLY_FEATURES),
            "combined_coordinate_count": combined.shape[1],
            "contains_stereo_imbalance": False,
            "assertion": "passed",
        })
        _save_figures(diagnostics, str(song), labels, combined, combined_dist, scalar_scaled, bark_raw, medoid_dist, nearest_dist, outlier_score, qc_rows, pool_indices, inclusion_counts, old_selected.get(str(song), set()))

    max_pcs = max(s.bark_components for s in song_summaries)
    processed_columns = (
        list(raw.columns)
        + ["distance_from_medoid", "nearest_neighbour_distance", "acoustic_outlier_score", "stereo_imbalance_qc_only", "stereo_imbalance_qc_flag", "candidate_pool_selected"]
        + [f"scaled_{c}" for c in V2_SCALARS]
        + [f"combined_scalar_{c}" for c in V2_SCALARS]
        + [f"bark_pc_{i:02d}" for i in range(1, max_pcs + 1)]
        + [f"combined_bark_pc_{i:02d}" for i in range(1, max_pcs + 1)]
    )
    processed_path = tables / "processed_features_v2.csv"
    _write_csv(processed_path, processed_rows, processed_columns)
    _write_csv(tables / "scalar_preprocessing_parameters_v2.csv", scalar_param_rows, ["artist", "song", "feature", "median", "q25", "q75", "iqr", "near_zero_iqr", "retained", "scale_formula"])
    _write_csv(tables / "bark_preprocessing_parameters_v2.csv", bark_param_rows, ["artist", "song", "feature", "median", "q25", "q75", "iqr", "near_zero_iqr", "retained", "scale_formula"])
    _write_csv(tables / "bark_pca_explained_variance_v2.csv", pca_var_rows, ["artist", "song", "component", "explained_variance_ratio", "cumulative_explained_variance", "retained"])
    _write_csv(tables / "bark_pca_loadings_v2.csv", pca_loading_rows, ["artist", "song", "component", "feature", "loading", "retained"])
    _write_csv(tables / "bark_pca_scores_v2.csv", pca_score_rows, ["artist", "song", "original_dataset_filename", "original_mix_name", "mix_id"] + [f"bark_pc_{i:02d}" for i in range(1, max_pcs + 1)])
    _write_csv(tables / "pairwise_distances_v2.csv", pair_rows, ["artist", "song", "mix_i_original_name", "mix_j_original_name", "mix_i_id", "mix_j_id", "combined_euclidean_distance", "scalar_only_distance", "bark_only_distance", "rms_excluded_distance", "combined_manhattan_distance", "near_duplicate_flag"])
    candidate_path = tables / "acoustic_candidate_pool.csv"
    _write_csv(candidate_path, pool_rows, ["artist", "song", "original_mix_name", "original_dataset_filename", "mix_id", "institution_code", "pool_rank", "pool_selection_order", "pool_selection_method", "distance_to_existing_pool_at_selection", "distance_from_medoid", "nearest_neighbour_distance", "acoustic_outlier_score", "stereo_imbalance", "stereo_imbalance_qc_flag", "rating_status", "technical_qc_status", "manual_review_required", "selection_notes"])
    _write_csv(tables / "acoustic_candidate_pool_summary.csv", summary_rows, ["artist", "song", "retained_mix_count", "candidate_pool_target", "candidate_pool_actual", "bark_pc_count", "bark_variance_explained", "medoid_original_name", "minimum_pairwise_distance_within_pool", "mean_pairwise_distance_within_pool", "stereo_imbalance_flags_in_pool", "unrated_mixes_in_pool", "notes"])
    _write_csv(tables / "method_sensitivity_comparison_v2.csv", sensitivity_rows, ["artist", "song", "method", "candidate_count", "original_mix_names", "mix_ids", "minimum_pairwise_distance", "mean_pairwise_distance", "pool_stability_against_primary"])
    _write_csv(tables / "stereo_imbalance_qc.csv", qc_rows_all, ["artist", "song", "original_mix_name", "original_dataset_filename", "mix_id", "stereo_imbalance", "absolute_stereo_imbalance", "within_song_median_absolute_stereo_imbalance", "within_song_robust_scale", "robust_qc_score", "qc_flag", "qc_reason", "review_required", "review_priority"])
    manifest_path = tables / "candidate_pool_preview_manifest.csv"
    _write_csv(manifest_path, preview_rows, ["artist", "song", "original_mix_name", "original_dataset_filename", "mix_id", "source_path", "preview_path", "approved_aligned_start_seconds", "approved_aligned_end_seconds", "actual_source_start_seconds", "actual_source_end_seconds", "acoustic_pool_rank", "stereo_imbalance_qc_flag", "rating_status", "preview_loudness_policy", "sha256_hash"])
    _write_csv(validation / "diversity_feature_assertions.csv", proof_rows, ["artist", "song", "diversity_scalar_features", "qc_only_features", "combined_coordinate_count", "contains_stereo_imbalance", "assertion"])

    root.joinpath("README.md").write_text(
        "\n".join([
            "# Stage 4 v2 Acoustic Candidate Pool",
            "",
            "This is the corrected acoustic candidate-pool stage.",
            "",
            "- Stereo imbalance is retained only as a QC feature.",
            "- Brecht preference ratings have not been used for selection.",
            "- No final mixes or final stimuli have been selected.",
            "- Outputs are awaiting Phase 2 ratings integration and supervisor review.",
            "- The superseded v1 method remains in `../04_mix_selection/`.",
            "",
        ]),
        encoding="utf-8",
    )
    _write_reports(reports, song_summaries, pool_rows, qc_rows_all, old_selected, preview_rows)
    return MixSelectionV2Result(output_root, candidate_path, reports / "acoustic_selection_v2_report.md", manifest_path, previews, song_summaries, preview_files)


def _write_reports(
    reports: Path,
    summaries: Sequence[V2SongSummary],
    pool_rows: Sequence[dict[str, object]],
    qc_rows: Sequence[dict[str, object]],
    old_selected: dict[str, set[str]],
    preview_rows: Sequence[dict[str, object]],
) -> None:
    report_lines = [
        "# Acoustic Selection v2 Report",
        "",
        "Stereo imbalance was removed from the acoustic-diversity distance after supervisor feedback. The concern is that a signed left/right imbalance descriptor, originally used in Diff-MST as part of a minimised reference-matching loss, can be rewarded when the dissertation pipeline maximises feature-space diversity.",
        "",
        "## Revised Feature Set",
        "",
        "- Scalar diversity block: `rms_mean`, `crest_factor_mean`, `stereo_width`.",
        "- Spectral diversity block: `bark_mid_01` through `bark_mid_24`, and `bark_side_01` through `bark_side_24`.",
        "- QC-only feature: `stereo_imbalance`.",
        "- No Brecht preference ratings were used in this phase.",
        "",
        "## Transformation",
        "",
        "Within each song, scalar and Bark dimensions are robust-scaled as `(x - median) / IQR`, with zero or near-zero IQR dimensions set to zero. PCA is fitted only to the robust-scaled Bark block, retaining the minimum number of components explaining at least 95% cumulative variance. The scalar block and retained Bark-PC block are each divided by `sqrt(mean(row_squared_norm))` before concatenation, giving equal expected squared contribution to the combined acoustic distance.",
        "",
        "## Stereo-Imbalance Exclusion Proof",
        "",
        "Automated assertions verified that `stereo_imbalance` is absent from the v2 scalar diversity list, combined coordinate names, and all distance matrices. The proof table is `tests_and_validation/diversity_feature_assertions.csv`.",
        "",
        "## Song Summaries",
        "",
        "| Song | Retained | Pool | Bark PCs | Variance | Medoid | Min pool distance | Mean pool distance | SI flags in pool | Unrated in pool |",
        "| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for s in summaries:
        report_lines.append(f"| {s.song} | {s.retained_count} | {s.candidate_pool_actual} | {s.bark_components} | {s.bark_variance:.3f} | {s.medoid_original_name} | {s.minimum_pairwise_distance:.3f} | {s.mean_pairwise_distance:.3f} | {s.stereo_imbalance_flags} | {s.unrated_mixes} |")
    report_lines.extend(["", "## Candidate Pool Composition", ""])
    for s in summaries:
        names = [str(row["original_mix_name"]) for row in pool_rows if row["song"] == s.song]
        report_lines.append(f"- {s.song}: {', '.join(names)}")
    report_lines.extend(["", "## Stereo-Imbalance QC Flags", ""])
    flagged = [row for row in qc_rows if str(row.get("qc_flag")) == "True" or row.get("qc_flag") is True]
    if flagged:
        for row in flagged:
            report_lines.append(f"- {row['song']} / {row['original_mix_name']}: score {float(row['robust_qc_score']):.2f}; signed imbalance {float(row['stereo_imbalance']):.4f}.")
    else:
        report_lines.append("- No mixes exceeded the robust stereo-imbalance QC threshold.")
    report_lines.extend(["", "## v1 Selection Comparison", ""])
    for s in summaries:
        pool = {str(row["original_mix_name"]) for row in pool_rows if row["song"] == s.song}
        old = old_selected.get(s.song, set())
        retained = sorted(old & pool)
        displaced = sorted(old - pool)
        report_lines.append(f"- {s.song}: v1 retained in v2 pool: {', '.join(retained) if retained else 'none'}; v1 displaced: {', '.join(displaced) if displaced else 'none'}.")
    report_lines.extend([
        "",
        "## Preview Audio",
        "",
        f"- Review previews generated: {len(preview_rows)}.",
        "- Location: `outputs/stimulus_selection/04_mix_selection_v2/candidate_pool_previews/`.",
        "- Policy: raw level with review fade; no loudness normalisation, limiting, or compression.",
        "",
        "## Phase 2 Readiness",
        "",
        "The corrected acoustic candidate pools are ready for Phase 2 preference-rating integration. These pools are not final stimuli and do not encode final six-mix recommendations.",
        "",
    ])
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "acoustic_selection_v2_report.md").write_text("\n".join(report_lines), encoding="utf-8")
    (reports / "v1_to_v2_method_change.md").write_text(
        "\n".join([
            "# v1 to v2 Method Change",
            "",
            "Stage 4 v1 is superseded for scientific selection because stereo imbalance contributed to a maximised diversity distance.",
            "",
            "Stage 4 v2 removes stereo imbalance from robust scaling, combined acoustic coordinates, medoid calculation, distance calculation, candidate ranking, and acoustic outlier scoring. Stereo imbalance remains available as QC-only metadata and is reported in `tables/stereo_imbalance_qc.csv`.",
            "",
            "The v1 folder has been preserved unchanged at `outputs/stimulus_selection/04_mix_selection/`.",
            "",
        ]),
        encoding="utf-8",
    )
