"""CDRH3 generation filter — constrains de novo designs before expensive scoring.

Rules prevent candidates with obvious liabilities from entering HDOCK/Rosetta.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

VALID_AAS = set("ACDEFGHIKLMNPQRSTVWY")
AROMATIC = set("FWY")
HYDROPHOBIC_AROMATIC = set("AILMFVWY")
ACIDIC = set("DE")
BASIC = set("KRH")

# ── Thresholds, calibrated against real antibodies ───────────────────────────
# Derived from 257 CDR-H3s extracted from the PDB (26 approved therapeutic
# antibodies + 231 antibody heavy chains) — see
# reports/antibody_benchmark_dataset.csv and scripts/run_antibody_benchmark.py.
#
# The soft-penalty thresholds sit at the P90 of that distribution, so they flag
# the most extreme ~10% of real antibodies rather than the majority.  The hard
# allowed range spans the full observed range: an approved drug is by
# definition developable, so no approved CDR-H3 may be hard-excluded.
#
# Previous values flagged the norm rather than the outlier:
#   preferred 13-16 covered only 24.1% of real antibodies (76% penalised)
#   aromatic  >0.30 fired on 45.9% of them (the real median is exactly 0.300)
PREFERRED_MIN_LEN = 8       # P10 of real CDR-H3 length (was 13)
PREFERRED_MAX_LEN = 16      # P90 (was 16); window now covers 80.5%
ALLOWED_MIN_LEN = 4         # observed minimum — nivolumab's CDR-H3 is 4aa (was 6)
ALLOWED_MAX_LEN = 32        # observed maximum (was 26)
AROMATIC_FRACTION_MAX = 0.45      # P90, fires on 10.1% (was 0.30 → 45.9%)
SINGLE_AROMATIC_FRACTION_MAX = 0.36   # P90, fires on 9.7% (was 0.25 → 27.2%)


# ── Filter function ──────────────────────────────────────────────────────────

def filter_cdrh3_design(
    cdrh3: str,
    epitope: str,
    preferred_min_len: int = PREFERRED_MIN_LEN,
    preferred_max_len: int = PREFERRED_MAX_LEN,
    allowed_min_len: int = ALLOWED_MIN_LEN,
    allowed_max_len: int = ALLOWED_MAX_LEN,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Filter a CDRH3 design for hard and soft quality issues.

    Returns:
        (accepted, flags, metrics)
        accepted: True if candidate should proceed to scoring
        flags: list of rejection/warning reasons
        metrics: dict with quantitative measurements
    """
    seq = (cdrh3 or "").strip().upper()
    epi = (epitope or "").strip().upper()
    flags = []
    hard_fail = False
    metrics: Dict[str, Any] = {}

    length = len(seq)
    metrics["length"] = length

    # ── Hard fails ───────────────────────────────────────────────────────
    # Extra Cys
    cys_count = seq.count("C")
    metrics["cys_count"] = cys_count
    if cys_count > 0:
        hard_fail = True
        flags.append("extra_Cys_in_CDRH3")

    # Allowed length range
    if length < allowed_min_len:
        hard_fail = True
        flags.append("cdrh3_length_out_of_allowed_range")
        metrics["length_violation"] = f"too_short_{length}"
    elif length > allowed_max_len:
        hard_fail = True
        flags.append("cdrh3_length_out_of_allowed_range")
        metrics["length_violation"] = f"too_long_{length}"

    # Non-canonical amino acids
    invalid = sorted(set(seq) - VALID_AAS)
    if invalid:
        hard_fail = True
        flags.append("noncanonical_amino_acid")
        metrics["invalid_chars"] = invalid

    # N-glycosylation motif
    if re.search(r"N[^P][ST]", seq):
        hard_fail = True
        flags.append("nglyc_motif_in_CDRH3")

    # ── Warnings / penalties ─────────────────────────────────────────────
    # Length outside preferred window
    if not hard_fail and (length < preferred_min_len or length > preferred_max_len):
        flags.append("cdrh3_length_outside_preferred_window")

    # Aromatic fraction above the calibrated P90
    aromatic_count = sum(1 for c in seq if c in AROMATIC)
    aromatic_frac = aromatic_count / length if length else 0
    metrics["aromatic_fraction"] = round(aromatic_frac, 3)
    if aromatic_frac > AROMATIC_FRACTION_MAX:
        flags.append("high_aromatic_fraction")

    # A single aromatic residue over-represented beyond the calibrated P90
    for aa in sorted(AROMATIC):
        frac = seq.count(aa) / length if length else 0
        if frac > SINGLE_AROMATIC_FRACTION_MAX:
            flags.append(f"high_single_{aa}_fraction")
            break

    # Electrostatic repulsion with acidic epitope
    epi_acidic = sum(1 for c in epi if c in ACIDIC)
    cdrh3_acidic = sum(1 for c in seq if c in ACIDIC)
    cdrh3_basic = sum(1 for c in seq if c in BASIC)
    metrics["epitope_acidic_count"] = epi_acidic
    metrics["cdrh3_acidic_count"] = cdrh3_acidic
    metrics["cdrh3_basic_count"] = cdrh3_basic

    if epi_acidic > 0 and cdrh3_acidic > 0:
        flags.append("possible_electrostatic_repulsion")

    # Missing basic residue for acidic epitope
    if epi_acidic > 0 and cdrh3_basic == 0:
        flags.append("missing_basic_residue_for_acidic_epitope")

    # Hydrophobic/aromatic cluster >= 4
    max_run = 0
    current_run = 0
    for c in seq:
        if c in HYDROPHOBIC_AROMATIC:
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 0
    metrics["max_hydrophobic_aromatic_run"] = max_run
    if max_run >= 4:
        flags.append("hydrophobic_aromatic_cluster")

    return (not hard_fail), list(dict.fromkeys(flags)), metrics


def generation_filter_summary(
    accepted: int, rejected: int, attempts: int,
    rejection_reasons: Dict[str, int],
) -> Dict[str, Any]:
    """Build a generation filter summary for audit logs."""
    return {
        "attempts": attempts,
        "rejected": rejected,
        "accepted": accepted,
        "acceptance_rate": round(accepted / attempts, 3) if attempts else 0.0,
        "rejection_reasons": rejection_reasons,
    }
