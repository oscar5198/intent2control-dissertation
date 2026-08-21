from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import signal


@dataclass(frozen=True)
class DecoderEnvironment:
    ffmpeg_path: str
    ffmpeg_version: str
    ffprobe_path: str
    ffprobe_version: str
    soundfile_available: bool
    librosa_available: bool
    audioread_available: bool


@dataclass(frozen=True)
class DecodedAudio:
    samples: np.ndarray
    sample_rate: int
    channels: int
    duration_seconds: float
    backend: str


def _version(exe: str | None) -> str:
    if not exe:
        return "unavailable"
    try:
        completed = subprocess.run([exe, "-version"], check=False, capture_output=True, text=True, timeout=10)
        first = (completed.stdout or completed.stderr).splitlines()[0]
        return first.strip() if first else "version_unknown"
    except Exception as exc:
        return f"version_error: {exc}"


def detect_decoder_environment() -> DecoderEnvironment:
    ffmpeg = shutil.which("ffmpeg") or ""
    ffprobe = shutil.which("ffprobe") or ""
    try:
        import soundfile  # noqa: F401
        soundfile_available = True
    except Exception:
        soundfile_available = False
    try:
        import librosa  # noqa: F401
        librosa_available = True
    except Exception:
        librosa_available = False
    try:
        import audioread  # noqa: F401
        audioread_available = True
    except Exception:
        audioread_available = False
    return DecoderEnvironment(
        ffmpeg_path=ffmpeg,
        ffmpeg_version=_version(ffmpeg),
        ffprobe_path=ffprobe,
        ffprobe_version=_version(ffprobe),
        soundfile_available=soundfile_available,
        librosa_available=librosa_available,
        audioread_available=audioread_available,
    )


def _decode_ffmpeg(path: Path) -> DecodedAudio:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("ffmpeg_or_ffprobe_unavailable")
    probe = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate,channels", "-show_entries", "format=duration", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    meta = json.loads(probe.stdout)
    stream = meta.get("streams", [{}])[0]
    sample_rate = int(stream.get("sample_rate") or 44100)
    channels = int(stream.get("channels") or 2)
    decoded = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(path), "-f", "f32le", "-acodec", "pcm_f32le", "-"],
        check=True,
        capture_output=True,
        timeout=120,
    )
    data = np.frombuffer(decoded.stdout, dtype=np.float32)
    if channels > 1:
        data = data[: data.size - (data.size % channels)].reshape(-1, channels)
    else:
        data = data.reshape(-1, 1)
    return DecodedAudio(data, sample_rate, channels, data.shape[0] / sample_rate, "ffmpeg")


def _decode_soundfile(path: Path) -> DecodedAudio:
    import soundfile as sf

    info = sf.info(str(path))
    data, sample_rate = sf.read(str(path), always_2d=True, dtype="float32")
    channels = int(data.shape[1]) if data.ndim == 2 else 1
    duration = float(getattr(info, "duration", 0.0) or (data.shape[0] / sample_rate))
    return DecodedAudio(np.asarray(data, dtype=np.float32), int(sample_rate), channels, duration, "soundfile")


def _decode_librosa_or_audioread(path: Path) -> DecodedAudio:
    try:
        import librosa

        data, sample_rate = librosa.load(str(path), sr=None, mono=False)
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        else:
            data = data.T
        return DecodedAudio(data.astype(np.float32), int(sample_rate), int(data.shape[1]), data.shape[0] / sample_rate, "librosa")
    except Exception as librosa_exc:
        try:
            import audioread
        except Exception as audioread_import_exc:
            raise RuntimeError(f"librosa_failed={librosa_exc}; audioread_unavailable={audioread_import_exc}") from librosa_exc
        chunks = []
        sample_rate = 0
        channels = 0
        try:
            with audioread.audio_open(str(path)) as handle:
                sample_rate = int(handle.samplerate)
                channels = int(handle.channels)
                for raw in handle:
                    chunk = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
                    chunks.append(chunk)
            data = np.concatenate(chunks) if chunks else np.empty(0, dtype=np.float32)
            if channels > 1:
                data = data[: data.size - (data.size % channels)].reshape(-1, channels)
            else:
                data = data.reshape(-1, 1)
            return DecodedAudio(data, sample_rate, channels, data.shape[0] / sample_rate, "audioread")
        except Exception as exc:
            raise RuntimeError(f"librosa_failed={librosa_exc}; audioread_failed={exc}") from exc


def decode_audio(path: Path) -> DecodedAudio:
    errors: list[str] = []
    for backend, func in (("ffmpeg", _decode_ffmpeg), ("soundfile", _decode_soundfile), ("librosa_audioread", _decode_librosa_or_audioread)):
        try:
            decoded = func(path)
            if decoded.samples.size == 0:
                raise RuntimeError("decoded_empty_audio")
            if not np.isfinite(decoded.samples).all():
                raise RuntimeError("decoded_nan_or_inf")
            return decoded
        except Exception as exc:
            errors.append(f"{backend}: {exc}")
    raise RuntimeError("No audio decoder worked for " + str(path) + "; " + " | ".join(errors))


def ensure_sample_rate(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if int(source_rate) == int(target_rate):
        return samples.astype(np.float32, copy=False)
    gcd = int(np.gcd(source_rate, target_rate))
    up = target_rate // gcd
    down = source_rate // gcd
    return signal.resample_poly(samples, up, down, axis=0).astype(np.float32)


def write_wav(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    from scipy.io import wavfile

    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(samples, -1.0, 1.0)
    wavfile.write(path, int(sample_rate), (clipped * 32767.0).astype(np.int16))
