from __future__ import annotations

"""Canonical output paths for the numbered stimulus-selection layout."""

from pathlib import Path


def stage1_tables(root: Path) -> Path:
    return root / "01_dataset_and_song_selection" / "tables"


def stage1_reports(root: Path) -> Path:
    return root / "01_dataset_and_song_selection" / "reports"


def stage2_tables(root: Path) -> Path:
    return root / "02_excerpt_selection" / "tables"


def stage2_reports(root: Path) -> Path:
    return root / "02_excerpt_selection" / "reports"


def stage2_previews(root: Path) -> Path:
    return root / "02_excerpt_selection" / "approved_excerpt_previews"


def stage2_diagnostics(root: Path) -> Path:
    return root / "02_excerpt_selection" / "diagnostics"


def stage3_tables(root: Path) -> Path:
    return root / "03_feature_extraction" / "tables"


def stage3_reports(root: Path) -> Path:
    return root / "03_feature_extraction" / "reports"


def stage3_diagnostics(root: Path) -> Path:
    return root / "03_feature_extraction" / "feature_diagnostics"


def stage4_tables(root: Path) -> Path:
    return root / "04_mix_selection" / "tables"


def stage4_reports(root: Path) -> Path:
    return root / "04_mix_selection" / "reports"


def stage4_diagnostics(root: Path) -> Path:
    return root / "04_mix_selection" / "selection_diagnostics"


def stage4_previews(root: Path) -> Path:
    return root / "04_mix_selection" / "selected_mix_review_previews"


def stage4_v2_root(root: Path) -> Path:
    return root / "04_mix_selection_v2"


def stage4_v2_tables(root: Path) -> Path:
    return stage4_v2_root(root) / "tables"


def stage4_v2_reports(root: Path) -> Path:
    return stage4_v2_root(root) / "reports"


def stage4_v2_diagnostics(root: Path) -> Path:
    return stage4_v2_root(root) / "diagnostics"


def stage4_v2_previews(root: Path) -> Path:
    return stage4_v2_root(root) / "candidate_pool_previews"


def stage4_v2_validation(root: Path) -> Path:
    return stage4_v2_root(root) / "tests_and_validation"


def ratings_integration_root(root: Path) -> Path:
    return root / "05_ratings_integration"


def ratings_integration_tables(root: Path) -> Path:
    return ratings_integration_root(root) / "tables"


def ratings_integration_reports(root: Path) -> Path:
    return ratings_integration_root(root) / "reports"


def ratings_integration_diagnostics(root: Path) -> Path:
    return ratings_integration_root(root) / "diagnostics"


def ratings_integration_validation(root: Path) -> Path:
    return ratings_integration_root(root) / "tests_and_validation"


def rating_stratification_root(root: Path) -> Path:
    return root / "06_rating_stratification"


def rating_stratification_tables(root: Path) -> Path:
    return rating_stratification_root(root) / "tables"


def rating_stratification_reports(root: Path) -> Path:
    return rating_stratification_root(root) / "reports"


def rating_stratification_diagnostics(root: Path) -> Path:
    return rating_stratification_root(root) / "diagnostics"


def rating_stratification_audio(root: Path) -> Path:
    return rating_stratification_root(root) / "candidate_review_audio"


def alignment_verification_root(root: Path) -> Path:
    return root / "05_alignment_verification"


def alignment_verification_tables(root: Path) -> Path:
    return alignment_verification_root(root) / "tables"


def alignment_verification_figures(root: Path) -> Path:
    return alignment_verification_root(root) / "figures"


def alignment_verification_audio(root: Path) -> Path:
    return alignment_verification_root(root) / "review_audio"


def alignment_verification_reports(root: Path) -> Path:
    return alignment_verification_root(root) / "reports"


def manual_review_tables(root: Path) -> Path:
    return root / "05_manual_review" / "tables"


def manual_review_instructions(root: Path) -> Path:
    return root / "05_manual_review" / "instructions"


def summaries(root: Path) -> Path:
    return root / "archive" / "medoid_contrast_legacy" / "06_final_summaries"


def provenance(root: Path) -> Path:
    return root / "logs_and_provenance"


def first_existing(root: Path, *relative_paths: str) -> Path:
    """Return the first existing path, falling back to the first canonical path."""
    candidates = [root / rel for rel in relative_paths]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]
