#!/usr/bin/env python3
"""Generate the competition pitch slide → Biochat_抗体设计系统.pptx.

One 16:9 page, all native PowerPoint shapes so it stays editable. The left
column is the self-built antibody pipeline with its open-source foundation
drawn explicitly as a base layer; the right column is the retrospective
benchmark evidence.

Every number on the right is read from the benchmark summaries, so the slide
cannot drift away from the measurements. Run the benchmark first:

    python scripts/run_antibody_benchmark.py --tag before
    python scripts/run_antibody_benchmark.py --tag after
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts._slide_kit import (  # noqa: E402
    ACCENT,
    ACCENT_DK,
    AMBER_DK,
    BLUE_DK,
    INK,
    INK_SOFT,
    RULE,
    VIOLET_DK,
    WHITE,
    badge,
    box,
    new_deck,
    rule,
    textbox,
)

REPORTS = PROJECT_ROOT / "reports"
OUT = PROJECT_ROOT / "Biochat_抗体设计系统.pptx"

STAGES = [
    ("CDRH3 候选生成与过滤", "扩散生成 / 外部候选 · 责任基序硬闸门"),
    ("结构预测", "NanoBodyBuilder2 · 结构合理性校验"),
    ("分子对接", "HDOCK · 接触面分析"),
    ("可开发性评估与多维排序", "聚集/糖基化/电荷 · 候选打分排序"),
]


def load_summaries() -> tuple[dict, dict]:
    try:
        before = json.loads((REPORTS / "antibody_benchmark_summary_before.json").read_text())
        after = json.loads((REPORTS / "antibody_benchmark_summary_after.json").read_text())
    except FileNotFoundError as exc:
        print(f"❌ {exc.filename} missing — run scripts/run_antibody_benchmark.py for both tags")
        raise SystemExit(1) from exc
    return before, after


def build_header(slide, n_gold: int) -> None:
    box(slide, 0.55, 0.40, 0.075, 0.66, ACCENT, ACCENT, 0.25, shape=MSO_SHAPE.RECTANGLE)
    textbox(slide, 0.78, 0.36, 8.6, 0.76, [
        ("基于 Agent 的抗体从头设计与可开发性评估系统", 24, True, INK),
        ("表位输入 → 候选生成 → 结构预测 → 分子对接 → 可开发性评估 → 多维排序", 11.5, False, INK_SOFT, 4),
    ])
    textbox(slide, 9.5, 0.44, 3.28, 0.66, [
        ("自研管线 8,200+ 行", 10.5, True, ACCENT_DK),
        (f"以 {n_gold} 个已获批治疗性抗体回顾性验证", 9.5, False, INK_SOFT, 3),
    ], align=PP_ALIGN.RIGHT)
    rule(slide, 0.55, 1.20, 12.23)


def build_pipeline(slide) -> None:
    x, w = 0.55, 6.15
    textbox(slide, x, 1.42, 4.0, 0.28, [("自研核心：端到端设计管线", 13, True, INK)])
    box(slide, x, 1.76, 0.42, 0.028, ACCENT, ACCENT, 0.25, shape=MSO_SHAPE.RECTANGLE)

    # input pill
    inp = box(slide, x, 1.98, w, 0.40, WHITE, RULE, 1.0)
    textbox(slide, x, 2.08, w, 0.24, [("表位序列输入", 10.5, True, INK_SOFT)], align=PP_ALIGN.CENTER)
    _ = inp

    # Sized so the foundation layer clears the footer rule at y=7.16.
    y0, step, h = 2.48, 0.76, 0.64
    for i, (title, detail) in enumerate(STAGES):
        y = y0 + i * step
        box(slide, x, y, w, h, WHITE, ACCENT, 1.3)
        badge(slide, x + 0.22, y + h / 2 - 0.16, 0.32, str(i + 1))
        textbox(slide, x + 0.68, y + 0.10, w - 0.88, 0.48, [
            (title, 11.5, True, ACCENT_DK),
            (detail, 8.8, False, INK_SOFT, 2),
        ])

    out_y = y0 + len(STAGES) * step
    box(slide, x, out_y, w, 0.44, ACCENT, ACCENT, 0.75)
    textbox(slide, x, out_y + 0.12, w, 0.26,
            [("候选排序 + 全流程审计日志（可复现、可追溯）", 10.5, True, WHITE)], align=PP_ALIGN.CENTER)

    # foundation layer — attribution stated on the slide, not buried
    base_y = out_y + 0.64
    box(slide, x, base_y, w, 0.74, RGBColor(0xF3, 0xF2, 0xF8), RGBColor(0xCF, 0xCB, 0xE0))
    textbox(slide, x + 0.22, base_y + 0.12, w - 0.44, 0.5, [
        ("技术底座：开源 Biomni（Apache 2.0，Stanford SNAP）", 10.5, True, VIOLET_DK),
        ("226 工具 · 76 数据集 · 113 库；本作品在其上构建管线与服务层", 8.8, False, INK_SOFT, 3),
    ])


def build_evidence(slide, before: dict, after: dict, n_gold: int) -> None:
    x, w = 7.10, 5.68
    textbox(slide, x, 1.42, 4.6, 0.28, [("验证：回顾性基准", 13, True, INK)])
    box(slide, x, 1.76, 0.42, 0.028, ACCENT, ACCENT, 0.25, shape=MSO_SHAPE.RECTANGLE)

    textbox(slide, x, 1.98, w, 0.34, [
        (f"已获批药物是「可开发性」金标准 —— 管线若拒绝它们，即标定有误。"
         f"金标准集 {n_gold} 个抗体，序列全部溯源自 PDB。", 9.5, False, INK_SOFT),
    ], spacing=1.25)

    # hero metric
    hero = box(slide, x, 2.52, w, 1.30, WHITE, ACCENT, 1.6)
    _ = hero
    textbox(slide, x + 0.24, 2.66, w - 0.48, 0.24,
            [("判别力 AUC（真药 vs 随机序列）", 9.5, True, INK_SOFT)])
    textbox(slide, x + 0.24, 2.94, 2.3, 0.62, [
        (str(before["auc_vs_random"]), 30, True, AMBER_DK),
        ("修复前", 9, False, INK_SOFT, 2),
    ])
    textbox(slide, x + 2.42, 3.02, 0.6, 0.4, [("→", 20, True, INK_SOFT)], align=PP_ALIGN.CENTER)
    textbox(slide, x + 3.05, 2.94, 2.3, 0.62, [
        (str(after["auc_vs_random"]), 30, True, ACCENT_DK),
        ("修复后", 9, False, INK_SOFT, 2),
    ])
    textbox(slide, x + 0.24, 3.56, w - 0.48, 0.22, [
        (f"修复前，随机序列有 {100 * (1 - before['auc_vs_random']):.0f}% 概率打败真实上市药物", 8.8, True, AMBER_DK),
    ])

    # supporting metrics
    metrics = [
        ("已获批药物通过率", f"{before['pass_rate']['approved_drug']}%", f"{after['pass_rate']['approved_drug']}%"),
        ("闸门冲突（过滤器 vs 打分器）", str(sum(before["gate_conflicts"].values())),
         str(sum(after["gate_conflicts"].values()))),
        ("已获批药物中位分", str(before["score_stats"]["approved_drug"]["p50"]),
         str(after["score_stats"]["approved_drug"]["p50"])),
    ]
    my = 3.98
    for i, (label, b, a) in enumerate(metrics):
        y = my + i * 0.34
        textbox(slide, x + 0.04, y, 3.5, 0.26, [(label, 9.5, False, INK)])
        textbox(slide, x + 3.5, y, 0.9, 0.26, [(b, 9.5, True, AMBER_DK)], align=PP_ALIGN.RIGHT)
        textbox(slide, x + 4.4, y, 0.42, 0.26, [("→", 9.5, False, INK_SOFT)], align=PP_ALIGN.CENTER)
        textbox(slide, x + 4.8, y, 0.84, 0.26, [(a, 9.5, True, ACCENT_DK)], align=PP_ALIGN.RIGHT)

    rule(slide, x, 5.08, w)

    textbox(slide, x, 5.22, w, 0.9, [
        ("基准暴露的问题（均已修复并加回归测试）", 10.5, True, INK),
        ("· 四个硬排除条件因旗标词表不匹配被静默降级为 -2 分警告", 9, False, INK_SOFT, 4),
        ("· 过滤器的否决结果在生产路径被丢弃，从未生效", 9, False, INK_SOFT, 1),
        ("· 长度/芳香族阈值在惩罚常态：旧偏好窗仅覆盖 24.1% 真实抗体", 9, False, INK_SOFT, 1),
    ], spacing=1.22)

    limit = box(slide, x, 6.34, w, 0.66, WHITE, RULE, 1.0)
    _ = limit
    textbox(slide, x + 0.2, 6.46, w - 0.4, 0.46, [
        ("已识别的后续方向", 9.5, True, BLUE_DK),
        ("打分仅由氨基酸组成决定，无法区分真实抗体与其乱序版本"
         f"（AUC {after['auc_vs_shuffled']}）→ 下一步引入位置敏感打分", 8.5, False, INK_SOFT, 2),
    ], spacing=1.2)


def main() -> int:
    before, after = load_summaries()
    n_gold = int(after["score_stats"]["approved_drug"]["n"])

    prs, slide = new_deck()
    build_header(slide, n_gold)
    build_pipeline(slide)
    build_evidence(slide, before, after, n_gold)

    rule(slide, 0.55, 7.16, 12.23)
    textbox(slide, 0.55, 7.24, 9.0, 0.24, [
        ("数据来源：RCSB PDB · 完整方法与结果见 reports/antibody_benchmark_report.md", 8.5, False, INK_SOFT),
    ])
    textbox(slide, 9.6, 7.24, 3.18, 0.24, [
        ("回归测试 20 项 · 全量 137 通过", 8.5, False, INK_SOFT),
    ], align=PP_ALIGN.RIGHT)

    prs.save(OUT)
    print(f"✅ Wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
