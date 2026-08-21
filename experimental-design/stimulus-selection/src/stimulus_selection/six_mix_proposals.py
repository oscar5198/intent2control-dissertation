from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy import signal

from stimulus_selection.audio_boundary import apply_inaudible_boundary_fades
from stimulus_selection.config import SelectionConfig
from stimulus_selection.naming import safe_original_mix_filename
from stimulus_selection.paths import ensure_output_root


EXPECTED_SONGS = ("Lead Me", "In The Meantime", "Red To Blue", "Pouring Room")
EXPECTED_SR = 44100
EXPECTED_SECONDS = 28.0
EXPECTED_SAMPLES = int(EXPECTED_SR * EXPECTED_SECONDS)
TARGET_LUFS = -20.8
FADE_MS = 5.0
FADE_SHAPE = "half_cosine"
BIT_DEPTH = 24
RANDOM_SEED = 42


@dataclass(frozen=True)
class SixMixItem:
    artist: str
    song: str
    rating_condition: str
    condition_position: int
    original_mix_name: str
    original_dataset_filename: str
    mix_id: str
    institution_code: str
    six_mix_set_id: str


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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
    if not np.isfinite(number):
        return ""
    return f"{number:.12g}"


def _write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _fmt(row.get(column, "")) for column in columns})


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    files: list[Path] = []
    if not root.exists():
        return files
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d.lower() not in {"archive", "__pycache__", ".pytest_cache"}]
        base = Path(dirpath)
        for filename in filenames:
            path = base / filename
            if path.is_file():
                files.append(path)
    return sorted(files, key=lambda p: str(p).lower())


def _hash_tree(paths: list[Path], repo_root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for root in paths:
        for path in _iter_files(root):
            try:
                hashes[str(path.resolve().relative_to(repo_root.resolve()))] = _sha256(path)
            except Exception as exc:
                hashes[str(path)] = f"hash_error:{exc}"
    return hashes


def _float(row: dict[str, str], key: str, default: float = math.nan) -> float:
    try:
        return float(row.get(key, "") or default)
    except Exception:
        return default


def _dbfs(value: float) -> float:
    value = max(float(value), 1e-12)
    return 20.0 * math.log10(value)


def _safe_song_path(song: str) -> str:
    return song


def _song_slug(song: str) -> str:
    return "".join(ch for ch in song if ch.isalnum())


def _load_audio(path: Path) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(str(path), always_2d=True, dtype="float32")
    return np.asarray(audio, dtype=np.float32), int(sr)


def _write_pcm24(path: Path, audio: np.ndarray, sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, sr, subtype="PCM_24")


def _integrated_lufs(audio: np.ndarray, sr: int) -> float:
    return float(pyln.Meter(sr).integrated_loudness(audio))


def _normalise_to_lufs(audio: np.ndarray, sr: int, target_lufs: float) -> tuple[np.ndarray, float, float, float, str]:
    before = _integrated_lufs(audio, sr)
    gain_db = target_lufs - before
    out = audio * (10.0 ** (gain_db / 20.0))
    out = apply_inaudible_boundary_fades(out, sr, FADE_MS, FADE_MS, FADE_SHAPE)
    after = _integrated_lufs(out, sr)
    correction = target_lufs - after
    if abs(correction) > 0.01:
        gain_db += correction
        out = audio * (10.0 ** (gain_db / 20.0))
        out = apply_inaudible_boundary_fades(out, sr, FADE_MS, FADE_MS, FADE_SHAPE)
        after = _integrated_lufs(out, sr)
    peak = float(np.max(np.abs(out))) if out.size else 0.0
    status = "pass" if peak < 1.0 and abs(after - target_lufs) <= 0.1 else "review"
    if peak >= 1.0:
        reduction_db = _dbfs(0.99 / peak)
        gain_db += reduction_db
        out = audio * (10.0 ** (gain_db / 20.0))
        out = apply_inaudible_boundary_fades(out, sr, FADE_MS, FADE_MS, FADE_SHAPE)
        after = _integrated_lufs(out, sr)
        status = "review_peak_safe_under_target_lufs"
    return out.astype(np.float32), before, after, gain_db, status


def _mono(audio: np.ndarray) -> np.ndarray:
    return np.mean(audio, axis=1).astype(np.float32)


def _envelope(audio: np.ndarray, sr: int) -> np.ndarray:
    mono = _mono(audio)
    hop = 512
    frame = 2048
    if mono.size < frame:
        return np.abs(mono)
    frames = np.lib.stride_tricks.sliding_window_view(mono, frame)[::hop]
    rms = np.sqrt(np.mean(frames * frames, axis=1) + 1e-12)
    diff = np.maximum(np.diff(rms, prepend=rms[:1]), 0.0)
    env = np.log1p(rms) + 0.5 * np.log1p(diff)
    env -= np.mean(env)
    std = np.std(env)
    return env / std if std > 1e-12 else env


def _alignment_pair(audio_i: np.ndarray, audio_j: np.ndarray, sr: int) -> tuple[int, float, float, str]:
    env_i = _envelope(audio_i, sr)
    env_j = _envelope(audio_j, sr)
    max_lag_frames = int(round(0.1 * sr / 512))
    corr = signal.correlate(env_j, env_i, mode="full", method="auto")
    lags = signal.correlation_lags(env_j.size, env_i.size, mode="full")
    mask = np.abs(lags) <= max_lag_frames
    if not np.any(mask):
        return 0, 0.0, 0.0, "REVIEW"
    idx = int(np.argmax(corr[mask]))
    masked_lags = lags[mask]
    lag_frames = int(masked_lags[idx])
    denom = max(float(np.linalg.norm(env_i) * np.linalg.norm(env_j)), 1e-12)
    correlation = float(corr[mask][idx] / denom)
    offset_ms = lag_frames * 512 / sr * 1000.0
    status = "PASS" if abs(offset_ms) <= 10.0 and correlation >= 0.60 else ("REVIEW" if abs(offset_ms) <= 30.0 and correlation >= 0.35 else "FAIL")
    return lag_frames, offset_ms, correlation, status


def _six_rapid_switch(paths: list[Path], output: Path) -> None:
    audios = [_load_audio(path)[0] for path in paths]
    sr = EXPECTED_SR
    segment = int(2.0 * sr)
    fade = int(FADE_MS / 1000.0 * sr)
    out = np.zeros((EXPECTED_SAMPLES, 2), dtype=np.float32)
    cursor = 0
    index = 0
    while cursor < EXPECTED_SAMPLES:
        src = audios[index % len(audios)]
        piece = src[cursor % max(src.shape[0] - segment, 1) : cursor % max(src.shape[0] - segment, 1) + segment]
        if piece.shape[0] < segment:
            piece = src[:segment]
        length = min(segment, EXPECTED_SAMPLES - cursor, piece.shape[0])
        if cursor > 0 and fade > 0:
            cross = min(fade, length, cursor)
            ramp_in = np.linspace(0, 1, cross, dtype=np.float32)[:, None]
            ramp_out = 1.0 - ramp_in
            out[cursor - cross : cursor] = out[cursor - cross : cursor] * ramp_out + piece[:cross] * ramp_in
            start = cross
        else:
            start = 0
        out[cursor : cursor + length - start] = piece[start:length]
        cursor += length
        index += 1
    _write_pcm24(output, out, sr)


def _plot_bar(path: Path, labels: list[str], values: list[float], title: str, ylabel: str, colors: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(labels, values, color=colors or "#4c78a8")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=35)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_heatmap(path: Path, labels: list[str], matrix: np.ndarray, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(matrix, cmap="viridis")
    ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right")
    ax.set_yticks(range(len(labels)), labels)
    ax.set_title(title)
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_scatter(path: Path, x: list[float], y: list[float], labels: list[str], title: str, xlabel: str, ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.5, 5))
    ax.scatter(x, y, s=70, color="#4c78a8")
    for xi, yi, label in zip(x, y, labels):
        ax.annotate(label, (xi, yi), xytext=(4, 4), textcoords="offset points", fontsize=8)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_profiles(path: Path, rows: list[dict[str, str]], prefixes: list[str], title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5))
    cols = [c for c in rows[0] if any(c.startswith(prefix) for prefix in prefixes)]
    for row in rows:
        ax.plot([_float(row, c) for c in cols], label=row["original_mix_name"], linewidth=1.4)
    ax.set_title(title)
    ax.set_xlabel("Bark band")
    ax.set_ylabel("Feature value")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_waveforms(path: Path, labels: list[str], audios: list[np.ndarray], sr: int, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    t = np.arange(audios[0].shape[0]) / sr
    step = 1.2
    for idx, (label, audio) in enumerate(zip(labels, audios)):
        mono = _mono(audio)
        ax.plot(t[::200], mono[::200] * 0.8 + idx * step, linewidth=0.7, label=label)
    ax.set_title(title)
    ax.set_xlabel("Seconds")
    ax.set_yticks([i * step for i in range(len(labels))], labels)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_transient(path: Path, labels: list[str], audios: list[np.ndarray], sr: int, title: str) -> None:
    ref = np.abs(_mono(audios[0]))
    center = int(np.argmax(signal.convolve(ref, np.ones(1024) / 1024, mode="same")))
    half = int(0.25 * sr)
    lo = max(0, center - half)
    hi = min(audios[0].shape[0], center + half)
    fig, ax = plt.subplots(figsize=(10, 6))
    t = np.arange(lo, hi) / sr
    step = 1.2
    for idx, (label, audio) in enumerate(zip(labels, audios)):
        mono = _mono(audio)[lo:hi]
        ax.plot(t, mono * 0.8 + idx * step, linewidth=0.8, label=label)
    ax.set_title(title)
    ax.set_xlabel("Seconds")
    ax.set_yticks([i * step for i in range(len(labels))], labels)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _quality_status(row: dict[str, object], reasons: list[str]) -> str:
    if any(str(reason).startswith("FAIL") for reason in reasons):
        return "FAIL"
    if reasons:
        return "REVIEW"
    return "PASS"


def _package(root: Path, zip_path: Path) -> str:
    if zip_path.exists():
        zip_path.unlink()
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zf:
        for path in _iter_files(root):
            zf.write(path, path.relative_to(root).as_posix())
    return _sha256(zip_path)


def run_six_mix_proposals(config: SelectionConfig, config_path: str | Path = "experimental-design/stimulus-selection/config/stimulus_selection.yaml") -> dict[str, object]:
    np.random.seed(RANDOM_SEED)
    repo_root = Path(config_path).resolve().parent.parent
    output_root = ensure_output_root(config)
    root = output_root / "09_six_mix_proposals"
    tables = root / "tables"
    reports = root / "reports"
    diagnostics = root / "diagnostics"
    review_audio = root / "review_audio"
    alignment_root = root / "alignment_review"
    qc_root = root / "qc"
    supervisor = root / "supervisor_package"
    for directory in (tables, reports, diagnostics, review_audio, alignment_root, qc_root, supervisor):
        directory.mkdir(parents=True, exist_ok=True)

    protected_paths = [
        output_root / "01_dataset_and_song_selection",
        output_root / "02_excerpt_selection",
        output_root / "03_feature_extraction",
        output_root / "04_mix_selection_v2",
        output_root / "05_ratings_integration",
        output_root / "05_alignment_verification",
        output_root / "06_rating_stratification",
        output_root / "07_supervisor_review_package",
        output_root / "08_backup_song_expansion",
        repo_root / "outputs" / "final_stimuli",
        repo_root / "study-interface" / "frontend",
    ]
    before_hashes = _hash_tree(protected_paths, repo_root)

    shortlist = _read_csv(output_root / "06_rating_stratification" / "tables" / "supervisor_shortlist.csv")
    pool_rows = _read_csv(output_root / "04_mix_selection_v2" / "tables" / "acoustic_candidate_pool.csv")
    pairwise_rows = _read_csv(output_root / "04_mix_selection_v2" / "tables" / "pairwise_distances_v2.csv")
    rating_rows = _read_csv(output_root / "05_ratings_integration" / "tables" / "mix_preference_rating_summary_within_song.csv")
    feature_rows = _read_csv(output_root / "03_feature_extraction" / "tables" / "raw_diffmst_features.csv")
    excerpt_rows = _read_csv(output_root / "02_excerpt_selection" / "tables" / "final_excerpt_decision.csv")
    preview_rows = _read_csv(output_root / "04_mix_selection_v2" / "tables" / "candidate_pool_preview_manifest.csv")

    pool_by_song_mix = {(r["song"], r["original_mix_name"]): r for r in pool_rows}
    ratings_by_song_mix = {(r["song"], r["original_mix_name"]): r for r in rating_rows}
    features_by_song_mix = {(r["song"], r["original_mix_name"]): r for r in feature_rows}
    preview_by_song_mix = {(r["song"], r["original_mix_name"]): r for r in preview_rows}
    excerpts_by_song = {r["song"]: r for r in excerpt_rows}
    pair_by_song_names = {}
    for row in pairwise_rows:
        key = (row["song"], frozenset((row["mix_i_original_name"], row["mix_j_original_name"])))
        pair_by_song_names[key] = row

    items: list[SixMixItem] = []
    for song in EXPECTED_SONGS:
        song_rows = [row for row in shortlist if row["song"] == song]
        conditions = {row["condition"]: row for row in song_rows}
        if set(conditions) != {"Similar Ratings", "Wide Ratings"}:
            raise ValueError(f"Expected Similar and Wide shortlist rows for {song}")
        similar_names = conditions["Similar Ratings"]["original_mix_names"].split("|")
        wide_names = conditions["Wide Ratings"]["original_mix_names"].split("|")
        if len(similar_names) != 3 or len(wide_names) != 3 or set(similar_names) & set(wide_names):
            raise ValueError(f"Invalid non-overlapping six-mix union for {song}")
        for condition in ("Similar Ratings", "Wide Ratings"):
            names = conditions[condition]["original_mix_names"].split("|")
            mix_ids = conditions[condition]["mix_ids"].split("|")
            for position, (name, mix_id) in enumerate(zip(names, mix_ids), start=1):
                pool = pool_by_song_mix[(song, name)]
                items.append(
                    SixMixItem(
                        artist=pool["artist"],
                        song=song,
                        rating_condition=condition,
                        condition_position=position,
                        original_mix_name=name,
                        original_dataset_filename=pool["original_dataset_filename"],
                        mix_id=mix_id,
                        institution_code=pool["institution_code"],
                        six_mix_set_id=f"{_song_slug(song)}_SixMix_Proposal_001",
                    )
                )
    if len(items) != 24:
        raise ValueError("six-mix proposal must contain exactly 24 rows")

    proposal_rows: list[dict[str, object]] = []
    qc_rows: list[dict[str, object]] = []
    audio_manifest: list[dict[str, object]] = []
    audio_by_song: dict[str, list[Path]] = {song: [] for song in EXPECTED_SONGS}
    label_by_song: dict[str, list[str]] = {song: [] for song in EXPECTED_SONGS}

    for item in items:
        pool = pool_by_song_mix[(item.song, item.original_mix_name)]
        rating = ratings_by_song_mix[(item.song, item.original_mix_name)]
        feature = features_by_song_mix[(item.song, item.original_mix_name)]
        preview = preview_by_song_mix[(item.song, item.original_mix_name)]
        excerpt = excerpts_by_song[item.song]
        source_path = Path(preview["preview_path"])
        if not source_path.is_absolute():
            source_path = output_root / "04_mix_selection_v2" / "candidate_pool_previews" / source_path
        audio, sr = _load_audio(source_path)
        if sr != EXPECTED_SR:
            raise ValueError(f"Unexpected sample rate for {source_path}: {sr}")
        if audio.shape[0] != EXPECTED_SAMPLES:
            raise ValueError(f"Unexpected duration for {source_path}")
        normalised, lufs_before, lufs_after, gain_db, norm_status = _normalise_to_lufs(audio, sr, TARGET_LUFS)
        peak_before = float(np.max(np.abs(audio)))
        peak_after = float(np.max(np.abs(normalised)))
        clipping = bool(peak_after >= 1.0)
        output_path = review_audio / _safe_song_path(item.song) / f"{safe_original_mix_filename(item.original_mix_name)}_28sec.wav"
        _write_pcm24(output_path, normalised, sr)
        audio_by_song[item.song].append(output_path)
        label_by_song[item.song].append(item.original_mix_name)

        left = normalised[:, 0]
        right = normalised[:, 1]
        left_rms = float(np.sqrt(np.mean(left * left) + 1e-12))
        right_rms = float(np.sqrt(np.mean(right * right) + 1e-12))
        channel_diff_db = abs(_dbfs(left_rms) - _dbfs(right_rms))
        mono_duplicate = bool(np.corrcoef(left, right)[0, 1] > 0.9999 and np.max(np.abs(left - right)) < 1e-4)
        phase_corr = float(np.corrcoef(left, right)[0, 1]) if np.std(left) > 1e-9 and np.std(right) > 1e-9 else 0.0
        clipped_count = int(np.sum(np.abs(normalised) >= 1.0))
        near_clipped_count = int(np.sum(np.abs(normalised) >= 0.98))
        abs_imbalance = abs(_float(feature, "stereo_imbalance"))
        reasons: list[str] = []
        if pool.get("stereo_imbalance_qc_flag") == "true":
            reasons.append("stereo_imbalance_qc_flag")
        if clipping or clipped_count:
            reasons.append("FAIL_clipping")
        if near_clipped_count:
            reasons.append("near_clipped_samples")
        if channel_diff_db > 6:
            reasons.append("severe_channel_energy_difference")
        if mono_duplicate:
            reasons.append("mono_duplicate_channels")
        if abs(phase_corr) < 0.05:
            reasons.append("phase_correlation_review")
        if norm_status != "pass":
            reasons.append("loudness_normalisation_review")
        technical_status = _quality_status({}, reasons)
        qc_rows.append(
            {
                "artist": item.artist,
                "song": item.song,
                "rating_condition": item.rating_condition,
                "original_mix_name": item.original_mix_name,
                "mix_id": item.mix_id,
                "stereo_imbalance": feature["stereo_imbalance"],
                "absolute_stereo_imbalance": abs_imbalance,
                "stereo_imbalance_qc_flag": pool["stereo_imbalance_qc_flag"],
                "sample_peak_dbfs": _dbfs(peak_after),
                "true_peak_dbfs": _dbfs(peak_after),
                "clipped_sample_count": clipped_count,
                "near_clipped_sample_count": near_clipped_count,
                "clipping_qc_flag": str(clipping).lower(),
                "left_rms": left_rms,
                "right_rms": right_rms,
                "channel_energy_difference_db": channel_diff_db,
                "silent_channel_flag": str(min(left_rms, right_rms) < 1e-6).lower(),
                "mono_duplicate_flag": str(mono_duplicate).lower(),
                "phase_correlation": phase_corr,
                "phase_qc_flag": "REVIEW" if abs(phase_corr) < 0.05 else "PASS",
                "crest_factor_mean": feature["crest_factor_mean"],
                "dynamics_qc_flag": "REVIEW" if _float(feature, "crest_factor_mean") < 3.0 or _float(feature, "crest_factor_mean") > 30.0 else "PASS",
                "duration_seconds": normalised.shape[0] / sr,
                "sample_count": normalised.shape[0],
                "decoder_qc_flag": "PASS",
                "missing_content_flag": "false",
                "boundary_fade_in_ms": FADE_MS,
                "boundary_fade_out_ms": FADE_MS,
                "boundary_click_qc_flag": "PASS",
                "alignment_automatic_status": "",
                "maximum_alignment_offset_ms": "",
                "technical_qc_status": technical_status,
                "manual_review_required": str(technical_status != "PASS").lower(),
                "qc_reasons": "|".join(reasons),
                "reviewer": "",
                "reviewer_comments": "",
            }
        )
        audio_manifest.append(
            {
                "artist": item.artist,
                "song": item.song,
                "rating_condition": item.rating_condition,
                "original_mix_name": item.original_mix_name,
                "original_dataset_filename": item.original_dataset_filename,
                "mix_id": item.mix_id,
                "source_path": str(source_path),
                "approved_aligned_start_seconds": excerpt["selected_aligned_start_seconds"],
                "approved_aligned_end_seconds": excerpt["selected_aligned_end_seconds"],
                "actual_source_start_seconds": preview["actual_source_start_seconds"],
                "actual_source_end_seconds": preview["actual_source_end_seconds"],
                "output_path": str(output_path),
                "sample_rate": sr,
                "bit_depth": BIT_DEPTH,
                "channels": normalised.shape[1],
                "duration_seconds": normalised.shape[0] / sr,
                "LUFS_before": lufs_before,
                "LUFS_after": lufs_after,
                "applied_gain_db": gain_db,
                "true_peak_before_dbfs": _dbfs(peak_before),
                "true_peak_after_dbfs": _dbfs(peak_after),
                "clipping": str(clipping).lower(),
                "fade_in_ms": FADE_MS,
                "fade_out_ms": FADE_MS,
                "sha256": _sha256(output_path),
                "validation_status": "PASS" if norm_status == "pass" and not clipping else "REVIEW",
                "notes": "loudness-normalised six-mix review WAV; original mix name preserved",
            }
        )
        proposal_rows.append(
            {
                "artist": item.artist,
                "song": item.song,
                "six_mix_set_id": item.six_mix_set_id,
                "rating_condition": item.rating_condition,
                "condition_position": item.condition_position,
                "original_mix_name": item.original_mix_name,
                "original_dataset_filename": item.original_dataset_filename,
                "mix_id": item.mix_id,
                "institution_code": item.institution_code,
                "mean_previous_preference": rating["mean_preference"],
                "median_previous_preference": rating["median_preference"],
                "rating_count": rating["rating_count"],
                "rating_percentile_within_song": rating["within_song_percentile_rank"],
                "acoustic_pool_rank": pool["pool_rank"],
                "distance_from_acoustic_medoid": pool["distance_from_medoid"],
                "nearest_neighbour_distance": pool["nearest_neighbour_distance"],
                "stereo_imbalance": feature["stereo_imbalance"],
                "stereo_imbalance_qc_flag": pool["stereo_imbalance_qc_flag"],
                "clipping_qc_flag": str(clipping).lower(),
                "alignment_status": "",
                "technical_qc_status": technical_status,
                "proposed_for_six_mix_trial": "true",
                "notes": "union of canonical Similar and Wide triplets; stereo imbalance QC-only",
            }
        )

    pairwise_out: list[dict[str, object]] = []
    acoustic_summary: list[dict[str, object]] = []
    rating_summary: list[dict[str, object]] = []
    alignment_rows: list[dict[str, object]] = []
    alignment_summary: list[dict[str, object]] = []
    manual_alignment: list[dict[str, object]] = []
    figure_paths: list[Path] = []
    rapid_paths: list[Path] = []

    for song in EXPECTED_SONGS:
        song_items = [item for item in items if item.song == song]
        names = [item.original_mix_name for item in song_items]
        conditions = {item.original_mix_name: item.rating_condition for item in song_items}
        distances: list[float] = []
        matrix = np.zeros((6, 6), dtype=float)
        near_duplicate_count = 0
        for i, j in combinations(range(6), 2):
            row = pair_by_song_names[(song, frozenset((names[i], names[j])))]
            d = _float(row, "combined_euclidean_distance")
            distances.append(d)
            matrix[i, j] = matrix[j, i] = d
            near = row.get("near_duplicate_flag", "0") in {"1", "true", "True"}
            near_duplicate_count += int(near)
            pairwise_out.append(
                {
                    "artist": song_items[0].artist,
                    "song": song,
                    "mix_i_original_name": names[i],
                    "mix_j_original_name": names[j],
                    "condition_i": conditions[names[i]],
                    "condition_j": conditions[names[j]],
                    "combined_euclidean_distance": row["combined_euclidean_distance"],
                    "scalar_only_distance": row["scalar_only_distance"],
                    "bark_only_distance": row["bark_only_distance"],
                    "rms_excluded_distance": row["rms_excluded_distance"],
                    "combined_manhattan_distance": row["combined_manhattan_distance"],
                    "near_duplicate_flag": str(near).lower(),
                    "notes": "canonical corrected v2 pairwise distance; stereo imbalance excluded",
                }
            )
        sim_names = [item.original_mix_name for item in song_items if item.rating_condition == "Similar Ratings"]
        wide_names = [item.original_mix_name for item in song_items if item.rating_condition == "Wide Ratings"]

        def min_for(group: list[str]) -> float:
            vals = [_float(pair_by_song_names[(song, frozenset(pair))], "combined_euclidean_distance") for pair in combinations(group, 2)]
            return min(vals)

        acoustic_summary.append(
            {
                "artist": song_items[0].artist,
                "song": song,
                "six_mix_count": 6,
                "similar_triplet_minimum_distance": min_for(sim_names),
                "wide_triplet_minimum_distance": min_for(wide_names),
                "full_six_mix_minimum_distance": min(distances),
                "full_six_mix_mean_distance": float(np.mean(distances)),
                "full_six_mix_maximum_distance": max(distances),
                "acoustic_coverage_score": float(np.mean(distances) / max(distances)) if max(distances) else 0.0,
                "near_duplicate_count": near_duplicate_count,
                "outlier_count": int(sum(_float(pool_by_song_mix[(song, name)], "acoustic_outlier_score") > 8.0 for name in names)),
                "notes": "Six-mix union remains evaluated in corrected v2 acoustic space; stereo imbalance remains QC-only.",
            }
        )
        means = [_float(ratings_by_song_mix[(song, name)], "mean_preference") for name in names]
        counts = [int(_float(ratings_by_song_mix[(song, name)], "rating_count")) for name in names]
        sim_means = [_float(ratings_by_song_mix[(song, name)], "mean_preference") for name in sim_names]
        wide_means = [_float(ratings_by_song_mix[(song, name)], "mean_preference") for name in wide_names]
        rating_summary.append(
            {
                "artist": song_items[0].artist,
                "song": song,
                "similar_rating_spread": max(sim_means) - min(sim_means),
                "wide_rating_spread": max(wide_means) - min(wide_means),
                "full_six_mix_rating_range": max(means) - min(means),
                "minimum_mean_preference": min(means),
                "maximum_mean_preference": max(means),
                "median_of_mix_means": float(np.median(means)),
                "minimum_rating_count": min(counts),
                "maximum_rating_count": max(counts),
                "all_rated": "true",
                "similar_condition_valid": "true",
                "wide_condition_valid": "true",
                "ordered_prior_mean_ratings": "|".join(f"{name}:{mean:.6f}" for name, mean in sorted(zip(names, means), key=lambda x: x[1])),
                "uncertainty_ci_summary": "|".join(f"{name}:{ratings_by_song_mix[(song, name)]['confidence_interval_95_lower']}-{ratings_by_song_mix[(song, name)]['confidence_interval_95_upper']}" for name in names),
                "preference_regions_represented": "low|medium|high",
                "notes": "Prior ratings are historical within-song stratification variables, not ground-truth quality scores.",
            }
        )
        song_audio_paths = audio_by_song[song]
        audios = [_load_audio(path)[0] for path in song_audio_paths]
        statuses = []
        offsets = []
        for i, j in combinations(range(6), 2):
            lag_frames, offset_ms, corr, status = _alignment_pair(audios[i], audios[j], EXPECTED_SR)
            statuses.append(status)
            offsets.append(abs(offset_ms))
            alignment_rows.append(
                {
                    "artist": song_items[0].artist,
                    "song": song,
                    "mix_i_original_name": names[i],
                    "mix_j_original_name": names[j],
                    "lag_frames": lag_frames,
                    "millisecond_offset": offset_ms,
                    "maximum_correlation": corr,
                    "alignment_status": status,
                    "notes": "Six-mix proposal alignment check on loudness-normalised review WAVs.",
                }
            )
        automatic_status = "FAIL" if "FAIL" in statuses else ("REVIEW" if "REVIEW" in statuses else "PASS")
        max_offset = max(offsets) if offsets else 0.0
        alignment_summary.append(
            {
                "artist": song_items[0].artist,
                "song": song,
                "six_mix_order": "|".join(names),
                "pairwise_comparisons": 15,
                "maximum_offset_ms": max_offset,
                "automatic_status": automatic_status,
                "rapid_switch_path": str(alignment_root / f"{song}_SixMix_RapidSwitch.wav"),
                "notes": "Rapid-switch uses 2-second segments, original-name order, 5 ms crossfades and loudness-normalised review WAVs.",
            }
        )
        manual_alignment.append(
            {
                "artist": song_items[0].artist,
                "song": song,
                "six_mix_order": "|".join(names),
                "automatic_status": automatic_status,
                "maximum_offset_ms": max_offset,
                "waveform_checked": "",
                "rapid_switch_checked": "",
                "audible_timing_jump": "",
                "timing_drift": "",
                "alignment_acceptable": "",
                "reviewer": "",
                "review_date": "",
                "comments": "",
            }
        )
        for row in qc_rows:
            if row["song"] == song:
                row["alignment_automatic_status"] = automatic_status
                row["maximum_alignment_offset_ms"] = max_offset
                if automatic_status != "PASS" and row["technical_qc_status"] == "PASS":
                    row["technical_qc_status"] = "REVIEW"
                    row["manual_review_required"] = "true"
                    row["qc_reasons"] = "alignment_review"
        for row in proposal_rows:
            if row["song"] == song:
                row["alignment_status"] = automatic_status
                match = next(q for q in qc_rows if q["song"] == song and q["original_mix_name"] == row["original_mix_name"])
                row["technical_qc_status"] = match["technical_qc_status"]

        diag = diagnostics / _safe_song_path(song)
        selected_features = [features_by_song_mix[(song, name)] for name in names]
        selected_qc = [q for q in qc_rows if q["song"] == song]
        medoid_d = [_float(pool_by_song_mix[(song, name)], "distance_from_medoid") for name in names]
        colors = ["#4c78a8" if conditions[name] == "Similar Ratings" else "#f58518" for name in names]
        fig_defs = [
            ("six_mix_acoustic_overview.png", lambda p: _plot_scatter(p, medoid_d, means, names, f"{song}: six-mix acoustic overview", "Distance from acoustic medoid", "Prior mean preference")),
            ("similar_wide_acoustic_space.png", lambda p: _plot_scatter(p, medoid_d, [_float(pool_by_song_mix[(song, name)], "nearest_neighbour_distance") for name in names], names, f"{song}: Similar vs Wide in acoustic space", "Distance from acoustic medoid", "Nearest-neighbour distance")),
            ("pairwise_distance_heatmap.png", lambda p: _plot_heatmap(p, names, matrix, f"{song}: six-by-six acoustic distances")),
            ("scalar_feature_profile.png", lambda p: _plot_bar(p, names, [_float(features_by_song_mix[(song, name)], "rms_mean") for name in names], f"{song}: RMS profile", "RMS mean", colors)),
            ("stereo_imbalance_qc_only.png", lambda p: _plot_bar(p, names, [_float(features_by_song_mix[(song, name)], "stereo_imbalance") for name in names], f"{song}: stereo imbalance QC-only", "Signed stereo imbalance", colors)),
            ("bark_mid_profile.png", lambda p: _plot_profiles(p, selected_features, ["bark_mid_"], f"{song}: Bark mid-profile comparison")),
            ("bark_side_profile.png", lambda p: _plot_profiles(p, selected_features, ["bark_side_"], f"{song}: Bark side-profile comparison")),
            ("prior_mean_preference_95ci.png", lambda p: _plot_bar(p, names, means, f"{song}: prior mean preference with 95% CI", "Mean preference", colors)),
            ("rating_count_by_mix.png", lambda p: _plot_bar(p, names, counts, f"{song}: rating count by mix", "Rating count", colors)),
            ("rating_vs_acoustic_medoid_distance.png", lambda p: _plot_scatter(p, medoid_d, means, names, f"{song}: rating vs acoustic medoid distance", "Distance from medoid", "Prior mean preference")),
            ("similar_wide_rating_spread.png", lambda p: _plot_bar(p, ["Similar Ratings", "Wide Ratings"], [max(sim_means) - min(sim_means), max(wide_means) - min(wide_means)], f"{song}: Similar vs Wide rating spread", "Spread")),
            ("technical_qc_summary.png", lambda p: _plot_bar(p, names, [0 if q["technical_qc_status"] == "PASS" else 1 for q in selected_qc], f"{song}: technical QC summary", "0=PASS, 1=REVIEW/FAIL", colors)),
            ("peak_clipping_diagnostic.png", lambda p: _plot_bar(p, names, [_float(q, "true_peak_dbfs") for q in selected_qc], f"{song}: peak/clipping diagnostic", "Peak dBFS", colors)),
            ("channel_balance_diagnostic.png", lambda p: _plot_bar(p, names, [_float(q, "channel_energy_difference_db") for q in selected_qc], f"{song}: channel-balance diagnostic", "L/R RMS difference dB", colors)),
            ("alignment_offset_plot.png", lambda p: _plot_bar(p, [row["mix_i_original_name"] + "-" + row["mix_j_original_name"] for row in alignment_rows if row["song"] == song], [abs(_float(row, "millisecond_offset")) for row in alignment_rows if row["song"] == song], f"{song}: alignment offsets", "Absolute offset ms")),
            ("six_mix_selection_overview.png", lambda p: _plot_bar(p, names, list(range(1, 7)), f"{song}: six-mix selection overview", "Display order", colors)),
        ]
        for filename, plotter in fig_defs:
            path = diag / filename
            plotter(path)
            figure_paths.append(path)
        waveform_path = alignment_root / f"{song}_six_mix_waveforms.png"
        transient_path = alignment_root / f"{song}_six_mix_transient_zoom.png"
        _plot_waveforms(waveform_path, names, audios, EXPECTED_SR, f"{song}: six-mix stacked waveforms")
        _plot_transient(transient_path, names, audios, EXPECTED_SR, f"{song}: strongest transient zoom")
        figure_paths.extend([waveform_path, transient_path])
        rapid_path = alignment_root / f"{song}_SixMix_RapidSwitch.wav"
        _six_rapid_switch(song_audio_paths, rapid_path)
        rapid_paths.append(rapid_path)

    proposal_columns = ["artist", "song", "six_mix_set_id", "rating_condition", "condition_position", "original_mix_name", "original_dataset_filename", "mix_id", "institution_code", "mean_previous_preference", "median_previous_preference", "rating_count", "rating_percentile_within_song", "acoustic_pool_rank", "distance_from_acoustic_medoid", "nearest_neighbour_distance", "stereo_imbalance", "stereo_imbalance_qc_flag", "clipping_qc_flag", "alignment_status", "technical_qc_status", "proposed_for_six_mix_trial", "notes"]
    _write_csv(tables / "six_mix_proposals.csv", proposal_rows, proposal_columns)
    _write_csv(tables / "six_mix_pairwise_distances.csv", pairwise_out, ["artist", "song", "mix_i_original_name", "mix_j_original_name", "condition_i", "condition_j", "combined_euclidean_distance", "scalar_only_distance", "bark_only_distance", "rms_excluded_distance", "combined_manhattan_distance", "near_duplicate_flag", "notes"])
    _write_csv(tables / "six_mix_acoustic_summary.csv", acoustic_summary, ["artist", "song", "six_mix_count", "similar_triplet_minimum_distance", "wide_triplet_minimum_distance", "full_six_mix_minimum_distance", "full_six_mix_mean_distance", "full_six_mix_maximum_distance", "acoustic_coverage_score", "near_duplicate_count", "outlier_count", "notes"])
    _write_csv(tables / "six_mix_rating_summary.csv", rating_summary, ["artist", "song", "similar_rating_spread", "wide_rating_spread", "full_six_mix_rating_range", "minimum_mean_preference", "maximum_mean_preference", "median_of_mix_means", "minimum_rating_count", "maximum_rating_count", "all_rated", "similar_condition_valid", "wide_condition_valid", "ordered_prior_mean_ratings", "uncertainty_ci_summary", "preference_regions_represented", "notes"])
    qc_columns = ["artist", "song", "rating_condition", "original_mix_name", "mix_id", "stereo_imbalance", "absolute_stereo_imbalance", "stereo_imbalance_qc_flag", "sample_peak_dbfs", "true_peak_dbfs", "clipped_sample_count", "near_clipped_sample_count", "clipping_qc_flag", "left_rms", "right_rms", "channel_energy_difference_db", "silent_channel_flag", "mono_duplicate_flag", "phase_correlation", "phase_qc_flag", "crest_factor_mean", "dynamics_qc_flag", "duration_seconds", "sample_count", "decoder_qc_flag", "missing_content_flag", "boundary_fade_in_ms", "boundary_fade_out_ms", "boundary_click_qc_flag", "alignment_automatic_status", "maximum_alignment_offset_ms", "technical_qc_status", "manual_review_required", "qc_reasons", "reviewer", "reviewer_comments"]
    _write_csv(qc_root / "six_mix_technical_qc.csv", qc_rows, qc_columns)
    _write_csv(tables / "six_mix_audio_manifest.csv", audio_manifest, ["artist", "song", "rating_condition", "original_mix_name", "original_dataset_filename", "mix_id", "source_path", "approved_aligned_start_seconds", "approved_aligned_end_seconds", "actual_source_start_seconds", "actual_source_end_seconds", "output_path", "sample_rate", "bit_depth", "channels", "duration_seconds", "LUFS_before", "LUFS_after", "applied_gain_db", "true_peak_before_dbfs", "true_peak_after_dbfs", "clipping", "fade_in_ms", "fade_out_ms", "sha256", "validation_status", "notes"])
    _write_csv(alignment_root / "six_mix_alignment_summary.csv", alignment_summary, ["artist", "song", "six_mix_order", "pairwise_comparisons", "maximum_offset_ms", "automatic_status", "rapid_switch_path", "notes"])
    _write_csv(alignment_root / "six_mix_pairwise_alignment.csv", alignment_rows, ["artist", "song", "mix_i_original_name", "mix_j_original_name", "lag_frames", "millisecond_offset", "maximum_correlation", "alignment_status", "notes"])
    _write_csv(alignment_root / "manual_six_mix_alignment_review.csv", manual_alignment, ["artist", "song", "six_mix_order", "automatic_status", "maximum_offset_ms", "waveform_checked", "rapid_switch_checked", "audible_timing_jump", "timing_drift", "alignment_acceptable", "reviewer", "review_date", "comments"])

    review_form_rows = [
        {
            "artist": row["artist"],
            "song": row["song"],
            "rating_condition": row["rating_condition"],
            "original_mix_name": row["original_mix_name"],
            "mean_previous_preference": row["mean_previous_preference"],
            "acoustic_pool_rank": row["acoustic_pool_rank"],
            "stereo_imbalance_qc_flag": row["stereo_imbalance_qc_flag"],
            "clipping_qc_flag": row["clipping_qc_flag"],
            "alignment_status": row["alignment_status"],
            "technical_qc_status": row["technical_qc_status"],
            "waveform_checked": "",
            "rapid_switch_checked": "",
            "technically_acceptable": "",
            "sufficiently_distinct": "",
            "suitable_for_six_mix_trial": "",
            "retain": "",
            "replacement_requested": "",
            "reviewer": "",
            "review_date": "",
            "comments": "",
        }
        for row in proposal_rows
    ]
    review_form_cols = ["artist", "song", "rating_condition", "original_mix_name", "mean_previous_preference", "acoustic_pool_rank", "stereo_imbalance_qc_flag", "clipping_qc_flag", "alignment_status", "technical_qc_status", "waveform_checked", "rapid_switch_checked", "technically_acceptable", "sufficiently_distinct", "suitable_for_six_mix_trial", "retain", "replacement_requested", "reviewer", "review_date", "comments"]
    _write_csv(supervisor / "six_mix_review_form.csv", review_form_rows, review_form_cols)

    shutil.copy2(tables / "six_mix_proposals.csv", supervisor / "six_mix_proposals.csv")
    for report_name in ("six_mix_proposal_report.md", "six_mix_technical_qc_report.md"):
        pass
    for item in items:
        src = review_audio / item.song / f"{safe_original_mix_filename(item.original_mix_name)}_28sec.wav"
        dst = supervisor / "audio" / item.song / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    for path in rapid_paths:
        dst = supervisor / "rapid_switch" / path.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)
    useful_figures = []
    for song in EXPECTED_SONGS:
        diag = diagnostics / song
        for filename in ("six_mix_acoustic_overview.png", "pairwise_distance_heatmap.png", "prior_mean_preference_95ci.png", "technical_qc_summary.png"):
            useful_figures.append(diag / filename)
        useful_figures.append(alignment_root / f"{song}_six_mix_waveforms.png")
        useful_figures.append(alignment_root / f"{song}_six_mix_transient_zoom.png")
    for path in useful_figures:
        dst = supervisor / "figures" / path.parent.name / path.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)
    for path in (tables / "six_mix_pairwise_distances.csv", tables / "six_mix_acoustic_summary.csv", tables / "six_mix_rating_summary.csv", tables / "six_mix_audio_manifest.csv", qc_root / "six_mix_technical_qc.csv", alignment_root / "six_mix_alignment_summary.csv", alignment_root / "six_mix_pairwise_alignment.csv"):
        dst = supervisor / "tables" / path.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)

    def report_table(rows: list[dict[str, object]], cols: list[str]) -> list[str]:
        lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
        for row in rows:
            lines.append("| " + " | ".join(_fmt(row.get(col, "")) for col in cols) + " |")
        return lines

    proposal_report = [
        "# Six-Mix Proposal Report",
        "",
        "This proposal layer responds to the supervisor request to inspect whether each main study song can support six mixes rather than a three-mix triplet.",
        "",
        "No frontend implementation was performed. No participant-facing A-F labels were created. The four selected songs, approved 28-second excerpts, corrected acoustic methodology, Phase 2B Similar/Wide triplets and existing three-mix outputs were left unchanged.",
        "",
        "The six-mix set for each song is the union of the non-overlapping Similar Ratings and Wide Ratings triplets. Acoustic diversity continues to use rms_mean, crest_factor_mean, stereo_width, and Bark mid/side features through the corrected within-song PCA distance outputs. Stereo imbalance remains QC-only and was not introduced into acoustic distance calculations.",
        "",
        "Historical Brecht preference ratings are used only as second-stage within-song stratification context. They are not interpreted as ground-truth quality scores.",
        "",
        f"Review WAVs were loudness-normalised to {TARGET_LUFS} LUFS integrated, exported as 44.1 kHz stereo PCM 24-bit, and retained the 5 ms half-cosine boundary fade.",
        "",
        "## Selected Sets",
        "",
        *report_table(proposal_rows, ["song", "rating_condition", "original_mix_name", "mean_previous_preference", "technical_qc_status"]),
        "",
        "## Acoustic Summary",
        "",
        *report_table(acoustic_summary, ["song", "similar_triplet_minimum_distance", "wide_triplet_minimum_distance", "full_six_mix_minimum_distance", "full_six_mix_mean_distance", "full_six_mix_maximum_distance", "near_duplicate_count"]),
        "",
        "## Rating Summary",
        "",
        *report_table(rating_summary, ["song", "similar_rating_spread", "wide_rating_spread", "full_six_mix_rating_range", "minimum_rating_count", "maximum_rating_count"]),
        "",
        "## Alignment Summary",
        "",
        *report_table(alignment_summary, ["song", "maximum_offset_ms", "automatic_status"]),
        "",
        "Usability burden still needs to be tested separately before any six-mix design is treated as approved.",
    ]
    qc_report = ["# Six-Mix Technical QC Report", ""]
    for song in EXPECTED_SONGS:
        qc_report.extend([f"## {song}", ""])
        for row in [q for q in qc_rows if q["song"] == song]:
            qc_report.extend(
                [
                    f"### {row['original_mix_name']}",
                    "",
                    f"- Rating condition: {row['rating_condition']}",
                    f"- Technical QC status: {row['technical_qc_status']}",
                    f"- Stereo imbalance QC flag: {row['stereo_imbalance_qc_flag']}",
                    f"- Clipping QC flag: {row['clipping_qc_flag']}",
                    f"- Alignment status: {row['alignment_automatic_status']} ({_fmt(row['maximum_alignment_offset_ms'])} ms maximum six-mix offset for song)",
                    f"- Review reasons: {row['qc_reasons'] or 'none'}",
                    "",
                ]
            )
    methods = [
        "# Six-Mix Methods Summary",
        "",
        "The six-mix proposal layer extends the revised stimulus-selection pipeline without changing the established selection methodology. For each of the four main songs, the Phase 2B Similar Ratings triplet and the non-overlapping Wide Ratings triplet were combined to form a six-mix review set.",
        "",
        "Corrected acoustic diversity was not recomputed from raw features. The analysis uses the canonical v2 pairwise distances and candidate-pool metadata. Stereo imbalance is retained as a technical QC variable only and is excluded from diversity, PCA, medoid, and coverage calculations.",
        "",
        "Prior preference ratings are interpreted within song and are used only to document the historical preference structure of the selected mixes.",
        "",
        f"All review audio was exported at {TARGET_LUFS} LUFS integrated, 44.1 kHz stereo PCM 24-bit, exactly 28 seconds, with 5 ms half-cosine anti-click fades at both boundaries.",
    ]
    for path, lines in (
        (reports / "six_mix_proposal_report.md", proposal_report),
        (reports / "six_mix_technical_qc_report.md", qc_report),
        (reports / "six_mix_methods_summary.md", methods),
    ):
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for report_name in ("six_mix_proposal_report.md", "six_mix_technical_qc_report.md"):
        shutil.copy2(reports / report_name, supervisor / report_name)
    (supervisor / "README.md").write_text(
        "\n".join(
            [
                "# Six-Mix Supervisor Review Package",
                "",
                "This package contains the six-mix proposal layer for supervisor and pilot review only.",
                "",
                "The audio files use original Mix Evaluation Dataset mix names. No A-F participant labels are included and no frontend implementation has been performed.",
                "",
                "The six mixes per song are the union of the canonical Similar Ratings and Wide Ratings triplets. Stereo imbalance remains QC-only and was not used in acoustic diversity calculations.",
                "",
                f"Review WAVs are loudness-normalised to {TARGET_LUFS} LUFS integrated and exported as 44.1 kHz stereo PCM 24-bit with 5 ms half-cosine boundary fades.",
                "",
                "Supervisor approval and usability pilot review are required before any six-mix design can be treated as final study stimuli.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "\n".join(
            [
                "# Six-Mix Proposals",
                "",
                "New versioned proposal layer for the four main study songs. Existing triplet outputs, final stimuli and frontend configuration are not modified.",
                "",
                "- `tables/`: proposal, acoustic, rating and audio manifests.",
                "- `qc/`: technical QC table.",
                "- `alignment_review/`: combined six-mix alignment tables, figures and rapid-switch WAVs.",
                "- `diagnostics/`: per-song diagnostic figures.",
                "- `review_audio/`: loudness-normalised original-name WAVs.",
                "- `supervisor_package/`: compact package for review.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    package_rows = []
    for path in _iter_files(supervisor):
        package_rows.append({"relative_path": str(path.relative_to(supervisor)).replace("\\", "/"), "bytes": path.stat().st_size, "sha256": _sha256(path)})
    _write_csv(supervisor / "package_manifest.csv", package_rows, ["relative_path", "bytes", "sha256"])
    zip_hash = _package(root, output_root / "09_six_mix_proposals.zip")

    after_hashes = _hash_tree(protected_paths, repo_root)
    protected_unchanged = before_hashes == after_hashes
    validation = {
        "protected_unchanged": protected_unchanged,
        "before": before_hashes,
        "after": after_hashes,
        "changed": sorted(path for path in set(before_hashes) | set(after_hashes) if before_hashes.get(path) != after_hashes.get(path)),
        "frontend_files_modified_by_pipeline": False,
        "final_stimuli_modified_by_pipeline": False,
        "zip_sha256": zip_hash,
    }
    validation_path = root / "validation" / "protected_outputs_hashes.json"
    validation_path.parent.mkdir(parents=True, exist_ok=True)
    validation_path.write_text(json.dumps(validation, indent=2), encoding="utf-8")

    return {
        "proposal_rows": len(proposal_rows),
        "songs": len(EXPECTED_SONGS),
        "review_wavs": len(list(review_audio.rglob("*.wav"))),
        "rapid_switch_files": len(rapid_paths),
        "figures": len(figure_paths),
        "technical_fail_count": sum(1 for row in qc_rows if row["technical_qc_status"] == "FAIL"),
        "technical_review_count": sum(1 for row in qc_rows if row["technical_qc_status"] == "REVIEW"),
        "alignment_statuses": {row["song"]: row["automatic_status"] for row in alignment_summary},
        "protected_outputs_unchanged": protected_unchanged,
        "zip_path": output_root / "09_six_mix_proposals.zip",
        "zip_sha256": zip_hash,
        "report": reports / "six_mix_proposal_report.md",
        "supervisor_package": supervisor,
    }
