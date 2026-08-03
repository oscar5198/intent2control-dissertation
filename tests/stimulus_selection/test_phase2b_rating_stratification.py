from __future__ import annotations

import csv
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from stimulus_selection.rating_stratification import qc_status, score_triplets  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]
TABLES = REPO_ROOT / "outputs" / "stimulus_selection" / "06_rating_stratification" / "tables"
AUDIO = REPO_ROOT / "outputs" / "stimulus_selection" / "06_rating_stratification" / "candidate_review_audio"
FINAL_STIMULI = REPO_ROOT / "outputs" / "final_stimuli"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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


@unittest.skipUnless(TABLES.exists(), "Phase 2B outputs have not been generated yet.")
class RatingStratificationGeneratedOutputTests(unittest.TestCase):
    def test_recommendation_tables_have_rated_three_mix_triplets(self) -> None:
        rows = _read_csv(TABLES / "supervisor_shortlist.csv")
        self.assertEqual(len(rows), 8)
        for row in rows:
            self.assertEqual(len(row["mix_ids"].split("|")), 3)
            self.assertEqual(len(row["original_mix_names"].split("|")), 3)
            self.assertNotIn("McG-pro", row["original_mix_names"].split("|"))

    def test_top10_tables_are_deterministic_shape(self) -> None:
        self.assertEqual(len(_read_csv(TABLES / "similar_rating_triplets.csv")), 40)
        self.assertEqual(len(_read_csv(TABLES / "wide_rating_triplets.csv")), 40)

    def test_qc_flags_and_original_names_preserved(self) -> None:
        rows = _read_csv(TABLES / "triplet_scores.csv")
        self.assertTrue(rows)
        self.assertIn("qc_statuses", rows[0])
        self.assertIn("original_mix_names", rows[0])
        self.assertFalse(any("mix_" in row["original_mix_names"] for row in rows))

    def test_candidate_audio_copied_with_original_names_and_no_participant_labels(self) -> None:
        wavs = list(AUDIO.rglob("*.wav"))
        self.assertTrue(wavs)
        for wav in wavs:
            self.assertTrue(wav.name.endswith("_28sec.wav"))
            self.assertNotIn("_A_", wav.name)
            self.assertNotIn("_B_", wav.name)
            self.assertNotIn("_C_", wav.name)
        self.assertFalse((REPO_ROOT / "outputs" / "final_stimuli_v2").exists())
        self.assertTrue(FINAL_STIMULI.exists())


if __name__ == "__main__":
    unittest.main()
