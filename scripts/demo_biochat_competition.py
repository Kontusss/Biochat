#!/usr/bin/env python3
"""Biochat competition demo — offline quick mode.

Demonstrates the Biochat runtime layers without an LLM call or the ~11GB
data lake:

1. Knowledge registry (bundled know-how documents + license policy)
2. Environment catalog (data-lake / library descriptors, commercial filter)
3. Tool catalog (dynamic tool-description registry)
4. P0 sanitizer + streaming answer card rendering
5. XunZi response-format quality evaluation

Usage:
    python scripts/demo_biochat_competition.py --quick

Non-quick mode (full agent) intentionally requires an LLM + data lake and
is not part of this script.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Competition demo runs the minimal tool profile by default.
os.environ.setdefault("BIOCHAT_TOOL_PROFILE", "minimal")


def demo_quick() -> int:
    print("🧬 Biochat competition demo (quick, offline)\n" + "=" * 56)

    # 1. Knowledge registry
    from biochat.knowledge import KnowledgeRegistry

    registry = KnowledgeRegistry()
    docs = registry.get_document_summaries()
    print(f"✅ Knowledge registry: {len(docs)} know-how documents loaded")
    for d in docs:
        print(f"   - {d['id']}: {d['name']}")
    excluded = registry.exclude_non_commercial()
    print(f"   license policy: {len(excluded)} non-commercial excluded")

    # 2. Environment catalog
    from biochat.environment import EnvironmentCatalog

    catalog = EnvironmentCatalog()
    print(f"✅ Environment catalog: {len(catalog.data_lake)} datasets, "
          f"{len(catalog.libraries)} libraries")
    nc = sum(1 for e in catalog.data_lake + catalog.libraries
             if not e.commercial_allowed)
    print(f"   commercial view drops {nc} non-commercial resources")

    # 3. Tool catalog — active profile (minimal by default for the demo)
    from biochat.core.settings import biochat_settings
    from biochat.tool.registry import ToolRegistry
    from biochat.utils.io_utils import load_all_tool_descriptions

    full = load_all_tool_descriptions(profile="full")
    minimal = load_all_tool_descriptions(profile="minimal")
    assert set(minimal) < set(full), "minimal profile must be a subset of full"
    profile = biochat_settings.tool_profile
    active = load_all_tool_descriptions(profile=profile)
    registry = ToolRegistry(active, profile=profile)
    n_full = sum(len(v) for v in full.values())
    n_min = sum(len(v) for v in minimal.values())
    print(f"✅ Tool catalog: full={n_full} tools ({len(full)} modules), "
          f"minimal={n_min} tools ({len(minimal)} modules)")
    print(f"   active profile: {profile} "
          f"(registry holds {len(registry.tools)} tools)")

    # 4. P0 sanitizer + streaming card
    from biochat.ui.biochat_streamlit import render_assistant_card_streaming
    from biochat.ui.sanitize import sanitize_visible_text

    raw = ("<thinking>internal reasoning must never leak</thinking>\n"
           "结论：EGFR 是受体酪氨酸激酶。")
    visible = sanitize_visible_text(raw)
    assert "internal reasoning" not in visible
    card = render_assistant_card_streaming(
        answer_html="EGFR 是受体酪氨酸激酶", trace_lines=[],
        status="answering", current_step="✍️ 正在生成回答...",
    )
    assert "bc-stream-cursor" in card
    print("✅ Sanitizer + streaming card: reasoning blocked, cursor renders")

    # 5. XunZi response-format evaluation
    from biochat.eval import evaluate_response_quality

    sample = (
        "## 结论\nEGFR 参与肿瘤生长。\n\n"
        "## 依据与原理\n文献表明……\n\n"
        "## 方法与依据摘要\n检索了 UniProt 与 PubMed。\n\n"
        "## 建议验证实验\n1. 敲低实验验证表型。\n\n"
        "## 不确定性与局限性\n基于公开数据。\n\n"
        "## 安全声明\n仅供研究参考。"
    )
    score = evaluate_response_quality(sample, task_type="general")
    missing = score.get("missing_sections", [])
    assert not missing, f"sample response missing sections: {missing}"
    print(f"✅ Response-quality eval: structure_score={score.get('structure_score')}")

    print("=" * 56)
    print("Demo passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Biochat competition demo.")
    parser.add_argument("--quick", action="store_true",
                        help="offline quick demo (no LLM, no data lake)")
    args = parser.parse_args()
    if not args.quick:
        parser.error("only --quick mode is available; run with --quick")
    return demo_quick()


if __name__ == "__main__":
    raise SystemExit(main())
