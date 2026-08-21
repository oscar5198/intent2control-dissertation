from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import yaml
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "experimental-design" / "stimulus-selection" / "src"))

from stimulus_selection.config import load_config
from stimulus_selection.feature_extraction import (
    BARK_MID_COLUMNS,
    BARK_SIDE_COLUMNS,
    EXPECTED_SAMPLES,
    RAW_FEATURE_COLUMNS,
    aligned_to_source_interval,
    alignment_row_for_mix,
    extract_exact_excerpt,
    extract_feature_rows,
    is_retained_human_mix,
    run_feature_extraction,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_config(root: Path, output_root: Path, approved: list[dict[str, object]] | None = None) -> Path:
    config_path = root / "configs with spaces" / "stimulus_selection.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "dataset_root": str(root / "Dataset Root With Spaces"),
                "relationship_tables_root": str(root / "relationships"),
                "public_audio_root": str(root / "audio"),
                "output_root": str(output_root),
                "target_sample_rate": 44100,
                "minimum_duration_seconds": 20,
                "require_stereo": True,
                "allowed_extensions": [".wav"],
                "institution_system_codes": ["MG", "AUTO", "Robot"],
                "primary_candidate_songs": [],
                "approved_excerpts": approved
                if approved is not None
                else [
                    {"artist": "Artist", "song": "Song", "aligned_start_seconds": 1.0, "aligned_end_seconds": 29.0},
                    {"artist": "Artist", "song": "Other", "aligned_start_seconds": 1.0, "aligned_end_seconds": 29.0},
                    {"artist": "Artist", "song": "Third", "aligned_start_seconds": 1.0, "aligned_end_seconds": 29.0},
                    {"artist": "Artist", "song": "Fourth", "aligned_start_seconds": 1.0, "aligned_end_seconds": 29.0},
                ],
            }
        ),
        encoding="utf-8",
    )
    return config_path


def _fixture(tmp: Path) -> Path:
    output = tmp / "outputs with spaces" / "stimulus_selection"
    audio = tmp / "Dataset Root With Spaces" / "MixEvaluation" / "audio" / "Song"
    audio.mkdir(parents=True, exist_ok=True)
    sr = 44100
    t = np.arange(sr * 32, dtype=np.float32) / sr
    samples_a = np.stack([0.1 * np.sin(2 * np.pi * 220 * t), 0.2 * np.sin(2 * np.pi * 330 * t)], axis=1).astype(np.float32)
    samples_b = np.stack([0.15 * np.sin(2 * np.pi * 220 * t), 0.05 * np.sin(2 * np.pi * 440 * t)], axis=1).astype(np.float32)
    wavfile.write(audio / "DU-A.wav", sr, samples_a)
    wavfile.write(audio / "McG-A.wav", sr, samples_b)
    wavfile.write(audio / "MixGenius.wav", sr, samples_a)
    inventory_rows = [
        {
            "artist": "Artist",
            "song": "Song",
            "song_id": "song",
            "mix_id": "mix_a",
            "mixer_id": "DU-A",
            "mixer_institution_code": "DU",
            "institution_name": "Dalarna University",
            "institution_category": "university_or_institution",
            "is_system_generated": "false",
            "valid_for_analysis": "true",
            "exclusion_reason": "",
            "filename": "DU-A.wav",
            "extension": ".wav",
            "source_path": str(audio / "DU-A.wav"),
        },
        {
            "artist": "Artist",
            "song": "Song",
            "song_id": "song",
            "mix_id": "mix_b",
            "mixer_id": "McG-A",
            "mixer_institution_code": "McG",
            "institution_name": "McGill University",
            "institution_category": "university_or_institution",
            "is_system_generated": "false",
            "valid_for_analysis": "true",
            "exclusion_reason": "",
            "filename": "McG-A.wav",
            "extension": ".wav",
            "source_path": str(audio / "McG-A.wav"),
        },
        {
            "artist": "Artist",
            "song": "Song",
            "song_id": "song",
            "mix_id": "mix_auto",
            "mixer_id": "MixGenius",
            "mixer_institution_code": "MG",
            "institution_name": "MixGenius",
            "institution_category": "automated_system",
            "is_system_generated": "true",
            "valid_for_analysis": "true",
            "exclusion_reason": "",
            "filename": "MixGenius.wav",
            "extension": ".wav",
            "source_path": str(audio / "MixGenius.wav"),
        },
    ]
    align_rows = []
    for mix_id, name, lag in [("mix_a", "DU-A.wav", 0.0), ("mix_b", "McG-A.wav", 0.1), ("mix_auto", "MixGenius.wav", 0.0)]:
        align_rows.append(
            {
                "artist": "Artist",
                "song": "Song",
                "mix_id": mix_id,
                "source_path": str(audio / name),
                "reference_mix_id": "mix_a",
                "decoder_backend": "soundfile",
                "original_sample_rate": "44100",
                "decoded_channels": "2",
                "original_duration_seconds": "32",
                "estimated_lag_seconds": str(lag),
                "refined_lag_seconds": str(lag),
                "retained_for_excerpt_selection": "true",
                "exclusion_reason": "",
            }
        )
    _write_csv(output / "mix_inventory.csv", inventory_rows)
    _write_csv(output / "alignment_results.csv", align_rows)
    return _write_config(tmp, output)


class Stage3BFeatureExtractionTests(unittest.TestCase):
    def test_aligned_to_source_timestamp_conversion(self) -> None:
        self.assertEqual(aligned_to_source_interval(10.0, 38.0, -0.25), (9.75, 37.75))

    def test_exact_28_second_extraction_and_stereo_preservation(self) -> None:
        samples = np.ones((44100 * 30, 2), dtype=np.float32)
        excerpt = extract_exact_excerpt(samples, 44100, 1.0)
        self.assertEqual(excerpt.shape, (EXPECTED_SAMPLES, 2))

    def test_automated_mix_exclusion(self) -> None:
        inv = {"mix_id": "mix_auto", "mixer_id": "MixGenius", "mixer_institution_code": "MG", "institution_name": "MixGenius", "filename": "MixGenius.wav", "is_system_generated": "true", "institution_category": "automated_system", "valid_for_analysis": "true"}
        ok, reason = is_retained_human_mix(inv, {"retained_for_excerpt_selection": "true"})
        self.assertFalse(ok)
        self.assertEqual(reason, "automated_or_system_generated")

    def test_bark_column_mapping_and_output_row_count(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage3b paths ") as tmp:
            config = load_config(_fixture(Path(tmp)))
            result = run_feature_extraction(config)
            self.assertEqual(len(result.rows), 2)
            self.assertTrue(all(row["feature_extraction_status"] == "ok" for row in result.rows))
            self.assertEqual(len(BARK_MID_COLUMNS), 24)
            self.assertEqual(len(BARK_SIDE_COLUMNS), 24)
            self.assertEqual(len(RAW_FEATURE_COLUMNS), 81)
            first = result.rows[0]
            self.assertIn("bark_mid_01", first)
            self.assertIn("bark_side_24", first)
            self.assertEqual(first["decoded_sample_count"], str(EXPECTED_SAMPLES))

    def test_deterministic_repeated_extraction(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage3b repeat ") as tmp:
            config = load_config(_fixture(Path(tmp)))
            first = run_feature_extraction(config).rows
            second = run_feature_extraction(config).rows
            self.assertEqual(first, second)

    def test_invalid_configuration_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _fixture(Path(tmp))
            output = Path(tmp) / "outputs with spaces" / "stimulus_selection"
            config = load_config(_write_config(Path(tmp), output, approved=[]))
            with self.assertRaises(ValueError):
                extract_feature_rows(config)

    def test_missing_alignment_row_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            alignment_row_for_mix([{"mix_id": "mix_a"}], "missing_mix")

    def test_nan_inf_rejection(self) -> None:
        with self.assertRaises(ValueError):
            from stimulus_selection.feature_extraction import _features_for_excerpt

            bad = np.full((EXPECTED_SAMPLES, 2), np.nan, dtype=np.float32)
            _features_for_excerpt(bad)


if __name__ == "__main__":
    unittest.main()
