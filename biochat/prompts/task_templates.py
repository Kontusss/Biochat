"""
Task-specific prompt templates — inspired by XunZi's structured query design.

Each template defines how the LLM should frame a task-specific query,
which output sections are required, which tools are recommended, and
which safety notes apply.  The templates are injected into the system
prompt by ``SystemPromptBuilder`` when a ``task_type`` is specified.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskTemplate:
    """A structured task template for a specific biomedical task type."""

    task_type: str
    user_prompt_template: str
    required_sections: tuple[str, ...]
    recommended_tools: tuple[str, ...]
    safety_notes: tuple[str, ...]


# ═══════════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════════

TASK_TEMPLATES: dict[str, TaskTemplate] = {
    # ── General assistant ─────────────────────────────────────────
    "general": TaskTemplate(
        task_type="general",
        user_prompt_template="{query}",
        required_sections=(
            "结论", "依据与原理", "分析步骤",
            "建议验证实验", "不确定性与局限", "安全声明",
        ),
        recommended_tools=(),
        safety_notes=(
            "回答仅供研究参考，不构成临床建议。",
        ),
    ),

    # ── Target discovery (XunZi-style) ──────────────────────────
    "target_discovery": TaskTemplate(
        task_type="target_discovery",
        user_prompt_template=(
            "Query: Is gene {gene} involved in {disease} in a functional way? "
            "If yes, summarize the most plausible mechanism (pathways/regulators) "
            "and propose 2-3 validation experiments."
        ),
        required_sections=(
            "结论", "机制依据", "分析步骤",
            "建议验证实验", "不确定性与局限", "安全声明",
        ),
        recommended_tools=(
            "query_uniprot", "query_opentarget", "search_pubmed",
            "analyze_gene_set_enrichment",
        ),
        safety_notes=(
            "靶点关联基于计算与文献分析，未经过实验验证。",
            "建议验证实验仅为研究设计建议，不代表已经完成实验验证。",
        ),
    ),

    # ── Antibody design ─────────────────────────────────────────
    "antibody_design": TaskTemplate(
        task_type="antibody_design",
        user_prompt_template=(
            "Query: Design VH-only antibody CDRH3 candidates targeting epitope {epitope}. "
            "Use the design_vh_only_antibodies() tool for computational design. "
            "Report candidates with provenance-tracked scores, then propose "
            "2-3 experimental validation steps."
        ),
        required_sections=(
            "结论", "依据与原理", "分析步骤",
            "建议验证实验", "不确定性与局限", "安全声明",
        ),
        recommended_tools=(
            "design_vh_only_antibodies", "score_and_rank_candidates",
            "build_vh_structures", "prepare_docking_inputs",
        ),
        safety_notes=(
            "候选序列为计算设计产物，未经湿实验验证。",
            "所有评分均为计算方法估算值，不代表实验结合亲和力。",
            "对接输出仅用于结构合理性参考，不构成候选有效性证明。",
        ),
    ),

    # ── Literature review ───────────────────────────────────────
    "literature_review": TaskTemplate(
        task_type="literature_review",
        user_prompt_template=(
            "Query: Summarize current evidence on {topic}. "
            "Cover key findings, open questions, and propose "
            "2-3 validation experiments for unresolved hypotheses."
        ),
        required_sections=(
            "结论", "文献依据", "分析步骤",
            "建议验证实验", "不确定性与局限", "安全声明",
        ),
        recommended_tools=("search_pubmed", "query_biorxiv", "query_uniprot"),
        safety_notes=(
            "文献总结基于检索结果，可能存在检索偏倚。",
        ),
    ),
}


def get_task_template(task_type: str) -> TaskTemplate | None:
    """Return the template for *task_type*, or None if not registered."""
    return TASK_TEMPLATES.get(task_type)
