from pathlib import Path
import json
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.evaluation.reporting import DEFAULT_OUTPUT_DIR, run_phase6f4_reporting  # noqa: E402


def main() -> None:
    audit_path = REPO_ROOT / DEFAULT_OUTPUT_DIR / "phase6f4_predata_readiness_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else run_phase6f4_reporting(REPO_ROOT)
    print(json.dumps(audit, indent=2, sort_keys=True))
    if not audit["predata_analysis_ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

