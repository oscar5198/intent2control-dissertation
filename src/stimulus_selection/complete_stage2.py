from __future__ import annotations

import csv
import shutil
from pathlib import Path

import numpy as np
import soundfile as sf
import yaml

from stimulus_selection.audio_decode import decode_audio, ensure_sample_rate, write_wav
from stimulus_selection.final_decision import (
    CandidateScore,
    SourceEvidence,
    _activity_envelope,
    _active_curve,
    _align_reference_to_source,
    _fmt,
    boundary_quality,
    coverage,
    cross_mix_variation,
    map_track_to_group,
    refine_and_select,
    simultaneous_core_coverage,
    validate_decision,
)

REPO = Path(r"C:\Users\oscar\Documents\7. QMUL UNIVERSITY\1. Master Program\3. MSc Project\intent2control-dissertation")
DATASET = Path(r"C:\Users\oscar\OneDrive\Public share - Mix Eval Dataset")
OUT = REPO / "outputs" / "stimulus_selection"
REMAINING = OUT / "stage2_remaining"
APPROVED_PREVIEW_ROOT = OUT / "approved_excerpt_previews"

SLUGS = {
    ("The DoneFors", "Lead Me"): "LeadMe",
    ("Fredy V", "In The Meantime"): "InTheMeantime",
    ("Broken Crank", "Red To Blue"): "RedToBlue",
    ("The DoneFors", "Pouring Room"): "PouringRoom",
}

DECISION_COLUMNS = [
    "artist", "song", "selected_original_candidate_rank", "selected_aligned_start_seconds",
    "selected_aligned_end_seconds", "duration_seconds", "boundary_shift_from_candidate_seconds",
    "vocal_activity_coverage", "bass_activity_coverage", "drum_activity_coverage",
    "other_instrument_activity_coverage", "simultaneous_core_activity_coverage",
    "cross_mix_variation_score", "cross_mix_consistency", "boundary_quality_score",
    "alignment_score_summary", "final_score", "decision_confidence", "selection_rationale", "evidence_sources",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def mapping_for_stem(path: Path):
    mapping = map_track_to_group(path)
    if mapping is not None:
        return mapping
    if path.stem.lower() == "rest":
        from stimulus_selection.final_decision import TrackMapping
        return TrackMapping(path, "other", "medium", "stem label 'rest' treated as remaining non-core instruments")
    return None


def build_red_to_blue_evidence(reference_path: Path) -> SourceEvidence:
    stem_root = DATASET / "audio" / "RedToBlueStems" / "McG-A"
    mappings = [m for p in sorted(stem_root.glob("*.wav")) if (m := mapping_for_stem(p)) is not None]
    offset, align_score = _align_reference_to_source(reference_path, mappings)
    group_envs: dict[str, list[np.ndarray]] = {"vocal": [], "bass": [], "drums": [], "other": []}
    times = None
    for mapping in mappings:
        data, sr = sf.read(str(mapping.path), always_2d=True, dtype="float32")
        mono = data.mean(axis=1).astype(np.float32)
        t, env = _activity_envelope(mono, sr, 0.25)
        times = t if times is None else times
        group_envs[mapping.group].append(env)
    assert times is not None
    group_activity = {}
    for group, envs in group_envs.items():
        if not envs:
            group_activity[group] = np.zeros_like(times)
        else:
            min_len = min(e.size for e in envs)
            group_activity[group] = np.max(np.vstack([_active_curve(e[:min_len]) for e in envs]), axis=0)
    return SourceEvidence("Broken Crank", "Red To Blue", stem_root, mappings, group_activity, times, offset, align_score)


def build_proxy_evidence(artist: str, song: str, alignment_rows: list[dict[str, str]]) -> SourceEvidence:
    # Explicit proxy fallback: derive broad activity groups from the alignment reference mix.
    ref_id = alignment_rows[0]["reference_mix_id"]
    ref = next(r for r in alignment_rows if r["mix_id"] == ref_id)
    audio = decode_audio(Path(ref["source_path"]))
    mono = audio.samples.mean(axis=1).astype(np.float32)
    t, env = _activity_envelope(mono, audio.sample_rate, 0.25)
    active = _active_curve(env)
    low = _active_curve(_band_envelope(mono, audio.sample_rate, 40, 180))
    mid = _active_curve(_band_envelope(mono, audio.sample_rate, 250, 3500))
    high_onset = _active_curve(np.maximum(0.0, np.diff(env, prepend=env[:1])))
    group_activity = {
        "vocal": mid * active,
        "bass": low * active,
        "drums": high_onset * active,
        "other": active,
    }
    return SourceEvidence(artist, song, Path("aligned_public_mix_proxy"), [], group_activity, t, 0.0, 1.0)


def _band_envelope(mono: np.ndarray, sr: int, lo: float, hi: float) -> np.ndarray:
    from scipy import signal
    sos = signal.butter(3, [lo, min(hi, sr / 2 - 100)], btype="bandpass", fs=sr, output="sos")
    filt = signal.sosfilt(sos, mono).astype(np.float32)
    _, env = _activity_envelope(filt, sr, 0.25)
    return env


def score_proxy_window(evidence: SourceEvidence, alignment_rows: list[dict[str, str]], candidate: dict[str, str], start: float) -> CandidateScore:
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
    final = 0.20 * vocal + 0.18 * bass + 0.18 * drums + 0.12 * other + 0.12 * core + 0.10 * variation + 0.10 * boundary
    confidence = max(0.0, min(1.0, 0.65 * final + 0.20 * min(confs) + 0.15 * evidence.source_alignment_score))
    rank = int(candidate["candidate_rank"])
    cstart = float(candidate["aligned_start_seconds"])
    return CandidateScore(
        evidence.artist, evidence.song, rank, cstart, start, end, vocal, bass, drums, other, core,
        variation, boundary, align_summary, final, confidence,
        "automatic proxy-based source-aware selection from aligned public mixes; no local stems/raw tracks found",
        "aligned public mix proxies for low-band, mid-band, onset/percussive and broad activity; no validated source stems found",
    )


def choose_proxy(evidence: SourceEvidence, alignment_rows: list[dict[str, str]], candidates: list[dict[str, str]], common_start: float, common_end: float) -> tuple[CandidateScore, list[CandidateScore]]:
    scores = []
    for cand in candidates:
        base = float(cand["aligned_start_seconds"])
        for shift in np.arange(-3.0, 3.0001, 0.5):
            start = round(base + float(shift), 6)
            if start < common_start or start + 28.0 > common_end:
                continue
            scores.append(score_proxy_window(evidence, alignment_rows, cand, start))
    scores.sort(key=lambda s: (s.score, s.boundary_quality, s.core, s.cross_mix_variation, -s.candidate_rank), reverse=True)
    return scores[0], scores


def decision_to_row(d: CandidateScore) -> dict[str, str]:
    return {
        "artist": d.artist,
        "song": d.song,
        "selected_original_candidate_rank": str(d.candidate_rank),
        "selected_aligned_start_seconds": _fmt(d.start),
        "selected_aligned_end_seconds": _fmt(d.end),
        "duration_seconds": _fmt(d.end - d.start),
        "boundary_shift_from_candidate_seconds": _fmt(d.start - d.candidate_start),
        "vocal_activity_coverage": _fmt(d.vocal),
        "bass_activity_coverage": _fmt(d.bass),
        "drum_activity_coverage": _fmt(d.drums),
        "other_instrument_activity_coverage": _fmt(d.other),
        "simultaneous_core_activity_coverage": _fmt(d.core),
        "cross_mix_variation_score": _fmt(d.cross_mix_variation),
        "cross_mix_consistency": d.alignment_summary,
        "boundary_quality_score": _fmt(d.boundary_quality),
        "alignment_score_summary": d.alignment_summary,
        "final_score": _fmt(d.score),
        "decision_confidence": _fmt(d.confidence),
        "selection_rationale": d.rationale,
        "evidence_sources": d.evidence_sources,
    }


def preserved_decisions() -> list[dict[str, str]]:
    rows = read_csv(OUT / "final_excerpt_decision.csv")
    keep = []
    for row in rows:
        if (row["artist"], row["song"]) in {("The DoneFors", "Lead Me"), ("Fredy V", "In The Meantime")}:
            row.setdefault("duration_seconds", _fmt(float(row["selected_aligned_end_seconds"]) - float(row["selected_aligned_start_seconds"])))
            row.setdefault("cross_mix_consistency", row.get("alignment_score_summary", ""))
            keep.append(row)
    return keep


def render_approved_previews(decisions: list[dict[str, str]], manifest_path: Path) -> None:
    if APPROVED_PREVIEW_ROOT.exists():
        shutil.rmtree(APPROVED_PREVIEW_ROOT)
    APPROVED_PREVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    all_alignment = read_csv(OUT / "alignment_results.csv") + read_csv(REMAINING / "alignment_results.csv")
    manifest = []
    for decision in decisions:
        key = (decision["artist"], decision["song"])
        retained = [r for r in all_alignment if r["artist"] == key[0] and r["song"] == key[1] and r["retained_for_excerpt_selection"] == "true"]
        seen = set()
        chosen = []
        for r in retained:
            if r["institution"] not in seen:
                chosen.append(r); seen.add(r["institution"])
            if len(chosen) == 3:
                break
        while len(chosen) < 3 and len(chosen) < len(retained):
            chosen.append(retained[len(chosen)])
        start = float(decision["selected_aligned_start_seconds"])
        end = float(decision["selected_aligned_end_seconds"])
        for i, row in enumerate(chosen[:3], 1):
            audio = decode_audio(Path(row["source_path"]))
            lag = float(row["refined_lag_seconds"] or row["estimated_lag_seconds"] or 0.0)
            s = int(round((start + lag) * audio.sample_rate))
            e = int(round((end + lag) * audio.sample_rate))
            if s < 0 or e > audio.samples.shape[0] or e <= s:
                raise ValueError(f"approved preview missing samples for {row['mix_id']}")
            seg = ensure_sample_rate(audio.samples[s:e], audio.sample_rate, 44100)
            target_len = 1234800
            if seg.shape[0] != target_len:
                if seg.shape[0] > target_len:
                    seg = seg[:target_len]
                else:
                    seg = np.vstack([seg, np.zeros((target_len - seg.shape[0], seg.shape[1]), dtype=np.float32)])
            fade = 44100
            ramp = np.linspace(0, 1, fade, dtype=np.float32)
            seg[:fade] *= ramp[:, None]
            seg[-fade:] *= ramp[::-1, None]
            filename = f"{SLUGS[key]}_approved_preview_{i:02d}.wav"
            path = APPROVED_PREVIEW_ROOT / filename
            write_wav(path, seg, 44100)
            manifest.append({
                "artist": key[0], "song": key[1],
                "approved_start_seconds": _fmt(start), "approved_end_seconds": _fmt(end),
                "preview_filename": filename, "mix_id": row["mix_id"], "institution": row["institution"],
                "source_path": row["source_path"], "purpose": "diagnostic approved-excerpt preview, not final selected study mix",
            })
    write_csv(manifest_path, manifest, ["artist", "song", "approved_start_seconds", "approved_end_seconds", "preview_filename", "mix_id", "institution", "source_path", "purpose"])


def validate_previews() -> None:
    wavs = sorted(APPROVED_PREVIEW_ROOT.glob("*.wav"))
    if len(wavs) != 12:
        raise ValueError(f"expected 12 approved previews, found {len(wavs)}")
    for wav in wavs:
        info = sf.info(str(wav))
        if info.samplerate != 44100 or info.channels != 2 or info.frames != 1234800:
            raise ValueError(f"invalid preview format: {wav.name} {info}")


def cleanup_obsolete_previews() -> list[Path]:
    candidates = []
    for folder in [OUT / "excerpt_previews", OUT / "final_previews"]:
        if folder.exists():
            candidates.extend(sorted(folder.rglob("*.wav")))
    report_lines = ["# Preview Cleanup Report", "", "## Files Scheduled For Removal", ""]
    for p in candidates:
        report_lines.append(f"- {p}")
    for p in candidates:
        p.unlink()
    report_lines += ["", "## Validation", "", f"Removed obsolete preview WAV files: {len(candidates)}", "Approved preview WAV files retained: 12", f"Approved preview folder: {APPROVED_PREVIEW_ROOT}", "Directories retained: excerpt_previews, final_previews, diagnostic_figures, stage2_remaining, and all analytical output directories/files.", "No source dataset audio or analytical CSV/Markdown/figure files were deleted."]
    (OUT / "preview_cleanup_report.md").write_text("\n".join(report_lines), encoding="utf-8")
    return candidates


def main() -> None:
    candidates = read_csv(REMAINING / "excerpt_candidates.csv")
    alignment = read_csv(REMAINING / "alignment_results.csv")
    overlaps = read_csv(REMAINING / "common_overlap_report.csv")
    new_decisions: list[CandidateScore] = []
    for artist, song in [("Broken Crank", "Red To Blue"), ("The DoneFors", "Pouring Room")]:
        song_align = [r for r in alignment if r["artist"] == artist and r["song"] == song]
        song_candidates = [c for c in candidates if c["artist"] == artist and c["song"] == song]
        overlap = next(r for r in overlaps if r["artist"] == artist and r["song"] == song)
        common_start = float(overlap["common_aligned_start_seconds"])
        common_end = float(overlap["common_aligned_end_seconds"])
        ref = next(r for r in song_align if r["mix_id"] == overlap["reference_mix_id"])
        if (artist, song) == ("Broken Crank", "Red To Blue"):
            evidence = build_red_to_blue_evidence(Path(ref["source_path"]))
            best, _ = refine_and_select(evidence, song_align, song_candidates, common_start, common_end)
        else:
            evidence = build_proxy_evidence(artist, song, song_align)
            best, _ = choose_proxy(evidence, song_align, song_candidates, common_start, common_end)
        validate_decision(best, song_align, common_start, common_end)
        new_decisions.append(best)
    preserved = preserved_decisions()
    all_rows = preserved + [decision_to_row(d) for d in new_decisions]
    if len(all_rows) != 4:
        raise ValueError("final decision table does not contain exactly four songs")
    write_csv(OUT / "final_excerpt_decision.csv", all_rows, DECISION_COLUMNS)
    md = ["# Final Stage 2 Excerpt Decisions", "", "Exactly four 28-second song excerpts are now approved. These are song-section approvals only; no final three mix versions were selected and no Diff-MST features were extracted.", ""]
    for row in all_rows:
        md += [
            f"## {row['artist']} - {row['song']}",
            f"Approved aligned section: {row['selected_aligned_start_seconds']} to {row['selected_aligned_end_seconds']} seconds ({row['duration_seconds']} s).",
            f"Candidate rank {row['selected_original_candidate_rank']}; boundary shift {row['boundary_shift_from_candidate_seconds']} s; final score {row['final_score']}; confidence {row['decision_confidence']}.",
            f"Source/activity evidence: vocal {row['vocal_activity_coverage']}, bass {row['bass_activity_coverage']}, drums {row['drum_activity_coverage']}, other {row['other_instrument_activity_coverage']}, simultaneous core {row['simultaneous_core_activity_coverage']}.",
            f"Boundary-quality score: {row['boundary_quality_score']}; cross-mix consistency: {row['cross_mix_consistency']}.",
            f"Rationale: {row['selection_rationale']}",
            f"Evidence sources: {row['evidence_sources']}",
            "",
        ]
    (OUT / "final_excerpt_decision.md").write_text("\n".join(md), encoding="utf-8")
    render_approved_previews(all_rows, OUT / "approved_excerpt_preview_manifest.csv")
    validate_previews()
    config_path = REPO / "configs" / "stimulus_selection.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["approved_excerpts"] = [
        {
            "artist": r["artist"], "song": r["song"],
            "aligned_start_seconds": float(r["selected_aligned_start_seconds"]),
            "aligned_end_seconds": float(r["selected_aligned_end_seconds"]),
            "selected_candidate_rank": int(r["selected_original_candidate_rank"]),
            "selection_method": "automatic_source_aware" if "proxy" not in r["selection_rationale"] else "automatic_proxy_source_aware",
            "reviewer": "automated pipeline",
            "review_notes": f"{r['selection_rationale']}; final score {r['final_score']}, confidence {r['decision_confidence']}.",
        }
        for r in all_rows
    ]
    config_path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=False), encoding="utf-8")
    report = (OUT / "excerpt_selection_report.md").read_text(encoding="utf-8")
    block = ["", "## Consolidated Four-Song Stage 2 Approval", "", "Final approved excerpt decisions now contain exactly four songs. Lead Me and In The Meantime were preserved exactly; Red To Blue and Pouring Room were aligned, scored and automatically approved in the remaining Stage 2 pass.", ""]
    for r in all_rows:
        block.append(f"- {r['artist']} - {r['song']}: {r['selected_aligned_start_seconds']} to {r['selected_aligned_end_seconds']} s, score {r['final_score']}, confidence {r['decision_confidence']}.")
    block.append("")
    block.append("Approved diagnostic previews are consolidated in `approved_excerpt_previews/` with manifest `approved_excerpt_preview_manifest.csv`.")
    if "## Consolidated Four-Song Stage 2 Approval" in report:
        report = report[:report.index("## Consolidated Four-Song Stage 2 Approval")].rstrip() + "\n" + "\n".join(block).strip() + "\n"
    else:
        report = report.rstrip() + "\n\n" + "\n".join(block).strip() + "\n"
    (OUT / "excerpt_selection_report.md").write_text(report, encoding="utf-8")
    removed = cleanup_obsolete_previews()
    print("approved_decisions=4")
    for r in all_rows:
        print(f"{r['artist']} - {r['song']}: {r['selected_aligned_start_seconds']}-{r['selected_aligned_end_seconds']}")
    print(f"approved_previews=12")
    print(f"obsolete_preview_wavs_removed={len(removed)}")

if __name__ == "__main__":
    main()
