from __future__ import annotations

from pathlib import Path

from stimulus_selection.config import SelectionConfig


def relationship_data_dir(config: SelectionConfig) -> Path:
    data_dir = config.relationship_tables_root / "data"
    if not data_dir.exists():
        raise FileNotFoundError(f"Relationship-table data directory not found: {data_dir}")
    return data_dir


def ensure_output_root(config: SelectionConfig) -> Path:
    config.output_root.mkdir(parents=True, exist_ok=True)
    return config.output_root


def source_path_from_relative(config: SelectionConfig, relative_path: str) -> Path:
    normalized = relative_path.replace("/", "\\")
    candidates = [
        config.dataset_root / normalized,
        config.dataset_root / "MixEvaluation" / normalized,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]
