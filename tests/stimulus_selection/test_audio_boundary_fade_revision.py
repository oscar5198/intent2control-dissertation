from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "experimental-design" / "stimulus-selection" / "src"))

from stimulus_selection.audio_boundary import apply_inaudible_boundary_fades, half_cosine_fade  # noqa: E402
from stimulus_selection.config import load_config  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]


class AudioBoundaryFadeRevisionTests(unittest.TestCase):
    def test_global_config_declares_supervisor_fade_revision(self) -> None:
        config = load_config(REPO_ROOT / "experimental-design" / "stimulus-selection" / "config" / "stimulus_selection.yaml")
        boundary = config.audio_boundary_processing
        self.assertEqual(boundary.methodology_version, "2.0")
        self.assertEqual(boundary.supervisor_revision_date, "2026-08-04")
        self.assertEqual(boundary.fade_in_ms, 5.0)
        self.assertEqual(boundary.fade_out_ms, 5.0)
        self.assertEqual(boundary.fade_shape, "half_cosine")
        self.assertEqual(boundary.exact_duration_seconds, 28.0)
        self.assertEqual(boundary.target_sample_rate, 44100)

    def test_half_cosine_shape_and_exact_fade_duration(self) -> None:
        sample_rate = 44100
        audio = np.ones((sample_rate * 28, 2), dtype=np.float32) * 0.25
        faded = apply_inaudible_boundary_fades(audio, sample_rate, 5.0, 5.0, "half_cosine")
        fade_samples = int(round(sample_rate * 0.005))
        self.assertEqual(fade_samples, 220)
        self.assertEqual(faded.shape, audio.shape)
        self.assertEqual(faded.shape[1], 2)
        self.assertAlmostEqual(float(faded[0, 0]), 0.0, places=7)
        self.assertAlmostEqual(float(faded[-1, 0]), 0.0, places=7)
        self.assertTrue(np.allclose(faded[fade_samples:-fade_samples], audio[fade_samples:-fade_samples]))
        self.assertTrue(np.allclose(faded[:fade_samples, 0], faded[:fade_samples, 1]))

    def test_half_cosine_curve_matches_helper(self) -> None:
        curve = half_cosine_fade(5, fade_in=True)
        self.assertAlmostEqual(float(curve[0]), 0.0, places=7)
        self.assertAlmostEqual(float(curve[-1]), 1.0, places=7)
        self.assertTrue(np.all(np.diff(curve) >= 0.0))

    def test_rejects_perceptible_fade_duration(self) -> None:
        audio = np.zeros((44100, 2), dtype=np.float32)
        with self.assertRaises(ValueError):
            apply_inaudible_boundary_fades(audio, 44100, 50.0, 50.0, "half_cosine")


if __name__ == "__main__":
    unittest.main()
