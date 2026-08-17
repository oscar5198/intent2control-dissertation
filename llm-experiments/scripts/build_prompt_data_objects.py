"""CLI wrapper for Phase 6B.4 condition-specific prompt-data objects."""

from __future__ import annotations

import sys
from pathlib import Path


LLM_SRC = Path(__file__).resolve().parents[1] / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.data.prompt_data import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
