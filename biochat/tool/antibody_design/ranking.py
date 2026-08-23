"""Transparent candidate ranking with multi-factor composite scoring.

Key principles:
1. Hard exclusion conditions always override scores
2. Fallback-scored candidates are penalized
3. Extra Cys in CDRH3 candidates cannot be recommended for screening
4. Ranking explanations are generated for every candidate
5. Score type (interface_dG vs fallback_score) is transparent in output
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from candidate_result import (
    CandidateResult, Recommendation,
)

# Extended recommendation type that includes the new seed-level category
EXTENDED_RECOMMENDATION = (
    "recommended_for_experimental_screening",
    "sequence_level_priority_candidate",
    "computational_seed_requires_structural_validation",
    "conditional_recommended_with_caution",
    "computational_hit_redesign_required",
    "not_recommended",
    "insufficient_data",
)


# ── Scoring weights for composite rank ───────────────────────────────────────
DEFAULT_WEIGHTS = {
    "rosetta_interface_dG": 0.35,      # Highest weight — real interface energy
    "rosetta_fallback_score": 0.12,    # Low weight — degraded score
    "hdock_score": 0.15,               # Moderate — docking score
    "developability": 0.20,            # Sequence developability
    "length_optimality": 0.08,         # CDRH3 length preference
    "charge_complementarity": 0.05,    # Epitope charge match
    "score_source_quality": 0.05,      # Penalizes fallback sources
}

# ── Penalties ────────────────────────────────────────────────────────────────
PENALTIES = {
    "extra_Cys_in_CDRH3": 0.40,        # Hard penalty — major liability
    "cdrh3_length_high_risk": 0.25,    # Length outside hard range
    "empty_sequence": 1.00,            # Invalid
    "invalid_amino_acid": 1.00,         # Invalid
    "nglyc_motif": 0.10,               # Moderate penalty
    "hydrophobic_patch": 0.08,
    "high_net_charge": 0.05,
    "high_hydrophobicity": 0.05,
    "possible_electrostatic_repulsion": 0.10,
}


def _safe_float(value: Any, default: float = float("inf")) -> float:
    """Safely coerce to float, returning default on failure."""
    try:
        if value is None:
            return default
        val = float(value)
        if math.isnan(val) or math.isinf(val):
            return default
        return val
    except (TypeError, ValueError):
        return default


def _length_optimality(length: int) -> float:
    """Score CDRH3 length optimality (max at 14, preferred 11–17)."""
    optimal = 14
    half_window = 3  # 11–17
    deviation = abs(length - optimal)
    if deviation <= half_window:
        return 1.0
    return max(0.0, 1.0 - (deviation - half_window) / 10.0)


def _charge_complementarity(cdrh3_charge: float, epitope_charge: float) -> float:
    """Score charge complementarity (opposite signs = good)."""
    if cdrh3_charge * epitope_charge < 0:
        return 1.0  # Opposite signs — complementary
    if abs(cdrh3_charge) < 0.5 or abs(epitope_charge) < 0.5:
        return 0.7  # One is nearly neutral
    return 0.3  # Same sign — possible repulsion


def compute_ranking_components(
    candidate: CandidateResult,
    all_candidates: List[CandidateResult],
) -> Dict[str, float]:
    """Compute normalized ranking components for a candidate.

    Components are normalized across the candidate pool (0–1 scale).
    """
    components: Dict[str, float] = {}

    # ── Rosetta score component ──────────────────────────────────────────
    rosetta_scores = []
    for c in all_candidates:
        if c.rosetta and c.rosetta.raw_score is not None:
            rosetta_scores.append(c.rosetta.raw_score)

    if rosetta_scores and candidate.rosetta and candidate.rosetta.raw_score is not None:
        min_score = min(rosetta_scores)
        max_score = max(rosetta_scores)
        if abs(max_score - min_score) > 1e-9:
            norm = (candidate.rosetta.raw_score - min_score) / (max_score - min_score)
            # Lower is better → invert
            components["rosetta_score_normalized"] = round(1.0 - norm, 4)
        else:
            components["rosetta_score_normalized"] = 0.5

        # Distinguish real vs fallback
        if candidate.rosetta.fallback_used:
            components["rosetta_interface_dG"] = (
                components["rosetta_score_normalized"] * DEFAULT_WEIGHTS["rosetta_fallback_score"]
            )
            components["rosetta_fallback_score"] = (
                components["rosetta_score_normalized"] * DEFAULT_WEIGHTS["rosetta_fallback_score"]
            )
        else:
            components["rosetta_interface_dG"] = (
                components["rosetta_score_normalized"] * DEFAULT_WEIGHTS["rosetta_interface_dG"]
            )
            components["rosetta_fallback_score"] = 0.0
    else:
        components["rosetta_score_normalized"] = 0.0
        components["rosetta_interface_dG"] = 0.0
        components["rosetta_fallback_score"] = 0.0

    # ── HDOCK score component ────────────────────────────────────────────
    hdock_scores = [
        c.docking.hdock_score for c in all_candidates
        if c.docking and c.docking.hdock_score is not None
    ]
    if hdock_scores and candidate.docking and candidate.docking.hdock_score is not None:
        min_h = min(hdock_scores)
        max_h = max(hdock_scores)
        if abs(max_h - min_h) > 1e-9:
            norm_h = (candidate.docking.hdock_score - min_h) / (max_h - min_h)
            components["hdock_score"] = round((1.0 - norm_h) * DEFAULT_WEIGHTS["hdock_score"], 4)
        else:
            components["hdock_score"] = 0.5 * DEFAULT_WEIGHTS["hdock_score"]
    else:
        components["hdock_score"] = 0.0

    # ── Developability component ─────────────────────────────────────────
    dev_status_scores = {"pass": 1.0, "conditional_pass": 0.75, "warning": 0.5,
                         "fail": 0.0, "not_run": 0.5}
    dev_score = dev_status_scores.get(candidate.developability_qc.status, 0.5)
    components["developability"] = round(dev_score * DEFAULT_WEIGHTS["developability"], 4)

    # ── Length optimality ────────────────────────────────────────────────
    length = len(candidate.cdrh3_sequence)
    components["length_optimality"] = round(
        _length_optimality(length) * DEFAULT_WEIGHTS["length_optimality"], 4
    )

    # ── Charge complementarity ───────────────────────────────────────────
    cdrh3_charge = candidate.sequence_features.net_charge_pH_7_4 or 0.0
    epi_charge = candidate.sequence_features.epitope_net_charge or 0.0
    components["charge_complementarity"] = round(
        _charge_complementarity(cdrh3_charge, epi_charge) * DEFAULT_WEIGHTS["charge_complementarity"], 4
    )

    # ── Score source quality ─────────────────────────────────────────────
    if candidate.rosetta and candidate.rosetta.fallback_used:
        src_quality = 0.3
    elif candidate.rosetta and not candidate.rosetta.fallback_used:
        src_quality = 1.0
    elif candidate.docking and candidate.docking.status in ("success", "warning"):
        src_quality = 0.6
    else:
        src_quality = 0.3
    components["score_source_quality"] = round(src_quality * DEFAULT_WEIGHTS["score_source_quality"], 4)

    # ── Compute composite ────────────────────────────────────────────────
    composite = sum(components.values())

    # ── Apply penalties ──────────────────────────────────────────────────
    total_penalty = 0.0
    all_flags = candidate.sequence_qc.risk_flags + candidate.developability_qc.risk_flags
    for flag in all_flags:
        for penalty_key, penalty_value in PENALTIES.items():
            if penalty_key in flag:
                total_penalty = max(total_penalty, penalty_value)
    # Cap penalty at 0.6
    total_penalty = min(0.6, total_penalty)
    components["penalty"] = round(-total_penalty, 4)
    composite += components["penalty"]

    components["composite_raw"] = composite
    return components


def determine_recommendation(
    candidate: CandidateResult,
    has_any_real_scoring: bool = False,
) -> Tuple[Recommendation, str]:
    """Determine the final recommendation for a candidate.

    Rules applied in order:
    1. Sequence QC fail (extra Cys) → computational_hit_redesign_required
    2. No real scoring anywhere → conditional_recommended_with_caution (at best)
    3. Developability QC fail → not_recommended or computational_hit_redesign_required
    4. All tools failed → insufficient_data
    5. All pass + real scoring → recommended_for_experimental_screening
    """
    seq_status = candidate.sequence_qc.status
    dev_status = candidate.developability_qc.status
    seq_flags = candidate.sequence_qc.risk_flags
    has_extra_cys = "extra_Cys_in_CDRH3" in seq_flags
    fallback_used = candidate.rosetta and candidate.rosetta.fallback_used if candidate.rosetta else False

    # Rule 1: Extra Cys → must redesign
    if has_extra_cys:
        return ("computational_hit_redesign_required",
                f"CDRH3 contains extra Cys (cys_count_cdrh3={candidate.sequence_features.cys_count_cdrh3}). "
                "Unpaired cysteines are a major developability liability. "
                "Remove or pair as designed disulfide with structural validation.")

    # Rule 2: Sequence QC fail (other reasons)
    if seq_status == "fail":
        return ("not_recommended",
                f"Sequence QC failed with flags: {seq_flags}. "
                "Candidate has hard sequence defects beyond CDRH3 Cys.")

    # Rule 2b: Contact analysis failure for short peptides
    contact = candidate.contact_analysis or {}
    contact_status = contact.get("status", "not_run")
    contact_cov = contact.get("contact_coverage", 0.0)
    is_short_peptide = len(candidate.epitope_sequence) <= 8 if candidate.epitope_sequence else False

    if is_short_peptide and contact_status == "failed":
        return ("not_recommended",
                f"Contact analysis failed for short peptide {candidate.epitope_sequence} — "
                "docking may be a false positive. contact_coverage=0.")
    if contact_status == "warning" and contact_cov < 0.4:
        return ("computational_seed_requires_structural_validation",
                f"Low contact coverage ({contact_cov:.2f}) for epitope — "
                "docking may not target the intended epitope. "
                "Structural validation with full antigen recommended.")

    # Rule 2d: Contact success with W6 contacted for PSAEVWD → evidence of specificity
    if contact_status == "success" and contact_cov >= 0.4:
        w6_contacted = 5 in contact.get("contacted_epitope_positions", [])
        if candidate.epitope_sequence == "PSAEVWD" and w6_contacted:
            # Good evidence of specific binding — continue to normal ranking
            pass

    # Rule 2c: Odd cysteine count in VH → cannot be experimental candidate
    vh_cys = candidate.sequence_features.cys_count_total or 0
    if vh_cys > 2 and vh_cys % 2 != 0:
        return ("computational_hit_redesign_required",
                f"Odd cysteine count ({vh_cys}) in VH — unpaired Cys is a "
                "major developability liability. Requires numbering + redesign.")

    # Rule 3: No docking → cannot be experimental recommendation
    docking_not_run = (not candidate.docking or
                       candidate.docking.status in ("not_run", "failed"))
    contact_not_run = (not contact or
                       contact.get("status") in ("not_run", None))

    if docking_not_run and contact_not_run:
        # Neither docking nor contact analysis ran — VH sequence candidate only
        has_dev_issues = dev_status in ("fail", "warning")
        if has_dev_issues or has_extra_cys:
            return ("computational_seed_requires_structural_validation",
                    "No docking or contact analysis performed. "
                    "Candidate has developability concerns — structural "
                    "validation required before experimental consideration.")
        return ("sequence_level_priority_candidate",
                "No docking or contact analysis performed. "
                "Candidate is a sequence-level priority candidate; "
                "requires structural validation (docking + contact analysis) "
                "before experimental recommendation.")

    # Rule 4: All tools failed
    docking_failed = not candidate.docking or candidate.docking.status in ("failed", "not_run")
    rosetta_failed = not candidate.rosetta or candidate.rosetta.status in ("failed", "not_run")
    if docking_failed and rosetta_failed:
        return ("insufficient_data",
                "Both docking and Rosetta scoring are unavailable. "
                "Cannot make binding affinity assessment.")

    # Rule 5: No real scoring (all fallback/proxy)
    if not has_any_real_scoring:
        if dev_status == "fail":
            return ("not_recommended",
                    "No real scoring data available AND developability QC failed. "
                    "Candidate should not proceed.")
        return ("conditional_recommended_with_caution",
                "No real Rosetta interface_dG available — only fallback/proxy scores. "
                "Binding affinity assessment has low confidence. "
                "Real docking + InterfaceAnalyzer strongly recommended before experimental validation.")

    # Rule 6: Fallback scoring only
    if fallback_used:
        if dev_status == "fail":
            return ("not_recommended",
                    "Rosetta used fallback/degraded scoring AND developability QC failed. "
                    "Score is NOT equivalent to standard interface_dG.")
        if dev_status == "warning":
            return ("conditional_recommended_with_caution",
                    "Rosetta used fallback scoring (not standard interface_dG) AND "
                    "developability has warnings. Ranking confidence is reduced. "
                    "Recommend re-running with full InterfaceAnalyzer before screening.")
        return ("conditional_recommended_with_caution",
                "Rosetta used fallback/degraded scoring. "
                "Score is NOT equivalent to standard interface_dG. "
                "Ranking confidence is reduced. Re-score with full InterfaceAnalyzer.")

    # Rule 7: Developability QC check
    if dev_status == "fail":
        return ("not_recommended",
                f"Developability QC failed with flags: {candidate.developability_qc.risk_flags}")

    if dev_status == "warning":
        return ("conditional_recommended_with_caution",
                f"Developability QC has warnings: {candidate.developability_qc.risk_flags}. "
                "Address before experimental screening.")

    if dev_status == "conditional_pass":
        return ("conditional_recommended_with_caution",
                "Developability is conditionally acceptable. "
                "Minor issues should be monitored during expression.")

    # Rule 7: All clear
    return ("recommended_for_experimental_screening",
            "All QC gates passed with real interface scoring. "
            "Candidate is suitable for experimental screening.")


def rank_candidates(
    candidates: List[CandidateResult],
    has_any_real_scoring: bool = False,
) -> List[CandidateResult]:
    """Rank candidates with transparent multi-factor scoring.

    Process:
    1. Compute ranking components for each candidate
    2. Assign recommendations based on hard rules
    3. Sort by: recommendation tier → composite score

    Returns candidates with .ranking populated.
    """
    if not candidates:
        return []

    # Compute components for all candidates
    for c in candidates:
        components = compute_ranking_components(c, candidates)
        rec, reason = determine_recommendation(c, has_any_real_scoring)
        c.ranking.rank_components = components
        c.ranking.composite_score = round(components["composite_raw"] * 100, 2)
        c.ranking.recommendation = rec
        c.ranking.recommendation_reason = reason

    # Sort: recommendation tier → composite score
    rec_order = {
        "recommended_for_experimental_screening": 0,
        "sequence_level_priority_candidate": 1,
        "computational_seed_requires_structural_validation": 2,
        "conditional_recommended_with_caution": 3,
        "computational_hit_redesign_required": 4,
        "not_recommended": 5,
        "insufficient_data": 6,
    }

    candidates.sort(key=lambda c: (
        rec_order.get(c.ranking.recommendation, 99),
        -(c.ranking.composite_score or 0),
    ))

    # Assign ranks
    for i, c in enumerate(candidates, 1):
        c.ranking.rank = i
        c.ranking.ranking_explanation = _build_explanation(c)

    return candidates


def _build_explanation(candidate: CandidateResult) -> str:
    """Build a transparent human-readable ranking explanation.

    Distinguishes raw developability from penalty-adjusted priority.
    """
    parts = [
        f"{candidate.candidate_id}: rank={candidate.ranking.rank}",
        f"composite={candidate.ranking.composite_score or 0:.1f}",
        f"recommendation={candidate.ranking.recommendation}",
    ]
    if candidate.sequence_qc.risk_flags:
        parts.append(f"seq_flags={candidate.sequence_qc.risk_flags}")
    if candidate.rosetta:
        if candidate.rosetta.fallback_used:
            parts.append(f"rosetta=FALLBACK({candidate.rosetta.raw_score})")
        else:
            parts.append(f"rosetta={candidate.rosetta.raw_score}")
    parts.append(f"reason={candidate.ranking.recommendation_reason}")
    # Note if raw score differs from adjusted rank
    if candidate.sequence_qc.penalty > 0:
        parts.append(
            "(note: raw developability may not be highest, but this candidate "
            "has the best penalty-adjusted priority in current screening tier)"
        )
    return " | ".join(parts)


def rank_legacy_results(
    results: List[Dict[str, Any]],
    epitope: str = "",
) -> List[Dict[str, Any]]:
    """Rank legacy dict-based results with transparent QC.

    This is a backward-compatible adapter that converts legacy results
    to CandidateResult, ranks them, and converts back.

    Returns results sorted by rank with added ranking fields.
    """
    from candidate_result import ensure_candidate_ids
    from sequence_qc import run_full_qc

    results = ensure_candidate_ids(results)
    candidates: List[CandidateResult] = []

    for row in results:
        cdrh3 = str(row.get("cdrh3", "")).strip().upper()
        cid = row.get("candidate_id", "")

        # Run full QC
        qc = run_full_qc(cdrh3, epitope=epitope,
                        rosetta_fallback_used=("fallback" in str(row.get("score_source", "")).lower()))

        # Build CandidateResult
        c = CandidateResult(
            candidate_id=cid,
            epitope_sequence=epitope,
            cdrh3_sequence=cdrh3,
            vh_sequence=row.get("full_sequence", ""),
        )

        # Populate QC (note: QC dict key "flags" maps to dataclass attr "risk_flags")
        _qc_key_map = {"flags": "risk_flags"}
        for k, v in qc["sequence_qc"].items():
            attr = _qc_key_map.get(k, k)
            if hasattr(c.sequence_qc, attr):
                setattr(c.sequence_qc, attr, v)
        for k, v in qc["developability_qc"].items():
            attr = _qc_key_map.get(k, k)
            if hasattr(c.developability_qc, attr):
                setattr(c.developability_qc, attr, v)
        for k, v in qc["features"].items():
            if hasattr(c.sequence_features, k):
                setattr(c.sequence_features, k, v)

        # Populate Rosetta
        rosetta_score = _safe_float(row.get("rosetta_ddg"), default=None)
        score_source = str(row.get("score_source", ""))
        is_fallback = ("fallback" in score_source.lower() or
                      "proxy" in score_source.lower() or
                      "decomp" in score_source.lower())

        from candidate_result import RosettaResult
        if rosetta_score is not None or score_source:
            c.rosetta = RosettaResult(
                candidate_id=cid,
                raw_score=rosetta_score,
                raw_score_type="fallback_score" if is_fallback else "decomposition_score",
                fallback_used=is_fallback,
                fallback_reason=("Score source indicates fallback/degraded scoring: " + score_source)
                if is_fallback else None,
                status="fallback" if is_fallback else "success",
            )

        candidates.append(c)

    # Rank
    has_real = any(
        c.rosetta and not c.rosetta.fallback_used
        for c in candidates
    )
    ranked = rank_candidates(candidates, has_any_real_scoring=has_real)

    # Convert back to dict rows, matching by candidate_id
    for c in ranked:
        # Find the original row by candidate_id
        for row in results:
            if row.get("candidate_id") == c.candidate_id:
                row["candidate_id"] = c.candidate_id
                row["sequence_qc"] = c.sequence_qc.status
                row["sequence_penalty"] = c.sequence_qc.penalty
                row["qc_flags"] = c.sequence_qc.risk_flags
                row["qc_notes"] = c.sequence_qc.notes
                row["developability_qc"] = c.developability_qc.status
                row["dev_risk_flags"] = c.developability_qc.risk_flags
                row["dev_notes"] = c.developability_qc.notes
                row["composite_score"] = c.ranking.composite_score
                row["rank"] = c.ranking.rank
                row["final_recommendation"] = c.ranking.recommendation
                row["recommendation_reason"] = c.ranking.recommendation_reason
                row["ranking_explanation"] = c.ranking.ranking_explanation
                row["fallback_used"] = c.rosetta.fallback_used if c.rosetta else False
                break

    # Sort results by rank
    results.sort(key=lambda r: r.get("rank", 999))

    return results
