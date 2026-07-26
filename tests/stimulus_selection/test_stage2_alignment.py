from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from stimulus_selection.alignment import MixAudio, _estimate_lag, _is_human_primary, _mono, _select_candidates
from stimulus_selection.audio_decode import DecodedAudio, decode_audio, ensure_sample_rate
from stimulus_selection.config import AlignmentConfig, ExcerptSelectionConfig, SelectionConfig


def _config(tmp_path: Path) -> SelectionConfig:
    return SelectionConfig(
        dataset_root=tmp_path,
        relationship_tables_root=tmp_path,
        public_audio_root=tmp_path,
        output_root=tmp_path / "outputs with spaces",
        target_sample_rate=44100,
        minimum_duration_seconds=1.0,
        require_stereo=True,
        allowed_extensions=(".mp3", ".wav"),
        institution_system_codes=("MG", "AUTO", "Robot"),
        primary_candidate_songs=({"artist": "A", "song": "S"},),
        approved_excerpts=(),
        target_excerpt_seconds=2.0,
        fade_seconds=0.1,
        alignment=AlignmentConfig("mono", 11025, 2.0, 0.70, True, True, True),
        excerpt_selection=ExcerptSelectionConfig(3, 0.25, 0.5, 0.5, 0.50, True),
        analysis_excerpt_root=tmp_path / "analysis excerpts",
        preview_excerpt_root=tmp_path / "preview excerpts",
    )


def _rep(x: np.ndarray, sr: int = 1000) -> np.ndarray:
    frame = 80
    hop = 20
    vals = []
    for i in range(0, len(x) - frame, hop):
        vals.append(float(np.sqrt(np.mean(x[i:i+frame] ** 2))))
    vals = np.asarray(vals, dtype=np.float32)
    vals -= vals.mean()
    vals /= vals.std() + 1e-9
    return vals


class Stage2AlignmentTests(unittest.TestCase):
    def test_known_artificial_time_offset(self) -> None:
        sr = 1000
        t = np.arange(0, 6, 1 / sr)
        ref = signal.chirp(t, 80, t[-1], 220).astype(np.float32) * (signal.square(2 * np.pi * 2 * t) > 0)
        offset = 0.42
        pad = np.zeros(int(offset * sr), dtype=np.float32)
        target = np.concatenate([pad, ref])
        lag, score, _, _, _ = _estimate_lag(_rep(ref), _rep(target), 0.02, 1.0)
        self.assertAlmostEqual(lag, offset, delta=0.05)
        self.assertGreater(score, 0.8)

    def test_alignment_differently_eqd_and_compressed_synthetic_signals(self) -> None:
        sr = 1000
        rng = np.random.default_rng(4)
        ref = rng.normal(0, 0.15, sr * 8).astype(np.float32)
        ref[1000:1500] += signal.windows.hann(500).astype(np.float32)
        ref[3500:3900] -= signal.windows.hann(400).astype(np.float32) * 0.8
        sos = signal.butter(3, 120, "lowpass", fs=sr, output="sos")
        processed = np.tanh(signal.sosfilt(sos, ref) * 3.0).astype(np.float32)
        target = np.concatenate([np.zeros(310, dtype=np.float32), processed])
        lag, score, _, _, _ = _estimate_lag(_rep(ref), _rep(target), 0.02, 1.0)
        self.assertAlmostEqual(lag, 0.31, delta=0.08)
        self.assertGreater(score, 0.45)

    def test_stereo_to_mono_analysis(self) -> None:
        stereo = np.array([[1.0, -1.0], [0.5, 0.25]], dtype=np.float32)
        mono = _mono(stereo)
        np.testing.assert_allclose(mono, np.array([0.0, 0.375], dtype=np.float32))

    def test_common_overlap_calculation_with_offsets(self) -> None:
        mixes = [
            DecodedAudio(np.zeros((1000, 2), np.float32), 100, 2, 10.0, "synthetic"),
            DecodedAudio(np.zeros((900, 2), np.float32), 100, 2, 9.0, "synthetic"),
        ]
        lags = [0.0, 0.75]
        starts = [-lag for lag in lags]
        ends = [mix.duration_seconds - lag for mix, lag in zip(mixes, lags)]
        self.assertAlmostEqual(max(starts), 0.0)
        self.assertAlmostEqual(min(ends), 8.25)

    def test_candidate_window_duration_and_non_overlap_separation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _config(Path(tmp))
            sr = 100
            t = np.linspace(0, 10, sr * 10, endpoint=False)
            audio = np.stack([0.4 * np.sin(2 * np.pi * 5 * t), 0.3 * np.sin(2 * np.pi * 7 * t)], axis=1).astype(np.float32)
            decoded = DecodedAudio(audio, sr, 2, 10.0, "synthetic")
            mix = MixAudio({"artist": "A", "song": "S", "mix_id": "m1", "mixer_institution_code": "DU", "source_path": "x"}, decoded, audio.mean(axis=1), audio.mean(axis=1), np.ones(10))
            candidates = _select_candidates(cfg, [mix], 0.0, 10.0)
            self.assertGreaterEqual(len(candidates), 2)
            for cand in candidates:
                self.assertAlmostEqual(cand["end"] - cand["start"], 2.0, places=6)
            starts = sorted(c["start"] for c in candidates)
            self.assertTrue(all((b - a) >= 1.9 for a, b in zip(starts, starts[1:])))

    def test_low_confidence_alignment_handling_and_system_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _config(Path(tmp))
            row = {"mix_id": "mix_mg", "mixer_id": "MixGenius", "mixer_institution_code": "MG", "institution_name": "MixGenius", "filename": "AUTO.mp3", "valid_for_analysis": "true", "extension": ".mp3", "is_system_generated": "false", "institution_category": "automated_system"}
            ok, reason = _is_human_primary(row, cfg)
            self.assertFalse(ok)
            self.assertEqual(reason, "automated_or_system_generated")
            a = np.random.default_rng(1).normal(size=100).astype(np.float32)
            b = np.random.default_rng(2).normal(size=100).astype(np.float32)
            _, score, _, _, _ = _estimate_lag(a, b, 0.02, 0.5)
            self.assertLess(score, 0.35)

    def test_windows_paths_containing_spaces_decode_wav(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage 2 spaces ") as tmp:
            path = Path(tmp) / "audio file.wav"
            samples = np.ones((1000, 2), dtype=np.float32) * 0.1
            wavfile.write(path, 1000, samples)
            decoded = decode_audio(path)
            self.assertEqual(decoded.channels, 2)
            self.assertEqual(decoded.sample_rate, 1000)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe not available")
    def test_mp3_decoding_through_ffmpeg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "tone.wav"
            mp3 = Path(tmp) / "tone.mp3"
            sr = 44100
            t = np.linspace(0, 1, sr, endpoint=False)
            samples = np.stack([0.2 * np.sin(2 * np.pi * 440 * t), 0.2 * np.sin(2 * np.pi * 220 * t)], axis=1).astype(np.float32)
            wavfile.write(wav, sr, samples)
            subprocess.run([shutil.which("ffmpeg"), "-y", "-v", "error", "-i", str(wav), str(mp3)], check=True)
            decoded = decode_audio(mp3)
            self.assertEqual(decoded.backend, "ffmpeg")
            self.assertEqual(decoded.channels, 2)

    def test_resample_preserves_channel_shape(self) -> None:
        x = np.ones((100, 2), dtype=np.float32)
        y = ensure_sample_rate(x, 1000, 500)
        self.assertEqual(y.shape[1], 2)


if __name__ == "__main__":
    unittest.main()

