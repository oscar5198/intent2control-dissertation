from __future__ import annotations

import csv
from pathlib import Path

from stimulus_selection.config import SelectionConfig
from stimulus_selection.paths import relationship_data_dir, source_path_from_relative


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_relationship_tables(config: SelectionConfig) -> dict[str, list[dict[str, str]]]:
    data_dir = relationship_data_dir(config)
    return {
        "songs": read_csv_rows(data_dir / "songs.csv"),
        "mixes": read_csv_rows(data_dir / "mixes.csv"),
        "audio_files": read_csv_rows(data_dir / "audio_files.csv"),
    }


def classify_institution(code: str, system_codes: tuple[str, ...]) -> tuple[str, bool]:
    if not code:
        return "unknown", False
    if code in system_codes:
        return "automated_system", True
    return "university_or_institution", False


def canonical_mix_type(raw_mix_type: str, institution_code: str, system_codes: tuple[str, ...]) -> str:
    value = (raw_mix_type or "").strip().lower()
    if institution_code in system_codes:
        return "automated_mix"
    if "original" in value or "release" in value:
        return "original_release"
    if "analog" in value or "analogue" in value:
        return "analogue_mix"
    if value in {"human_or_reference", "human", "reference", "student", "professional"}:
        return "human_mix"
    return "unknown"


def build_joined_records(config: SelectionConfig) -> list[dict[str, str]]:
    tables = load_relationship_tables(config)
    songs = {row["song_id"]: row for row in tables["songs"]}
    mixes = {row["mix_id"]: row for row in tables["mixes"]}
    records: list[dict[str, str]] = []

    for audio in tables["audio_files"]:
        song = songs.get(audio["song_id"])
        mix = mixes.get(audio["mix_id"])
        join_status = "matched"
        if song is None and mix is None:
            join_status = "missing_song_and_mix"
        elif song is None:
            join_status = "missing_song"
        elif mix is None:
            join_status = "missing_mix"

        institution_code = (mix or {}).get("mixer_institution_code", "")
        category, is_system = classify_institution(institution_code, config.institution_system_codes)
        source_path = source_path_from_relative(config, audio["relative_path"])
        metadata_source = "relationship_tables"
        confidence = "high" if join_status == "matched" and institution_code else "low"

        records.append(
            {
                "artist": (song or {}).get("artist", ""),
                "song": (song or {}).get("title", audio.get("legacy_song_id", "")),
                "song_id": audio.get("song_id", ""),
                "mix_id": audio.get("mix_id", ""),
                "mixer_id": audio.get("legacy_mix_code", ""),
                "mixer_institution_code": institution_code,
                "institution_name": (mix or {}).get("mixer_institution_name", ""),
                "institution_category": category,
                "institution_confidence": confidence,
                "engineer_or_participant_id": "",
                "mix_type": canonical_mix_type((mix or {}).get("mix_type", ""), institution_code, config.institution_system_codes),
                "is_public_audio": str(bool(audio.get("relative_path", "").startswith("audio/"))).lower(),
                "is_system_generated": str(is_system).lower(),
                "metadata_source": metadata_source,
                "metadata_join_status": join_status,
                "source_path": str(source_path),
                "relative_source_path": audio.get("relative_path", ""),
                "filename": Path(audio.get("relative_path", "")).name,
                "extension": "." + audio.get("file_extension", "").lower().lstrip("."),
                "codec": audio.get("codec", ""),
                "sample_rate": audio.get("sample_rate_hz", ""),
                "channels": audio.get("channels", ""),
                "duration_seconds": audio.get("duration_seconds", ""),
                "bit_rate": audio.get("bitrate_bps", ""),
                "file_size_bytes": audio.get("file_size_bytes", ""),
                "_decode_status": audio.get("decode_status", ""),
            }
        )

    return records
