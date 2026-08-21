from __future__ import annotations

"""Phase 2A integration of prior Mix Evaluation Dataset preference ratings."""

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from scipy import stats

from stimulus_selection.naming import get_original_dataset_filename, get_original_mix_name
from stimulus_selection.output_layout import (
    first_existing,
    ratings_integration_diagnostics,
    ratings_integration_reports,
    ratings_integration_root,
    ratings_integration_tables,
    ratings_integration_validation,
)
from stimulus_selection.paths import ensure_output_root
from stimulus_selection.config import SelectionConfig


REQUIRED_EVALUATION_COLUMNS = [
    "evaluation_id",
    "session_id",
    "session_song_id",
    "experiment_id",
    "participant_id",
    "evaluator_institution_code",
    "year",
    "song_id",
    "mix_id",
    "legacy_song_id",
    "legacy_mix_code",
    "mixer_institution_code",
    "preference_score_0_1",
]
EXPECTED_COUNTS = {"Lead Me": 37, "In The Meantime": 36, "Red To Blue": 10, "Pouring Room": 9}


@dataclass(frozen=True)
class RatingsIntegrationResult:
    output_root: Path
    report_path: Path
    coverage_by_song_path: Path
    evaluation_rows: int
    retained_mixes: int
    rated_retained_mixes: int
    unrated_retained_mixes: int


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


def _load_raw_config(config_path: str | Path) -> dict[str, object]:
    raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    cfg = raw.get("ratings_integration")
    if not isinstance(cfg, dict):
        raise ValueError("experimental-design/stimulus-selection/config/stimulus_selection.yaml is missing ratings_integration.")
    return cfg


def load_evaluations(path: Path, rating_column: str = "preference_score_0_1") -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = [col for col in REQUIRED_EVALUATION_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Evaluations file is missing required columns: {missing}")
    df[f"{rating_column}_raw"] = df[rating_column]
    df[rating_column] = pd.to_numeric(df[rating_column], errors="coerce")
    valid = df[rating_column].notna()
    if not df.loc[valid, rating_column].between(0.0, 1.0).all():
        raise ValueError("Ratings are outside the expected 0-1 range.")
    return df


def confidence_interval_95(values: np.ndarray) -> tuple[float | None, float | None, str]:
    values = np.asarray(values, dtype=np.float64)
    values = values[np.isfinite(values)]
    if values.size < 2:
        return None, None, "unavailable_n_less_than_2"
    mean = float(np.mean(values))
    sem = float(stats.sem(values))
    margin = float(stats.t.ppf(0.975, values.size - 1) * sem)
    return mean - margin, mean + margin, "student_t"


def aggregate_mix_ratings(eval_rows: pd.DataFrame, rating_column: str, warning_threshold: int) -> dict[str, object]:
    all_values = eval_rows[rating_column].to_numpy(dtype=np.float64)
    values = all_values[np.isfinite(all_values)]
    n = int(values.size)
    missing = int(all_values.size - n)
    if n == 0:
        return {
            "rating_count": 0,
            "unique_participant_count": 0,
            "unique_session_count": 0,
            "unique_experiment_count": 0,
            "evaluator_institution_count": 0,
            "evaluator_institution_codes": "",
            "years": "",
            "mean_preference": "",
            "median_preference": "",
            "standard_deviation": "",
            "variance": "",
            "standard_error": "",
            "percentile_25": "",
            "percentile_75": "",
            "interquartile_range": "",
            "minimum": "",
            "maximum": "",
            "range": "",
            "confidence_interval_95_lower": "",
            "confidence_interval_95_upper": "",
            "confidence_interval_method": "unavailable_unrated",
            "missing_rating_count": missing if len(eval_rows) else 0,
            "low_count_warning": True,
            "aggregation_status": "unrated",
            "notes": "No prior ratings found for this retained mix.",
        }
    q25, q75 = np.percentile(values, [25, 75])
    ci_low, ci_high, ci_method = confidence_interval_95(values)
    sd = float(np.std(values, ddof=1)) if n > 1 else ""
    var = float(np.var(values, ddof=1)) if n > 1 else ""
    se = float(stats.sem(values)) if n > 1 else ""
    return {
        "rating_count": n,
        "unique_participant_count": int(eval_rows["participant_id"].nunique()),
        "unique_session_count": int(eval_rows["session_id"].nunique()),
        "unique_experiment_count": int(eval_rows["experiment_id"].nunique()),
        "evaluator_institution_count": int(eval_rows["evaluator_institution_code"].replace("", np.nan).nunique()),
        "evaluator_institution_codes": "|".join(sorted(v for v in eval_rows["evaluator_institution_code"].unique() if v)),
        "years": "|".join(sorted(v for v in eval_rows["year"].unique() if v)),
        "mean_preference": float(np.mean(values)),
        "median_preference": float(np.median(values)),
        "standard_deviation": sd,
        "variance": var,
        "standard_error": se,
        "percentile_25": float(q25),
        "percentile_75": float(q75),
        "interquartile_range": float(q75 - q25),
        "minimum": float(np.min(values)),
        "maximum": float(np.max(values)),
        "range": float(np.max(values) - np.min(values)),
        "confidence_interval_95_lower": ci_low,
        "confidence_interval_95_upper": ci_high,
        "confidence_interval_method": ci_method,
        "missing_rating_count": missing,
        "low_count_warning": n < warning_threshold,
        "aggregation_status": "ok" if n >= warning_threshold else "low_count",
        "notes": "All available ratings included.",
    }


def within_song_descriptors(summary: pd.DataFrame) -> pd.DataFrame:
    out = summary.copy()
    out["within_song_mean_rank"] = ""
    out["within_song_percentile_rank"] = ""
    out["within_song_z_score"] = ""
    out["within_song_robust_z_score"] = ""
    out["mean_centered_rating_within_song"] = ""
    out["uncertainty_weight"] = ""
    for song, idx in out.groupby("song").groups.items():
        rated_idx = [i for i in idx if str(out.loc[i, "aggregation_status"]) != "unrated"]
        if not rated_idx:
            continue
        means = out.loc[rated_idx, "mean_preference"].astype(float)
        ranks = means.rank(method="average", ascending=True)
        out.loc[rated_idx, "within_song_mean_rank"] = ranks
        out.loc[rated_idx, "within_song_percentile_rank"] = means.rank(method="average", pct=True)
        sd = float(means.std(ddof=1)) if len(means) > 1 else 0.0
        centre = float(means.mean())
        out.loc[rated_idx, "mean_centered_rating_within_song"] = means - centre
        if sd > 0:
            out.loc[rated_idx, "within_song_z_score"] = (means - centre) / sd
        med = float(means.median())
        mad = float(np.median(np.abs(means - med)))
        if mad > 0:
            out.loc[rated_idx, "within_song_robust_z_score"] = (means - med) / (1.4826 * mad)
        counts = out.loc[rated_idx, "rating_count"].astype(float)
        se = pd.to_numeric(out.loc[rated_idx, "standard_error"], errors="coerce")
        weight = counts / counts.max()
        valid_se = se.notna() & (se > 0)
        weight.loc[valid_se] = 1.0 / se.loc[valid_se]
        if weight.max() > 0:
            weight = weight / weight.max()
        out.loc[rated_idx, "uncertainty_weight"] = weight
    return out


def _source_profile(df: pd.DataFrame, schema_text: str, rating_column: str) -> list[dict[str, object]]:
    interpretations = {
        "preference_score_0_1": "Normalized preference/rating score on a 0-1 scale.",
        "mix_id": "Canonical mix join key.",
        "participant_id": "Anonymized participant identifier.",
        "session_id": "Original XML session identifier.",
        "session_song_id": "Song occurrence within session.",
        "experiment_id": "Listening-test experiment batch.",
        "evaluator_institution_code": "Institution that conducted evaluation.",
        "year": "Session/evaluation year when known.",
        "song_id": "Canonical song identifier.",
        "legacy_song_id": "Original song identifier.",
        "legacy_mix_code": "Original mix code.",
        "mixer_institution_code": "Inferred institution/system code of mix.",
    }
    rows = []
    for col in df.columns:
        series = df[col]
        numeric = pd.to_numeric(series, errors="coerce")
        missing = series.isna() | (series.astype(str) == "")
        is_numeric = numeric.notna().any()
        examples = "|".join(str(v) for v in series[~missing].drop_duplicates().head(3).tolist())
        rows.append({
            "column_name": col,
            "dtype": str(series.dtype),
            "non_null_count": int((~missing).sum()),
            "null_count": int(missing.sum()),
            "unique_count": int(series.nunique(dropna=False)),
            "minimum": float(numeric.min(skipna=True)) if is_numeric else "",
            "maximum": float(numeric.max(skipna=True)) if is_numeric else "",
            "example_values": examples,
            "interpretation": interpretations.get(col, "See SCHEMA.md." if col in schema_text else ""),
            "used_in_phase2a": col in REQUIRED_EVALUATION_COLUMNS or col == rating_column,
            "notes": "canonical rating column" if col == rating_column else "",
        })
    return rows


def _plot_bar(path: Path, labels: list[str], values: list[float], title: str, ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(max(8, len(labels) * 0.28), 4))
    plt.bar(range(len(labels)), values)
    plt.xticks(range(len(labels)), labels, rotation=90, fontsize=6)
    plt.title(title)
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def _write_figures(diag: Path, summary: pd.DataFrame, coverage: pd.DataFrame, eval_retained: pd.DataFrame, acoustic: pd.DataFrame) -> None:
    for song, song_summary in summary.groupby("song", sort=True):
        out = diag / re_slug(song)
        labels = song_summary["original_mix_name"].tolist()
        mean_vals = pd.to_numeric(song_summary["mean_preference"], errors="coerce")
        ci_low = pd.to_numeric(song_summary["confidence_interval_95_lower"], errors="coerce")
        ci_high = pd.to_numeric(song_summary["confidence_interval_95_upper"], errors="coerce")
        errors = np.vstack([(mean_vals - ci_low).fillna(0), (ci_high - mean_vals).fillna(0)])
        out.mkdir(parents=True, exist_ok=True)
        plt.figure(figsize=(max(8, len(labels) * 0.28), 4))
        plt.bar(range(len(labels)), mean_vals.fillna(0))
        plt.errorbar(range(len(labels)), mean_vals.fillna(0), yerr=errors, fmt="none", color="black", linewidth=0.8)
        plt.xticks(range(len(labels)), labels, rotation=90, fontsize=6)
        plt.ylim(0, 1)
        plt.title("Mean preference by mix with 95% CI")
        plt.tight_layout()
        plt.savefig(out / "mean_preference_with_95ci.png", dpi=160)
        plt.close()
        _plot_bar(out / "median_preference.png", labels, pd.to_numeric(song_summary["median_preference"], errors="coerce").fillna(0).tolist(), "Median preference by mix", "median")
        _plot_bar(out / "rating_count_by_mix.png", labels, song_summary["rating_count"].astype(int).tolist(), "Rating count by mix", "ratings")
        plt.figure(figsize=(6, 4))
        plt.scatter(song_summary["rating_count"].astype(int), mean_vals)
        plt.xlabel("rating count")
        plt.ylabel("mean preference")
        plt.title("Mean preference versus rating count")
        plt.tight_layout()
        plt.savefig(out / "mean_preference_vs_rating_count.png", dpi=160)
        plt.close()
        merged = song_summary.merge(acoustic[["mix_id", "distance_from_medoid", "pool_rank", "candidate_pool_selected"]], on="mix_id", how="left")
        plt.figure(figsize=(6, 4))
        plt.scatter(pd.to_numeric(merged["distance_from_medoid"], errors="coerce"), pd.to_numeric(merged["mean_preference"], errors="coerce"), c=merged["candidate_pool_selected"].map({True: "#1f77b4", False: "#aaaaaa"}).fillna("#aaaaaa"))
        plt.xlabel("corrected acoustic distance from medoid")
        plt.ylabel("mean preference")
        plt.title("Mean preference versus acoustic distance")
        plt.tight_layout()
        plt.savefig(out / "mean_preference_vs_acoustic_medoid_distance.png", dpi=160)
        plt.close()
        pool_rank = pd.to_numeric(merged["pool_rank"], errors="coerce")
        plt.figure(figsize=(6, 4))
        plt.scatter(pool_rank, pd.to_numeric(merged["mean_preference"], errors="coerce"))
        plt.xlabel("acoustic pool rank")
        plt.ylabel("mean preference")
        plt.title("Mean preference versus acoustic pool rank")
        plt.tight_layout()
        plt.savefig(out / "mean_preference_vs_acoustic_pool_rank.png", dpi=160)
        plt.close()
        comp = eval_retained[eval_retained["song"] == song].pivot_table(index="legacy_mix_code", columns="evaluator_institution_code", values="evaluation_id", aggfunc="count", fill_value=0)
        if not comp.empty:
            comp.plot(kind="bar", stacked=True, figsize=(max(8, comp.shape[0] * 0.28), 4))
            plt.title("Evaluator-institution composition by mix")
            plt.ylabel("rating rows")
            plt.tight_layout()
            plt.savefig(out / "evaluator_institution_composition_by_mix.png", dpi=160)
            plt.close()
        _plot_bar(out / "candidate_pool_highlight.png", labels, [1.0 if v else 0.0 for v in song_summary["selected_in_acoustic_pool_v2"]], "Candidate-pool mixes highlighted", "in pool")
        low_or_unrated = (song_summary["low_count_warning"].astype(str) == "True") | (song_summary["rating_count"].astype(int) == 0)
        _plot_bar(out / "unrated_and_low_count_highlight.png", labels, [1.0 if v else 0.0 for v in low_or_unrated], "Unrated and low-count mixes", "flag")


def re_slug(text: str) -> str:
    return "".join(ch for ch in text if ch.isalnum())


def run_ratings_integration(config: SelectionConfig, config_path: str | Path) -> RatingsIntegrationResult:
    cfg = _load_raw_config(config_path)
    rating_column = str(cfg.get("rating_column", "preference_score_0_1"))
    warning_threshold = int(cfg.get("minimum_rating_count_warning", 5))
    source = cfg.get("canonical_source", {})
    evaluations_path = Path(str(source.get("evaluations_csv", config.relationship_tables_root / "data" / "evaluations.csv")))
    schema_path = Path(str(source.get("schema_md", config.relationship_tables_root / "SCHEMA.md")))
    evaluations = load_evaluations(evaluations_path, rating_column)
    schema_text = schema_path.read_text(encoding="utf-8", errors="replace") if schema_path.exists() else ""
    output_root = ensure_output_root(config)
    raw_path = first_existing(output_root, "03_feature_extraction/tables/raw_diffmst_features.csv", "raw_diffmst_features.csv")
    pool_path = first_existing(output_root, "04_mix_selection_v2/tables/acoustic_candidate_pool.csv")
    processed_v2_path = first_existing(output_root, "04_mix_selection_v2/tables/processed_features_v2.csv")
    retained = pd.read_csv(raw_path, dtype=str, keep_default_na=False)
    retained = retained[retained["feature_extraction_status"] == "ok"].copy()
    retained["original_dataset_filename"] = retained["source_path"].map(get_original_dataset_filename)
    retained["original_mix_name"] = retained["source_path"].map(get_original_mix_name)
    retained_counts = retained.groupby("song").size().to_dict()
    expected_counts = cfg.get("expected_retained_counts", EXPECTED_COUNTS)
    if expected_counts:
        expected_counts = {str(k): int(v) for k, v in dict(expected_counts).items()}
        if retained_counts != expected_counts:
            raise ValueError(f"Unexpected retained rows by selected song; got {retained_counts}; expected {expected_counts}.")
    if retained["mix_id"].duplicated().any():
        raise ValueError("Duplicate retained mix_id rows found.")
    pool = pd.read_csv(pool_path, dtype=str, keep_default_na=False)
    processed_v2 = pd.read_csv(processed_v2_path, dtype=str, keep_default_na=False)
    pool_by_mix = pool.set_index("mix_id").to_dict("index")
    eval_retained = evaluations[evaluations["mix_id"].isin(set(retained["mix_id"]))].copy()
    if eval_retained.groupby("evaluation_id")["mix_id"].nunique().gt(1).any():
        raise ValueError("One evaluation record maps ambiguously to more than one retained mix.")

    tables = ratings_integration_tables(output_root)
    reports = ratings_integration_reports(output_root)
    diagnostics = ratings_integration_diagnostics(output_root)
    validation = ratings_integration_validation(output_root)
    root = ratings_integration_root(output_root)
    for folder in (tables, reports, diagnostics, validation):
        folder.mkdir(parents=True, exist_ok=True)

    _write_csv(tables / "ratings_source_profile.csv", _source_profile(evaluations, schema_text, rating_column), ["column_name", "dtype", "non_null_count", "null_count", "unique_count", "minimum", "maximum", "example_values", "interpretation", "used_in_phase2a", "notes"])

    grouped = {mix_id: group for mix_id, group in eval_retained.groupby("mix_id", sort=False)}
    coverage_rows = []
    summary_rows = []
    self_rows = []
    for _, row in retained.sort_values(["artist", "song", "original_mix_name"]).iterrows():
        mix_id = row["mix_id"]
        eval_rows = grouped.get(mix_id, evaluations.iloc[0:0])
        in_pool = mix_id in pool_by_mix
        coverage_rows.append({
            "artist": row["artist"],
            "song": row["song"],
            "song_id": row["song_id"],
            "original_mix_name": row["original_mix_name"],
            "original_dataset_filename": row["original_dataset_filename"],
            "mix_id": mix_id,
            "institution_code": row["institution_code"],
            "retained_stage3": True,
            "selected_in_acoustic_pool_v2": in_pool,
            "acoustic_pool_rank": pool_by_mix.get(mix_id, {}).get("pool_rank", ""),
            "rating_available": len(eval_rows) > 0,
            "rating_row_count": len(eval_rows),
            "join_status": "matched_by_mix_id" if len(eval_rows) else "retained_mix_unrated",
            "join_notes": "Canonical mix_id join; no filename or legacy-code fallback used.",
        })
        agg = aggregate_mix_ratings(eval_rows, rating_column, warning_threshold)
        summary = {
            "artist": row["artist"],
            "song": row["song"],
            "song_id": row["song_id"],
            "original_mix_name": row["original_mix_name"],
            "original_dataset_filename": row["original_dataset_filename"],
            "mix_id": mix_id,
            "institution_code": row["institution_code"],
            "selected_in_acoustic_pool_v2": in_pool,
            "acoustic_pool_rank": pool_by_mix.get(mix_id, {}).get("pool_rank", ""),
        }
        summary.update(agg)
        summary_rows.append(summary)
        for _, ev in eval_rows.iterrows():
            self_rows.append({
                "evaluation_id": ev["evaluation_id"],
                "song": row["song"],
                "original_mix_name": row["original_mix_name"],
                "mix_id": mix_id,
                "participant_id": ev["participant_id"],
                "evaluator_institution_code": ev["evaluator_institution_code"],
                "mixer_identity_fields": f"mixer_id={row.get('mixer_id','')}; legacy_mix_code={ev.get('legacy_mix_code','')}; mixer_institution_code={ev.get('mixer_institution_code','')}",
                "self_rating_identifiable": False,
                "self_rating_flag": "",
                "evidence": "No explicit participant-to-mixer identity mapping or creator/evaluator flag found in evaluations.csv, mixes.csv, retained feature table, or SCHEMA.md.",
                "exclusion_feasible": False,
                "notes": "Institution equality alone was not used as self-rating evidence.",
            })

    coverage_df = pd.DataFrame(coverage_rows)
    summary_df = pd.DataFrame(summary_rows)
    if len(coverage_df) != len(retained) or coverage_df["mix_id"].duplicated().any():
        raise ValueError("Coverage table failed retained-mix preservation checks.")
    if not set(pool["mix_id"]).issubset(set(coverage_df["mix_id"])):
        raise ValueError("Some candidate-pool mixes are missing from retained coverage.")
    _write_csv(tables / "retained_mix_rating_coverage.csv", coverage_rows, ["artist", "song", "song_id", "original_mix_name", "original_dataset_filename", "mix_id", "institution_code", "retained_stage3", "selected_in_acoustic_pool_v2", "acoustic_pool_rank", "rating_available", "rating_row_count", "join_status", "join_notes"])
    summary_columns = ["artist", "song", "song_id", "original_mix_name", "original_dataset_filename", "mix_id", "institution_code", "selected_in_acoustic_pool_v2", "acoustic_pool_rank", "rating_count", "unique_participant_count", "unique_session_count", "unique_experiment_count", "evaluator_institution_count", "evaluator_institution_codes", "years", "mean_preference", "median_preference", "standard_deviation", "variance", "standard_error", "percentile_25", "percentile_75", "interquartile_range", "minimum", "maximum", "range", "confidence_interval_95_lower", "confidence_interval_95_upper", "confidence_interval_method", "missing_rating_count", "low_count_warning", "aggregation_status", "notes"]
    _write_csv(tables / "mix_preference_rating_summary.csv", summary_rows, summary_columns)
    _write_csv(tables / "self_rating_inspection.csv", self_rows, ["evaluation_id", "song", "original_mix_name", "mix_id", "participant_id", "evaluator_institution_code", "mixer_identity_fields", "self_rating_identifiable", "self_rating_flag", "evidence", "exclusion_feasible", "notes"])

    within = within_song_descriptors(summary_df)
    within_columns = summary_columns + ["within_song_mean_rank", "within_song_percentile_rank", "within_song_z_score", "within_song_robust_z_score", "mean_centered_rating_within_song", "uncertainty_weight"]
    _write_csv(tables / "mix_preference_rating_summary_within_song.csv", within.to_dict("records"), within_columns)

    coverage_by_song = []
    for song, cov in coverage_df.groupby("song", sort=True):
        mix_ids = set(cov["mix_id"])
        ev = eval_retained[eval_retained["mix_id"].isin(mix_ids)]
        counts = cov["rating_row_count"].astype(int)
        pool_cov = cov[cov["selected_in_acoustic_pool_v2"] == True]  # noqa: E712
        coverage_by_song.append({
            "song": song,
            "retained_mix_count": len(cov),
            "rated_retained_mix_count": int((counts > 0).sum()),
            "unrated_retained_mix_count": int((counts == 0).sum()),
            "acoustic_candidate_pool_size": len(pool_cov),
            "rated_acoustic_pool_count": int((pool_cov["rating_row_count"].astype(int) > 0).sum()),
            "unrated_acoustic_pool_count": int((pool_cov["rating_row_count"].astype(int) == 0).sum()),
            "total_rating_rows": len(ev),
            "rating_count_minimum": int(counts.min()),
            "rating_count_median": float(counts.median()),
            "rating_count_maximum": int(counts.max()),
            "mixes_below_warning_threshold": int((counts < warning_threshold).sum()),
            "evaluator_institutions_represented": "|".join(sorted(v for v in ev["evaluator_institution_code"].unique() if v)),
            "years_represented": "|".join(sorted(v for v in ev["year"].unique() if v)),
            "sessions_represented": int(ev["session_id"].nunique()),
            "experiments_represented": int(ev["experiment_id"].nunique()),
        })
    coverage_path = tables / "rating_coverage_by_song.csv"
    _write_csv(coverage_path, coverage_by_song, ["song", "retained_mix_count", "rated_retained_mix_count", "unrated_retained_mix_count", "acoustic_candidate_pool_size", "rated_acoustic_pool_count", "unrated_acoustic_pool_count", "total_rating_rows", "rating_count_minimum", "rating_count_median", "rating_count_maximum", "mixes_below_warning_threshold", "evaluator_institutions_represented", "years_represented", "sessions_represented", "experiments_represented"])

    warning_rows = []
    for row in summary_rows:
        reasons = []
        if int(row["rating_count"]) == 0:
            reasons.append("unrated")
        if int(row["rating_count"]) < warning_threshold:
            reasons.append(f"rating_count_below_{warning_threshold}")
        if row["confidence_interval_method"] != "student_t":
            reasons.append("confidence_interval_unavailable")
        if int(row["evaluator_institution_count"]) <= 1 and int(row["rating_count"]) > 0:
            reasons.append("narrow_evaluator_coverage")
        if reasons:
            warning_rows.append({**{k: row[k] for k in ["artist", "song", "original_mix_name", "original_dataset_filename", "mix_id", "selected_in_acoustic_pool_v2", "acoustic_pool_rank", "rating_count"]}, "warning_reasons": ";".join(reasons), "action": "retain_and_report"})
    _write_csv(tables / "low_rating_count_warnings.csv", warning_rows, ["artist", "song", "original_mix_name", "original_dataset_filename", "mix_id", "selected_in_acoustic_pool_v2", "acoustic_pool_rank", "rating_count", "warning_reasons", "action"])

    context_rows = []
    for keys, group in eval_retained.groupby(["song_id", "legacy_song_id", "evaluator_institution_code"], sort=True):
        context_rows.append({"context_type": "evaluator_institution", "song_id": keys[0], "legacy_song_id": keys[1], "context_value": keys[2], "rating_count": len(group), "mean_preference": group[rating_column].mean(), "unique_participants": group["participant_id"].nunique(), "unique_sessions": group["session_id"].nunique()})
    for keys, group in eval_retained.groupby(["song_id", "legacy_song_id", "experiment_id"], sort=True):
        context_rows.append({"context_type": "experiment", "song_id": keys[0], "legacy_song_id": keys[1], "context_value": keys[2], "rating_count": len(group), "mean_preference": group[rating_column].mean(), "unique_participants": group["participant_id"].nunique(), "unique_sessions": group["session_id"].nunique()})
    for keys, group in eval_retained.groupby(["song_id", "legacy_song_id", "year"], sort=True):
        context_rows.append({"context_type": "year", "song_id": keys[0], "legacy_song_id": keys[1], "context_value": keys[2] or "unknown", "rating_count": len(group), "mean_preference": group[rating_column].mean(), "unique_participants": group["participant_id"].nunique(), "unique_sessions": group["session_id"].nunique()})
    _write_csv(tables / "evaluator_context_summary.csv", context_rows, ["context_type", "song_id", "legacy_song_id", "context_value", "rating_count", "mean_preference", "unique_participants", "unique_sessions"])

    acoustic = processed_v2[["mix_id", "distance_from_medoid"]].merge(pool[["mix_id", "pool_rank"]], on="mix_id", how="left")
    acoustic["candidate_pool_selected"] = acoustic["pool_rank"].astype(str) != ""
    _write_figures(diagnostics, within, pd.DataFrame(coverage_by_song), eval_retained.merge(retained[["mix_id", "song"]], on="mix_id", how="left"), acoustic)

    validation_rows = [
        {"check": "retained_mix_count", "observed": len(coverage_df), "expected": 92, "passed": len(coverage_df) == 92},
        {"check": "duplicate_retained_mix_rows", "observed": int(coverage_df["mix_id"].duplicated().sum()), "expected": 0, "passed": not coverage_df["mix_id"].duplicated().any()},
        {"check": "rating_range_0_1", "observed": f"{evaluations[rating_column].min()}..{evaluations[rating_column].max()}", "expected": "0..1", "passed": evaluations[rating_column].between(0, 1).all()},
        {"check": "candidate_pool_preserved", "observed": len(pool), "expected": len(pool), "passed": set(pool["mix_id"]).issubset(set(coverage_df["mix_id"]))},
        {"check": "no_self_excluded_summary", "observed": "not_created", "expected": "not_feasible", "passed": True},
    ]
    _write_csv(validation / "ratings_integration_validation.csv", validation_rows, ["check", "observed", "expected", "passed"])
    _write_readme_and_reports(root, reports, evaluations, rating_column, coverage_by_song, summary_rows, warning_rows, context_rows, evaluations_path, schema_path)
    return RatingsIntegrationResult(output_root, reports / "ratings_integration_report.md", coverage_path, len(evaluations), len(coverage_df), int((coverage_df["rating_row_count"].astype(int) > 0).sum()), int((coverage_df["rating_row_count"].astype(int) == 0).sum()))


def _write_readme_and_reports(root: Path, reports: Path, evaluations: pd.DataFrame, rating_column: str, coverage_by_song: list[dict[str, object]], summary_rows: list[dict[str, object]], warning_rows: list[dict[str, object]], context_rows: list[dict[str, object]], evaluations_path: Path, schema_path: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    root.joinpath("README.md").write_text(
        "\n".join([
            "# Phase 2A Ratings Integration",
            "",
            "This stage only aggregates and validates prior Mix Evaluation Dataset ratings.",
            "",
            "- No final mixes have been selected.",
            "- No similar-rating or wide-rating groups have been chosen.",
            "- Corrected acoustic candidate pools remain unchanged.",
            "- Outputs are inputs to Phase 2B rating stratification.",
            "",
        ]),
        encoding="utf-8",
    )
    unrated = [row for row in summary_rows if int(row["rating_count"]) == 0]
    lines = [
        "# Ratings Integration Report",
        "",
        f"Canonical source: `{evaluations_path}`.",
        f"Schema: `{schema_path}`.",
        f"Rating column: `{rating_column}`; observed scale {evaluations[rating_column].min():.3g} to {evaluations[rating_column].max():.3g}.",
        f"Rows: {len(evaluations)}; participants: {evaluations['participant_id'].nunique()}; songs: {evaluations['song_id'].nunique()}; mixes: {evaluations['mix_id'].nunique()}; sessions: {evaluations['session_id'].nunique()}; experiments: {evaluations['experiment_id'].nunique()}.",
        "",
        "## Coverage By Song",
        "",
        "| Song | Retained | Rated | Unrated | Pool | Rated Pool | Rating Rows | Count Range | Institutions | Years |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in coverage_by_song:
        lines.append(f"| {row['song']} | {row['retained_mix_count']} | {row['rated_retained_mix_count']} | {row['unrated_retained_mix_count']} | {row['acoustic_candidate_pool_size']} | {row['rated_acoustic_pool_count']} | {row['total_rating_rows']} | {row['rating_count_minimum']}-{row['rating_count_maximum']} | {row['evaluator_institutions_represented']} | {row['years_represented']} |")
    lines.extend(["", "## Unrated Mixes", ""])
    for row in unrated:
        lines.append(f"- {row['song']} / {row['original_mix_name']} ({row['mix_id']})")
    lines.extend([
        "",
        "## Aggregation Method",
        "",
        "Ratings were aggregated per retained mix using the canonical `mix_id` join key. For rated mixes, the table reports mean, median, standard deviation, variance, standard error, quartiles, IQR, min, max, range, and a 95% Student-t confidence interval where n > 1. Confidence intervals are not fabricated for unrated or single-rating cases.",
        "",
        "## Self-Rating Inspection",
        "",
        "Exact producer/self-ratings could not be identified from the available canonical metadata. The schema and tables expose participant/session/evaluator identifiers and mix/institution codes, but no explicit participant-to-mixer identity mapping or creator/evaluator flag. Institution equality alone was not treated as reliable self-rating evidence. Therefore no self-excluded summary was produced.",
        "",
        "## Heterogeneity And Use",
        "",
        "Ratings are on a common 0-1 scale, but they were collected across different sessions, evaluator institutions, experiments, years, and participant groups. The safest Phase 2B use is within-song stratification. Raw cross-song mean comparisons are not recommended.",
        "",
        "## Warnings",
        "",
        f"Low-count/unrated/narrow-coverage warning rows: {len(warning_rows)}.",
        "",
        "## Readiness",
        "",
        "Phase 2A is ready for Phase 2B rating stratification. No acoustic distances were modified and no final selections were made.",
        "",
    ])
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "ratings_integration_report.md").write_text("\n".join(lines), encoding="utf-8")
    (reports / "ratings_methodology_notes.md").write_text(
        "\n".join([
            "# Ratings Methodology Notes",
            "",
            "Brecht's prior Mix Evaluation Dataset ratings are used as an external second-stage stratification variable, after acoustic candidate pools have been generated without stereo imbalance in the diversity distance.",
            "",
            "The prior ratings are context-free preference ratings from the existing dataset. They are not new study outcomes, not ground-truth quality labels, and not part of the acoustic distance. They are aggregated within song using `mix_id`, preserving unequal rating counts, session/evaluator/year metadata, and uncertainty estimates.",
            "",
            "Phase 2B should use within-song descriptors, ranks, and uncertainty annotations to construct similar-rating and wide-rating comparisons. Cross-song raw mean comparisons should be avoided unless explicitly modelled.",
            "",
            "Exact self-rating exclusion is not feasible from the current canonical metadata because no reliable participant-to-mixer identity mapping or explicit self-rating flag is present.",
            "",
        ]),
        encoding="utf-8",
    )
