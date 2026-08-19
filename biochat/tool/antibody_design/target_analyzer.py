"""Universal target analyzer — automatically classifies any target input
and selects priors, filters, and scoring strategies.

Target-agnostic: works for peptides, proteins, surface patches, and unknown targets.
Replaces hardcoded per-epitope logic with data-driven target profiling.
"""

from __future__ import annotations

# DEPRECATED: """DEPRECATED: 靶点分析功能已由 autonomous_research.py 内联替代。"""

import json
import math
import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from biochat.tool.antibody_design.artifact_schema import TargetType, new_artifact_id, _hash_string, _utc_now_iso

# ── Constants ──────────────────────────────────────────────────────────────
VALID_AAS = set("ACDEFGHIKLMNPQRSTVWY")
HYDROPHOBIC = set("AILMFWV")
POLAR = set("STNQY")
AROMATIC = set("FWY")
POSITIVE = set("KRH")
NEGATIVE = set("DE")
DISORDER_PROMOTING = set("PEGSKQN")


@dataclass
class TargetProfile:
    """Complete analysis of an antibody design target."""

    target_id: str = ""
    target_type: TargetType = TargetType.UNKNOWN
    input_type: str = ""  # "sequence" | "structure_file" | "mixed"

    # Sequence properties (when applicable)
    sequence: str = ""
    length: int = 0
    hydrophobic_fraction: float = 0.0
    polar_fraction: float = 0.0
    aromatic_fraction: float = 0.0
    net_charge: float = 0.0
    cysteine_count: int = 0
    glycine_proline_fraction: float = 0.0
    disorder_propensity: float = 0.0
    low_complexity: bool = False

    # Structure properties (when available)
    structure_path: str = ""
    structure_chain_count: int = 0
    structure_residue_count: int = 0
    surface_accessibility_available: bool = False

    # CDRH3 design priors
    recommended_cdrh3_min: int = 8
    recommended_cdrh3_max: int = 22
    recommended_cdrh3_typical: int = 14
    hard_cdrh3_min: int = 6
    hard_cdrh3_max: int = 32
    length_distribution_mode: str = "normal"  # "normal" | "uniform" | "bimodal"

    # Developability constraints (derived from target properties)
    max_allowed_hydrophobic: float = 0.45
    max_allowed_aromatic: float = 0.40
    max_allowed_charge_magnitude: float = 6.0
    charge_complement_required: bool = True
    max_poly_run: int = 3
    max_single_aa_fraction: float = 0.25

    # Scoring strategy
    preferred_scoring_mode: str = "auto"  # "auto" | "proxy" | "real" | "hybrid"
    requires_structure_context: bool = False
    requires_capping: bool = False  # N-term acetylation / C-term amidation for peptides

    # Caveats
    caveats: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)


def _fraction(seq: str, alphabet: set) -> float:
    if not seq:
        return 0.0
    return round(sum(1 for c in seq if c in alphabet) / len(seq), 4)


def _compute_disorder_propensity(seq: str) -> float:
    """Simple disorder propensity based on amino acid composition."""
    if not seq:
        return 0.0
    return round(sum(1 for c in seq if c in DISORDER_PROMOTING) / len(seq), 4)


def _detect_low_complexity(seq: str) -> bool:
    """Detect low-complexity regions using Shannon entropy."""
    if not seq or len(seq) < 3:
        return False
    counts = Counter(seq)
    length = len(seq)
    n_unique = len(set(seq))
    if n_unique <= 1:
        return True  # all same residue = low complexity
    if n_unique <= 2 and length >= 8:
        return True  # e.g., AAAAAGGGGG
    entropy = 0.0
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    denom = math.log2(min(20, n_unique))
    if denom < 1e-9:
        return True
    entropy_norm = entropy / denom
    return entropy_norm < 0.55


def _net_charge_from_seq(seq: str) -> float:
    counts = Counter(seq)
    return counts["K"] + counts["R"] + 0.1 * counts["H"] - counts["D"] - counts["E"]


def _classify_target_type(sequence: str, has_structure: bool,
                           length: int, input_type: str = "sequence") -> TargetType:
    """Classify target based on length, structure context, and input type."""
    if length <= 0:
        return TargetType.UNKNOWN
    # PDB file input → full_protein regardless of extracted sequence length
    if input_type == "structure_file":
        return TargetType.FULL_PROTEIN
    if length <= 12:
        return TargetType.SHORT_PEPTIDE
    if length <= 30:
        return TargetType.MEDIUM_PEPTIDE
    if length > 30:
        return TargetType.FULL_PROTEIN
    return TargetType.UNKNOWN


def _derive_cdrh3_priors(profile: TargetProfile) -> None:
    """Set CDRH3 length priors based on target type and properties."""
    tt = profile.target_type

    if tt == TargetType.SHORT_PEPTIDE:
        profile.recommended_cdrh3_min = 8
        profile.recommended_cdrh3_max = 16
        profile.recommended_cdrh3_typical = 12
        profile.hard_cdrh3_max = 22
        profile.length_distribution_mode = "normal"
    elif tt == TargetType.MEDIUM_PEPTIDE:
        profile.recommended_cdrh3_min = 10
        profile.recommended_cdrh3_max = 20
        profile.recommended_cdrh3_typical = 15
        profile.hard_cdrh3_max = 25
        profile.length_distribution_mode = "normal"
    elif tt == TargetType.PROTEIN_PATCH:
        profile.recommended_cdrh3_min = 10
        profile.recommended_cdrh3_max = 24
        profile.recommended_cdrh3_typical = 17
        profile.hard_cdrh3_max = 26
        profile.length_distribution_mode = "bimodal"
    elif tt == TargetType.FULL_PROTEIN:
        profile.recommended_cdrh3_min = 10
        profile.recommended_cdrh3_max = 24
        profile.recommended_cdrh3_typical = 17
        profile.hard_cdrh3_max = 26
        profile.length_distribution_mode = "uniform"
    else:  # UNKNOWN
        profile.recommended_cdrh3_min = 9
        profile.recommended_cdrh3_max = 18
        profile.recommended_cdrh3_typical = 14
        profile.hard_cdrh3_max = 22
        profile.length_distribution_mode = "normal"
        profile.caveats.append("UNKNOWN_TARGET_TYPE: 使用保守 CDRH3 长度先验。")

    # Adjust based on target hydrophobicity
    if profile.hydrophobic_fraction > 0.5:
        profile.recommended_cdrh3_min = max(profile.recommended_cdrh3_min, 10)
        profile.caveats.append("HIGH_TARGET_HYDROPHOBICITY: 可能需要更长 CDRH3 以形成充分界面。")

    # Adjust based on target charge
    if abs(profile.net_charge) > 4:
        profile.max_allowed_charge_magnitude = min(8.0, abs(profile.net_charge) + 3)
        profile.charge_complement_required = True
        profile.caveats.append("HIGH_TARGET_CHARGE: 要求 CDRH3 电荷互补以避免排斥。")


def _derive_developability_constraints(profile: TargetProfile) -> None:
    """Set developability filters based on target properties."""
    if profile.target_type == TargetType.SHORT_PEPTIDE:
        profile.max_allowed_hydrophobic = 0.42
    elif profile.hydrophobic_fraction > 0.4:
        profile.max_allowed_hydrophobic = 0.48
    else:
        profile.max_allowed_hydrophobic = 0.45

    if profile.cysteine_count > 0:
        profile.caveats.append("TARGET_CONTAINS_CYS: 可能需要考虑二硫键配对设计。")

    if profile.low_complexity:
        profile.caveats.append("LOW_COMPLEXITY_TARGET: 靶标自身复杂度低，可能导致非特异性结合。")


def _derive_scoring_strategy(profile: TargetProfile) -> None:
    """Select scoring strategy based on target characteristics."""
    if profile.target_type == TargetType.SHORT_PEPTIDE:
        profile.preferred_scoring_mode = "hybrid"
        profile.requires_capping = True
        profile.caveats.append(
            "LINEAR_PEPTIDE_ONLY: 短肽可能无法代表天然蛋白构象。"
            "若目标是蛋白表面识别，标记为 STRUCTURAL_CONTEXT_MISSING。"
        )
    elif profile.target_type == TargetType.MEDIUM_PEPTIDE:
        profile.preferred_scoring_mode = "hybrid"
        profile.requires_capping = True
    elif profile.target_type in (TargetType.PROTEIN_PATCH, TargetType.FULL_PROTEIN):
        profile.preferred_scoring_mode = "real"
        profile.requires_structure_context = True
        if not profile.structure_path:
            profile.caveats.append("STRUCTURAL_CONTEXT_MISSING: 需要抗原结构进行可信评分。")
            profile.flags.append("STRUCTURAL_CONTEXT_MISSING")
    else:
        profile.preferred_scoring_mode = "proxy"
        profile.caveats.append("UNKNOWN_TARGET: 仅代理评分可用。")

    if not profile.requires_structure_context and profile.target_type == TargetType.SHORT_PEPTIDE:
        profile.flags.append("NATIVE_PROTEIN_BINDING_UNVERIFIED")


def analyze_target(
    target_input: str,
    structure_path: str = "",
    target_id: str = "",
) -> TargetProfile:
    """Analyze any target input and return a complete TargetProfile.

    Args:
        target_input: Amino acid sequence (required). May also be a path to a
                      FASTA or PDB file — auto-detected.
        structure_path: Optional path to antigen structure (PDB).
        target_id: Optional identifier for the target.

    Returns:
        TargetProfile with all derived priors, constraints, and caveats.
    """
    profile = TargetProfile(target_id=target_id or f"target_{new_artifact_id()}")

    # Detect input type
    cleaned = (target_input or "").strip()
    if os.path.isfile(cleaned):
        profile.input_type = "structure_file"
        profile.structure_path = cleaned
        # Try to extract sequence from PDB (basic)
        seq_chars = []
        try:
            with open(cleaned) as f:
                for line in f:
                    if line.startswith("ATOM") and line[13:15].strip() == "CA":
                        res = line[17:20].strip()
                        aa_map = {
                            "ALA": "A", "CYS": "C", "ASP": "D", "GLU": "E", "PHE": "F",
                            "GLY": "G", "HIS": "H", "ILE": "I", "LYS": "K", "LEU": "L",
                            "MET": "M", "ASN": "N", "PRO": "P", "GLN": "Q", "ARG": "R",
                            "SER": "S", "THR": "T", "VAL": "V", "TRP": "W", "TYR": "Y",
                        }
                        aa = aa_map.get(res, "X")
                        if aa in VALID_AAS:
                            seq_chars.append(aa)
            profile.sequence = "".join(seq_chars)
        except Exception:
            profile.sequence = ""
    else:
        profile.input_type = "sequence"
        # Check if it's a valid AA sequence
        invalid = sorted(set(cleaned.upper()) - VALID_AAS)
        if invalid:
            profile.caveats.append(f"INVALID_AMINO_ACIDS: {''.join(invalid)}")
            profile.flags.append("INVALID_INPUT")
            return profile
        profile.sequence = cleaned.upper()

    # Compute sequence properties
    seq = profile.sequence
    profile.length = len(seq)
    if profile.length > 0:
        profile.hydrophobic_fraction = _fraction(seq, HYDROPHOBIC)
        profile.polar_fraction = _fraction(seq, POLAR)
        profile.aromatic_fraction = _fraction(seq, AROMATIC)
        profile.net_charge = _net_charge_from_seq(seq)
        profile.cysteine_count = seq.count("C")
        profile.glycine_proline_fraction = _fraction(seq, set("GP"))
        profile.disorder_propensity = _compute_disorder_propensity(seq)
        profile.low_complexity = _detect_low_complexity(seq)

    # Structure info
    if structure_path and os.path.isfile(structure_path):
        profile.structure_path = structure_path
        profile.requires_structure_context = True
        # Quick count
        try:
            chains = set()
            res_count = 0
            with open(structure_path) as f:
                for line in f:
                    if line.startswith("ATOM"):
                        chains.add(line[21].strip())
                        res_count += 1
            profile.structure_chain_count = len(chains)
            profile.structure_residue_count = res_count
            profile.surface_accessibility_available = True
        except Exception:
            pass

    # Classify target type
    profile.target_type = _classify_target_type(
        profile.sequence,
        bool(profile.structure_path),
        profile.length,
        input_type=profile.input_type,
    )

    # Derive priors and constraints
    _derive_cdrh3_priors(profile)
    _derive_developability_constraints(profile)
    _derive_scoring_strategy(profile)

    # Specific flag for short peptides in protein context
    if profile.target_type in (TargetType.SHORT_PEPTIDE, TargetType.MEDIUM_PEPTIDE) and \
       not profile.structure_path:
        profile.flags.append("NATIVE_PROTEIN_BINDING_UNVERIFIED")

    return profile


def target_profile_to_dict(profile: TargetProfile) -> Dict[str, Any]:
    """Serialize TargetProfile to JSON-compatible dict."""
    return {
        "target_id": profile.target_id,
        "target_type": profile.target_type.value,
        "input_type": profile.input_type,
        "sequence": profile.sequence,
        "length": profile.length,
        "hydrophobic_fraction": profile.hydrophobic_fraction,
        "polar_fraction": profile.polar_fraction,
        "aromatic_fraction": profile.aromatic_fraction,
        "net_charge": profile.net_charge,
        "cysteine_count": profile.cysteine_count,
        "glycine_proline_fraction": profile.glycine_proline_fraction,
        "disorder_propensity": profile.disorder_propensity,
        "low_complexity": profile.low_complexity,
        "structure_path": profile.structure_path,
        "structure_chain_count": profile.structure_chain_count,
        "structure_residue_count": profile.structure_residue_count,
        "cdrh3_priors": {
            "recommended_min": profile.recommended_cdrh3_min,
            "recommended_max": profile.recommended_cdrh3_max,
            "recommended_typical": profile.recommended_cdrh3_typical,
            "hard_min": profile.hard_cdrh3_min,
            "hard_max": profile.hard_cdrh3_max,
            "length_distribution_mode": profile.length_distribution_mode,
        },
        "developability_constraints": {
            "max_allowed_hydrophobic": profile.max_allowed_hydrophobic,
            "max_allowed_aromatic": profile.max_allowed_aromatic,
            "max_allowed_charge_magnitude": profile.max_allowed_charge_magnitude,
            "charge_complement_required": profile.charge_complement_required,
            "max_poly_run": profile.max_poly_run,
            "max_single_aa_fraction": profile.max_single_aa_fraction,
        },
        "scoring_strategy": {
            "preferred_mode": profile.preferred_scoring_mode,
            "requires_structure_context": profile.requires_structure_context,
            "requires_capping": profile.requires_capping,
        },
        "caveats": profile.caveats,
        "flags": profile.flags,
    }


def save_target_analysis(profile: TargetProfile, output_dir: str) -> str:
    """Save target analysis as structured artifact."""
    data = {
        "artifact_id": new_artifact_id(),
        "timestamp": _utc_now_iso(),
        "input_hash": _hash_string(profile.sequence),
        "analysis": target_profile_to_dict(profile),
    }
    path = os.path.join(output_dir, "target_analysis.json")
    os.makedirs(output_dir, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path
