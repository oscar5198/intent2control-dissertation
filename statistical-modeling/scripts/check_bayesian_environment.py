"""Lightweight Bayesian environment check for the statistical modeling project."""

from __future__ import annotations

import importlib.metadata as metadata
import multiprocessing
import platform
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_SRC = REPO_ROOT / "statistical-modeling" / "src"
if str(BASELINE_SRC) not in sys.path:
    sys.path.insert(0, str(BASELINE_SRC))


def package_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "not installed"


def print_environment() -> None:
    import pytensor

    print("Python:", sys.version.replace("\n", " "))
    print("Bambi:", package_version("bambi"))
    print("PyMC:", package_version("pymc"))
    print("ArviZ:", package_version("arviz"))
    print("nutpie:", package_version("nutpie"))
    print("numba:", package_version("numba"))
    print("PyTensor cxx:", pytensor.config.cxx)
    print("PyTensor mode:", pytensor.config.mode)
    print("PyTensor base_compiledir:", pytensor.config.base_compiledir)
    print("CPU count:", multiprocessing.cpu_count())
    print("Platform:", platform.platform())


def smoke_test() -> None:
    import pymc as pm

    print("\nTiny sampler smoke test:")
    with pm.Model():
        mu = pm.Normal("mu", mu=0.0, sigma=1.0)
        pm.Normal("y", mu=mu, sigma=1.0, observed=[-0.2, 0.0, 0.1, 0.3])
        idata = pm.sample(
            draws=20,
            tune=20,
            chains=2,
            target_accept=0.95,
            random_seed=20260817,
            nuts_sampler="nutpie",
            progressbar=False,
            compute_convergence_checks=False,
        )
    draws = int(idata.posterior.sizes["chain"] * idata.posterior.sizes["draw"])
    print(f"Smoke test completed: {draws} posterior draws.")


def main() -> int:
    print_environment()
    smoke_test()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
