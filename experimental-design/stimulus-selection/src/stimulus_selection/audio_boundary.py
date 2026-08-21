from __future__ import annotations

"""Shared boundary processing for regenerated stimulus excerpts."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BoundaryFadeConfig:
    fade_in_ms: float = 5.0
    fade_out_ms: float = 5.0
    fade_shape: str = "half_cosine"
    target_sample_rate: int = 44100
    exact_duration_seconds: float = 28.0

    @property
    def fade_in_samples(self) -> int:
        return int(round((self.fade_in_ms / 1000.0) * self.target_sample_rate))

    @property
    def fade_out_samples(self) -> int:
        return int(round((self.fade_out_ms / 1000.0) * self.target_sample_rate))


def half_cosine_fade(length: int, *, fade_in: bool) -> np.ndarray:
    if length < 0:
        raise ValueError("fade length must be non-negative")
    if length == 0:
        return np.asarray([], dtype=np.float32)
    phase = np.linspace(0.0, np.pi, length, endpoint=True, dtype=np.float64)
    if fade_in:
        curve = 0.5 - 0.5 * np.cos(phase)
    else:
        curve = 0.5 + 0.5 * np.cos(phase)
    return curve.astype(np.float32)


def apply_inaudible_boundary_fades(
    audio: np.ndarray,
    sample_rate: int,
    fade_in_ms: float = 5.0,
    fade_out_ms: float = 5.0,
    shape: str = "half_cosine",
) -> np.ndarray:
    """Apply identical short anti-click fades to an excerpt boundary."""
    if audio.ndim != 2:
        raise ValueError("audio must be a 2D channels-last array")
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if shape not in {"half_cosine", "equal_power"}:
        raise ValueError(f"unsupported fade shape: {shape}")
    fade_in = int(round((fade_in_ms / 1000.0) * sample_rate))
    fade_out = int(round((fade_out_ms / 1000.0) * sample_rate))
    if fade_in < 0 or fade_out < 0:
        raise ValueError("fade durations must be non-negative")
    if max(fade_in_ms, fade_out_ms) > 10.0:
        raise ValueError("review excerpt fades must not exceed 10 ms")
    if fade_in + fade_out > audio.shape[0]:
        raise ValueError("fade durations exceed audio length")

    out = audio.astype(np.float32, copy=True)
    if fade_in:
        out[:fade_in] *= half_cosine_fade(fade_in, fade_in=True)[:, None]
    if fade_out:
        out[-fade_out:] *= half_cosine_fade(fade_out, fade_in=False)[:, None]
    return out
