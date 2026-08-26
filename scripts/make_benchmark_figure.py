#!/usr/bin/env python3
"""Render the benchmark before/after figure → reports/antibody_benchmark.png.

Two panels tell the whole story:

* **left** — score distributions per cohort, before vs after the fixes.  The
  headline is the reversal: uniformly random sequences used to out-score
  approved drugs.
* **right** — the real CDR-H3 length distribution with the old and new
  preferred windows drawn on it, which is the evidence behind the recalibration.

Requires the summaries written by ``scripts/run_antibody_benchmark.py``.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from biochat.tool.antibody_design.generation_filter import (  # noqa: E402
    PREFERRED_MAX_LEN,
    PREFERRED_MIN_LEN,
)

REPORTS = PROJECT_ROOT / "reports"
OUT_PNG = REPORTS / "antibody_benchmark.png"

# Validated categorical slots 1-3 (light surface) — see the dataviz palette.
# `node scripts/validate_palette.js "#2a78d6,#eb6834,#1baf7a" --mode light --pairs all`
# passes every hard gate; the aqua slot carries a contrast WARN, discharged here
# by direct median labels on every cohort.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SURFACE = "#fcfcfb"
INK, INK_2, INK_MUTED = "#0b0b0b", "#52514e", "#8a8880"
GRID = "#e4e3df"

OLD_PREFERRED = (13, 16)  # the window this benchmark replaced

COHORTS = [
    ("approved_drug", "已获批药物", BLUE),
    ("decoy_shuffled", "组分打乱诱饵", ORANGE),
    ("decoy_random", "均匀随机诱饵", AQUA),
]


def _use_cjk_font() -> None:
    available = {f.name for f in fm.fontManager.ttflist}
    for candidate in ("Hiragino Sans GB", "PingFang SC", "Heiti SC", "STHeiti", "Arial Unicode MS", "Songti SC"):
        if candidate in available:
            plt.rcParams["font.sans-serif"] = [candidate]
            break
    plt.rcParams["axes.unicode_minus"] = False


def load(tag: str) -> tuple[dict, list[dict]]:
    summary = json.loads((REPORTS / f"antibody_benchmark_summary_{tag}.json").read_text())
    with (REPORTS / f"antibody_benchmark_results_{tag}.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return summary, rows


def scores_by_cohort(rows: list[dict], cohort: str) -> list[float]:
    return [float(r["score"]) for r in rows if r["cohort"] == cohort]


def panel_scores(ax, before_rows, after_rows, before, after) -> None:
    rng = np.random.default_rng(7)
    ax.set_title("修复前后的打分分布", fontsize=12, color=INK, pad=12, loc="left")

    for row, (key, label, color) in enumerate(COHORTS):
        for col, (rows, state) in enumerate(((before_rows, "前"), (after_rows, "后"))):
            values = scores_by_cohort(rows, key)
            if not values:
                continue
            y = row * 2.4 + col * 0.85
            jitter = rng.uniform(-0.16, 0.16, len(values))
            ax.scatter(
                values, y + jitter, s=26, color=color, alpha=0.5,
                linewidths=0.8, edgecolors=SURFACE, zorder=3,
            )
            median = float(np.median(values))
            ax.plot([median, median], [y - 0.34, y + 0.34], color=color, lw=2.2, zorder=4,
                    solid_capstyle="round")
            # Direct label: discharges the aqua slot's contrast WARN.
            ax.annotate(
                f"{state} · 中位 {median:.0f}", xy=(median, y + 0.46),
                fontsize=8.5, color=INK_2, ha="center", zorder=5,
            )

    ax.set_yticks([row * 2.4 + 0.42 for row in range(len(COHORTS))])
    ax.set_yticklabels([label for _, label, _ in COHORTS], fontsize=10, color=INK)
    ax.set_xlabel("aggregate_score", fontsize=9.5, color=INK_2)
    ax.set_xlim(-6, 106)
    ax.set_ylim(-0.9, len(COHORTS) * 2.4)
    ax.invert_yaxis()

    note = (
        f"真药 vs 随机诱饵 AUC：{before['auc_vs_random']} → {after['auc_vs_random']}\n"
        f"真药 vs 组分打乱 AUC：{before['auc_vs_shuffled']} → {after['auc_vs_shuffled']}（未改善）"
    )
    ax.annotate(
        note, xy=(0.015, 0.03), xycoords="axes fraction", fontsize=8.5, color=INK_2,
        va="bottom", ha="left",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": SURFACE, "edgecolor": GRID, "linewidth": 0.8},
    )


def panel_lengths(ax, lengths: list[int]) -> None:
    ax.set_title(f"真实抗体 CDR-H3 长度分布（n={len(lengths)}）", fontsize=12, color=INK, pad=12, loc="left")

    bins = np.arange(min(lengths) - 0.5, max(lengths) + 1.5, 1)
    counts, _, _ = ax.hist(
        lengths, bins=bins, color=BLUE, alpha=0.75, edgecolor=SURFACE, linewidth=0.8, zorder=3
    )

    # Reserve headroom above the bars and draw the two windows there as range
    # bars.  Overlaying them on the plot as shaded spans would both collide with
    # the tallest bar and blend into a third colour where 13-16 overlaps 8-16.
    peak = counts.max()
    ax.set_ylim(0, peak * 1.42)

    def coverage(lo: int, hi: int) -> float:
        return 100 * sum(1 for x in lengths if lo <= x <= hi) / len(lengths)

    windows = [
        (OLD_PREFERRED[0], OLD_PREFERRED[1], ORANGE, f"旧窗 {OLD_PREFERRED[0]}–{OLD_PREFERRED[1]}"),
        (PREFERRED_MIN_LEN, PREFERRED_MAX_LEN, "#0f7d57", f"新窗 {PREFERRED_MIN_LEN}–{PREFERRED_MAX_LEN}"),
    ]
    for i, (lo, hi, color, label) in enumerate(windows):
        y = peak * (1.30 - i * 0.145)
        ax.plot([lo, hi], [y, y], color=color, lw=5, solid_capstyle="round", zorder=4)
        for x in (lo, hi):
            ax.plot([x, x], [0, y], color=color, lw=0.9, ls=(0, (3, 3)), alpha=0.5, zorder=2)
        ax.annotate(
            f"{label} · 覆盖 {coverage(lo, hi):.1f}%",
            xy=(hi + 0.7, y), fontsize=9, color=color, va="center", ha="left", fontweight="bold",
        )

    ax.set_xlabel("CDR-H3 长度（氨基酸）", fontsize=9.5, color=INK_2)
    ax.set_ylabel("抗体数量", fontsize=9.5, color=INK_2)


def style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
        ax.spines[side].set_linewidth(1.0)
    ax.tick_params(colors=INK_MUTED, labelsize=9, length=3)
    ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=REPORTS / "antibody_benchmark_dataset.csv")
    args = parser.parse_args()

    for tag in ("before", "after"):
        path = REPORTS / f"antibody_benchmark_summary_{tag}.json"
        if not path.exists():
            print(f"❌ missing {path.name} — run: python scripts/run_antibody_benchmark.py --tag {tag}")
            return 1

    _use_cjk_font()
    before, before_rows = load("before")
    after, after_rows = load("after")

    with args.dataset.open(encoding="utf-8") as fh:
        lengths = [int(r["cdrh3_length"]) for r in csv.DictReader(fh)]

    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(13.5, 5.2), facecolor=SURFACE)
    for ax in (ax_left, ax_right):
        style(ax)

    panel_scores(ax_left, before_rows, after_rows, before, after)
    panel_lengths(ax_right, lengths)

    fig.suptitle(
        "抗体管线回顾性基准：以已获批治疗性抗体为可开发性金标准",
        fontsize=14, color=INK, x=0.008, ha="left", y=0.985, fontweight="bold",
    )
    fig.text(
        0.008, 0.017,
        "数据来源：RCSB PDB（26 个已获批抗体 + 231 条抗体重链）  ·  打分使用空表位，仅考察序列内在责任基序",
        fontsize=8.5, color=INK_MUTED, ha="left",
    )
    fig.tight_layout(rect=(0, 0.035, 1, 0.945))
    fig.savefig(OUT_PNG, dpi=150, bbox_inches="tight", facecolor=SURFACE)

    print(f"✅ Wrote {OUT_PNG.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
