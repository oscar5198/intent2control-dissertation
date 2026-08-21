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

from llm_experiments.inference.phase6g3 import freeze_phase6g3  # noqa: E402


def main() -> int:
    args = parse_args()
    manifest = freeze_phase6g3(args.repo_root.resolve())
    print(json.dumps({
        "rendered_prompt_count": manifest["rendered_prompt_count"],
        "condition_counts": manifest["condition_counts"],
        "matched_pair_count": manifest["matched_pair_count"],
        "request_count": manifest["request_count"],
        "REAL_PRODUCTION_PROMPTS_FROZEN": manifest["REAL_PRODUCTION_PROMPTS_FROZEN"],
        "PHASE6G3_COMPLETE": manifest["PHASE6G3_COMPLETE"],
        "PHASE6G4_CAN_BEGIN_IMMEDIATELY": manifest["PHASE6G4_CAN_BEGIN_IMMEDIATELY"],
    }, indent=2))
    return 0 if manifest["REAL_PRODUCTION_PROMPTS_FROZEN"] else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze Phase 6G.3 final real rendered prompts and request manifests.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
