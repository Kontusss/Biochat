"""Fixed charge complementarity assessment for CDRH3 vs epitope.

Key rules:
- Epitope acidic (D/E) + CDRH3 basic (K/R/H) → complementary (NOT repulsive)
- Epitope acidic + CDRH3 acidic → electrostatic repulsion
- Epitope basic + CDRH3 basic → electrostatic repulsion
- Overly basic CDRH3 → possible non-specific binding
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict


ACIDIC = {"D", "E"}
BASIC = {"K", "R", "H"}


def assess_charge_complementarity(
    cdrh3: str,
    epitope: str,
    basic_threshold: int = 4,
    acidic_threshold: int = 3,
) -> Dict[str, Any]:
    """Assess charge complementarity between CDRH3 and epitope.

    Returns dict with:
        epitope_acidic_count: int
        epitope_basic_count: int
        cdrh3_acidic_count: int
        cdrh3_basic_count: int
        complementarity_type: str
        flags: list[str]
        notes: list[str]
    """
    seq = (cdrh3 or "").upper()
    epi = (epitope or "").upper()

    epi_counts = Counter(epi)
    cdrh3_counts = Counter(seq)

    epi_acidic = sum(epi_counts.get(aa, 0) for aa in ACIDIC)
    epi_basic = sum(epi_counts.get(aa, 0) for aa in BASIC)
    cdrh3_acidic = sum(cdrh3_counts.get(aa, 0) for aa in ACIDIC)
    cdrh3_basic = sum(cdrh3_counts.get(aa, 0) for aa in BASIC)

    flags = []
    notes = []

    # Determine complementarity type
    _has_repulsion = False
    _has_complement = False

    if epi_acidic >= acidic_threshold and cdrh3_acidic >= acidic_threshold:
        _has_repulsion = True
        flags.append("possible_electrostatic_repulsion")
        notes.append(
            f"Both epitope ({epi_acidic} D/E) and CDRH3 ({cdrh3_acidic} D/E) "
            "have multiple acidic residues — same-sign charge REPULSION possible."
        )

    if epi_basic >= basic_threshold and cdrh3_basic >= basic_threshold:
        _has_repulsion = True
        flags.append("possible_electrostatic_repulsion")
        notes.append(
            f"Both epitope ({epi_basic} K/R/H) and CDRH3 ({cdrh3_basic} K/R/H) "
            "have multiple basic residues — same-sign charge REPULSION possible."
        )

    if epi_acidic > 0 and cdrh3_basic > 0:
        _has_complement = True
        flags.append("potential_charge_complementarity")
        notes.append(
            f"Epitope has {epi_acidic} acidic residue(s) (D/E) and CDRH3 has "
            f"{cdrh3_basic} basic residue(s) (K/R/H) — this is "
            "CHARGE-COMPLEMENTARY (opposite charges attract), NOT repulsive."
        )

    if epi_basic >= basic_threshold and cdrh3_basic >= basic_threshold:
        flags.append("possible_electrostatic_repulsion")
        notes.append(
            f"Both epitope ({epi_basic} K/R/H) and CDRH3 ({cdrh3_basic} K/R/H) "
            "have multiple basic residues — same-sign charge REPULSION possible."
        )

    # Overly basic warning
    if cdrh3_basic > basic_threshold:
        flags.append("possible_nonspecific_binding")
        notes.append(
            f"CDRH3 has {cdrh3_basic} basic residues (K/R/H) which exceeds "
            f"threshold {basic_threshold} — may cause non-specific binding "
            "to negatively charged surfaces or nucleic acids."
        )

    if not flags:
        flags.append("neutral_or_balanced_charge")
        notes.append("No significant charge complementarity or repulsion detected.")

    return {
        "epitope_acidic_count": epi_acidic,
        "epitope_basic_count": epi_basic,
        "cdrh3_acidic_count": cdrh3_acidic,
        "cdrh3_basic_count": cdrh3_basic,
        "complementarity_type": (
            "repulsive" if _has_repulsion
            else "complementary" if _has_complement
            else "neutral"
        ),
        "flags": flags,
        "notes": notes,
    }
