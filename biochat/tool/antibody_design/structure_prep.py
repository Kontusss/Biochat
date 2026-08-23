"""
Phase 3C-0: Structure readiness pre-screening.

Evaluates CDRH3 candidates for structural modeling feasibility BEFORE
any heavy computation (NanoBodyBuilder2, HDOCK, Rosetta) is attempted.
All checks are pure Python — no external dependencies.

Output explicitly labeled as uncalibrated computational predictions.
Never outputs Kd, ddG, binding affinity, or validated-binder claims.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

# ═══════════════════════════════════════════════════════════════
# Rule definitions
# ═══════════════════════════════════════════════════════════════

FORBIDDEN_RESIDUES = set("BJOXZ")          # non-standard, ambiguous
CATIONIC = set("KR")
ANIONIC = set("DE")
AROMATIC = set("FWYH")
HYDROPHOBIC_PATCH = set("AILMFVWY")
N_GLYC_MOTIF = "N"                         # N-X-[ST] pattern uses regex
VALID_AAS = set("ACDEFGHIKLMNPQRSTVWY")

CDRH3_ABS_MIN = 6
CDRH3_SOFT_MIN = 8
CDRH3_SOFT_MAX = 25
CDRH3_ABS_MAX = 30


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════

def check_structure_readiness(
    cdrh3_sequences: List[str],
    epitope: str = "",
) -> Dict[str, Any]:
    """Evaluate CDRH3 candidates for structural modeling readiness.

    Returns a dict with per-candidate readiness assessment and
    an overall pipeline-level summary.  All results are labeled
    as uncalibrated computational predictions.

    Args:
        cdrh3_sequences: List of CDRH3 amino acid sequences.
        epitope: Optional target epitope for context.

    Returns:
        {
            "candidates": [...],
            "structure_readiness": {overall summary},
            "export": {paths if written},
        }
    """
    candidates: List[Dict[str, Any]] = []
    overall_ready_count = 0
    overall_blocked_count = 0

    for i, seq in enumerate(cdrh3_sequences):
        seq = (seq or "").strip().upper()
        c = _assess_single(seq, i, epitope)
        candidates.append(c)
        if c["ready"]:
            overall_ready_count += 1
        else:
            overall_blocked_count += 1

    return {
        "candidates": candidates,
        "structure_readiness": {
            "ready": overall_blocked_count == 0,
            "total": len(cdrh3_sequences),
            "ready_count": overall_ready_count,
            "blocked_count": overall_blocked_count,
            "provenance": "computed",
            "source": "structure_prep.py:Phase3C-0",
            "calibration": "none",
            "disclaimer": (
                "All readiness checks are computational predictions. "
                "Structure-ready status does NOT imply experimental "
                "validation, binding affinity, or biological activity."
            ),
        },
    }


def export_fasta(
    cdrh3_sequences: List[str],
    epitope: str = "",
    filepath: str = "candidates.fasta",
) -> str:
    """Export CDRH3 candidates as a FASTA file. Returns the file path."""
    lines: List[str] = []
    for i, seq in enumerate(cdrh3_sequences, 1):
        seq = (seq or "").strip().upper()
        header = f">candidate_{i:03d}|CDRH3|len={len(seq)}"
        if epitope:
            header += f"|epitope={epitope}"
        lines.append(header)
        lines.append(seq)
    content = "\n".join(lines) + "\n"
    with open(filepath, "w") as fh:
        fh.write(content)
    return filepath


def export_readiness_json(
    readiness_result: Dict[str, Any],
    filepath: str = "structure_ready_candidates.json",
) -> str:
    """Export readiness assessment as JSON. Returns the file path."""
    with open(filepath, "w") as fh:
        json.dump(readiness_result, fh, indent=2, ensure_ascii=False)
    return filepath


# ═══════════════════════════════════════════════════════════════
# Per-candidate assessment
# ═══════════════════════════════════════════════════════════════

def _assess_single(seq: str, index: int, epitope: str) -> Dict[str, Any]:
    length = len(seq)
    warnings: List[str] = []
    blocking: List[str] = []
    metrics: Dict[str, Any] = {"length": length}

    # ── 1. Forbidden residues ────────────────────────────────
    forbidden = sorted({c for c in seq if c in FORBIDDEN_RESIDUES})
    if forbidden:
        blocking.append(f"forbidden_residues: {forbidden}")

    # ── 2. Length limits ─────────────────────────────────────
    if length < CDRH3_ABS_MIN:
        blocking.append(f"cdrh3_too_short: {length}aa < {CDRH3_ABS_MIN}")
    elif length > CDRH3_ABS_MAX:
        blocking.append(f"cdrh3_too_long: {length}aa > {CDRH3_ABS_MAX}")
    elif length < CDRH3_SOFT_MIN:
        warnings.append(f"cdrh3_below_soft_min: {length}aa < {CDRH3_SOFT_MIN}")
    elif length > CDRH3_SOFT_MAX:
        warnings.append(f"cdrh3_above_soft_max: {length}aa > {CDRH3_SOFT_MAX}")

    # ── 3. Cysteine count ────────────────────────────────────
    cys_count = seq.count("C")
    metrics["cysteine_count"] = cys_count
    if cys_count == 1:
        blocking.append("odd_cysteine_count: 1 unpaired Cys")
    elif cys_count > 1:
        if cys_count % 2 != 0:
            warnings.append(f"odd_cysteine_count: {cys_count} Cys (possible unpaired)")
        else:
            warnings.append(f"paired_cysteine: {cys_count} Cys (disulfide bond formation possible)")

    # ── 4. Poly-basic cluster (≥3 consecutive K/R) ────────────
    max_basic_run = _max_consecutive(seq, CATIONIC)
    metrics["max_basic_run"] = max_basic_run
    if max_basic_run >= 5:
        blocking.append(f"poly_basic_cluster: {max_basic_run} consecutive K/R")
    elif max_basic_run >= 3:
        warnings.append(f"poly_basic_run: {max_basic_run} consecutive K/R — may cause aggregation")

    # ── 5. Poly-acidic cluster (≥3 consecutive D/E) ──────────
    max_acidic_run = _max_consecutive(seq, ANIONIC)
    metrics["max_acidic_run"] = max_acidic_run
    if max_acidic_run >= 5:
        blocking.append(f"poly_acidic_cluster: {max_acidic_run} consecutive D/E")
    elif max_acidic_run >= 3:
        warnings.append(f"poly_acidic_run: {max_acidic_run} consecutive D/E")

    # ── 6. Excessive charge ──────────────────────────────────
    total_cationic = sum(1 for aa in seq if aa in CATIONIC)
    total_anionic = sum(1 for aa in seq if aa in ANIONIC)
    charge_ratio = (total_cationic + total_anionic) / length if length > 0 else 0
    metrics["charge_fraction"] = round(charge_ratio, 2)
    if charge_ratio > 0.5:
        warnings.append(f"high_charge_density: {charge_ratio:.0%} charged residues — may affect folding")

    # ── 7. Glycosylation motif (N-X-[ST], X≠P) ──────────────
    import re
    nglyc_matches = [(m.start() + 1, m.group())
                     for m in re.finditer(r'N[^P][ST]', seq)]
    metrics["n_glyc_motifs"] = len(nglyc_matches)
    if nglyc_matches:
        sites = ",".join(f"{pos}{motif}" for pos, motif in nglyc_matches)
        warnings.append(f"n_glycosylation_sites: {sites} — may interfere with expression")

    # ── 8. Hydrophobic patch (≥4 consecutive) ────────────────
    max_hydro_run = _max_consecutive(seq, HYDROPHOBIC_PATCH)
    metrics["max_hydrophobic_run"] = max_hydro_run
    if max_hydro_run >= 6:
        warnings.append(f"large_hydrophobic_patch: {max_hydro_run} consecutive hydrophobic — solubility risk")
    elif max_hydro_run >= 4:
        warnings.append(f"hydrophobic_patch: {max_hydro_run} consecutive hydrophobic")

    # ── 9. Aromatic patch (≥3 consecutive F/W/Y/H) ───────────
    max_aro_run = _max_consecutive(seq, AROMATIC)
    metrics["max_aromatic_run"] = max_aro_run
    if max_aro_run >= 3:
        warnings.append(f"aromatic_cluster: {max_aro_run} consecutive aromatic — π-stacking may bias folding")

    # ── 10. Low complexity ───────────────────────────────────
    from collections import Counter
    counts = Counter(seq)
    dominant_frac = max(counts.values()) / length if length > 0 else 0
    metrics["dominant_aa_fraction"] = round(dominant_frac, 2)
    if dominant_frac > 0.40:
        warnings.append(f"low_complexity: {max(counts, key=counts.get)} at {dominant_frac:.0%}")
    elif dominant_frac > 0.30:
        warnings.append(f"moderate_low_complexity: {max(counts, key=counts.get)} at {dominant_frac:.0%}")

    return {
        "index": index,
        "cdrh3_sequence": seq,
        "length": length,
        "ready": len(blocking) == 0,
        "warnings": warnings,
        "blocking_issues": blocking,
        "metrics": metrics,
        "provenance": "computed",
        "source": "structure_prep.py",
        "calibration": "none",
    }


def _max_consecutive(seq: str, allowed: set) -> int:
    """Return the longest consecutive run of amino acids in *allowed*."""
    max_run = 0
    cur = 0
    for aa in seq:
        if aa in allowed:
            cur += 1
            max_run = max(max_run, cur)
        else:
            cur = 0
    return max_run
