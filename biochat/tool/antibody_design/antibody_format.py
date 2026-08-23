"""Antibody format state machine — prevents auto-switching to VHH and enforces
format-aware guardrails on design output.

Core invariant:  the system MUST NOT switch to VHH/nanobody workflow unless the
user explicitly requests it.  Detection of camelid FR2 motifs in the default
scaffold does NOT constitute a user request.

Also provides artifact-truthfulness checks so the renderer never claims a file
"has been saved / generated" without actual tool evidence.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


# ── Enums ──────────────────────────────────────────────────────────────────────

class DesignFormat(str, Enum):
    """Antibody format explicitly requested by the user or inferred from input."""
    UNSPECIFIED = "unspecified"           # user never specified a format
    VH_EXPLORATORY = "VH_exploratory"     # default scaffold exploratory only
    IGG = "IgG"                           # full IgG (VH + VL)
    FAB = "Fab"                           # Fab fragment
    SCFV = "scFv"                         # single-chain Fv
    VHH = "VHH"                           # camelid nanobody (explicitly requested)


class ScaffoldType(str, Enum):
    """Type of default scaffold used when user provides no VH/VL."""
    HUMAN_VH = "human_VH"    # IGHV3-family human VH framework
    VHH = "VHH"              # genuine VHH/camelid scaffold
    NONE = "none"            # no scaffold available


# ── Mappings ───────────────────────────────────────────────────────────────────

# Terms that are ONLY allowed when design_format == VHH
VHH_ONLY_TERMS: Set[str] = {
    "VHH", "纳米抗体", "nanobody", "single-domain antibody",
    "骆驼源", "camelid", "llama", "alpaca", "IGHV3H", "VHH scaffold",
    "VHH hallmark", "hallmark residues", "FR2 ERE", "EREGWGR",
    "标准骆驼源", "camelid VHH scaffold",
}

# Terms that are ONLY allowed when a real file artifact exists
ARTIFACT_CLAIM_PATTERNS: List[str] = [
    r"已保存.*(?:文件|PDB|PDF|FASTA|CSV|报告)",
    r"已生成.*(?:并保存|文件|报告)",
    r"已写入.*(?:文件|路径|目录)",
    r"文件.*已.*(?:保存|生成|创建|写入)",
    r"(?:提供|可|请).*下载",
    r"保存.*路径.*(?:真实|可.*写入|有效)",
    r"report.*\.pdf",
    r"vhh_.*\.pdb",
    r"psaevwd.*\.pdb",
]

# Terms that require HDOCK to have actually run
HDOCK_CLAIM_PATTERNS: List[str] = [
    r"平台.*不支持.*HDOCK",
    r"HDOCK.*不可用(?!.*独立.*接口)",
]

# Mutation terms that are ONLY allowed for true humanization
HUMANIZATION_ONLY_TERMS: Set[str] = {
    "人源化", "humanization", "CDR移植", "CDR grafting",
    "framework replacement", "backmutation",
}

# ── State machine ──────────────────────────────────────────────────────────────

@dataclass
class AntibodyFormatState:
    """Tracks the current antibody design format and what claims are allowed."""

    design_format: DesignFormat = DesignFormat.UNSPECIFIED
    user_requested_format: Optional[str] = None       # raw user input
    default_scaffold_type: ScaffoldType = ScaffoldType.HUMAN_VH
    has_real_vh: bool = False
    has_real_vl: bool = False
    vhh_motifs_detected: bool = False                  # in default scaffold
    hdock_ran: bool = False
    hdock_independent_available: bool = False          # run_hdock_from_pdb tool
    contact_analysis_ran: bool = False
    artifacts_verified: Dict[str, bool] = field(default_factory=dict)

    def is_vhh_allowed(self) -> bool:
        """VHH terminology is ONLY allowed when explicitly requested by user."""
        return self.design_format == DesignFormat.VHH

    def can_claim_artifact_exists(self, path: str) -> bool:
        """Can we claim a file exists? Only if verified by tool output."""
        return self.artifacts_verified.get(path, False)

    def can_claim_hdock_standalone(self) -> bool:
        """Can we claim HDOCK is available as a standalone tool?"""
        return self.hdock_independent_available

    def can_claim_humanization(self) -> bool:
        """Humanization claims require non-human input + actual framework replacement."""
        return False  # de-novo CDRH3 grafting is NEVER humanization

    def get_allowed_format_description(self) -> str:
        """Return the correct format description based on current state."""
        if self.design_format == DesignFormat.VHH:
            return "VHH (纳米抗体) — 用户明确指定的单域抗体格式"
        if self.design_format in (DesignFormat.IGG, DesignFormat.FAB, DesignFormat.SCFV):
            return f"{self.design_format.value} — 用户指定的抗体格式"
        # UNSPECIFIED or VH_EXPLORATORY
        if self.has_real_vh and self.has_real_vl:
            return "完整 VH+VL — 可评估 IgG/Fab/scFv 格式"
        return (
            "未指定抗体格式 — 系统使用默认人源 VH scaffold 进行探索性 "
            "CDRH3 grafting 和结构建模。该结果不等于完整 IgG/Fab/scFv，"
            "也不等于 VHH 纳米抗体。"
        )


# ── Validation functions ───────────────────────────────────────────────────────

def validate_format_claims(text: str, state: AntibodyFormatState) -> List[str]:
    """Check text for forbidden format claims and return violations.

    Returns list of violation descriptions (empty = clean).
    """
    violations: List[str] = []

    # 1. VHH auto-switch guard
    if not state.is_vhh_allowed():
        for term in VHH_ONLY_TERMS:
            if term.lower() in text.lower():
                # Allow negations
                if any(neg in text.lower() for neg in [
                    "不是", "不等于", "不能自动称为", "不代表",
                    "not ", "cannot", "does not", "not a",
                ]):
                    # Check if the term appears in a negated context nearby
                    idx = text.lower().find(term.lower())
                    before = text[max(0, idx - 40):idx].lower()
                    if any(n in before for n in [
                        "不是", "不等于", "不能", "不代表", "not ", "cannot",
                    ]):
                        continue
                violations.append(f"VHH term '{term}' used without explicit VHH request")

    # 2. Artifact truthfulness guard
    for pattern in ARTIFACT_CLAIM_PATTERNS:
        import re
        if re.search(pattern, text, re.IGNORECASE):
            # Check if any artifact path is verified
            if not any(state.artifacts_verified.values()):
                violations.append(
                    f"File artifact claim '{pattern}' without verified artifact existence"
                )

    # 3. Humanization vs grafting guard
    if not state.can_claim_humanization():
        for term in HUMANIZATION_ONLY_TERMS:
            if term.lower() in text.lower():
                # Only flag if it's describing de-novo CDRH3 work
                if any(ctx in text.lower() for ctx in [
                    "de novo", "从头设计", "cdrh3", "graft",
                ]):
                    violations.append(
                        f"'{term}' used for de-novo CDRH3 grafting — "
                        "use 'human scaffold grafting' instead"
                    )

    return violations


def assert_artifact_exists(path: str) -> bool:
    """Check if a file artifact actually exists on disk.

    The renderer must call this before claiming any file was generated.
    """
    if not path or not isinstance(path, str):
        return False
    try:
        return os.path.isfile(path) and os.path.getsize(path) > 0
    except (OSError, TypeError):
        return False


def get_allowed_format_terms(state: AntibodyFormatState) -> Set[str]:
    """Return the set of format-related terms allowed given the current state."""
    allowed: Set[str] = set()

    # Always allowed
    allowed.add("CDRH3")
    allowed.add("scaffold")
    allowed.add("grafting")
    allowed.add("exploratory")
    allowed.add("默认 scaffold")

    # Format-specific
    if state.design_format == DesignFormat.VHH:
        allowed.update(VHH_ONLY_TERMS)
    elif state.design_format in (DesignFormat.IGG, DesignFormat.FAB, DesignFormat.SCFV):
        allowed.add("IgG")
        allowed.add("VH/VL")
        allowed.add("light chain")
        allowed.add("轻链")

    # Scaffold type
    if state.default_scaffold_type == ScaffoldType.HUMAN_VH:
        allowed.add("human VH scaffold")
        allowed.add("人源 VH scaffold")
        allowed.add("IGHV3")

    return allowed


def format_discipline_notice(state: AntibodyFormatState) -> str:
    """Generate the format discipline notice for the system prompt or tool output.

    This is the canonical text that explains what format is in use and
    what the limitations are.
    """
    if state.design_format == DesignFormat.VHH:
        return (
            "格式: VHH (纳米抗体) — 用户明确指定。使用经验证的 VHH scaffold，"
            "检查 hallmark residues，不要求 VL 配对。"
        )

    if state.design_format == DesignFormat.UNSPECIFIED:
        if state.vhh_motifs_detected and state.default_scaffold_type == ScaffoldType.HUMAN_VH:
            return (
                "⚠️ 格式未指定。默认 scaffold 含 camelid FR2 基序 (GWWRQ/EREA)，"
                "但这不代表 VHH。系统仅进行探索性 human VH scaffold CDRH3 grafting。"
                "如需 VHH/纳米抗体，请明确说明。"
            )
        return (
            "格式未指定。系统使用默认人源 VH scaffold 进行探索性 CDRH3 grafting "
            "和结构建模。该结果不等于完整 IgG/Fab/scFv，也不等于 VHH 纳米抗体。"
        )

    if state.design_format == DesignFormat.VH_EXPLORATORY:
        return (
            "探索性 VH scaffold 建模 — 不代表真实 IgG/Fab/scFv/VHH 格式。"
            "需用户提供完整 VH/VL 或明确格式后才可评估。"
        )

    return f"格式: {state.design_format.value}"


def build_default_format_state(
    user_requested_format: Optional[str] = None,
    has_real_vh: bool = False,
    has_real_vl: bool = False,
    hdock_ran: bool = False,
    hdock_independent_available: bool = False,
    contact_analysis_ran: bool = False,
    artifacts_verified: Optional[Dict[str, bool]] = None,
) -> AntibodyFormatState:
    """Build an AntibodyFormatState from available pipeline information.

    This is the single entry-point for constructing format state in the
    design pipeline — ensures consistent defaults.
    """
    # Determine design_format from user input
    user_fmt = (user_requested_format or "").strip().lower()
    if any(kw in user_fmt for kw in ["vhh", "纳米抗体", "纳米抗体", "nanobody",
                                        "single-domain", "single domain",
                                        "camelid", "llama", "alpaca"]):
        design_format = DesignFormat.VHH
    elif any(kw in user_fmt for kw in ["igg", "完整抗体", "full antibody"]):
        design_format = DesignFormat.IGG
    elif any(kw in user_fmt for kw in ["fab"]):
        design_format = DesignFormat.FAB
    elif any(kw in user_fmt for kw in ["scfv", "单链抗体"]):
        design_format = DesignFormat.SCFV
    elif has_real_vh and has_real_vl:
        design_format = DesignFormat.VH_EXPLORATORY
    else:
        design_format = DesignFormat.UNSPECIFIED

    return AntibodyFormatState(
        design_format=design_format,
        user_requested_format=user_requested_format,
        default_scaffold_type=ScaffoldType.HUMAN_VH,
        has_real_vh=has_real_vh,
        has_real_vl=has_real_vl,
        vhh_motifs_detected=True,   # default scaffold always has them
        hdock_ran=hdock_ran,
        hdock_independent_available=hdock_independent_available,
        contact_analysis_ran=contact_analysis_ran,
        artifacts_verified=artifacts_verified or {},
    )
