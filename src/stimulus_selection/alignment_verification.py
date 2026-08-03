from __future__ import annotations

"""Phase 2C alignment QA for rating-stratified recommendation triplets."""

import csv
import hashlib
import itertools
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import soundfile as sf
from scipy import signal

from stimulus_selection.config import SelectionConfig
from stimulus_selection.output_layout import (
    alignment_verification_audio,
    alignment_verification_figures,
    alignment_verification_reports,
    alignment_verification_root,
    alignment_verification_tables,
    first_existing,
)
from stimulus_selection.paths import ensure_output_root


EXPECTED_SR = 44100
EXPECTED_SECONDS = 28.0
SWITCH_SECONDS = 2.0
CROSSFADE_MS = 5.0


@dataclass(frozen=True)
class AlignmentVerificationResult:
    output_root: Path
    report_path: Path
    triplets_verified: int
    pairwise_rows: int
    rapid_switch_files: int
    figures: int
    maximum_ms_offset: float


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


def _hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_wav(path: Path) -> tuple[np.ndarray, int]:
    data, sr = sf.read(str(path), always_2d=True, dtype="float32")
    if sr != EXPECTED_SR:
        raise ValueError(f"{path} has sample rate {sr}, expected {EXPECTED_SR}.")
    expected = int(round(EXPECTED_SR * EXPECTED_SECONDS))
    if data.shape[0] != expected:
        raise ValueError(f"{path} has {data.shape[0]} samples, expected {expected}.")
    if data.shape[1] != 2:
        raise ValueError(f"{path} has {data.shape[1]} channels, expected stereo.")
    return data, sr


def _mono_envelope(audio: np.ndarray, hop: int = 512, frame: int = 2048) -> np.ndarray:
    mono = audio.mean(axis=1)
    if mono.size < frame:
        mono = np.pad(mono, (0, frame - mono.size))
    starts = np.arange(0, mono.size - frame + 1, hop)
    env = np.empty(starts.size, dtype=np.float64)
    for idx, start in enumerate(starts):
        seg = mono[start:start + frame]
        env[idx] = math.sqrt(float(np.mean(seg * seg)) + 1e-12)
    env = np.diff(np.log1p(env), prepend=env[0])
    env = env - float(np.mean(env))
    sd = float(np.std(env))
    return env / sd if sd > 1e-12 else env


def pairwise_alignment(a: np.ndarray, b: np.ndarray, sr: int) -> dict[str, float | str]:
    hop = 512
    env_a = _mono_envelope(a, hop=hop)
    env_b = _mono_envelope(b, hop=hop)
    max_lag_ms = 100.0
    max_lag_frames = int(round((max_lag_ms / 1000.0) * sr / hop))
    corr = signal.correlate(env_b, env_a, mode="full", method="fft")
    lags = signal.correlation_lags(env_b.size, env_a.size, mode="full")
    mask = np.abs(lags) <= max_lag_frames
    corr = corr[mask]
    lags = lags[mask]
    denom = max(float(np.linalg.norm(env_a) * np.linalg.norm(env_b)), 1e-12)
    norm = corr / denom
    best = int(np.argmax(norm))
    lag_frames = int(lags[best])
    sample_offset = int(lag_frames * hop)
    ms_offset = sample_offset / sr * 1000.0
    peak = float(norm[best])
    abs_ms = abs(ms_offset)
    if abs_ms <= 10.0 and peak >= 0.60:
        quality = "PASS"
    elif abs_ms <= 30.0 and peak >= 0.35:
        quality = "REVIEW"
    else:
        quality = "FAIL"
    return {
        "lag_frames": lag_frames,
        "sample_offset": sample_offset,
        "millisecond_offset": ms_offset,
        "maximum_correlation": peak,
        "peak_correlation": peak,
        "alignment_confidence": max(0.0, min(1.0, peak)),
        "common_overlap_seconds": EXPECTED_SECONDS - abs(sample_offset) / sr,
        "alignment_quality": quality,
    }


def _transient_times(audio: np.ndarray, sr: int, count: int = 8) -> np.ndarray:
    env = _mono_envelope(audio)
    peaks, _ = signal.find_peaks(env, distance=10)
    if peaks.size == 0:
        return np.asarray([], dtype=float)
    strongest = peaks[np.argsort(env[peaks])[-count:]]
    return np.sort(strongest * 512 / sr)


def _save_waveform_figures(
    figure_root: Path,
    song: str,
    condition: str,
    names: list[str],
    audios: list[np.ndarray],
    pair_rows: list[dict[str, object]],
) -> list[Path]:
    out = figure_root / song / condition
    out.mkdir(parents=True, exist_ok=True)
    sr = EXPECTED_SR
    t = np.arange(audios[0].shape[0]) / sr
    offsets = {str(row["mix_j"]): float(row["millisecond_offset"]) / 1000.0 for row in pair_rows if row["mix_i"] == names[0]}
    offsets[names[0]] = 0.0
    transients = _transient_times(audios[0], sr)
    paths: list[Path] = []
    fig, axes = plt.subplots(3, 1, figsize=(11, 6), sharex=True)
    for ax, name, audio in zip(axes, names, audios):
        mono = audio.mean(axis=1)
        ax.plot(t, mono, linewidth=0.45)
        ax.set_ylabel(name)
        for tr in transients:
            ax.axvline(tr, color="#d62728", alpha=0.25, linewidth=0.8)
        if name in offsets and offsets[name]:
            ax.axvline(max(0.0, min(EXPECTED_SECONDS, offsets[name])), color="#1f77b4", linestyle="--", linewidth=0.8)
    axes[-1].set_xlabel("seconds")
    fig.suptitle(f"{song} / {condition}: stacked waveform alignment")
    fig.tight_layout()
    path = out / "stacked_waveforms.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    paths.append(path)
    centre = float(transients[0]) if transients.size else 5.0
    lo, hi = max(0.0, centre - 0.25), min(EXPECTED_SECONDS, centre + 0.25)
    fig, axes = plt.subplots(3, 1, figsize=(11, 6), sharex=True)
    mask = (t >= lo) & (t <= hi)
    for ax, name, audio in zip(axes, names, audios):
        ax.plot(t[mask], audio.mean(axis=1)[mask], linewidth=0.7)
        ax.set_ylabel(name)
        ax.axvline(centre, color="#d62728", alpha=0.5, linewidth=0.9)
    axes[-1].set_xlabel("seconds")
    fig.suptitle(f"{song} / {condition}: strongest-transient zoom")
    fig.tight_layout()
    zoom_path = out / "strongest_transient_zoom.png"
    fig.savefig(zoom_path, dpi=160)
    plt.close(fig)
    paths.append(zoom_path)
    return paths


def _rapid_switch(audios: list[np.ndarray], sr: int) -> np.ndarray:
    segment = int(round(SWITCH_SECONDS * sr))
    fade = int(round((CROSSFADE_MS / 1000.0) * sr))
    target = int(round(EXPECTED_SECONDS * sr))
    pieces = []
    pos = 0
    idx = 0
    while pos < target:
        source = audios[idx % len(audios)]
        end = min(pos + segment, target)
        pieces.append(source[pos:end].copy())
        pos = end
        idx += 1
    out = pieces[0]
    for piece in pieces[1:]:
        if fade > 0 and out.shape[0] >= fade and piece.shape[0] >= fade:
            ramp = np.linspace(0.0, 1.0, fade, endpoint=True, dtype=np.float32)[:, None]
            overlap = out[-fade:] * (1.0 - ramp) + piece[:fade] * ramp
            out = np.vstack([out[:-fade], overlap, piece[fade:]])
        else:
            out = np.vstack([out, piece])
    if out.shape[0] < target:
        out = np.pad(out, ((0, target - out.shape[0]), (0, 0)))
    return out[:target]


def run_alignment_verification(config: SelectionConfig) -> AlignmentVerificationResult:
    output_root = ensure_output_root(config)
    shortlist_path = first_existing(output_root, "06_rating_stratification/tables/supervisor_shortlist.csv")
    source_audio = first_existing(output_root, "06_rating_stratification/candidate_review_audio")
    root = alignment_verification_root(output_root)
    tables = alignment_verification_tables(output_root)
    figures = alignment_verification_figures(output_root)
    audio_root = alignment_verification_audio(output_root)
    reports = alignment_verification_reports(output_root)
    for folder in (tables, figures, audio_root, reports):
        folder.mkdir(parents=True, exist_ok=True)
    shortlist = pd.read_csv(shortlist_path, dtype=str, keep_default_na=False)
    pair_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    checklist_rows: list[dict[str, object]] = []
    copied_rows: list[dict[str, object]] = []
    figure_paths: list[Path] = []
    rapid_files: list[Path] = []
    for _, row in shortlist.iterrows():
        song = row["song"]
        condition = row["condition"]
        names = row["original_mix_names"].split("|")
        audios = []
        source_paths = []
        for name in names:
            src = source_audio / song / condition / f"{name}_28sec.wav"
            dst = audio_root / song / condition / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            audio, sr = _read_wav(dst)
            audios.append(audio)
            source_paths.append(src)
            copied_rows.append({
                "song": song,
                "condition": condition,
                "original_mix_name": name,
                "source_path": str(src),
                "review_path": str(dst),
                "source_sha256": _hash(src),
                "review_sha256": _hash(dst),
                "hash_match": _hash(src) == _hash(dst),
            })
        triplet_pair_rows: list[dict[str, object]] = []
        for (i, name_i), (j, name_j) in itertools.combinations(list(enumerate(names)), 2):
            metrics = pairwise_alignment(audios[i], audios[j], EXPECTED_SR)
            pair_label = f"{name_i}-{name_j}"
            pair_row = {
                "song": song,
                "condition": condition,
                "triplet_id": row["triplet_id"],
                "pair": pair_label,
                "mix_i": name_i,
                "mix_j": name_j,
                **metrics,
                "thresholds": "PASS <=10 ms and correlation >=0.60; REVIEW <=30 ms and correlation >=0.35; otherwise FAIL",
            }
            pair_rows.append(pair_row)
            triplet_pair_rows.append(pair_row)
        fig_paths = _save_waveform_figures(figures, song, condition, names, audios, triplet_pair_rows)
        figure_paths.extend(fig_paths)
        rapid = _rapid_switch(audios, EXPECTED_SR)
        rapid_path = audio_root / song / condition / "RapidSwitch.wav"
        sf.write(str(rapid_path), rapid.astype(np.float32, copy=False), EXPECTED_SR, subtype="PCM_16")
        rapid_files.append(rapid_path)
        qualities = [str(p["alignment_quality"]) for p in triplet_pair_rows]
        max_ms = max(abs(float(p["millisecond_offset"])) for p in triplet_pair_rows)
        min_corr = min(float(p["maximum_correlation"]) for p in triplet_pair_rows)
        automatic = "PASS" if all(q == "PASS" for q in qualities) else ("FAIL" if any(q == "FAIL" for q in qualities) else "REVIEW")
        summary_rows.append({
            "song": song,
            "condition": condition,
            "mix_names": "|".join(names),
            "maximum_lag_samples": max(abs(int(p["sample_offset"])) for p in triplet_pair_rows),
            "maximum_ms_offset": max_ms,
            "minimum_correlation": min_corr,
            "confidence": min(float(p["alignment_confidence"]) for p in triplet_pair_rows),
            "automatic_result": automatic,
            "visual_result": "figures_generated",
            "manual_status": "pending",
            "overall_recommendation": "suitable_for_supervisor_review" if automatic != "FAIL" else "requires_alignment_review_before_supervisor_review",
        })
        checklist_rows.append({
            "song": song,
            "condition": condition,
            "mixes": "|".join(names),
            "automatic_pass": automatic == "PASS",
            "waveform_checked": "",
            "rapid_switch_checked": "",
            "audible_alignment_issue": "",
            "alignment_accept": "",
            "reviewer": "",
            "date": "",
            "comments": "",
        })
    _write_csv(tables / "pairwise_alignment_verification.csv", pair_rows, ["song", "condition", "triplet_id", "pair", "mix_i", "mix_j", "lag_frames", "sample_offset", "millisecond_offset", "maximum_correlation", "peak_correlation", "alignment_confidence", "common_overlap_seconds", "alignment_quality", "thresholds"])
    _write_csv(tables / "alignment_summary.csv", summary_rows, ["song", "condition", "mix_names", "maximum_lag_samples", "maximum_ms_offset", "minimum_correlation", "confidence", "automatic_result", "visual_result", "manual_status", "overall_recommendation"])
    _write_csv(tables / "manual_alignment_review.csv", checklist_rows, ["song", "condition", "mixes", "automatic_pass", "waveform_checked", "rapid_switch_checked", "audible_alignment_issue", "alignment_accept", "reviewer", "date", "comments"])
    _write_csv(tables / "review_audio_manifest.csv", copied_rows, ["song", "condition", "original_mix_name", "source_path", "review_path", "source_sha256", "review_sha256", "hash_match"])
    root.joinpath("README.md").write_text(
        "\n".join([
            "# Phase 2C Alignment Verification",
            "",
            "This phase does not change selection. It only verifies alignment quality for the Phase 2B recommended triplets.",
            "",
            "- Acoustic candidate pools are unchanged.",
            "- Prior rating summaries are unchanged.",
            "- Recommendation sets are unchanged.",
            "- Final stimuli and frontend files are unchanged.",
            "- Rapid-switch files are listening-review aids, not participant stimuli.",
            "",
        ]),
        encoding="utf-8",
    )
    report_lines = [
        "# Alignment Verification Report",
        "",
        "Phase 2C verifies the Phase 2B recommended mixes using automatic pairwise alignment checks, stacked waveform figures, transient zoom figures, and rapid-switch listening files.",
        "",
        "Automatic procedure: each 28-second stereo review WAV is reduced to a mono onset/RMS-change envelope. Pairwise normalized cross-correlation is searched within +/-100 ms. PASS is <=10 ms and correlation >=0.60; REVIEW is <=30 ms and correlation >=0.35; otherwise FAIL.",
        "",
        "Visual inspection: `figures/` contains one stacked waveform and one strongest-transient zoom per triplet.",
        "",
        "Perceptual inspection: `review_audio/` contains the original copied WAVs plus `RapidSwitch.wav` for each triplet. Rapid-switch files alternate 2-second segments with 5 ms crossfades and no loudness normalization.",
        "",
        "## Triplet Summary",
        "",
        "| Song | Condition | Maximum offset ms | Minimum correlation | Automatic result | Overall recommendation |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in summary_rows:
        report_lines.append(f"| {row['song']} | {row['condition']} | {float(row['maximum_ms_offset']):.3f} | {float(row['minimum_correlation']):.3f} | {row['automatic_result']} | {row['overall_recommendation']} |")
    requiring = [r for r in summary_rows if r["automatic_result"] != "PASS"]
    report_lines.extend(["", "## Triplets Requiring Review", ""])
    if requiring:
        for row in requiring:
            report_lines.append(f"- {row['song']} / {row['condition']}: {row['automatic_result']}, max offset {float(row['maximum_ms_offset']):.3f} ms.")
    else:
        report_lines.append("- None by the automatic thresholds. Manual perceptual review remains pending.")
    report_lines.extend([
        "",
        "## Dissertation Statement",
        "",
        "Alignment of the recommended stimuli was checked automatically by pairwise envelope cross-correlation, visually through stacked waveform and transient plots, and perceptually through rapid-switch listening files. Final acceptance remains subject to supervisor/manual review.",
        "",
    ])
    report_path = reports / "alignment_verification_report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    max_offset = max(abs(float(row["millisecond_offset"])) for row in pair_rows) if pair_rows else 0.0
    return AlignmentVerificationResult(output_root, report_path, len(summary_rows), len(pair_rows), len(rapid_files), len(figure_paths), max_offset)
