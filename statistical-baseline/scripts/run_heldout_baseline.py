"""CLI wrapper for Phase 6C held-out baseline dry-run/future fitting."""

from __future__ import annotations

import sys
from pathlib import Path


BASELINE_SRC = Path(__file__).resolve().parents[1] / "src"
if str(BASELINE_SRC) not in sys.path:
    sys.path.insert(0, str(BASELINE_SRC))

from statistical_baseline.heldout import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
