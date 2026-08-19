"""Short peptide epitope contact analysis for antibody docking.

Validates that docked antibody/CDRH3 actually contacts the epitope, not just
binds elsewhere on the antigen surface. Essential for short peptide (≤8 aa)
targets where docking false positives are common.

No external dependency beyond stdlib — uses lightweight PDB parsing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


# ── Amino acid property tables ───────────────────────────────────────────────
_AA3TO1 = {
    "ALA": "A", "CYS": "C", "ASP": "D", "GLU": "E", "PHE": "F",
    "GLY": "G", "HIS": "H", "ILE": "I", "LYS": "K", "LEU": "L",
    "MET": "M", "ASN": "N", "PRO": "P", "GLN": "Q", "ARG": "R",
    "SER": "S", "THR": "T", "VAL": "V", "TRP": "W", "TYR": "Y",
}

_ACIDIC = {"D", "E"}
_BASIC = {"K", "R", "H"}
_AROMATIC = {"W", "F", "Y", "H"}
_HYDROPHOBIC = {"A", "V", "L", "I", "M", "P", "F", "W", "Y", "C"}
_POLAR = {"S", "T", "N", "Q", "D", "E", "K", "R", "H"}


def _aa3to1(resname: str) -> str:
    return _AA3TO1.get(resname.strip().upper(), "X")


def _is_acidic(aa: str) -> bool:
    return aa in _ACIDIC


def _is_basic(aa: str) -> bool:
    return aa in _BASIC


def _is_aromatic(aa: str) -> bool:
    return aa in _AROMATIC


def _is_hydrophobic(aa: str) -> bool:
    return aa in _HYDROPHOBIC


def _is_polar(aa: str) -> bool:
    return aa in _POLAR


def _distance(a: tuple, b: tuple) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class ResidueContact:
    epitope_position: int          # 0-based position in epitope sequence
    epitope_residue: str           # 1-letter
    epitope_chain: str
    epitope_residue_id: str        # PDB resseq+icode
    antibody_chain: str
    antibody_residue_id: str
    antibody_residue_name: str     # 3-letter
    min_distance: float            # Å
    contact_type: str              # hydrophobic / polar / salt_bridge / aromatic / clash / unknown
    antibody_region: Optional[str] = None  # CDRH1/CDRH2/CDRH3/FR/unavailable


@dataclass
class ContactAnalysisResult:
    candidate_id: str
    complex_pdb: str
    epitope_sequence: str
    epitope_chain: Optional[str] = None
    contacted_epitope_positions: List[int] = field(default_factory=list)
    contact_coverage: float = 0.0
    num_contacts: int = 0
    num_epitope_residues_contacted: int = 0
    cdr_contact_fraction: Optional[float] = None
    contacts: List[ResidueContact] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    status: Literal["not_run", "success", "warning", "failed"] = "not_run"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "complex_pdb": self.complex_pdb,
            "epitope_chain": self.epitope_chain,
            "contacted_epitope_positions": self.contacted_epitope_positions,
            "contact_coverage": self.contact_coverage,
            "num_contacts": self.num_contacts,
            "num_epitope_residues_contacted": self.num_epitope_residues_contacted,
            "cdr_contact_fraction": self.cdr_contact_fraction,
            "contacts": [
                {
                    "epitope_position": c.epitope_position,
                    "epitope_residue": c.epitope_residue,
                    "epitope_chain": c.epitope_chain,
                    "antibody_chain": c.antibody_chain,
                    "antibody_residue_id": c.antibody_residue_id,
                    "min_distance": c.min_distance,
                    "contact_type": c.contact_type,
                }
                for c in self.contacts
            ],
            "warnings": self.warnings,
            "status": self.status,
        }


# ── PDB parsing helpers ──────────────────────────────────────────────────────

def _parse_pdb_atoms(pdb_path: str) -> List[Dict[str, Any]]:
    """Extract all ATOM/HETATM records with coordinates."""
    atoms = []
    with open(pdb_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not (line.startswith("ATOM") or line.startswith("HETATM")):
                continue
            if len(line) < 54:
                continue
            atom_name = line[12:16].strip()
            if atom_name == "H":
                continue  # Skip hydrogens
            resname = line[17:20].strip()
            chain = line[21].strip() or "_"
            resseq = line[22:26].strip()
            icode = line[26].strip() or " "
            try:
                x = float(line[30:38].strip())
                y = float(line[38:46].strip())
                z = float(line[46:54].strip())
            except (ValueError, IndexError):
                continue
            atoms.append({
                "atom_name": atom_name,
                "resname": resname,
                "chain": chain,
                "resseq": resseq,
                "icode": icode,
                "x": x, "y": y, "z": z,
            })
    return atoms


def _group_by_residue(atoms: List[Dict]) -> Dict[tuple, List[Dict]]:
    """Group atoms by (chain, resseq, icode)."""
    groups = {}
    for a in atoms:
        key = (a["chain"], a["resseq"], a["icode"])
        groups.setdefault(key, []).append(a)
    return groups


def _residue_key_to_str(key: tuple) -> str:
    chain, resseq, icode = key
    if icode.strip():
        return f"{chain}:{resseq}{icode}"
    return f"{chain}:{resseq}"


def _find_epitope_chain(
    atoms: List[Dict], epitope_seq: str,
    preferred_chain: Optional[str] = None,
) -> Optional[str]:
    """Identify which chain contains the epitope sequence.

    Tries preferred_chain first, then scans all chains.
    """
    chains = set(a["chain"] for a in atoms)
    if preferred_chain and preferred_chain in chains:
        return preferred_chain

    # Try to find the chain containing the epitope
    for chain in sorted(chains):
        chain_residues = _extract_chain_sequence(atoms, chain)
        if epitope_seq.upper() in chain_residues:
            return chain
    # Fallback: return first non-"_" chain
    non_blank = [c for c in sorted(chains) if c != "_"]
    return non_blank[0] if non_blank else None


def _extract_chain_sequence(atoms: List[Dict], chain: str) -> str:
    """Extract 1-letter sequence from a chain's CA atoms."""
    residues = {}
    for a in atoms:
        if a["chain"] != chain:
            continue
        if a["atom_name"] != "CA":
            continue
        key = (a["resseq"], a["icode"])
        if key not in residues:
            aa = _aa3to1(a["resname"])
            if aa != "X":
                residues[key] = aa
    sorted_keys = sorted(residues.keys(), key=lambda k: (int(k[0]) if k[0].isdigit() else 9999, k[1]))
    return "".join(residues[k] for k in sorted_keys)


def _find_epitope_in_chain_sequence(chain_seq: str, epitope_seq: str) -> Optional[int]:
    """Find epitope in a chain sequence. Returns start index or None.

    Tries: (1) exact match at start, (2) sliding window match anywhere.
    """
    epi = epitope_seq.upper()
    cs = chain_seq.upper()
    # Exact full-chain match
    if cs == epi:
        return 0
    # Sliding window
    idx = cs.find(epi)
    if idx >= 0:
        return idx
    return None


def _identify_chains(atoms: List[Dict], epitope_seq: str) -> Dict[str, Any]:
    """Identify epitope chain and antibody chains from PDB atoms.

    Returns dict with:
        epitope_chain: str or None
        antibody_chains: list[str]
        epitope_start: int or None (0-based index in chain)
        reason: str or None (if identification failed)
    """
    chains = {}
    for a in atoms:
        c = a["chain"]
        if c == "_":
            continue
        if c not in chains:
            chains[c] = []
        chains[c].append(a)

    result = {
        "epitope_chain": None,
        "antibody_chains": [],
        "epitope_start": None,
        "reason": None,
    }

    # Extract sequences for all chains
    chain_sequences = {}
    for c in sorted(chains.keys()):
        seq = _extract_chain_sequence(atoms, c)
        if seq:
            chain_sequences[c] = seq

    # Find epitope chain
    epitope_upper = epitope_seq.upper()

    # Strategy 1: chain whose full sequence matches epitope
    for c, seq in chain_sequences.items():
        if seq == epitope_upper:
            result["epitope_chain"] = c
            result["epitope_start"] = 0
            break

    # Strategy 2: sliding window match
    if result["epitope_chain"] is None:
        for c, seq in chain_sequences.items():
            idx = seq.find(epitope_upper)
            if idx >= 0:
                result["epitope_chain"] = c
                result["epitope_start"] = idx
                break

    if result["epitope_chain"] is None:
        result["reason"] = "epitope_sequence_not_found_in_pdb"
        return result

    # Antibody chains: all protein chains except epitope
    ab_chains = [c for c in chain_sequences if c != result["epitope_chain"]]
    if not ab_chains:
        result["reason"] = "no_antibody_chains_found"
        return result

    result["antibody_chains"] = ab_chains
    return result


def _map_epitope_positions_to_pdb_with_start(
    atoms: List[Dict], epitope_chain: str, epitope_seq: str,
    start_offset: int = 0,
) -> Dict[int, tuple]:
    """Map 0-based epitope positions to PDB (chain, resseq, icode) keys,
    given a known start_offset into the chain sequence.
    """
    residues = []
    seen = set()
    for a in atoms:
        if a["chain"] != epitope_chain:
            continue
        if a["atom_name"] != "CA":
            continue
        key = (a["resseq"], a["icode"])
        if key not in seen:
            seen.add(key)
            aa = _aa3to1(a["resname"])
            residues.append((key, aa))

    residues.sort(key=lambda r: (int(r[0][0]) if r[0][0].isdigit() else 9999, r[0][1]))

    mapping = {}
    for i in range(len(epitope_seq)):
        pos = start_offset + i
        if 0 <= pos < len(residues):
            mapping[i] = residues[pos][0]
    return mapping


def _map_epitope_positions_to_pdb(
    atoms: List[Dict], epitope_chain: str, epitope_seq: str,
) -> Dict[int, tuple]:
    """Map 0-based epitope positions to PDB (chain, resseq, icode) keys."""
    # Get all residues for the chain in order
    residues = []
    seen = set()
    for a in atoms:
        if a["chain"] != epitope_chain:
            continue
        if a["atom_name"] != "CA":
            continue
        key = (a["resseq"], a["icode"])
        if key not in seen:
            seen.add(key)
            aa = _aa3to1(a["resname"])
            residues.append((key, aa))

    residues.sort(key=lambda r: (int(r[0][0]) if r[0][0].isdigit() else 9999, r[0][1]))
    chain_seq = "".join(r[1] for r in residues)

    # Find epitope in chain sequence
    epitope_upper = epitope_seq.upper()
    idx = chain_seq.find(epitope_upper)
    if idx < 0:
        return {}

    mapping = {}
    for i, aa in enumerate(epitope_upper):
        if idx + i < len(residues):
            mapping[i] = residues[idx + i][0]
    return mapping


# ── Contact type classification ──────────────────────────────────────────────

def _classify_contact(
    epitope_aa: str, antibody_aa: str, distance: float,
) -> str:
    """Classify contact type based on residue pair and distance."""
    if distance < 2.0:
        return "clash"

    # Salt bridge: acidic epitope + basic antibody or vice versa
    if _is_acidic(epitope_aa) and _is_basic(antibody_aa):
        return "salt_bridge"
    if _is_basic(epitope_aa) and _is_acidic(antibody_aa):
        return "salt_bridge"

    # Aromatic stacking
    if _is_aromatic(epitope_aa) and _is_aromatic(antibody_aa):
        return "aromatic"
    if _is_aromatic(epitope_aa) and _is_hydrophobic(antibody_aa):
        return "aromatic"

    # Hydrophobic
    if _is_hydrophobic(epitope_aa) and _is_hydrophobic(antibody_aa):
        return "hydrophobic"

    # Polar
    if _is_polar(epitope_aa) or _is_polar(antibody_aa):
        return "polar"

    return "unknown"


# ── Main analysis function ───────────────────────────────────────────────────

def analyze_epitope_contacts(
    complex_pdb: str,
    epitope_sequence: str,
    candidate_id: str,
    epitope_chain: Optional[str] = None,
    antibody_chains: Optional[List[str]] = None,
    distance_cutoff: float = 4.5,
    clash_cutoff: float = 2.0,
) -> ContactAnalysisResult:
    """Analyze epitope-antibody contacts in a docked complex PDB.

    Args:
        complex_pdb: Path to the complex PDB file.
        epitope_sequence: Epitope amino acid sequence (1-letter).
        candidate_id: Candidate identifier.
        epitope_chain: Preferred chain ID for the epitope (auto-detected if None).
        antibody_chains: Explicit list of antibody chain IDs (auto-detected if None).
        distance_cutoff: Maximum Å for a contact.
        clash_cutoff: Maximum Å for a steric clash.

    Returns:
        ContactAnalysisResult with contacts, coverage, and status.
    """
    result = ContactAnalysisResult(
        candidate_id=candidate_id,
        complex_pdb=complex_pdb,
        epitope_sequence=epitope_sequence.upper(),
    )

    # Parse PDB
    try:
        atoms = _parse_pdb_atoms(complex_pdb)
    except Exception as e:
        result.status = "failed"
        result.warnings.append(f"Cannot parse PDB: {e}")
        result.warnings.append("pdb_parse_failed")
        return result

    if not atoms:
        result.status = "failed"
        result.warnings.append("No ATOM records in PDB")
        result.warnings.append("pdb_parse_failed")
        return result

    epitope_seq = epitope_sequence.upper()
    epi_len = len(epitope_seq)

    # ── Use enhanced chain identification ────────────────────────────────
    chain_id = _identify_chains(atoms, epitope_seq)
    if chain_id["reason"]:
        result.status = "failed"
        result.warnings.append(chain_id["reason"])
        return result

    epi_chain = chain_id["epitope_chain"]
    ab_chains = antibody_chains or chain_id["antibody_chains"]
    result.epitope_chain = epi_chain

    if not ab_chains:
        result.status = "failed"
        result.warnings.append("no_antibody_chains_found")
        return result

    # Map epitope positions to PDB residues (using identified start)
    epi_mapping = _map_epitope_positions_to_pdb_with_start(
        atoms, epi_chain, epitope_seq,
        start_offset=chain_id["epitope_start"] or 0,
    )
    if not epi_mapping:
        result.status = "failed"
        result.warnings.append(
            f"Epitope sequence '{epitope_seq}' not found in chain {epi_chain}"
        )
        return result

    # Build antibody atom index
    ab_atoms = [a for a in atoms if a["chain"] in ab_chains]
    if not ab_atoms:
        result.status = "failed"
        result.warnings.append("No antibody atoms found")
        return result

    # For each epitope residue, find minimum distance to any antibody atom
    contacted_positions = set()
    all_contacts = []

    for epi_pos, pdb_key in epi_mapping.items():
        # Get epitope residue atoms
        epi_atoms_here = [
            a for a in atoms
            if a["chain"] == epi_chain
            and a["resseq"] == pdb_key[0]
            and a["icode"] == pdb_key[1]
        ]
        if not epi_atoms_here:
            continue

        epi_aa = epitope_seq[epi_pos]
        min_dist = float("inf")
        best_ab_atom = None

        for ea in epi_atoms_here:
            epi_xyz = (ea["x"], ea["y"], ea["z"])
            for aa in ab_atoms:
                ab_xyz = (aa["x"], aa["y"], aa["z"])
                d = _distance(epi_xyz, ab_xyz)
                if d < min_dist:
                    min_dist = d
                    best_ab_atom = aa

        if min_dist <= distance_cutoff:
            contacted_positions.add(epi_pos)
            ab_aa = _aa3to1(best_ab_atom["resname"]) if best_ab_atom else "X"
            contact = ResidueContact(
                epitope_position=epi_pos,
                epitope_residue=epi_aa,
                epitope_chain=epi_chain,
                epitope_residue_id=_residue_key_to_str((epi_chain,) + pdb_key),
                antibody_chain=best_ab_atom["chain"],
                antibody_residue_id=_residue_key_to_str(
                    (best_ab_atom["chain"], best_ab_atom["resseq"], best_ab_atom["icode"])
                ),
                antibody_residue_name=best_ab_atom["resname"],
                min_distance=round(min_dist, 3),
                contact_type=_classify_contact(epi_aa, ab_aa, min_dist),
            )
            all_contacts.append(contact)

    # Compute coverage
    result.contacts = all_contacts
    result.contacted_epitope_positions = sorted(contacted_positions)
    result.num_contacts = len(all_contacts)
    result.num_epitope_residues_contacted = len(contacted_positions)
    result.contact_coverage = round(len(contacted_positions) / epi_len, 3) if epi_len else 0.0

    # ── Warnings for short peptides (≤8 aa) ──────────────────────────────
    is_short = epi_len <= 8

    if is_short:
        if result.num_epitope_residues_contacted < 3:
            result.warnings.append(
                f"short_peptide_low_contact_count: only "
                f"{result.num_epitope_residues_contacted}/{epi_len} epitope "
                f"residues contacted in short peptide docking"
            )

        # Check aromatic residues
        aromatic_positions = [
            i for i, aa in enumerate(epitope_seq)
            if aa in _AROMATIC
        ]
        for pos in aromatic_positions:
            if pos not in contacted_positions:
                result.warnings.append(
                    f"aromatic_epitope_residue_not_contacted: "
                    f"position {pos} ({epitope_seq[pos]}) has no contact"
                )

        # Check acidic residues
        acidic_positions = [
            i for i, aa in enumerate(epitope_seq)
            if aa in _ACIDIC
        ]
        for pos in acidic_positions:
            if pos not in contacted_positions:
                result.warnings.append(
                    f"acidic_epitope_residue_lacks_polar_or_salt_bridge_contact: "
                    f"position {pos} ({epitope_seq[pos]}) is not contacted"
                )
            else:
                # Check if the contact is polar or salt_bridge
                pos_contacts = [
                    c for c in all_contacts
                    if c.epitope_position == pos
                ]
                has_polar_or_sb = any(
                    c.contact_type in ("polar", "salt_bridge")
                    for c in pos_contacts
                )
                if not has_polar_or_sb:
                    result.warnings.append(
                        f"acidic_epitope_residue_{epitope_seq[pos]}_contacted_but_no_polar_or_salt_bridge: "
                        f"contact types: {[c.contact_type for c in pos_contacts]}"
                    )

    # For PSAEVWD specifically — check W at position 5
    if epitope_seq == "PSAEVWD":
        w_pos = 5  # 0-based
        if w_pos not in contacted_positions:
            result.warnings.append(
                "PSAEVWD_W6_not_contacted: key aromatic residue W6 "
                "(Trp) is not contacted by antibody — docking may "
                "be a false positive"
            )

    # ── Determine status ────────────────────────────────────────────────
    if result.contact_coverage == 0:
        result.status = "failed"
    elif result.contact_coverage < 0.4:
        result.status = "warning"
    else:
        result.status = "success"

    return result
