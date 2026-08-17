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

from llm_experiments.inference.phase6g2 import build_final_registry_scaffold, validate_remote_artifact, write_json  # noqa: E402


def main() -> int:
    args = parse_args()
    qmul = validate_remote_artifact(resolve(args.qmul), "qmul") if args.qmul else {"valid": False, "errors": ["QMUL artifact not provided"], "warnings": []}
    runpod = validate_remote_artifact(resolve(args.runpod), "runpod") if args.runpod else {"valid": False, "errors": ["RunPod artifact not provided"], "warnings": []}
    scaffold = build_final_registry_scaffold(REPO_ROOT)
    scaffold["qmul_validation"] = qmul
    scaffold["runpod_validation"] = runpod
    scaffold["can_freeze_final_production_registry"] = bool(qmul.get("backend_verified") and runpod.get("backend_verified"))
    scaffold["status"] = "ready_for_manual_final_registry_freeze" if scaffold["can_freeze_final_production_registry"] else "blocked_pending_remote_verification"
    scaffold["PRODUCTION_INFERENCE_READY"] = False
    if args.output:
        write_json(resolve(args.output), scaffold)
    print(json.dumps({"qmul_valid": qmul["valid"], "qmul_execution_architectures_verified": qmul.get("execution_architectures_verified", False), "qmul_production_config_verified": qmul.get("production_config_verified", False), "qmul_backend_verified": qmul.get("backend_verified", False), "runpod_valid": runpod["valid"], "runpod_execution_architecture_verified": runpod.get("execution_architectures_verified", False), "runpod_production_config_verified": runpod.get("production_config_verified", False), "runpod_backend_verified": runpod.get("backend_verified", False), "can_freeze_final_production_registry": scaffold["can_freeze_final_production_registry"], "PRODUCTION_INFERENCE_READY": False}, indent=2))
    return 0 if qmul.get("backend_verified") and runpod.get("backend_verified") else 1


def resolve(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate copied-back Phase 6G.2 remote verification artifacts.")
    parser.add_argument("--qmul", help="Path to phase6g2b_qmul_model_verification.json.")
    parser.add_argument("--runpod", help="Path to phase6g2c_runpod_centaur_verification.json.")
    parser.add_argument("--output", help="Path for the local Phase 6G.2D reconciliation scaffold.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
