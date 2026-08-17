from pathlib import Path
import json
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.evaluation.comparisons import run_phase6f3_comparisons  # noqa: E402
from llm_experiments.evaluation.metrics import run_phase6f2_metrics  # noqa: E402
from llm_experiments.evaluation.reporting import run_phase6f4_reporting  # noqa: E402
from llm_experiments.phase6f import validate_phase6f_determinism  # noqa: E402


def main() -> None:
    validate_phase6f_determinism(REPO_ROOT)
    run_phase6f2_metrics(REPO_ROOT)
    run_phase6f3_comparisons(REPO_ROOT)
    audit = run_phase6f4_reporting(REPO_ROOT)
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
