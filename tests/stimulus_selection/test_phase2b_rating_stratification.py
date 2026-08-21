from __future__ import annotations

import csv
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "experimental-design" / "stimulus-selection" / "src"))

from stimulus_selection.rating_stratification import qc_status, score_triplets  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]


class RatingStratificationHelperTests(unittest.TestCase):
    def test_qc_status_propagates_review_and_caution(self) -> None:
        self.assertEqual(qc_status(pd.Series({"stereo_imbalance_qc_flag": "true", "low_count_warning": "false", "aggregation_status": "ok"})), "review")
        self.assertEqual(qc_status(pd.Series({"stereo_imbalance_qc_flag": "false", "low_count_warning": "true", "aggregation_status": "ok"})), "caution")
        self.assertEqual(qc_status(pd.Series({"stereo_imbalance_qc_flag": "false", "low_count_warning": "false", "aggregation_status": "ok"})), "clear")

    def test_triplet_ranking_is_deterministic_and_uses_fixed_distances(self) -> None:
        candidates = pd.DataFrame(
            {
                "song": ["Song"] * 4,
                "mix_id": ["a", "b", "c", "d"],
                "original_mix_name": ["A", "B", "C", "D"],
                "mean_preference": [0.1, 0.2, 0.8, 0.9],
                "stereo_imbalance_qc_flag": ["false"] * 4,
                "low_count_warning": ["false"] * 4,
                "aggregation_status": ["ok"] * 4,
                "rating_count": [10] * 4,
            }
        )
        distances = {
            frozenset(["a", "b"]): 1.0,
            frozenset(["a", "c"]): 3.0,
            frozenset(["a", "d"]): 4.0,
            frozenset(["b", "c"]): 2.5,
            frozenset(["b", "d"]): 3.5,
            frozenset(["c", "d"]): 1.0,
        }
        first = score_triplets(candidates, distances, "Wide Ratings", 0.8, 0.2, 0.05, 0.025)
        second = score_triplets(candidates, distances, "Wide Ratings", 0.8, 0.2, 0.05, 0.025)
        self.assertEqual([r["mix_ids"] for r in first], [r["mix_ids"] for r in second])
        self.assertIn("minimum_acoustic_distance", first[0])


if __name__ == "__main__":
    unittest.main()
