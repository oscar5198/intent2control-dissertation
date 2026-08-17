"""Data processing helpers for LLM evaluation datasets."""

from .processing import (
    CANONICAL_COLUMNS,
    EXPECTED_LABELS,
    build_analysis_ready_dataset,
    write_analysis_ready_outputs,
)
from .targets import (
    CANDIDATE_TARGET_COLUMNS,
    TRIAL_TARGET_COLUMNS,
    build_preference_targets,
    derive_observed_ranks,
    derive_preferred_set,
    write_preference_target_outputs,
)

__all__ = [
    "CANONICAL_COLUMNS",
    "EXPECTED_LABELS",
    "build_analysis_ready_dataset",
    "write_analysis_ready_outputs",
    "CANDIDATE_TARGET_COLUMNS",
    "TRIAL_TARGET_COLUMNS",
    "build_preference_targets",
    "derive_observed_ranks",
    "derive_preferred_set",
    "write_preference_target_outputs",
]
"""Data-building utilities for the LLM experiment pipeline."""
