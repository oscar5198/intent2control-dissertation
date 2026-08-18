#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.inference.phase6g4a_gpt_recovery import run_gpt_recovery  # noqa: E402


def main() -> int:
    args = parse_args()
    summary = run_gpt_recovery(args.repo_root.resolve(), guarded_batch_size=args.guarded_batch_size)
    print(json.dumps({
        "run_id": summary["run_id"],
        "source_run03_id": summary["source_run03_id"],
        "preflight_passed": summary["preflight_passed"],
        "guarded_batch_limit": summary["guarded_batch_limit"],
        "recovery_predictions_executed_this_invocation": summary["recovery_predictions_executed_this_invocation"],
        "remaining_unresolved_recovery_predictions": summary["remaining_unresolved_recovery_predictions"],
        "halted_due_quota_exhaustion": summary["halted_due_quota_exhaustion"],
        "GPT_RECOVERY_RUN_COMPLETE": summary["GPT_RECOVERY_RUN_COMPLETE"],
        "ALL_GPT_RECOVERY_PREDICTIONS_VALID": summary["ALL_GPT_RECOVERY_PREDICTIONS_VALID"],
    }, indent=2))
    return 0 if summary["GPT_RECOVERY_RUN_COMPLETE"] and summary["ALL_GPT_RECOVERY_PREDICTIONS_VALID"] else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 6G.4A targeted GPT-5.5 recovery from Run 03 operational failures.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--guarded-batch-size", type=int, default=6)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
