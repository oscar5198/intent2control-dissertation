from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

from stimulus_selection.audio_probe import file_sha256, preview_fingerprint, probe_audio
from stimulus_selection.config import SelectionConfig
from stimulus_selection.metadata import build_joined_records

INVENTORY_COLUMNS = [
    "artist",
    "song",
    "song_id",
    "mix_id",
    "mixer_id",
    "mixer_institution_code",
    "institution_name",
    "institution_category",
    "institution_confidence",
    "engineer_or_participant_id",
    "mix_type",
    "is_public_audio",
    "is_system_generated",
    "metadata_source",
    "metadata_join_status",
    "source_path",
    "relative_source_path",
    "filename",
    "extension",
    "codec",
    "sample_rate",
    "channels",
    "duration_seconds",
    "bit_rate",
    "file_size_bytes",
    "readable",
    "contains_nan_or_inf",
    "peak_amplitude",
    "preview_rms",
    "near_silence_detected",
    "clipping_or_near_clipping_detected",
    "duplicate_file_hash",
    "duplicate_audio_candidate",
    "valid_for_analysis",
    "exclusion_reason",
    "validation_notes",
]


def _is_valid_record(row: dict[str, str], config: SelectionConfig) -> tuple[bool, str]:
    reasons: list[str] = []
    if row["is_public_audio"] != "true":
        reasons.append("not_public_audio")
    if row["readable"] != "true":
        reasons.append("unreadable_audio")
    if row["extension"].lower() not in config.allowed_extensions:
        reasons.append("unsupported_extension")
    if config.require_stereo and row["channels"] != "2":
        reasons.append("not_stereo")
    try:
        if float(row["duration_seconds"]) < config.minimum_duration_seconds:
            reasons.append("duration_below_minimum")
    except ValueError:
        reasons.append("unknown_duration")
    if row["contains_nan_or_inf"] == "true":
        reasons.append("contains_nan_or_inf")
    if row["near_silence_detected"] == "true":
        reasons.append("near_silence")
    if row["institution_category"] == "unknown":
        reasons.append("unknown_institution")
    if row["metadata_join_status"] != "matched":
        reasons.append(row["metadata_join_status"])
    return not reasons, ";".join(reasons)


def build_inventory(config: SelectionConfig) -> list[dict[str, str]]:
    rows = build_joined_records(config)
    hashes: list[str] = []
    fingerprints: list[str] = []

    for row in rows:
        path = Path(row["source_path"])
        probe = probe_audio(path, row["extension"], row.pop("_decode_status", ""))
        row.update(
            {
                "readable": str(probe.readable).lower(),
                "contains_nan_or_inf": probe.contains_nan_or_inf,
                "peak_amplitude": probe.peak_amplitude,
                "preview_rms": probe.preview_rms,
                "near_silence_detected": str(probe.near_silence_detected).lower(),
                "clipping_or_near_clipping_detected": str(probe.clipping_or_near_clipping_detected).lower(),
                "validation_notes": probe.validation_notes,
            }
        )
        row["_file_hash"] = file_sha256(path) if path.exists() else ""
        row["_fingerprint"] = preview_fingerprint(
            path,
            row["extension"],
            row["duration_seconds"],
            row["sample_rate"],
            row["channels"],
        )
        hashes.append(row["_file_hash"])
        fingerprints.append(row["_fingerprint"])

    hash_counts = Counter(h for h in hashes if h)
    fp_counts = Counter(fp for fp in fingerprints if fp)
    for row in rows:
        row["_exact_duplicate"] = str(bool(row["_file_hash"] and hash_counts[row["_file_hash"]] > 1)).lower()
        row["duplicate_file_hash"] = row["_file_hash"]
        row["duplicate_audio_candidate"] = str(bool(row["_fingerprint"] and fp_counts[row["_fingerprint"]] > 1)).lower()
        valid, reason = _is_valid_record(row, config)
        row["valid_for_analysis"] = str(valid).lower()
        row["exclusion_reason"] = reason
        row.pop("_file_hash", None)
        row.pop("_fingerprint", None)
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def inventory_by_song(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["song_id"]].append(row)
    return grouped
