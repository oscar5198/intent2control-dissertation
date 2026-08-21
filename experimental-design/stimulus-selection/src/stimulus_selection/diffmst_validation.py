from __future__ import annotations

import csv
import importlib.util
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace
from typing import Callable

import numpy as np
import torch

from stimulus_selection.audio_decode import decode_audio, ensure_sample_rate
from stimulus_selection.config import SelectionConfig
from stimulus_selection.output_layout import stage2_previews, stage3_reports, stage3_tables
from stimulus_selection.paths import ensure_output_root
from stimulus_selection.third_party import diffmst_features as vendored


REFERENCE_COMMIT = "3b90ef838272b827c86610cf25b510a23a4147fd"
FEATURES: tuple[tuple[str, str, dict[str, object]], ...] = (
    ("RMS", "compute_rms", {}),
    ("CF", "compute_crest_factor", {}),
    ("SW", "compute_stereo_width", {}),
    ("SI", "compute_stereo_imbalance", {}),
    ("BS", "compute_barkspectrum", {}),
)
CSV_COLUMNS = [
    "test_case",
    "feature",
    "reference_shape",
    "vendored_shape",
    "reference_dtype",
    "vendored_dtype",
    "max_absolute_error",
    "mean_absolute_error",
    "maximum_relative_error",
    "tolerance_absolute",
    "tolerance_relative",
    "finite",
    "passed",
    "notes",
]


@dataclass(frozen=True)
class ValidationResult:
    rows: list[dict[str, str]]
    edge_rows: list[dict[str, str]]
    bark_shapes: dict[str, tuple[int, ...]]
    csv_path: Path
    report_path: Path


def load_reference_loss(reference_root: str | Path) -> ModuleType:
    """Load original Diff-MST feature functions for validation only."""
    root = Path(reference_root).resolve()
    if not (root / "mst" / "loss.py").exists():
        raise FileNotFoundError(f"Diff-MST reference loss.py not found under {root}")

    previous_path = list(os.sys.path)
    stub_names = ("librosa", "mst.fx_encoder", "mst.modules")
    old_modules = {name: os.sys.modules.get(name) for name in ("mst", "mst.loss", "mst.filter", *stub_names)}
    for name in ("mst.loss", "mst.filter", "mst"):
        os.sys.modules.pop(name, None)
    try:
        os.sys.modules.setdefault("librosa", SimpleNamespace(filters=SimpleNamespace(mel=lambda *args, **kwargs: None)))
        os.sys.modules.setdefault("mst.fx_encoder", SimpleNamespace(FXencoder=object))
        os.sys.modules.setdefault("mst.modules", SimpleNamespace(SpectrogramEncoder=object))
        os.sys.path.insert(0, str(root))
        spec = importlib.util.find_spec("mst.loss")
        if spec is None:
            raise ImportError(f"Could not import mst.loss from {root}")
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        os.sys.path[:] = previous_path
        for name in ("mst.loss", "mst.filter", "mst", *stub_names):
            os.sys.modules.pop(name, None)
        for name, module in old_modules.items():
            if module is not None:
                os.sys.modules[name] = module


def deterministic_test_signals(dtype: torch.dtype = torch.float32) -> list[tuple[str, torch.Tensor]]:
    sr = 44100
    seconds = 1.0
    t = torch.arange(int(sr * seconds), dtype=dtype) / sr
    sine_a = torch.sin(2 * torch.pi * 440 * t)
    sine_b = torch.sin(2 * torch.pi * 660 * t)
    rng = torch.Generator(device="cpu").manual_seed(1234)
    noise_l = torch.randn(t.numel(), generator=rng, dtype=dtype) * 0.05
    rng = torch.Generator(device="cpu").manual_seed(1235)
    noise_r = torch.randn(t.numel(), generator=rng, dtype=dtype) * 0.05
    impulse = torch.zeros_like(t)
    impulse[100] = 1.0
    low_noise = torch.randn(t.numel(), generator=torch.Generator().manual_seed(44), dtype=dtype) * 1e-4
    return [
        ("identical_stereo_sine", torch.stack([0.25 * sine_a, 0.25 * sine_a]).unsqueeze(0)),
        ("different_amplitude_stereo_sine", torch.stack([0.10 * sine_a, 0.35 * sine_a]).unsqueeze(0)),
        ("left_only_signal", torch.stack([0.25 * sine_a, torch.zeros_like(sine_a)]).unsqueeze(0)),
        ("correlated_stereo_deterministic_noise", torch.stack([noise_l, noise_l * 0.8]).unsqueeze(0)),
        ("partially_decorrelated_stereo_noise", torch.stack([noise_l, 0.5 * noise_l + 0.5 * noise_r]).unsqueeze(0)),
        ("impulse_plus_low_level_noise", torch.stack([impulse + low_noise, low_noise]).unsqueeze(0)),
    ]


def real_excerpt_signal(config: SelectionConfig) -> tuple[str, torch.Tensor] | None:
    preview_root = stage2_previews(config.output_root)
    candidates = sorted(preview_root.glob("*.wav"))
    if not candidates:
        return None
    decoded = decode_audio(candidates[0])
    samples = ensure_sample_rate(decoded.samples, decoded.sample_rate, config.target_sample_rate)
    if samples.shape[1] == 1:
        samples = np.repeat(samples, 2, axis=1)
    samples = samples[:, :2]
    tensor = torch.from_numpy(samples.T.astype(np.float32, copy=False)).unsqueeze(0)
    return (f"real_stage2_decoded_excerpt:{candidates[0].name}", tensor)


def compare_feature(
    test_case: str,
    feature_label: str,
    reference_func: Callable[..., torch.Tensor],
    vendored_func: Callable[..., torch.Tensor],
    tensor: torch.Tensor,
    kwargs: dict[str, object],
) -> dict[str, str]:
    with torch.no_grad():
        ref = reference_func(tensor.clone(), **kwargs)
        ven = vendored_func(tensor.clone(), **kwargs)
    diff = (ref - ven).detach()
    abs_diff = torch.abs(diff)
    ref_abs = torch.abs(ref.detach())
    rel = abs_diff / torch.clamp(ref_abs, min=1e-8)
    atol = 1e-5 if tensor.dtype == torch.float32 else 1e-8
    rtol = 1e-5 if tensor.dtype == torch.float32 else 1e-8
    finite = bool(torch.isfinite(ref).all() and torch.isfinite(ven).all())
    close = bool(torch.allclose(ref, ven, atol=atol, rtol=rtol, equal_nan=False))
    return {
        "test_case": test_case,
        "feature": feature_label,
        "reference_shape": str(tuple(ref.shape)),
        "vendored_shape": str(tuple(ven.shape)),
        "reference_dtype": str(ref.dtype),
        "vendored_dtype": str(ven.dtype),
        "max_absolute_error": f"{float(abs_diff.max().item()):.12g}",
        "mean_absolute_error": f"{float(abs_diff.mean().item()):.12g}",
        "maximum_relative_error": f"{float(rel.max().item()):.12g}",
        "tolerance_absolute": str(atol),
        "tolerance_relative": str(rtol),
        "finite": str(finite).lower(),
        "passed": str(finite and close and tuple(ref.shape) == tuple(ven.shape) and ref.dtype == ven.dtype).lower(),
        "notes": "",
    }


def edge_case_results() -> list[dict[str, str]]:
    cases = [
        ("silence", torch.zeros(1, 2, 32768, dtype=torch.float32), "finite"),
        ("near_silence", torch.ones(1, 2, 32768, dtype=torch.float32) * 1e-12, "finite"),
        ("zero_energy_sum_signal", torch.stack([torch.ones(32768), -torch.ones(32768)]).unsqueeze(0), "finite"),
        ("mono_input_to_stereo_feature", torch.zeros(1, 1, 4096, dtype=torch.float32), "reject"),
        ("nan_input", torch.full((1, 2, 4096), float("nan")), "reject"),
        ("inf_input", torch.full((1, 2, 4096), float("inf")), "reject"),
        ("very_short_input", torch.zeros(1, 2, 8, dtype=torch.float32), "finite_or_clear_error"),
        ("float64_cpu_input", torch.zeros(1, 2, 32768, dtype=torch.float64), "finite"),
    ]
    rows: list[dict[str, str]] = []
    funcs = {
        "RMS": vendored.compute_rms,
        "CF": vendored.compute_crest_factor,
        "SW": vendored.compute_stereo_width,
        "SI": vendored.compute_stereo_imbalance,
        "BS": vendored.compute_barkspectrum,
    }
    for case, tensor, expectation in cases:
        for label, func in funcs.items():
            feature_expectation = expectation
            if case == "mono_input_to_stereo_feature" and label in {"RMS", "CF"}:
                feature_expectation = "finite"
            try:
                output = func(tensor)
                finite = bool(torch.isfinite(output).all())
                passed = finite if feature_expectation in {"finite", "finite_or_clear_error"} else False
                note = "finite output"
            except (TypeError, ValueError, RuntimeError) as exc:
                finite = False
                passed = feature_expectation in {"reject", "finite_or_clear_error"}
                note = f"raised {type(exc).__name__}: {exc}"
            rows.append({"case": case, "feature": label, "finite": str(finite).lower(), "passed": str(passed).lower(), "notes": note})
    return rows


def bark_output_shapes() -> dict[str, tuple[int, ...]]:
    x = deterministic_test_signals()[0][1]
    return {
        mode: tuple(vendored.compute_barkspectrum(x, mode=mode).shape)
        for mode in ("mono", "stereo", "mid-side")
    }


def run_diffmst_feature_validation(config: SelectionConfig, reference_root: str | Path) -> ValidationResult:
    reference = load_reference_loss(reference_root)
    cases = deterministic_test_signals(torch.float32) + deterministic_test_signals(torch.float64)
    real = real_excerpt_signal(config)
    if real is not None:
        cases.append(real)

    rows: list[dict[str, str]] = []
    for test_case, tensor in cases:
        for label, name, kwargs in FEATURES:
            rows.append(compare_feature(test_case, label, getattr(reference, name), getattr(vendored, name), tensor, kwargs))

    edge_rows = edge_case_results()
    shapes = bark_output_shapes()
    output_root = ensure_output_root(config)
    csv_path = stage3_tables(output_root) / "reference_equivalence_report.csv"
    report_path = stage3_reports(output_root) / "diffmst_feature_validation_report.md"
    write_equivalence_csv(csv_path, rows)
    write_validation_report(report_path, rows, edge_rows, shapes, reference_root)
    return ValidationResult(rows, edge_rows, shapes, csv_path, report_path)


def write_equivalence_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_validation_report(
    path: Path,
    rows: list[dict[str, str]],
    edge_rows: list[dict[str, str]],
    bark_shapes: dict[str, tuple[int, ...]],
    reference_root: str | Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    passed = sum(row["passed"] == "true" for row in rows)
    max_abs = max(float(row["max_absolute_error"]) for row in rows)
    max_rel = max(float(row["maximum_relative_error"]) for row in rows)
    edge_passed = sum(row["passed"] == "true" for row in edge_rows)
    approved = passed == len(rows) and edge_passed == len(edge_rows)
    lines = [
        "# Diff-MST Feature Validation Report",
        "",
        f"- Reference repository: `{reference_root}`",
        "- Source repository: `https://github.com/sai-soum/Diff-MST.git`",
        f"- Source commit: `{REFERENCE_COMMIT}`",
        "- Source paths: `mst/loss.py`, `mst/filter.py`",
        "- Functions copied: `compute_rms`, `compute_crest_factor`, `compute_stereo_width`, `compute_stereo_imbalance`, `compute_barkspectrum`, `barkscale_fbanks`, `_hz_to_bark`, `_bark_to_hz`, `_create_triangular_filterbank`",
        "- Compatibility changes: removed neural-model dependencies; converted imports to package-local paths; added shape and finite-value validation; preserved reference feature defaults for valid tensors.",
        f"- Package versions: Python {platform.python_version()}, PyTorch {torch.__version__}, NumPy {np.__version__}",
        "",
        "## Bark Output Shape",
        "",
    ]
    for mode, shape in bark_shapes.items():
        lines.append(f"- `{mode}`: `{shape}`")
    lines.extend([
        "",
        "## Equivalence Summary",
        "",
        f"- Passed rows: {passed}/{len(rows)}",
        f"- Maximum absolute error: {max_abs:.12g}",
        f"- Maximum relative error: {max_rel:.12g}",
        "- Test cases: identical stereo sine wave; different-amplitude stereo sine wave; left-only signal; correlated deterministic stereo noise; partially decorrelated stereo noise; impulse plus low-level noise; float32 and float64 variants; one Stage 2 decoded real preview excerpt when present.",
        "",
        "| test_case | feature | max_abs | mean_abs | max_rel | passed |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ])
    for row in rows:
        lines.append(
            f"| {row['test_case']} | {row['feature']} | {row['max_absolute_error']} | "
            f"{row['mean_absolute_error']} | {row['maximum_relative_error']} | {row['passed']} |"
        )
    lines.extend(["", "## Edge Cases", "", "| case | feature | passed | notes |", "| --- | --- | --- | --- |"])
    for row in edge_rows:
        lines.append(f"| {row['case']} | {row['feature']} | {row['passed']} | {row['notes']} |")
    lines.extend([
        "",
        "## Approval",
        "",
        "Approved for dataset extraction: " + ("yes" if approved else "no"),
        "",
        "These transforms describe mix dynamics, spectral characteristics and spatialisation. They are not subjective quality scores.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
