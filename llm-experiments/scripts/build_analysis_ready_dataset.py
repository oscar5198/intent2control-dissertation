#!/usr/bin/env python3
"""CLI wrapper for the Phase 6B.1 LLM analysis-ready dataset builder."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_experiments.data.processing import main


if __name__ == "__main__":
    raise SystemExit(main())
