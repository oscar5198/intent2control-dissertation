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

from llm_experiments.inference.phase6g2d import freeze_phase6g2d  # noqa: E402


def main() -> int:
    args = parse_args()
    readiness = freeze_phase6g2d(args.repo_root.resolve())
    print(json.dumps({
        "MODEL_IDENTITIES_FROZEN": readiness["MODEL_IDENTITIES_FROZEN"],
        "EXACT_DEPLOYMENT_IDENTITIES_VERIFIED": readiness["EXACT_DEPLOYMENT_IDENTITIES_VERIFIED"],
        "INFERENCE_BACKENDS_VERIFIED": readiness["INFERENCE_BACKENDS_VERIFIED"],
        "PRIMARY_INFERENCE_CONFIG_FROZEN": readiness["PRIMARY_INFERENCE_CONFIG_FROZEN"],
        "PRODUCTION_INFERENCE_READY": readiness["PRODUCTION_INFERENCE_READY"],
        "expected_primary_request_count": readiness["expected_primary_request_count"],
        "PHASE6G2_COMPLETE": readiness["PHASE6G2_COMPLETE"],
        "PHASE6G3_CAN_BEGIN_IMMEDIATELY": readiness["PHASE6G3_CAN_BEGIN_IMMEDIATELY"],
    }, indent=2))
    return 0 if readiness["PRODUCTION_INFERENCE_READY"] else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze Phase 6G.2D final production registries and dry-run manifest.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
