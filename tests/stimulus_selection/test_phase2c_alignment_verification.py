from __future__ import annotations

import csv
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from stimulus_selection.alignment_verification import EXPECTED_SR, _rapid_switch, pairwise_alignment  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE2C = REPO_ROOT / "outputs" / "stimulus_selection" / "05_alignment_verification"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class AlignmentVerificationHelperTests(unittest.TestCase):
    def test_pairwise_alignment_identical_audio_passes(self) -> None:
        t = np.arange(EXPECTED_SR * 28, dtype=np.float32) / EXPECTED_SR
        sig = np.stack([0.1 * np.sin(2 * np.pi * 440 * t), 0.1 * np.sin(2 * np.pi * 440 * t)], axis=1)
        result = pairwise_alignment(sig, sig, EXPECTED_SR)
        self.assertEqual(result["alignment_quality"], "PASS")
        self.assertEqual(result["sample_offset"], 0)

    def test_rapid_switch_length_and_stereo_shape(self) -> None:
        audios = [np.zeros((EXPECTED_SR * 28, 2), dtype=np.float32) + i * 0.01 for i in range(3)]
        rapid = _rapid_switch(audios, EXPECTED_SR)
        self.assertEqual(rapid.shape, (EXPECTED_SR * 28, 2))


@unittest.skipUnless(PHASE2C.exists(), "Phase 2C outputs have not been generated yet.")
class AlignmentVerificationGeneratedOutputTests(unittest.TestCase):
    def test_tables_are_complete(self) -> None:
        pairs = _read_csv(PHASE2C / "tables" / "pairwise_alignment_verification.csv")
        summary = _read_csv(PHASE2C / "tables" / "alignment_summary.csv")
        checklist = _read_csv(PHASE2C / "tables" / "manual_alignment_review.csv")
        self.assertEqual(len(pairs), 24)
        self.assertEqual(len(summary), 8)
        self.assertEqual(len(checklist), 8)

    def test_figures_and_rapid_switch_files_generated(self) -> None:
        figures = list((PHASE2C / "figures").rglob("*.png"))
        rapid = list((PHASE2C / "review_audio").rglob("RapidSwitch.wav"))
        self.assertEqual(len(figures), 16)
        self.assertEqual(len(rapid), 8)

    def test_review_audio_contains_copied_individual_wavs(self) -> None:
        wavs = [p for p in (PHASE2C / "review_audio").rglob("*.wav") if p.name != "RapidSwitch.wav"]
        self.assertEqual(len(wavs), 24)
        for wav in wavs:
            self.assertTrue(wav.name.endswith("_28sec.wav"))
            self.assertNotIn("_A_", wav.name)
            self.assertNotIn("_B_", wav.name)
            self.assertNotIn("_C_", wav.name)

    def test_review_audio_hashes_match_source(self) -> None:
        manifest = _read_csv(PHASE2C / "tables" / "review_audio_manifest.csv")
        self.assertEqual(len(manifest), 24)
        self.assertTrue(all(row["hash_match"] == "true" for row in manifest))


if __name__ == "__main__":
    unittest.main()
