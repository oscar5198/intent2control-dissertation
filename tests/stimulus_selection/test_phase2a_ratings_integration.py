from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "experimental-design" / "stimulus-selection" / "src"))

from stimulus_selection.ratings_integration import (  # noqa: E402
    REQUIRED_EVALUATION_COLUMNS,
    aggregate_mix_ratings,
    confidence_interval_95,
    load_evaluations,
    within_song_descriptors,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_EVIDENCE = REPO_ROOT / "experimental-design" / "stimulus-selection" / "final-selection" / "source-evidence"
FINAL_STIMULI = REPO_ROOT / "outputs" / "final_stimuli"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _evaluation_fixture(path: Path, scores: list[float]) -> Path:
    rows = []
    for idx, score in enumerate(scores):
        rows.append(
            {
                "evaluation_id": f"e{idx}",
                "session_id": f"s{idx}",
                "session_song_id": f"ss{idx}",
                "experiment_id": "exp",
                "participant_id": f"p{idx}",
                "song_id": "song_a",
                "mix_id": "mix_a",
                "legacy_song_id": "SongA",
                "legacy_mix_code": "McG-A",
                "evaluator_institution_code": "DU",
                "mixer_institution_code": "McG",
                "year": "2017",
                "mix_order_in_xml": "1",
                "presented_id": "1",
                "preference_score_0_1": str(score),
                "comment_raw": "",
                "has_comment": "no",
                "listened_flag": "true",
                "slider_moved_flag": "true",
                "listen_duration_seconds": "10",
                "stimulus_sample_rate_hz": "44100",
                "stimulus_channels": "2",
                "stimulus_duration_seconds": "28",
                "source_xml_file": "x.xml",
            }
        )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


class RatingsIntegrationHelperTests(unittest.TestCase):
    def test_load_evaluations_validates_required_columns_and_range(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ratings paths ") as tmp:
            path = _evaluation_fixture(Path(tmp) / "evaluations.csv", [0.0, 0.5, 1.0])
            df = load_evaluations(path)
            self.assertEqual(len(df), 3)
            self.assertTrue(set(REQUIRED_EVALUATION_COLUMNS).issubset(df.columns))
            bad = _evaluation_fixture(Path(tmp) / "bad.csv", [1.5])
            with self.assertRaises(ValueError):
                load_evaluations(bad)

    def test_aggregation_and_confidence_interval(self) -> None:
        df = pd.DataFrame(
            {
                "preference_score_0_1": [0.2, 0.4, 0.6],
                "participant_id": ["p1", "p2", "p3"],
                "session_id": ["s1", "s2", "s3"],
                "experiment_id": ["e1", "e1", "e2"],
                "evaluator_institution_code": ["DU", "DU", "QUT"],
                "year": ["2017", "2017", "2018"],
            }
        )
        agg = aggregate_mix_ratings(df, "preference_score_0_1", 5)
        self.assertEqual(agg["rating_count"], 3)
        self.assertAlmostEqual(float(agg["mean_preference"]), 0.4)
        self.assertEqual(agg["confidence_interval_method"], "student_t")
        self.assertTrue(agg["low_count_warning"])

    def test_zero_and_single_rating_ci_handling(self) -> None:
        low, high, method = confidence_interval_95(np.asarray([0.5]))
        self.assertIsNone(low)
        self.assertIsNone(high)
        self.assertEqual(method, "unavailable_n_less_than_2")
        empty = aggregate_mix_ratings(pd.DataFrame(columns=["preference_score_0_1"]), "preference_score_0_1", 5)
        self.assertEqual(empty["aggregation_status"], "unrated")

    def test_within_song_descriptors_do_not_cross_standardise(self) -> None:
        summary = pd.DataFrame(
            {
                "song": ["A", "A", "B", "B"],
                "mix_id": ["a1", "a2", "b1", "b2"],
                "mean_preference": [0.1, 0.9, 0.1, 0.9],
                "rating_count": [10, 10, 1, 1],
                "standard_error": [0.1, 0.1, "", ""],
                "aggregation_status": ["ok", "ok", "low_count", "low_count"],
            }
        )
        out = within_song_descriptors(summary)
        self.assertEqual(out.loc[0, "within_song_mean_rank"], 1.0)
        self.assertEqual(out.loc[2, "within_song_mean_rank"], 1.0)
        self.assertAlmostEqual(float(out.loc[0, "mean_centered_rating_within_song"]), -0.4)
        self.assertAlmostEqual(float(out.loc[2, "mean_centered_rating_within_song"]), -0.4)


@unittest.skipUnless(SOURCE_EVIDENCE.exists(), "Final source-evidence package is not present.")
class FinalRatingEvidenceTests(unittest.TestCase):
    def test_rating_summary_and_within_song_outputs(self) -> None:
        within = _read_csv(SOURCE_EVIDENCE / "current_ratings" / "mix_preference_rating_summary_within_song.csv")
        self.assertEqual(len(within), 92)
        self.assertIn("within_song_z_score", within[0])

    def test_no_final_or_v2_acoustic_side_effect_outputs(self) -> None:
        self.assertTrue(FINAL_STIMULI.exists())
        self.assertFalse((REPO_ROOT / "outputs" / "final_stimuli_v2").exists())


if __name__ == "__main__":
    unittest.main()
