"""Enhanced sequence QC module with layered logic and hard developability gates.

Implements:
- CDRH3 length windows with pass/warning/fail thresholds
- Extra Cys in CDRH3 → hard fail (unless designed_disulfide + structural evidence)
- N-glycosylation motif detection
- Hydrophobic run detection
- Electrostatic repulsion (CDRH3 vs epitope)
- Low complexity / single-AA runs
- Aggregated developability QC

Target-agnostic: works for any epitope sequence.
"""

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from biochat.tool.antibody_design.generation_filter import (
    ALLOWED_MAX_LEN,
    ALLOWED_MIN_LEN,
    PREFERRED_MAX_LEN,
    PREFERRED_MIN_LEN,
)

# Minimum absolute count before the single-AA *fraction* rule may hard-fail a
# sequence.  Calibrated on 257 real CDR-H3s — see generation_filter.
SINGLE_AA_MIN_COUNT = 4

VALID_AAS = set("ACDEFGHIKLMNPQRSTVWY")
AROMATIC_AAS = set("YFW")
ACIDIC_AAS = set("DE")
HYDROPHOBIC = set("AILMFWV")
POSITIVE = set("KRH")
NEGATIVE = set("DE")
POLAR = set("STNQY")


def _escalate_status(current: str, new: str) -> str:
    order = {"pass": 0, "warning": 1, "fail": 2}
    return new if order.get(new, 0) > order.get(current, 0) else current


def _charge_from_counter(counts: Counter) -> float:
    return counts["K"] + counts["R"] + 0.1 * counts["H"] - counts["D"] - counts["E"]


def _charge_from_seq(seq: str) -> float:
    seq = seq.upper()
    return sum(1 for c in seq if c in POSITIVE) - sum(1 for c in seq if c in NEGATIVE)


def detect_nglyc_motifs(seq: str) -> List[Dict[str, Any]]:
    """Detect N-linked glycosylation motifs: N-X-S/T (X ≠ P)."""
    seq = (seq or "").upper()
    results = []
    for m in re.finditer(r"N[^P][ST]", seq):
        results.append({
            "start": m.start(),
            "motif": m.group(),
            "risk": "nglyc_motif",
        })
    return results


def detect_hydrophobic_runs(seq: str, window: int = 4) -> List[Dict[str, Any]]:
    """Detect continuous hydrophobic runs >= window residues."""
    seq = (seq or "").upper()
    results = []
    i = 0
    while i < len(seq):
        if seq[i] in HYDROPHOBIC:
            run_start = i
            while i < len(seq) and seq[i] in HYDROPHOBIC:
                i += 1
            run_len = i - run_start
            if run_len >= window:
                results.append({
                    "start": run_start,
                    "length": run_len,
                    "sequence": seq[run_start:i],
                    "risk": "hydrophobic_patch",
                })
        else:
            i += 1
    return results


def detect_identical_runs(seq: str, window: int = 4) -> List[Dict[str, Any]]:
    """Detect continuous runs of the same amino acid >= window residues."""
    seq = (seq or "").upper()
    results = []
    if not seq:
        return results
    max_run = 1
    current_run = 1
    max_run_aa = seq[0]
    for i in range(1, len(seq)):
        if seq[i] == seq[i - 1]:
            current_run += 1
        else:
            if current_run >= window:
                results.append({
                    "start": i - current_run,
                    "length": current_run,
                    "aa": seq[i - 1],
                    "risk": f"poly_{seq[i-1]}_run",
                })
            if current_run > max_run:
                max_run = current_run
                max_run_aa = seq[i - 1]
            current_run = 1
    if current_run >= window:
        results.append({
            "start": len(seq) - current_run,
            "length": current_run,
            "aa": seq[-1],
            "risk": f"poly_{seq[-1]}_run",
        })
    if current_run > max_run:
        max_run = current_run
        max_run_aa = seq[-1]
    return results


def get_max_identical_run(seq: str) -> int:
    runs = detect_identical_runs(seq, window=1)
    if not runs:
        if not seq:
            return 0
        # All unique
        return 1
    return max(r["length"] for r in runs)


# ── Enhanced CDRH3 sequence QC ───────────────────────────────────────────────
def evaluate_cdrh3_sequence(
    seq: str,
    target_peptide: Optional[str] = None,
    designed_disulfide: bool = False,
    structure_validated_disulfide: bool = False,
) -> Dict[str, Any]:
    """Evaluate CDRH3 sequence quality with layered QC rules.

    Returns a dict with:
        status: "pass" | "warning" | "fail"
        penalty: float
        flags: list[str]
        metrics: dict
        summary: str
        notes: list[str]

    Hard rules (→ fail):
    - Empty sequence
    - Invalid amino acids
    - Length outside ALLOWED_MIN_LEN..ALLOWED_MAX_LEN (shared with generation_filter)
    - Extra Cys in CDRH3 (unless designed_disulfide + structure validated)
    - Max identical run >= 5
    - Excessive single-AA fraction > 0.35

    Soft rules (→ warning):
    - Length outside PREFERRED_MIN_LEN..PREFERRED_MAX_LEN
    - N-glycosylation motif present
    - Hydrophobic run >= 4
    - Identical run == 4
    - High aromatic fraction (0.35–0.45)
    - High acidic fraction (0.30–0.40)
    - High net charge (abs > 4)
    - Same-sign electrostatic with epitope
    - Low complexity entropy (0.50–0.65)
    """
    seq = (seq or "").strip().upper()
    status = "pass"
    penalty = 0.0
    flags: List[str] = []
    notes: List[str] = []
    metrics: Dict[str, Any] = {}

    # ── Empty sequence ──────────────────────────────────────────────────
    if not seq:
        return {
            "status": "fail",
            "penalty": 10000.0,
            "flags": ["empty_sequence"],
            "metrics": {"length": 0},
            "summary": "empty_sequence",
            "notes": ["Empty CDRH3 sequence — invalid candidate"],
        }

    # ── Invalid amino acids ─────────────────────────────────────────────
    invalid_chars = sorted(set(ch for ch in seq if ch not in VALID_AAS))
    if invalid_chars:
        return {
            "status": "fail",
            "penalty": 10000.0,
            "flags": ["invalid_amino_acid"],
            "metrics": {"length": len(seq), "invalid_chars": invalid_chars},
            "summary": f"invalid_amino_acid: {','.join(invalid_chars)}",
            "notes": [f"Invalid amino acid chars in CDRH3: {invalid_chars}"],
        }

    length = len(seq)
    counts = Counter(seq)
    metrics["length"] = length

    # ── CDRH3 length rules ──────────────────────────────────────────────
    # Thresholds are imported from generation_filter so the two gates cannot
    # drift apart.  They were previously independent (fail <8 or >22 here,
    # <6 or >26 there), which let the same sequence pass one gate and fail the
    # other.  See generation_filter for the calibration data.
    if length < ALLOWED_MIN_LEN:
        status = _escalate_status(status, "fail")
        penalty += 10000.0
        flags.append("cdrh3_length_high_risk")
        notes.append(f"CDRH3 too short: {length} aa (<{ALLOWED_MIN_LEN})")
    elif length > ALLOWED_MAX_LEN:
        status = _escalate_status(status, "fail")
        penalty += 10000.0
        flags.append("cdrh3_length_high_risk")
        notes.append(f"CDRH3 too long: {length} aa (>{ALLOWED_MAX_LEN})")
    elif length < PREFERRED_MIN_LEN:
        status = _escalate_status(status, "warning")
        penalty += 100.0
        flags.append("cdrh3_length_outside_preferred_window")
        notes.append(f"CDRH3 length {length} is below the preferred {PREFERRED_MIN_LEN}–{PREFERRED_MAX_LEN} window")
    elif length > PREFERRED_MAX_LEN:
        status = _escalate_status(status, "warning")
        penalty += 50.0
        flags.append("cdrh3_length_outside_preferred_window")
        notes.append(f"CDRH3 length {length} is above the preferred {PREFERRED_MIN_LEN}–{PREFERRED_MAX_LEN} window")

    # ── Extra Cys in CDRH3 ──────────────────────────────────────────────
    cys_count = counts.get("C", 0)
    metrics["cdrh3_cys_count"] = cys_count

    if cys_count > 0:
        if cys_count % 2 == 1:
            # Odd Cys → unpaired → always fail
            status = _escalate_status(status, "fail")
            penalty += 10000.0
            flags.append("extra_Cys_in_CDRH3")
            notes.append(
                f"CDRH3 has odd number of Cys ({cys_count}) — unpaired cysteine "
                "is a major developability liability"
            )
        elif not designed_disulfide:
            # Even Cys but not designed as disulfide → fail
            status = _escalate_status(status, "fail")
            penalty += 5000.0
            flags.append("extra_Cys_in_CDRH3")
            notes.append(
                f"CDRH3 has {cys_count} Cys but not marked as designed_disulfide. "
                "Unexpected cysteines may cause aggregation or mispairing."
            )
        elif not structure_validated_disulfide:
            # Designed but not structurally validated → warning only
            status = _escalate_status(status, "warning")
            penalty += 200.0
            flags.append("extra_Cys_in_CDRH3")
            notes.append(
                f"CDRH3 has {cys_count} Cys marked as designed disulfide, "
                "but no structural validation was performed."
            )

    # ── N-glycosylation motifs ──────────────────────────────────────────
    nglyc = detect_nglyc_motifs(seq)
    metrics["nglyc_motifs"] = [m["motif"] for m in nglyc]
    if nglyc:
        status = _escalate_status(status, "warning")
        penalty += 150.0
        flags.append("nglyc_motif")
        notes.append(
            f"N-glycosylation motif(s) detected: {[m['motif'] for m in nglyc]}. "
            "May affect expression and stability."
        )

    # ── Hydrophobic runs ────────────────────────────────────────────────
    hydro_runs = detect_hydrophobic_runs(seq, window=4)
    max_hydro_run = max((r["length"] for r in hydro_runs), default=0)
    metrics["max_hydrophobic_run"] = max_hydro_run
    if hydro_runs:
        status = _escalate_status(status, "warning")
        penalty += 100.0
        flags.append("hydrophobic_patch")
        notes.append(
            f"Continuous hydrophobic runs detected (max length={max_hydro_run}). "
            "May increase aggregation propensity."
        )

    # ── Identical AA runs ───────────────────────────────────────────────
    id_runs = detect_identical_runs(seq, window=4)
    max_id_run = max((r["length"] for r in id_runs), default=1)
    metrics["max_identical_run"] = max_id_run

    if max_id_run >= 5:
        status = _escalate_status(status, "fail")
        penalty += 10000.0
        run_aa = next((r["aa"] for r in id_runs if r["length"] >= 5), "X")
        flags.append(f"poly_{run_aa}_run_{max_id_run}")
        notes.append(f"Single AA run of {max_id_run} {run_aa}s — likely unstructured")
    elif max_id_run == 4:
        status = _escalate_status(status, "warning")
        penalty += 150.0
        run_aa = next((r["aa"] for r in id_runs if r["length"] == 4), "X")
        flags.append(f"poly_{run_aa}_run_4")
        notes.append(f"Run of 4 identical {run_aa}s — may affect specificity")

    # ── Single AA fraction ──────────────────────────────────────────────
    max_aa, max_count = counts.most_common(1)[0]
    max_fraction = max_count / length
    metrics["dominant_aa"] = max_aa
    metrics["dominant_aa_fraction"] = round(max_fraction, 3)

    # A bare fraction is unreliable on short loops — in a 4aa CDR-H3 a single
    # repeat already reads as 50%.  Requiring a minimum absolute count removes
    # that artefact: on the 257 real CDR-H3s in the benchmark it drops the
    # false-positive rate from 16.0% to 10.5% (the P90 target) and eliminates
    # all seven short-sequence false positives, including nivolumab's `NDDY`.
    if max_fraction > 0.35 and max_count >= SINGLE_AA_MIN_COUNT:
        status = _escalate_status(status, "fail")
        penalty += 10000.0
        flags.append(f"excessive_single_aa_{max_aa}_fraction")
        notes.append(f"Single AA ({max_aa}) fraction {max_fraction:.2f} > 0.35 ({max_count} residues)")
    elif max_fraction >= 0.25:
        status = _escalate_status(status, "warning")
        penalty += 100.0
        flags.append(f"high_single_aa_{max_aa}_fraction")

    # ── Aromatic fraction ───────────────────────────────────────────────
    aromatic_count = sum(counts.get(aa, 0) for aa in AROMATIC_AAS)
    aromatic_frac = aromatic_count / length
    metrics["aromatic_fraction"] = round(aromatic_frac, 3)

    if aromatic_frac > 0.45:
        status = _escalate_status(status, "fail")
        penalty += 10000.0
        flags.append("excessive_aromatic_fraction")
    elif aromatic_frac > 0.35:
        status = _escalate_status(status, "warning")
        penalty += 150.0
        flags.append("high_aromatic_fraction")

    # ── Acidic fraction ─────────────────────────────────────────────────
    acidic_count = sum(counts.get(aa, 0) for aa in ACIDIC_AAS)
    acidic_frac = acidic_count / length
    metrics["acidic_fraction"] = round(acidic_frac, 3)

    if acidic_frac > 0.40:
        status = _escalate_status(status, "fail")
        penalty += 10000.0
        flags.append("excessive_acidic_fraction")
    elif acidic_frac > 0.30:
        status = _escalate_status(status, "warning")
        penalty += 150.0
        flags.append("high_acidic_fraction")

    # ── Net charge ──────────────────────────────────────────────────────
    net_charge = _charge_from_counter(counts)
    metrics["net_charge"] = round(net_charge, 2)

    if abs(net_charge) >= 4:
        status = _escalate_status(status, "warning")
        penalty += 100.0
        flags.append("high_net_charge")
        notes.append(f"CDRH3 net charge={net_charge:.1f} — abs(charge) >= 4")
    if abs(net_charge) > 8:
        status = _escalate_status(status, "fail")
        penalty += 10000.0
        flags.append("extreme_net_charge")

    # ── Hydrophobic fraction ────────────────────────────────────────────
    hydro_count = sum(counts.get(aa, 0) for aa in HYDROPHOBIC)
    hydro_frac = hydro_count / length
    metrics["hydrophobic_fraction"] = round(hydro_frac, 3)

    if hydro_frac > 0.50:
        status = _escalate_status(status, "warning")
        penalty += 100.0
        flags.append("high_hydrophobicity")

    # ── Sequence complexity (Shannon entropy) ───────────────────────────
    entropy = 0.0
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    entropy_norm = entropy / math.log2(len(VALID_AAS))
    metrics["entropy_norm"] = round(entropy_norm, 3)

    if entropy_norm < 0.50:
        status = _escalate_status(status, "fail")
        penalty += 10000.0
        flags.append("low_complexity_entropy")
    elif entropy_norm <= 0.65:
        status = _escalate_status(status, "warning")
        penalty += 200.0
        flags.append("borderline_low_complexity_entropy")

    # ── Electrostatic repulsion with epitope ────────────────────────────
    metrics["epitope_net_charge"] = None
    if target_peptide:
        target_seq = (target_peptide or "").strip().upper()
        target_invalid = sorted(set(ch for ch in target_seq if ch not in VALID_AAS))
        if not target_invalid and target_seq:
            target_charge = _charge_from_seq(target_seq)
            metrics["epitope_net_charge"] = round(target_charge, 2)

            # Both negative: electrostatic repulsion risk
            if target_charge < 0 and net_charge < 0:
                if abs(target_charge) >= 1 and abs(net_charge) >= 1:
                    status = _escalate_status(status, "warning")
                    penalty += 150.0
                    flags.append("possible_electrostatic_repulsion")
                    notes.append(
                        f"Epitope ({target_charge:.1f}) and CDRH3 ({net_charge:.1f}) "
                        "are both negatively charged — electrostatic repulsion possible"
                    )
            # Both positive: also a risk
            elif target_charge > 0 and net_charge > 0:
                if abs(target_charge) >= 1 and abs(net_charge) >= 1:
                    status = _escalate_status(status, "warning")
                    penalty += 100.0
                    flags.append("electrostatic_same_sign_with_target")
                    notes.append(
                        f"Epitope ({target_charge:.1f}) and CDRH3 ({net_charge:.1f}) "
                        "have same-sign charge — may reduce binding"
                    )

    # ── Final assembly ──────────────────────────────────────────────────
    unique_flags = list(dict.fromkeys(flags))
    unique_notes = list(dict.fromkeys(notes))
    summary = f"status={status}; penalty={round(penalty, 2)}; flags={unique_flags or ['none']}"

    return {
        "status": status,
        "penalty": round(penalty, 2),
        "flags": unique_flags,
        "metrics": metrics,
        "summary": summary,
        "notes": unique_notes,
    }


# ── Aggregated developability QC ─────────────────────────────────────────────
def evaluate_developability(
    sequence_qc_result: Dict[str, Any],
    has_real_structure: bool = False,
    rosetta_fallback_used: bool = False,
    docking_fallback_used: bool = False,
    extra_flags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Aggregate sequence QC + tool status into developability QC.

    Rules:
    - If sequence_QC=fail → developability_QC can be fail at best
    - If extra_Cys_in_CDRH3 → must be fail or warning
    - If only minor length issues → can be conditional_pass
    - If Rosetta/docking fallback → does NOT cause fail, but adds note

    Returns:
        dict with status, risk_flags, notes
    """
    sqc_status = sequence_qc_result.get("status", "fail")
    sqc_flags = list(sequence_qc_result.get("flags", []))
    sqc_notes = list(sequence_qc_result.get("notes", []))
    all_flags = list(sqc_flags)
    all_notes = list(sqc_notes)
    if extra_flags:
        all_flags.extend(extra_flags)

    # Determine developability status
    if sqc_status == "fail":
        status: str = "fail"
    elif sqc_status == "warning":
        # Check if any flag forces fail at developability level
        hard_dev_flags = {"extra_Cys_in_CDRH3", "empty_sequence", "invalid_amino_acid"}
        if hard_dev_flags & set(sqc_flags):
            status = "fail"
        else:
            status = "warning"
    else:
        # sqc_status == "pass"
        status = "pass"

    # Extra Cys in CDRH3 always pushes to fail at developability level
    if "extra_Cys_in_CDRH3" in sqc_flags:
        status = "fail"
        all_notes.append(
            "Extra Cys in CDRH3 — hard developability fail. "
            "Candidate must be redesigned to remove unpaired cysteines."
        )

    # Fallback scoring impacts
    if rosetta_fallback_used or docking_fallback_used:
        if status == "pass":
            status = "conditional_pass"
        all_notes.append(
            "Fallback scoring was used — ranking confidence is reduced. "
            "Structural interface metrics are NOT equivalent to standard interface ΔG."
        )

    # Minor length issues only → conditional_pass
    if (status in ("pass", "warning")
        and "cdrh3_length_outside_preferred_window" in sqc_flags
        and "extra_Cys_in_CDRH3" not in sqc_flags):
        status = "conditional_pass"

    unique_flags = list(dict.fromkeys(all_flags))
    unique_notes = list(dict.fromkeys(all_notes))

    return {
        "status": status,
        "risk_flags": unique_flags,
        "notes": unique_notes,
    }


# ── Full candidate QC pipeline ───────────────────────────────────────────────
def run_full_qc(
    cdrh3: str,
    epitope: str = "",
    vh_sequence: str = "",
    designed_disulfide: bool = False,
    structure_validated_disulfide: bool = False,
    rosetta_fallback_used: bool = False,
    docking_fallback_used: bool = False,
) -> Dict[str, Any]:
    """Run the complete QC pipeline for a single CDRH3 candidate.

    Returns a dict with:
        sequence_qc: dict
        developability_qc: dict
        features: dict (sequence features)
    """
    from biochat.tool.antibody_design.developability_checks import basic_developability_report, detect_deamidation_sites

    seq_qc = evaluate_cdrh3_sequence(
        cdrh3,
        target_peptide=epitope,
        designed_disulfide=designed_disulfide,
        structure_validated_disulfide=structure_validated_disulfide,
    )

    dev_qc = evaluate_developability(
        seq_qc,
        rosetta_fallback_used=rosetta_fallback_used,
        docking_fallback_used=docking_fallback_used,
    )

    # Compute sequence features
    seq = cdrh3.upper()
    dev_report = basic_developability_report(cdrh3)
    deam = detect_deamidation_sites(cdrh3)

    features = {
        "cdrh3_length": len(seq),
        "vh_length": len(vh_sequence) if vh_sequence else None,
        "net_charge_pH_7_4": seq_qc["metrics"].get("net_charge"),
        "aromatic_fraction": seq_qc["metrics"].get("aromatic_fraction"),
        "hydrophobic_fraction": seq_qc["metrics"].get("hydrophobic_fraction"),
        "cys_count_total": seq_qc["metrics"].get("cdrh3_cys_count", 0),
        "cys_count_cdrh3": seq_qc["metrics"].get("cdrh3_cys_count", 0),
        "nglyc_motifs": seq_qc["metrics"].get("nglyc_motifs", []),
        "low_complexity_regions": [],
        "max_hydrophobic_run": seq_qc["metrics"].get("max_hydrophobic_run"),
        "max_identical_run": seq_qc["metrics"].get("max_identical_run"),
        "epitope_net_charge": seq_qc["metrics"].get("epitope_net_charge"),
    }

    return {
        "sequence_qc": seq_qc,
        "developability_qc": dev_qc,
        "features": features,
    }
