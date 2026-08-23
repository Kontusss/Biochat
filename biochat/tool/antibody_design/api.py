"""Public API — design_vh_only_antibodies + score_and_rank_candidates."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from biochat.tool.antibody_design.schemas import SAFETY_DISCLAIMER
from biochat.tool.antibody_design.validators import validate_epitope
from biochat.tool.antibody_design.scoring import score_candidate, rank_candidates


def design_vh_only_antibodies(
    epitope_sequence: str,
    num_candidates: int = 5,
    framework: str = "IGHV3-23",
    pipeline_level: str = "heuristic_sequence",
    cdrh3_candidates: Optional[List[str]] = None,
    random_seed: Optional[int] = 42,
    device: str = "auto",
    run_structure: bool = False,
    run_docking: bool = False,
    mode: str = "sequence_only",
) -> Dict[str, Any]:
    """Design VH-only antibody CDRH3 candidates for a peptide epitope.

    Pipeline levels:
      "heuristic_sequence" (3A) — externally-provided CDRH3 via cdrh3_candidates
      "diffusion_sequence"  (3B) — DiffCDRH3 model generates candidates
    """
    epitope = (epitope_sequence or "").strip().upper()
    valid, err = validate_epitope(epitope)
    if not valid:
        return _error(err, pipeline_level)

    phase = "3B" if pipeline_level == "diffusion_sequence" else "3A"

    # ── Resolve sequences ────────────────────────────────────
    if pipeline_level == "diffusion_sequence":
        try:
            from biochat.tool.antibody_design.diffusion_pipeline import generate_cdrh3_candidates
            gen = generate_cdrh3_candidates(
                epitope_sequence=epitope, num_candidates=num_candidates,
                random_seed=random_seed, device=device,
            )
            sequences = gen["cdrh3_sequences"]
            generation_meta = gen["generation"]
        except ImportError as exc:
            return _error(
                f"Diffusion model requires torch. Install: pip install torch. "
                f"Or use pipeline_level='heuristic_sequence'. Error: {exc}",
                pipeline_level,
            )
        except FileNotFoundError as exc:
            return _error(str(exc), pipeline_level)
        except Exception as exc:
            return _error(f"Model generation failed: {exc}", pipeline_level)
    else:
        if not cdrh3_candidates:
            return _error(
                "No cdrh3_candidates provided. "
                "Use cdrh3_candidates=[...] or pipeline_level='diffusion_sequence'.",
                pipeline_level,
            )
        sequences = cdrh3_candidates
        generation_meta = {
            "method": "heuristic", "provenance": "llm_estimated",
            "note": "Sequences provided by caller",
        }

    # ── Score and rank ───────────────────────────────────────
    result = score_and_rank_candidates(sequences, epitope)

    # Stamp per-candidate generation metadata
    gen_by = {
        "method": generation_meta.get("method", "unknown"),
        "provenance": generation_meta.get("provenance", "unknown"),
    }
    for c in result["candidates"]:
        c["generated_by"] = gen_by

    # Phase 3C-0: Structure readiness screening
    try:
        from biochat.tool.antibody_design.structure_prep import check_structure_readiness
        sr = check_structure_readiness(sequences, epitope)
        result["structure_readiness"] = sr["structure_readiness"]
        result["structure_readiness"]["candidates"] = sr["candidates"]
    except Exception as exc:
        result["structure_readiness"] = {
            "ready": False, "error": str(exc),
            "provenance": "computed", "source": "structure_prep.py",
            "calibration": "none",
        }

    result["pipeline_level"] = pipeline_level
    result["phase"] = phase
    result["generation"] = generation_meta
    result["docking_available"] = False
    result["calibrated_affinity_available"] = False
    return result


def score_and_rank_candidates(
    cdrh3_sequences: List[str],
    epitope_sequence: str,
    full_sequences: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Validate, score, and rank CDRH3 candidates."""
    epitope = (epitope_sequence or "").strip().upper()
    candidates: List[Dict[str, Any]] = []

    for i, cdrh3 in enumerate(cdrh3_sequences):
        cdrh3 = (cdrh3 or "").strip().upper()
        full = (full_sequences or [""] * len(cdrh3_sequences))[i] if full_sequences and i < len(cdrh3_sequences) else ""

        # Get filter flags
        flags: List[str] = []
        metrics: Dict[str, Any] = {}
        try:
            from biochat.tool.antibody_design.generation_filter import filter_cdrh3_design
            ok, f, m = filter_cdrh3_design(cdrh3, epitope)
            flags = list(f)
            metrics = dict(m)
        except Exception:
            pass

        c = score_candidate(cdrh3, epitope, full, flags, metrics)

        # Add developability if full sequence available
        if full:
            try:
                from biochat.tool.antibody_design.developability_checks import basic_developability_report
                dev = basic_developability_report(full)
                c["scores"]["developability"] = {
                    "value": round(float(dev.get("score", 0)), 1),
                    "source": "developability_checks.py", "provenance": "computed",
                }
            except Exception as exc:
                c["warnings"].append(f"dev_failed: {exc}")

        c["index"] = i
        candidates.append(c)

    ranked = rank_candidates(candidates)
    return {
        "candidates": ranked,
        "epitope": epitope,
        "mode": "sequence_only",
        "scoring_model": "base80_penalty_deduction",
        "safety_disclaimer": SAFETY_DISCLAIMER,
        "docking_available": False,
        "calibrated_affinity_available": False,
        "warnings": [],
        "errors": [],
    }


def _error(msg: str, pipeline_level: str = "heuristic_sequence") -> Dict[str, Any]:
    phase = "3B" if pipeline_level == "diffusion_sequence" else "3A"
    return {
        "candidates": [], "epitope": "", "pipeline_level": pipeline_level,
        "phase": phase, "scoring_model": "base80_penalty_deduction",
        "safety_disclaimer": SAFETY_DISCLAIMER,
        "docking_available": False, "calibrated_affinity_available": False,
        "warnings": [], "errors": [msg],
    }
