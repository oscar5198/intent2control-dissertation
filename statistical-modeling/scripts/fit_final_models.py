"""Run the final real-data Bayesian models from the repository root.

This entry point is intended for the QMUL/Linux Jupyter environment. It uses
the existing reusable model modules and the current canonical cleaned real
dataset under data/processed/.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_SRC = REPO_ROOT / "statistical-modeling" / "src"
if str(BASELINE_SRC) not in sys.path:
    sys.path.insert(0, str(BASELINE_SRC))

from statistical_baseline.real_feature_model import (  # noqa: E402
    BOUNDED_FORMULA,
    PRIMARY_FORMULA,
    SI_FORMULA,
    SAMPLING as FEATURE_SAMPLING,
    SEED as FEATURE_SEED,
    run_real_feature_model,
)
from statistical_baseline.real_stimulus_model import (  # noqa: E402
    FINAL_FORMULA,
    SAMPLING as STIMULUS_SAMPLING,
    SEED as STIMULUS_SEED,
    run_real_stimulus_model,
)


CURATED_DATA_DIR = REPO_ROOT / "data" / "processed"
ANCILLARY_DATA_DIR = REPO_ROOT / "statistical-modeling" / "data" / "real"
SUMMARY_PATH = ANCILLARY_DATA_DIR / "real_data_summary.csv"
PARTICIPANTS_PATH = CURATED_DATA_DIR / "participants_final.csv"
RATINGS_PATH = CURATED_DATA_DIR / "ratings_final.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the final full-data real Bayesian statistical modeling models.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--all", action="store_true", help="Run stimulus and feature model suites. This is the default.")
    mode.add_argument("--stimulus-only", action="store_true", help="Run only the stimulus model suite.")
    mode.add_argument("--feature-only", action="store_true", help="Run only the feature model suite.")
    parser.add_argument("--draws", type=int, default=1000, help="Posterior draws per chain.")
    parser.add_argument("--tune", type=int, default=1000, help="Tuning draws per chain.")
    parser.add_argument("--chains", type=int, default=4, help="Number of MCMC chains.")
    parser.add_argument("--target-accept", type=float, default=0.95, help="NUTS target acceptance probability.")
    return parser.parse_args()


def configure_sampling(args: argparse.Namespace) -> None:
    settings = {
        "draws": args.draws,
        "tune": args.tune,
        "chains": args.chains,
        "target_accept": args.target_accept,
    }
    STIMULUS_SAMPLING.update(settings)
    FEATURE_SAMPLING.update(settings)


def dataset_summary() -> dict[str, Any]:
    if not RATINGS_PATH.exists():
        raise FileNotFoundError(f"Missing canonical ratings file: {RATINGS_PATH}")
    ratings = pd.read_csv(RATINGS_PATH)
    summary = pd.read_csv(SUMMARY_PATH) if SUMMARY_PATH.exists() else pd.DataFrame()
    participants = pd.read_csv(PARTICIPANTS_PATH) if PARTICIPANTS_PATH.exists() else pd.DataFrame()
    group_split = (
        participants["group"].value_counts().sort_index().astype(int).to_dict()
        if "group" in participants
        else ratings[["participant_id", "group"]].drop_duplicates()["group"].value_counts().sort_index().astype(int).to_dict()
    )
    return {
        "ratings_path": str(RATINGS_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "rating_rows": int(len(ratings)),
        "analysable_n": int(ratings["participant_id"].nunique()),
        "group_split": group_split,
        "summary_rows": summary.to_dict("records"),
    }


def print_json(label: str, payload: dict[str, Any]) -> None:
    print(f"\n## {label}")
    print(json.dumps(payload, indent=2, default=str))


def main() -> int:
    args = parse_args()
    configure_sampling(args)
    run_stimulus = args.all or args.stimulus_only or not args.feature_only
    run_feature = args.all or args.feature_only or not args.stimulus_only

    print_json("Canonical cleaned dataset", dataset_summary())
    print_json(
        "Scientific formulas",
        {
            "stimulus_model": FINAL_FORMULA,
            "primary_feature_model": PRIMARY_FORMULA,
            "si_sensitivity": SI_FORMULA,
            "bounded_sensitivity": BOUNDED_FORMULA,
        },
    )
    print_json(
        "Production sampling",
        {
            "stimulus_sampling": STIMULUS_SAMPLING | {"seed": STIMULUS_SEED, "sampler": "nutpie"},
            "feature_sampling": FEATURE_SAMPLING | {"seed": FEATURE_SEED, "sampler": "nutpie"},
        },
    )

    if run_stimulus:
        print("\n## Running real stimulus model suite")
        run_real_stimulus_model()
    if run_feature:
        print("\n## Running real feature model suite")
        run_real_feature_model()

    print("\nCompleted requested real-data model suite.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
