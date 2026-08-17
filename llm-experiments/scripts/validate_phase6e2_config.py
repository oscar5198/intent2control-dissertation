"""CLI wrapper for Phase 6E.2 primary inference configuration validation."""

from __future__ import annotations

import sys
from pathlib import Path


LLM_SRC = Path(__file__).resolve().parents[1] / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.inference.configuration import (  # noqa: E402
    DEFAULT_OUTPUT_DIR,
    PRIMARY_INFERENCE_CONFIG_VERSION,
    production_preflight,
    write_phase6e2_validation_outputs,
)
from llm_experiments.prompts.prompt_spec import write_json  # noqa: E402


def main() -> int:
    repo_root = Path.cwd().resolve()
    validation = write_phase6e2_validation_outputs(repo_root)
    preflight = production_preflight(repo_root)
    write_json(repo_root / DEFAULT_OUTPUT_DIR / "phase6e2_production_preflight.json", preflight)
    print(f"config_version={PRIMARY_INFERENCE_CONFIG_VERSION}")
    print(f"MODEL_IDENTITIES_FROZEN={validation['freeze_gates']['MODEL_IDENTITIES_FROZEN']}")
    print(f"INFERENCE_BACKENDS_VERIFIED={validation['freeze_gates']['INFERENCE_BACKENDS_VERIFIED']}")
    print(f"PRIMARY_INFERENCE_CONFIG_FROZEN={validation['freeze_gates']['PRIMARY_INFERENCE_CONFIG_FROZEN']}")
    print(f"production_inference_allowed={preflight['production_inference_allowed']}")
    print(f"unresolved_warning_count={len(validation['warnings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
