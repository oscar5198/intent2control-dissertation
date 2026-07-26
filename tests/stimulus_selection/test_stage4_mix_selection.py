from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from stimulus_selection.mix_selection import (
    best_triplet,
    equal_block_weight,
    exact_k_medoids,
    medoid_index,
    pairwise_matrix,
    robust_parameters,
    select_bark_pca,
)


class Stage4MixSelectionMathTests(unittest.TestCase):
    def test_robust_scaling_and_zero_iqr_handling(self) -> None:
        matrix = np.asarray([[1.0, 5.0], [2.0, 5.0], [3.0, 5.0]])
        scaled, params = robust_parameters(matrix, ["varies", "constant"])
        self.assertTrue(np.allclose(scaled[:, 0], [-1.0, 0.0, 1.0]))
        self.assertTrue(np.allclose(scaled[:, 1], 0.0))
        self.assertFalse(params[0]["near_zero_iqr"])
        self.assertTrue(params[1]["near_zero_iqr"])
        self.assertFalse(params[1]["retained"])

    def test_bark_pca_component_selection_is_capped(self) -> None:
        rng = np.random.default_rng(42)
        matrix = rng.normal(size=(5, 10))
        pca, scores, retained = select_bark_pca(matrix, 0.95)
        self.assertLessEqual(retained, 4)
        self.assertEqual(scores.shape, (5, retained))
        self.assertGreaterEqual(np.sum(pca.explained_variance_ratio_[:retained]), 0.95)

    def test_equal_block_weighting_has_unit_expected_squared_norm(self) -> None:
        block = np.asarray([[1.0, 0.0], [0.0, 2.0], [2.0, 2.0]])
        weighted = equal_block_weight(block)
        self.assertAlmostEqual(float(np.mean(np.sum(weighted**2, axis=1))), 1.0)

    def test_medoid_and_triplet_enumeration(self) -> None:
        coords = np.asarray([[0.0], [1.0], [2.0], [10.0]])
        distances = pairwise_matrix(coords)
        self.assertEqual(medoid_index(distances), 1)
        self.assertEqual(best_triplet(distances, required_index=1), (0, 1, 3))
        self.assertEqual(best_triplet(distances), (0, 2, 3))

    def test_minimum_pairwise_distance_calculation(self) -> None:
        distances = pairwise_matrix(np.asarray([[0.0, 0.0], [3.0, 4.0], [6.0, 8.0]]))
        self.assertAlmostEqual(distances[0, 1], 5.0)
        self.assertAlmostEqual(distances[1, 2], 5.0)

    def test_deterministic_k_medoids(self) -> None:
        coords = np.asarray([[0.0], [0.1], [5.0], [5.1], [10.0], [10.1]])
        distances = pairwise_matrix(coords)
        self.assertEqual(exact_k_medoids(distances, 3), (0, 2, 5))
        self.assertEqual(exact_k_medoids(distances, 3), (0, 2, 5))


class Stage4PathAndContractTests(unittest.TestCase):
    def test_windows_paths_with_spaces_round_trip_in_csv(self) -> None:
        with tempfile.TemporaryDirectory(prefix="Stage 4 Path ") as tmp:
            path = Path(tmp) / "manifest.csv"
            source = r"C:\Users\oscar\Documents\7. QMUL UNIVERSITY\file with spaces.wav"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["source_path"])
                writer.writeheader()
                writer.writerow({"source_path": source})
            with path.open("r", newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["source_path"], source)


if __name__ == "__main__":
    unittest.main()
