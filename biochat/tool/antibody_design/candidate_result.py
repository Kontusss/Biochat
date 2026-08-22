"""Unified candidate result data structures for antibody design pipeline.

Provides a single source of truth for all candidate data: design, modeling,
docking, scoring, QC, ranking, and recommendations. Every field is explicitly
typed and documented to prevent inconsistent or fabricated claims.

Target-agnostic: works for any epitope/antigen/target.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional, Literal


# ── Status enums ─────────────────────────────────────────────────────────────
ToolStatus = Literal["not_run", "success", "warning", "failed", "fallback"]
QCStatus = Literal["pass", "warning", "fail", "not_run"]
DevelopabilityStatus = Literal["pass", "conditional_pass", "warning", "fail", "not_run"]
ScoreType = Literal[
    "interface_dG", "dG_separated", "total_score",
    "decomposition_score", "fallback_score", "unknown",
]
Recommendation = Literal[
    "recommended_for_experimental_screening",
    "conditional_recommended_with_caution",
    "computational_hit_redesign_required",
    "not_recommended",
    "insufficient_data",
]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"


# ── ToolRunRecord ────────────────────────────────────────────────────────────
@dataclass
class ToolRunRecord:
    """Single tool invocation record with full audit trail."""
    tool_name: str
    tool_version: Optional[str] = None
    candidate_id: str = ""
    input_files: List[str] = field(default_factory=list)
    output_files: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    command: Optional[str] = None
    random_seed: Optional[int] = None
    execution_mode: Optional[str] = None  # local / docker / remote_ssh
    status: ToolStatus = "not_run"
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    runtime_seconds: Optional[float] = None
    stdout_tail: Optional[str] = None
    stderr_tail: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    infrastructure_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def mark_start(self) -> None:
        self.started_at = _utc_now_iso()
        self.status = "success"  # will be updated on failure

    def mark_end(self, status: ToolStatus = "success", runtime: Optional[float] = None) -> None:
        self.finished_at = _utc_now_iso()
        self.status = status
        if runtime is not None:
            self.runtime_seconds = round(runtime, 3)
        elif self.started_at:
            try:
                t0 = datetime.fromisoformat(self.started_at.replace("Z", "+00:00"))
                self.runtime_seconds = round(
                    (datetime.now(UTC) - t0).total_seconds(), 3
                )
            except Exception:
                pass


# ── DesignRecord ─────────────────────────────────────────────────────────────
@dataclass
class DesignRecord:
    """CDRH3 generation / design metadata."""
    method: str = "diffusion_model"
    model_name: Optional[str] = None
    seed: Optional[int] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: ToolStatus = "not_run"
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── StructureModelingRecord ──────────────────────────────────────────────────
@dataclass
class StructureModelingRecord:
    """Antibody structure modeling / folding metadata."""
    tool_name: str = ""
    tool_version: Optional[str] = None
    input_sequence: str = ""
    input_file: Optional[str] = None
    output_pdb: Optional[str] = None
    confidence: Optional[float] = None
    status: ToolStatus = "not_run"
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── DockingResult ────────────────────────────────────────────────────────────
@dataclass
class DockingResult:
    """HDOCK docking result with full provenance."""
    tool_name: str = "HDOCK"
    tool_version: Optional[str] = None
    candidate_id: str = ""
    execution_mode: Optional[str] = None  # local / docker / remote_ssh
    receptor_file: Optional[str] = None
    ligand_file: Optional[str] = None
    rsite_file: Optional[str] = None
    output_dir: Optional[str] = None
    selected_pose_file: Optional[str] = None
    all_pose_files: List[str] = field(default_factory=list)
    hdock_score: Optional[float] = None
    confidence_score: Optional[float] = None
    top_poses: List[Dict[str, Any]] = field(default_factory=list)
    selection_reason: Optional[str] = None
    status: ToolStatus = "not_run"
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    infrastructure_warnings: List[str] = field(default_factory=list)
    tool_run: Optional[ToolRunRecord] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.tool_run:
            d["tool_run"] = self.tool_run.to_dict()
        return d


# ── RosettaResult ────────────────────────────────────────────────────────────
@dataclass
class RosettaResult:
    """Rosetta scoring result with explicit fallback tracking.

    CRITICAL INVARIANT: When fallback_used=True or raw_score_type is
    "fallback_score" / "decomposition_score", the interface_dG, dSASA_int,
    shape_complementarity, and interface_hbonds fields MUST remain None.
    Fallback scores must NOT be silently promoted to interface metrics.
    """
    tool_name: str = "PyRosetta"
    tool_version: Optional[str] = None
    candidate_id: str = ""
    protocol: Optional[str] = None
    score_function: Optional[str] = None
    input_complex_pdb: Optional[str] = None
    output_pdb: Optional[str] = None
    # Primary scores — ONLY populated by InterfaceAnalyzer
    total_score: Optional[float] = None
    interface_dG: Optional[float] = None
    dG_separated: Optional[float] = None
    dSASA_int: Optional[float] = None
    shape_complementarity: Optional[float] = None
    interface_hbonds: Optional[int] = None
    unsat_hbonds: Optional[int] = None
    fa_atr: Optional[float] = None
    fa_rep: Optional[float] = None
    packstat: Optional[float] = None
    # Raw score tracking — always populated regardless of scoring method
    raw_score: Optional[float] = None
    decomposition_score: Optional[float] = None
    raw_score_type: ScoreType = "unknown"
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    status: ToolStatus = "not_run"
    subprocess_success: bool = False
    scientific_status: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    tool_run: Optional[ToolRunRecord] = None

    def __post_init__(self) -> None:
        """Enforce invariant: fallback scores must not leak into interface fields.

        When fallback_used=True or raw_score_type is fallback/decomposition/unknown,
        ALL interface metric fields are unconditionally cleared. Each cleared
        field generates a specific warning so the leakage is auditable.
        """
        _FALLBACK_TYPES = ("fallback_score", "decomposition_score", "unknown")
        _is_fallback = (
            self.fallback_used
            or self.raw_score_type in _FALLBACK_TYPES
        )

        if not _is_fallback:
            return  # Real InterfaceAnalyzer result — fields are valid

        # Fields that ONLY InterfaceAnalyzer can populate
        _INTERFACE_ONLY_FIELDS = {
            "interface_dG": self.interface_dG,
            "dG_separated": self.dG_separated,
            "dSASA_int": self.dSASA_int,
            "shape_complementarity": self.shape_complementarity,
            "interface_hbonds": self.interface_hbonds,
            "unsat_hbonds": self.unsat_hbonds,
            "packstat": self.packstat,
        }

        cleared_fields = []
        for field_name, value in _INTERFACE_ONLY_FIELDS.items():
            if value is not None:
                setattr(self, field_name, None)
                cleared_fields.append(field_name)

        if cleared_fields:
            msg = (
                f"Fallback result (type={self.raw_score_type}, "
                f"fallback_used={self.fallback_used}) had non-null interface "
                f"fields leaked: {cleared_fields}. ALL cleared to None. "
                f"Fallback scores are NOT equivalent to interface metrics."
            )
            if msg not in self.warnings:
                self.warnings.append(msg)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.tool_run:
            d["tool_run"] = self.tool_run.to_dict()
        return d

    @property
    def display_score_type(self) -> str:
        """Human-readable score type for reports."""
        labels = {
            "interface_dG": "Interface ΔG (REU)",
            "dG_separated": "dG_separated (REU)",
            "total_score": "Total Score (REU)",
            "decomposition_score": "Decomposition Score (REU)",
            "fallback_score": "FALLBACK/DEGRADED Score",
            "unknown": "Unknown Score Type",
        }
        return labels.get(self.raw_score_type, self.raw_score_type)

    @property
    def has_interface_metrics(self) -> bool:
        """True only if full InterfaceAnalyzer metrics are available.

        Requires: not fallback, dG_separated is set, and score_type is
        a genuine interface metric type.
        """
        return (
            not self.fallback_used
            and self.dG_separated is not None
            and self.raw_score_type in ("interface_dG", "dG_separated")
            and self.interface_dG is not None  # additional safety
        )

    def validate_no_interface_leakage(self) -> List[str]:
        """Return violations if fallback score leaked into interface fields.

        Since __post_init__ now clears all interface fields on fallback,
        this method validates that the guard worked correctly.
        """
        violations = []
        fallback_types = ("fallback_score", "decomposition_score", "unknown")
        if self.raw_score_type in fallback_types or self.fallback_used:
            checks = {
                "interface_dG": self.interface_dG,
                "dG_separated": self.dG_separated,
                "dSASA_int": self.dSASA_int,
                "shape_complementarity": self.shape_complementarity,
                "interface_hbonds": self.interface_hbonds,
                "unsat_hbonds": self.unsat_hbonds,
                "packstat": self.packstat,
            }
            for name, value in checks.items():
                if value is not None:
                    violations.append(
                        f"[{self.candidate_id}] {name}={value} leaked on "
                        f"fallback result (type={self.raw_score_type}, "
                        f"fallback_used={self.fallback_used})"
                    )
        return violations


# ── SequenceFeatures ─────────────────────────────────────────────────────────
@dataclass
class SequenceFeatures:
    """Quantitative sequence features for QC assessment."""
    candidate_id: str = ""
    cdrh3_length: int = 0
    vh_length: Optional[int] = None
    net_charge_pH_7_4: Optional[float] = None
    pI: Optional[float] = None
    gravy: Optional[float] = None
    aromatic_fraction: Optional[float] = None
    hydrophobic_fraction: Optional[float] = None
    cys_count_total: Optional[int] = None
    cys_count_cdrh3: int = 0
    nglyc_motifs: List[str] = field(default_factory=list)
    low_complexity_regions: List[str] = field(default_factory=list)
    max_hydrophobic_run: Optional[int] = None
    max_identical_run: Optional[int] = None
    epitope_net_charge: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── SequenceQC ───────────────────────────────────────────────────────────────
@dataclass
class SequenceQC:
    """Layered sequence QC result."""
    candidate_id: str = ""
    status: QCStatus = "pass"
    risk_flags: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    penalty: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def is_pass(self) -> bool:
        return self.status == "pass"

    @property
    def is_fail(self) -> bool:
        return self.status == "fail"


# ── DevelopabilityQC ─────────────────────────────────────────────────────────
@dataclass
class DevelopabilityQC:
    """Aggregated developability QC — gates experimental readiness."""
    candidate_id: str = ""
    status: DevelopabilityStatus = "not_run"
    risk_flags: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def is_pass(self) -> bool:
        return self.status == "pass"

    @property
    def is_fail(self) -> bool:
        return self.status == "fail"


# ── Ranking ──────────────────────────────────────────────────────────────────
@dataclass
class Ranking:
    """Transparent candidate ranking with rationale."""
    candidate_id: str = ""
    composite_score: Optional[float] = None
    rank: Optional[int] = None
    rank_components: Dict[str, float] = field(default_factory=dict)
    recommendation: Recommendation = "insufficient_data"
    recommendation_reason: str = ""
    ranking_explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── CandidateResult (top-level) ──────────────────────────────────────────────
@dataclass
class CandidateResult:
    """Complete candidate result — single source of truth for one antibody candidate.

    This dataclass is the canonical representation of a candidate through the
    entire design→modeling→docking→scoring→QC→ranking pipeline. Reports, FASTA
    files, and JSON exports should derive exclusively from this structure.
    """
    # Identity
    candidate_id: str = ""
    run_id: str = ""
    epitope_sequence: str = ""
    cdrh3_sequence: str = ""
    vh_sequence: Optional[str] = None
    vl_sequence: Optional[str] = None
    antibody_format: Optional[str] = None
    framework_id: Optional[str] = None

    # Pipeline stages
    design: DesignRecord = field(default_factory=DesignRecord)
    structure_modeling: StructureModelingRecord = field(default_factory=StructureModelingRecord)
    docking: Optional[DockingResult] = None
    rosetta: Optional[RosettaResult] = None

    # QC layers
    sequence_features: SequenceFeatures = field(default_factory=SequenceFeatures)
    sequence_qc: SequenceQC = field(default_factory=SequenceQC)
    developability_qc: DevelopabilityQC = field(default_factory=DevelopabilityQC)

    # Ranking
    ranking: Ranking = field(default_factory=Ranking)

    # Contact analysis & generation filter
    contact_analysis: Optional[Dict[str, Any]] = None
    generation_filter: Optional[Dict[str, Any]] = None

    # Audit
    tool_runs: List[ToolRunRecord] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        d = {
            "candidate_id": self.candidate_id,
            "run_id": self.run_id,
            "epitope_sequence": self.epitope_sequence,
            "cdrh3_sequence": self.cdrh3_sequence,
            "vh_sequence": self.vh_sequence,
            "vl_sequence": self.vl_sequence,
            "antibody_format": self.antibody_format,
            "framework_id": self.framework_id,
            "design": self.design.to_dict(),
            "structure_modeling": self.structure_modeling.to_dict(),
            "docking": self.docking.to_dict() if self.docking else None,
            "rosetta": self.rosetta.to_dict() if self.rosetta else None,
            "sequence_features": self.sequence_features.to_dict(),
            "sequence_qc": self.sequence_qc.to_dict(),
            "developability_qc": self.developability_qc.to_dict(),
            "ranking": self.ranking.to_dict(),
            "generation_filter": self.generation_filter,
            "contact_analysis": self.contact_analysis,
            "tool_runs": [tr.to_dict() for tr in self.tool_runs],
            "warnings": self.warnings,
            "errors": self.errors,
            "assumptions": self.assumptions,
        }
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def add_tool_run(self, run: ToolRunRecord) -> None:
        run.candidate_id = run.candidate_id or self.candidate_id
        self.tool_runs.append(run)

    def add_warning(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)

    def add_error(self, msg: str) -> None:
        if msg not in self.errors:
            self.errors.append(msg)

    # ── FASTA header generation ───────────────────────────────────────────
    def fasta_header(self, max_length: int = 200) -> str:
        """Generate a QC-consistent FASTA header.

        Aggregates ALL risk sources: sequence QC, developability QC, VH Cys,
        docking/contact/rosetta status, VL availability, fallback usage.
        Key rule: if any risk exists, risk field CANNOT be 'none'.
        """
        risk_str, all_risks = self._risk_string_with_sources()
        header = (
            f"{self.candidate_id} | "
            f"epitope={self.epitope_sequence} | "
            f"CDRH3={self.cdrh3_sequence} | "
            f"structure_QC={self.structure_modeling.status} | "
            f"docking_QC={self.docking.status if self.docking else 'not_run'} | "
            f"rosetta_QC={self.rosetta.status if self.rosetta else 'not_run'} | "
            f"sequence_QC={self.sequence_qc.status} | "
            f"developability_QC={self.developability_qc.status} | "
            f"risk={risk_str} | "
            f"recommendation={self.ranking.recommendation}"
        )
        if len(header) > max_length:
            # Truncated: keep critical risks only
            critical = self._critical_risks(all_risks)
            risk_short = ",".join(critical) if critical else "none"
            header = (
                f"{self.candidate_id} | "
                f"CDRH3={self.cdrh3_sequence} | "
                f"seq_QC={self.sequence_qc.status} | "
                f"dev_QC={self.developability_qc.status} | "
                f"risk={risk_short} | "
                f"rec={self.ranking.recommendation}"
            )
        return header

    @staticmethod
    def fasta_short_header(candidate_id: str, cdrh3: str,
                           seq_qc: str, dev_qc: str,
                           risk_flags: List[str],
                           recommendation: str) -> str:
        """Generate a compact FASTA header."""
        risk_str = ",".join(risk_flags) if risk_flags else "none"
        return (
            f">{candidate_id} | CDRH3={cdrh3} | "
            f"seq_QC={seq_qc} | dev_QC={dev_qc} | "
            f"risk={risk_str} | rec={recommendation}"
        )

    def _risk_string(self) -> str:
        """Generate risk string — NEVER 'none' if flags are non-empty."""
        risk_str, _ = self._risk_string_with_sources()
        return risk_str

    def _risk_string_with_sources(self) -> tuple:
        """Generate risk string with ALL sources aggregated.

        Returns (risk_string, all_risk_flags_list).
        Aggregates from: sequence_qc, developability_qc, VH Cys, docking,
        contact_analysis, rosetta, VL, fallback status.
        """
        risks = []

        # Sequence & developability QC
        risks.extend(self.sequence_qc.risk_flags)
        risks.extend(self.developability_qc.risk_flags)

        # VH cysteine status
        vh_seq = self.vh_sequence or ""
        vh_cys = vh_seq.count("C")
        if vh_cys != 2:
            if vh_cys % 2 != 0:
                risks.append("odd_cysteine_count")
            elif vh_cys > 2:
                risks.append("unexpected_cysteine_count")

        # Docking status
        if self.docking:
            if self.docking.status in ("not_run",):
                risks.append("docking_not_run")
            elif self.docking.status in ("failed",):
                risks.append("docking_failed")
        else:
            risks.append("docking_not_run")

        # Contact analysis
        ca = self.contact_analysis or {}
        ca_status = ca.get("status", "not_run")
        ca_cov = ca.get("contact_coverage", 0.0)
        if ca_status in ("not_run",):
            risks.append("contact_analysis_not_run")
        elif ca_status in ("failed",):
            risks.append("contact_analysis_failed")
        elif ca_status == "warning":
            if ca_cov < 0.4:
                risks.append("low_contact_coverage")
            # Check W6 for PSAEVWD
            positions = ca.get("contacted_epitope_positions", [])
            if self.epitope_sequence == "PSAEVWD" and 5 not in positions:
                risks.append("w6_not_contacted")
        elif ca_status == "success":
            # Even on success, check W6
            positions_s = ca.get("contacted_epitope_positions", [])
            if self.epitope_sequence == "PSAEVWD" and 5 not in positions_s:
                risks.append("w6_not_contacted")

        # Rosetta
        if self.rosetta:
            if self.rosetta.status in ("not_run",):
                risks.append("rosetta_not_run")
            elif self.rosetta.status in ("failed", "fallback"):
                risks.append("rosetta_fallback" if self.rosetta.fallback_used
                            else "rosetta_failed")
        else:
            risks.append("rosetta_not_run")

        # VL availability
        if not self.vl_sequence:
            risks.append("no_real_VL")

        # Deduplicate and stable-sort (critical first)
        seen = set()
        all_risks = []
        for r in risks:
            if r not in seen:
                seen.add(r)
                all_risks.append(r)

        # Sort: critical risks first
        critical_order = {
            "extra_Cys_in_CDRH3": 0, "odd_cysteine_count": 1,
            "unexpected_cysteine_count": 2, "empty_sequence": 3,
            "invalid_amino_acid": 4, "cdrh3_length_high_risk": 5,
            "docking_not_run": 10, "docking_failed": 11,
            "contact_analysis_not_run": 12, "contact_analysis_failed": 13,
            "rosetta_not_run": 14, "rosetta_fallback": 15, "rosetta_failed": 16,
            "no_real_VL": 17,
        }
        all_risks.sort(key=lambda x: critical_order.get(x, 50))

        risk_str = ",".join(all_risks) if all_risks else "none"
        return risk_str, all_risks

    @staticmethod
    def _critical_risks(all_risks: list) -> list:
        """Filter to only the most critical risks for truncated headers."""
        critical_patterns = [
            "extra_Cys", "odd_cysteine", "unexpected_cysteine",
            "docking_not_run", "docking_failed",
            "contact_analysis_not_run", "contact_analysis_failed",
            "rosetta_fallback", "rosetta_not_run", "rosetta_failed",
            "no_real_VL",
        ]
        result = []
        for r in all_risks:
            if any(p in r for p in critical_patterns):
                result.append(r)
        # Also keep CDRH3 length risk if present
        for r in all_risks:
            if "cdrh3_length" in r.lower() and r not in result:
                result.append(r)
        return result if result else all_risks[:5]

    # ── Report status lines with correct icons ───────────────────────────
    def report_status_lines(self) -> List[str]:
        """Generate status-icon-prefixed summary lines for reports.

        Uses the correct icon for each status: ✅=pass, ⚠️=warning/not_run,
        ❌=fail/odd_cys, ❔=unknown.
        """
        lines = []

        # Sequence QC
        sqc_icon = status_icon(self.sequence_qc.status, self.sequence_qc.risk_flags)
        sqc_flags = ", ".join(self.sequence_qc.risk_flags) if self.sequence_qc.risk_flags else "none"
        lines.append(
            f"{sqc_icon} sequence_QC: {self.sequence_qc.status} ({sqc_flags})"
        )

        # Developability QC
        dqc_icon = status_icon(self.developability_qc.status)
        dqc_flags = ", ".join(self.developability_qc.risk_flags) if self.developability_qc.risk_flags else "none"
        lines.append(
            f"{dqc_icon} developability_QC: {self.developability_qc.status} ({dqc_flags})"
        )

        # VH Cysteine
        vh_seq = self.vh_sequence or ""
        vh_cys = vh_seq.count("C")
        vh_cys_status = "ok" if vh_cys == 2 else (
            "odd_cysteine_count" if vh_cys % 2 != 0 else "unexpected_cysteine_count"
        )
        cys_icon = status_icon(vh_cys_status)
        # Detect if VH is from default scaffold (always has 2 Cys in FR)
        is_default_scaffold = (
            not self.vl_sequence
            and vh_seq
            and "GWWRQAPGKEREA" in vh_seq
        )
        scaffold_note = " (默认 scaffold VH)" if is_default_scaffold else ""
        if vh_cys != 2:
            lines.append(
                f"{cys_icon} VH Cys{scaffold_note}: {vh_cys} ({vh_cys_status}) — "
                "requires IMGT/Kabat/ANARCI numbering; do not suggest position-specific mutations"
            )
        else:
            lines.append(
                f"{cys_icon} VH Cys{scaffold_note}: {vh_cys} "
                "(1 conserved intra-domain disulfide)"
            )

        # Docking
        dock_status = self.docking.status if self.docking else "not_run"
        dock_icon = status_icon(dock_status)
        dock_line = f"{dock_icon} HDOCK: {dock_status}"
        # If HDOCK ran but contact_analysis not run, add caveat
        ca = self.contact_analysis or {}
        ca_status = ca.get("status", "not_run")
        if dock_status == "success" and ca_status == "not_run":
            dock_line += " (缺少 contact_analysis，不可判断 W6/D7 接触)"
        elif dock_status == "success":
            dock_line += " (探索性 docking, 默认 scaffold)"
        lines.append(dock_line)

        # Rosetta
        ros_status = self.rosetta.status if self.rosetta else "not_run"
        ros_icon = status_icon(ros_status)
        ros_detail = ""
        if self.rosetta:
            if self.rosetta.fallback_used:
                ros_detail = f" (fallback: {self.rosetta.raw_score_type})"
            elif self.rosetta.raw_score is not None:
                ros_detail = f" (score: {self.rosetta.raw_score})"
        lines.append(f"{ros_icon} Rosetta: {ros_status}{ros_detail}")

        # Contact analysis
        ca_status = ca.get("status", "not_run")
        ca_icon = status_icon(ca_status)
        ca_detail = ""
        if ca_status == "success":
            ca_cov = ca.get("contact_coverage", 0.0)
            ca_detail = f" (coverage={ca_cov})"
        elif ca_status == "not_run" and dock_status == "success":
            ca_detail = " — 已完成探索性 docking，但缺少 contact_analysis，不可判断 W6/D7 接触"
        lines.append(f"{ca_icon} contact_analysis: {ca_status}{ca_detail}")

        # Charge analysis — can use ✅ if complementary
        if self.generation_filter:
            lines.append("✅ generation_filter: applied (see generation_filter field)")

        # VL / Scaffold
        if self.vl_sequence:
            lines.append("✅ VL: provided")
        elif self.vh_sequence and not self.vl_sequence:
            # Has VH but no VL — default scaffold used
            vh_has_vhh_motifs = any(
                m in (self.vh_sequence or "") for m in ("GWWRQ", "EREA", "EREF", "EREG", "GLVW")
            )
            if vh_has_vhh_motifs:
                lines.append(
                    "⚠️ VL: not provided — 默认 scaffold 含 VHH FR2 基序，"
                    "但不可自动称为 VHH 纳米抗体。该单链模型仅用于探索性 folding + docking，"
                    "不能判断完整 IgG/Fab/scFv 表达可行性、VH/VL 界面或真实轻链配对。"
                )
            else:
                lines.append(
                    "⚠️ VL: not provided — 使用默认 VH scaffold 进行探索性建模，"
                    "不能判断完整 IgG/Fab/scFv 表达可行性或真实轻链配对。"
                )
        else:
            lines.append("⚠️ VL/VH: not provided — cannot claim paired IgG or complete antibody")

        # Recommendation
        rec_icon = "✅" if "recommended_for_experimental" in self.ranking.recommendation else (
            "⚠️" if "priority" in self.ranking.recommendation or "conditional" in self.ranking.recommendation
            else "❌" if "redesign" in self.ranking.recommendation or "not_recommended" in self.ranking.recommendation
            else "❔"
        )
        lines.append(
            f"{rec_icon} recommendation: {self.ranking.recommendation}"
        )
        if self.ranking.recommendation_reason:
            lines.append(f"   → reason: {self.ranking.recommendation_reason}")

        return lines

    # ── Summary row for reports ──────────────────────────────────────────
    def summary_row(self) -> Dict[str, Any]:
        """Return a single-row dict for report tables."""
        rosetta_score = None
        score_type = "not_run"
        fallback_used = False
        if self.rosetta:
            rosetta_score = self.rosetta.raw_score
            score_type = self.rosetta.raw_score_type
            fallback_used = self.rosetta.fallback_used

        return {
            "candidate_id": self.candidate_id,
            "CDRH3": self.cdrh3_sequence,
            "length": len(self.cdrh3_sequence),
            "HDOCK_score": self.docking.hdock_score if self.docking else "not_run",
            "Rosetta_score": rosetta_score if rosetta_score is not None else "not_run",
            "score_type": score_type,
            "fallback_used": fallback_used,
            "sequence_QC": self.sequence_qc.status,
            "developability_QC": self.developability_qc.status,
            "final_recommendation": self.ranking.recommendation,
            "reason": self.ranking.recommendation_reason,
        }


# ── CandidateResult batch helpers ────────────────────────────────────────────
# ── Status icon utility ──────────────────────────────────────────────────────

def status_icon(status: str, risk_flags: Optional[List[str]] = None) -> str:
    """Return the correct emoji icon for a pipeline status string.

    Rules:
        pass / success / ok → ✅
        warning / conditional_pass / partial / fallback / not_run → ⚠️
        fail / failed / rejected / odd_cysteine_count / extra_Cys / hard_fail → ❌
        unknown / insufficient_data → ❔
    """
    s = (status or "").lower().strip()
    risk_flags = risk_flags or []

    # Success group
    if s in ("pass", "success", "ok"):
        return "✅"

    # Danger group — always ❌
    if s in ("fail", "failed", "rejected", "hard_fail"):
        return "❌"
    if "odd_cysteine" in s or "extra_cys" in s:
        return "❌"
    if any("extra_Cys" in f or "odd_cysteine" in f for f in risk_flags):
        return "❌"

    # Warning group — ⚠️
    if s in ("warning", "conditional_pass", "partial", "fallback", "not_run",
             "degraded", "needs_remodeling"):
        return "⚠️"

    # Unknown
    if s in ("unknown", "insufficient_data"):
        return "❔"

    # Default: unknown
    return "❔"


# ── Candidate ID helpers ─────────────────────────────────────────────────────

def build_candidate_id(index: int) -> str:
    """Generate a canonical candidate ID from a 1-based index."""
    return f"C{index}"


def ensure_candidate_ids(results: List[Dict[str, Any]], offset: int = 1) -> List[Dict[str, Any]]:
    """Assign C1, C2, ... IDs to any results that lack a candidate_id."""
    for i, row in enumerate(results):
        if not row.get("candidate_id"):
            row["candidate_id"] = build_candidate_id(i + offset)
    return results


def candidate_to_row(candidate: CandidateResult) -> Dict[str, Any]:
    """Convert a CandidateResult to a dict row compatible with existing pipeline outputs."""
    return candidate.summary_row()


def generate_run_id() -> str:
    """Generate a unique run ID for this design round."""
    return f"run_{_new_id()}"
