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

from llm_experiments.inference.phase6g4c_llama import run_llama_production  # noqa: E402


def main() -> int:
    args = parse_args()
    summary = run_llama_production(args.repo_root.resolve(), guarded_batch_size=args.guarded_batch_size)
    print(json.dumps({
        "preflight_passed": summary["preflight_passed"],
        "preflight_failures": summary.get("preflight_failures", []),
        "exact_requested_backend_model": summary["exact_requested_backend_model"],
        "actual_returned_models": summary["actual_returned_models"],
        "guarded_batch_limit": summary["guarded_batch_limit"],
        "predictions_executed_this_invocation": summary["predictions_executed_this_invocation"],
        "remaining_predictions": summary["remaining_predictions"],
        "stopped_after_guarded_batch": summary["stopped_after_guarded_batch"],
        "attempted_prediction_count": summary["attempted_prediction_count"],
        "terminal_prediction_count": summary["terminal_prediction_count"],
        "LLAMA_PRODUCTION_INFERENCE_COMPLETE": summary["LLAMA_PRODUCTION_INFERENCE_COMPLETE"],
        "ALL_LLAMA_PREDICTIONS_VALID": summary["ALL_LLAMA_PREDICTIONS_VALID"],
    }, indent=2))
    return 0 if summary["LLAMA_PRODUCTION_INFERENCE_COMPLETE"] else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 6G.4C Llama 3.1 70B Instruct production inference from the frozen QMUL Llama shard.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--guarded-batch-size", type=int, default=5)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
