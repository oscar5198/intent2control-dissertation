from __future__ import annotations

import csv
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from stimulus_selection.mix_selection_v2 import (  # noqa: E402
    EXPECTED_COUNTS,
    V2_SCALARS,
    assert_no_stereo_imbalance_in_diversity,
    farthest_point_pool,
    greedy_kmedoids_pool,
    stereo_imbalance_qc,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
V2_TABLES = REPO_ROOT / "outputs" / "stimulus_selection" / "04_mix_selection_v2" / "tables"
FINAL_STIMULI = REPO_ROOT / "outputs" / "final_stimuli"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@unittest.skipUnless(V2_TABLES.exists(), "Stage 4 v2 outputs have not been generated yet.")
class Stage4V2GeneratedOutputTests(unittest.TestCase):
    def test_revised_scalar_set_and_qc_only_stereo_imbalance(self) -> None:
        params = _read_csv(V2_TABLES / "scalar_preprocessing_parameters_v2.csv")
        self.assertEqual(sorted({row["feature"] for row in params}), sorted(V2_SCALARS))
        qc = _read_csv(V2_TABLES / "stereo_imbalance_qc.csv")
        self.assertIn("stereo_imbalance", qc[0])
        self.assertIn("robust_qc_score", qc[0])

    def test_processed_features_do_not_place_stereo_imbalance_in_combined_coordinates(self) -> None:
        processed = _read_csv(V2_TABLES / "processed_features_v2.csv")
        combined_columns = [col for col in processed[0] if col.startswith("combined_")]
        self.assertTrue(combined_columns)
        self.assertFalse(any("stereo_imbalance" in col for col in combined_columns))
        self.assertIn("stereo_imbalance_qc_only", processed[0])

    def test_distance_table_has_no_stereo_imbalance_distance(self) -> None:
        pairs = _read_csv(V2_TABLES / "pairwise_distances_v2.csv")
        self.assertFalse(any("stereo_imbalance" in col for col in pairs[0]))
        self.assertIn("combined_euclidean_distance", pairs[0])
        self.assertIn("combined_manhattan_distance", pairs[0])

    def test_candidate_pool_targets(self) -> None:
        rows = _read_csv(V2_TABLES / "acoustic_candidate_pool.csv")
        counts: dict[str, int] = {}
        for row in rows:
            counts[row["song"]] = counts.get(row["song"], 0) + 1
        self.assertEqual(counts["Lead Me"], 20)
        self.assertEqual(counts["In The Meantime"], 20)
        self.assertEqual(counts["Red To Blue"], EXPECTED_COUNTS["Red To Blue"])
        self.assertEqual(counts["Pouring Room"], EXPECTED_COUNTS["Pouring Room"])

    def test_original_name_preview_filenames_and_excerpt_boundaries(self) -> None:
        manifest = _read_csv(V2_TABLES / "candidate_pool_preview_manifest.csv")
        self.assertTrue(manifest)
        for row in manifest:
            preview = row["preview_path"]
            self.assertTrue(preview.endswith(f"{row['original_mix_name']}_28sec.wav"))
            self.assertNotIn("contrast", preview.lower())
            self.assertNotIn("representative", preview.lower())
            duration = float(row["approved_aligned_end_seconds"]) - float(row["approved_aligned_start_seconds"])
            self.assertAlmostEqual(duration, 28.0, places=6)

    def test_no_final_stimuli_v2_side_effect(self) -> None:
        self.assertTrue(FINAL_STIMULI.exists())
        self.assertFalse((REPO_ROOT / "outputs" / "final_stimuli_v2").exists())


class Stage4V2HelperTests(unittest.TestCase):
    def test_stereo_imbalance_assertion(self) -> None:
        assert_no_stereo_imbalance_in_diversity(["rms_mean", "bark_pc_01"])
        with self.assertRaises(AssertionError):
            assert_no_stereo_imbalance_in_diversity(["rms_mean", "stereo_imbalance"])

    def test_deterministic_farthest_point_pool(self) -> None:
        coords = np.asarray([[0.0], [1.0], [2.0], [10.0], [11.0]])
        distances = np.abs(coords - coords.T)
        first = farthest_point_pool(distances, 3, 1, set(), ["a", "b", "c", "d", "e"])[0]
        second = farthest_point_pool(distances, 3, 1, set(), ["a", "b", "c", "d", "e"])[0]
        self.assertEqual(first, second)
        self.assertEqual(first[0], 1)
        self.assertEqual(len(first), 3)

    def test_farthest_point_avoids_near_duplicate_where_possible(self) -> None:
        coords = np.asarray([[0.0], [0.01], [5.0], [10.0]])
        distances = np.abs(coords - coords.T)
        selected = farthest_point_pool(distances, 3, 0, {frozenset(["a", "b"])}, ["a", "b", "c", "d"])[0]
        self.assertNotIn(1, selected)

    def test_greedy_kmedoids_is_deterministic(self) -> None:
        coords = np.asarray([[0.0], [0.1], [5.0], [5.1], [10.0], [10.1]])
        distances = np.abs(coords - coords.T)
        self.assertEqual(greedy_kmedoids_pool(distances, 3, 0), greedy_kmedoids_pool(distances, 3, 0))

    def test_stereo_imbalance_qc_retains_raw_values(self) -> None:
        import pandas as pd

        group = pd.DataFrame(
            {
                "artist": ["A"] * 5,
                "song": ["S"] * 5,
                "original_mix_name": ["m1", "m2", "m3", "m4", "m5"],
                "original_dataset_filename": ["m1.wav", "m2.wav", "m3.wav", "m4.wav", "m5.wav"],
                "mix_id": ["1", "2", "3", "4", "5"],
                "stereo_imbalance": [0.0, 0.01, -0.02, 0.03, 0.5],
            }
        )
        rows = stereo_imbalance_qc(group)
        self.assertEqual(len(rows), 5)
        self.assertIn("stereo_imbalance", rows[0])
        self.assertTrue(any(row["qc_flag"] for row in rows))


if __name__ == "__main__":
    unittest.main()
