from __future__ import annotations

import hashlib
import math
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.io import wavfile


@dataclass(frozen=True)
class ProbeResult:
    readable: bool
    contains_nan_or_inf: str
    peak_amplitude: str
    preview_rms: str
    near_silence_detected: bool
    clipping_or_near_clipping_detected: bool
    validation_notes: str


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wav_preview(path: Path, max_seconds: float = 30.0) -> tuple[np.ndarray, int]:
    try:
        sample_rate, data = wavfile.read(path)
        max_frames = int(sample_rate * max_seconds)
        data = data[:max_frames]
        if np.issubdtype(data.dtype, np.integer):
            scale = float(max(abs(np.iinfo(data.dtype).min), np.iinfo(data.dtype).max))
            data = data.astype(np.float32) / scale
        else:
            data = data.astype(np.float32)
        return data, int(sample_rate)
    except Exception:
        with wave.open(str(path), "rb") as handle:
            sample_rate = handle.getframerate()
            channels = handle.getnchannels()
            sample_width = handle.getsampwidth()
            frames = min(handle.getnframes(), int(sample_rate * max_seconds))
            raw = handle.readframes(frames)
        if sample_width == 2:
            data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        elif sample_width == 3:
            bytes_ = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
            signed = (
                bytes_[:, 0].astype(np.int32)
                | (bytes_[:, 1].astype(np.int32) << 8)
                | (bytes_[:, 2].astype(np.int32) << 16)
            )
            signed = np.where(signed & 0x800000, signed - 0x1000000, signed)
            data = signed.astype(np.float32) / 8388608.0
        elif sample_width == 4:
            data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
        else:
            raise ValueError(f"Unsupported WAV sample width: {sample_width}")
        if channels > 1:
            data = data.reshape(-1, channels)
        return data, int(sample_rate)


def probe_audio(path: Path, extension: str, decode_status: str = "") -> ProbeResult:
    if not path.exists():
        return ProbeResult(False, "", "", "", False, False, "file_missing")

    extension = extension.lower()
    if extension == ".wav":
        try:
            data, _ = _wav_preview(path)
            finite = bool(np.isfinite(data).all())
            peak = float(np.nanmax(np.abs(data))) if data.size else 0.0
            rms = float(math.sqrt(float(np.nanmean(data**2)))) if data.size else 0.0
            notes = "sample_preview_ok"
            return ProbeResult(
                readable=True,
                contains_nan_or_inf=str(not finite).lower(),
                peak_amplitude=f"{peak:.8g}",
                preview_rms=f"{rms:.8g}",
                near_silence_detected=rms < 1e-5,
                clipping_or_near_clipping_detected=peak >= 0.999,
                validation_notes=notes,
            )
        except Exception as exc:
            return ProbeResult(False, "", "", "", False, False, f"hard_decode_failure: {exc}")

    if extension == ".mp3":
        if decode_status == "ok":
            try:
                import torch
                import torchaudio

                info = torchaudio.info(str(path))
                frames = min(int(info.sample_rate * 30), int(info.num_frames or info.sample_rate * 30))
                waveform, _ = torchaudio.load(str(path), frame_offset=0, num_frames=frames)
                finite = bool(torch.isfinite(waveform).all().item())
                peak = float(torch.max(torch.abs(waveform)).item()) if waveform.numel() else 0.0
                rms = float(torch.sqrt(torch.mean(waveform**2)).item()) if waveform.numel() else 0.0
                notes = "metadata_decode_ok; sample_preview_ok"
                if peak > 1.0:
                    notes += "; mp3_decoder_peak_overshoot_possible"
                return ProbeResult(
                    readable=True,
                    contains_nan_or_inf=str(not finite).lower(),
                    peak_amplitude=f"{peak:.8g}",
                    preview_rms=f"{rms:.8g}",
                    near_silence_detected=rms < 1e-5,
                    clipping_or_near_clipping_detected=peak >= 0.999,
                    validation_notes=notes,
                )
            except Exception as exc:
                return ProbeResult(
                    readable=True,
                    contains_nan_or_inf="unknown",
                    peak_amplitude="",
                    preview_rms="",
                    near_silence_detected=False,
                    clipping_or_near_clipping_detected=False,
                    validation_notes=f"metadata_decode_ok; sample_preview_failed: {exc}",
                )
        return ProbeResult(False, "", "", "", False, False, f"metadata_decode_status={decode_status or 'unknown'}")

    return ProbeResult(
        readable=decode_status == "ok",
        contains_nan_or_inf="unknown",
        peak_amplitude="",
        preview_rms="",
        near_silence_detected=False,
        clipping_or_near_clipping_detected=False,
        validation_notes=f"sample_preview_not_implemented_for_{extension}",
    )


def preview_fingerprint(path: Path, extension: str, duration_seconds: str, sample_rate: str, channels: str) -> str:
    if not path.exists():
        return ""
    if extension.lower() == ".wav":
        try:
            data, _ = _wav_preview(path, max_seconds=5.0)
            if data.ndim > 1:
                data = data.mean(axis=1)
            if data.size == 0:
                return "wav-empty"
            bins = np.linspace(0, data.size, num=33, dtype=int)
            values = []
            for start, end in zip(bins[:-1], bins[1:]):
                segment = data[start:end]
                values.append(float(np.sqrt(np.mean(segment**2))) if segment.size else 0.0)
            quantized = ",".join(f"{round(v, 5):.5f}" for v in values)
            return hashlib.sha1(quantized.encode("ascii")).hexdigest()
        except Exception:
            pass
    if extension.lower() == ".mp3":
        try:
            import torch
            import torchaudio

            info = torchaudio.info(str(path))
            frames = min(int(info.sample_rate * 5), int(info.num_frames or info.sample_rate * 5))
            waveform, _ = torchaudio.load(str(path), frame_offset=0, num_frames=frames)
            if waveform.ndim > 1:
                waveform = waveform.mean(dim=0)
            if waveform.numel() == 0:
                return "mp3-empty"
            chunk_count = 32
            values = []
            for segment in torch.tensor_split(waveform, chunk_count):
                values.append(float(torch.sqrt(torch.mean(segment**2)).item()) if segment.numel() else 0.0)
            quantized = ",".join(f"{round(v, 5):.5f}" for v in values)
            return hashlib.sha1(quantized.encode("ascii")).hexdigest()
        except Exception:
            pass
    return f"{extension}|{duration_seconds}|{sample_rate}|{channels}|{path.stat().st_size}"
