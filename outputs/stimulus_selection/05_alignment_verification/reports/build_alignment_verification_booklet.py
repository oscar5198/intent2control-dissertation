from __future__ import annotations

import csv
import hashlib
import os
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
PHASE2C = REPO_ROOT / "outputs" / "stimulus_selection" / "05_alignment_verification"
REPORTS = PHASE2C / "reports"
TABLES = PHASE2C / "tables"
FIGURES = PHASE2C / "figures"
REVIEW_AUDIO = PHASE2C / "review_audio"
RECOMMENDATIONS = (
    REPO_ROOT
    / "outputs"
    / "stimulus_selection"
    / "06_rating_stratification"
    / "tables"
    / "recommended_triplets_for_review.csv"
)

PDF_PATH = REPORTS / "alignment_verification_booklet.pdf"
SOURCE_MD_PATH = REPORTS / "alignment_verification_booklet_source.md"
VALIDATION_MD_PATH = REPORTS / "alignment_verification_booklet_validation.md"

TRIPLET_ORDER = [
    ("In The Meantime", "Similar Ratings"),
    ("In The Meantime", "Wide Ratings"),
    ("Lead Me", "Similar Ratings"),
    ("Lead Me", "Wide Ratings"),
    ("Pouring Room", "Similar Ratings"),
    ("Pouring Room", "Wide Ratings"),
    ("Red To Blue", "Similar Ratings"),
    ("Red To Blue", "Wide Ratings"),
]

SOURCE_TABLES = [
    TABLES / "pairwise_alignment_verification.csv",
    TABLES / "alignment_summary.csv",
    TABLES / "manual_alignment_review.csv",
    TABLES / "review_audio_manifest.csv",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(PHASE2C).as_posix()


def safe_anchor(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def mix_display(mix_names: str) -> str:
    return mix_names.replace("|", " | ")


def para(text: object, style: ParagraphStyle) -> Paragraph:
    text = "" if text is None else str(text)
    text = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )
    return Paragraph(text, style)


def link_para(label: str, path: Path, style: ParagraphStyle) -> Paragraph:
    safe_label = label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(f'<a href="{file_uri(path)}">{safe_label}</a>', style)


def status_color(status: str) -> colors.Color:
    return {
        "PASS": colors.HexColor("#DDEFE2"),
        "REVIEW": colors.HexColor("#FFF2CC"),
        "FAIL": colors.HexColor("#F4D5D5"),
    }.get(status, colors.white)


def table_style(header_rows: int = 1, font_size: int = 7) -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, header_rows - 1), colors.HexColor("#E9EDF3")),
            ("TEXTCOLOR", (0, 0), (-1, header_rows - 1), colors.HexColor("#172033")),
            ("FONTNAME", (0, 0), (-1, header_rows - 1), "Helvetica-Bold"),
            ("FONTNAME", (0, header_rows), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
            ("LEADING", (0, 0), (-1, -1), font_size + 2),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C8CED8")),
            ("ROWBACKGROUNDS", (0, header_rows), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
    )


def on_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#5C6470"))
    canvas.drawString(0.55 * inch, 0.35 * inch, "Alignment Verification Booklet - Phase 2C")
    canvas.drawRightString(10.45 * inch, 0.35 * inch, f"Page {doc.page}")
    canvas.restoreState()


def build_context() -> dict[str, object]:
    summary = read_csv(TABLES / "alignment_summary.csv")
    pairwise = read_csv(TABLES / "pairwise_alignment_verification.csv")
    manual = read_csv(TABLES / "manual_alignment_review.csv")
    manifest = read_csv(TABLES / "review_audio_manifest.csv")
    recs = read_csv(RECOMMENDATIONS)

    summary_by_key = {(row["song"], row["condition"]): row for row in summary}
    manual_by_key = {(row["song"], row["condition"]): row for row in manual}
    rec_by_key = {(row["song"], row["condition"]): row for row in recs}
    pairwise_by_key: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in pairwise:
        pairwise_by_key[(row["song"], row["condition"])].append(row)

    manifest_by_key: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in manifest:
        manifest_by_key[(row["song"], row["condition"])].append(row)

    triplets: list[dict[str, object]] = []
    for key in TRIPLET_ORDER:
        srow = summary_by_key[key]
        mrow = manual_by_key[key]
        rrow = rec_by_key[key]
        song, condition = key
        stacked = FIGURES / song / condition / "stacked_waveforms.png"
        zoom = FIGURES / song / condition / "strongest_transient_zoom.png"
        rapid = REVIEW_AUDIO / song / condition / "RapidSwitch.wav"
        individual_audio = [
            REVIEW_AUDIO / song / condition / f"{mix}_28sec.wav"
            for mix in srow["mix_names"].split("|")
        ]
        triplets.append(
            {
                "key": key,
                "summary": srow,
                "manual": mrow,
                "recommendation": rrow,
                "pairwise": pairwise_by_key[key],
                "manifest": manifest_by_key[key],
                "stacked": stacked,
                "zoom": zoom,
                "rapid": rapid,
                "individual_audio": individual_audio,
            }
        )

    thresholds = pairwise[0]["thresholds"] if pairwise else ""
    return {
        "summary": summary,
        "pairwise": pairwise,
        "manual": manual,
        "manifest": manifest,
        "recommendations": recs,
        "triplets": triplets,
        "thresholds": thresholds,
    }


def write_source_md(ctx: dict[str, object]) -> None:
    triplets = ctx["triplets"]
    summary = ctx["summary"]
    thresholds = ctx["thresholds"]
    max_row = max(summary, key=lambda row: float(row["maximum_ms_offset"]))
    lines: list[str] = []
    lines.extend(
        [
            "# Alignment Verification Booklet",
            "",
            "Subtitle: Revised Stimulus Selection - Phase 2C",
            "",
            f"Generation date: {date.today().isoformat()}",
            "",
            "Methodology status: Awaiting manual/supervisor alignment review",
            "",
            "Phase 2C is quality assurance only. Selection recommendations have not been changed. Automatic confidence is not treated as sufficient on its own; final acceptance requires visual and perceptual review. REVIEW and FAIL labels mean manual inspection is required, not necessarily that the mixes must be discarded. The rapid-switch audio remains the primary perceptual verification material.",
            "",
            "## Executive Summary",
            "",
            "- 8 triplets verified",
            "- 24 pairwise comparisons",
            "- 8 rapid-switch files",
            "- 16 visual figures",
            f"- maximum automatic offset: {float(max_row['maximum_ms_offset']):.3f} ms",
            f"- maximum-offset triplet: {max_row['song']} / {max_row['condition']}",
            "",
            "## Methods Summary",
            "",
            "- Approved 28-second excerpts were retained.",
            "- Pairwise residual alignment was recomputed for each recommended triplet.",
            "- Lag was reported in samples and milliseconds.",
            "- Waveform plots were inspected on a shared time axis.",
            "- Zoomed transient plots were generated.",
            "- Rapid-switch WAVs were created for direct perceptual comparison.",
            "- No loudness normalisation was applied to review audio.",
            "- No selection decisions were changed.",
            f"- Automatic thresholds: {thresholds}",
            "",
            "## Overall Alignment Results",
            "",
            "| Song | Condition | Mix names | Max lag ms | Min correlation | Automatic status | Manual status |",
            "| --- | --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for row in summary:
        lines.append(
            f"| {row['song']} | {row['condition']} | {mix_display(row['mix_names'])} | {float(row['maximum_ms_offset']):.3f} | {float(row['minimum_correlation']):.3f} | {row['automatic_result']} | {row['manual_status']} |"
        )

    for item in triplets:
        srow = item["summary"]
        rrow = item["recommendation"]
        lines.extend(
            [
                "",
                f"## {srow['song']} - {srow['condition']}",
                "",
                f"- Original mix names: {mix_display(srow['mix_names'])}",
                f"- Automatic status: {srow['automatic_result']}",
                f"- Maximum lag: {float(srow['maximum_ms_offset']):.3f} ms",
                f"- Minimum correlation: {float(srow['minimum_correlation']):.3f}",
                f"- Stereo-imbalance QC flags: {rrow['qc_flags']}",
                f"- Rapid-switch audio: {rel(item['rapid'])}",
                "- Individual review audio:",
                *[f"  - {rel(path)}" for path in item["individual_audio"]],
                f"- Stacked waveform figure: {rel(item['stacked'])}",
                f"- Zoomed strongest-transient figure: {rel(item['zoom'])}",
                "",
                "| Pair | Lag samples | Lag ms | Correlation | Result |",
                "| --- | ---: | ---: | ---: | --- |",
            ]
        )
        for prow in item["pairwise"]:
            lines.append(
                f"| {prow['pair']} | {prow['sample_offset']} | {float(prow['millisecond_offset']):.3f} | {float(prow['peak_correlation']):.3f} | {prow['alignment_quality']} |"
            )
        lines.extend(
            [
                "",
                "Manual-review prompts:",
                "",
                "- Do major transients align visually?",
                "- Is there any apparent constant offset?",
                "- Is there any timing drift across the 28-second excerpt?",
                "- Does rapid switching reveal a perceptible timing jump?",
                "- Is the issue alignment, or only a mix-production difference?",
                "- Accept alignment?",
                "- Reviewer comments.",
            ]
        )

    lines.extend(
        [
            "",
            "## Appendix",
            "",
            f"- Alignment thresholds used: {thresholds}",
            "- Lag is the residual pairwise offset estimated from the onset/RMS-change envelope.",
            "- Correlation is the peak normalized cross-correlation within the search window.",
            "- Source CSVs: tables/pairwise_alignment_verification.csv, tables/alignment_summary.csv, tables/manual_alignment_review.csv, tables/review_audio_manifest.csv.",
            "- Figure folders: figures/<song>/<condition>/stacked_waveforms.png and figures/<song>/<condition>/strongest_transient_zoom.png.",
            "- Review-audio folders: review_audio/<song>/<condition>/.",
            "- Review WAV hashes match Phase 2B source WAVs according to tables/review_audio_manifest.csv.",
            "- Protected upstream outputs remained unchanged during booklet generation.",
        ]
    )
    SOURCE_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_pdf(ctx: dict[str, object]) -> None:
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], fontSize=30, leading=36, alignment=TA_CENTER, spaceAfter=24))
    styles.add(ParagraphStyle(name="CoverSub", parent=styles["Heading2"], fontSize=16, leading=20, alignment=TA_CENTER, textColor=colors.HexColor("#4B5563"), spaceAfter=18))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=7, leading=9))
    styles.add(ParagraphStyle(name="Tiny", parent=styles["BodyText"], fontSize=6, leading=8))
    styles.add(ParagraphStyle(name="Cell", parent=styles["BodyText"], fontSize=7, leading=9, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="Box", parent=styles["BodyText"], fontSize=8, leading=11, backColor=colors.HexColor("#F3F6FA"), borderPadding=8, spaceAfter=8))

    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=landscape(letter),
        rightMargin=0.45 * inch,
        leftMargin=0.45 * inch,
        topMargin=0.48 * inch,
        bottomMargin=0.55 * inch,
        title="Alignment Verification Booklet",
        author="Codex",
    )
    story = []
    summary = ctx["summary"]
    manual = ctx["manual"]
    triplets = ctx["triplets"]
    thresholds = ctx["thresholds"]
    max_row = max(summary, key=lambda row: float(row["maximum_ms_offset"]))

    story.extend(
        [
            Spacer(1, 0.6 * inch),
            Paragraph("Alignment Verification Booklet", styles["CoverTitle"]),
            Paragraph("Revised Stimulus Selection - Phase 2C", styles["CoverSub"]),
            Paragraph("MSc dissertation project", styles["Heading3"]),
            Paragraph("Project: intent2control-dissertation", styles["BodyText"]),
            Paragraph(f"Generation date: {date.today().isoformat()}", styles["BodyText"]),
            Paragraph("Methodology status: Awaiting manual/supervisor alignment review", styles["BodyText"]),
            Spacer(1, 0.25 * inch),
            Paragraph("Total triplets: 8", styles["BodyText"]),
            Paragraph("Total recommended mixes: 24", styles["BodyText"]),
            Spacer(1, 0.35 * inch),
            Paragraph(
                "This booklet consolidates Phase 2C quality-assurance evidence only. The selection recommendations have not been changed, and no triplet is finally approved unless the manual review table records approval.",
                styles["Box"],
            ),
            PageBreak(),
        ]
    )

    story.append(Paragraph("Executive Summary", styles["Heading1"]))
    status_groups = defaultdict(list)
    for row in summary:
        status_groups[row["automatic_result"]].append(f"{row['song']} / {row['condition']}")
    bullets = [
        "8 triplets verified.",
        "24 pairwise comparisons.",
        "8 rapid-switch files.",
        "16 visual figures.",
        f"Maximum automatic offset: {float(max_row['maximum_ms_offset']):.3f} ms.",
        f"Maximum-offset triplet: {max_row['song']} / {max_row['condition']}.",
        "Automatic classifications are screening results. Final inclusion requires visual inspection of waveform figures and perceptual inspection of rapid-switch audio.",
        "REVIEW and FAIL labels mean manual inspection is required, not necessarily that the mixes must be discarded.",
    ]
    story.append(ListFlowable([ListItem(Paragraph(b, styles["BodyText"])) for b in bullets], bulletType="bullet", leftIndent=18))
    status_data = [[para("Status", styles["Cell"]), para("Triplets", styles["Cell"])]]
    for status in ["PASS", "REVIEW", "FAIL"]:
        status_data.append([para(status, styles["Cell"]), para("<br/>".join(status_groups.get(status, [])), styles["Cell"])])
    t = Table(status_data, colWidths=[1.1 * inch, 8.8 * inch], repeatRows=1)
    t.setStyle(table_style(font_size=8))
    for idx, row in enumerate(status_data[1:], start=1):
        t.setStyle(TableStyle([("BACKGROUND", (0, idx), (0, idx), status_color(row[0].getPlainText()))]))
    story.extend([Spacer(1, 0.12 * inch), t, PageBreak()])

    story.append(Paragraph("Methods Summary", styles["Heading1"]))
    methods = [
        "Approved 28-second excerpts were retained.",
        "Pairwise residual alignment was recomputed for each recommended triplet.",
        "Lag was reported in samples and milliseconds.",
        "Waveform plots were inspected on a shared time axis.",
        "Zoomed transient plots were generated.",
        "Rapid-switch WAVs were created for direct perceptual comparison.",
        "No loudness normalisation was applied to review audio.",
        "No selection decisions were changed.",
        f"Automatic PASS/REVIEW/FAIL thresholds: {thresholds}.",
        "Automatic confidence is not treated as sufficient on its own.",
    ]
    story.append(ListFlowable([ListItem(Paragraph(m, styles["BodyText"])) for m in methods], bulletType="bullet", leftIndent=18))
    story.append(PageBreak())

    story.append(Paragraph("Overall Alignment Results", styles["Heading1"]))
    overall_header = ["Song", "Rating condition", "Original mix names", "Max abs lag ms", "Min corr.", "Auto status", "Rapid-switch", "Waveform", "Zoomed", "Manual", "Notes"]
    overall_data = [[para(h, styles["Cell"]) for h in overall_header]]
    for item in triplets:
        row = item["summary"]
        overall_data.append(
            [
                para(row["song"], styles["Cell"]),
                para(row["condition"], styles["Cell"]),
                para(mix_display(row["mix_names"]), styles["Cell"]),
                para(f"{float(row['maximum_ms_offset']):.3f}", styles["Cell"]),
                para(f"{float(row['minimum_correlation']):.3f}", styles["Cell"]),
                para(row["automatic_result"], styles["Cell"]),
                para(rel(item["rapid"]), styles["Tiny"]),
                para(rel(item["stacked"]), styles["Tiny"]),
                para(rel(item["zoom"]), styles["Tiny"]),
                para(row["manual_status"], styles["Cell"]),
                para(row["overall_recommendation"], styles["Tiny"]),
            ]
        )
    t = Table(overall_data, colWidths=[1.1 * inch, 0.9 * inch, 1.3 * inch, 0.55 * inch, 0.55 * inch, 0.55 * inch, 1.25 * inch, 1.25 * inch, 1.25 * inch, 0.55 * inch, 1.15 * inch], repeatRows=1)
    t.setStyle(table_style(font_size=6))
    for ridx, item in enumerate(triplets, start=1):
        t.setStyle(TableStyle([("BACKGROUND", (5, ridx), (5, ridx), status_color(item["summary"]["automatic_result"]))]))
    story.extend([t, PageBreak()])

    for item in triplets:
        row = item["summary"]
        rec = item["recommendation"]
        story.append(Paragraph(f"{row['song']} - {row['condition']}", styles["Heading1"]))
        story.append(Paragraph(f"Original mix names: {mix_display(row['mix_names'])} | Automatic status: {row['automatic_result']}", styles["Heading3"]))
        qc_pairs = [f"{mix}: {flag}" for mix, flag in zip(row["mix_names"].split("|"), rec["qc_flags"].split("|"))]
        box_text = (
            f"Maximum lag: {float(row['maximum_ms_offset']):.3f} ms<br/>"
            f"Minimum correlation: {float(row['minimum_correlation']):.3f}<br/>"
            f"Automatic confidence/result: {float(row['confidence']):.3f} / {row['automatic_result']}<br/>"
            f"Stereo-imbalance QC flags: {'; '.join(qc_pairs)}<br/>"
            f"Rapid-switch audio path: {rel(item['rapid'])}"
        )
        story.append(Paragraph(box_text, styles["Box"]))
        pair_header = ["Pair", "Lag samples", "Lag ms", "Correlation", "Automatic result"]
        pair_data = [[para(h, styles["Cell"]) for h in pair_header]]
        for prow in item["pairwise"]:
            pair_data.append(
                [
                    para(prow["pair"], styles["Cell"]),
                    para(prow["sample_offset"], styles["Cell"]),
                    para(f"{float(prow['millisecond_offset']):.3f}", styles["Cell"]),
                    para(f"{float(prow['peak_correlation']):.3f}", styles["Cell"]),
                    para(prow["alignment_quality"], styles["Cell"]),
                ]
            )
        pt = Table(pair_data, colWidths=[2.1 * inch, 1.0 * inch, 1.0 * inch, 1.1 * inch, 1.3 * inch], repeatRows=1)
        pt.setStyle(table_style(font_size=8))
        for ridx, prow in enumerate(item["pairwise"], start=1):
            pt.setStyle(TableStyle([("BACKGROUND", (4, ridx), (4, ridx), status_color(prow["alignment_quality"]))]))
        story.append(pt)
        story.append(Spacer(1, 0.12 * inch))
        audio_rows = [[para("Review-audio paths relative to 05_alignment_verification", styles["Cell"])]]
        for path in item["individual_audio"] + [item["rapid"]]:
            audio_rows.append([link_para(rel(path), path, styles["Tiny"])])
        at = Table(audio_rows, colWidths=[9.8 * inch], repeatRows=1)
        at.setStyle(table_style(font_size=7))
        story.append(at)
        prompts = [
            "Do major transients align visually?",
            "Is there any apparent constant offset?",
            "Is there any timing drift across the 28-second excerpt?",
            "Does rapid switching reveal a perceptible timing jump?",
            "Is the issue alignment, or only a mix-production difference?",
            "Accept alignment?",
            "Reviewer comments.",
        ]
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph("Manual-review prompts", styles["Heading3"]))
        story.append(ListFlowable([ListItem(Paragraph(p, styles["Small"])) for p in prompts], bulletType="bullet", leftIndent=16))
        story.append(PageBreak())

        story.append(Paragraph(f"Visual Evidence: {row['song']} - {row['condition']}", styles["Heading2"]))
        img_table = Table(
            [
                [para("Full stacked-waveform figure", styles["Cell"]), para("Zoomed strongest-transient figure", styles["Cell"])],
                [Image(str(item["stacked"]), width=4.85 * inch, height=3.65 * inch), Image(str(item["zoom"]), width=4.85 * inch, height=3.65 * inch)],
                [link_para(rel(item["stacked"]), item["stacked"], styles["Tiny"]), link_para(rel(item["zoom"]), item["zoom"], styles["Tiny"])],
            ],
            colWidths=[5.0 * inch, 5.0 * inch],
        )
        img_table.setStyle(table_style(font_size=7))
        story.append(img_table)
        story.append(PageBreak())

    story.append(Paragraph("Manual-Review Checklist", styles["Heading1"]))
    checklist_header = ["Song", "Condition", "Mix names", "Automatic result", "Waveform checked", "Rapid-switch checked", "Audible issue", "Accepted", "Reviewer", "Review date", "Comments"]
    checklist = [[para(h, styles["Cell"]) for h in checklist_header]]
    for item in triplets:
        man = item["manual"]
        checklist.append(
            [
                para(man["song"], styles["Cell"]),
                para(man["condition"], styles["Cell"]),
                para(mix_display(man["mixes"]), styles["Cell"]),
                para(item["summary"]["automatic_result"], styles["Cell"]),
                para(man["waveform_checked"], styles["Cell"]),
                para(man["rapid_switch_checked"], styles["Cell"]),
                para(man["audible_alignment_issue"], styles["Cell"]),
                para(man["alignment_accept"], styles["Cell"]),
                para(man["reviewer"], styles["Cell"]),
                para(man["date"], styles["Cell"]),
                para(man["comments"], styles["Cell"]),
            ]
        )
    ct = Table(checklist, colWidths=[1.0 * inch, 0.85 * inch, 1.25 * inch, 0.75 * inch, 0.75 * inch, 0.8 * inch, 0.75 * inch, 0.65 * inch, 0.7 * inch, 0.7 * inch, 1.6 * inch], repeatRows=1)
    ct.setStyle(table_style(font_size=6))
    story.extend([ct, PageBreak()])

    story.append(Paragraph("Final Status Summary", styles["Heading1"]))
    approved = [row for row in manual if row.get("alignment_accept", "").strip().lower() in {"yes", "true", "accepted", "accept"}]
    final_points = [
        f"Automatically passing triplets: {', '.join(status_groups.get('PASS', [])) or 'None'}.",
        f"Triplets requiring REVIEW: {', '.join(status_groups.get('REVIEW', [])) or 'None'}.",
        f"Triplets classified as FAIL/review-required: {', '.join(status_groups.get('FAIL', [])) or 'None'}.",
        f"Maximum observed lag: {float(max_row['maximum_ms_offset']):.3f} ms.",
        f"Triplets with manual approval recorded: {len(approved)}.",
        "Next action required: visual inspection of waveform figures and perceptual inspection of rapid-switch audio before final inclusion.",
        "The automatic classifications are screening results. Final inclusion requires visual inspection of the waveform figures and perceptual inspection of the rapid-switch audio.",
    ]
    story.append(ListFlowable([ListItem(Paragraph(p, styles["BodyText"])) for p in final_points], bulletType="bullet", leftIndent=18))
    story.append(PageBreak())

    story.append(Paragraph("Appendix", styles["Heading1"]))
    appendix = [
        f"Alignment thresholds used: {thresholds}.",
        "Lag fields report residual pairwise offsets in samples and milliseconds.",
        "Correlation fields report peak normalized cross-correlation over the Phase 2C search window.",
        "Canonical CSV files: tables/pairwise_alignment_verification.csv, tables/alignment_summary.csv, tables/manual_alignment_review.csv, tables/review_audio_manifest.csv.",
        "Figure files: figures/<song>/<condition>/stacked_waveforms.png and figures/<song>/<condition>/strongest_transient_zoom.png.",
        "Review-audio folders: review_audio/<song>/<condition>/ with three individual 28-second WAVs plus RapidSwitch.wav.",
        "Review WAV hashes match Phase 2B source WAVs according to review_audio_manifest.csv.",
        "Protected upstream outputs remained unchanged during booklet generation.",
    ]
    story.append(ListFlowable([ListItem(Paragraph(a, styles["BodyText"])) for a in appendix], bulletType="bullet", leftIndent=18))
    story.append(Spacer(1, 0.14 * inch))
    paths = [[para("Source", styles["Cell"]), para("Path", styles["Cell"])]]
    for path in SOURCE_TABLES + [RECOMMENDATIONS]:
        paths.append([para(path.name, styles["Cell"]), para(path.relative_to(REPO_ROOT).as_posix(), styles["Tiny"])])
    pt = Table(paths, colWidths=[2.2 * inch, 7.4 * inch], repeatRows=1)
    pt.setStyle(table_style(font_size=7))
    story.append(pt)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


def count_pdf_images(pdf_path: Path) -> int:
    reader = PdfReader(str(pdf_path))
    count = 0
    for page in reader.pages:
        resources = page.get("/Resources") or {}
        xobjects = resources.get("/XObject") or {}
        for obj in xobjects.values():
            resolved = obj.get_object()
            if resolved.get("/Subtype") == "/Image":
                count += 1
    return count


def validate(ctx: dict[str, object], before_hashes: dict[str, str]) -> dict[str, object]:
    source_text = SOURCE_MD_PATH.read_text(encoding="utf-8")
    pdf_reader = PdfReader(str(PDF_PATH))
    page_count = len(pdf_reader.pages)
    figure_paths = []
    audio_paths = []
    missing_assets = []
    for item in ctx["triplets"]:
        heading = f"## {item['summary']['song']} - {item['summary']['condition']}"
        if heading not in source_text:
            missing_assets.append(f"Missing source heading: {heading}")
        for fig in [item["stacked"], item["zoom"]]:
            figure_paths.append(fig)
            if not fig.exists():
                missing_assets.append(f"Missing figure: {rel(fig)}")
            if rel(fig) not in source_text:
                missing_assets.append(f"Figure path absent from source: {rel(fig)}")
        for audio in item["individual_audio"] + [item["rapid"]]:
            audio_paths.append(audio)
            if not audio.exists():
                missing_assets.append(f"Missing review audio: {rel(audio)}")
            if rel(audio) not in source_text:
                missing_assets.append(f"Audio path absent from source: {rel(audio)}")
        if item["summary"]["automatic_result"] not in source_text:
            missing_assets.append(f"Status absent from source: {item['summary']['automatic_result']}")

    manifest = ctx["manifest"]
    hash_match_ok = all(row["hash_match"] == "true" for row in manifest)
    csv_hashes_after = {str(path): sha256(path) for path in SOURCE_TABLES}
    csv_hashes_unchanged = csv_hashes_after == before_hashes
    review_hashes_ok = all(sha256(Path(row["review_path"])) == row["review_sha256"] for row in manifest)
    rec_mixes = {
        (row["song"], row["condition"]): row["original_mix_names"]
        for row in ctx["recommendations"]
    }
    mix_names_match = all(
        item["summary"]["mix_names"] == rec_mixes[item["key"]]
        for item in ctx["triplets"]
    )
    statuses_match = all(
        item["summary"]["automatic_result"] in {"PASS", "REVIEW", "FAIL"}
        for item in ctx["triplets"]
    )
    rapid_paths_exist = all(item["rapid"].exists() for item in ctx["triplets"])
    image_count = count_pdf_images(PDF_PATH)

    passed = (
        PDF_PATH.exists()
        and page_count > 8
        and len(ctx["triplets"]) == 8
        and len(figure_paths) == 16
        and image_count >= 16
        and statuses_match
        and mix_names_match
        and rapid_paths_exist
        and hash_match_ok
        and csv_hashes_unchanged
        and review_hashes_ok
        and not missing_assets
    )
    return {
        "passed": passed,
        "page_count": page_count,
        "file_size": PDF_PATH.stat().st_size,
        "triplets": [f"{item['summary']['song']} / {item['summary']['condition']}" for item in ctx["triplets"]],
        "figures": [rel(path) for path in figure_paths],
        "pdf_image_count": image_count,
        "missing_assets": missing_assets,
        "statuses_match": statuses_match,
        "mix_names_match": mix_names_match,
        "rapid_paths_exist": rapid_paths_exist,
        "csv_hashes_unchanged": csv_hashes_unchanged,
        "review_wav_hashes_unchanged": review_hashes_ok,
        "phase2b_hash_matches": hash_match_ok,
    }


def write_validation_md(result: dict[str, object]) -> None:
    lines = [
        "# Alignment Verification Booklet Validation",
        "",
        f"- PDF path: {PDF_PATH.relative_to(REPO_ROOT).as_posix()}",
        f"- PDF page count: {result['page_count']}",
        f"- PDF file size: {result['file_size']} bytes",
        f"- Embedded PDF image XObjects: {result['pdf_image_count']}",
        f"- Triplets included: {len(result['triplets'])}",
        f"- Figures included: {len(result['figures'])}",
        f"- Status values match canonical summary: {str(result['statuses_match']).lower()}",
        f"- Mix names match Phase 2B recommendation sets: {str(result['mix_names_match']).lower()}",
        f"- Rapid-switch paths exist: {str(result['rapid_paths_exist']).lower()}",
        f"- Phase 2C CSV hashes unchanged: {str(result['csv_hashes_unchanged']).lower()}",
        f"- Review WAV hashes unchanged: {str(result['review_wav_hashes_unchanged']).lower()}",
        f"- Review WAV hashes match Phase 2B source WAVs: {str(result['phase2b_hash_matches']).lower()}",
        "",
        "## Triplets Included",
        "",
    ]
    lines.extend(f"- {triplet}" for triplet in result["triplets"])
    lines.extend(["", "## Figures Included", ""])
    lines.extend(f"- {figure}" for figure in result["figures"])
    lines.extend(["", "## Missing Assets", ""])
    if result["missing_assets"]:
        lines.extend(f"- {asset}" for asset in result["missing_assets"])
    else:
        lines.append("- None")
    lines.extend(["", f"Validation result: {'PASS' if result['passed'] else 'FAIL'}", ""])
    VALIDATION_MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    os.makedirs(REPORTS, exist_ok=True)
    before_hashes = {str(path): sha256(path) for path in SOURCE_TABLES}
    ctx = build_context()
    write_source_md(ctx)
    build_pdf(ctx)
    result = validate(ctx, before_hashes)
    write_validation_md(result)
    if not result["passed"]:
        raise SystemExit("Booklet validation failed. See alignment_verification_booklet_validation.md")
    print(f"PDF: {PDF_PATH}")
    print(f"Source: {SOURCE_MD_PATH}")
    print(f"Validation: {VALIDATION_MD_PATH}")
    print(f"Pages: {result['page_count']}")
    print(f"Figures: {len(result['figures'])}")
    print("Validation result: PASS")


if __name__ == "__main__":
    main()
