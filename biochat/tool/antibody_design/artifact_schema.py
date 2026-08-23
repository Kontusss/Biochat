"""Universal provenance and anti-hallucination layer.

Every sequence, score, structure, and report conclusion must be traceable to a
real artifact. This module provides the schema, validation, and manifest system
that enforces evidence-bound pipeline behavior.

Target-agnostic: works for any epitope, antigen, peptide, or protein target.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Status taxonomy ────────────────────────────────────────────────────────
class ArtifactStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    NOT_RUN = "NOT_RUN"
    MISSING = "MISSING"
    TIMEOUT = "TIMEOUT"
    TOOL_NOT_AVAILABLE = "TOOL_NOT_AVAILABLE"
    UNVERIFIED = "UNVERIFIED"
    PRELIMINARY_PROXY_ONLY = "PRELIMINARY_PROXY_ONLY"


class SequenceType(str, Enum):
    CDRH3_FRAGMENT = "CDRH3_FRAGMENT"
    VH_VARIABLE_DOMAIN = "VH_VARIABLE_DOMAIN"
    VL_VARIABLE_DOMAIN = "VL_VARIABLE_DOMAIN"
    SCFV = "SCFV"
    IGG_HEAVY_CHAIN = "IGG_HEAVY_CHAIN"
    IGG_LIGHT_CHAIN = "IGG_LIGHT_CHAIN"
    VHH = "VHH"


class TargetType(str, Enum):
    SHORT_PEPTIDE = "short_peptide"          # 4-12 aa
    MEDIUM_PEPTIDE = "medium_peptide"        # 13-30 aa
    PROTEIN_PATCH = "protein_patch"          # surface patch on full protein
    FULL_PROTEIN = "full_protein"            # whole antigen
    UNKNOWN = "unknown"


# ── Core artifact record ───────────────────────────────────────────────────
def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _hash_string(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _hash_file(path: str) -> Optional[str]:
    if not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def new_artifact_id() -> str:
    return f"art_{uuid.uuid4().hex[:12]}"


class ArtifactRecord:
    """Single provenance record for one piece of pipeline output."""

    def __init__(
        self,
        artifact_id: str = "",
        run_id: str = "",
        target_id: str = "",
        target_type: str = "",
        candidate_id: str = "",
        stage: str = "",
        sequence_type: str = "",
        sequence: str = "",
        status: str = ArtifactStatus.NOT_RUN,
        source_tool: str = "",
        source_version: str = "",
        artifact_path: str = "",
        artifact_hash: str = "",
        scores: Optional[List[Dict[str, Any]]] = None,
        flags: Optional[List[str]] = None,
        failure_reason: str = "",
        timestamp: str = "",
    ):
        self.artifact_id = artifact_id or new_artifact_id()
        self.run_id = run_id
        self.target_id = target_id
        self.target_type = target_type
        self.candidate_id = candidate_id
        self.stage = stage
        self.sequence_type = sequence_type
        self.sequence = sequence
        self.status = status
        self.source_tool = source_tool
        self.source_version = source_version
        self.artifact_path = artifact_path
        self.artifact_hash = artifact_hash or (_hash_file(artifact_path) if artifact_path else "")
        self.scores = scores or []
        self.flags = flags or []
        self.failure_reason = failure_reason
        self.timestamp = timestamp or _utc_now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "run_id": self.run_id,
            "target_id": self.target_id,
            "target_type": self.target_type,
            "candidate_id": self.candidate_id,
            "stage": self.stage,
            "sequence_type": self.sequence_type,
            "sequence": self.sequence,
            "status": self.status,
            "source": {
                "tool": self.source_tool,
                "version": self.source_version,
                "artifact_path": self.artifact_path,
                "artifact_hash": self.artifact_hash,
                "timestamp": self.timestamp,
            },
            "scores": self.scores,
            "flags": self.flags,
            "failure_reason": self.failure_reason,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ArtifactRecord":
        src = d.get("source", {})
        return cls(
            artifact_id=d.get("artifact_id", ""),
            run_id=d.get("run_id", ""),
            target_id=d.get("target_id", ""),
            target_type=d.get("target_type", ""),
            candidate_id=d.get("candidate_id", ""),
            stage=d.get("stage", ""),
            sequence_type=d.get("sequence_type", ""),
            sequence=d.get("sequence", ""),
            status=d.get("status", ArtifactStatus.NOT_RUN),
            source_tool=src.get("tool", ""),
            source_version=src.get("version", ""),
            artifact_path=src.get("artifact_path", ""),
            artifact_hash=src.get("artifact_hash", ""),
            scores=d.get("scores", []),
            flags=d.get("flags", []),
            failure_reason=d.get("failure_reason", ""),
            timestamp=src.get("timestamp", ""),
        )


# ── Score record schema ────────────────────────────────────────────────────
def new_score_record(
    score_name: str,
    score_value: float,
    score_unit: str = "arbitrary",
    score_direction: str = "lower_is_better",
    score_source: str = "unknown",
    calibration_status: str = "UNCALIBRATED",
    artifact_path: str = "",
    candidate_id: str = "",
) -> Dict[str, Any]:
    """Create a standardized score record.

    score_direction: "lower_is_better" (e.g. ddG) or "higher_is_better" (e.g. affinity proxy)
    calibration_status: "CALIBRATED" | "UNCALIBRATED" | "UNRELIABLE_FOR_RANKING" | "UNKNOWN"
    """
    return {
        "score_name": score_name,
        "score_value": score_value,
        "score_unit": score_unit,
        "score_direction": score_direction,
        "score_source": score_source,
        "calibration_status": calibration_status,
        "artifact_path": artifact_path,
        "candidate_id": candidate_id,
    }


# ── Manifest ───────────────────────────────────────────────────────────────
class ProvenanceManifest:
    """Collects all artifact records for a single run.

    The manifest is the single source of truth for report generation.
    Reports MUST only reference artifacts present in the manifest.
    """

    def __init__(self, run_id: str = ""):
        self.run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        self.records: List[ArtifactRecord] = []
        self.run_config_hash: str = ""
        self.tool_availability: Dict[str, bool] = {}
        self.missing_fields: List[str] = []

    def add(self, record: ArtifactRecord) -> None:
        record.run_id = record.run_id or self.run_id
        self.records.append(record)

    def find_by_candidate(self, candidate_id: str) -> List[ArtifactRecord]:
        return [r for r in self.records if r.candidate_id == candidate_id]

    def find_by_stage(self, stage: str) -> List[ArtifactRecord]:
        return [r for r in self.records if r.stage == stage]

    def find_by_status(self, status: str) -> List[ArtifactRecord]:
        return [r for r in self.records if r.status == status]

    def has_real_scoring(self) -> bool:
        for r in self.records:
            for s in r.scores:
                if s.get("score_source", "") in {
                    "rosetta_subprocess_decomp",
                    "rosetta_subprocess_interface",
                    "rosetta_inproc_decomp",
                    "hdock",
                }:
                    return True
        return False

    def has_complete_igg(self) -> bool:
        has_vh = any(
            r.sequence_type == SequenceType.VH_VARIABLE_DOMAIN
            and r.status == ArtifactStatus.SUCCESS
            for r in self.records
        )
        has_vl = any(
            r.sequence_type == SequenceType.VL_VARIABLE_DOMAIN
            and r.status == ArtifactStatus.SUCCESS
            for r in self.records
        )
        return has_vh and has_vl

    def missing_required_artifacts(self) -> List[str]:
        """Return list of expected artifact types that are missing."""
        required_stages = {
            "target_analysis": False,
            "candidate_generation": False,
            "sequence_qc": False,
            "scoring": False,
        }
        for r in self.records:
            if r.stage in required_stages and r.status == ArtifactStatus.SUCCESS:
                required_stages[r.stage] = True
        return [k for k, v in required_stages.items() if not v]

    def summary(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "total_records": len(self.records),
            "by_status": {
                s.value: len(self.find_by_status(s.value))
                for s in ArtifactStatus
            },
            "has_real_scoring": self.has_real_scoring(),
            "has_complete_igg": self.has_complete_igg(),
            "missing_required": self.missing_required_artifacts(),
            "tool_availability": self.tool_availability,
            "run_config_hash": self.run_config_hash,
            "missing_fields": self.missing_fields,
        }

    def to_list(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self.records]

    def save(self, path: str) -> str:
        data = {
            "manifest_version": "1.0",
            "run_id": self.run_id,
            "run_config_hash": self.run_config_hash,
            "tool_availability": self.tool_availability,
            "summary": self.summary(),
            "records": self.to_list(),
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    @classmethod
    def load(cls, path: str) -> "ProvenanceManifest":
        with open(path) as f:
            data = json.load(f)
        m = cls(run_id=data.get("run_id", ""))
        m.run_config_hash = data.get("run_config_hash", "")
        m.tool_availability = data.get("tool_availability", {})
        for rd in data.get("records", []):
            m.add(ArtifactRecord.from_dict(rd))
        return m


# ── Strict provenance mode ─────────────────────────────────────────────────
class StrictProvenanceMode:
    """Global guard that prevents reports from fabricating data.

    When enabled (default), any claim in a report must be backed by an
    artifact in the manifest. Missing artifacts produce UNVERIFIED markers,
    never fabricated values.
    """

    _enabled: bool = True

    @classmethod
    def is_enabled(cls) -> bool:
        return cls._enabled and os.getenv("STRICT_PROVENANCE", "1") == "1"

    @classmethod
    def set_enabled(cls, value: bool) -> None:
        cls._enabled = value


# ── Claim validators ───────────────────────────────────────────────────────
def validate_sequence_claim(sequence: str, manifest: ProvenanceManifest) -> str:
    """Check if a sequence exists in the manifest. Returns status marker."""
    if not sequence:
        return "MISSING"
    seq_hash = _hash_string(sequence)
    for r in manifest.records:
        if r.sequence and _hash_string(r.sequence) == seq_hash:
            return r.status
    return "UNVERIFIED"


def validate_structure_claim(pdb_path: str, manifest: ProvenanceManifest) -> str:
    """Check if a PDB path is backed by a real artifact."""
    if not pdb_path:
        return "MISSING"
    if not os.path.isfile(pdb_path):
        return "MISSING"
    file_hash = _hash_file(pdb_path)
    for r in manifest.records:
        if r.artifact_hash == file_hash:
            return r.status
    return "UNVERIFIED"


def validate_scoring_claim(score_value: float, manifest: ProvenanceManifest) -> str:
    """Check if a score value is backed by a real scoring artifact."""
    for r in manifest.records:
        for s in r.scores:
            if abs(s.get("score_value", 0.0) - score_value) < 1e-6:
                return r.status
    return "UNVERIFIED"


# ── Report-safe getters ────────────────────────────────────────────────────
def safe_get_sequence(manifest: ProvenanceManifest, candidate_id: str,
                      seq_type: str) -> Dict[str, Any]:
    """Get a sequence from manifest, never fabricate."""
    for r in manifest.records:
        if r.candidate_id == candidate_id and r.sequence_type == seq_type:
            return {
                "sequence": r.sequence,
                "status": r.status,
                "source": r.source_tool,
                "artifact_path": r.artifact_path,
                "artifact_hash": r.artifact_hash,
                "flags": r.flags,
            }
    return {
        "sequence": "",
        "status": "MISSING",
        "source": "",
        "artifact_path": "",
        "artifact_hash": "",
        "flags": ["MISSING_FROM_MANIFEST"],
    }


def safe_get_score(manifest: ProvenanceManifest, candidate_id: str,
                   score_name: str) -> Dict[str, Any]:
    """Get a score from manifest, never fabricate."""
    for r in manifest.records:
        if r.candidate_id == candidate_id:
            for s in r.scores:
                if s.get("score_name") == score_name:
                    return s
    return {
        "score_name": score_name,
        "score_value": None,
        "score_unit": "unknown",
        "score_direction": "unknown",
        "score_source": "NOT_RUN",
        "calibration_status": "UNKNOWN",
    }


# ── Report caveat generators ───────────────────────────────────────────────
def generate_report_caveats(manifest: ProvenanceManifest) -> List[str]:
    """Generate mandatory caveats based on what's actually in the manifest."""
    caveats = []
    if not manifest.has_real_scoring():
        caveats.append(
            "PRELIMINARY_PROXY_ONLY: 本报告仅基于代理评分，未执行真实物理对接/Rosetta计算。"
            "所有 binding affinity 结论均为初步估计，不可作为实验验证依据。"
        )
    if not manifest.has_complete_igg():
        caveats.append(
            "INCOMPLETE_ANTIBODY: 当前未产出完整 VH+VL 配对的 IgG 抗体。"
            "缺少轻链可变区（VL），不可声称完整 IgG。"
        )
    missing = manifest.missing_required_artifacts()
    if missing:
        caveats.append(
            f"MISSING_ARTIFACTS: 以下关键阶段无 artifact: {', '.join(missing)}。"
            "相关结论不可信。"
        )
    for tool, available in manifest.tool_availability.items():
        if not available:
            caveats.append(f"TOOL_NOT_AVAILABLE: {tool} 不可用，相关结果缺失或为代理值。")
    if not caveats:
        caveats.append("所有关键 artifact 均已验证，报告结论可追溯到真实计算输出。")
    return caveats


# ── Anti-hallucination assertions ──────────────────────────────────────────
def assert_no_fabricated_sequence(seq: str, manifest: ProvenanceManifest,
                                   context: str = "") -> None:
    """Raise if a sequence cannot be traced to the manifest."""
    if StrictProvenanceMode.is_enabled():
        status = validate_sequence_claim(seq, manifest)
        if status in ("UNVERIFIED", "MISSING"):
            raise AssertionError(
                f"[ANTI-HALLUCINATION] {context}: 序列无法溯源到任何 artifact (status={status})。"
                f"禁止编造序列。"
            )


def assert_no_fabricated_structure(pdb_path: str, manifest: ProvenanceManifest,
                                    context: str = "") -> None:
    """Raise if a structure file cannot be verified."""
    if StrictProvenanceMode.is_enabled():
        if not pdb_path:
            raise AssertionError(
                f"[ANTI-HALLUCINATION] {context}: PDB 路径为空，禁止声称结构已生成。"
            )
        if not os.path.isfile(pdb_path):
            raise AssertionError(
                f"[ANTI-HALLUCINATION] {context}: PDB 文件不存在 ({pdb_path})，"
                f"禁止声称 fold success。"
            )
