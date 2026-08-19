"""Phase 3B: DiffCDRH3 diffusion model pipeline.

Environment: BIOMNI_ANTIBODY_MODEL_DIR must point to directory containing:
  cdrh3_vae_model_best.pth / epitope_evo_vae_model_best.pth / diff_cdrh3_best_model_unfrozen.pth
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

_REQUIRED_MODEL_FILES = [
    "cdrh3_vae_model_best.pth",
    "epitope_evo_vae_model_best.pth",
    "diff_cdrh3_best_model_unfrozen.pth",
]

_model_cache: Dict[str, Any] = {}


def check_model_files(model_dir: Optional[str] = None) -> Dict[str, Any]:
    """Verify all model files exist. Returns {status, files, missing}."""
    if model_dir is None:
        model_dir = os.getenv("BIOMNI_ANTIBODY_MODEL_DIR", "")
    if not model_dir:
        return {"status": "error", "error": "BIOMNI_ANTIBODY_MODEL_DIR not set", "files": {}, "missing": _REQUIRED_MODEL_FILES}
    if not os.path.isdir(model_dir):
        return {"status": "error", "error": f"Directory not found: {model_dir}", "files": {}, "missing": _REQUIRED_MODEL_FILES}

    files = {}
    missing = []
    for fname in _REQUIRED_MODEL_FILES:
        path = os.path.join(model_dir, fname)
        exists = os.path.isfile(path)
        files[fname] = {"path": path, "exists": exists, "size_mb": round(os.path.getsize(path) / 1024 / 1024, 1) if exists else 0}
        if not exists:
            missing.append(fname)

    return {"status": "ok" if not missing else "error", "files": files, "missing": missing}


def _resolve_device(device: str) -> str:
    if device != "auto":
        return device
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def load_diffusion_model(model_dir: Optional[str] = None, device: str = "auto") -> Dict[str, Any]:
    """Load DiffCDRH3 model (cached). Requires torch."""
    global _model_cache
    cache_key = f"{model_dir}:{device}"
    if cache_key in _model_cache:
        return _model_cache[cache_key]

    import torch

    if model_dir is None:
        model_dir = os.getenv("BIOMNI_ANTIBODY_MODEL_DIR", "")
    if not model_dir:
        raise FileNotFoundError("BIOMNI_ANTIBODY_MODEL_DIR not set")

    resolved_device = _resolve_device(device)
    weights_path = os.path.join(model_dir, "diff_cdrh3_best_model_unfrozen.pth")

    from biomni.tool.antibody_design.model_inference import load_pretrained_model
    model = load_pretrained_model(weights_path, resolved_device)
    if model is None:
        raise RuntimeError(f"Failed to load model from {weights_path}")

    result = {
        "model": model, "device": resolved_device, "model_dir": model_dir,
        "model_files": {
            "cdrh3_vae": os.path.join(model_dir, "cdrh3_vae_model_best.pth"),
            "epitope_vae": os.path.join(model_dir, "epitope_evo_vae_model_best.pth"),
            "diffusion": weights_path,
        },
    }
    _model_cache[cache_key] = result
    return result


def generate_cdrh3_candidates(
    epitope_sequence: str,
    num_candidates: int = 20,
    model_dir: Optional[str] = None,
    device: str = "auto",
    random_seed: Optional[int] = 42,
) -> Dict[str, Any]:
    """Generate CDRH3 candidates using DiffCDRH3 model."""
    import torch

    if random_seed is not None:
        torch.manual_seed(random_seed)
        import random as _random
        _random.seed(random_seed)

    model_info = load_diffusion_model(model_dir, device)
    model = model_info["model"]
    dev = model_info["device"]

    from biomni.tool.antibody_design.model_inference import generate_cdrh3 as _generate

    raw_count = max(num_candidates * 3, 15)
    raw_sequences = _generate(model, epitope_sequence, dev, num_samples=raw_count)

    seen: set[str] = set()
    unique: list[str] = []
    for seq in raw_sequences:
        s = seq.strip().upper()
        if s and s not in seen:
            seen.add(s)
            unique.append(s)

    return {
        "cdrh3_sequences": unique[:num_candidates],
        "raw_count": len(raw_sequences),
        "deduplicated_count": len(unique),
        "generation": {
            "method": "DiffCDRH3", "provenance": "model_inferred",
            "model_dir": model_info["model_dir"],
            "model_files": model_info["model_files"],
            "device": dev, "random_seed": random_seed,
        },
    }
