from __future__ import annotations

from pathlib import Path


def write_markdown_report(path: Path, inventory: list[dict[str, str]], summary: list[dict[str, str]]) -> None:
    by_title = {(row["artist"], row["song"]): row for row in summary}
    lead = by_title.get(("The DoneFors", "Lead Me"))
    itm = by_title.get(("Fredy V", "In The Meantime"))
    automated_excluded = sum(r["is_system_generated"] == "true" for r in inventory)
    ambiguous = [r for r in inventory if r["institution_confidence"] != "high" or r["metadata_join_status"] != "matched"]
    mp3_count = sum(r["extension"] == ".mp3" for r in inventory)

    lines = [
        "# Stage 1 Dataset Inspection Report",
        "",
        "This report was generated from canonical relationship tables and public listening-test audio.",
        "",
        "## Primary Candidates",
    ]
    for label, row in [("Lead Me", lead), ("In The Meantime", itm)]:
        if row is None:
            lines.append(f"- {label}: not found.")
            continue
        lines.append(
            f"- {row['artist']} - {row['song']}: {row['human_mix_count']} valid human stereo mixes; "
            f"{row['confident_real_institution_count']} real institutions "
            f"({row['real_institution_codes']}); Stage 2 suitable: {row['cross_institution_eligible']}."
        )

    lines.extend(
        [
            "",
            "## Institution And System Handling",
            f"- Automated/system mixes excluded from institution diversity: {automated_excluded}.",
            "- MG / MixGenius, AUTO, and Robot are classified as automated systems when present.",
            "",
            "## Metadata Issues",
            f"- Ambiguous or incomplete metadata rows: {len(ambiguous)}.",
            "",
            "## MP3 Excerpt Technical Note",
            f"- Public listening-test audio records are MP3 excerpts for {mp3_count} records.",
            "- Duration, channel count, sample rate, codec, bitrate, and file size come from canonical decoded metadata.",
            "- Sample-level peak/RMS screening for MP3 requires an installed MP3 decoder; rows are marked accordingly when unavailable.",
            "- Slight MP3 duration and decoder peak differences should be handled during Stage 2 alignment, not by modifying source audio in Stage 1.",
            "",
            "## Ranking",
            "",
            "| Rank | Artist | Song | Real institutions | Human mixes | Eligible | Notes |",
            "|---:|---|---|---:|---:|---|---|",
        ]
    )
    for row in summary:
        rank = row["recommendation_rank"] or "-"
        lines.append(
            f"| {rank} | {row['artist']} | {row['song']} | {row['confident_real_institution_count']} | "
            f"{row['human_mix_count']} | {row['cross_institution_eligible']} | {row['recommendation_notes']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
