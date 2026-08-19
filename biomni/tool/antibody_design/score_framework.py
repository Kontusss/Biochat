"""Universal scoring framework for antibody design.

Prevents proxy scores from being mislabeled as ddG or high-affinity conclusions.
All scores have explicit source, direction, calibration status, and gate level.

Target-agnostic: works for any epitope/antigen/target.
"""

from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from biomni.tool.antibody_design.artifact_schema import (
    ArtifactStatus,
    new_score_record,
    new_artifact_id,
    _hash_string,
    _utc_now_iso,
    ProvenanceManifest,
)


# ── Promotion gate levels ──────────────────────────────────────────────────
class PromotionGate(str, Enum):
    """Multi-stage gating: each stage reflects what the candidate is ready for.

    The gates are ordered by maturity — later gates imply earlier ones passed.
    Only PROMOTE_FOR_EXPRESSION_REVIEW means the candidate is ready for wet-lab.
    """
    # Early-stage
    RAW_CDRH3_PASS = "RAW_CDRH3_PASS"                       # CDRH3 passed sequence QC
    READY_FOR_VH_GRAFTING = "READY_FOR_VH_GRAFTING"        # CDRH3 + QC → can graft to VH
    VH_ASSEMBLED = "VH_ASSEMBLED"                           # Full VH variable domain ready
    VL_PAIRED_HEURISTIC = "VL_PAIRED_HEURISTIC"            # VH+VL paired (heuristic)
    INCOMPLETE_FOR_EXPRESSION = "INCOMPLETE_FOR_EXPRESSION" # Missing VL or other required components

    # Scoring-dependent
    PRELIMINARY_PROXY_ONLY = "PRELIMINARY_PROXY_ONLY"      # Only proxy scores — cannot promote
    REAL_SCORED = "REAL_SCORED"                              # Has real docking/Rosetta
    NO_PREDICTED_BINDING = "NO_PREDICTED_BINDING"           # Real scores unfavorable

    # Final
    PROMOTE_FOR_EXPRESSION_REVIEW = "PROMOTE_FOR_EXPRESSION_REVIEW"  # All gates passed
    DO_NOT_PROMOTE = "DO_NOT_PROMOTE"                       # Hard fail (sequence, developability)


# ── Score calibration ──────────────────────────────────────────────────────
class ScoreCalibration:
    """Tracks correlation between proxy and real scores across runs."""

    def __init__(self):
        self.pairs: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
        # proxy_mode -> [(proxy_score, real_score), ...]

    def add_pair(self, proxy_mode: str, proxy_score: float, real_score: float) -> None:
        self.pairs[proxy_mode].append((proxy_score, real_score))

    def spearman_rho(self, proxy_mode: str) -> Optional[float]:
        """Compute Spearman rank correlation for a proxy mode."""
        pairs = self.pairs.get(proxy_mode, [])
        if len(pairs) < 5:
            return None
        n = len(pairs)

        def rank(values):
            indexed = sorted(enumerate(values), key=lambda x: x[1])
            ranks = [0.0] * n
            for pos, (idx, _) in enumerate(indexed):
                ranks[idx] = pos
            return ranks

        proxy_ranks = rank([p[0] for p in pairs])
        real_ranks = rank([p[1] for p in pairs])

        d2 = sum((pr - rr) ** 2 for pr, rr in zip(proxy_ranks, real_ranks))
        rho = 1.0 - (6.0 * d2) / (n * (n**2 - 1))
        return round(rho, 4)

    def calibration_status(self, proxy_mode: str) -> str:
        """Determine calibration reliability."""
        rho = self.spearman_rho(proxy_mode)
        if rho is None:
            return "UNCALIBRATED"
        if abs(rho) < 0.3:
            return "UNRELIABLE_FOR_RANKING"
        if abs(rho) < 0.6:
            return "UNCALIBRATED"
        return "CALIBRATED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            mode: {
                "n_pairs": len(pairs),
                "spearman_rho": self.spearman_rho(mode),
                "calibration_status": self.calibration_status(mode),
            }
            for mode, pairs in self.pairs.items()
        }


# ── Score validation ───────────────────────────────────────────────────────
def is_real_score_source(score_source: str) -> bool:
    """Check if a score source represents real physical scoring."""
    src = str(score_source or "").lower()
    real_sources = {
        "rosetta_subprocess_decomp",
        "rosetta_subprocess_interface",
        "rosetta_inproc_decomp",
        "rosetta_shape_complementarity",
        "hdock",
        "hdock_docking_score",
    }
    return src in real_sources


def is_proxy_score_source(score_source: str) -> bool:
    """Check if a score source is a proxy/fast estimate."""
    src = str(score_source or "").lower()
    proxy_sources = {
        "proxy_sequence_fast",
        "proxy_contacts",
        "fold_failed_proxy",
        "sequence_screening",
    }
    return src in proxy_sources


def is_fallback_score_source(score_source: str) -> bool:
    """Check if a score source is a degraded fallback."""
    src = str(score_source or "").lower()
    return "fallback" in src or "default" in src or not src


def validate_score_sanity(score_value: float) -> Tuple[bool, List[str]]:
    """Check if a score value is physically reasonable.

    Returns (is_valid, flags). Non-fatal flags (like zero score) don't invalidate.
    """
    flags = []
    hard_fail = False
    if math.isnan(score_value):
        flags.append("SCORE_IS_NAN")
        hard_fail = True
    if math.isinf(score_value):
        flags.append("SCORE_IS_INF")
        hard_fail = True
    if abs(score_value) > 1e6:
        flags.append("SCORE_ABSOLUTELY_EXTREME")
        hard_fail = True
    if score_value == 0.0:
        flags.append("SCORE_IS_ZERO_POSSIBLE_DEFAULT")
    return not hard_fail, flags


def score_source_quality(score_source: str, candidate_status: str) -> float:
    """Return quality weight for a score source (0.0 to 1.0)."""
    st = str(candidate_status or "").lower()
    if st in {"failed", "degraded"}:
        return 0.1
    if is_real_score_source(score_source):
        return 1.0
    if is_proxy_score_source(score_source):
        return 0.72
    if is_fallback_score_source(score_source):
        return 0.25
    return 0.55


# ── Promotion gate logic ───────────────────────────────────────────────────
def determine_promotion_gate(
    scores: List[Dict[str, Any]],
    has_complete_vh: bool = False,
    has_complete_vl: bool = False,
    sequence_qc_status: str = "fail",
    developability_flags: Optional[List[str]] = None,
    has_real_docking: bool = False,
) -> Tuple[PromotionGate, str]:
    """Determine the promotion gate for a candidate.

    Multi-stage semantics:
    - CDRH3 only with QC pass → READY_FOR_VH_GRAFTING (not DO_NOT_PROMOTE)
    - Missing VL is not a hard fail; it's INCOMPLETE_FOR_EXPRESSION
    - Only VH+VL+real_score+QC+developability pass reaches PROMOTE_FOR_EXPRESSION_REVIEW

    Returns:
        (PromotionGate, rationale_string)
    """
    developability_flags = developability_flags or []

    # Gate 1: Sequence integrity (hard gate)
    if sequence_qc_status == "fail":
        return PromotionGate.DO_NOT_PROMOTE, "序列 QC 失败 — 存在硬性序列缺陷"

    # Gate 2: Check what stage we're at
    if not has_complete_vh:
        # CDRH3-only: passed QC but not yet assembled into VH
        if sequence_qc_status in ("pass", "warning"):
            return PromotionGate.READY_FOR_VH_GRAFTING, (
                "CDRH3 通过序列 QC，可进入 VH framework grafting"
            )
        return PromotionGate.RAW_CDRH3_PASS, "CDRH3 基本通过，建议进入装配"

    if not has_complete_vl:
        # Has VH but no VL: cannot be called complete IgG, but this is expected mid-pipeline
        return PromotionGate.INCOMPLETE_FOR_EXPRESSION, (
            "VH 已装配，VL 缺失 — 不可称完整 IgG。需 VL pairing 后进入评分。"
        )

    # Below here: complete VH+VL
    # Gate 3: Developability hard liabilities
    hard_liabilities = {
        "poly_", "excessive_single_aa", "excessive_aromatic",
        "low_complexity_entropy", "odd_cysteine", "invalid_amino_acid",
        "empty_sequence",
    }
    has_hard_liability = any(
        any(liab in flag for liab in hard_liabilities)
        for flag in developability_flags
    )
    if has_hard_liability:
        return PromotionGate.DO_NOT_PROMOTE, f"硬性可开发性风险: {developability_flags}"

    # Gate 4: Scoring level
    if not has_real_docking:
        return PromotionGate.PRELIMINARY_PROXY_ONLY, (
            "VH+VL 已装配但仅有代理评分 — 不可推荐表达。需真实对接/Rosetta 验证。"
        )

    # Gate 5: Real score evaluation
    real_scores = [s for s in scores if is_real_score_source(s.get("score_source", ""))]
    if real_scores:
        has_favorable = False
        for s in real_scores:
            value = s.get("score_value", float("inf"))
            direction = s.get("score_direction", "lower_is_better")
            if direction == "lower_is_better" and value < 0:
                has_favorable = True
            elif direction == "higher_is_better" and value > 0:
                has_favorable = True

        if not has_favorable:
            all_positive = all(
                s.get("score_value", 0) > 100
                for s in real_scores
                if s.get("score_direction") == "lower_is_better"
            )
            if all_positive:
                return PromotionGate.NO_PREDICTED_BINDING, (
                    "真实物理评分均为正值，预测无高亲和力结合"
                )

    # Gate 6: All clear for expression review
    soft_warnings = [f for f in developability_flags
                     if not any(liab in f for liab in hard_liabilities)]
    if soft_warnings:
        return PromotionGate.PROMOTE_FOR_EXPRESSION_REVIEW, (
            f"通过所有 gate — 可推荐表达评审。软性警告: {soft_warnings}"
        )

    return PromotionGate.PROMOTE_FOR_EXPRESSION_REVIEW, "通过所有 gate — 可推荐表达评审"


# ── Composite score (only within same calibration context) ─────────────────
def compute_composite_score(
    ddg_rank_score: float,
    developability_score: float,
    qc_bonus: float,
    score_source_quality: float,
    flag_penalty: float = 0.0,
) -> float:
    """Compute composite score from normalized components.

    IMPORTANT: This is ONLY for comparison within the same calibration context.
    Cross-mode comparison is not valid.
    """
    composite = (
        0.48 * ddg_rank_score
        + 0.30 * developability_score
        + 0.17 * score_source_quality
        + 0.05 * max(0.0, 1.0 - flag_penalty)
    )
    return round(composite * 100, 2)


# ── Final recommendation ───────────────────────────────────────────────────
def final_recommendation(
    candidates: List[Dict[str, Any]],
    manifest: Optional[ProvenanceManifest] = None,
) -> Dict[str, Any]:
    """Generate final recommendation with mandatory caveats.

    Never produces "high affinity" claims without real scoring.
    """
    if not candidates:
        return {
            "recommendation": "NO_CANDIDATES",
            "rationale": "未生成任何候选。",
            "top_candidate": None,
            "caveats": ["NO_CANDIDATES_PRODUCED"],
        }

    top = candidates[0]
    gate = top.get("promotion_gate", PromotionGate.DO_NOT_PROMOTE)

    has_real = manifest.has_real_scoring() if manifest else False
    has_igg = manifest.has_complete_igg() if manifest else False

    caveats = []
    if not has_real:
        caveats.append("PRELIMINARY_PROXY_ONLY: 基于代理评分，不可声称高亲和力。")
    if not has_igg:
        caveats.append("NO_COMPLETE_IGG: 缺少完整 VH+VL。")
    if top.get("sequence_qc") == "warning":
        caveats.append("SEQUENCE_QC_WARNING: Top 候选存在序列质量警告。")

    if gate == PromotionGate.PROMOTE_FOR_EXPRESSION_REVIEW:
        rec = "PROMOTE_FOR_EXPRESSION_REVIEW"
        rationale = "Top 候选通过所有 gate，可进入表达评审。"
    elif gate == PromotionGate.NO_PREDICTED_BINDING:
        rec = "NO_PREDICTED_BINDING"
        rationale = "真实评分表明无预测结合 — 不建议表达。"
    elif gate == PromotionGate.PRELIMINARY_PROXY_ONLY:
        rec = "PRELIMINARY_ONLY"
        rationale = "仅有代理评分，不可进入表达 — 需真实对接验证。"
    else:
        rec = "DO_NOT_PROMOTE"
        rationale = "候选未通过关键 gate — 不可推荐。"

    return {
        "recommendation": rec,
        "rationale": rationale,
        "top_candidate_id": top.get("candidate_id", ""),
        "top_cdrh3": top.get("cdrh3", ""),
        "top_composite_score": top.get("composite_score", 0.0),
        "promotion_gate": gate,
        "total_candidates": len(candidates),
        "has_real_scoring": has_real,
        "has_complete_igg": has_igg,
        "caveats": caveats,
    }


# ── Score report for candidates ────────────────────────────────────────────
def score_candidate(
    candidate_id: str,
    cdrh3: str,
    full_vh: str = "",
    full_vl: str = "",
    proxy_score: Optional[float] = None,
    real_ddg: Optional[float] = None,
    score_source: str = "unknown",
    sequence_qc: Dict[str, Any] = None,
    developability_flags: Optional[List[str]] = None,
    has_real_docking: bool = False,
) -> Dict[str, Any]:
    """Score a single candidate and determine its promotion gate.

    This is the unified entry point for candidate scoring.
    """
    sequence_qc = sequence_qc or {}
    developability_flags = developability_flags or []

    scores = []

    if proxy_score is not None:
        scores.append(new_score_record(
            score_name="proxy_score",
            score_value=proxy_score,
            score_unit="arbitrary",
            score_direction="lower_is_better",
            score_source=score_source if is_proxy_score_source(score_source) else "proxy_sequence_fast",
            calibration_status="UNCALIBRATED",
            candidate_id=candidate_id,
        ))

    if real_ddg is not None and is_real_score_source(score_source):
        scores.append(new_score_record(
            score_name="rosetta_ddg",
            score_value=real_ddg,
            score_unit="REU",
            score_direction="lower_is_better",
            score_source=score_source,
            calibration_status="CALIBRATED",
            candidate_id=candidate_id,
        ))

    has_vh = len(full_vh) >= 90 and "WGQG" in full_vh[-10:]
    has_vl = len(full_vl) >= 85 and any(m in full_vl[-10:] for m in ("FGQG", "FGQGT", "FGGGT"))

    gate, gate_rationale = determine_promotion_gate(
        scores=scores,
        has_complete_vh=has_vh,
        has_complete_vl=has_vl,
        sequence_qc_status=sequence_qc.get("status", "fail"),
        developability_flags=developability_flags,
        has_real_docking=has_real_docking,
    )

    return {
        "candidate_id": candidate_id,
        "cdrh3": cdrh3,
        "full_vh": full_vh,
        "full_vl": full_vl,
        "has_complete_vh": has_vh,
        "has_complete_vl": has_vl,
        "scores": scores,
        "sequence_qc": sequence_qc,
        "developability_flags": developability_flags,
        "promotion_gate": gate,
        "gate_rationale": gate_rationale,
    }
