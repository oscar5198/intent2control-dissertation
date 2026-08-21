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

from llm_experiments.inference.phase6g5_final_predictions import build_phase6g5_final_predictions  # noqa: E402


def main() -> int:
    args = parse_args()
    result = build_phase6g5_final_predictions(args.repo_root.resolve())
    print(json.dumps({
        "paths": result["paths"],
        "total_rows": result["qc_summary"]["actual_total_rows"],
        "model_counts": result["qc_summary"]["model_counts"],
        "cross_model_request_alignment": result["qc_summary"]["cross_model_request_alignment"],
        "duplicate_count": result["qc_summary"]["duplicate_model_canonical_request_key_count"],
        "qc_error_count": result["qc_summary"]["row_qc_error_count"],
        "gates": result["freeze_manifest"]["gates"],
        "freeze_blockers": result["freeze_manifest"]["freeze_blockers"][:5],
    }, indent=2))
    return 0 if result["qc_summary"]["FINAL_LLM_PREDICTIONS_QC_PASSED"] else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Phase 6G.5 final ground-truth-free LLM prediction package.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
