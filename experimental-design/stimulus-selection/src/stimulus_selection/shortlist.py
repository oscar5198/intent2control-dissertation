from __future__ import annotations

from collections import defaultdict

from stimulus_selection.audio_inventory import inventory_by_song
from stimulus_selection.config import SelectionConfig

SUMMARY_COLUMNS = [
    "artist",
    "song",
    "song_id",
    "total_audio_records",
    "public_audio_records",
    "readable_audio_files",
    "valid_stereo_mixes",
    "human_mix_count",
    "automated_mix_count",
    "confident_real_institution_count",
    "real_institution_codes",
    "real_institution_names",
    "uncertain_institution_count",
    "sample_rate_values",
    "codec_values",
    "duration_min_seconds",
    "duration_max_seconds",
    "duration_range_seconds",
    "exact_duplicate_count",
    "possible_audio_duplicate_count",
    "metadata_confidence",
    "cross_institution_eligible",
    "recommended_for_consideration",
    "recommendation_rank",
    "recommendation_notes",
]


def _duration_values(rows: list[dict[str, str]]) -> list[float]:
    values = []
    for row in rows:
        try:
            values.append(float(row["duration_seconds"]))
        except ValueError:
            pass
    return values


def build_song_summary(rows: list[dict[str, str]], config: SelectionConfig) -> list[dict[str, str]]:
    summaries = []
    primary = {(s["artist"], s["song"]) for s in config.primary_candidate_songs}
    for song_rows in inventory_by_song(rows).values():
        first = song_rows[0]
        valid = [r for r in song_rows if r["valid_for_analysis"] == "true"]
        human = [r for r in valid if r["mix_type"] == "human_mix" and r["is_system_generated"] != "true"]
        automated = [r for r in song_rows if r["is_system_generated"] == "true" or r["mix_type"] == "automated_mix"]
        real = {
            r["mixer_institution_code"]: r["institution_name"]
            for r in human
            if r["institution_category"] == "university_or_institution"
            and r["institution_confidence"] == "high"
        }
        uncertain = [
            r
            for r in song_rows
            if r["institution_confidence"] != "high" or r["institution_category"] == "unknown"
        ]
        durations = _duration_values(song_rows)
        readable = [r for r in song_rows if r["readable"] == "true"]
        eligible = bool(len(real) >= 2 and len(human) >= 3 and readable and not uncertain)
        metadata_confidence = "high" if not uncertain else "medium"
        duration_range = (max(durations) - min(durations)) if durations else 0.0
        notes = []
        if (first["artist"], first["song"]) in primary:
            notes.append("primary_candidate")
        if any(r["extension"] == ".mp3" for r in song_rows):
            notes.append("public_audio_is_mp3_excerpt")
        if duration_range > 0.25:
            notes.append("duration_varies_across_public_files")
        summaries.append(
            {
                "artist": first["artist"],
                "song": first["song"],
                "song_id": first["song_id"],
                "total_audio_records": str(len(song_rows)),
                "public_audio_records": str(sum(r["is_public_audio"] == "true" for r in song_rows)),
                "readable_audio_files": str(len(readable)),
                "valid_stereo_mixes": str(len(valid)),
                "human_mix_count": str(len(human)),
                "automated_mix_count": str(len(automated)),
                "confident_real_institution_count": str(len(real)),
                "real_institution_codes": "|".join(sorted(real)),
                "real_institution_names": "|".join(real[k] for k in sorted(real)),
                "uncertain_institution_count": str(len(uncertain)),
                "sample_rate_values": "|".join(sorted({r["sample_rate"] for r in song_rows if r["sample_rate"]})),
                "codec_values": "|".join(sorted({r["codec"] for r in song_rows if r["codec"]})),
                "duration_min_seconds": f"{min(durations):.6f}" if durations else "",
                "duration_max_seconds": f"{max(durations):.6f}" if durations else "",
                "duration_range_seconds": f"{duration_range:.6f}" if durations else "",
                "exact_duplicate_count": str(sum(r.get("_exact_duplicate") == "true" for r in song_rows)),
                "possible_audio_duplicate_count": str(sum(r["duplicate_audio_candidate"] == "true" for r in song_rows)),
                "metadata_confidence": metadata_confidence,
                "cross_institution_eligible": str(eligible).lower(),
                "recommended_for_consideration": str(eligible).lower(),
                "recommendation_rank": "",
                "recommendation_notes": ";".join(notes),
            }
        )

    summaries.sort(
        key=lambda r: (
            int(r["confident_real_institution_count"]),
            int(r["human_mix_count"]),
            1 if r["metadata_confidence"] == "high" else 0,
            -float(r["duration_range_seconds"] or 0),
        ),
        reverse=True,
    )
    rank = 1
    for summary in summaries:
        if summary["recommended_for_consideration"] == "true":
            summary["recommendation_rank"] = str(rank)
            rank += 1
    return summaries


def institution_mapping_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = {}
    for row in rows:
        key = (row["mixer_institution_code"], row["institution_name"], row["institution_category"])
        seen[key] = {
            "mixer_institution_code": row["mixer_institution_code"],
            "institution_name": row["institution_name"],
            "institution_category": row["institution_category"],
            "institution_confidence": row["institution_confidence"],
            "metadata_source": row["metadata_source"],
            "is_system_generated": row["is_system_generated"],
        }
    return sorted(seen.values(), key=lambda r: (r["institution_category"], r["mixer_institution_code"]))
