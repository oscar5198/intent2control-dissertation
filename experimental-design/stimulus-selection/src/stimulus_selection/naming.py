from __future__ import annotations

"""Human-facing mix naming helpers.

Internal ``mix_id`` values remain the stable join keys for analytical tables.
The original Mix Evaluation Dataset filename is the preferred display identity
for reports, plots, manifests, and preview/archive audio filenames.
"""

import re
from pathlib import Path


def get_original_dataset_filename(source_path: str | Path) -> str:
    """Return the dataset basename from an existing source path."""
    return Path(str(source_path)).name


def get_original_mix_name(source_path: str | Path) -> str:
    """Return the dataset filename stem used as the public mix name."""
    return Path(get_original_dataset_filename(source_path)).stem


def safe_original_mix_filename(name: str) -> str:
    """Sanitize an original mix name for generated WAV filenames."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(name)).strip("._-")
    return cleaned or "unnamed_mix"


def format_mix_display_name(original_mix_name: str, mix_id: str | None = None) -> str:
    """Format a human-facing mix label with optional internal traceability."""
    if mix_id:
        return f"{original_mix_name} (internal ID: {mix_id})"
    return original_mix_name
