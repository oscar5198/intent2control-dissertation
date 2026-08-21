from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class AlignmentConfig:
    analysis_downmix: str
    coarse_sample_rate: int
    maximum_expected_offset_seconds: float
    minimum_alignment_confidence: float
    use_onset_envelope: bool
    use_chroma_fallback: bool
    use_waveform_correlation_for_refinement: bool


@dataclass(frozen=True)
class ExcerptSelectionConfig:
    candidate_count: int
    activity_hop_seconds: float
    avoid_first_seconds: float
    avoid_last_seconds: float
    minimum_activity_quantile: float
    prefer_vocal_drums_bass_region: bool


@dataclass(frozen=True)
class AudioBoundaryProcessingConfig:
    methodology_version: str
    supervisor_revision_date: str
    fade_required: bool
    fade_in_ms: float
    fade_out_ms: float
    fade_shape: str
    apply_identically_to_all_versions: bool
    candidate_review_loudness_policy: str
    final_stimulus_loudness_policy: str
    exact_duration_seconds: float
    target_sample_rate: int
    deterministic: bool


@dataclass(frozen=True)
class SelectionConfig:
    dataset_root: Path
    relationship_tables_root: Path
    public_audio_root: Path
    output_root: Path
    target_sample_rate: int
    minimum_duration_seconds: float
    require_stereo: bool
    allowed_extensions: tuple[str, ...]
    institution_system_codes: tuple[str, ...]
    primary_candidate_songs: tuple[dict[str, str], ...]
    approved_excerpts: tuple[dict[str, Any], ...]
    target_excerpt_seconds: float
    fade_seconds: float
    alignment: AlignmentConfig
    excerpt_selection: ExcerptSelectionConfig
    audio_boundary_processing: AudioBoundaryProcessingConfig
    analysis_excerpt_root: Path
    preview_excerpt_root: Path


def _as_path(value: str, base_dir: Path | None = None) -> Path:
    path = Path(value)
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    return path


def _repo_root_from_config(config_path: Path) -> Path:
    for parent in [config_path.parent, *config_path.parents]:
        if (parent / ".git").exists():
            return parent
    if config_path.parent.name.lower() == "configs":
        return config_path.parent.parent
    return Path.cwd()


def load_config(path: str | Path) -> SelectionConfig:
    config_path = Path(path).resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle)

    repo_root = _repo_root_from_config(config_path)
    alignment_raw = raw.get("alignment", {})
    excerpt_raw = raw.get("excerpt_selection", {})
    boundary_raw = raw.get("audio_boundary_processing", {})
    output_root = _as_path(raw["output_root"], repo_root)
    return SelectionConfig(
        dataset_root=_as_path(raw["dataset_root"]),
        relationship_tables_root=_as_path(raw["relationship_tables_root"]),
        public_audio_root=_as_path(raw["public_audio_root"]),
        output_root=output_root,
        target_sample_rate=int(raw["target_sample_rate"]),
        minimum_duration_seconds=float(raw["minimum_duration_seconds"]),
        require_stereo=bool(raw["require_stereo"]),
        allowed_extensions=tuple(e.lower() for e in raw["allowed_extensions"]),
        institution_system_codes=tuple(raw["institution_system_codes"]),
        primary_candidate_songs=tuple(raw.get("primary_candidate_songs", [])),
        approved_excerpts=tuple(raw.get("approved_excerpts", [])),
        target_excerpt_seconds=float(raw.get("target_excerpt_seconds", 28.0)),
        fade_seconds=float(raw.get("fade_seconds", 1.0)),
        alignment=AlignmentConfig(
            analysis_downmix=str(alignment_raw.get("analysis_downmix", "mono")),
            coarse_sample_rate=int(alignment_raw.get("coarse_sample_rate", 11025)),
            maximum_expected_offset_seconds=float(alignment_raw.get("maximum_expected_offset_seconds", 2.0)),
            minimum_alignment_confidence=float(alignment_raw.get("minimum_alignment_confidence", 0.70)),
            use_onset_envelope=bool(alignment_raw.get("use_onset_envelope", True)),
            use_chroma_fallback=bool(alignment_raw.get("use_chroma_fallback", True)),
            use_waveform_correlation_for_refinement=bool(alignment_raw.get("use_waveform_correlation_for_refinement", True)),
        ),
        excerpt_selection=ExcerptSelectionConfig(
            candidate_count=int(excerpt_raw.get("candidate_count", 5)),
            activity_hop_seconds=float(excerpt_raw.get("activity_hop_seconds", 0.25)),
            avoid_first_seconds=float(excerpt_raw.get("avoid_first_seconds", 3.0)),
            avoid_last_seconds=float(excerpt_raw.get("avoid_last_seconds", 3.0)),
            minimum_activity_quantile=float(excerpt_raw.get("minimum_activity_quantile", 0.50)),
            prefer_vocal_drums_bass_region=bool(excerpt_raw.get("prefer_vocal_drums_bass_region", True)),
        ),
        audio_boundary_processing=AudioBoundaryProcessingConfig(
            methodology_version=str(boundary_raw.get("methodology_version", "1.0")),
            supervisor_revision_date=str(boundary_raw.get("supervisor_revision_date", "")),
            fade_required=bool(boundary_raw.get("fade_required", True)),
            fade_in_ms=float(boundary_raw.get("fade_in_ms", raw.get("fade_seconds", 1.0) * 1000.0)),
            fade_out_ms=float(boundary_raw.get("fade_out_ms", raw.get("fade_seconds", 1.0) * 1000.0)),
            fade_shape=str(boundary_raw.get("fade_shape", "linear")),
            apply_identically_to_all_versions=bool(boundary_raw.get("apply_identically_to_all_versions", True)),
            candidate_review_loudness_policy=str(boundary_raw.get("candidate_review_loudness_policy", "preserve_raw_level")),
            final_stimulus_loudness_policy=str(boundary_raw.get("final_stimulus_loudness_policy", "preserve_existing_target")),
            exact_duration_seconds=float(boundary_raw.get("exact_duration_seconds", raw.get("target_excerpt_seconds", 28.0))),
            target_sample_rate=int(boundary_raw.get("target_sample_rate", raw.get("target_sample_rate", 44100))),
            deterministic=bool(boundary_raw.get("deterministic", True)),
        ),
        analysis_excerpt_root=_as_path(raw.get("analysis_excerpt_root", "experimental-design/stimulus-selection/supporting-analysis/02_excerpt_selection/diagnostics/analysis_excerpts"), repo_root),
        preview_excerpt_root=_as_path(raw.get("preview_excerpt_root", "experimental-design/stimulus-selection/supporting-analysis/02_excerpt_selection/diagnostics/excerpt_previews"), repo_root),
    )
