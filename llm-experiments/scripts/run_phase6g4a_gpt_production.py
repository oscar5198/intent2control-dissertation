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

from llm_experiments.inference.phase6g4a_gpt import prepare_infrastructure_recovery, prepare_output_budget_correction, run_gpt_production  # noqa: E402


def main() -> int:
    args = parse_args()
    if args.prepare_recovery:
        recovery = prepare_infrastructure_recovery(args.repo_root.resolve())
        print(json.dumps({
            "old_run_id": recovery["old_run_id"],
            "new_corrected_run_id": recovery["new_corrected_run_id"],
            "archive_dir": recovery["archive_dir"],
            "affected_prediction_count": recovery["failure_classification"]["affected_prediction_count"],
            "failed_transport_attempt_count": recovery["failure_classification"]["failed_transport_attempt_count"],
        }, indent=2))
        return 0
    if args.prepare_output_budget_correction:
        correction = prepare_output_budget_correction(args.repo_root.resolve())
        print(json.dumps({
            "prior_run_id": correction["prior_run_id"],
            "new_run_id": correction["new_run_id"],
            "prior_max_output_tokens": correction["prior_max_output_tokens"],
            "new_max_output_tokens": correction["new_max_output_tokens"],
            "configuration_correction_manifest": "llm-experiments/outputs/real/phase6g4/gpt/configuration_correction_256_to_1024.json",
        }, indent=2))
        return 0
    summary = run_gpt_production(args.repo_root.resolve(), guarded_batch_size=args.guarded_batch_size)
    print(json.dumps({
        "preflight_passed": summary["preflight_passed"],
        "preflight_failures": summary.get("preflight_failures", []),
        "guarded_batch_limit": summary["guarded_batch_limit"],
        "predictions_executed_this_invocation": summary["predictions_executed_this_invocation"],
        "remaining_predictions": summary["remaining_predictions"],
        "stopped_after_guarded_batch": summary["stopped_after_guarded_batch"],
        "attempted_prediction_count": summary["attempted_prediction_count"],
        "terminal_prediction_count": summary["terminal_prediction_count"],
        "GPT_PRODUCTION_INFERENCE_COMPLETE": summary["GPT_PRODUCTION_INFERENCE_COMPLETE"],
        "ALL_GPT_PREDICTIONS_VALID": summary["ALL_GPT_PREDICTIONS_VALID"],
    }, indent=2))
    return 0 if summary["GPT_PRODUCTION_INFERENCE_COMPLETE"] else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 6G.4A GPT-5.5 production inference from the frozen GPT shard.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--guarded-batch-size", type=int, default=5)
    parser.add_argument("--prepare-recovery", action="store_true", help="Archive/record the confirmed infrastructure-failure run and exit without inference.")
    parser.add_argument("--prepare-output-budget-correction", action="store_true", help="Record the GPT-only 256-to-1024 output-budget correction and exit without inference.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
