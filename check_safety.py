#!/usr/bin/env python3
"""Biochat safety checks (lightweight, offline).

Verifies the guardrails that protect Biochat's runtime output:

1. The P0 sanitizer (``biomni/ui/sanitize.py``) strips internal reasoning
   blocks, XML tags, and self-talk from UI-visible text.
2. The system prompt carries the output-format requirements (six-section
   XunZi format) and the anti-fabrication requirements (no invented
   binding-affinity / ΔG / Kd claims).
3. Provenance documentation exists (upstream attribution, license).

Exit code 0 = all checks passed.  Usage: ``python check_safety.py``
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

FAILURES: list[str] = []


def check(condition: bool, label: str) -> None:
    status = "✅" if condition else "❌"
    print(f"{status} {label}")
    if not condition:
        FAILURES.append(label)


# ═══════════════════════════════════════════════════════════════════
# 1. P0 sanitizer behavior
# ═══════════════════════════════════════════════════════════════════

def check_sanitizer() -> None:
    from biomni.ui.sanitize import FALLBACK_MESSAGE, sanitize_visible_text

    cleaned = sanitize_visible_text(
        "前置内容\n<thinking>隐藏的推理过程</thinking>\n"
        "我需要重新生成回复。\n正常回答 <solution>结果</solution>"
    )
    check("隐藏的推理过程" not in cleaned, "sanitizer strips <thinking> blocks")
    check("<solution>" not in cleaned and "</solution>" not in cleaned,
          "sanitizer strips XML tags")
    check("重新生成回复" not in cleaned, "sanitizer strips self-talk lines")
    check("正常回答" in cleaned, "sanitizer keeps user-facing content")
    check(bool(FALLBACK_MESSAGE.strip()), "fallback message present")


# ═══════════════════════════════════════════════════════════════════
# 2. System-prompt guardrails
# ═══════════════════════════════════════════════════════════════════

def check_system_prompt() -> None:
    from biomni.prompts.system_prompt_v2 import SystemPromptBuilder

    builder = SystemPromptBuilder(
        tool_desc={}, data_lake_content=[], library_content_list=[],
        data_lake_path="/dev/null", data_lake_dict={},
        library_content_dict={},
    )
    prompt = builder.build(task_type="general")

    for section in ("结论", "依据与原理", "建议验证实验", "不确定性与局限", "安全声明"):
        check(section in prompt, f"system prompt requires section: {section}")
    for ban in ("禁止输出隐藏思考过程", "<thinking>", "chain-of-thought"):
        check(ban in prompt, f"system prompt prohibits: {ban!r}")

    antibody_prompt = builder.build(task_type="antibody_design")
    for ban in ("binding affinity", "ΔG", "Kd", "ddG"):
        check(f"NEVER call any computed score" in antibody_prompt
              or ban in antibody_prompt,
              f"antibody prompt guards score claims: {ban!r}")


# ═══════════════════════════════════════════════════════════════════
# 3. Provenance / license files
# ═══════════════════════════════════════════════════════════════════

def check_provenance() -> None:
    for rel in (
        "LICENSE",
        "THIRD_PARTY_PROVENANCE.md",
        "BIOCHAT_ORIGINAL_CONTRIBUTIONS.md",
        "third_party/biomni_upstream_archive/README.md",
        "third_party/biomni_upstream_reference/LICENSE",
        "reports/upstream_usage_audit.csv",
        "reports/similarity_reduction_candidates.csv",
    ):
        check((ROOT / rel).exists(), f"provenance file exists: {rel}")


def main() -> int:
    print("Biochat safety checks\n" + "=" * 40)
    check_sanitizer()
    check_system_prompt()
    check_provenance()
    print("=" * 40)
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s)")
        return 1
    print("All safety checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
