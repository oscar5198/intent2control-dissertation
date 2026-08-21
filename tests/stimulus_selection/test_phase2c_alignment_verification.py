from __future__ import annotations

import csv
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "experimental-design" / "stimulus-selection" / "src"))

from stimulus_selection.alignment_verification import EXPECTED_SR, _rapid_switch, pairwise_alignment  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_EVIDENCE = REPO_ROOT / "experimental-design" / "stimulus-selection" / "final-selection" / "source-evidence"


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


@unittest.skipUnless(SOURCE_EVIDENCE.exists(), "Final source-evidence package is not present.")
class FinalAlignmentEvidenceTests(unittest.TestCase):
    def test_alignment_evidence_tables_are_retained(self) -> None:
        six_alignment = _read_csv(SOURCE_EVIDENCE / "six_alignment" / "six_mix_alignment_summary.csv")
        backup_alignment = _read_csv(SOURCE_EVIDENCE / "backup_alignment" / "alignment_summary_backup.csv")
        backup_pairs = _read_csv(SOURCE_EVIDENCE / "backup_pairwise_alignment" / "pairwise_alignment_verification_backup.csv")
        self.assertTrue(six_alignment)
        self.assertTrue(backup_alignment)
        self.assertTrue(backup_pairs)


if __name__ == "__main__":
    unittest.main()
