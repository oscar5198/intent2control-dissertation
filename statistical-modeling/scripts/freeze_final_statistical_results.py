"""Freeze compact final statistical result tables from retained model outputs."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "statistical-modeling" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from statistical_baseline.phase6h2a_finalize import finalize_phase6h2a  # noqa: E402


if __name__ == "__main__":
    finalize_phase6h2a(REPO_ROOT)
