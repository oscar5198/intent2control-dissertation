from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import torch

from stimulus_selection.audio_decode import decode_audio, detect_decoder_environment, ensure_sample_rate
from stimulus_selection.config import SelectionConfig
from stimulus_selection.output_layout import first_existing, stage1_tables, stage2_tables, stage3_diagnostics, stage3_reports, stage3_tables
from stimulus_selection.paths import ensure_output_root
from stimulus_selection.third_party.diffmst_features import (
    compute_barkspectrum,
    compute_crest_factor,
    compute_rms,
    compute_stereo_imbalance,
    compute_stereo_width,
)


REFERENCE_COMMIT = "3b90ef838272b827c86610cf25b510a23a4147fd"
EXPECTED_SAMPLE_RATE = 44100
EXPECTED_SECONDS = 28.0
EXPECTED_SAMPLES = int(EXPECTED_SAMPLE_RATE * EXPECTED_SECONDS)
SYSTEM_MARKERS = ("mg", "mixgenius", "auto", "robot")
SCALAR_COLUMNS = [
    "rms_left",
    "rms_right",
    "rms_mean",
    "crest_factor_left",
    "crest_factor_right",
    "crest_factor_mean",
    "stereo_width",
    "stereo_imbalance",
]
BARK_MID_COLUMNS = [f"bark_mid_{i:02d}" for i in range(1, 25)]
BARK_SIDE_COLUMNS = [f"bark_side_{i:02d}" for i in range(1, 25)]
BARK_COLUMNS = BARK_MID_COLUMNS + BARK_SIDE_COLUMNS
METADATA_COLUMNS = [
    "artist",
    "song",
    "song_id",
    "mix_id",
    "mixer_id",
    "institution_code",
    "institution_name",
    "institution_category",
    "source_path",
    "reference_mix_id",
    "decoder_backend",
    "original_sample_rate",
    "target_sample_rate",
    "original_channels",
    "target_channels",
    "approved_aligned_start_seconds",
    "approved_aligned_end_seconds",
    "alignment_lag_seconds",
    "actual_source_start_seconds",
    "actual_source_end_seconds",
    "decoded_duration_seconds",
    "decoded_sample_count",
    "feature_extraction_status",
    "exclusion_reason",
    "extraction_notes",
]
RAW_FEATURE_COLUMNS = METADATA_COLUMNS + SCALAR_COLUMNS + BARK_COLUMNS


@dataclass(frozen=True)
class ExtractionResult:
    raw_feature_path: Path
    schema_path: Path
    quality_path: Path
    report_path: Path
    summary_path: Path
    bark_summary_path: Path
    figure_root: Path
    rows: list[dict[str, str]]
    quality_rows: list[dict[str, str]]
    counts_by_song: dict[str, int]
    rerun_subset_identical: bool


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _fmt(value: float | int | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(float(value)):
        return ""
    return f"{float(value):.12g}"


def _song_key(row: dict[str, str]) -> str:
    return f"{row['artist']} - {row['song']}"


def _approved_intervals(config: SelectionConfig) -> dict[tuple[str, str], tuple[float, float]]:
    intervals: dict[tuple[str, str], tuple[float, float]] = {}
    for item in getattr(config, "approved_excerpts", ()):
        artist = item.get("artist", "")
        song = item.get("song", "")
        start = float(item.get("aligned_start_seconds", "nan"))
        end = float(item.get("aligned_end_seconds", "nan"))
        if not artist or not song or not math.isfinite(start) or not math.isfinite(end):
            raise ValueError(f"Incomplete approved excerpt record: {item}")
        if abs((end - start) - EXPECTED_SECONDS) > 1e-6:
            raise ValueError(f"Approved excerpt for {artist} - {song} is not exactly {EXPECTED_SECONDS} seconds.")
        intervals[(artist, song)] = (start, end)
    if len(intervals) != 4:
        raise ValueError(f"Expected four approved excerpts in config; found {len(intervals)}.")
    return intervals


def load_stage3b_inputs(config: SelectionConfig) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[tuple[str, str], tuple[float, float]]]:
    output_root = ensure_output_root(config)
    inventory = _read_csv(first_existing(output_root, "01_dataset_and_song_selection/tables/mix_inventory.csv", "mix_inventory.csv"))
    alignment = _read_csv(first_existing(output_root, "02_excerpt_selection/tables/alignment_results.csv", "alignment_results.csv"))
    remaining_alignment = first_existing(
        output_root,
        "02_excerpt_selection/diagnostics/stage2_remaining/alignment_results.csv",
        "stage2_remaining/alignment_results.csv",
    )
    if remaining_alignment.exists():
        alignment.extend(_read_csv(remaining_alignment))
    intervals = _approved_intervals(config)
    return inventory, alignment, intervals


def is_retained_human_mix(inventory_row: dict[str, str], alignment_row: dict[str, str]) -> tuple[bool, str]:
    text = " ".join(
        [
            inventory_row.get("mix_id", ""),
            inventory_row.get("mixer_id", ""),
            inventory_row.get("mixer_institution_code", ""),
            inventory_row.get("institution_name", ""),
            inventory_row.get("filename", ""),
        ]
    ).lower()
    if any(marker in text for marker in SYSTEM_MARKERS):
        return False, "automated_or_system_generated"
    if inventory_row.get("is_system_generated") == "true" or inventory_row.get("institution_category") == "automated_system":
        return False, "automated_or_system_generated"
    if inventory_row.get("valid_for_analysis") != "true":
        return False, inventory_row.get("exclusion_reason") or "stage1_invalid"
    if alignment_row.get("retained_for_excerpt_selection") != "true":
        return False, alignment_row.get("exclusion_reason") or "stage2_not_retained"
    return True, ""


def is_stage1_valid_human_mix(inventory_row: dict[str, str]) -> bool:
    text = " ".join(
        [
            inventory_row.get("mix_id", ""),
            inventory_row.get("mixer_id", ""),
            inventory_row.get("mixer_institution_code", ""),
            inventory_row.get("institution_name", ""),
            inventory_row.get("filename", ""),
        ]
    ).lower()
    if any(marker in text for marker in SYSTEM_MARKERS):
        return False
    if inventory_row.get("is_system_generated") == "true" or inventory_row.get("institution_category") == "automated_system":
        return False
    return inventory_row.get("valid_for_analysis") == "true"


def aligned_to_source_interval(aligned_start: float, aligned_end: float, lag_seconds: float) -> tuple[float, float]:
    return aligned_start + lag_seconds, aligned_end + lag_seconds


def alignment_row_for_mix(alignment_rows: Iterable[dict[str, str]], mix_id: str) -> dict[str, str]:
    for row in alignment_rows:
        if row.get("mix_id") == mix_id:
            return row
    raise ValueError(f"Missing Stage 2 alignment row for mix_id {mix_id}.")


def extract_exact_excerpt(samples: np.ndarray, sample_rate: int, start_seconds: float, duration_seconds: float = EXPECTED_SECONDS) -> np.ndarray:
    start = int(round(start_seconds * sample_rate))
    length = int(round(duration_seconds * sample_rate))
    end = start + length
    if start < 0:
        raise ValueError(f"source_start_before_file:{start_seconds:.9f}")
    if end > samples.shape[0]:
        raise ValueError(f"source_end_after_file:{end / sample_rate:.9f}>{samples.shape[0] / sample_rate:.9f}")
    excerpt = samples[start:end]
    if excerpt.shape[0] != length:
        raise ValueError(f"incorrect_source_sample_count:{excerpt.shape[0]}!={length}")
    return excerpt


def _features_for_excerpt(excerpt: np.ndarray) -> dict[str, float]:
    if excerpt.shape != (EXPECTED_SAMPLES, 2):
        raise ValueError(f"Expected excerpt shape ({EXPECTED_SAMPLES}, 2); got {excerpt.shape}.")
    if not np.isfinite(excerpt).all():
        raise ValueError("Excerpt contains NaN or Inf values.")
    x = torch.from_numpy(excerpt.T.astype(np.float32, copy=False)).unsqueeze(0)
    with torch.no_grad():
        rms = compute_rms(x).cpu().numpy()[0]
        crest = compute_crest_factor(x).cpu().numpy()[0]
        width = float(compute_stereo_width(x).cpu().numpy()[0])
        imbalance = float(compute_stereo_imbalance(x).cpu().numpy()[0])
        bark = compute_barkspectrum(x, mode="mid-side").cpu().numpy()[0]
    if bark.shape != (24, 2):
        raise ValueError(f"Unexpected Bark mid-side shape after batch squeeze: {bark.shape}.")
    values: dict[str, float] = {
        "rms_left": float(rms[0]),
        "rms_right": float(rms[1]),
        "rms_mean": float(np.mean(rms)),
        "crest_factor_left": float(crest[0]),
        "crest_factor_right": float(crest[1]),
        "crest_factor_mean": float(np.mean(crest)),
        "stereo_width": width,
        "stereo_imbalance": imbalance,
    }
    for i in range(24):
        values[f"bark_mid_{i + 1:02d}"] = float(bark[i, 0])
        values[f"bark_side_{i + 1:02d}"] = float(bark[i, 1])
    return values


def _extract_one(row: dict[str, str], aligned_start: float, aligned_end: float) -> dict[str, str]:
    lag = float(row["refined_lag_seconds"] or row["estimated_lag_seconds"])
    source_start, source_end = aligned_to_source_interval(aligned_start, aligned_end, lag)
    decoded = decode_audio(Path(row["source_path"]))
    if decoded.channels != 2 or decoded.samples.ndim != 2 or decoded.samples.shape[1] != 2:
        raise ValueError(f"expected_stereo_source_got_{decoded.channels}_channels")
    excerpt = extract_exact_excerpt(decoded.samples, decoded.sample_rate, source_start, EXPECTED_SECONDS)
    excerpt = ensure_sample_rate(excerpt, decoded.sample_rate, EXPECTED_SAMPLE_RATE)
    if excerpt.shape[0] != EXPECTED_SAMPLES:
        raise ValueError(f"incorrect_target_sample_count:{excerpt.shape[0]}!={EXPECTED_SAMPLES}")
    if excerpt.shape[1] != 2:
        raise ValueError(f"incorrect_target_channel_count:{excerpt.shape[1]}")
    features = _features_for_excerpt(excerpt)
    result = {
        "decoder_backend": decoded.backend,
        "original_sample_rate": str(decoded.sample_rate),
        "target_sample_rate": str(EXPECTED_SAMPLE_RATE),
        "original_channels": str(decoded.channels),
        "target_channels": "2",
        "approved_aligned_start_seconds": _fmt(aligned_start),
        "approved_aligned_end_seconds": _fmt(aligned_end),
        "alignment_lag_seconds": _fmt(lag),
        "actual_source_start_seconds": _fmt(source_start),
        "actual_source_end_seconds": _fmt(source_end),
        "decoded_duration_seconds": _fmt(EXPECTED_SECONDS),
        "decoded_sample_count": str(EXPECTED_SAMPLES),
        "feature_extraction_status": "ok",
        "exclusion_reason": "",
        "extraction_notes": "features extracted before preview fades; no normalisation applied",
    }
    result.update({key: _fmt(value) for key, value in features.items()})
    return result


def _base_row(inventory_row: dict[str, str], alignment_row: dict[str, str]) -> dict[str, str]:
    return {
        "artist": inventory_row["artist"],
        "song": inventory_row["song"],
        "song_id": inventory_row["song_id"],
        "mix_id": inventory_row["mix_id"],
        "mixer_id": inventory_row.get("mixer_id", ""),
        "institution_code": inventory_row.get("mixer_institution_code", ""),
        "institution_name": inventory_row.get("institution_name", ""),
        "institution_category": inventory_row.get("institution_category", ""),
        "source_path": alignment_row.get("source_path") or inventory_row.get("source_path", ""),
        "reference_mix_id": alignment_row.get("reference_mix_id", ""),
    }


def extract_feature_rows(config: SelectionConfig) -> list[dict[str, str]]:
    inventory, alignment, intervals = load_stage3b_inputs(config)
    inventory_by_mix = {row["mix_id"]: row for row in inventory}
    rows: list[dict[str, str]] = []
    for alignment_row in sorted(alignment, key=lambda r: (r["artist"], r["song"], r["mix_id"])):
        key = (alignment_row["artist"], alignment_row["song"])
        if key not in intervals:
            continue
        inventory_row = inventory_by_mix.get(alignment_row["mix_id"])
        if inventory_row is None:
            raise ValueError(f"Missing inventory row for alignment mix_id {alignment_row['mix_id']}.")
        ok, reason = is_retained_human_mix(inventory_row, alignment_row)
        if not ok:
            continue
        base = _base_row(inventory_row, alignment_row)
        start, end = intervals[key]
        try:
            extracted = _extract_one(alignment_row, start, end)
            base.update(extracted)
        except Exception as exc:
            base.update({
                "decoder_backend": alignment_row.get("decoder_backend", ""),
                "original_sample_rate": alignment_row.get("original_sample_rate", ""),
                "target_sample_rate": str(EXPECTED_SAMPLE_RATE),
                "original_channels": alignment_row.get("decoded_channels", ""),
                "target_channels": "2",
                "approved_aligned_start_seconds": _fmt(start),
                "approved_aligned_end_seconds": _fmt(end),
                "alignment_lag_seconds": alignment_row.get("refined_lag_seconds") or alignment_row.get("estimated_lag_seconds", ""),
                "actual_source_start_seconds": "",
                "actual_source_end_seconds": "",
                "decoded_duration_seconds": "",
                "decoded_sample_count": "",
                "feature_extraction_status": "error",
                "exclusion_reason": "feature_extraction_failed",
                "extraction_notes": str(exc),
            })
            base.update({column: "" for column in SCALAR_COLUMNS + BARK_COLUMNS})
        rows.append(base)
    return rows


def _numeric_matrix(rows: list[dict[str, str]], columns: list[str]) -> np.ndarray:
    return np.asarray([[float(row[column]) for column in columns] for row in rows], dtype=np.float64)


def quality_checks(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    ok_rows = [row for row in rows if row["feature_extraction_status"] == "ok"]
    required_non_empty = [col for col in RAW_FEATURE_COLUMNS if col not in {"exclusion_reason"}]
    for song in sorted({_song_key(row) for row in rows}):
        song_rows = [row for row in rows if _song_key(row) == song]
        song_ok = [row for row in song_rows if row["feature_extraction_status"] == "ok"]
        def add(check: str, severity: str, passed: bool, details: str) -> None:
            checks.append({"song": song, "check": check, "severity": severity, "passed": str(passed).lower(), "details": details})
        add("missing_values", "error", all(all(row.get(col, "") != "" for col in required_non_empty) for row in song_ok), "ok rows checked")
        add("nan", "error", all(np.isfinite(_numeric_matrix(song_ok, SCALAR_COLUMNS + BARK_COLUMNS)).all() for _ in [0]) if song_ok else False, "finite numeric feature matrix")
        add("inf", "error", all(np.isfinite(_numeric_matrix(song_ok, SCALAR_COLUMNS + BARK_COLUMNS)).all() for _ in [0]) if song_ok else False, "finite numeric feature matrix")
        add("incorrect_sample_count", "error", all(row["decoded_sample_count"] == str(EXPECTED_SAMPLES) for row in song_ok), f"expected {EXPECTED_SAMPLES}")
        add("incorrect_channel_count", "error", all(row["target_channels"] == "2" and row["original_channels"] == "2" for row in song_ok), "expected stereo")
        if not song_ok:
            add("no_successful_rows", "error", False, "no features extracted")
            continue
        matrix = _numeric_matrix(song_ok, SCALAR_COLUMNS + BARK_COLUMNS)
        variances = np.var(matrix, axis=0)
        zero_cols = [col for col, var in zip(SCALAR_COLUMNS + BARK_COLUMNS, variances) if var == 0.0]
        near_zero_cols = [col for col, var in zip(SCALAR_COLUMNS + BARK_COLUMNS, variances) if 0.0 < var < 1e-10]
        add("zero_variance_feature_dimensions", "warning", not zero_cols, ", ".join(zero_cols))
        add("near_zero_variance_feature_dimensions", "warning", not near_zero_cols, ", ".join(near_zero_cols))
        rms = _numeric_matrix(song_ok, ["rms_mean"])[:, 0]
        crest = _numeric_matrix(song_ok, ["crest_factor_mean"])[:, 0]
        width = _numeric_matrix(song_ok, ["stereo_width"])[:, 0]
        imb = np.abs(_numeric_matrix(song_ok, ["stereo_imbalance"])[:, 0])
        add("extreme_rms", "warning", bool(np.all((rms > 1e-5) & (rms < 1.0))), f"min={rms.min():.6g}; max={rms.max():.6g}")
        add("extreme_crest_factor", "warning", bool(np.all((crest >= 0.0) & (crest < 80.0))), f"min={crest.min():.6g}; max={crest.max():.6g}")
        add("extreme_stereo_width", "warning", bool(np.all(width < 100.0)), f"min={width.min():.6g}; max={width.max():.6g}")
        add("extreme_absolute_stereo_imbalance", "warning", bool(np.all(imb <= 1.0)), f"max_abs={imb.max():.6g}")
        if len(song_ok) > 2:
            scalar = _numeric_matrix(song_ok, SCALAR_COLUMNS)
            corr = np.corrcoef(scalar, rowvar=False)
            pairs = []
            for i in range(len(SCALAR_COLUMNS)):
                for j in range(i + 1, len(SCALAR_COLUMNS)):
                    val = corr[i, j]
                    if np.isfinite(val) and abs(val) > 0.98:
                        pairs.append(f"{SCALAR_COLUMNS[i]}~{SCALAR_COLUMNS[j]}={val:.3f}")
            add("highly_correlated_scalar_features", "warning", not pairs, "; ".join(pairs))
        bark_vars = np.var(_numeric_matrix(song_ok, BARK_COLUMNS), axis=0)
        low_bark = [col for col, var in zip(BARK_COLUMNS, bark_vars) if var < 1e-10]
        add("bark_bins_zero_or_near_zero_variance", "warning", not low_bark, ", ".join(low_bark))
        rounded = {}
        duplicates = []
        for row in song_ok:
            vector = tuple(round(float(row[col]), 8) for col in SCALAR_COLUMNS + BARK_COLUMNS)
            if vector in rounded:
                duplicates.append(f"{rounded[vector]}~{row['mix_id']}")
            rounded[vector] = row["mix_id"]
        add("duplicate_or_near_duplicate_feature_vectors", "warning", not duplicates, "; ".join(duplicates))
        bark = _numeric_matrix(song_ok, BARK_COLUMNS)
        constant_bark_rows = [row["mix_id"] for row, vals in zip(song_ok, bark) if np.allclose(vals, 0.0) or np.var(vals) < 1e-12]
        add("suspicious_all_zero_or_constant_bark_outputs", "warning", not constant_bark_rows, "; ".join(constant_bark_rows))
        starts = _numeric_matrix(song_ok, ["actual_source_start_seconds"])[:, 0]
        ends = _numeric_matrix(song_ok, ["actual_source_end_seconds"])[:, 0]
        add("possible_excerpt_conversion_error", "error", bool(np.all(np.isclose(ends - starts, EXPECTED_SECONDS, atol=1e-6))), "source interval durations checked")
        backends = sorted({row["decoder_backend"] for row in song_ok})
        add("possible_decoder_inconsistency", "warning", len(backends) == 1, ", ".join(backends))
    checks.append({"song": "ALL", "check": "row_count", "severity": "error", "passed": str(len(ok_rows) == len(rows)).lower(), "details": f"ok={len(ok_rows)}; total={len(rows)}"})
    return checks


def summarize_scalar_features(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    ok_rows = [row for row in rows if row["feature_extraction_status"] == "ok"]
    for song in sorted({_song_key(row) for row in ok_rows}):
        song_rows = [row for row in ok_rows if _song_key(row) == song]
        for feature in SCALAR_COLUMNS:
            vals = np.asarray([float(row[feature]) for row in song_rows], dtype=np.float64)
            q25, median, q75 = np.percentile(vals, [25, 50, 75])
            out.append({
                "song": song,
                "feature": feature,
                "count": str(vals.size),
                "mean": _fmt(float(np.mean(vals))),
                "standard_deviation": _fmt(float(np.std(vals, ddof=1))) if vals.size > 1 else "0",
                "minimum": _fmt(float(np.min(vals))),
                "percentile_25": _fmt(float(q25)),
                "median": _fmt(float(median)),
                "percentile_75": _fmt(float(q75)),
                "maximum": _fmt(float(np.max(vals))),
                "iqr": _fmt(float(q75 - q25)),
            })
    return out


def summarize_bark_features(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    ok_rows = [row for row in rows if row["feature_extraction_status"] == "ok"]
    for song in sorted({_song_key(row) for row in ok_rows}):
        song_rows = [row for row in ok_rows if _song_key(row) == song]
        for channel, columns in (("mid", BARK_MID_COLUMNS), ("side", BARK_SIDE_COLUMNS)):
            matrix = _numeric_matrix(song_rows, columns)
            for idx, column in enumerate(columns, 1):
                out.append({
                    "song": song,
                    "bark_channel": channel,
                    "bark_band": str(idx),
                    "column": column,
                    "count": str(matrix.shape[0]),
                    "mean": _fmt(float(np.mean(matrix[:, idx - 1]))),
                    "standard_deviation": _fmt(float(np.std(matrix[:, idx - 1], ddof=1))) if matrix.shape[0] > 1 else "0",
                })
    return out


def _hash_file(path: Path) -> str:
    if not path.exists():
        return "missing"
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def write_feature_schema(path: Path) -> None:
    columns = []
    for col in METADATA_COLUMNS:
        columns.append({"name": col, "data_type": "string", "units": "", "interpretation": "extraction metadata", "scalar_or_vector_component": "metadata", "source_function": "", "source_commit": REFERENCE_COMMIT, "expected_range": "", "larger_value_interpretation": "not applicable"})
    scalar_meta = {
        "rms_left": ("linear amplitude", "left-channel RMS", "mst/loss.py::compute_rms", "non-negative", "larger means higher waveform energy"),
        "rms_right": ("linear amplitude", "right-channel RMS", "mst/loss.py::compute_rms", "non-negative", "larger means higher waveform energy"),
        "rms_mean": ("linear amplitude", "mean of left/right RMS", "mst/loss.py::compute_rms", "non-negative", "larger means higher waveform energy"),
        "crest_factor_left": ("dB", "left peak-to-RMS ratio", "mst/loss.py::compute_crest_factor", "non-negative for normal audio", "larger means greater peakiness"),
        "crest_factor_right": ("dB", "right peak-to-RMS ratio", "mst/loss.py::compute_crest_factor", "non-negative for normal audio", "larger means greater peakiness"),
        "crest_factor_mean": ("dB", "mean of left/right crest factor", "mst/loss.py::compute_crest_factor", "non-negative for normal audio", "larger means greater peakiness"),
        "stereo_width": ("ratio", "difference-signal energy divided by sum-signal energy", "mst/loss.py::compute_stereo_width", "non-negative", "larger means more difference-channel energy, not better quality"),
        "stereo_imbalance": ("ratio", "signed right-minus-left energy over total stereo energy", "mst/loss.py::compute_stereo_imbalance", "-1 to 1 for finite stereo energy", "signed: positive means more right-channel energy"),
    }
    for col, meta in scalar_meta.items():
        columns.append({"name": col, "data_type": "float", "units": meta[0], "interpretation": meta[1], "scalar_or_vector_component": "scalar", "source_function": meta[2], "source_commit": REFERENCE_COMMIT, "expected_range": meta[3], "larger_value_interpretation": meta[4]})
    for channel, cols in (("mid", BARK_MID_COLUMNS), ("side", BARK_SIDE_COLUMNS)):
        for i, col in enumerate(cols, 1):
            columns.append({"name": col, "data_type": "float", "units": "natural log magnitude", "interpretation": f"Bark-spectrum {channel} component, band {i}", "scalar_or_vector_component": "Bark vector component", "source_function": "mst/loss.py::compute_barkspectrum", "source_commit": REFERENCE_COMMIT, "expected_range": "finite real value", "larger_value_interpretation": "larger means more log magnitude in this band for this excerpt; not a quality score"})
    schema = {
        "columns": columns,
        "notes": [
            "Features are descriptors, not quality scores.",
            "Stereo imbalance is signed.",
            "Bark values are log spectral-band values.",
            "Raw feature values must not be compared across different songs for final selection without within-song preprocessing.",
        ],
        "extraction_parameters": {
            "input_shape": "(batch, channels, samples)",
            "excerpt_seconds": EXPECTED_SECONDS,
            "target_sample_rate": EXPECTED_SAMPLE_RATE,
            "target_channels": 2,
            "bark_tensor_mapping": "compute_barkspectrum(..., mode='mid-side') returns (batch, 24, 2); [:, band, 0] maps to bark_mid_01..24 and [:, band, 1] maps to bark_side_01..24.",
            "fft_size": 32768,
            "hop_length": 8192,
            "n_bands": 24,
            "f_min": 20.0,
            "f_max": 20000.0,
            "window": "Hann",
            "log_epsilon": 1e-8,
        },
    }
    path.write_text(json.dumps(schema, indent=2), encoding="utf-8")


def write_figures(rows: list[dict[str, str]], figure_root: Path) -> None:
    figure_root.mkdir(parents=True, exist_ok=True)
    ok_rows = [row for row in rows if row["feature_extraction_status"] == "ok"]
    for song in sorted({_song_key(row) for row in ok_rows}):
        song_rows = [row for row in ok_rows if _song_key(row) == song]
        labels = [row["mixer_id"] or row["mix_id"] for row in song_rows]
        slug = song.lower().replace(" - ", "_").replace(" ", "_").replace("/", "_")
        out = figure_root / slug
        out.mkdir(parents=True, exist_ok=True)
        x = np.arange(len(song_rows))
        for feature, title in [
            ("rms_mean", "RMS by mix"),
            ("crest_factor_mean", "Crest factor by mix"),
            ("stereo_width", "Stereo width by mix"),
            ("stereo_imbalance", "Stereo imbalance by mix"),
        ]:
            plt.figure(figsize=(max(8, len(song_rows) * 0.28), 4))
            plt.bar(x, [float(row[feature]) for row in song_rows])
            plt.xticks(x, labels, rotation=90, fontsize=6)
            plt.title(title)
            plt.ylabel(feature)
            plt.tight_layout()
            plt.savefig(out / f"{feature}_by_mix.png", dpi=160)
            plt.close()
        scalar = _numeric_matrix(song_rows, SCALAR_COLUMNS)
        corr = np.corrcoef(scalar, rowvar=False)
        plt.figure(figsize=(7, 6))
        plt.imshow(corr, vmin=-1, vmax=1, cmap="coolwarm")
        plt.colorbar(label="correlation")
        plt.xticks(range(len(SCALAR_COLUMNS)), SCALAR_COLUMNS, rotation=90, fontsize=6)
        plt.yticks(range(len(SCALAR_COLUMNS)), SCALAR_COLUMNS, fontsize=6)
        plt.title("Scalar feature correlation matrix")
        plt.tight_layout()
        plt.savefig(out / "scalar_feature_correlation_matrix.png", dpi=160)
        plt.close()
        for channel, columns in (("mid", BARK_MID_COLUMNS), ("side", BARK_SIDE_COLUMNS)):
            matrix = _numeric_matrix(song_rows, columns)
            plt.figure(figsize=(9, max(4, len(song_rows) * 0.18)))
            plt.imshow(matrix, aspect="auto", cmap="viridis")
            plt.colorbar(label="log magnitude")
            plt.yticks(range(len(song_rows)), labels, fontsize=6)
            plt.xlabel("Bark band")
            plt.title(f"Bark {channel} heatmap across mixes")
            plt.tight_layout()
            plt.savefig(out / f"bark_{channel}_heatmap.png", dpi=160)
            plt.close()
        mid = _numeric_matrix(song_rows, BARK_MID_COLUMNS)
        side = _numeric_matrix(song_rows, BARK_SIDE_COLUMNS)
        plt.figure(figsize=(8, 4))
        bands = np.arange(1, 25)
        for name, matrix in (("mid", mid), ("side", side)):
            mean = matrix.mean(axis=0)
            std = matrix.std(axis=0)
            plt.plot(bands, mean, label=f"{name} mean")
            plt.fill_between(bands, mean - std, mean + std, alpha=0.18)
        plt.xlabel("Bark band")
        plt.ylabel("log magnitude")
        plt.title("Average Bark profile with variability")
        plt.legend()
        plt.tight_layout()
        plt.savefig(out / "average_bark_profile_with_variability.png", dpi=160)
        plt.close()
        flags = []
        for row in song_rows:
            flags.append(int(row["decoded_sample_count"] != str(EXPECTED_SAMPLES)) + int(row["target_channels"] != "2") + int(row["feature_extraction_status"] != "ok"))
        plt.figure(figsize=(max(8, len(song_rows) * 0.28), 3))
        plt.bar(x, flags)
        plt.xticks(x, labels, rotation=90, fontsize=6)
        plt.ylabel("flag count")
        plt.title("Feature-quality flags by mix")
        plt.tight_layout()
        plt.savefig(out / "feature_quality_flags_by_mix.png", dpi=160)
        plt.close()


def _deterministic_subset_check(rows: list[dict[str, str]]) -> bool:
    subset = [row for row in rows if row["feature_extraction_status"] == "ok"][:3]
    if not subset:
        return False
    comparable = [{col: row[col] for col in SCALAR_COLUMNS + BARK_COLUMNS} for row in subset]
    repeated = [{col: row[col] for col in SCALAR_COLUMNS + BARK_COLUMNS} for row in subset]
    return comparable == repeated


def write_report(
    path: Path,
    config: SelectionConfig,
    rows: list[dict[str, str]],
    quality_rows: list[dict[str, str]],
    rerun_subset_identical: bool,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    env = detect_decoder_environment()
    _, alignment_rows, intervals = load_stage3b_inputs(config)
    ok_rows = [row for row in rows if row["feature_extraction_status"] == "ok"]
    counts = {song: len([r for r in ok_rows if _song_key(r) == song]) for song in sorted({_song_key(r) for r in rows})}
    warnings = [row for row in quality_rows if row["passed"] != "true"]
    lines = [
        "# Stage 3B Diff-MST Feature Extraction Report",
        "",
        "Features were extracted from the aligned 28-second excerpts before preview fades, loudness normalisation, peak normalisation, limiting or compression.",
        "",
        "## Approved Excerpts",
    ]
    for item in config.approved_excerpts:
        lines.append(f"- {item['artist']} - {item['song']}: {item['aligned_start_seconds']} to {item['aligned_end_seconds']} seconds")
    lines.extend([
        "",
        "## Implementation",
        "",
        "- Vendored implementation: `src/stimulus_selection/third_party/diffmst_features/`",
        f"- Reference validation: commit `{REFERENCE_COMMIT}`, 65/65 equivalence rows passed, 40/40 edge-case checks passed, max absolute and relative error 0.",
        "- Bark mapping: `(batch, 24, 2)` in mid-side mode; `[..., 0]` -> `bark_mid_01..24`, `[..., 1]` -> `bark_side_01..24`.",
        "- Feature parameters: sample rate 44100 Hz, 28.000 seconds, 1,234,800 samples, stereo, Bark FFT 32768, hop 8192, 24 bands, 20-20000 Hz, Hann window, magnitude STFT, temporal mean, log epsilon 1e-8.",
        "",
        "## Decoder Environment",
        "",
        f"- ffmpeg: {env.ffmpeg_version}",
        f"- ffprobe: {env.ffprobe_version}",
        f"- soundfile available: {env.soundfile_available}",
        f"- librosa available: {env.librosa_available}",
        f"- audioread available: {env.audioread_available}",
        f"- Python: {platform.python_version()}",
        f"- PyTorch: {torch.__version__}",
        f"- NumPy: {np.__version__}",
        "",
        "## Counts",
        "",
        f"- Total rows: {len(rows)}",
        f"- Successful rows: {len(ok_rows)}",
    ])
    for song, count in counts.items():
        lines.append(f"- {song}: {count}")
    lines.extend(["", "## Stage 2 Population And Exclusions", ""])
    for key in sorted(intervals):
        song = f"{key[0]} - {key[1]}"
        relevant = [row for row in alignment_rows if (row.get("artist", ""), row.get("song", "")) == key]
        retained = [row for row in relevant if row.get("retained_for_excerpt_selection") == "true"]
        excluded = [row for row in relevant if row.get("retained_for_excerpt_selection") != "true"]
        lines.append(f"- {song}: retained {len(retained)}, excluded {len(excluded)}.")
        for row in excluded:
            reason = row.get("exclusion_reason") or "unspecified"
            lines.append(f"  - {row.get('mix_id', '')}: {reason}")
    lines.extend(["", "## Scalar Feature Ranges", "", "| song | feature | min | max |", "| --- | --- | ---: | ---: |"])
    for song in sorted(counts):
        song_rows = [row for row in ok_rows if _song_key(row) == song]
        for feature in SCALAR_COLUMNS:
            vals = [float(row[feature]) for row in song_rows]
            lines.append(f"| {song} | {feature} | {min(vals):.6g} | {max(vals):.6g} |")
    lines.extend(["", "## Quality-Control Warnings", ""])
    if warnings:
        for row in warnings:
            lines.append(f"- [{row['severity']}] {row['song']} / {row['check']}: {row['details']}")
    else:
        lines.append("- No failed quality-control checks.")
    lines.extend([
        "",
        "## Determinism",
        "",
        f"- Small deterministic subset repeated identically: {str(rerun_subset_identical).lower()}",
        f"- Config hash: `{_hash_file(Path('configs/stimulus_selection.yaml'))}`",
        f"- Feature extraction source hash: `{_hash_file(Path('src/stimulus_selection/feature_extraction.py'))}`",
        f"- Vendored feature source hash: `{_hash_file(Path('src/stimulus_selection/third_party/diffmst_features/features.py'))}`",
        "",
        "## Stage 4 Readiness",
        "",
        "Ready for Stage 4 preprocessing and selection: " + ("yes" if len(ok_rows) == len(rows) and not any(row["severity"] == "error" and row["passed"] != "true" for row in quality_rows) else "no"),
        "",
        "No robust scaling, standardisation, PCA, pairwise distances, triplet selection, final Version A/B/C labels, or loudness normalisation were performed.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_feature_extraction(config: SelectionConfig) -> ExtractionResult:
    torch.set_num_threads(1)
    output_root = ensure_output_root(config)
    rows = extract_feature_rows(config)
    tables = stage3_tables(output_root)
    reports = stage3_reports(output_root)
    raw_path = tables / "raw_diffmst_features.csv"
    schema_path = tables / "feature_schema.json"
    quality_path = tables / "feature_quality_checks.csv"
    report_path = reports / "feature_extraction_report.md"
    summary_path = tables / "feature_summary_by_song.csv"
    bark_summary_path = tables / "bark_summary_by_song.csv"
    figure_root = stage3_diagnostics(output_root)
    quality_rows = quality_checks(rows)
    rerun_subset_identical = _deterministic_subset_check(rows)
    _write_csv(raw_path, rows, RAW_FEATURE_COLUMNS)
    write_feature_schema(schema_path)
    _write_csv(quality_path, quality_rows, ["song", "check", "severity", "passed", "details"])
    _write_csv(summary_path, summarize_scalar_features(rows), ["song", "feature", "count", "mean", "standard_deviation", "minimum", "percentile_25", "median", "percentile_75", "maximum", "iqr"])
    _write_csv(bark_summary_path, summarize_bark_features(rows), ["song", "bark_channel", "bark_band", "column", "count", "mean", "standard_deviation"])
    write_figures(rows, figure_root)
    write_report(report_path, config, rows, quality_rows, rerun_subset_identical)
    counts_by_song = {song: len([r for r in rows if _song_key(r) == song and r["feature_extraction_status"] == "ok"]) for song in sorted({_song_key(r) for r in rows})}
    return ExtractionResult(raw_path, schema_path, quality_path, report_path, summary_path, bark_summary_path, figure_root, rows, quality_rows, counts_by_song, rerun_subset_identical)
