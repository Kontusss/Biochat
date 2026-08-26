"""Side-channel antibody-likeness signal — reported, never ranked on.

Wraps the trained CDR-H3 adjacency model (``biochat.eval.cdrh3_lm``) for the
production path.  The value is attached to a candidate alongside the liability
score and **does not participate in ranking**: the two answer different
questions and are not on a common scale.

    aggregate_score   0-100, "does this carry developability liabilities"
    antibody_likeness unbounded mean PMI, "does this look like a real
                      antibody loop" (approved drugs ~ +0.20, shuffles ~ -0.11)

It is emphatically **not** an affinity, ΔG, Kd, or developability figure.  The
returned record carries ``provenance`` and ``interpretation`` fields so a
downstream report cannot present it as one.

If the model artifact is absent the signal is simply omitted — an optional
diagnostic must never break candidate scoring.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_MODEL_PATH = _PROJECT_ROOT / "reports" / "cdrh3_bigram_model.json"

# Cache: None = not yet attempted, False = attempted and unavailable.
_MODEL: Any = None


def model_path() -> Path:
    """Resolve the model artifact path, honouring ``BIOCHAT_CDRH3_LM_PATH``."""
    override = os.environ.get("BIOCHAT_CDRH3_LM_PATH")
    return Path(override) if override else _DEFAULT_MODEL_PATH


def _load_model():
    """Load and cache the model, or cache ``False`` if it is unavailable."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL or None

    path = model_path()
    if not path.exists():
        _MODEL = False
        return None
    try:
        from biochat.eval.cdrh3_lm import CDRH3BigramModel

        _MODEL = CDRH3BigramModel.load(path)
    except Exception:  # noqa: BLE001 - an optional diagnostic never breaks scoring
        _MODEL = False
        return None
    return _MODEL


def reset_cache() -> None:
    """Drop the cached model — for tests that swap the artifact."""
    global _MODEL
    _MODEL = None


def score_antibody_likeness(cdrh3: str) -> dict[str, Any] | None:
    """Return the antibody-likeness record for ``cdrh3``, or ``None``.

    ``None`` means the signal is unavailable (no trained artifact, or a
    sequence too short to contain an adjacent pair) — callers omit the field
    rather than substituting a placeholder number.
    """
    seq = (cdrh3 or "").strip().upper()
    if len(seq) < 2:
        return None

    model = _load_model()
    if model is None:
        return None

    return {
        "value": round(float(model.score(seq)), 4),
        "unit": "mean_pointwise_mutual_information",
        "source": "cdrh3_lm.py:CDRH3BigramModel",
        "provenance": "model_inferred",
        "calibration": "uncalibrated",
        "ranking_input": False,
        "interpretation": (
            "Sequence resemblance to real antibody CDR-H3 loops. "
            "NOT binding affinity, NOT ΔG/Kd, NOT a developability score. "
            "Reference: approved therapeutics ≈ +0.20, composition-matched shuffles ≈ -0.11."
        ),
        "n_train": getattr(model, "n_train", 0),
    }
