"""Run the official real-data held-out statistical MCMC evaluation.

This script is intended for the QMUL/Linux environment. It does not define new
scientific models; it calls the reusable held-out evaluation module with the
official MCMC settings and checkpointing enabled by default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_SRC = REPO_ROOT / "statistical-baseline" / "src"
if str(BASELINE_SRC) not in sys.path:
    sys.path.insert(0, str(BASELINE_SRC))

from statistical_baseline.real_heldout_evaluation import (  # noqa: E402
    OUTPUT_DIR,
    REAL_DATA_PATH,
    SAMPLER_SETTINGS,
    heldout_checkpoint_status,
    run_real_heldout_evaluation,
)


SUMMARY_PATH = REPO_ROOT / "statistical-baseline" / "data" / "real" / "real_data_summary.csv"
MANIFEST_PATH = REPO_ROOT / "statistical-baseline" / "data" / "real" / "real_cleaning_manifest.json"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run official Phase 6 real held-out statistical MCMC evaluation.")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR, help="Held-out output directory.")
    parser.add_argument("--no-resume", action="store_true", help="Disable checkpoint resume and refit requested folds.")
    parser.add_argument("--max-folds", type=int, default=None, help="Optional smoke/debug limit; omit for all 198 folds.")
    parser.add_argument("--fold-id", type=int, action="append", default=None, help="Specific fold_id to run; repeat for multiple folds.")
    parser.add_argument("--parallel-folds", type=int, default=1, help="Number of fold/model fits to run concurrently.")
    parser.add_argument("--status", action="store_true", help="Report checkpoint/resume status without fitting models.")
    parser.add_argument("--chains", type=int, default=2, help="MCMC chains.")
    parser.add_argument("--draws", type=int, default=500, help="Posterior draws per chain.")
    parser.add_argument("--tune", type=int, default=500, help="Tuning draws per chain.")
    parser.add_argument("--target-accept", type=float, default=0.95, help="NUTS target acceptance probability.")
    parser.add_argument("--cores", type=int, default=None, help="Optional PyMC cores per fold; omit for PyMC default.")
    parser.add_argument(
        "--escalated",
        action="store_true",
        help="Use the documented problematic-fold escalation preset: 2 chains, 1000 tune, 1000 draws, target_accept=0.97.",
    )
    return parser.parse_args()


def verify_current_dataset() -> dict[str, Any]:
    ratings = pd.read_csv(REAL_DATA_PATH)
    summary = pd.read_csv(SUMMARY_PATH)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    expected = {
        "participants": 33,
        "group_01": 17,
        "group_02": 16,
        "rating_rows": 990,
        "trials": 198,
        "stimuli": 20,
    }
    actual = {
        "participants": int(ratings["participant_id"].nunique()),
        "group_01": int(ratings[["participant_id", "group"]].drop_duplicates()["group"].eq("group_01").sum()),
        "group_02": int(ratings[["participant_id", "group"]].drop_duplicates()["group"].eq("group_02").sum()),
        "rating_rows": int(len(ratings)),
        "trials": int(ratings[["participant_id", "song_id", "episode"]].drop_duplicates().shape[0]),
        "stimuli": int(ratings["stimulus_id"].nunique()),
    }
    if actual != expected:
        raise ValueError(f"Canonical real dataset mismatch: expected {expected}, found {actual}")
    summary_row = summary.iloc[0].to_dict()
    return {
        "ratings_path": str(REAL_DATA_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "ratings_sha256": file_sha256(REAL_DATA_PATH),
        "cleaning_manifest": str(MANIFEST_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "raw_sha256": manifest["raw_provenance"]["sha256"],
        "summary": summary_row,
    }


def sampler_settings(args: argparse.Namespace) -> dict[str, Any]:
    if args.escalated:
        args.chains = 2
        args.draws = 1000
        args.tune = 1000
        args.target_accept = 0.97
    settings = {
        **SAMPLER_SETTINGS,
        "chains": args.chains,
        "draws": args.draws,
        "tune": args.tune,
        "target_accept": args.target_accept,
        "inference_method": "nutpie",
    }
    if args.cores is not None:
        settings["cores"] = args.cores
    return settings


def main() -> int:
    args = parse_args()
    dataset = verify_current_dataset()
    settings = sampler_settings(args)
    print("Verified current canonical N=33 dataset:")
    print(json.dumps(dataset, indent=2, default=str))
    print("Held-out MCMC settings:")
    print(json.dumps(settings, indent=2, default=str))
    if args.status:
        status = heldout_checkpoint_status(
            output_dir=args.output_dir,
            fit_method="mcmc",
            sampler_settings=settings,
            max_folds=args.max_folds,
            fold_ids=args.fold_id,
        )
        print("Held-out MCMC checkpoint status:")
        print(json.dumps(status, indent=2, default=str))
        return 0
    run_real_heldout_evaluation(
        output_dir=args.output_dir,
        resume=not args.no_resume,
        max_folds=args.max_folds,
        fit_method="mcmc",
        sampler_settings=settings,
        parallel_folds=args.parallel_folds,
        fold_ids=args.fold_id,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
