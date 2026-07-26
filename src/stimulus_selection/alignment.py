from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
from scipy import signal

from stimulus_selection.audio_decode import DecodedAudio, decode_audio, detect_decoder_environment, ensure_sample_rate, write_wav
from stimulus_selection.config import SelectionConfig
from stimulus_selection.output_layout import first_existing, stage1_tables, stage2_diagnostics, stage2_reports, stage2_tables

ALIGNMENT_COLUMNS = [
    "artist", "song", "mix_id", "institution", "source_path", "reference_mix_id", "decoder_backend",
    "original_sample_rate", "decoded_channels", "original_duration_seconds", "estimated_lag_seconds",
    "refined_lag_seconds", "alignment_score", "second_best_score", "confidence_margin", "alignment_confidence",
    "aligned_start_seconds", "aligned_end_seconds", "usable_overlap_seconds", "retained_for_excerpt_selection",
    "exclusion_reason", "notes",
]

OVERLAP_COLUMNS = [
    "artist", "song", "reference_mix_id", "retained_mix_count", "excluded_mix_count", "common_aligned_start_seconds",
    "common_aligned_end_seconds", "common_overlap_seconds", "target_excerpt_seconds", "sufficient_overlap",
    "minimum_alignment_confidence", "notes",
]

CANDIDATE_COLUMNS = [
    "artist", "song", "candidate_rank", "aligned_start_seconds", "aligned_end_seconds", "reference_file_start_seconds",
    "reference_file_end_seconds", "activity_score", "onset_score", "spectral_activity_score", "silence_penalty",
    "boundary_penalty", "cross_mix_consistency_score", "total_score", "notes",
]

SYSTEM_MARKERS = ("mg", "mixgenius", "auto", "robot")


@dataclass
class MixAudio:
    row: dict[str, str]
    decoded: DecodedAudio
    mono: np.ndarray
    analysis: np.ndarray
    representation: np.ndarray
    lag: float = 0.0
    score: float = 1.0
    second_best: float = 0.0
    margin: float = 1.0
    confidence: float = 1.0
    retained: bool = True
    exclusion_reason: str = ""
    notes: str = ""


@dataclass(frozen=True)
class Stage2Result:
    decoder_backend_counts: dict[str, int]
    retained_counts: dict[str, int]
    excluded_counts: dict[str, int]
    confidence_summary: dict[str, str]
    common_overlap: dict[str, float]
    top_candidates: dict[str, list[dict[str, str]]]
    preview_files: list[str]
    manual_review: list[str]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _f(value: float) -> str:
    if not math.isfinite(value):
        return ""
    return f"{value:.6f}"


def _song_key(row: dict[str, str]) -> str:
    return f"{row['artist']} - {row['song']}"


def _is_human_primary(row: dict[str, str], config: SelectionConfig) -> tuple[bool, str]:
    text = " ".join([row.get("mix_id", ""), row.get("mixer_id", ""), row.get("mixer_institution_code", ""), row.get("institution_name", ""), row.get("filename", "")]).lower()
    if any(marker in text for marker in SYSTEM_MARKERS):
        return False, "automated_or_system_generated"
    if row.get("is_system_generated") == "true" or row.get("institution_category") == "automated_system":
        return False, "automated_or_system_generated"
    if row.get("valid_for_analysis") != "true":
        return False, row.get("exclusion_reason") or "stage1_invalid"
    if row.get("extension", "").lower() not in config.allowed_extensions:
        return False, "unsupported_extension"
    return True, ""


def _mono(samples: np.ndarray) -> np.ndarray:
    if samples.ndim == 1:
        return samples.astype(np.float32)
    return samples.mean(axis=1).astype(np.float32)


def _normalise(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    if x.size == 0:
        return x
    x = x - float(np.mean(x))
    scale = float(np.std(x))
    if scale < 1e-8:
        return np.zeros_like(x)
    return x / scale


def _frame_signal(x: np.ndarray, frame: int, hop: int) -> np.ndarray:
    if x.size < frame:
        return x.reshape(1, -1)
    count = 1 + (x.size - frame) // hop
    shape = (count, frame)
    strides = (x.strides[0] * hop, x.strides[0])
    return np.lib.stride_tricks.as_strided(x, shape=shape, strides=strides)


def _representation(x: np.ndarray, sample_rate: int, use_onset: bool = True) -> np.ndarray:
    frame = max(256, int(0.046 * sample_rate))
    hop = max(64, int(0.023 * sample_rate))
    frames = _frame_signal(x, frame, hop) * np.hanning(frame).astype(np.float32)
    rms = np.sqrt(np.mean(frames**2, axis=1) + 1e-12)
    if not use_onset:
        return _normalise(rms)
    spectra = np.abs(np.fft.rfft(frames, axis=1))
    flux = np.maximum(0.0, np.diff(spectra, axis=0, prepend=spectra[:1])).mean(axis=1)
    rep = 0.55 * _normalise(np.log1p(flux)) + 0.45 * _normalise(np.log1p(rms))
    return _normalise(rep)


def _corr_at_lag(ref: np.ndarray, target: np.ndarray, lag_frames: int) -> float:
    if lag_frames >= 0:
        n = min(ref.size, target.size - lag_frames)
        if n <= 4:
            return -1.0
        a = ref[:n]
        b = target[lag_frames:lag_frames + n]
    else:
        n = min(ref.size + lag_frames, target.size)
        if n <= 4:
            return -1.0
        a = ref[-lag_frames:-lag_frames + n]
        b = target[:n]
    den = float(np.linalg.norm(a) * np.linalg.norm(b))
    if den < 1e-9:
        return -1.0
    return float(np.dot(a, b) / den)


def _estimate_lag(ref: np.ndarray, target: np.ndarray, hop_seconds: float, max_offset_seconds: float) -> tuple[float, float, float, float, bool]:
    max_lag = int(round(max_offset_seconds / hop_seconds))
    lags = np.arange(-max_lag, max_lag + 1)
    scores = np.array([_corr_at_lag(ref, target, int(lag)) for lag in lags], dtype=np.float32)
    best_i = int(np.argmax(scores))
    best_lag = int(lags[best_i])
    best = float(scores[best_i])
    exclusion = max(1, int(round(0.25 / hop_seconds)))
    masked = scores.copy()
    lo = max(0, best_i - exclusion)
    hi = min(masked.size, best_i + exclusion + 1)
    masked[lo:hi] = -np.inf
    second = float(np.max(masked)) if np.isfinite(masked).any() else 0.0
    margin = best - second
    confidence = max(0.0, min(1.0, 0.75 * max(best, 0.0) + 0.25 * max(min(margin / 0.15, 1.0), 0.0)))
    multimodal = second > 0.92 * best if best > 0 else True
    return best_lag * hop_seconds, best, second, margin, multimodal


def _refine_lag(ref: np.ndarray, target: np.ndarray, sample_rate: int, coarse_lag: float) -> tuple[float, float]:
    max_adjust = int(round(0.20 * sample_rate))
    base = int(round(coarse_lag * sample_rate))
    step = max(1, int(round(0.005 * sample_rate)))
    lags = range(base - max_adjust, base + max_adjust + 1, step)
    scores = [(_corr_at_lag(ref, target, lag), lag) for lag in lags]
    score, lag = max(scores, key=lambda item: item[0])
    return lag / sample_rate, float(score)


def _activity_curves(mixes: Iterable[MixAudio], start: float, end: float, hop: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    times = np.arange(start, end, hop, dtype=np.float32)
    curves = []
    onsets = []
    spectral = []
    for mix in mixes:
        mono = mix.mono
        sr = mix.decoded.sample_rate
        values = []
        specs = []
        frame = max(1, int(0.20 * sr))
        for t in times:
            file_t = float(t + mix.lag)
            s = int(round(file_t * sr))
            e = min(mono.size, s + frame)
            if s < 0 or e <= s:
                values.append(0.0)
                specs.append(0.0)
                continue
            seg = mono[s:e]
            values.append(float(np.sqrt(np.mean(seg**2) + 1e-12)))
            sp = np.abs(np.fft.rfft(seg * np.hanning(seg.size))) if seg.size > 8 else np.array([0.0])
            freqs = np.fft.rfftfreq(seg.size, 1.0 / sr) if seg.size > 8 else np.array([0.0])
            band = sp[(freqs >= 80) & (freqs <= 8000)]
            specs.append(float(np.mean(np.log1p(band))) if band.size else 0.0)
        curve = np.asarray(values, dtype=np.float32)
        curves.append(curve)
        onsets.append(np.maximum(0.0, np.diff(curve, prepend=curve[:1])))
        spectral.append(np.asarray(specs, dtype=np.float32))
    activity = np.vstack([_normalise(np.log1p(c)) for c in curves]) if curves else np.zeros((0, times.size))
    onset = np.vstack([_normalise(o) for o in onsets]) if onsets else np.zeros((0, times.size))
    spec = np.vstack([_normalise(s) for s in spectral]) if spectral else np.zeros((0, times.size))
    return times, activity, onset, spec


def _select_candidates(config: SelectionConfig, mixes: list[MixAudio], common_start: float, common_end: float) -> list[dict[str, float]]:
    target = config.target_excerpt_seconds
    hop = config.excerpt_selection.activity_hop_seconds
    start = common_start + config.excerpt_selection.avoid_first_seconds
    latest = common_end - config.excerpt_selection.avoid_last_seconds - target
    if latest < start:
        start = common_start
        latest = common_end - target
    if latest < start:
        return []
    times, activity, onset, spec = _activity_curves(mixes, common_start, common_end, hop)
    candidates: list[dict[str, float]] = []
    window_bins = max(1, int(round(target / hop)))
    starts = np.arange(start, latest + 1e-6, hop)
    for s in starts:
        i0 = int(np.searchsorted(times, s, side="left"))
        i1 = min(times.size, i0 + window_bins)
        if i1 - i0 < window_bins * 0.95:
            continue
        act = activity[:, i0:i1]
        ons = onset[:, i0:i1]
        spc = spec[:, i0:i1]
        raw = np.maximum(0.0, act)
        silence_prop = float(np.mean(raw < np.quantile(raw, config.excerpt_selection.minimum_activity_quantile))) if raw.size else 1.0
        activity_score = float(np.mean(act))
        onset_score = float(np.mean(ons))
        spectral_score = float(np.mean(spc))
        consistency = float(1.0 / (1.0 + np.mean(np.std(act, axis=0)))) if act.size else 0.0
        dist = min(s - common_start, common_end - (s + target))
        boundary_penalty = float(max(0.0, 1.0 - dist / max(config.excerpt_selection.avoid_first_seconds, 1.0)))
        silence_penalty = silence_prop
        total = activity_score + 0.55 * onset_score + 0.45 * spectral_score + 0.75 * consistency - 0.6 * silence_penalty - 0.4 * boundary_penalty
        candidates.append({
            "start": float(s), "end": float(s + target), "activity": activity_score, "onset": onset_score,
            "spectral": spectral_score, "silence": silence_penalty, "boundary": boundary_penalty,
            "consistency": consistency, "total": float(total),
        })
    selected = []
    min_sep = max(target * 0.20, 3.0)
    for cand in sorted(candidates, key=lambda x: x["total"], reverse=True):
        if all(abs(cand["start"] - old["start"]) >= min_sep for old in selected):
            selected.append(cand)
        if len(selected) >= config.excerpt_selection.candidate_count:
            break
    return selected


def _reference_mix(rows: list[dict[str, str]]) -> dict[str, str]:
    durations = [float(r.get("duration_seconds") or 0) for r in rows]
    median = float(np.median(durations))
    rates = [r.get("sample_rate", "") for r in rows]
    common_rate = max(set(rates), key=rates.count) if rates else ""
    def score(row: dict[str, str]) -> tuple[float, str]:
        dur_score = abs(float(row.get("duration_seconds") or 0) - median)
        rate_penalty = 0.0 if row.get("sample_rate") == common_rate else 1.0
        conf_penalty = 0.0 if row.get("institution_confidence") == "high" else 1.0
        dup_penalty = 0.2 if row.get("duplicate_audio_candidate") == "true" else 0.0
        return (dur_score + rate_penalty + conf_penalty + dup_penalty, row.get("mix_id", ""))
    return min(rows, key=score)


def _alignment_row(mix: MixAudio, ref_id: str) -> dict[str, str]:
    aligned_start = -mix.lag
    aligned_end = mix.decoded.duration_seconds - mix.lag
    reason = mix.exclusion_reason
    return {
        "artist": mix.row["artist"], "song": mix.row["song"], "mix_id": mix.row["mix_id"],
        "institution": mix.row.get("mixer_institution_code") or mix.row.get("institution_name", ""),
        "source_path": mix.row["source_path"], "reference_mix_id": ref_id, "decoder_backend": mix.decoded.backend,
        "original_sample_rate": str(mix.decoded.sample_rate), "decoded_channels": str(mix.decoded.channels),
        "original_duration_seconds": _f(mix.decoded.duration_seconds), "estimated_lag_seconds": _f(mix.lag),
        "refined_lag_seconds": _f(mix.lag), "alignment_score": _f(mix.score), "second_best_score": _f(mix.second_best),
        "confidence_margin": _f(mix.margin), "alignment_confidence": _f(mix.confidence),
        "aligned_start_seconds": _f(aligned_start), "aligned_end_seconds": _f(aligned_end),
        "usable_overlap_seconds": _f(max(0.0, aligned_end - aligned_start)),
        "retained_for_excerpt_selection": str(mix.retained).lower(), "exclusion_reason": reason, "notes": mix.notes,
    }


def _render_preview(config: SelectionConfig, song_slug: str, mix: MixAudio, rank: int, start: float, end: float) -> Path:
    sr = config.target_sample_rate
    file_start = max(0.0, start + mix.lag)
    s = int(round(file_start * mix.decoded.sample_rate))
    e = int(round((end + mix.lag) * mix.decoded.sample_rate))
    samples = mix.decoded.samples[max(0, s):min(mix.decoded.samples.shape[0], e)]
    target_len = int(round((end - start) * mix.decoded.sample_rate))
    if samples.shape[0] < target_len:
        pad = np.zeros((target_len - samples.shape[0], samples.shape[1]), dtype=np.float32)
        samples = np.vstack([samples, pad])
    samples = ensure_sample_rate(samples, mix.decoded.sample_rate, sr)
    fade = int(round(config.fade_seconds * sr))
    if fade > 0 and samples.shape[0] > fade * 2:
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        samples[:fade] *= ramp[:, None]
        samples[-fade:] *= ramp[::-1, None]
    name = f"c{rank:02d}_{mix.row.get('mixer_institution_code','mix')}_{mix.row['mix_id']}.wav"
    path = config.preview_excerpt_root / song_slug / name
    write_wav(path, samples, sr)
    return path


def _plot_diagnostics(output_root: Path, song_slug: str, mixes: list[MixAudio], common: tuple[float, float], candidates: list[dict[str, float]]) -> None:
    fig_root = stage2_diagnostics(output_root) / "diagnostic_figures" / song_slug
    fig_root.mkdir(parents=True, exist_ok=True)
    lags = [m.lag for m in mixes]
    conf = [m.confidence for m in mixes]
    labels = [m.row.get("mixer_id") or m.row["mix_id"] for m in mixes]
    plt.figure(figsize=(8, 4)); plt.hist(lags, bins=12); plt.xlabel("Lag seconds"); plt.ylabel("Mix count"); plt.tight_layout(); plt.savefig(fig_root / "alignment_lag_distribution.png"); plt.close()
    plt.figure(figsize=(10, 4)); plt.bar(range(len(conf)), conf); plt.xticks(range(len(conf)), labels, rotation=90, fontsize=6); plt.axhline(0.70, color="r", linestyle="--"); plt.ylabel("Confidence"); plt.tight_layout(); plt.savefig(fig_root / "alignment_confidence_by_mix.png"); plt.close()
    plt.figure(figsize=(10, 3))
    for i, m in enumerate(mixes):
        plt.plot([-m.lag, m.decoded.duration_seconds - m.lag], [i, i], linewidth=5)
    plt.axvspan(common[0], common[1], color="green", alpha=0.2); plt.xlabel("Aligned seconds"); plt.tight_layout(); plt.savefig(fig_root / "common_overlap_timeline.png"); plt.close()
    if mixes:
        times, activity, _, _ = _activity_curves(mixes, common[0], common[1], 0.25)
        curve = np.mean(activity, axis=0) if activity.size else np.zeros_like(times)
        plt.figure(figsize=(10, 4)); plt.plot(times, curve)
        for c in candidates:
            plt.axvspan(c["start"], c["end"], alpha=0.18)
        plt.xlabel("Aligned seconds"); plt.ylabel("Mean activity z-score"); plt.tight_layout(); plt.savefig(fig_root / "activity_curve_with_candidate_windows.png"); plt.close()


def run_align_excerpts(config: SelectionConfig) -> Stage2Result:
    env = detect_decoder_environment()
    print(f"ffmpeg: {env.ffmpeg_version}")
    print(f"ffprobe: {env.ffprobe_version}")
    if not env.ffmpeg_path:
        print("ffmpeg unavailable; continuing with configured decoder fallbacks.")
    inventory_path = first_existing(
        config.output_root,
        "01_dataset_and_song_selection/tables/mix_inventory.csv",
        "mix_inventory.csv",
    )
    rows = _read_csv(inventory_path)
    wanted = {(s["artist"], s["song"]) for s in config.primary_candidate_songs}
    rows = [r for r in rows if (r["artist"], r["song"]) in wanted]

    alignment_rows: list[dict[str, str]] = []
    overlap_rows: list[dict[str, str]] = []
    candidate_rows: list[dict[str, str]] = []
    checklist_rows: list[dict[str, str]] = []
    preview_files: list[str] = []
    manual_review: list[str] = []
    backend_counts: dict[str, int] = {}
    retained_counts: dict[str, int] = {}
    excluded_counts: dict[str, int] = {}
    confidence_summary: dict[str, str] = {}
    common_overlap: dict[str, float] = {}
    top_by_song: dict[str, list[dict[str, str]]] = {}

    for artist, song in sorted(wanted):
        song_rows_all = [r for r in rows if r["artist"] == artist and r["song"] == song]
        eligible = []
        for row in song_rows_all:
            ok, reason = _is_human_primary(row, config)
            if ok:
                eligible.append(row)
            else:
                dummy = MixAudio(row=row, decoded=DecodedAudio(np.zeros((1, 1), np.float32), int(row.get("sample_rate") or 0), int(row.get("channels") or 0), float(row.get("duration_seconds") or 0), "not_decoded"), mono=np.zeros(1), analysis=np.zeros(1), representation=np.zeros(1), retained=False, exclusion_reason=reason)
                alignment_rows.append(_alignment_row(dummy, ""))
        ref_row = _reference_mix(eligible)
        song_slug = (artist + "_" + song).lower().replace(" ", "_").replace("/", "_")
        decoded_mixes: list[MixAudio] = []
        for row in eligible:
            try:
                decoded = decode_audio(Path(row["source_path"]))
                backend_counts[decoded.backend] = backend_counts.get(decoded.backend, 0) + 1
                mono = _mono(decoded.samples)
                analysis = ensure_sample_rate(mono.reshape(-1, 1), decoded.sample_rate, config.alignment.coarse_sample_rate)[:, 0]
                rep = _representation(analysis, config.alignment.coarse_sample_rate, config.alignment.use_onset_envelope)
                decoded_mixes.append(MixAudio(row=row, decoded=decoded, mono=mono, analysis=analysis, representation=rep))
            except Exception as exc:
                dummy = MixAudio(row=row, decoded=DecodedAudio(np.zeros((1, 1), np.float32), int(row.get("sample_rate") or 0), int(row.get("channels") or 0), float(row.get("duration_seconds") or 0), "decode_failed"), mono=np.zeros(1), analysis=np.zeros(1), representation=np.zeros(1), retained=False, exclusion_reason="decode_failed", notes=str(exc))
                alignment_rows.append(_alignment_row(dummy, ref_row["mix_id"]))
        ref = next(m for m in decoded_mixes if m.row["mix_id"] == ref_row["mix_id"])
        hop_seconds = 0.023
        for mix in decoded_mixes:
            if mix is ref:
                mix.lag = 0.0; mix.score = 1.0; mix.second_best = 0.0; mix.margin = 1.0; mix.confidence = 1.0
            else:
                lag, score, second, margin, multimodal = _estimate_lag(ref.representation, mix.representation, hop_seconds, config.alignment.maximum_expected_offset_seconds)
                if config.alignment.use_waveform_correlation_for_refinement:
                    refined, wave_score = _refine_lag(ref.analysis, mix.analysis, config.alignment.coarse_sample_rate, lag)
                    lag = refined
                    score = max(score, wave_score)
                confidence = max(0.0, min(1.0, 0.75 * max(score, 0.0) + 0.25 * max(min(margin / 0.15, 1.0), 0.0)))
                mix.lag = lag; mix.score = score; mix.second_best = second; mix.margin = margin; mix.confidence = confidence
                notes = []
                if multimodal:
                    notes.append("multimodal_correlation")
                if abs(float(mix.row.get("duration_seconds") or mix.decoded.duration_seconds) - float(ref.row.get("duration_seconds") or ref.decoded.duration_seconds)) > 0.75:
                    notes.append("duration_mismatch")
                mix.notes = ";".join(notes)
            if mix.confidence < config.alignment.minimum_alignment_confidence:
                mix.retained = False
                mix.exclusion_reason = "low_alignment_confidence"
                manual_review.append(f"{artist} - {song}: {mix.row.get('mixer_id') or mix.row['mix_id']} low confidence {mix.confidence:.3f}")
            alignment_rows.append(_alignment_row(mix, ref.row["mix_id"]))
        retained = [m for m in decoded_mixes if m.retained]
        common_start, common_end = (0.0, 0.0)
        if retained:
            common_start = max(-m.lag for m in retained)
            common_end = min(m.decoded.duration_seconds - m.lag for m in retained)
        overlap = max(0.0, common_end - common_start)
        sufficient = overlap >= config.target_excerpt_seconds
        retained_counts[f"{artist} - {song}"] = len(retained)
        excluded_counts[f"{artist} - {song}"] = len(song_rows_all) - len(retained)
        common_overlap[f"{artist} - {song}"] = overlap
        confidences = [m.confidence for m in decoded_mixes]
        confidence_summary[f"{artist} - {song}"] = f"min={min(confidences):.3f}; median={float(np.median(confidences)):.3f}; max={max(confidences):.3f}" if confidences else "none"
        overlap_rows.append({
            "artist": artist, "song": song, "reference_mix_id": ref.row["mix_id"], "retained_mix_count": str(len(retained)),
            "excluded_mix_count": str(len(song_rows_all) - len(retained)), "common_aligned_start_seconds": _f(common_start),
            "common_aligned_end_seconds": _f(common_end), "common_overlap_seconds": _f(overlap),
            "target_excerpt_seconds": _f(config.target_excerpt_seconds), "sufficient_overlap": str(sufficient).lower(),
            "minimum_alignment_confidence": _f(config.alignment.minimum_alignment_confidence),
            "notes": f"reference selected near median duration/common sample rate: {ref.row.get('mixer_id') or ref.row['mix_id']}",
        })
        candidates = _select_candidates(config, retained, common_start, common_end) if sufficient else []
        top_by_song[f"{artist} - {song}"] = []
        for rank, cand in enumerate(candidates, 1):
            row = {
                "artist": artist, "song": song, "candidate_rank": str(rank), "aligned_start_seconds": _f(cand["start"]),
                "aligned_end_seconds": _f(cand["end"]), "reference_file_start_seconds": _f(cand["start"] + ref.lag),
                "reference_file_end_seconds": _f(cand["end"] + ref.lag), "activity_score": _f(cand["activity"]),
                "onset_score": _f(cand["onset"]), "spectral_activity_score": _f(cand["spectral"]),
                "silence_penalty": _f(cand["silence"]), "boundary_penalty": _f(cand["boundary"]),
                "cross_mix_consistency_score": _f(cand["consistency"]), "total_score": _f(cand["total"]),
                "notes": "diagnostic candidate; active/full arrangement inferred from energy, onset and spectrum metrics",
            }
            candidate_rows.append(row); top_by_song[f"{artist} - {song}"].append(row)
            checklist_rows.append({"artist": artist, "song": song, "candidate_rank": str(rank), "same_musical_passage": "", "clear_musical_activity": "", "no_abrupt_phrase_cut": "", "no_silence_or_fade": "", "audible_mix_differences": "", "suitable_duration": "", "preferred_candidate_rank": "", "reviewer_notes": ""})
            preview_mix_pool = [ref] + [m for m in retained if m.row.get("mixer_institution_code") != ref.row.get("mixer_institution_code")]
            seen_inst = set()
            for mix in preview_mix_pool:
                inst = mix.row.get("mixer_institution_code", "")
                if inst in seen_inst and mix is not ref:
                    continue
                seen_inst.add(inst)
                preview_files.append(str(_render_preview(config, song_slug, mix, rank, cand["start"], cand["end"])))
                if len(seen_inst) >= 2:
                    break
        _plot_diagnostics(config.output_root, song_slug, decoded_mixes, (common_start, common_end), candidates)

    tables = stage2_tables(config.output_root)
    reports = stage2_reports(config.output_root)
    _write_csv(tables / "alignment_results.csv", alignment_rows, ALIGNMENT_COLUMNS)
    _write_csv(tables / "common_overlap_report.csv", overlap_rows, OVERLAP_COLUMNS)
    _write_csv(tables / "excerpt_candidates.csv", candidate_rows, CANDIDATE_COLUMNS)
    _write_csv(tables / "excerpt_manual_review_checklist.csv", checklist_rows, ["artist", "song", "candidate_rank", "same_musical_passage", "clear_musical_activity", "no_abrupt_phrase_cut", "no_silence_or_fade", "audible_mix_differences", "suitable_duration", "preferred_candidate_rank", "reviewer_notes"])
    report = ["# Stage 2 Excerpt Selection Report", "", "Diagnostic previews are not final study stimuli and are not loudness normalised.", "", f"ffmpeg: {env.ffmpeg_version}", f"ffprobe: {env.ffprobe_version}", ""]
    for row in overlap_rows:
        key = f"{row['artist']} - {row['song']}"
        report.extend([f"## {key}", f"Reference mix: {row['reference_mix_id']}", f"Retained/excluded: {row['retained_mix_count']}/{row['excluded_mix_count']}", f"Common overlap: {row['common_overlap_seconds']} seconds", f"Confidence: {confidence_summary.get(key, '')}", "", "Top candidate windows:"])
        for cand in top_by_song.get(key, []):
            report.append(f"- Rank {cand['candidate_rank']}: {cand['aligned_start_seconds']} to {cand['aligned_end_seconds']} s, score {cand['total_score']}")
        report.append("")
    if manual_review:
        report.extend(["## Manual Review Flags", *[f"- {item}" for item in manual_review], ""])
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "excerpt_selection_report.md").write_text("\n".join(report), encoding="utf-8")
    return Stage2Result(backend_counts, retained_counts, excluded_counts, confidence_summary, common_overlap, top_by_song, preview_files, manual_review)

