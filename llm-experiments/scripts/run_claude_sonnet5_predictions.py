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

from llm_experiments.inference.phase6g4b_claude import revalidate_existing_claude_attempts, run_claude_production  # noqa: E402


def main() -> int:
    args = parse_args()
    if args.revalidate_existing:
        manifest = revalidate_existing_claude_attempts(args.repo_root.resolve())
        print(json.dumps({
            "run_id": manifest["run_id"],
            "parser_normalizer_version": manifest["parser_normalizer_version"],
            "requests_revalidated": manifest["requests_revalidated"],
            "predictions_recovered_from_primary_attempts": manifest["predictions_recovered_from_primary_attempts"],
            "predictions_recovered_from_repair_attempts": manifest["predictions_recovered_from_repair_attempts"],
            "predictions_still_invalid": manifest["predictions_still_invalid"],
            "api_calls_during_offline_recovery": manifest["api_calls_during_offline_recovery"],
        }, indent=2))
        return 0
    summary = run_claude_production(args.repo_root.resolve(), guarded_batch_size=args.guarded_batch_size)
    print(json.dumps({
        "preflight_passed": summary["preflight_passed"],
        "preflight_failures": summary.get("preflight_failures", []),
        "guarded_batch_limit": summary["guarded_batch_limit"],
        "predictions_executed_this_invocation": summary["predictions_executed_this_invocation"],
        "remaining_predictions": summary["remaining_predictions"],
        "stopped_after_guarded_batch": summary["stopped_after_guarded_batch"],
        "halted_due_quota_exhaustion": summary["halted_due_quota_exhaustion"],
        "attempted_prediction_count": summary["attempted_prediction_count"],
        "terminal_prediction_count": summary["terminal_prediction_count"],
        "CLAUDE_PRODUCTION_INFERENCE_COMPLETE": summary["CLAUDE_PRODUCTION_INFERENCE_COMPLETE"],
        "ALL_CLAUDE_PREDICTIONS_VALID": summary["ALL_CLAUDE_PREDICTIONS_VALID"],
    }, indent=2))
    return 0 if summary["CLAUDE_PRODUCTION_INFERENCE_COMPLETE"] else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 6G.4B Claude Sonnet 5 production inference from the frozen Claude shard.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--guarded-batch-size", type=int, default=5)
    parser.add_argument("--revalidate-existing", action="store_true", help="Rebuild Claude canonical predictions from existing attempt_log.jsonl without API calls.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
