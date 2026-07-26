"""Bark-scale filterbank functions adapted from Diff-MST.

Adapted from Diff-MST ``mst/filter.py`` at commit
3b90ef838272b827c86610cf25b510a23a4147fd.
"""

from __future__ import annotations

import math
import warnings

import torch


def _create_triangular_filterbank(all_freqs: torch.Tensor, f_pts: torch.Tensor) -> torch.Tensor:
    """Create a triangular filter bank.

    Adapted from Diff-MST ``mst/filter.py``.
    """
    f_diff = f_pts[1:] - f_pts[:-1]
    slopes = f_pts.unsqueeze(0) - all_freqs.unsqueeze(1)
    zero = torch.zeros(1, dtype=all_freqs.dtype, device=all_freqs.device)
    down_slopes = (-1.0 * slopes[:, :-2]) / f_diff[:-1]
    up_slopes = slopes[:, 2:] / f_diff[1:]
    return torch.max(zero, torch.min(down_slopes, up_slopes))


def _hz_to_bark(freqs: float, bark_scale: str = "traunmuller") -> float:
    """Convert Hz to Barks.

    Adapted from Diff-MST ``mst/filter.py``.
    """
    if bark_scale not in ["schroeder", "traunmuller", "wang"]:
        raise ValueError('bark_scale should be one of "schroeder", "traunmuller" or "wang".')

    if bark_scale == "wang":
        return 6.0 * math.asinh(freqs / 600.0)
    if bark_scale == "schroeder":
        return 7.0 * math.asinh(freqs / 650.0)

    barks = ((26.81 * freqs) / (1960.0 + freqs)) - 0.53
    if barks < 2:
        barks += 0.15 * (2 - barks)
    elif barks > 20.1:
        barks += 0.22 * (barks - 20.1)
    return barks


def _bark_to_hz(barks: torch.Tensor, bark_scale: str = "traunmuller") -> torch.Tensor:
    """Convert Bark bin numbers to frequencies.

    Adapted from Diff-MST ``mst/filter.py``. The in-place Bark correction is
    intentionally preserved to match the reference implementation.
    """
    if bark_scale not in ["schroeder", "traunmuller", "wang"]:
        raise ValueError('bark_scale should be one of "traunmuller", "schroeder" or "wang".')

    if bark_scale == "wang":
        return 600.0 * torch.sinh(barks / 6.0)
    if bark_scale == "schroeder":
        return 650.0 * torch.sinh(barks / 7.0)

    if any(barks < 2):
        idx = barks < 2
        barks[idx] = (barks[idx] - 0.3) / 0.85
    elif any(barks > 20.1):
        idx = barks > 20.1
        barks[idx] = (barks[idx] + 4.422) / 1.22
    return 1960 * ((barks + 0.53) / (26.28 - barks))


def barkscale_fbanks(
    n_freqs: int,
    f_min: float,
    f_max: float,
    n_barks: int,
    sample_rate: int,
    bark_scale: str = "traunmuller",
) -> torch.Tensor:
    """Create a Bark-scale triangular filter bank.

    Adapted from Diff-MST ``mst/filter.py``.
    """
    all_freqs = torch.linspace(0, sample_rate // 2, n_freqs)
    m_min = _hz_to_bark(f_min, bark_scale=bark_scale)
    m_max = _hz_to_bark(f_max, bark_scale=bark_scale)
    m_pts = torch.linspace(m_min, m_max, n_barks + 2)
    f_pts = _bark_to_hz(m_pts, bark_scale=bark_scale)
    fb = _create_triangular_filterbank(all_freqs, f_pts)

    if (fb.max(dim=0).values == 0.0).any():
        warnings.warn(
            "At least one bark filterbank has all zero values. "
            f"The value for `n_barks` ({n_barks}) may be set too high. "
            f"Or, the value for `n_freqs` ({n_freqs}) may be set too low.",
            stacklevel=2,
        )
    return fb
