"""CLI wrapper for Phase 6B.5 synthetic end-to-end validation."""

from __future__ import annotations

import sys
from pathlib import Path


LLM_SRC = Path(__file__).resolve().parents[1] / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.data.integration import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
