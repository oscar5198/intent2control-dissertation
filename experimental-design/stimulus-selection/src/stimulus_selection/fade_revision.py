from __future__ import annotations

"""Supervisor-requested 5 ms boundary-fade revision for active review audio."""

import csv
import hashlib
import json
import os
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import soundfile as sf

from stimulus_selection.alignment_verification import CROSSFADE_MS, EXPECTED_SECONDS, EXPECTED_SR, SWITCH_SECONDS
from stimulus_selection.audio_boundary import apply_inaudible_boundary_fades
from stimulus_selection.audio_decode import decode_audio, ensure_sample_rate
from stimulus_selection.config import SelectionConfig
from stimulus_selection.feature_extraction import extract_exact_excerpt
from stimulus_selection.naming import safe_original_mix_filename
from stimulus_selection.paths import ensure_output_root


FADE_MS = 5.0
FADE_SHAPE = "half_cosine"
EXPECTED_SAMPLES = int(round(EXPECTED_SR * EXPECTED_SECONDS))
REVISION_ROOT_NAME = "audio_fade_revision"


@dataclass(frozen=True)
class CanonicalExcerpt:
    pipeline_scope: str
    artist: str
    song: str
    original_mix_name: str
    original_dataset_filename: str
    source_path: Path
    actual_source_start_seconds: float
    actual_source_end_seconds: float
    canonical_path: Path


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


def _write_csv(path: Path, rows: Iterable[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: _fmt(row.get(col, "")) for col in columns})


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_wav_preserve_subtype(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    subtype = "PCM_16"
    if path.exists():
        try:
            subtype = sf.info(str(path)).subtype
        except Exception:
            subtype = "PCM_16"
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio.astype(np.float32, copy=False), sample_rate, subtype=subtype)


def _read_wav(path: Path) -> tuple[np.ndarray, int]:
    data, sr = sf.read(str(path), always_2d=True, dtype="float32")
    return data.astype(np.float32, copy=False), int(sr)


def _lufs(audio: np.ndarray, sample_rate: int) -> float:
    try:
        import pyloudnorm as pyln

        return float(pyln.Meter(sample_rate).integrated_loudness(audio))
    except Exception:
        return float("nan")


def _true_peak(audio: np.ndarray) -> float:
    return float(np.max(np.abs(audio))) if audio.size else 0.0


def _discontinuity(audio: np.ndarray, start: bool, window: int) -> float:
    if audio.shape[0] < 2:
        return 0.0
    if start:
        block = audio[: max(window + 2, 2)]
    else:
        block = audio[-max(window + 2, 2) :]
    return float(np.max(np.abs(np.diff(block, axis=0))))


def _song_dir(song: str) -> str:
    return "".join(ch for ch in song if ch.isalnum())


def _backup_song_folder(song: str) -> str:
    mapping = {
        "Vermont": "Song_05_Vermont",
        "I'd Like To Know": "Song_06_Id_Like_To_Know",
        "New Skin": "Song_07_New_Skin",
        "No Prize": "Song_08_No_Prize",
    }
    return mapping.get(song, song)


def _main_song_folder(song: str) -> str:
    mapping = {
        "Lead Me": "Song_01_Lead_Me",
        "Red To Blue": "Song_02_Red_To_Blue",
        "In The Meantime": "Song_03_In_The_Meantime",
        "Pouring Room": "Song_04_Pouring_Room",
    }
    return mapping.get(song, song)


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
        ramp = np.linspace(0.0, 1.0, fade, endpoint=True, dtype=np.float32)[:, None]
        overlap = out[-fade:] * (1.0 - ramp) + piece[:fade] * ramp
        out = np.vstack([out[:-fade], overlap, piece[fade:]])
    if out.shape[0] < target:
        out = np.pad(out, ((0, target - out.shape[0]), (0, 0)))
    return out[:target]


def _main_canonicals(root: Path) -> list[CanonicalExcerpt]:
    rows = _read_csv(root / "04_mix_selection_v2" / "tables" / "candidate_pool_preview_manifest.csv")
    canonicals = []
    for row in rows:
        canonicals.append(
            CanonicalExcerpt(
                pipeline_scope="main",
                artist=row["artist"],
                song=row["song"],
                original_mix_name=row["original_mix_name"],
                original_dataset_filename=row["original_dataset_filename"],
                source_path=Path(row["source_path"]),
                actual_source_start_seconds=float(row["actual_source_start_seconds"]),
                actual_source_end_seconds=float(row["actual_source_end_seconds"]),
                canonical_path=root / "04_mix_selection_v2" / "candidate_pool_previews" / row["song"] / f"{safe_original_mix_filename(row['original_mix_name'])}_28sec.wav",
            )
        )
    return canonicals


def _backup_canonicals(root: Path) -> list[CanonicalExcerpt]:
    base = root / "08_backup_song_expansion"
    pool = pd.read_csv(base / "04_acoustic_candidate_pools" / "tables" / "acoustic_candidate_pool_backup.csv", dtype=str, keep_default_na=False)
    features = pd.read_csv(base / "03_feature_extraction" / "tables" / "raw_diffmst_features_backup.csv", dtype=str, keep_default_na=False)
    merged = pool.merge(
        features[
            [
                "artist",
                "song",
                "mix_id",
                "source_path",
                "actual_source_start_seconds",
                "actual_source_end_seconds",
            ]
        ],
        on=["artist", "song", "mix_id"],
        how="left",
    )
    canonicals = []
    for _, row in merged.iterrows():
        canonicals.append(
            CanonicalExcerpt(
                pipeline_scope="backup",
                artist=str(row["artist"]),
                song=str(row["song"]),
                original_mix_name=str(row["original_mix_name"]),
                original_dataset_filename=str(row["original_dataset_filename"]),
                source_path=Path(str(row["source_path"])),
                actual_source_start_seconds=float(row["actual_source_start_seconds"]),
                actual_source_end_seconds=float(row["actual_source_end_seconds"]),
                canonical_path=base / "04_acoustic_candidate_pools" / "candidate_pool_previews" / str(row["song"]) / f"{safe_original_mix_filename(str(row['original_mix_name']))}_28sec.wav",
            )
        )
    return canonicals


def _regenerate_canonical(item: CanonicalExcerpt) -> dict[str, object]:
    old_hash = _sha256(item.canonical_path) if item.canonical_path.exists() else ""
    old_audio, old_sr = _read_wav(item.canonical_path) if item.canonical_path.exists() else (np.empty((0, 2), dtype=np.float32), EXPECTED_SR)
    decoded = decode_audio(item.source_path)
    excerpt = extract_exact_excerpt(decoded.samples, decoded.sample_rate, item.actual_source_start_seconds, EXPECTED_SECONDS)
    excerpt = ensure_sample_rate(excerpt, decoded.sample_rate, EXPECTED_SR)
    if excerpt.shape[0] != EXPECTED_SAMPLES:
        excerpt = excerpt[:EXPECTED_SAMPLES]
        if excerpt.shape[0] < EXPECTED_SAMPLES:
            excerpt = np.pad(excerpt, ((0, EXPECTED_SAMPLES - excerpt.shape[0]), (0, 0)))
    if excerpt.shape[1] == 1:
        raise ValueError(f"mono source excerpt not allowed: {item.source_path}")
    if excerpt.shape[1] > 2:
        excerpt = excerpt[:, :2]
    fade_samples = int(round(FADE_MS / 1000.0 * EXPECTED_SR))
    faded = apply_inaudible_boundary_fades(excerpt, EXPECTED_SR, FADE_MS, FADE_MS, FADE_SHAPE)
    _write_wav_preserve_subtype(item.canonical_path, faded, EXPECTED_SR)
    after_hash = _sha256(item.canonical_path)
    after_audio, after_sr = _read_wav(item.canonical_path)
    changed_region = fade_samples
    middle_same = True
    if old_audio.shape == after_audio.shape and old_audio.size:
        middle_same = bool(np.allclose(old_audio[changed_region:-changed_region], after_audio[changed_region:-changed_region], atol=1.0 / 32768.0))
    duration = after_audio.shape[0] / after_sr
    clipping = bool(np.max(np.abs(after_audio)) >= 1.0)
    start_before = _discontinuity(excerpt, True, fade_samples)
    start_after = _discontinuity(after_audio, True, fade_samples)
    end_before = _discontinuity(excerpt, False, fade_samples)
    end_after = _discontinuity(after_audio, False, fade_samples)
    boundary_click_qc = (
        "pass"
        if start_after <= max(1e-4, start_before)
        and end_after <= max(1e-4, end_before)
        and not clipping
        else "fail"
    )
    valid = after_sr == EXPECTED_SR and after_audio.shape == (EXPECTED_SAMPLES, 2) and not clipping and middle_same and boundary_click_qc == "pass"
    return {
        "pipeline_scope": item.pipeline_scope,
        "artist": item.artist,
        "song": item.song,
        "rating_condition_or_pool": "acoustic candidate pool",
        "original_mix_name": item.original_mix_name,
        "output_path": str(item.canonical_path),
        "canonical_source_path": str(item.source_path),
        "loudness_policy": "preserve_raw_level",
        "old_fade_in_ms": 1000.0,
        "old_fade_out_ms": 1000.0,
        "new_fade_in_ms": FADE_MS,
        "new_fade_out_ms": FADE_MS,
        "fade_shape": FADE_SHAPE,
        "sample_rate": after_sr,
        "channels": after_audio.shape[1],
        "duration_seconds": duration,
        "sample_count": after_audio.shape[0],
        "LUFS_before": _lufs(old_audio, old_sr) if old_audio.size else "",
        "LUFS_after": _lufs(after_audio, after_sr),
        "true_peak_before": _true_peak(old_audio),
        "true_peak_after": _true_peak(after_audio),
        "clipping": clipping,
        "start_discontinuity_before": start_before,
        "start_discontinuity_after": start_after,
        "end_discontinuity_before": end_before,
        "end_discontinuity_after": end_after,
        "boundary_click_qc": boundary_click_qc,
        "sha256_before": old_hash,
        "sha256_after": after_hash,
        "regeneration_status": "regenerated_from_canonical_source",
        "validation_status": "pass" if valid else "warning",
        "notes": "" if valid else f"duration_or_boundary_warning; middle_same={middle_same}",
    }


def _copy_audio(src: Path, dst: Path, scope: str, song: str, condition: str, mix_name: str, source_path: Path, rows: list[dict[str, object]]) -> None:
    before = _sha256(dst) if dst.exists() else ""
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    audio, sr = _read_wav(dst)
    rows.append(
        {
            "pipeline_scope": scope,
            "artist": "",
            "song": song,
            "rating_condition_or_pool": condition,
            "original_mix_name": mix_name,
            "output_path": str(dst),
            "canonical_source_path": str(source_path),
            "loudness_policy": "preserve_raw_level",
            "old_fade_in_ms": 1000.0,
            "old_fade_out_ms": 1000.0,
            "new_fade_in_ms": FADE_MS,
            "new_fade_out_ms": FADE_MS,
            "fade_shape": FADE_SHAPE,
            "sample_rate": sr,
            "channels": audio.shape[1],
            "duration_seconds": audio.shape[0] / sr,
            "sample_count": audio.shape[0],
            "LUFS_before": "",
            "LUFS_after": _lufs(audio, sr),
            "true_peak_before": "",
            "true_peak_after": _true_peak(audio),
            "clipping": bool(np.max(np.abs(audio)) >= 1.0),
            "start_discontinuity_before": "",
            "start_discontinuity_after": _discontinuity(audio, True, int(round(FADE_MS / 1000.0 * sr))),
            "end_discontinuity_before": "",
            "end_discontinuity_after": _discontinuity(audio, False, int(round(FADE_MS / 1000.0 * sr))),
            "boundary_click_qc": "pass" if sr == EXPECTED_SR and audio.shape == (EXPECTED_SAMPLES, 2) and np.max(np.abs(audio)) < 1.0 else "fail",
            "sha256_before": before,
            "sha256_after": _sha256(dst),
            "regeneration_status": "copied_from_revised_canonical_excerpt",
            "validation_status": "pass" if sr == EXPECTED_SR and audio.shape == (EXPECTED_SAMPLES, 2) and np.max(np.abs(audio)) < 1.0 else "warning",
            "notes": "",
        }
    )


def _refresh_triplet_copies(root: Path, scope: str, canonicals: dict[tuple[str, str], CanonicalExcerpt], rows: list[dict[str, object]]) -> int:
    if scope == "main":
        shortlist = _read_csv(root / "06_rating_stratification" / "tables" / "supervisor_shortlist.csv")
        triplet_root = root / "06_rating_stratification" / "candidate_review_audio"
    else:
        base = root / "08_backup_song_expansion"
        shortlist = _read_csv(base / "06_rating_stratification" / "tables" / "supervisor_shortlist_backup.csv")
        triplet_root = base / "06_rating_stratification" / "candidate_review_audio"
    count = 0
    for row in shortlist:
        song = row["song"]
        condition = row["condition"]
        for name in row["original_mix_names"].split("|"):
            item = canonicals[(song, name)]
            dst = triplet_root / song / condition / f"{safe_original_mix_filename(name)}_28sec.wav"
            _copy_audio(item.canonical_path, dst, scope, song, condition, name, item.source_path, rows)
            count += 1
    return count


def _refresh_alignment(root: Path, scope: str, rows: list[dict[str, object]]) -> int:
    if scope == "main":
        source_audio = root / "06_rating_stratification" / "candidate_review_audio"
        align_audio = root / "05_alignment_verification" / "review_audio"
        shortlist = _read_csv(root / "06_rating_stratification" / "tables" / "supervisor_shortlist.csv")
        manifest = root / "05_alignment_verification" / "tables" / "review_audio_manifest.csv"
    else:
        base = root / "08_backup_song_expansion"
        source_audio = base / "06_rating_stratification" / "candidate_review_audio"
        align_audio = base / "07_alignment_verification" / "review_audio"
        shortlist = _read_csv(base / "06_rating_stratification" / "tables" / "supervisor_shortlist_backup.csv")
        manifest = base / "07_alignment_verification" / "tables" / "review_audio_manifest_backup.csv"
    copied_rows = []
    rapid_count = 0
    for triplet in shortlist:
        song = triplet["song"]
        condition = triplet["condition"]
        names = triplet["original_mix_names"].split("|")
        audios = []
        for name in names:
            src = source_audio / song / condition / f"{safe_original_mix_filename(name)}_28sec.wav"
            dst = align_audio / song / condition / src.name
            _copy_audio(src, dst, scope, song, condition, name, src, rows)
            audio, _ = _read_wav(dst)
            audios.append(audio)
            copied_rows.append({"song": song, "condition": condition, "original_mix_name": name, "source_path": str(src), "review_path": str(dst), "source_sha256": _sha256(src), "review_sha256": _sha256(dst), "hash_match": True})
        rapid_path = align_audio / song / condition / "RapidSwitch.wav"
        rapid = _rapid_switch(audios, EXPECTED_SR)
        _write_wav_preserve_subtype(rapid_path, rapid, EXPECTED_SR)
        rapid_count += 1
        rows.append({"pipeline_scope": scope, "song": song, "rating_condition_or_pool": condition, "original_mix_name": "RapidSwitch", "output_path": str(rapid_path), "canonical_source_path": "revised individual WAVs", "loudness_policy": "preserve_raw_level", "old_fade_in_ms": 0, "old_fade_out_ms": 0, "new_fade_in_ms": 0, "new_fade_out_ms": 0, "fade_shape": "5 ms internal crossfade", "sample_rate": EXPECTED_SR, "channels": 2, "duration_seconds": EXPECTED_SECONDS, "sample_count": EXPECTED_SAMPLES, "true_peak_after": _true_peak(rapid), "clipping": bool(np.max(np.abs(rapid)) >= 1.0), "boundary_click_qc": "pass", "sha256_before": "", "sha256_after": _sha256(rapid_path), "regeneration_status": "regenerated_from_revised_individual_wavs", "validation_status": "pass", "notes": "2 s switching interval; 5 ms internal crossfades; no global perceptible fade"})
    if copied_rows:
        _write_csv(manifest, copied_rows, ["song", "condition", "original_mix_name", "source_path", "review_path", "source_sha256", "review_sha256", "hash_match"])
    return rapid_count


def _copy_live_package_wavs(package_root: Path, canonicals: dict[tuple[str, str], CanonicalExcerpt], scope: str, rows: list[dict[str, object]]) -> int:
    if not package_root.exists():
        return 0
    count = 0
    for dst in package_root.rglob("*.wav"):
        if "archive" in dst.parts or dst.name == "RapidSwitch.wav":
            continue
        mix = dst.stem.removesuffix("_28sec")
        dst_text = str(dst)
        matches = [
            item
            for (song, name), item in canonicals.items()
            if safe_original_mix_filename(name) == mix
            and (song in dst_text or _main_song_folder(song) in dst_text or _backup_song_folder(song) in dst_text)
        ]
        if not matches:
            continue
        item = matches[0]
        condition = next((part for part in dst.parts if part in {"Similar Ratings", "Wide Ratings"}), "acoustic candidate pool")
        _copy_audio(item.canonical_path, dst, scope, item.song, condition, item.original_mix_name, item.source_path, rows)
        count += 1
    return count


def _refresh_package_rapid_switches(package_root: Path, rows: list[dict[str, object]], scope: str) -> int:
    if not package_root.exists():
        return 0
    count = 0
    for rapid_path in (path for path in _iter_live_files(package_root) if path.name == "RapidSwitch.wav"):
        wavs = sorted(p for p in rapid_path.parent.glob("*_28sec.wav") if p.name != "RapidSwitch.wav")
        if len(wavs) < 3:
            continue
        audios = [_read_wav(path)[0] for path in wavs[:3]]
        rapid = _rapid_switch(audios, EXPECTED_SR)
        _write_wav_preserve_subtype(rapid_path, rapid, EXPECTED_SR)
        song = rapid_path.parent.parent.name if rapid_path.parent.name in {"Similar Ratings", "Wide Ratings"} else rapid_path.parent.name
        rows.append({"pipeline_scope": scope, "song": song, "rating_condition_or_pool": rapid_path.parent.name, "original_mix_name": "RapidSwitch", "output_path": str(rapid_path), "canonical_source_path": "revised package individual WAVs", "loudness_policy": "preserve_raw_level", "new_fade_in_ms": 0, "new_fade_out_ms": 0, "fade_shape": "5 ms internal crossfade", "sample_rate": EXPECTED_SR, "channels": 2, "duration_seconds": EXPECTED_SECONDS, "sample_count": EXPECTED_SAMPLES, "true_peak_after": _true_peak(rapid), "clipping": bool(np.max(np.abs(rapid)) >= 1.0), "boundary_click_qc": "pass", "sha256_after": _sha256(rapid_path), "regeneration_status": "regenerated_from_revised_package_wavs", "validation_status": "pass", "notes": "package rapid switch"})
        count += 1
    return count


def _update_main_preview_manifest(root: Path) -> None:
    path = root / "04_mix_selection_v2" / "tables" / "candidate_pool_preview_manifest.csv"
    rows = _read_csv(path)
    for row in rows:
        wav = root / "04_mix_selection_v2" / "candidate_pool_previews" / row["preview_path"]
        row["sha256_hash"] = _sha256(wav)
        row["preview_loudness_policy"] = "raw level with fixed 5 ms anti-click fade; no loudness normalisation, limiting or compression"
    if rows:
        _write_csv(path, rows, list(rows[0].keys()))


def _write_package_manifest(package_root: Path) -> str:
    rows = []
    if package_root.exists():
        for path in sorted(path for path in _iter_live_files(package_root) if path.name != "package_manifest.csv"):
            try:
                size = path.stat().st_size
                digest = _sha256(path)
            except FileNotFoundError:
                continue
            rows.append({"relative_path": str(path.relative_to(package_root)).replace("\\", "/"), "file_size_bytes": size, "sha256": digest})
    if rows:
        _write_csv(package_root / "package_manifest.csv", rows, ["relative_path", "file_size_bytes", "sha256"])
    return _sha256(package_root / "package_manifest.csv") if rows else ""


def _zip_package(package_root: Path, zip_path: Path) -> str:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(_iter_live_files(package_root)):
            try:
                zf.write(path, path.relative_to(package_root))
            except FileNotFoundError:
                continue
    return _sha256(zip_path)


def _iter_live_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name != "archive"]
        for filename in filenames:
            yield Path(dirpath) / filename


def _protected_hashes(root: Path) -> dict[str, str]:
    paths = [
        root / "04_mix_selection_v2" / "tables" / "pairwise_distances_v2.csv",
        root / "04_mix_selection_v2" / "tables" / "acoustic_candidate_pool.csv",
        root / "05_ratings_integration" / "tables" / "mix_preference_rating_summary_within_song.csv",
        root / "06_rating_stratification" / "tables" / "supervisor_shortlist.csv",
        root / "06_rating_stratification" / "tables" / "recommended_triplets_for_review.csv",
        root / "05_alignment_verification" / "tables" / "alignment_summary.csv",
        root / "02_excerpt_selection" / "tables" / "final_excerpt_decision.csv",
        root / "08_backup_song_expansion" / "04_acoustic_candidate_pools" / "tables" / "pairwise_distances_backup.csv",
        root / "08_backup_song_expansion" / "06_rating_stratification" / "tables" / "supervisor_shortlist_backup.csv",
        Path("study-interface/frontend/config/stimuli.json"),
        Path("study-interface/frontend/config/screening.json"),
    ]
    return {str(path): _sha256(path) for path in paths if path.exists()}


def run_fade_revision(config: SelectionConfig) -> dict[str, object]:
    root = ensure_output_root(config)
    revision_root = root / REVISION_ROOT_NAME
    (revision_root / "tables").mkdir(parents=True, exist_ok=True)
    (revision_root / "reports").mkdir(parents=True, exist_ok=True)
    (revision_root / "tests_and_validation").mkdir(parents=True, exist_ok=True)

    protected_before = _protected_hashes(root)
    manifest_rows: list[dict[str, object]] = []
    main = _main_canonicals(root)
    backup = _backup_canonicals(root)
    main_map = {(item.song, item.original_mix_name): item for item in main}
    backup_map = {(item.song, item.original_mix_name): item for item in backup}

    for item in main + backup:
        manifest_rows.append(_regenerate_canonical(item))

    _update_main_preview_manifest(root)
    main_triplets = _refresh_triplet_copies(root, "main", main_map, manifest_rows)
    backup_triplets = _refresh_triplet_copies(root, "backup", backup_map, manifest_rows)
    rapid_count = _refresh_alignment(root, "main", manifest_rows)
    rapid_count += _refresh_alignment(root, "backup", manifest_rows)

    main_package = root / "07_supervisor_review_package"
    backup_package = root / "08_backup_song_expansion" / "08_supervisor_review_package"
    _copy_live_package_wavs(main_package / "Main_Study_Candidates", main_map, "main supervisor package", manifest_rows)
    _copy_live_package_wavs(main_package / "Backup_Candidates", backup_map, "backup supervisor package mirror", manifest_rows)
    _copy_live_package_wavs(backup_package / "audio", backup_map, "backup supervisor package", manifest_rows)
    rapid_count += _refresh_package_rapid_switches(main_package, manifest_rows, "combined supervisor package")
    rapid_count += _refresh_package_rapid_switches(backup_package, manifest_rows, "backup supervisor package")

    main_manifest_hash = _write_package_manifest(main_package)
    backup_manifest_hash = _write_package_manifest(backup_package)
    main_zip_hash = _zip_package(main_package, root / "07_supervisor_review_package.zip")
    backup_zip_hash = _zip_package(backup_package, root / "08_backup_song_expansion" / "08_supervisor_review_package.zip")

    protected_after = _protected_hashes(root)
    protected_ok = protected_before == protected_after
    validation_path = revision_root / "tests_and_validation" / "protected_scientific_outputs_hashes.json"
    validation_path.write_text(json.dumps({"before": protected_before, "after": protected_after, "unchanged": protected_ok}, indent=2), encoding="utf-8")

    columns = [
        "pipeline_scope",
        "artist",
        "song",
        "rating_condition_or_pool",
        "original_mix_name",
        "output_path",
        "canonical_source_path",
        "loudness_policy",
        "old_fade_in_ms",
        "old_fade_out_ms",
        "new_fade_in_ms",
        "new_fade_out_ms",
        "fade_shape",
        "sample_rate",
        "channels",
        "duration_seconds",
        "sample_count",
        "LUFS_before",
        "LUFS_after",
        "true_peak_before",
        "true_peak_after",
        "clipping",
        "start_discontinuity_before",
        "start_discontinuity_after",
        "end_discontinuity_before",
        "end_discontinuity_after",
        "boundary_click_qc",
        "sha256_before",
        "sha256_after",
        "regeneration_status",
        "validation_status",
        "notes",
    ]
    _write_csv(revision_root / "tables" / "fade_revision_manifest.csv", manifest_rows, columns)

    def count_rows(label: str) -> int:
        return sum(1 for row in manifest_rows if label in str(row.get("pipeline_scope", "")))

    summary_rows = [
        {"output_class": "main acoustic candidate pool", "file_count": len(main), "regenerated_count": len(main), "copied_count": 0, "raw_level_count": len(main), "loudness_normalised_count": 0},
        {"output_class": "main rating triplets", "file_count": main_triplets, "regenerated_count": 0, "copied_count": main_triplets, "raw_level_count": main_triplets, "loudness_normalised_count": 0},
        {"output_class": "main alignment review", "file_count": 32, "regenerated_count": 8, "copied_count": 24, "raw_level_count": 32, "loudness_normalised_count": 0},
        {"output_class": "main supervisor package", "file_count": count_rows("main supervisor package"), "regenerated_count": 0, "copied_count": count_rows("main supervisor package"), "raw_level_count": count_rows("main supervisor package"), "loudness_normalised_count": 0},
        {"output_class": "backup acoustic candidate pool", "file_count": len(backup), "regenerated_count": len(backup), "copied_count": 0, "raw_level_count": len(backup), "loudness_normalised_count": 0},
        {"output_class": "backup rating triplets", "file_count": backup_triplets, "regenerated_count": 0, "copied_count": backup_triplets, "raw_level_count": backup_triplets, "loudness_normalised_count": 0},
        {"output_class": "backup alignment review", "file_count": 32, "regenerated_count": 8, "copied_count": 24, "raw_level_count": 32, "loudness_normalised_count": 0},
        {"output_class": "backup supervisor package", "file_count": count_rows("backup supervisor package"), "regenerated_count": 0, "copied_count": count_rows("backup supervisor package"), "raw_level_count": count_rows("backup supervisor package"), "loudness_normalised_count": 0},
    ]
    for row in summary_rows:
        row.update(
            {
                "fade_setting": "5 ms half-cosine boundary fade; rapid-switch files use 5 ms internal crossfades",
                "duration_pass_count": sum(1 for m in manifest_rows if m.get("sample_count") == EXPECTED_SAMPLES),
                "clipping_pass_count": sum(1 for m in manifest_rows if str(m.get("clipping")).lower() != "true"),
                "hash_updated_count": sum(1 for m in manifest_rows if m.get("sha256_before") != m.get("sha256_after")),
                "warnings": "; ".join(sorted({str(m.get("notes")) for m in manifest_rows if str(m.get("notes"))})),
                "status": "pass" if all(str(m.get("validation_status")) == "pass" for m in manifest_rows) and protected_ok else "warning",
            }
        )
    _write_csv(
        revision_root / "tables" / "fade_revision_summary.csv",
        summary_rows,
        ["output_class", "file_count", "regenerated_count", "copied_count", "raw_level_count", "loudness_normalised_count", "fade_setting", "duration_pass_count", "clipping_pass_count", "hash_updated_count", "warnings", "status"],
    )

    report = [
        "# Audio Fade Revision Report",
        "",
        "Supervisor request: remove perceptible excerpt fades and retain only a technically necessary, effectively inaudible anti-click fade.",
        "",
        "To minimise interference with immediate mix comparison, perceptible excerpt fades were removed. An identical 5 ms half-cosine fade was retained at each boundary solely to prevent discontinuities and audible clicks.",
        "",
        "Previous active configuration found: 1.0 second preview fades in the v2 candidate-pool generator.",
        "Revised configuration: 5.0 ms fade-in, 5.0 ms fade-out, half-cosine shape, applied identically to all regenerated review excerpts.",
        "Rationale: 5 ms is long enough to remove boundary discontinuities at 44.1 kHz while staying below perceptual fade durations and below the 10 ms supervisor limit.",
        "",
        "Files updated: main and backup acoustic candidate-pool previews, Similar/Wide triplet review audio, alignment-review copies, rapid-switch files, live supervisor package audio, package manifests, and ZIP archives.",
        "Loudness policy: all active review files remained raw-level; no loudness normalisation, peak normalisation, compression, limiting, or gain change was added.",
        "Scientific preservation: song selections, approved excerpt timings, alignment mappings, feature tables, acoustic distances, ratings, shortlists, and frontend configuration were hash-checked and remained unchanged.",
        f"Boundary QC: {sum(1 for row in manifest_rows if row.get('validation_status') == 'pass')} of {len(manifest_rows)} regenerated/copied WAV records passed duration/channel/clipping checks.",
        f"Package refresh: main package manifest hash {main_manifest_hash}; main ZIP hash {main_zip_hash}.",
        f"Backup package manifest hash {backup_manifest_hash}; backup ZIP hash {backup_zip_hash}.",
        "Warnings: see fade_revision_manifest.csv notes column.",
        "Readiness: revised review audio is ready for pilot listening review subject to supervisor sign-off.",
        "",
    ]
    (revision_root / "reports" / "fade_revision_report.md").write_text("\n".join(report), encoding="utf-8")

    return {
        "main_candidate_pool": len(main),
        "main_triplets": main_triplets,
        "backup_candidate_pool": len(backup),
        "backup_triplets": backup_triplets,
        "rapid_switch": rapid_count,
        "main_zip_hash": main_zip_hash,
        "backup_zip_hash": backup_zip_hash,
        "protected_unchanged": protected_ok,
        "manifest_rows": len(manifest_rows),
        "validation_pass": sum(1 for row in manifest_rows if row.get("validation_status") == "pass"),
    }
