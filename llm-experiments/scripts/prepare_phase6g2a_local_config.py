#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.inference.phase6g2 import write_phase6g2a_outputs  # noqa: E402


def main() -> int:
    readiness = write_phase6g2a_outputs(REPO_ROOT)
    print(f"local_preparation_ready={str(readiness['local_preparation_ready']).lower()}")
    print(f"SCIENTIFIC_MODEL_IDENTITIES_SELECTED={readiness['SCIENTIFIC_MODEL_IDENTITIES_SELECTED']}")
    print(f"PRODUCTION_INFERENCE_READY={readiness['PRODUCTION_INFERENCE_READY']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
