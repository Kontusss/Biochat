"""Lightweight structural response quality evaluation.

Checks whether an LLM response contains the six required sections
defined by the XunZi-inspired output format.  No heavy dependencies
(BLEU/ROUGE/BERTScore are intentionally NOT imported — see docstring
for optional future extension).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

# ── Section markers (Chinese + English variants) ────────────────
_SECTION_PATTERNS: Dict[str, List[str]] = {
    "conclusion": [
        r"结论", r"Conclusion", r"\*\*结论\*\*",
    ],
    "evidence": [
        r"依据与原理", r"Evidence", r"机制依据", r"文献依据",
    ],
    "analysis_steps": [
        r"方法与依据摘要", r"分析步骤", r"Analysis Steps",
        r"Methods & Rationale Summary",
    ],
    "suggested_experiments": [
        r"建议验证实验", r"Suggested Validation Experiments",
        r"验证实验", r"Validation Experiments",
    ],
    "uncertainty": [
        r"不确定性", r"Uncertaint", r"局限", r"Limitations",
    ],
    "safety_statement": [
        r"安全声明", r"Safety Disclaimer",
    ],
}


def evaluate_response_quality(
    text: str,
    task_type: str = "general",
) -> Dict[str, Any]:
    """Evaluate the structural quality of an LLM response.

    Args:
        text: The response text to evaluate.
        task_type: Task type label (currently informational only).

    Returns:
        Dict with per-section booleans, experiment count estimate,
        structure score, and missing sections list.

    Note:
        This is a *structural* check only — it verifies that the
        response follows the required format.  It does NOT measure
        factual accuracy or scientific validity.

    Optional future extension (NOT imported by default):
        - BLEU/ROUGE: n-gram overlap against reference explanations
          (pip install rouge-score nltk)
        - BERTScore: semantic similarity via SciBERT embeddings
          (pip install bert-score)
    """
    if not text or not text.strip():
        return {
            "has_conclusion": False,
            "has_evidence": False,
            "has_analysis_steps": False,
            "has_suggested_experiments": False,
            "suggested_experiment_count_estimate": 0,
            "has_uncertainty": False,
            "has_safety_statement": False,
            "structure_score": 0.0,
            "missing_sections": list(_SECTION_PATTERNS.keys()),
        }

    results: Dict[str, bool] = {}
    for key, patterns in _SECTION_PATTERNS.items():
        results[key] = any(
            re.search(pattern, text, re.IGNORECASE) for pattern in patterns
        )

    # Count suggested experiments (heuristic: count "实验目的" occurrences)
    experiment_count = len(re.findall(r"实验目的", text))
    # If section present but no explicit purpose markers, estimate from format lines
    if results["suggested_experiments"] and experiment_count == 0:
        experiment_count = min(
            len(re.findall(r"^\s*[-•]\s", text, re.MULTILINE)) // 5,
            3,
        )

    missing = [key for key, ok in results.items() if not ok]
    score = (len(_SECTION_PATTERNS) - len(missing)) / len(_SECTION_PATTERNS)

    return {
        "has_conclusion": results["conclusion"],
        "has_evidence": results["evidence"],
        "has_analysis_steps": results["analysis_steps"],
        "has_suggested_experiments": results["suggested_experiments"],
        "suggested_experiment_count_estimate": experiment_count,
        "has_uncertainty": results["uncertainty"],
        "has_safety_statement": results["safety_statement"],
        "structure_score": round(score, 2),
        "missing_sections": missing,
    }
