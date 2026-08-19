"""Structured audit logger for antibody design pipeline.

Provides:
- JSONL event logging for each pipeline stage
- Console logging with candidate_id prefix
- Audit report generation (JSON + Markdown)
- Tool call tracking with full provenance

Every candidate gets a unique ID and every tool call is traceable.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, TextIO

from biomni.tool.antibody_design.candidate_result import (
    CandidateResult, ToolRunRecord, DockingResult, RosettaResult,
    SequenceQC, DevelopabilityQC, Ranking, build_candidate_id,
    generate_run_id,
)


# ── JSONL event logger ───────────────────────────────────────────────────────
class AuditLogger:
    """Structured audit logger that writes JSONL events and optional console logs."""

    def __init__(self, output_dir: str, run_id: Optional[str] = None,
                 verbose: bool = True):
        self.output_dir = output_dir
        self.run_id = run_id or generate_run_id()
        self.verbose = verbose
        self._jsonl_file: Optional[TextIO] = None
        self._event_count: int = 0
        self._candidates: Dict[str, CandidateResult] = {}
        self._tool_runs: List[ToolRunRecord] = []

        os.makedirs(output_dir, exist_ok=True)
        self._open_jsonl()

    def _open_jsonl(self) -> None:
        path = os.path.join(self.output_dir, "tool_runs.jsonl")
        self._jsonl_file = open(path, "a", encoding="utf-8")
        self._log_console(f"Audit log opened: {path}")

    def close(self) -> None:
        if self._jsonl_file:
            self._jsonl_file.close()
            self._jsonl_file = None

    def _emit_jsonl(self, event: Dict[str, Any]) -> None:
        event["run_id"] = self.run_id
        event["seq"] = self._event_count
        self._event_count += 1
        if self._jsonl_file:
            self._jsonl_file.write(json.dumps(event, ensure_ascii=False) + "\n")
            self._jsonl_file.flush()

    def _log_console(self, message: str, candidate_id: str = "",
                     stage: str = "") -> None:
        if not self.verbose:
            return
        prefix = ""
        if candidate_id:
            prefix += f"[{candidate_id}]"
        if stage:
            prefix += f"[{stage}]"
        if prefix:
            prefix += " "
        print(f"{prefix}{message}", file=sys.stderr)

    # ── Event emitters ────────────────────────────────────────────────────
    def tool_start(self, tool_name: str, candidate_id: str = "",
                   input_files: Optional[List[str]] = None,
                   parameters: Optional[Dict[str, Any]] = None,
                   execution_mode: Optional[str] = None) -> ToolRunRecord:
        """Emit a tool_start event and return a ToolRunRecord for tracking."""
        record = ToolRunRecord(
            tool_name=tool_name,
            candidate_id=candidate_id,
            input_files=input_files or [],
            parameters=parameters or {},
            execution_mode=execution_mode,
            status="not_run",
        )
        record.mark_start()
        self._tool_runs.append(record)

        event = {
            "event": "tool_start",
            "candidate_id": candidate_id,
            "tool": tool_name,
            "input_files": record.input_files,
            "parameters": record.parameters,
            "execution_mode": execution_mode,
            "time": record.started_at,
        }
        self._emit_jsonl(event)
        self._log_console(
            f"▶ start {tool_name} | files={record.input_files}",
            candidate_id, tool_name,
        )
        return record

    def tool_finish(self, record: ToolRunRecord,
                    status: str = "success",
                    output_files: Optional[List[str]] = None,
                    runtime: Optional[float] = None,
                    warnings: Optional[List[str]] = None,
                    errors: Optional[List[str]] = None) -> None:
        """Emit a tool_finish event."""
        if output_files:
            record.output_files = output_files
        record.mark_end(status=str(status) if status else "success", runtime=runtime)
        if warnings:
            record.warnings = warnings
        if errors:
            record.errors = errors

        event = {
            "event": "tool_finish",
            "candidate_id": record.candidate_id,
            "tool": record.tool_name,
            "status": record.status,
            "output_files": record.output_files,
            "runtime_seconds": record.runtime_seconds,
            "warnings": record.warnings,
            "errors": record.errors,
            "fallback_used": record.fallback_used,
            "time": record.finished_at,
        }
        self._emit_jsonl(event)
        status_icon = {"success": "✅", "warning": "⚠️", "failed": "❌", "fallback": "⬇️"}.get(record.status, "?")
        self._log_console(
            f"{status_icon} finish {record.tool_name} | status={record.status} | "
            f"runtime={record.runtime_seconds}s | outputs={record.output_files}",
            record.candidate_id, record.tool_name,
        )

    def hdock_event(self, candidate_id: str, event_type: str,
                    **kwargs: Any) -> None:
        """Emit a structured HDOCK event."""
        event = {
            "event": f"hdock_{event_type}",
            "candidate_id": candidate_id,
            "tool": "HDOCK",
            **kwargs,
        }
        self._emit_jsonl(event)

    def rosetta_event(self, candidate_id: str, event_type: str,
                      **kwargs: Any) -> None:
        """Emit a structured Rosetta event."""
        event = {
            "event": f"rosetta_{event_type}",
            "candidate_id": candidate_id,
            "tool": "Rosetta",
            **kwargs,
        }
        self._emit_jsonl(event)

    def qc_event(self, candidate_id: str, qc_type: str,
                 status: str, flags: List[str], **kwargs: Any) -> None:
        """Emit a QC result event."""
        event = {
            "event": "qc_result",
            "candidate_id": candidate_id,
            "qc_type": qc_type,
            "status": status,
            "flags": flags,
            **kwargs,
        }
        self._emit_jsonl(event)

    def ranking_event(self, candidate_id: str,
                      composite_score: float, rank: int,
                      recommendation: str, reason: str) -> None:
        """Emit a ranking event."""
        event = {
            "event": "ranking",
            "candidate_id": candidate_id,
            "composite_score": composite_score,
            "rank": rank,
            "recommendation": recommendation,
            "reason": reason,
        }
        self._emit_jsonl(event)

    def register_candidate(self, candidate: CandidateResult) -> None:
        candidate.run_id = self.run_id
        self._candidates[candidate.candidate_id] = candidate

    # ── Report generation ─────────────────────────────────────────────────
    def generate_audit_report(self) -> Dict[str, Any]:
        """Generate a complete audit report (JSON-serializable)."""
        candidates_list = [c.to_dict() for c in self._candidates.values()]
        tool_runs_list = [tr.to_dict() for tr in self._tool_runs]

        return {
            "audit_report_version": "2.0",
            "run_id": self.run_id,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "summary": {
                "total_candidates": len(candidates_list),
                "total_tool_runs": len(tool_runs_list),
                "tool_runs_by_status": self._count_by_status(tool_runs_list),
                "candidates_by_recommendation": self._count_by_recommendation(candidates_list),
            },
            "global_parameters": self._global_params(),
            "candidates": candidates_list,
            "tool_runs": tool_runs_list,
        }

    def _count_by_status(self, runs: List[Dict]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for r in runs:
            s = r.get("status", "unknown")
            counts[s] = counts.get(s, 0) + 1
        return counts

    def _count_by_recommendation(self, candidates: List[Dict]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for c in candidates:
            rec = c.get("ranking", {}).get("recommendation", "unknown")
            counts[rec] = counts.get(rec, 0) + 1
        return counts

    def _global_params(self) -> Dict[str, Any]:
        return {
            "allow_fallback": os.getenv("ALLOW_FALLBACK", "0"),
            "stable_execution_mode": os.getenv("STABLE_EXECUTION_MODE", "1"),
            "hdock_docker_image": os.getenv("HDOCK_DOCKER_IMAGE", "hdock-runner:latest"),
            "hdock_timeout_sec": os.getenv("HDOCK_TIMEOUT_SEC", "2400"),
            "rosetta_timeout_sec": os.getenv("ROSETTA_TIMEOUT_SEC", "900"),
            "scoring_mode": os.getenv("SCORING_MODE", "auto"),
        }

    def write_audit_report(self) -> str:
        """Write audit_report.json and return the path."""
        report = self.generate_audit_report()
        path = os.path.join(self.output_dir, "audit_report.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        self._log_console(f"Audit report written: {path}")
        return path

    def write_candidates_json(self) -> str:
        """Write candidates.json (sorted by rank) and return the path."""
        candidates_list = sorted(
            [c.to_dict() for c in self._candidates.values()],
            key=lambda c: (c.get("ranking", {}).get("rank", 999))
        )
        path = os.path.join(self.output_dir, "candidates.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(candidates_list, f, ensure_ascii=False, indent=2)
        self._log_console(f"Candidates JSON written: {path}")
        return path

    def write_summary_md(self, epitope: str = "",
                         short_peptide_warning: bool = False) -> str:
        """Write summary.md and return the path."""
        candidates = sorted(
            self._candidates.values(),
            key=lambda c: (c.ranking.rank or 999)
        )

        lines = [
            "# Antibody Design Run Summary",
            f"- **Run ID**: {self.run_id}",
            f"- **Epitope**: {epitope}",
            f"- **Total Candidates**: {len(candidates)}",
            f"- **Generated At**: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}",
            "",
        ]

        # Short peptide warning
        if short_peptide_warning or (epitope and len(epitope) <= 8):
            lines.append("## ⚠️ Short Peptide Caveat")
            lines.append("")
            lines.append(
                "The target epitope is ≤ 8 amino acids. Short peptides lack the "
                "native structural context of the full-length protein. Docking "
                "conformations may differ significantly from the in-vivo binding "
                "mode. Experimental validation with longer peptides and full-length "
                "antigen is strongly recommended."
            )
            lines.append("")

        # Fallback detection
        has_fallback = any(
            c.rosetta and c.rosetta.fallback_used for c in candidates
        )
        if has_fallback:
            lines.append("## ⚠️ Fallback Scoring Alert")
            lines.append("")
            lines.append(
                "**One or more candidates used fallback/degraded Rosetta scoring.** "
                "Fallback scores (decomposition_score, fallback_score) are NOT "
                "equivalent to standard interface ΔG (interface_dG or dG_separated). "
                "Ranking confidence is reduced for fallback-scored candidates. "
                "Do not claim these as validated binding affinities."
            )
            lines.append("")

        # QC usage table
        lines.append("## QC Status Summary")
        lines.append("")
        lines.append(
            "| candidate_id | CDRH3 | length | HDOCK_score | Rosetta_score | "
            "score_type | fallback | seq_QC | dev_QC | recommendation | reason |"
        )
        lines.append(
            "|---|---:|---:|---:|---:|---:|---:|---|---|---|"
        )
        for c in candidates:
            row = c.summary_row()
            hdock_str = f"{row['HDOCK_score']:.1f}" if isinstance(row['HDOCK_score'], (int, float)) else str(row['HDOCK_score'])
            ros_str = f"{row['Rosetta_score']:.1f}" if isinstance(row['Rosetta_score'], (int, float)) else str(row['Rosetta_score'])
            fallback_str = "⚠️ YES" if row['fallback_used'] else "no"

            lines.append(
                f"| {row['candidate_id']} | {row['CDRH3']} | {row['length']} | "
                f"{hdock_str} | {ros_str} | {row['score_type']} | "
                f"{fallback_str} | {row['sequence_QC']} | {row['developability_QC']} | "
                f"{row['final_recommendation']} | {row['reason']} |"
            )

        lines.append("")

        # Input assumptions
        lines.append("## Input Assumptions")
        lines.append("")
        lines.append("- CDRH3 sequences are generated by a conditional diffusion model.")
        lines.append("- Structure modeling uses ABodyBuilder2 / ImmuneBuilder.")
        lines.append("- Docking is performed with HDOCK (rigid-body).")
        lines.append("- Rosetta scoring uses the REF2015 (fa_scorefxn) energy function.")
        lines.append("- All scores are computational predictions — NOT experimental measurements.")
        lines.append("")

        # Output files
        lines.append("## Output Files")
        lines.append("")
        lines.append(f"- `audit_report.json` — Full audit trail (this run)")
        lines.append(f"- `candidates.json` — Complete candidate data")
        lines.append(f"- `tool_runs.jsonl` — Per-tool-call event log")
        lines.append(f"- `summary.md` — This summary")
        lines.append(f"- `ranked_candidates.fasta` — QC-consistent FASTA output")
        lines.append("")

        path = os.path.join(self.output_dir, "summary.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        self._log_console(f"Summary written: {path}")
        return path

    def write_fasta(self) -> str:
        """Write risk-consistent FASTA file."""
        candidates = sorted(
            self._candidates.values(),
            key=lambda c: (c.ranking.rank or 999)
        )
        path = os.path.join(self.output_dir, "ranked_candidates.fasta")
        with open(path, "w", encoding="utf-8") as f:
            for c in candidates:
                header = c.fasta_header()
                seq = c.vh_sequence or c.cdrh3_sequence
                f.write(f">{header}\n")
                for i in range(0, len(seq), 60):
                    f.write(seq[i:i + 60] + "\n")
        self._log_console(f"FASTA written: {path}")
        return path

    def write_csv(self) -> str:
        """Write CSV summary of all candidates."""
        import csv
        candidates = sorted(
            self._candidates.values(),
            key=lambda c: (c.ranking.rank or 999)
        )
        path = os.path.join(self.output_dir, "design_summary.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            fieldnames = [
                "candidate_id", "CDRH3", "length", "HDOCK_score",
                "Rosetta_score", "score_type", "fallback_used",
                "sequence_QC", "developability_QC", "final_recommendation",
                "reason", "cdrh3_cys_count", "risk_flags",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for c in candidates:
                row = c.summary_row()
                row["cdrh3_cys_count"] = c.sequence_features.cys_count_cdrh3
                row["risk_flags"] = ",".join(
                    c.sequence_qc.risk_flags + c.developability_qc.risk_flags
                )
                writer.writerow(row)
        self._log_console(f"CSV written: {path}")
        return path

    def write_all_outputs(self, epitope: str = "") -> Dict[str, str]:
        """Write all output files and return a dict of paths."""
        short_peptide_warning = bool(epitope and len(epitope) <= 8)
        paths = {
            "audit_report": self.write_audit_report(),
            "candidates_json": self.write_candidates_json(),
            "summary_md": self.write_summary_md(
                epitope=epitope,
                short_peptide_warning=short_peptide_warning,
            ),
            "fasta": self.write_fasta(),
            "csv": self.write_csv(),
        }
        return paths


# ── Convenience function ─────────────────────────────────────────────────────
def create_audit_logger(output_dir: str,
                        run_id: Optional[str] = None,
                        verbose: bool = True) -> AuditLogger:
    """Create a new audit logger for a design run."""
    return AuditLogger(output_dir=output_dir, run_id=run_id, verbose=verbose)
