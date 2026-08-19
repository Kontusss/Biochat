"""
Phase 3C-2: PDB structure validation for docking eligibility.

Validates PDB files before they are passed to docking backends.
Rejects mock structures, empty files, and files with forbidden claims.
"""

from __future__ import annotations

import os
from typing import Any, Dict


FORBIDDEN_PDB_TERMS = [
    "MOCK STRUCTURE",
    "NOT FOR SCIENTIFIC USE",
    "DO NOT USE FOR DOCKING",
    "PLACEHOLDER",
]

FORBIDDEN_CLAIMS = [
    "ddg", "binding_affinity", "validated",
    "experimentally confirmed", "high affinity",
]


def validate_pdb_for_docking(pdb_path: str) -> Dict[str, Any]:
    """Validate a PDB file for docking eligibility.

    Checks:
      - File exists and is non-empty
      - Contains ATOM records (≥100 atoms)
      - Contains ≥50 residues
      - Has at least one chain ID
      - Does NOT contain mock/placeholder markers
      - Does NOT contain forbidden scientific claims

    Returns:
        {
            "eligible_for_docking": bool,
            "path": str,
            "atom_count": int,
            "residue_count": int,
            "chain_ids": list[str],
            "issues": list[str],
            "provenance": "computed",
            "calibration": "uncalibrated",
        }
    """
    result: Dict[str, Any] = {
        "eligible_for_docking": False,
        "path": os.path.abspath(pdb_path),
        "atom_count": 0,
        "residue_count": 0,
        "chain_ids": [],
        "issues": [],
        "provenance": "computed",
        "calibration": "uncalibrated",
    }

    # 1. File existence
    if not os.path.isfile(pdb_path):
        result["issues"].append("file_not_found")
        return result

    # 2. Read and scan
    try:
        with open(pdb_path) as fh:
            content = fh.read()
    except Exception as exc:
        result["issues"].append(f"read_error: {exc}")
        return result

    if not content.strip():
        result["issues"].append("empty_file")
        return result

    content_upper = content.upper()

    # 3. Check for mock/placeholder markers
    for term in FORBIDDEN_PDB_TERMS:
        if term.upper() in content_upper:
            result["issues"].append(f"mock_or_placeholder: contains '{term}'")
            return result

    # 4. Check for forbidden scientific claims
    for term in FORBIDDEN_CLAIMS:
        if term.upper() in content_upper:
            result["issues"].append(f"forbidden_claim: contains '{term}'")
            # Don't return — collect all issues

    # 5. Count ATOM/HETATM records
    atom_lines = [l for l in content.splitlines()
                  if l.startswith("ATOM  ") or l.startswith("HETATM")]
    result["atom_count"] = len(atom_lines)

    if result["atom_count"] < 100:
        result["issues"].append(f"insufficient_atoms: {result['atom_count']} < 100")
        return result

    # 6. Count unique residues (chain + resnum + ins_code)
    residues: set[tuple[str, str, str]] = set()
    chains: set[str] = set()
    for line in atom_lines:
        if len(line) >= 26:
            chain = line[21:22].strip()
            resnum = line[22:26].strip()
            inscode = line[26:27].strip()
            residues.add((chain, resnum, inscode))
            if chain:
                chains.add(chain)

    result["residue_count"] = len(residues)
    result["chain_ids"] = sorted(chains)

    if result["residue_count"] < 50:
        result["issues"].append(f"insufficient_residues: {result['residue_count']} < 50")
        return result

    if not chains:
        result["issues"].append("no_chain_ids")
        return result

    # 7. If we got here with no issues from steps 4-6, it's eligible
    if not result["issues"]:
        result["eligible_for_docking"] = True

    return result
