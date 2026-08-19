"""CSV export for antibody design results.

Exports candidates with full provenance metadata.  Deliberately does
NOT sort by score — rows are written in ``display_order`` (the order
they were ranked by the pipeline, but this export makes no new
ranking claims).
"""

from __future__ import annotations

import csv
import os
from typing import Any, Dict, List

SAFETY_NOTE = (
    "计算设计结果，未经实验验证；评分未校准，不可视为结合亲和力证据。"
)

# ── CSV column order ────────────────────────────────────────────
CSV_COLUMNS = [
    "candidate_id", "epitope", "cdrh3_sequence", "length", "filter_status",
    "hard_fail_count", "soft_penalty_count", "warning_count",
    "heuristic_score", "score_source", "score_calibration",
    "structure_status", "pdb_path", "docking_status",
    "hdock_output_exists", "hdock_output_size", "hdock_format_detected",
    "score_parsed", "ranking_performed", "extraction_performed",
    "provenance", "safety_note", "display_order",
]


def export_antibody_results_csv(
    pipeline_result: Dict[str, Any],
    output_path: str,
) -> str:
    """Export antibody design pipeline results to CSV.

    Args:
        pipeline_result: Output dict from ``design_vh_only_antibodies()``
                         or ``score_and_rank_candidates()``.
        output_path: CSV file path to write.

    Returns:
        The absolute path of the written CSV.

    Safety invariants (enforced):
        - ``score_parsed`` is always False
        - ``ranking_performed`` is always False
        - ``extraction_performed`` is always False
        - ``score_calibration`` is always "uncalibrated"
    """
    candidates: List[Dict[str, Any]] = pipeline_result.get("candidates", [])
    epitope = pipeline_result.get("epitope", "")

    rows: List[Dict[str, Any]] = []
    for i, cand in enumerate(candidates, 1):
        penalties = cand.get("penalties", [])
        hard_fails = sum(1 for p in penalties if p.get("level") == "HARD_EXCLUDE")
        soft_pens = sum(1 for p in penalties if p.get("level") == "SOFT_PENALTY")
        warnings = sum(1 for p in penalties if p.get("level") == "WARNING")

        pdb_path = cand.get("output_pdb") or ""
        docking = cand.get("docking_performed", False)
        hdock_out = cand.get("output_file") or ""
        hdock_exists = bool(hdock_out and os.path.exists(hdock_out))
        hdock_size = os.path.getsize(hdock_out) if hdock_exists else 0

        rows.append({
            "candidate_id": cand.get("candidate_id", cand.get("cdrh3_sequence", f"candidate_{i:03d}")),
            "epitope": epitope,
            "cdrh3_sequence": cand.get("cdrh3_sequence", ""),
            "length": len(cand.get("cdrh3_sequence", "")),
            "filter_status": "accepted" if cand.get("accepted", True) else "filtered_out",
            "hard_fail_count": hard_fails,
            "soft_penalty_count": soft_pens,
            "warning_count": warnings,
            "heuristic_score": cand.get("aggregate_score", 0.0),
            "score_source": "base80_penalty_deduction",
            "score_calibration": "uncalibrated",
            "structure_status": cand.get("status", "not_run"),
            "pdb_path": pdb_path,
            "docking_status": "performed" if docking else "not_run",
            "hdock_output_exists": hdock_exists,
            "hdock_output_size": hdock_size,
            "hdock_format_detected": bool(hdock_exists and hdock_size > 1024),
            "score_parsed": False,
            "ranking_performed": False,
            "extraction_performed": False,
            "provenance": cand.get("provenance", "computed"),
            "safety_note": SAFETY_NOTE,
            "display_order": i,
        })

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    return os.path.abspath(output_path)
