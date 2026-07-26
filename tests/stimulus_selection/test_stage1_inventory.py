from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import numpy as np
import yaml
from scipy.io import wavfile

from stimulus_selection.audio_inventory import build_inventory
from stimulus_selection.audio_probe import file_sha256, probe_audio
from stimulus_selection.config import load_config
from stimulus_selection.metadata import build_joined_records, classify_institution
from stimulus_selection.shortlist import build_song_summary


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_wav(path: Path, samples: np.ndarray, sample_rate: int = 44100) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(path, sample_rate, samples.astype(np.float32))


def _fixture_config(tmp_path: Path) -> Path:
    dataset_root = tmp_path / "Dataset Root With Spaces"
    rel_root = dataset_root / "mix_evaluation_relationship_tables"
    audio_root = dataset_root / "MixEvaluation" / "audio"
    data = rel_root / "data"
    _write_csv(
        data / "songs.csv",
        [
            {
                "song_id": "song_one",
                "legacy_song_id": "SongOne",
                "title": "Song One",
                "artist": "Artist A",
                "license_label": "CC",
                "source_name": "",
                "source_url": "",
                "metadata_status": "documented",
                "evaluation_count": "0",
                "mix_count": "5",
                "audio_file_count": "5",
            },
            {
                "song_id": "song_uncertain",
                "legacy_song_id": "Uncertain",
                "title": "Uncertain Song",
                "artist": "Artist B",
                "license_label": "",
                "source_name": "",
                "source_url": "",
                "metadata_status": "observed",
                "evaluation_count": "0",
                "mix_count": "1",
                "audio_file_count": "1",
            },
        ],
    )
    _write_csv(
        data / "mixes.csv",
        [
            {
                "mix_id": "mix_du",
                "song_id": "song_one",
                "legacy_song_id": "SongOne",
                "legacy_mix_code": "DU-A",
                "mixer_institution_code": "DU",
                "mixer_institution_name": "Dalarna University",
                "mix_type": "human_or_reference",
                "evaluation_count": "1",
                "comment_count": "0",
                "audio_file_count": "1",
                "audio_availability": "available",
            },
            {
                "mix_id": "mix_mcg",
                "song_id": "song_one",
                "legacy_song_id": "SongOne",
                "legacy_mix_code": "McG-A",
                "mixer_institution_code": "McG",
                "mixer_institution_name": "McGill University",
                "mix_type": "human_or_reference",
                "evaluation_count": "1",
                "comment_count": "0",
                "audio_file_count": "1",
                "audio_availability": "available",
            },
            {
                "mix_id": "mix_pxl",
                "song_id": "song_one",
                "legacy_song_id": "SongOne",
                "legacy_mix_code": "PXL-A",
                "mixer_institution_code": "PXL",
                "mixer_institution_name": "PXL University College",
                "mix_type": "human_or_reference",
                "evaluation_count": "1",
                "comment_count": "0",
                "audio_file_count": "1",
                "audio_availability": "available",
            },
            {
                "mix_id": "mix_mg",
                "song_id": "song_one",
                "legacy_song_id": "SongOne",
                "legacy_mix_code": "Mixgenius",
                "mixer_institution_code": "MG",
                "mixer_institution_name": "MixGenius",
                "mix_type": "human_or_reference",
                "evaluation_count": "0",
                "comment_count": "0",
                "audio_file_count": "1",
                "audio_availability": "available",
            },
            {
                "mix_id": "mix_unknown",
                "song_id": "song_uncertain",
                "legacy_song_id": "Uncertain",
                "legacy_mix_code": "X",
                "mixer_institution_code": "",
                "mixer_institution_name": "",
                "mix_type": "",
                "evaluation_count": "0",
                "comment_count": "0",
                "audio_file_count": "1",
                "audio_availability": "available",
            },
        ],
    )

    tone = np.stack([np.sin(np.linspace(0, 100, 44100)), np.sin(np.linspace(0, 100, 44100))], axis=1)
    mono = np.sin(np.linspace(0, 100, 44100))
    silence = np.zeros((44100, 2))
    clipped = np.ones((44100, 2))
    _write_wav(audio_root / "SongOne" / "DU-A.wav", tone)
    _write_wav(audio_root / "SongOne" / "McG-A.wav", tone.copy())
    _write_wav(audio_root / "SongOne" / "PXL-A.wav", clipped)
    _write_wav(audio_root / "SongOne" / "Mixgenius.wav", silence)
    _write_wav(audio_root / "Uncertain" / "X.wav", mono)
    (audio_root / "SongOne" / "bad.wav").write_bytes(b"not audio")

    audio_rows = []
    for mix_id, legacy_song, code, rel, ch in [
        ("mix_du", "SongOne", "DU-A", "audio/SongOne/DU-A.wav", "2"),
        ("mix_mcg", "SongOne", "McG-A", "audio/SongOne/McG-A.wav", "2"),
        ("mix_pxl", "SongOne", "PXL-A", "audio/SongOne/PXL-A.wav", "2"),
        ("mix_mg", "SongOne", "Mixgenius", "audio/SongOne/Mixgenius.wav", "2"),
        ("mix_unknown", "Uncertain", "X", "audio/Uncertain/X.wav", "1"),
    ]:
        p = dataset_root / "MixEvaluation" / rel
        audio_rows.append(
            {
                "audio_file_id": f"audio_{mix_id}",
                "song_id": "song_one" if legacy_song == "SongOne" else "song_uncertain",
                "mix_id": mix_id,
                "legacy_song_id": legacy_song,
                "legacy_mix_code": code,
                "relative_path": rel,
                "file_extension": "wav",
                "file_size_bytes": str(p.stat().st_size),
                "channels": ch,
                "sample_rate_hz": "44100",
                "codec": ".wav",
                "duration_seconds": "1.0",
                "bitrate_bps": "",
                "decode_status": "ok",
            }
        )
    audio_rows.append(
        {
            "audio_file_id": "audio_bad",
            "song_id": "song_one",
            "mix_id": "mix_du",
            "legacy_song_id": "SongOne",
            "legacy_mix_code": "bad",
            "relative_path": "audio/SongOne/bad.wav",
            "file_extension": "wav",
            "file_size_bytes": str((audio_root / "SongOne" / "bad.wav").stat().st_size),
            "channels": "2",
            "sample_rate_hz": "44100",
            "codec": ".wav",
            "duration_seconds": "1.0",
            "bitrate_bps": "",
            "decode_status": "ok",
        }
    )
    _write_csv(data / "audio_files.csv", audio_rows)

    config_path = tmp_path / "selection.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "dataset_root": str(dataset_root).replace("\\", "/"),
                "relationship_tables_root": str(rel_root).replace("\\", "/"),
                "public_audio_root": str(audio_root).replace("\\", "/"),
                "output_root": str(tmp_path / "outputs").replace("\\", "/"),
                "target_sample_rate": 44100,
                "minimum_duration_seconds": 0.5,
                "require_stereo": True,
                "allowed_extensions": [".mp3", ".wav"],
                "institution_system_codes": ["MG", "AUTO", "Robot"],
                "primary_candidate_songs": [{"artist": "Artist A", "song": "Song One"}],
            }
        ),
        encoding="utf-8",
    )
    return config_path


class Stage1InventoryTests(unittest.TestCase):
    def test_canonical_metadata_join_and_windows_paths_with_spaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(_fixture_config(Path(tmp)))
            rows = build_joined_records(config)
            du = next(row for row in rows if row["mixer_id"] == "DU-A")
            self.assertEqual(du["artist"], "Artist A")
            self.assertEqual(du["institution_name"], "Dalarna University")
            self.assertTrue(Path(du["source_path"]).exists())
            self.assertIn("Dataset Root With Spaces", du["source_path"])

    def test_institution_and_system_classification(self) -> None:
        self.assertEqual(classify_institution("MG", ("MG", "AUTO", "Robot")), ("automated_system", True))
        self.assertEqual(classify_institution("DU", ("MG", "AUTO", "Robot")), ("university_or_institution", False))
        self.assertEqual(classify_institution("", ("MG", "AUTO", "Robot")), ("unknown", False))

    def test_audio_probe_stereo_mono_silent_clipped_unreadable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stereo = tmp_path / "stereo.wav"
            mono = tmp_path / "mono.wav"
            silent = tmp_path / "silent.wav"
            clipped = tmp_path / "clipped.wav"
            bad = tmp_path / "bad.wav"
            _write_wav(stereo, np.ones((1000, 2)) * 0.1)
            _write_wav(mono, np.ones(1000) * 0.1)
            _write_wav(silent, np.zeros((1000, 2)))
            _write_wav(clipped, np.ones((1000, 2)))
            bad.write_bytes(b"bad")
            self.assertTrue(probe_audio(stereo, ".wav").readable)
            self.assertTrue(probe_audio(mono, ".wav").readable)
            self.assertTrue(probe_audio(silent, ".wav").near_silence_detected)
            self.assertTrue(probe_audio(clipped, ".wav").clipping_or_near_clipping_detected)
            self.assertFalse(probe_audio(bad, ".wav").readable)

    def test_inventory_flags_duplicates_uncertain_and_mg_not_real(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(_fixture_config(Path(tmp)))
            rows = build_inventory(config)
            summary = build_song_summary(rows, config)
            song_one = next(row for row in summary if row["song"] == "Song One")
            mg_row = next(row for row in rows if row["mixer_id"] == "Mixgenius")
            unknown_row = next(row for row in rows if row["song"] == "Uncertain Song")
            self.assertEqual(mg_row["institution_category"], "automated_system")
            self.assertEqual(mg_row["mix_type"], "automated_mix")
            self.assertEqual(song_one["confident_real_institution_count"], "3")
            self.assertEqual(song_one["human_mix_count"], "3")
            self.assertEqual(song_one["cross_institution_eligible"], "true")
            self.assertEqual(unknown_row["institution_category"], "unknown")
            self.assertIn("not_stereo", unknown_row["exclusion_reason"])
            duplicate_hashes = [row["duplicate_file_hash"] for row in rows if row.get("_exact_duplicate") == "true"]
            self.assertGreaterEqual(len(duplicate_hashes), 2)
            self.assertTrue(all(len(value) == 64 for value in duplicate_hashes))

    def test_exact_duplicate_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            a = tmp_path / "a.bin"
            b = tmp_path / "b.bin"
            a.write_bytes(b"same")
            b.write_bytes(b"same")
            self.assertEqual(file_sha256(a), file_sha256(b))


if __name__ == "__main__":
    unittest.main()

