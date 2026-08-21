from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "experimental-design" / "stimulus-selection" / "src"))

from stimulus_selection.final_decision import (
    CandidateScore,
    SourceEvidence,
    boundary_quality,
    coverage,
    map_track_to_group,
    refine_and_select,
    simultaneous_core_coverage,
    validate_decision,
)
from stimulus_selection.audio_decode import DecodedAudio


class FinalDecisionTests(unittest.TestCase):
    def _evidence(self) -> SourceEvidence:
        times = np.arange(0, 40, 0.25, dtype=np.float32)
        active = ((times >= 4) & (times < 34)).astype(np.float32)
        return SourceEvidence(
            artist="Artist",
            song="Song",
            raw_root=Path("raw"),
            mappings=[],
            group_activity={
                "vocal": active,
                "bass": active,
                "drums": active,
                "other": ((times >= 2) & (times < 36)).astype(np.float32),
            },
            times=times,
            source_offset_seconds=0.0,
            source_alignment_score=0.9,
        )

    def test_source_group_activity_scoring(self) -> None:
        ev = self._evidence()
        self.assertAlmostEqual(coverage(ev, "vocal", 4.0, 8.0), 1.0)
        self.assertAlmostEqual(coverage(ev, "bass", 0.0, 4.0), 0.0)
        self.assertAlmostEqual(simultaneous_core_coverage(ev, 4.0, 8.0), 1.0)
        self.assertGreater(boundary_quality(ev, 4.0, 8.0), 0.0)

    def test_track_mapping_is_cautious_and_label_based(self) -> None:
        self.assertEqual(map_track_to_group(Path("LeadVoc.wav")).group, "vocal")
        self.assertEqual(map_track_to_group(Path("Bass DI.wav")).group, "bass")
        self.assertEqual(map_track_to_group(Path("KOut.wav")).group, "drums")
        self.assertEqual(map_track_to_group(Path("Paul GTR.wav")).group, "other")
        self.assertIsNone(map_track_to_group(Path("mix.wav")))

    def test_candidate_boundary_refinement_and_deterministic_selection(self) -> None:
        ev = self._evidence()
        align = [{
            "retained_for_excerpt_selection": "true",
            "alignment_confidence": "0.9",
            "source_path": "unused.wav",
            "refined_lag_seconds": "0",
            "estimated_lag_seconds": "0",
            "mix_id": "m1",
        }]
        candidates = [
            {"candidate_rank": "1", "aligned_start_seconds": "1.0"},
            {"candidate_rank": "2", "aligned_start_seconds": "4.0"},
        ]
        import stimulus_selection.final_decision as fd
        old = fd.cross_mix_variation
        fd.cross_mix_variation = lambda rows, start, end: 0.5
        try:
            best_a, scored_a = refine_and_select(ev, align, candidates, 0.0, 40.0)
            best_b, scored_b = refine_and_select(ev, align, candidates, 0.0, 40.0)
        finally:
            fd.cross_mix_variation = old
        self.assertEqual((best_a.candidate_rank, best_a.start), (best_b.candidate_rank, best_b.start))
        self.assertGreaterEqual(best_a.start, 1.0)
        self.assertTrue(scored_a)

    def test_exactly_28_second_final_decision_validation(self) -> None:
        score = CandidateScore("Artist", "Song", 1, 5.0, 5.0, 33.0, 1, 1, 1, 1, 1, 0.5, 1, "min=1", 1, 1, "", "")
        align = [{
            "retained_for_excerpt_selection": "true",
            "source_path": "unused.wav",
            "refined_lag_seconds": "0",
            "estimated_lag_seconds": "0",
            "mix_id": "m1",
        }]
        import stimulus_selection.final_decision as fd
        old_cache = fd._DECODE_CACHE.copy()
        fd._DECODE_CACHE["unused.wav"] = DecodedAudio(np.zeros((40 * 44100, 2), dtype=np.float32), 44100, 2, 40.0, "synthetic")
        try:
            validate_decision(score, align, 0.0, 40.0)
            bad = CandidateScore("Artist", "Song", 1, 5.0, 5.0, 32.5, 1, 1, 1, 1, 1, 0.5, 1, "min=1", 1, 1, "", "")
            with self.assertRaises(ValueError):
                validate_decision(bad, align, 0.0, 40.0)
        finally:
            fd._DECODE_CACHE.clear()
            fd._DECODE_CACHE.update(old_cache)


if __name__ == "__main__":
    unittest.main()
