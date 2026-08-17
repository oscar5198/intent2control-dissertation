"""CLI wrapper for Phase 6E.3 synthetic prediction logging."""

from __future__ import annotations

import sys
from pathlib import Path


LLM_SRC = Path(__file__).resolve().parents[1] / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.inference.records import PREDICTION_LOGGING_VERSION, run_logged_synthetic_mock  # noqa: E402


def main() -> int:
    summary = run_logged_synthetic_mock(Path.cwd().resolve())
    print(f"prediction_logging_version={PREDICTION_LOGGING_VERSION}")
    print(f"run_id={summary['run_id']}")
    print(f"attempts_total={summary['attempts_total']}")
    print(f"predictions_attempted={summary['predictions_attempted']}")
    print(f"valid_primary={summary['valid_primary']}")
    print(f"valid_after_repair={summary['valid_after_repair']}")
    print(f"invalid={summary['invalid']}")
    print(f"backend_failures={summary['backend_failures']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
