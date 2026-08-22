"""
NanoBodyBuilder2 adapter — backend detection, sequence construction,
and real structure prediction (Phase 3C-3).

All outputs are labeled as computational predictions with
calibration="uncalibrated" and experimental_support="none".
"""

from __future__ import annotations

import os
import traceback
from typing import Any, Dict, Optional

# Standard IGHV3-23 framework template for VH-only antibody construction.
# CDRH3 is inserted at the "..." placeholder between the conserved CAR/CAK
# motif and the WGQGTLVTVSS J-region.
_VH_FRAMEWORK_TEMPLATES: Dict[str, str] = {
    "IGHV3-23": (
        "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVS"
        "GISGSGGSTYYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYCAK"
        "{cdrh3}"
        "WGQGTLVTVSS"
    ),
}

VALID_AAS = set("ACDEFGHIKLMNPQRSTVWY")


# ═══════════════════════════════════════════════════════════════
# Backend detection
# ═══════════════════════════════════════════════════════════════

def check_nanobodybuilder2_available() -> Dict[str, Any]:
    """Check if NanoBodyBuilder2 is importable and report its status."""
    result: Dict[str, Any] = {
        "available": False,
        "version": None,
        "backend": "NanoBodyBuilder2",
        "provenance": "computed",
        "install_hint": (
            "NanoBodyBuilder2 is not installed. Install with: "
            "pip install nanobodybuilder2\n"
            "Or use mock=True for placeholder structures "
            "(NOT for scientific use)."
        ),
    }

    try:
        from ImmuneBuilder import NanoBodyBuilder2 as _NB2
        result["available"] = True
        result["version"] = getattr(_NB2, "__version__", None) or "ImmuneBuilder"
        result["backend"] = "ImmuneBuilder.NanoBodyBuilder2"
        result.pop("install_hint", None)
    except ImportError:
        try:
            import importlib
            nb2 = importlib.import_module("nanobodybuilder2")
            result["available"] = True
            result["version"] = getattr(nb2, "__version__", "unknown")
            result.pop("install_hint", None)
        except ImportError:
            pass

    return result


# ═══════════════════════════════════════════════════════════════
# VH sequence construction from CDRH3
# ═══════════════════════════════════════════════════════════════

def construct_vh_sequence_from_cdrh3(
    cdrh3_sequence: str,
    framework: str = "IGHV3-23",
) -> Dict[str, Any]:
    """Construct a full VH sequence by inserting CDRH3 into a framework template.

    The CDRH3 is placed between the conserved CAR/CAK motif and the
    WGQGTLVTVSS J-region.  This is a designed construct — NOT a natural
    antibody sequence.

    Returns metadata including provenance and experimental_support=none.
    """
    cdrh3 = (cdrh3_sequence or "").strip().upper()
    if not cdrh3:
        raise ValueError("cdrh3_sequence is empty")
    invalid = [c for c in cdrh3 if c not in VALID_AAS]
    if invalid:
        raise ValueError(f"Invalid amino acids in CDRH3: {sorted(set(invalid))}")

    template = _VH_FRAMEWORK_TEMPLATES.get(framework)
    if template is None:
        raise ValueError(f"Unknown framework: {framework}. Available: {list(_VH_FRAMEWORK_TEMPLATES)}")

    vh_sequence = template.format(cdrh3=cdrh3)

    # Verify CDRH3 is present in the output
    assert cdrh3 in vh_sequence, f"CDRH3 '{cdrh3}' not found in constructed VH sequence"

    return {
        "vh_sequence": vh_sequence,
        "framework": framework,
        "cdrh3_sequence": cdrh3,
        "cdrh3_inserted": True,
        "framework_template": True,
        "sequence_is_designed_construct": True,
        "experimental_support": "none",
        "provenance": "template_constructed",
        "calibration": "uncalibrated",
    }


# ═══════════════════════════════════════════════════════════════
# Real structure prediction
# ═══════════════════════════════════════════════════════════════

def predict_nanobody_structure(
    sequence: str,
    output_pdb: str,
    model_index: Optional[int] = None,
) -> Dict[str, Any]:
    """Predict a nanobody structure using ImmuneBuilder.NanoBodyBuilder2.

    Args:
        sequence: Full VH amino acid sequence (>70 aa).
        output_pdb: Path to write the predicted PDB file.
        model_index: Which model to save (None = best, 0-3 for specific).

    Returns:
        {
            "success": bool,
            "method": "ImmuneBuilder.NanoBodyBuilder2",
            "mock": false,
            "output_pdb": str or None,
            "structure_type": "predicted_model",
            "experimental_support": "none",
            "calibration": "uncalibrated",
            "provenance": "computed",
            "error_type": str or None (on failure),
            "error_message": str or None (on failure),
        }
    """
    result: Dict[str, Any] = {
        "success": False,
        "method": "ImmuneBuilder.NanoBodyBuilder2",
        "mock": False,
        "output_pdb": None,
        "structure_type": "predicted_model",
        "experimental_support": "none",
        "calibration": "uncalibrated",
        "provenance": "computed",
        "error_type": None,
        "error_message": None,
    }

    try:
        from ImmuneBuilder import NanoBodyBuilder2

        predictor = NanoBodyBuilder2()
        nb_result = predictor.predict({"H": sequence})

        os.makedirs(os.path.dirname(output_pdb), exist_ok=True)

        if model_index is not None:
            nb_result.save_single_unrefined(output_pdb, index=model_index)
        else:
            nb_result.save(output_pdb)

        result["success"] = True
        result["output_pdb"] = output_pdb

    except FileNotFoundError as exc:
        result["error_type"] = "FileNotFoundError"
        result["error_message"] = str(exc)
        result["traceback"] = traceback.format_exc()
    except AssertionError as exc:
        result["error_type"] = "AssertionError"
        result["error_message"] = str(exc)
        result["traceback"] = traceback.format_exc()
    except Exception as exc:
        result["error_type"] = type(exc).__name__
        result["error_message"] = str(exc)
        result["traceback"] = traceback.format_exc()

    return result

