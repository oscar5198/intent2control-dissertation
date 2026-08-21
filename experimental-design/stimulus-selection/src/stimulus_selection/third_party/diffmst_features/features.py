"""Diff-MST audio-production feature transforms for dissertation Stage 3.

The feature math is adapted from Diff-MST ``mst/loss.py`` at commit
3b90ef838272b827c86610cf25b510a23a4147fd. This wrapper enforces the
dissertation input contract ``(batch, channels, samples)`` and rejects
non-finite tensors before applying the adapted transforms.
"""

from __future__ import annotations

import torch

from stimulus_selection.third_party.diffmst_features.bark_filterbank import barkscale_fbanks


def _validate_audio_tensor(x: torch.Tensor, *, stereo: bool = False) -> None:
    if not isinstance(x, torch.Tensor):
        raise TypeError("Expected a torch.Tensor with shape (batch, channels, samples).")
    if x.ndim != 3:
        raise ValueError(f"Expected input shape (batch, channels, samples); got {tuple(x.shape)}.")
    if x.shape[0] < 1 or x.shape[1] < 1 or x.shape[2] < 1:
        raise ValueError(f"Input dimensions must be non-empty; got {tuple(x.shape)}.")
    if stereo and x.shape[1] != 2:
        raise ValueError(f"Expected exactly two channels for this stereo feature; got {x.shape[1]}.")
    if not torch.is_floating_point(x):
        raise TypeError("Expected a floating-point tensor.")
    if not torch.isfinite(x).all():
        raise ValueError("Input contains NaN or Inf values.")


def compute_rms(x: torch.Tensor, **kwargs) -> torch.Tensor:
    """Compute root mean square energy.

    Input shape: ``(batch, channels, samples)``.
    Output shape: ``(batch, channels)``.

    Adapted from Diff-MST ``mst/loss.py::compute_rms``.
    """
    _validate_audio_tensor(x)
    return torch.sqrt(torch.mean(x**2, dim=-1).clamp(min=1e-8))


def compute_crest_factor(x: torch.Tensor, **kwargs) -> torch.Tensor:
    """Compute peak-to-RMS ratio in dB independently per channel.

    Input shape: ``(batch, channels, samples)``.
    Output shape: ``(batch, channels)``.

    Adapted from Diff-MST ``mst/loss.py::compute_crest_factor``.
    """
    _validate_audio_tensor(x)
    num = torch.max(torch.abs(x), dim=-1)[0]
    den = compute_rms(x).clamp(min=1e-8)
    return 20 * torch.log10((num / den).clamp(min=1e-8))


def compute_stereo_width(x: torch.Tensor, **kwargs) -> torch.Tensor:
    """Compute difference-signal energy divided by sum-signal energy.

    Input shape: ``(batch, 2, samples)``.
    Output shape: ``(batch,)``.

    Adapted from Diff-MST ``mst/loss.py::compute_stereo_width``.
    """
    _validate_audio_tensor(x, stereo=True)
    x_sum = x[:, 0, :] + x[:, 1, :]
    x_diff = x[:, 0, :] - x[:, 1, :]
    sum_energy = torch.mean(x_sum**2, dim=-1)
    diff_energy = torch.mean(x_diff**2, dim=-1)
    return diff_energy / sum_energy.clamp(min=1e-8)


def compute_stereo_imbalance(x: torch.Tensor, **kwargs) -> torch.Tensor:
    """Compute right-minus-left energy divided by total stereo energy.

    Input shape: ``(batch, 2, samples)``.
    Output shape: ``(batch,)``.

    Adapted from Diff-MST ``mst/loss.py::compute_stereo_imbalance``.
    """
    _validate_audio_tensor(x, stereo=True)
    left_energy = torch.mean(x[:, 0, :] ** 2, dim=-1)
    right_energy = torch.mean(x[:, 1, :] ** 2, dim=-1)
    return (right_energy - left_energy) / (right_energy + left_energy).clamp(min=1e-8)


def compute_barkspectrum(
    x: torch.Tensor,
    fft_size: int = 32768,
    n_bands: int = 24,
    sample_rate: int = 44100,
    f_min: float = 20.0,
    f_max: float = 20000.0,
    mode: str = "mid-side",
    **kwargs,
) -> torch.Tensor:
    """Compute the Diff-MST Bark-spectrum representation.

    Input shape: ``(batch, channels, samples)``. ``stereo`` and ``mid-side``
    modes require exactly two channels.

    Output shapes with default ``n_bands=24``:
    ``mono`` -> ``(batch, 24, 1)``;
    ``stereo`` -> ``(batch, 24, 2)``;
    ``mid-side`` -> ``(batch, 24, 2)``.

    Adapted from Diff-MST ``mst/loss.py::compute_barkspectrum``.
    """
    if mode not in {"mono", "stereo", "mid-side"}:
        raise ValueError(f"Invalid mode {mode}")
    _validate_audio_tensor(x, stereo=(mode in {"stereo", "mid-side"}))

    fb = barkscale_fbanks((fft_size // 2) + 1, f_min, f_max, n_bands, sample_rate)
    fb = fb.unsqueeze(0).type_as(x)
    fb = fb.permute(0, 2, 1)

    if mode == "mono":
        signals = [x.mean(dim=1)]
    elif mode == "stereo":
        signals = [x[:, 0, :], x[:, 1, :]]
    else:
        x_mid = x[:, 0, :] + x[:, 1, :]
        x_side = x[:, 0, :] - x[:, 1, :]
        signals = [x_mid, x_side]

    outputs = []
    for signal in signals:
        spectrum = torch.stft(
            signal,
            n_fft=fft_size,
            hop_length=fft_size // 4,
            return_complex=True,
            window=torch.hann_window(fft_size).to(x.device),
        )
        spectrum = torch.abs(spectrum)
        spectrum = torch.mean(spectrum, dim=-1, keepdim=True)
        spectrum = torch.matmul(fb, spectrum)
        outputs.append(torch.log(spectrum + 1e-8))
    return torch.cat(outputs, dim=-1)
