"""CLI wrapper for Phase 6E.4 synthetic failure-matrix execution."""

from __future__ import annotations

import sys
from pathlib import Path


LLM_SRC = Path(__file__).resolve().parents[1] / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.inference.failures import FAILURE_HANDLING_VERSION  # noqa: E402
from llm_experiments.inference.state_machine import run_synthetic_failure_matrix  # noqa: E402


def main() -> int:
    summary = run_synthetic_failure_matrix(Path.cwd().resolve())
    print(f"failure_handling_version={FAILURE_HANDLING_VERSION}")
    print(f"run_id={summary['run_id']}")
    print(f"attempts_total={summary['attempts_total']}")
    print(f"predictions_attempted={summary['predictions_attempted']}")
    print(f"valid_primary={summary['valid_primary']}")
    print(f"valid_after_repair={summary['valid_after_repair']}")
    print(f"invalid={summary['invalid']}")
    print(f"backend_failures={summary['backend_failures']}")
    print(f"total_transport_retries={summary['total_transport_retries']}")
    print(f"total_formatting_repairs={summary['total_formatting_repairs']}")
    print(f"INFERENCE_RUN_COMPLETE={summary['INFERENCE_RUN_COMPLETE']}")
    print(f"ALL_EXPECTED_PREDICTIONS_VALID={summary['ALL_EXPECTED_PREDICTIONS_VALID']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
