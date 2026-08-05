from __future__ import annotations

import argparse
from pathlib import Path

from stimulus_selection.alignment import run_align_excerpts
from stimulus_selection.audio_inventory import INVENTORY_COLUMNS, build_inventory, write_csv
from stimulus_selection.config import load_config
from stimulus_selection.diffmst_validation import run_diffmst_feature_validation
from stimulus_selection.feature_extraction import run_feature_extraction
from stimulus_selection.mix_selection import run_mix_selection
from stimulus_selection.mix_selection_v2 import run_mix_selection_v2
from stimulus_selection.ratings_integration import run_ratings_integration
from stimulus_selection.rating_stratification import run_rating_stratification
from stimulus_selection.alignment_verification import run_alignment_verification
from stimulus_selection.fade_revision import run_fade_revision
from stimulus_selection.six_mix_proposals import run_six_mix_proposals
from stimulus_selection.output_layout import stage1_reports, stage1_tables
from stimulus_selection.paths import ensure_output_root
from stimulus_selection.reports import write_markdown_report
from stimulus_selection.shortlist import SUMMARY_COLUMNS, build_song_summary, institution_mapping_rows


def run_inventory(config_path: str | Path) -> dict[str, int]:
    config = load_config(config_path)
    output_root = ensure_output_root(config)
    tables = stage1_tables(output_root)
    reports = stage1_reports(output_root)

    inventory = build_inventory(config)
    summary = build_song_summary(inventory, config)

    write_csv(tables / "mix_inventory.csv", inventory, INVENTORY_COLUMNS)
    write_csv(tables / "song_summary.csv", summary, SUMMARY_COLUMNS)
    write_csv(tables / "candidate_song_ranking.csv", summary, SUMMARY_COLUMNS)
    write_csv(
        tables / "institution_mapping_report.csv",
        institution_mapping_rows(inventory),
        [
            "mixer_institution_code",
            "institution_name",
            "institution_category",
            "institution_confidence",
            "metadata_source",
            "is_system_generated",
        ],
    )
    write_csv(
        tables / "duplicate_files_report.csv",
        [r for r in inventory if r.get("_exact_duplicate") == "true" or r["duplicate_audio_candidate"] == "true"],
        INVENTORY_COLUMNS,
    )
    write_csv(
        tables / "validation_failures.csv",
        [r for r in inventory if r["valid_for_analysis"] != "true"],
        INVENTORY_COLUMNS,
    )
    write_markdown_report(reports / "dataset_inspection_report.md", inventory, summary)

    return {
        "inventory_records": len(inventory),
        "songs": len(summary),
        "valid_for_analysis": sum(r["valid_for_analysis"] == "true" for r in inventory),
        "eligible_songs": sum(r["cross_institution_eligible"] == "true" for r in summary),
    }


def run_alignment(config_path: str | Path) -> dict[str, object]:
    config = load_config(config_path)
    result = run_align_excerpts(config)
    return {
        "decoder_backends": result.decoder_backend_counts,
        "retained_counts": result.retained_counts,
        "excluded_counts": result.excluded_counts,
        "confidence_summary": result.confidence_summary,
        "common_overlap_seconds": result.common_overlap,
        "preview_file_count": len(result.preview_files),
        "manual_review_count": len(result.manual_review),
    }


def run_validate_diffmst_features(config_path: str | Path, reference_root: str | Path) -> dict[str, object]:
    config = load_config(config_path)
    result = run_diffmst_feature_validation(config, reference_root)
    return {
        "equivalence_rows": len(result.rows),
        "equivalence_passed": sum(row["passed"] == "true" for row in result.rows),
        "edge_case_rows": len(result.edge_rows),
        "edge_case_passed": sum(row["passed"] == "true" for row in result.edge_rows),
        "bark_mid_side_shape": result.bark_shapes["mid-side"],
        "csv_report": result.csv_path,
        "markdown_report": result.report_path,
    }


def run_extract_features(config_path: str | Path) -> dict[str, object]:
    config = load_config(config_path)
    result = run_feature_extraction(config)
    return {
        "total_rows": len(result.rows),
        "successful_rows": sum(row["feature_extraction_status"] == "ok" for row in result.rows),
        "counts_by_song": result.counts_by_song,
        "rerun_subset_identical": result.rerun_subset_identical,
        "raw_feature_table": result.raw_feature_path,
        "quality_checks": result.quality_path,
        "report": result.report_path,
    }


def run_select_mixes(config_path: str | Path) -> dict[str, object]:
    config = load_config(config_path)
    result = run_mix_selection(config)
    return {
        "retained_counts": {f"{s.artist} - {s.song}": s.retained_count for s in result.song_selections},
        "bark_pca_components": {f"{s.artist} - {s.song}": s.bark_components for s in result.song_selections},
        "bark_pca_explained_variance": {f"{s.artist} - {s.song}": round(s.bark_variance, 6) for s in result.song_selections},
        "medoids": {f"{s.artist} - {s.song}": s.medoid_mix_id for s in result.song_selections},
        "recommended_triplets": {f"{s.artist} - {s.song}": s.recommended_mix_ids for s in result.song_selections},
        "preview_file_count": len(result.preview_files),
        "recommended_triplets_csv": result.recommended_triplets_path,
        "report": result.report_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="stimulus_selection")
    subparsers = parser.add_subparsers(dest="command", required=True)
    inventory = subparsers.add_parser("inventory", help="Build Stage 1 inventory and validation reports.")
    inventory.add_argument("--config", required=True, help="Path to selection YAML config.")
    align = subparsers.add_parser("align-excerpts", help="Run Stage 2 decoding, alignment and excerpt candidate selection.")
    align.add_argument("--config", required=True, help="Path to selection YAML config.")
    diffmst = subparsers.add_parser("validate-diffmst-features", help="Validate vendored Stage 3 Diff-MST feature transforms.")
    diffmst.add_argument("--config", required=True, help="Path to selection YAML config.")
    diffmst.add_argument(
        "--reference-root",
        default=None,
        help="Path to the external Diff-MST reference repository. Defaults to DIFF_MST_REFERENCE_ROOT.",
    )
    extract = subparsers.add_parser("extract-features", help="Extract validated Diff-MST features for Stage 3B retained mixes.")
    extract.add_argument("--config", required=True, help="Path to selection YAML config.")
    select = subparsers.add_parser("select-mixes", help="Run Stage 4 preprocessing and final analytical mix selection.")
    select.add_argument("--config", required=True, help="Path to selection YAML config.")
    select_v2 = subparsers.add_parser("select-mixes-v2", help="Run corrected Stage 4 v2 acoustic candidate-pool generation.")
    select_v2.add_argument("--config", required=True, help="Path to selection YAML config.")
    ratings = subparsers.add_parser("integrate-ratings", help="Run Phase 2A prior-rating ingestion and aggregation.")
    ratings.add_argument("--config", required=True, help="Path to selection YAML config.")
    stratify = subparsers.add_parser("stratify-ratings", help="Run Phase 2B rating-stratified supervisor recommendation sets.")
    stratify.add_argument("--config", required=True, help="Path to selection YAML config.")
    verify_alignment = subparsers.add_parser("verify-alignment", help="Run Phase 2C alignment QA for recommended triplets.")
    verify_alignment.add_argument("--config", required=True, help="Path to selection YAML config.")
    revise_fades = subparsers.add_parser("revise-fades", help="Apply supervisor-requested 5 ms boundary fade revision to active review audio.")
    revise_fades.add_argument("--config", required=True, help="Path to selection YAML config.")
    six_mix = subparsers.add_parser("six-mix-proposals", help="Create the six-mix proposal layer for supervisor/pilot review.")
    six_mix.add_argument("--config", required=True, help="Path to selection YAML config.")
    args = parser.parse_args()

    if args.command == "inventory":
        counts = run_inventory(args.config)
    elif args.command == "align-excerpts":
        counts = run_alignment(args.config)
    elif args.command == "validate-diffmst-features":
        reference_root = args.reference_root
        if reference_root is None:
            import os

            reference_root = os.environ.get("DIFF_MST_REFERENCE_ROOT")
        if not reference_root:
            raise ValueError("Provide --reference-root or set DIFF_MST_REFERENCE_ROOT.")
        counts = run_validate_diffmst_features(args.config, reference_root)
    elif args.command == "extract-features":
        counts = run_extract_features(args.config)
    elif args.command == "select-mixes":
        counts = run_select_mixes(args.config)
    elif args.command == "select-mixes-v2":
        config = load_config(args.config)
        result = run_mix_selection_v2(config, args.config)
        counts = {
            "retained_counts": {s.song: s.retained_count for s in result.song_summaries},
            "candidate_pool_sizes": {s.song: s.candidate_pool_actual for s in result.song_summaries},
            "bark_pca_components": {s.song: s.bark_components for s in result.song_summaries},
            "medoids": {s.song: s.medoid_original_name for s in result.song_summaries},
            "candidate_pool_csv": result.candidate_pool_path,
            "report": result.report_path,
            "preview_file_count": len(result.preview_files),
        }
    elif args.command == "integrate-ratings":
        config = load_config(args.config)
        result = run_ratings_integration(config, args.config)
        counts = {
            "evaluation_rows": result.evaluation_rows,
            "retained_mixes": result.retained_mixes,
            "rated_retained_mixes": result.rated_retained_mixes,
            "unrated_retained_mixes": result.unrated_retained_mixes,
            "report": result.report_path,
            "coverage_by_song": result.coverage_by_song_path,
        }
    elif args.command == "stratify-ratings":
        config = load_config(args.config)
        result = run_rating_stratification(config, args.config)
        counts = {
            "recommended_rows": result.recommended_rows,
            "audio_files": result.audio_files,
            "supervisor_shortlist": result.supervisor_shortlist_path,
            "report": result.report_path,
        }
    elif args.command == "verify-alignment":
        config = load_config(args.config)
        result = run_alignment_verification(config)
        counts = {
            "triplets_verified": result.triplets_verified,
            "pairwise_rows": result.pairwise_rows,
            "rapid_switch_files": result.rapid_switch_files,
            "figures": result.figures,
            "maximum_ms_offset": round(result.maximum_ms_offset, 6),
            "report": result.report_path,
        }
    elif args.command == "revise-fades":
        config = load_config(args.config)
        counts = run_fade_revision(config)
    elif args.command == "six-mix-proposals":
        config = load_config(args.config)
        counts = run_six_mix_proposals(config, args.config)
    else:
        raise ValueError(args.command)
    for key, value in counts.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
