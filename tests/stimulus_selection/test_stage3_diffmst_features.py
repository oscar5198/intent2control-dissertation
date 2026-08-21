from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

import torch
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "experimental-design" / "stimulus-selection" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from stimulus_selection.config import load_config
from stimulus_selection.diffmst_validation import (
    deterministic_test_signals,
    edge_case_results,
    run_diffmst_feature_validation,
)
from stimulus_selection.third_party.diffmst_features import (
    compute_barkspectrum,
    compute_crest_factor,
    compute_rms,
    compute_stereo_imbalance,
    compute_stereo_width,
)

from reference_adapters.diffmst_reference import import_reference_loss


REFERENCE_ROOT = Path(
    os.environ.get(
        "DIFF_MST_REFERENCE_ROOT",
        "C:/Users/oscar/Documents/7. QMUL UNIVERSITY/1. Master Program/3. MSc Project/Diff-MST",
    )
)


def _minimal_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "stimulus_selection.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "dataset_root": str(tmp_path / "dataset"),
                "relationship_tables_root": str(tmp_path / "relationships"),
                "public_audio_root": str(tmp_path / "audio"),
                "output_root": str(tmp_path / "outputs"),
                "target_sample_rate": 44100,
                "minimum_duration_seconds": 20,
                "require_stereo": True,
                "allowed_extensions": [".wav"],
                "institution_system_codes": ["MG"],
                "primary_candidate_songs": [],
            }
        ),
        encoding="utf-8",
    )
    return config_path


@unittest.skipUnless((REFERENCE_ROOT / "mst" / "loss.py").exists(), "Diff-MST reference repository not available")
class Stage3DiffMSTEquivalenceTests(unittest.TestCase):
    def test_reference_adapter_imports_original_functions_temporarily(self) -> None:
        before = list(sys.path)
        reference = import_reference_loss(REFERENCE_ROOT)
        self.assertTrue(callable(reference.compute_rms))
        self.assertEqual(sys.path, before)

    def test_feature_shapes_dtype_and_equivalence_on_deterministic_signals(self) -> None:
        reference = import_reference_loss(REFERENCE_ROOT)
        features = [
            ("RMS", reference.compute_rms, compute_rms, {}),
            ("CF", reference.compute_crest_factor, compute_crest_factor, {}),
            ("SW", reference.compute_stereo_width, compute_stereo_width, {}),
            ("SI", reference.compute_stereo_imbalance, compute_stereo_imbalance, {}),
            ("BS", reference.compute_barkspectrum, compute_barkspectrum, {}),
        ]
        for case_name, signal in deterministic_test_signals(torch.float32):
            with self.subTest(case=case_name):
                for _, reference_func, vendored_func, kwargs in features:
                    ref = reference_func(signal.clone(), **kwargs)
                    ven = vendored_func(signal.clone(), **kwargs)
                    self.assertEqual(tuple(ref.shape), tuple(ven.shape))
                    self.assertEqual(ref.dtype, ven.dtype)
                    self.assertTrue(torch.isfinite(ven).all())
                    self.assertTrue(torch.allclose(ref, ven, atol=1e-5, rtol=1e-5))

    def test_bark_output_shapes_are_documented_not_assumed(self) -> None:
        x = deterministic_test_signals(torch.float32)[0][1]
        self.assertEqual(tuple(compute_barkspectrum(x, mode="mono").shape), (1, 24, 1))
        self.assertEqual(tuple(compute_barkspectrum(x, mode="stereo").shape), (1, 24, 2))
        self.assertEqual(tuple(compute_barkspectrum(x, mode="mid-side").shape), (1, 24, 2))

    def test_validation_command_writes_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(_minimal_config(Path(tmp)))
            result = run_diffmst_feature_validation(config, REFERENCE_ROOT)
            self.assertTrue(result.csv_path.exists())
            self.assertTrue(result.report_path.exists())
            self.assertTrue(all(row["passed"] == "true" for row in result.rows))


class Stage3DiffMSTEdgeCaseTests(unittest.TestCase):
    def test_invalid_shape_and_non_finite_inputs_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            compute_stereo_width(torch.zeros(1, 1, 1024))
        with self.assertRaises(ValueError):
            compute_stereo_imbalance(torch.zeros(1, 3, 1024))
        with self.assertRaises(ValueError):
            compute_rms(torch.full((1, 2, 1024), float("nan")))
        with self.assertRaises(ValueError):
            compute_crest_factor(torch.full((1, 2, 1024), float("inf")))

    def test_edge_case_matrix_passes(self) -> None:
        rows = edge_case_results()
        self.assertTrue(rows)
        self.assertTrue(all(row["passed"] == "true" for row in rows))


if __name__ == "__main__":
    unittest.main()
