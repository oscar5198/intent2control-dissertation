from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import soundfile as sf
from scipy import signal
import yaml

from stimulus_selection.audio_decode import decode_audio, ensure_sample_rate, write_wav
from stimulus_selection.output_layout import first_existing, stage2_diagnostics, stage2_reports, stage2_tables

DECISION_COLUMNS = [
    "artist", "song", "selected_original_candidate_rank", "selected_aligned_start_seconds",
    "selected_aligned_end_seconds", "boundary_shift_from_candidate_seconds", "vocal_activity_coverage",
    "bass_activity_coverage", "drum_activity_coverage", "other_instrument_activity_coverage",
    "simultaneous_core_activity_coverage", "cross_mix_variation_score", "boundary_quality_score",
    "alignment_score_summary", "final_score", "decision_confidence", "selection_rationale", "evidence_sources",
]

RAW_ROOTS = {
    ("The DoneFors", "Lead Me"): "LeadMeRaw",
    ("Fredy V", "In The Meantime"): "InTheMeantimeRaw",
}

SLUGS = {
    ("The DoneFors", "Lead Me"): "the_donefors_lead_me",
    ("Fredy V", "In The Meantime"): "fredy_v_in_the_meantime",
}

_DECODE_CACHE = {}

PREVIEW_INSTITUTIONS = {
    ("The DoneFors", "Lead Me"): ["DU", "CNS", "QUT"],
    ("Fredy V", "In The Meantime"): ["QUT", "DU", "McG"],
}

@dataclass(frozen=True)
class TrackMapping:
    path: Path
    group: str
    confidence: str
    rationale: str

@dataclass(frozen=True)
class SourceEvidence:
    artist: str
    song: str
    raw_root: Path
    mappings: list[TrackMapping]
    group_activity: dict[str, np.ndarray]
    times: np.ndarray
    source_offset_seconds: float
    source_alignment_score: float

@dataclass(frozen=True)
class CandidateScore:
    artist: str
    song: str
    candidate_rank: int
    candidate_start: float
    start: float
    end: float
    vocal: float
    bass: float
    drums: float
    other: float
    core: float
    cross_mix_variation: float
    boundary_quality: float
    alignment_summary: str
    score: float
    confidence: float
    rationale: str
    evidence_sources: str


def _fmt(value: float) -> str:
    return f"{value:.6f}" if math.isfinite(value) else ""


def map_track_to_group(path: Path) -> TrackMapping | None:
    name = path.stem.lower().replace(" ", "")
    if name in {"mix", "dry", "wet", "bounce", "rest", "mix_nocomp", "drums_nocomp"}:
        return None
    if any(token in name for token in ["leadvoc", "janinevoc", "vocal", "bvocal"]):
        return TrackMapping(path, "vocal", "high", "filename explicitly identifies vocal")
    if name.startswith("bg") or name.startswith("bgd"):
        return TrackMapping(path, "vocal", "medium", "filename suggests backing vocal group, not a validated lead-vocal stem")
    if name == "ldc2":
        return TrackMapping(path, "vocal", "low", "ambiguous microphone label; treated as possible vocal evidence with low confidence")
    if "bass" in name:
        return TrackMapping(path, "bass", "high", "filename explicitly identifies bass")
    if any(token in name for token in ["kin", "kout", "kick", "sn", "snt", "hat", "hh", "tom", "floor", "oh", "monodr", "percussion", "snaps", "stoh"]):
        return TrackMapping(path, "drums", "high", "filename identifies drum/percussion source")
    if any(token in name for token in ["guit", "gtr", "keys", "org", "accordion", "accordian", "egtr", "ekeys", "paul"]):
        return TrackMapping(path, "other", "high", "filename identifies harmonic/instrumental source")
    return TrackMapping(path, "other", "low", "unrecognised source label mapped cautiously to other instruments")


def _read_mono(path: Path) -> tuple[np.ndarray, int]:
    data, sr = sf.read(str(path), always_2d=True, dtype="float32")
    return data.mean(axis=1).astype(np.float32), int(sr)


def _activity_envelope(samples: np.ndarray, sample_rate: int, hop_seconds: float = 0.25) -> tuple[np.ndarray, np.ndarray]:
    hop = max(1, int(round(hop_seconds * sample_rate)))
    frame = max(hop, int(round(0.50 * sample_rate)))
    if samples.size < frame:
        samples = np.pad(samples, (0, frame - samples.size))
    starts = np.arange(0, samples.size - frame + 1, hop)
    values = np.empty(starts.size, dtype=np.float32)
    for i, s in enumerate(starts):
        seg = samples[s:s + frame]
        values[i] = float(np.sqrt(np.mean(seg * seg) + 1e-12))
    times = starts.astype(np.float32) / sample_rate
    return times, values


def _active_curve(envelope: np.ndarray) -> np.ndarray:
    if envelope.size == 0:
        return envelope
    floor = float(np.percentile(envelope, 20))
    active = float(np.percentile(envelope, 70))
    threshold = floor + 0.20 * max(active - floor, 1e-9)
    return (envelope > threshold).astype(np.float32)


def _normalise(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.float32)
    x = x - float(np.mean(x))
    s = float(np.std(x))
    return x / s if s > 1e-9 else np.zeros_like(x)


def _mixdown_raw_tracks(mappings: Iterable[TrackMapping], target_sr: int) -> tuple[np.ndarray, int]:
    acc = None
    for mapping in mappings:
        samples, sr = _read_mono(mapping.path)
        down = ensure_sample_rate(samples.reshape(-1, 1), sr, target_sr)[:, 0]
        peak = float(np.max(np.abs(down))) if down.size else 0.0
        if peak > 1e-7:
            down = down / peak
        if acc is None:
            acc = np.zeros_like(down)
        if down.size < acc.size:
            down = np.pad(down, (0, acc.size - down.size))
        elif down.size > acc.size:
            acc = np.pad(acc, (0, down.size - acc.size))
        acc += down
    if acc is None:
        acc = np.zeros(1, dtype=np.float32)
    return acc.astype(np.float32), target_sr


def _align_reference_to_source(ref_path: Path, mappings: list[TrackMapping]) -> tuple[float, float]:
    target_sr = 11025
    raw_mix, _ = _mixdown_raw_tracks(mappings, target_sr)
    ref = decode_audio(ref_path)
    ref_mono = ref.samples.mean(axis=1).astype(np.float32)
    ref_down = ensure_sample_rate(ref_mono.reshape(-1, 1), ref.sample_rate, target_sr)[:, 0]
    _, raw_env = _activity_envelope(raw_mix, target_sr, 0.05)
    _, ref_env = _activity_envelope(ref_down, target_sr, 0.05)
    raw_z = _normalise(np.log1p(raw_env))
    ref_z = _normalise(np.log1p(ref_env))
    corr = signal.correlate(raw_z, ref_z, mode="valid", method="fft")
    den = max(1e-9, float(np.linalg.norm(ref_z)))
    window_energy = np.sqrt(signal.convolve(raw_z * raw_z, np.ones(ref_z.size), mode="valid"))
    norm_corr = corr / np.maximum(den * window_energy, 1e-9)
    idx = int(np.argmax(norm_corr))
    return idx * 0.05, float(norm_corr[idx])


def build_source_evidence(dataset_root: Path, artist: str, song: str, reference_path: Path) -> SourceEvidence:
    raw_root = dataset_root / "audio" / RAW_ROOTS[(artist, song)]
    mappings = [m for p in sorted(raw_root.glob("*.wav")) if (m := map_track_to_group(p)) is not None]
    source_offset, align_score = _align_reference_to_source(reference_path, mappings)
    group_envelopes: dict[str, list[np.ndarray]] = defaultdict(list)
    times = None
    for mapping in mappings:
        samples, sr = _read_mono(mapping.path)
        t, env = _activity_envelope(samples, sr, 0.25)
        group_envelopes[mapping.group].append(env)
        if times is None:
            times = t
    if times is None:
        times = np.zeros(1, dtype=np.float32)
    group_activity = {}
    for group in ["vocal", "bass", "drums", "other"]:
        envs = group_envelopes.get(group, [])
        if not envs:
            group_activity[group] = np.zeros_like(times, dtype=np.float32)
            continue
        min_len = min(e.size for e in envs)
        stacked = np.vstack([_active_curve(e[:min_len]) for e in envs])
        group_activity[group] = np.max(stacked, axis=0)
    return SourceEvidence(artist, song, raw_root, mappings, group_activity, times, source_offset, align_score)


def coverage(evidence: SourceEvidence, group: str, aligned_start: float, aligned_end: float) -> float:
    source_start = aligned_start + evidence.source_offset_seconds
    source_end = aligned_end + evidence.source_offset_seconds
    mask = (evidence.times >= source_start) & (evidence.times < source_end)
    if not mask.any():
        return 0.0
    return float(np.mean(evidence.group_activity[group][mask]))


def simultaneous_core_coverage(evidence: SourceEvidence, aligned_start: float, aligned_end: float) -> float:
    source_start = aligned_start + evidence.source_offset_seconds
    source_end = aligned_end + evidence.source_offset_seconds
    mask = (evidence.times >= source_start) & (evidence.times < source_end)
    if not mask.any():
        return 0.0
    core = evidence.group_activity["vocal"][mask] * evidence.group_activity["bass"][mask] * evidence.group_activity["drums"][mask]
    return float(np.mean(core))


def boundary_quality(evidence: SourceEvidence, aligned_start: float, aligned_end: float) -> float:
    source_start = aligned_start + evidence.source_offset_seconds
    source_end = aligned_end + evidence.source_offset_seconds
    total = sum(evidence.group_activity[g] for g in ["vocal", "bass", "drums", "other"])
    near = 1.0
    for boundary in [source_start, source_end]:
        near_mask = (evidence.times >= boundary - 0.75) & (evidence.times <= boundary + 0.75)
        inner_mask = (evidence.times >= boundary + 0.75) & (evidence.times <= boundary + 2.0)
        if not near_mask.any():
            continue
        edge_activity = float(np.mean(total[near_mask] > 0))
        inner_activity = float(np.mean(total[inner_mask] > 0)) if inner_mask.any() else edge_activity
        # Prefer boundaries that are active but not abrupt high-density spikes.
        near *= max(0.0, min(1.0, 1.0 - 0.35 * abs(edge_activity - inner_activity)))
    return float(near)


def cross_mix_variation(alignment_rows: list[dict[str, str]], aligned_start: float, aligned_end: float) -> float:
    feats = []
    retained = [r for r in alignment_rows if r["retained_for_excerpt_selection"] == "true"]
    for row in retained:
        path = row["source_path"]
        audio = _DECODE_CACHE.get(path)
        if audio is None:
            audio = decode_audio(Path(path))
            _DECODE_CACHE[path] = audio
        lag = float(row["refined_lag_seconds"] or row["estimated_lag_seconds"] or 0.0)
        start = int(round((aligned_start + lag) * audio.sample_rate))
        end = int(round((aligned_end + lag) * audio.sample_rate))
        if start < 0 or end > audio.samples.shape[0] or end <= start:
            raise ValueError(f"missing samples for {row['mix_id']}")
        seg = audio.samples[start:end]
        mono = seg.mean(axis=1)
        rms = float(np.sqrt(np.mean(mono * mono) + 1e-12))
        peak = float(np.max(np.abs(mono)) + 1e-12)
        crest = peak / max(rms, 1e-12)
        spec = np.abs(np.fft.rfft(mono[::max(1, int(audio.sample_rate / 11025))] * np.hanning(len(mono[::max(1, int(audio.sample_rate / 11025))]))))
        centroid = float(np.sum(np.arange(spec.size) * spec) / max(np.sum(spec), 1e-12))
        width = 0.0
        imbalance = 0.0
        if seg.ndim == 2 and seg.shape[1] >= 2:
            left = seg[:, 0]; right = seg[:, 1]
            side = (left - right) * 0.5
            mid = (left + right) * 0.5
            width = float(np.sqrt(np.mean(side * side) + 1e-12) / max(np.sqrt(np.mean(mid * mid) + 1e-12), 1e-12))
            imbalance = float(abs(np.sqrt(np.mean(left * left) + 1e-12) - np.sqrt(np.mean(right * right) + 1e-12)))
        feats.append([math.log(max(rms, 1e-9)), math.log(max(crest, 1e-9)), math.log(max(centroid, 1e-9)), width, imbalance])
    arr = np.asarray(feats, dtype=np.float32)
    if arr.shape[0] < 2:
        return 0.0
    variation = np.mean(np.std(arr, axis=0) / (np.mean(np.abs(arr), axis=0) + 1e-6))
    return float(max(0.0, min(1.0, variation * 8.0)))


def score_window(evidence: SourceEvidence, alignment_rows: list[dict[str, str]], candidate: dict[str, str], start: float) -> CandidateScore:
    end = start + 28.0
    vocal = coverage(evidence, "vocal", start, end)
    bass = coverage(evidence, "bass", start, end)
    drums = coverage(evidence, "drums", start, end)
    other = coverage(evidence, "other", start, end)
    core = simultaneous_core_coverage(evidence, start, end)
    variation = cross_mix_variation(alignment_rows, start, end)
    boundary = boundary_quality(evidence, start, end)
    confs = [float(r["alignment_confidence"]) for r in alignment_rows if r["retained_for_excerpt_selection"] == "true"]
    align_summary = f"min={min(confs):.3f}; median={float(np.median(confs)):.3f}; max={max(confs):.3f}"
    source_score = 0.24 * vocal + 0.18 * bass + 0.20 * drums + 0.10 * other + 0.16 * core
    final = source_score + 0.07 * variation + 0.05 * boundary
    confidence = max(0.0, min(1.0, 0.65 * final + 0.20 * evidence.source_alignment_score + 0.15 * min(confs)))
    rank = int(candidate["candidate_rank"])
    cand_start = float(candidate["aligned_start_seconds"])
    rationale = "source-aware score balances raw-track activity, simultaneous vocal/bass/drums coverage, cross-mix variation, boundary stability and alignment confidence"
    evidence_sources = f"raw tracks: {evidence.raw_root}; mappings: {len(evidence.mappings)} tracks; public aligned mixes: {len(confs)}; source-reference alignment={evidence.source_alignment_score:.3f}"
    return CandidateScore(evidence.artist, evidence.song, rank, cand_start, start, end, vocal, bass, drums, other, core, variation, boundary, align_summary, final, confidence, rationale, evidence_sources)


def refine_and_select(evidence: SourceEvidence, alignment_rows: list[dict[str, str]], candidates: list[dict[str, str]], common_start: float, common_end: float) -> tuple[CandidateScore, list[CandidateScore]]:
    scored = []
    for candidate in candidates:
        base = float(candidate["aligned_start_seconds"])
        for shift in np.arange(-3.0, 3.0001, 0.5):
            start = round(base + float(shift), 6)
            if start < common_start or start + 28.0 > common_end:
                continue
            scored.append(score_window(evidence, alignment_rows, candidate, start))
    scored.sort(key=lambda s: (s.score, s.boundary_quality, s.core, s.vocal + s.bass + s.drums, s.cross_mix_variation, -s.candidate_rank), reverse=True)
    return scored[0], scored


def validate_decision(score: CandidateScore, alignment_rows: list[dict[str, str]], common_start: float, common_end: float) -> None:
    if abs((score.end - score.start) - 28.0) > 1e-6:
        raise ValueError("approved excerpt is not exactly 28 seconds")
    if score.start < common_start - 1e-6 or score.end > common_end + 1e-6:
        raise ValueError("approved excerpt lies outside common overlap")
    for row in alignment_rows:
        if row["retained_for_excerpt_selection"] != "true":
            continue
        path_key = row["source_path"]
        audio = _DECODE_CACHE.get(path_key)
        if audio is None:
            audio = decode_audio(Path(path_key))
            _DECODE_CACHE[path_key] = audio
        lag = float(row["refined_lag_seconds"] or row["estimated_lag_seconds"] or 0.0)
        s = int(round((score.start + lag) * audio.sample_rate))
        e = int(round((score.end + lag) * audio.sample_rate))
        if s < 0 or e > audio.samples.shape[0] or e <= s:
            raise ValueError(f"source-time conversion failed for {row['mix_id']}")


def render_final_previews(score: CandidateScore, alignment_rows: list[dict[str, str]], output_root: Path) -> list[Path]:
    selected = []
    wanted = PREVIEW_INSTITUTIONS[(score.artist, score.song)]
    retained = [r for r in alignment_rows if r["retained_for_excerpt_selection"] == "true"]
    for inst in wanted:
        match = next((r for r in retained if r["institution"] == inst), None)
        if match is not None:
            selected.append(match)
    if len(selected) < 3:
        for row in retained:
            if row not in selected and row["institution"] not in {r["institution"] for r in selected}:
                selected.append(row)
            if len(selected) == 3:
                break
    paths = []
    root = stage2_diagnostics(output_root) / "final_previews" / SLUGS[(score.artist, score.song)]
    for row in selected[:3]:
        path_key = row["source_path"]
        audio = _DECODE_CACHE.get(path_key)
        if audio is None:
            audio = decode_audio(Path(path_key))
            _DECODE_CACHE[path_key] = audio
        lag = float(row["refined_lag_seconds"] or row["estimated_lag_seconds"] or 0.0)
        s = int(round((score.start + lag) * audio.sample_rate))
        e = int(round((score.end + lag) * audio.sample_rate))
        seg = audio.samples[s:e]
        seg = ensure_sample_rate(seg, audio.sample_rate, 44100)
        fade = 44100
        if seg.shape[0] > fade * 2:
            ramp = np.linspace(0, 1, fade, dtype=np.float32)
            seg[:fade] *= ramp[:, None]
            seg[-fade:] *= ramp[::-1, None]
        name = f"approved_c{score.candidate_rank:02d}_{row['institution']}_{row['mix_id']}.wav"
        path = root / name
        write_wav(path, seg, 44100)
        paths.append(path)
    return paths


def write_config_approvals(config_path: Path, decisions: list[CandidateScore]) -> None:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    approved = []
    for d in decisions:
        approved.append({
            "artist": d.artist,
            "song": d.song,
            "aligned_start_seconds": round(d.start, 6),
            "aligned_end_seconds": round(d.end, 6),
            "selected_candidate_rank": d.candidate_rank,
            "selection_method": "automatic_source_aware",
            "reviewer": "automated pipeline",
            "review_notes": f"Selected by source-aware rescoring; core coverage {d.core:.3f}, boundary score {d.boundary_quality:.3f}, final score {d.score:.3f}.",
        })
    raw["approved_excerpts"] = approved
    config_path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=False), encoding="utf-8")


def write_outputs(repo: Path, decisions: list[CandidateScore], all_scores: dict[tuple[str, str], list[CandidateScore]], preview_paths: dict[tuple[str, str], list[Path]]) -> None:
    out = repo / "outputs" / "stimulus_selection"
    tables = stage2_tables(out)
    reports = stage2_reports(out)
    rows = []
    for d in decisions:
        rows.append({
            "artist": d.artist,
            "song": d.song,
            "selected_original_candidate_rank": str(d.candidate_rank),
            "selected_aligned_start_seconds": _fmt(d.start),
            "selected_aligned_end_seconds": _fmt(d.end),
            "boundary_shift_from_candidate_seconds": _fmt(d.start - d.candidate_start),
            "vocal_activity_coverage": _fmt(d.vocal),
            "bass_activity_coverage": _fmt(d.bass),
            "drum_activity_coverage": _fmt(d.drums),
            "other_instrument_activity_coverage": _fmt(d.other),
            "simultaneous_core_activity_coverage": _fmt(d.core),
            "cross_mix_variation_score": _fmt(d.cross_mix_variation),
            "boundary_quality_score": _fmt(d.boundary_quality),
            "alignment_score_summary": d.alignment_summary,
            "final_score": _fmt(d.score),
            "decision_confidence": _fmt(d.confidence),
            "selection_rationale": d.rationale,
            "evidence_sources": d.evidence_sources,
        })
    tables.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    with (tables / "final_excerpt_decision.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DECISION_COLUMNS)
        writer.writeheader(); writer.writerows(rows)
    md = ["# Final Stage 2 Excerpt Decision", "", "One 28-second song section is approved per song. These decisions do not select mix versions and do not run Diff-MST feature extraction.", ""]
    for d in decisions:
        key = (d.artist, d.song)
        competitors = [s for s in all_scores[key] if abs(s.start - d.start) > 1e-6][:8]
        md.extend([
            f"## {d.artist} - {d.song}",
            f"Selected aligned section: {d.start:.6f} to {d.end:.6f} seconds.",
            f"Original candidate rank: {d.candidate_rank}; boundary shift: {d.start - d.candidate_start:+.3f} seconds.",
            f"Source coverage: vocal {d.vocal:.3f}, bass {d.bass:.3f}, drums {d.drums:.3f}, other instruments {d.other:.3f}, simultaneous vocal+bass+drums {d.core:.3f}.",
            f"Cross-mix variation score: {d.cross_mix_variation:.3f}; boundary quality score: {d.boundary_quality:.3f}; final score: {d.score:.3f}; decision confidence: {d.confidence:.3f}.",
            f"Evidence: {d.evidence_sources}.",
            "The section was preferred because it produced the strongest source-aware compromise among candidate neighborhoods, preserving substantial activity in the core musical groups while maintaining valid overlap across retained aligned mixes.",
            "Limitations: source-group labels are filename-derived. Lead Me has explicit lead-vocal labels; In The Meantime has clear bass/drum/instrument labels but vocal evidence includes backing-vocal labels and an ambiguous LDC2 microphone label, so vocal coverage is treated cautiously rather than as validated lead-vocal detection.",
            "Final diagnostic previews, all representing this same approved song section:",
        ])
        for p in preview_paths[key]:
            md.append(f"- {p.name}")
        md.append("Nearest alternatives considered:")
        for alt in competitors[:5]:
            md.append(f"- Candidate {alt.candidate_rank}, start {alt.start:.3f}, score {alt.score:.3f}, core {alt.core:.3f}, boundary {alt.boundary_quality:.3f}")
        md.append("")
    (reports / "final_excerpt_decision.md").write_text("\n".join(md), encoding="utf-8")
    report_path = first_existing(out, "02_excerpt_selection/reports/excerpt_selection_report.md", "excerpt_selection_report.md")
    report = report_path.read_text(encoding="utf-8")
    block = ["", "## Final Automatic Decisions", "", "Selections were made by source-aware rescoring of the five Stage 2 candidates plus +/-3 second boundary refinements. No mix triplets were selected and no loudness normalisation or Diff-MST feature extraction was run.", ""]
    for d in decisions:
        block.append(f"- {d.artist} - {d.song}: approved {d.start:.6f} to {d.end:.6f} s from candidate {d.candidate_rank} (shift {d.start - d.candidate_start:+.3f} s), final score {d.score:.3f}, confidence {d.confidence:.3f}.")
    marker = "## Final Automatic Decisions"
    if marker in report:
        report = report[:report.index(marker)].rstrip() + "\n" + "\n".join(block).strip() + "\n"
    else:
        report = report.rstrip() + "\n\n" + "\n".join(block).strip() + "\n"
    (reports / "excerpt_selection_report.md").write_text(report, encoding="utf-8")


def run(repo: Path, dataset_root: Path) -> list[CandidateScore]:
    out = repo / "outputs" / "stimulus_selection"
    with first_existing(out, "02_excerpt_selection/tables/excerpt_candidates.csv", "excerpt_candidates.csv").open("r", encoding="utf-8", newline="") as handle:
        candidates = list(csv.DictReader(handle))
    with first_existing(out, "02_excerpt_selection/tables/alignment_results.csv", "alignment_results.csv").open("r", encoding="utf-8", newline="") as handle:
        alignment = list(csv.DictReader(handle))
    with first_existing(out, "02_excerpt_selection/tables/common_overlap_report.csv", "common_overlap_report.csv").open("r", encoding="utf-8", newline="") as handle:
        overlap = list(csv.DictReader(handle))
    decisions = []
    all_scores = {}
    preview_paths = {}
    for key in RAW_ROOTS:
        artist, song = key
        song_align = [r for r in alignment if r["artist"] == artist and r["song"] == song]
        ref_id = next(r["reference_mix_id"] for r in overlap if r["artist"] == artist and r["song"] == song)
        ref = next(r for r in song_align if r["mix_id"] == ref_id)
        evidence = build_source_evidence(dataset_root, artist, song, Path(ref["source_path"]))
        song_candidates = [c for c in candidates if c["artist"] == artist and c["song"] == song]
        overlap_row = next(r for r in overlap if r["artist"] == artist and r["song"] == song)
        common_start = float(overlap_row["common_aligned_start_seconds"])
        common_end = float(overlap_row["common_aligned_end_seconds"])
        best, scored = refine_and_select(evidence, song_align, song_candidates, common_start, common_end)
        validate_decision(best, song_align, common_start, common_end)
        previews = render_final_previews(best, song_align, out)
        decisions.append(best)
        all_scores[key] = scored
        preview_paths[key] = previews
    write_config_approvals(repo / "configs" / "stimulus_selection.yaml", decisions)
    write_outputs(repo, decisions, all_scores, preview_paths)
    return decisions

if __name__ == "__main__":
    repo = Path(r"C:\Users\oscar\Documents\7. QMUL UNIVERSITY\1. Master Program\3. MSc Project\intent2control-dissertation")
    dataset = Path(r"C:\Users\oscar\OneDrive\Public share - Mix Eval Dataset")
    for decision in run(repo, dataset):
        print(f"{decision.artist} - {decision.song}: {decision.start:.6f}-{decision.end:.6f}, candidate {decision.candidate_rank}, score {decision.score:.3f}")
