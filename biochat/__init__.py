"""
CRITICAL — torch MUST be imported before numpy/pandas anywhere in the process.

In this conda env (macOS arm64, torch 2.2.2 + numpy 1.26.4, conda-forge),
if numpy's OpenBLAS is loaded before torch, torch CPU kernels crash the
interpreter with SIGSEGV (100% reproducible, e.g. the antibody-design
DiffCDRH3 pipeline). Importing torch here first — before any submodule
that pulls in pandas/numpy — prevents the crash in every biochat entry
point. Verified 2026-08-20.
"""
try:
    import torch  # noqa: F401  (intentional import-order guard)
except ImportError:
    pass  # torch optional — environments without it skip the guard

from .version import __version__

__all__ = ["__version__"]
