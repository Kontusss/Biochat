"""Validation: anti-copy rules, epitope validation, charge complementarity."""

from typing import Any, Dict, List

from biochat.tool.antibody_design.schemas import VALID_AAS, PENALTY_TABLE


def validate_epitope(epitope: str) -> tuple[bool, str]:
    """Return (is_valid, error_message)."""
    if not epitope or not epitope.strip():
        return False, "empty_epitope"
    epi = epitope.strip().upper()
    invalid = sorted(set(c for c in epi if c not in VALID_AAS))
    if invalid:
        return False, f"invalid_amino_acids: {invalid}"
    if len(epi) < 3:
        return False, f"epitope_too_short: {len(epi)}aa (min 3)"
    if len(epi) > 24:
        return False, f"epitope_too_long: {len(epi)}aa (max 24)"
    return True, ""


def check_epitope_copy(cdrh3: str, epitope: str) -> List[Dict[str, Any]]:
    """Detect CDRH3 copy of epitope (full or partial ≥4aa)."""
    penalties: List[Dict[str, Any]] = []
    if not cdrh3 or not epitope:
        return penalties

    c_up = cdrh3.upper()
    e_up = epitope.upper()

    if e_up in c_up:
        penalties.append(_make_penalty("contains_full_epitope_subsequence"))

    for i in range(len(e_up) - 3):
        if e_up[i:i + 4] in c_up:
            p = _make_penalty("contains_long_epitope_subsequence")
            p["detail"] = f"matched_substring: {e_up[i:i+4]}"
            penalties.append(p)
            break
    return penalties


def assess_charge_complementarity(
    cdrh3: str, epitope: str,
    basic_threshold: int = 4, acidic_threshold: int = 3,
) -> Dict[str, Any]:
    """Assess charge complementarity between CDRH3 and epitope."""
    BASIC = set("KRH")
    ACIDIC = set("DE")

    e_acidic = sum(1 for aa in epitope.upper() if aa in ACIDIC)
    e_basic = sum(1 for aa in epitope.upper() if aa in BASIC)
    c_acidic = sum(1 for aa in cdrh3.upper() if aa in ACIDIC)
    c_basic = sum(1 for aa in cdrh3.upper() if aa in BASIC)

    flags: List[str] = []
    notes: List[str] = []

    if e_acidic >= acidic_threshold and c_basic < 1:
        flags.append("missing_basic_residue_for_acidic_epitope")
        notes.append(f"Epitope has {e_acidic} acidic residues but CDRH3 has 0 basic")
    if e_basic >= basic_threshold and c_acidic < 1:
        flags.append("missing_acidic_residue_for_basic_epitope")
        notes.append(f"Epitope has {e_basic} basic residues but CDRH3 has 0 acidic")

    if e_acidic > 0 and c_basic > 0:
        ctype = "complementary"
    elif e_basic > 0 and c_acidic > 0:
        ctype = "complementary"
    elif e_acidic > 0 and c_basic == 0:
        ctype = "repulsive"
    elif e_basic > 0 and c_acidic == 0:
        ctype = "repulsive"
    elif c_acidic + c_basic == 0 and e_acidic + e_basic == 0:
        ctype = "neutral"
    else:
        ctype = "partially_complementary"

    return {
        "complementarity_type": ctype,
        "epitope_acidic_count": e_acidic,
        "epitope_basic_count": e_basic,
        "cdrh3_acidic_count": c_acidic,
        "cdrh3_basic_count": c_basic,
        "flags": flags,
        "notes": notes,
    }


def charge_bonus(cc: Dict[str, Any]) -> float:
    """Convert charge assessment to bonus score (0–15)."""
    ctype = str(cc.get("complementarity_type", "neutral")).lower()
    return {"complementary": 15.0, "partially_complementary": 8.0,
            "neutral": 5.0, "repulsive": 0.0}.get(ctype, 5.0)


def _make_penalty(flag: str) -> Dict[str, Any]:
    info = PENALTY_TABLE.get(flag, ("WARNING", 2, flag))
    return {
        "flag": flag, "level": info[0], "deduction": info[1],
        "explanation": info[2],
        "source": "validators.py:penalty_table", "provenance": "computed",
    }
