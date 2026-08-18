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

from llm_experiments.inference.phase6g4c_llama import (  # noqa: E402
    prepare_backend_failed_recovery,
    run_llama_backend_failed_recovery,
    run_llama_production,
    run_llama_runtime_diagnostic,
)


def main() -> int:
    args = parse_args()
    if args.diagnose_runtime:
        diagnostic = run_llama_runtime_diagnostic(args.repo_root.resolve(), max_new_tokens=args.diagnostic_max_new_tokens)
        print(json.dumps({
            "diagnostic_only": diagnostic["diagnostic_only"],
            "preflight_passed": diagnostic["preflight_passed"],
            "preflight_failures": diagnostic["preflight_failures"],
            "runtime_success": diagnostic["runtime_success"],
            "runtime_diagnostic": diagnostic["runtime_diagnostic"],
        }, indent=2))
        return 0 if diagnostic["runtime_success"] else 1
    if args.prepare_recovery:
        manifest = prepare_backend_failed_recovery(args.repo_root.resolve())
        print(json.dumps({
            "recovery_run_id": manifest["recovery_run_id"],
            "eligible_request_count": manifest["eligible_request_count"],
            "eligibility_rule": manifest["eligibility_rule"],
            "historical_source_artifacts_preserved": manifest["historical_source_artifacts_preserved"],
        }, indent=2))
        return 0
    if args.recover_backend_failed:
        summary = run_llama_backend_failed_recovery(args.repo_root.resolve(), guarded_batch_size=args.guarded_batch_size)
    else:
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
    parser.add_argument("--diagnose-runtime", action="store_true", help="Run one non-study local runtime diagnostic in a separate diagnostic namespace.")
    parser.add_argument("--diagnostic-max-new-tokens", type=int, default=8)
    parser.add_argument("--prepare-recovery", action="store_true", help="Write backend-failed recovery eligibility manifest without running inference.")
    parser.add_argument("--recover-backend-failed", action="store_true", help="Run a guarded recovery batch only for source run backend_failed slots.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
