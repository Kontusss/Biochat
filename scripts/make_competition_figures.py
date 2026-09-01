#!/usr/bin/env python3
"""Generate competition-grade figures from the Biochat benchmark evidence."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.image import imread

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
GREEN = "#0f7d57"
SURFACE = "#fcfcfb"
INK, INK_2, INK_MUTED = "#0b0b0b", "#52514e", "#8a8880"
GRID = "#e4e3df"
FIG_DIR = "figs"
DPI = 160
NL = "\n"


def _use_cjk_font() -> None:
    available = {f.name for f in fm.fontManager.ttflist}
    for candidate in ("Hiragino Sans GB", "PingFang SC", "Heiti SC", "STHeiti", "Arial Unicode MS", "Songti SC"):
        if candidate in available:
            plt.rcParams["font.sans-serif"] = [candidate]
            break
    plt.rcParams["axes.unicode_minus"] = False


def style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
        ax.spines[side].set_linewidth(1.0)
    ax.tick_params(colors=INK_MUTED, labelsize=9, length=3)


def fig_pipeline() -> None:
    steps = [
        ("① 表位输入", "靶点序列" + NL + "(如 HER2 ECD)"),
        ("② CDRH3 扩散生成", "DiffCDRH3" + NL + "Transformer-VAE + 条件扩散"),
        ("③ 结构预测", "NanoBodyBuilder2" + NL + "VH 结构合理性校验"),
        ("④ 分子对接", "HDOCK" + NL + "接触面分析"),
        ("⑤ 可开发性评估", "聚集 / 糖基化 / 电荷" + NL + "责任基序硬闸门"),
        ("⑥ 多维排序", "候选打分排序" + NL + "全流程审计日志"),
    ]
    n = len(steps)
    fig, ax = plt.subplots(figsize=(13.8, 3.6), facecolor=SURFACE)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 34)
    ax.axis("off")

    box_w, box_h, gap = 15.0, 22.0, 2.0
    start_x = 1.0
    colors = [BLUE, "#1b7fae", GREEN, ORANGE, "#6d4fa1", "#b5453a"]
    for i, (title, desc) in enumerate(steps):
        x0 = start_x + i * (box_w + gap)
        y0 = 8.0
        color = colors[i]
        box = FancyBboxPatch((x0, y0), box_w, box_h,
                             boxstyle="round,pad=0.35,rounding_size=1.4",
                             facecolor=color, edgecolor="none", zorder=3)
        ax.add_patch(box)
        ax.text(x0 + box_w / 2, y0 + box_h - 4.2, title, ha="center", va="center",
                fontsize=11.5, fontweight="bold", color="white", zorder=4)
        for ln, line in enumerate(desc.split(NL)):
            ax.text(x0 + box_w / 2, y0 + box_h - 9.4 - ln * 4.6, line, ha="center", va="center",
                    fontsize=8.2, color="white", alpha=0.96, zorder=4)
        if i < n - 1:
            ax.add_patch(FancyArrowPatch(
                (x0 + box_w + 0.2, y0 + box_h / 2), (x0 + box_w + gap - 0.2, y0 + box_h / 2),
                arrowstyle="-|>", mutation_scale=22, color=INK_MUTED, lw=1.8, zorder=2))

    ax.text(50, 30.6, "自研抗体从头设计管线  ·  8,400+ 行代码", ha="center",
            fontsize=15, fontweight="bold", color=INK)
    ax.text(50, 2.2, "每阶段输出经审计日志记录 · 端到端可复现 · 以 26 个获批治疗性抗体回顾性验证",
            ha="center", fontsize=9.5, color=INK_2)
    fig.tight_layout()
    fig.savefig(FIG_DIR + "/pipeline_flow.png", dpi=DPI, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    print("OK pipeline_flow.png")


def fig_before_after() -> None:
    metrics = [
        ("判别力 AUC" + NL + "(真药 vs 随机序列)", 0.212, 0.734, "越高越好"),
        ("获批药物通过率" + NL + "(26 个金标准抗体)", 96.2, 100.0, "越高越好"),
        ("闸门冲突" + NL + "(过滤器 vs 打分器)", 36.0, 0.0, "越低越好"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2), facecolor=SURFACE)
    for ax, (label, before, after, note) in zip(axes, metrics):
        style(ax)
        lo, hi = min(before, after), max(before, after)
        pad = max((hi - lo) * 0.35, hi * 0.06)
        ax.set_xlim(lo - pad, hi + pad)
        ax.set_ylim(-0.9, 0.9)
        ax.axis("off")
        ax.plot([before, after], [0, 0], color=GRID, lw=10, solid_capstyle="round", zorder=1)
        ax.scatter([before], [0], s=340, color="#b9c6d8", edgecolor=INK_2, linewidth=1.6, zorder=3)
        ax.annotate(f"{before:g}", xy=(before, 0.12), ha="center", fontsize=15,
                    fontweight="bold", color=INK_2, zorder=4)
        ax.annotate("修复前", xy=(before, -0.52), ha="center", fontsize=9.5, color=INK_2, zorder=4)
        ax.scatter([after], [0], s=430, color=BLUE, edgecolor="white", linewidth=1.8, zorder=3)
        ax.annotate(f"{after:g}", xy=(after, 0.12), ha="center", fontsize=17,
                    fontweight="bold", color=BLUE, zorder=4)
        ax.annotate("修复后", xy=(after, -0.52), ha="center", fontsize=9.5, color=BLUE, zorder=4)
        improved = (after > before) if "越高" in note else (after < before)
        ax.annotate("▲ 改善" if improved else "▼ 恶化", xy=((before + after) / 2, 0.42),
                    ha="center", fontsize=9.5, fontweight="bold",
                    color=GREEN if improved else "#b5453a", zorder=4)
        ax.set_title(label, fontsize=11.5, color=INK, pad=16)
        ax.text(0.5, -0.86, note, transform=ax.transAxes, ha="center", fontsize=9, color=INK_MUTED)

    fig.suptitle("回顾性基准暴露的缺陷 — 修复前后对比(以已获批治疗性抗体为金标准)",
                 fontsize=14.5, fontweight="bold", color=INK, y=1.0)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(FIG_DIR + "/benchmark_before_after.png", dpi=DPI, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    print("OK benchmark_before_after.png")


def fig_cdrh3() -> None:
    fig, ax = plt.subplots(figsize=(8.2, 4.8), facecolor=SURFACE)
    style(ax)
    names = ["生产打分器" + NL + "(组成型)", "CDRH3 位置敏感" + NL + "二肽模型"]
    values = [0.5, 0.8844]
    errs = [0.0, 0.0246]
    colors = ["#b9c6d8", BLUE]

    bars = ax.bar(names, values, yerr=errs, width=0.52, color=colors, edgecolor="none", zorder=3,
                  error_kw=dict(ecolor=INK_2, lw=1.6, capsize=6))
    for bar, v in zip(bars, values):
        ax.annotate(f"{v:.2f}", xy=(bar.get_x() + bar.get_width() / 2, v + 0.035),
                    ha="center", fontsize=14, fontweight="bold", color=INK, zorder=4)
    ax.axhline(0.5, color=GRID, lw=1.4, ls=(0, (4, 4)), zorder=1)
    ax.annotate("随机水平 AUC = 0.5", xy=(1.42, 0.5), fontsize=9, color=INK_MUTED, va="center")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("AUC(真药 vs 组分打乱序列)", fontsize=10, color=INK_2)
    ax.set_title("CDRH3 位置敏感二肽模型:解决组成型打分无分辨率瓶颈",
                 fontsize=13, color=INK, pad=14, loc="left", fontweight="bold")
    ax.text(0.015, 0.04,
            "40 个随机种子平均 0.884 ± 0.025 (min 0.839, max 0.922)" + NL +
            "训练 1,296 条 PDB 抗体重链 · 测试 26 个获批抗体全程留出 · 打分=相邻残基点互信息均值",
            transform=ax.transAxes, fontsize=8.5, color=INK_2, va="bottom",
            bbox={"boxstyle": "round,pad=0.5", "facecolor": SURFACE, "edgecolor": GRID, "linewidth": 0.8})
    fig.tight_layout()
    fig.savefig(FIG_DIR + "/cdrh3_model_auc.png", dpi=DPI, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    print("OK cdrh3_model_auc.png")


def fig_engineering() -> None:
    fig, ax = plt.subplots(figsize=(11.5, 4.6), facecolor=SURFACE)
    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)

    cards = [
        ("149", "通过 / 1 跳过", "pytest 全量测试", BLUE),
        ("63 MB", "模型权重", "git 可复现 (.pth)", AQUA),
        ("226", "生物医学工具", "23 个子领域模块", GREEN),
        ("76 + 113", "数据集 / 软件库", "数据湖 (~11GB)", ORANGE),
        ("8,400+", "自研管线代码行", "抗体设计全流程", "#6d4fa1"),
        ("8 大", "LLM 供应商", "Anthropic/OpenAI/Gemini…", "#b5453a"),
    ]
    cols, rows = 3, 2
    cw, ch, gx, gy = 30.0, 38.0, 2.5, 4.0
    for idx, (num, label, sub, color) in enumerate(cards):
        r, c = divmod(idx, cols)
        x0 = 2.0 + c * (cw + gx)
        y0 = 100 - (r + 1) * (ch + gy) + 4
        box = FancyBboxPatch((x0, y0), cw, ch, boxstyle="round,pad=0.3,rounding_size=1.2",
                             facecolor=SURFACE, edgecolor=GRID, linewidth=1.2, zorder=2)
        ax.add_patch(box)
        ax.plot([x0 + 3, x0 + cw - 3], [y0 + ch - 6.5, y0 + ch - 6.5], color=color, lw=3, zorder=3)
        ax.text(x0 + cw / 2, y0 + ch - 16, num, ha="center", fontsize=23, fontweight="bold", color=color, zorder=4)
        ax.text(x0 + cw / 2, y0 + ch - 24.5, label, ha="center", fontsize=10.5, color=INK, zorder=4)
        ax.text(x0 + cw / 2, y0 + 5.5, sub, ha="center", fontsize=8.5, color=INK_MUTED, zorder=4)

    ax.text(50, 96.5, "工程完成度总览", ha="center", fontsize=15, fontweight="bold", color=INK)
    ax.text(50, 3.2, "离线比赛演示脚本通过 · HER2 抗体实际设计结果 · 3 类审计脚本 · 完整文档",
            ha="center", fontsize=9, color=INK_2)
    fig.tight_layout()
    fig.savefig(FIG_DIR + "/engineering_overview.png", dpi=DPI, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    print("OK engineering_overview.png")


def fig_summary() -> None:
    files = ["pipeline_flow.png", "benchmark_before_after.png", "cdrh3_model_auc.png", "engineering_overview.png"]
    titles = ["(a) 自研抗体设计管线", "(b) 回顾性基准:缺陷修复前后", "(c) CDRH3 位置敏感模型", "(d) 工程完成度"]
    fig, axes = plt.subplots(2, 2, figsize=(15, 9.5), facecolor=SURFACE)
    for ax, f, t in zip(axes.flat, files, titles):
        img = imread(FIG_DIR + "/" + f)
        ax.imshow(img)
        ax.axis("off")
        ax.set_title(t, fontsize=12.5, color=INK, loc="left", pad=8, fontweight="bold")
    fig.suptitle("Biochat 抗体设计系统 — 数据图汇总", fontsize=17, fontweight="bold", color=INK, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(FIG_DIR + "/summary_2x2.png", dpi=150, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    print("OK summary_2x2.png")


if __name__ == "__main__":
    _use_cjk_font()
    fig_pipeline()
    fig_before_after()
    fig_cdrh3()
    fig_engineering()
    fig_summary()
    print("ALL DONE")
