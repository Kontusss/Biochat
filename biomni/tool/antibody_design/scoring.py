"""Scoring engine — applies penalties and bonuses to produce aggregate scores."""

from typing import Any, Dict, List

from biomni.tool.antibody_design.schemas import PENALTY_TABLE
from biomni.tool.antibody_design.validators import (
    check_epitope_copy, assess_charge_complementarity, charge_bonus,
)

BASE_SCORE = 80.0
MAX_SCORE = 100.0


def score_candidate(
    cdrh3: str,
    epitope: str,
    full_sequence: str = "",
    filter_flags: List[str] | None = None,
    filter_metrics: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Score a single CDRH3 candidate through all Phase 3A gates.

    Returns a dict with: accepted, aggregate_score, scores, penalties, warnings.
    """
    filter_flags = filter_flags or []
    filter_metrics = filter_metrics or {}

    result: Dict[str, Any] = {
        "cdrh3_sequence": cdrh3,
        "full_sequence": full_sequence,
        "accepted": True,
        "aggregate_score": BASE_SCORE,
        "scores": {},
        "penalties": [],
        "warnings": [],
        "generated_by": {"method": "unknown", "provenance": "unknown"},
    }

    # Step 1: Anti-copy check
    result["penalties"].extend(check_epitope_copy(cdrh3, epitope))

    # Step 2: Map filter flags to penalties
    for flag in filter_flags:
        if flag not in [p["flag"] for p in result["penalties"]]:
            info = PENALTY_TABLE.get(flag, ("WARNING", 2, flag))
            result["penalties"].append({
                "flag": flag, "level": info[0], "deduction": info[1],
                "explanation": info[2],
                "source": "generation_filter.py:penalty_table", "provenance": "computed",
            })

    # Step 3: Apply penalties
    hard = any(p["level"] == "HARD_EXCLUDE" for p in result["penalties"])
    soft_ded = sum(p["deduction"] for p in result["penalties"] if p["level"] == "SOFT_PENALTY")
    warn_ded = sum(p["deduction"] for p in result["penalties"] if p["level"] == "WARNING")

    if hard:
        result["accepted"] = False
        result["aggregate_score"] = 0.0
    else:
        result["aggregate_score"] = max(0.0, min(MAX_SCORE, BASE_SCORE - soft_ded - warn_ded))

    # Step 4: Charge complementarity bonus
    try:
        cc = assess_charge_complementarity(cdrh3, epitope)
        bonus = charge_bonus(cc)
        result["scores"]["charge_complementarity"] = {
            "value": round(bonus, 1), "source": "validators.py",
            "provenance": "computed", "detail": cc,
        }
        if not hard:
            result["aggregate_score"] = min(MAX_SCORE, result["aggregate_score"] + bonus)
    except Exception as exc:
        result["warnings"].append(f"charge_failed: {exc}")

    # Step 5: Collect warnings from penalties
    for p in result["penalties"]:
        if p["level"] in ("SOFT_PENALTY", "WARNING"):
            result["warnings"].append(f"{p['flag']}: {p['explanation']}")

    result["aggregate_score"] = round(result["aggregate_score"], 1)
    return result


def rank_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort candidates: accepted first, then by aggregate_score descending."""
    ranked = sorted(candidates, key=lambda c: (c["accepted"], c.get("aggregate_score", 0)), reverse=True)
    for i, c in enumerate(ranked, 1):
        c["rank"] = i
    return ranked
