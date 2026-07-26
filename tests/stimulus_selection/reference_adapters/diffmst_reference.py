from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace


FEATURE_NAMES = (
    "compute_rms",
    "compute_crest_factor",
    "compute_stereo_width",
    "compute_stereo_imbalance",
    "compute_barkspectrum",
)


def import_reference_loss(reference_root: str | Path) -> ModuleType:
    """Import Diff-MST's original ``mst.loss`` without retaining sys.path edits."""
    root = Path(reference_root).resolve()
    if not (root / "mst" / "loss.py").exists():
        raise FileNotFoundError(f"Diff-MST reference loss.py not found under {root}")

    root_text = str(root)
    previous_path = list(sys.path)
    stub_names = ("librosa", "mst.fx_encoder", "mst.modules")
    old_modules = {name: sys.modules.get(name) for name in ("mst", "mst.loss", "mst.filter", *stub_names)}
    for name in ("mst.loss", "mst.filter", "mst"):
        sys.modules.pop(name, None)
    try:
        sys.modules.setdefault("librosa", SimpleNamespace(filters=SimpleNamespace(mel=lambda *args, **kwargs: None)))
        sys.modules.setdefault("mst.fx_encoder", SimpleNamespace(FXencoder=object))
        sys.modules.setdefault("mst.modules", SimpleNamespace(SpectrogramEncoder=object))
        sys.path.insert(0, root_text)
        module = importlib.import_module("mst.loss")
        missing = [name for name in FEATURE_NAMES if not hasattr(module, name)]
        if missing:
            raise AttributeError(f"Reference mst.loss is missing: {', '.join(missing)}")
        return module
    finally:
        sys.path[:] = previous_path
        for name in ("mst.loss", "mst.filter", "mst", *stub_names):
            sys.modules.pop(name, None)
        for name, module in old_modules.items():
            if module is not None:
                sys.modules[name] = module
