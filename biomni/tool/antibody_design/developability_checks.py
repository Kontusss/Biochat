"""可开发性校验模块

Usage:
    from developability_checks import detect_nglyc_motifs, basic_developability_report
"""

import re
from typing import List, Dict

VALID_AAS = set("ACDEFGHIKLMNPQRSTVWY")
HYDROPHOBIC = set("AILMFWV")


def detect_nglyc_motifs(seq: str) -> List[Dict]:
    """检测 N-糖基化基序 N-X-S/T (X ≠ P)。"""
    seq = (seq or "").upper()
    results = []
    pattern = re.compile(r"N[^P][ST]")
    for m in pattern.finditer(seq):
        results.append({
            "start": m.start(),
            "motif": m.group(),
            "risk": "n_glycosylation",
        })
    return results


def detect_free_cysteines(seq: str) -> List[int]:
    """返回所有半胱氨酸的 0-based 索引。"""
    seq = (seq or "").upper()
    return [i for i, aa in enumerate(seq) if aa == "C"]


def detect_hydrophobic_runs(seq: str, window: int = 5) -> List[Dict]:
    """检测连续疏水残基斑块 (≥ window 个)。"""
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


def detect_deamidation_sites(seq: str) -> List[Dict]:
    """检测脱酰胺/异构化风险位点 (NG, NS, NT, DG, DP)。"""
    seq = (seq or "").upper()
    risks = []
    for motif, risk_type in [
        ("NG", "deamidation"), ("NS", "deamidation"), ("NT", "deamidation"),
        ("DG", "isomerization"), ("DP", "isomerization"),
    ]:
        idx = 0
        while True:
            idx = seq.find(motif, idx)
            if idx < 0:
                break
            risks.append({"start": idx, "motif": motif, "risk": risk_type})
            idx += 1
    return risks


def basic_developability_report(seq: str) -> Dict:
    """基础可开发性报告（不依赖外部工具）。

    未计算的字段标注 "not_computed"。
    """
    seq = (seq or "").upper()
    if not seq:
        return {"error": "empty_sequence"}

    n = len(seq)
    hydro_count = sum(1 for c in seq if c in HYDROPHOBIC)
    aromatic_count = sum(1 for c in seq if c in "FWY")
    cys_count = seq.count("C")

    nglyc = detect_nglyc_motifs(seq)
    hydro_runs = detect_hydrophobic_runs(seq, window=3)
    deam = detect_deamidation_sites(seq)

    flags = []
    if hydro_count / n > 0.50:
        flags.append("high_hydrophobicity")
    if aromatic_count / n > 0.30:
        flags.append("high_aromatic_fraction")
    if cys_count % 2 == 1:
        flags.append("odd_cysteine_count")
    if nglyc:
        flags.append("n_glycosylation_motif")
    if hydro_runs:
        flags.append("hydrophobic_patches")
    if deam:
        flags.append("deamidation_or_isomerization_risk")

    return {
        "length": n,
        "hydrophobic_fraction": round(hydro_count / n, 3) if n else 0,
        "aromatic_fraction": round(aromatic_count / n, 3) if n else 0,
        "cysteine_count": cys_count,
        "n_glyc_sites": len(nglyc),
        "deamidation_sites": len(deam),
        "hydrophobic_runs": len(hydro_runs),
        "flags": flags,
        "tango_aggregation": "not_computed",
        "solubility_score": "not_computed",
        "pi": "not_computed",
    }
