#!/usr/bin/env python3
"""Journal-grade figures (English, publication style) for the Biochat antibody
design system.  Colour-blind safe palette (Okabe-Ito), Helvetica, white
background, vector output, 300 dpi.

Figures:
  fig1_pipeline.png/svg   — end-to-end antibody design pipeline (scheme)
  fig2_benchmark.png/svg  — before/after retrospective benchmark (3 panels)
  fig3_cdrh3.png/svg      — position-sensitive CDRH3 model vs production scorer
  fig4_engineering.png/svg— engineering quality: tests + codebase composition
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np

# ── Okabe-Ito colour-blind-safe palette ─────────────────────────
BLUE   = "#0072B2"
ORANGE = "#E69F00"
GREEN  = "#009E73"
RED    = "#D55E00"
SKY    = "#56B4E9"
GREY   = "#999999"
DARK   = "#000000"
LIGHT_GREY = "#CCCCCC"

FIG_DIR = "figs"
DPI = 300

FONT = "Helvetica"


def _setup_font() -> None:
    avail = {f.name for f in fm.fontManager.ttflist}
    if FONT in avail:
        plt.rcParams["font.sans-serif"] = [FONT, "DejaVu Sans"]
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["axes.unicode_minus"] = False


def _save(fig, name: str) -> None:
    for ext in ("png", "svg"):
        fig.savefig(f"{FIG_DIR}/{name}.{ext}", dpi=DPI, bbox_inches="tight",
                    facecolor="white", transparent=False)
    plt.close(fig)
    print("OK", name)


def _style_axis(ax) -> None:
    ax.set_facecolor("white")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(DARK)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=DARK, labelsize=7.5, length=2.5, width=0.8)


# ═══════════════════════════════════════════════════════════════
# FIG 1 — pipeline scheme
# ═══════════════════════════════════════════════════════════════
def fig1_pipeline() -> None:
    steps = [
        ("1", "Epitope input", "target sequence\n(e.g. HER2 ECD)"),
        ("2", "CDRH3 diffusion", "DiffCDRH3\nTransformer-VAE + cond. diffusion"),
        ("3", "Structure prediction", "NanoBodyBuilder2\nVH geometry checks"),
        ("4", "Molecular docking", "HDOCK\ninterface analysis"),
        ("5", "Developability", "aggregation / glycan / charge\nhard liability gates"),
        ("6", "Multi-dim ranking", "candidate scoring\naudit-trail logging"),
    ]
    fig, ax = plt.subplots(figsize=(11.0, 3.1), facecolor="white")
    ax.set_xlim(0, 100); ax.set_ylim(0, 30)
    ax.axis("off")

    n = len(steps)
    bw, gap = 14.6, 2.2
    x0 = 1.0
    for i, (num, title, desc) in enumerate(steps):
        x = x0 + i * (bw + gap)
        # node body: thin grey border, white fill (journal style)
        box = FancyBboxPatch((x, 8.5), bw, 15.5,
                             boxstyle="round,pad=0.15,rounding_size=0.9",
                             facecolor="white", edgecolor=DARK, linewidth=0.9, zorder=3)
        ax.add_patch(box)
        # number circle
        circ = plt.Circle((x + 1.6, 8.5 + 15.5 - 2.2), 1.15, facecolor=BLUE,
                          edgecolor="none", zorder=4)
        ax.add_patch(circ)
        ax.text(x + 1.6, 8.5 + 15.5 - 2.2, num, ha="center", va="center",
                fontsize=7.5, fontweight="bold", color="white", zorder=5)
        # title
        ax.text(x + bw / 2 + 0.6, 8.5 + 11.0, title, ha="center", va="center",
                fontsize=8.6, fontweight="bold", color=DARK, zorder=4)
        # description
        for ln, line in enumerate(desc.split("\n")):
            ax.text(x + bw / 2 + 0.6, 8.5 + 6.6 - ln * 2.6, line, ha="center",
                    va="center", fontsize=6.3, color="#333333", zorder=4)
        if i < n - 1:
            ax.add_patch(FancyArrowPatch(
                (x + bw + 0.15, 8.5 + 7.75), (x + bw + gap - 0.15, 8.5 + 7.75),
                arrowstyle="-|>", mutation_scale=13, color=DARK, lw=1.0, zorder=2))

    ax.text(50, 27.2, "Self-developed antibody design pipeline  (8,400+ lines)",
            ha="center", fontsize=12.5, fontweight="bold", color=DARK)
    ax.text(50, 2.6,
            "Every stage writes an audit-trail record \u00b7 end-to-end reproducible \u00b7 "
            "validated against 26 approved therapeutic antibodies",
            ha="center", fontsize=7.6, color="#333333")
    _save(fig, "fig1_pipeline")


# ═══════════════════════════════════════════════════════════════
# FIG 2 — retrospective benchmark, before vs after
# ═══════════════════════════════════════════════════════════════
def fig2_benchmark() -> None:
    metrics = [
        ("(a)  Discriminative power\nAUC, approved vs random decoys", 0.212, 0.734, "AUC", "higher is better"),
        ("(b)  Approved-drug pass rate\n26 gold-standard antibodies", 96.2, 100.0, "%", "higher is better"),
        ("(c)  Gate conflicts\nfilter vs scorer disagreements", 36.0, 0.0, "count", "lower is better"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.6), facecolor="white")
    for ax, (label, before, after, unit, note) in zip(axes, metrics):
        _style_axis(ax)

        cats = ["before", "after"]
        vals = [before, after]
        cols = ["#D9D9D9", BLUE]
        x = np.arange(2)
        bars = ax.bar(x, vals, width=0.52, color=cols, edgecolor=DARK,
                      linewidth=0.7, zorder=3)
        for xi, v in zip(x, vals):
            ax.annotate(f"{v:g}", xy=(xi, v), xytext=(0, 3),
                        textcoords="offset points", ha="center", fontsize=12,
                        fontweight="bold",
                        color="#444444" if xi == 0 else BLUE, zorder=4)
        ax.set_xticks(x)
        ax.set_xticklabels(cats, fontsize=8.5, color=DARK)
        ax.set_ylabel(unit, fontsize=8.2, color=DARK)
        ax.tick_params(axis="y", labelsize=7.5)

        # improvement tag: vector arrow + delta text (side-by-side, no overlap)
        improved = (after > before) if "higher" in note else (after < before)
        delta = abs(after - before)
        top = max(vals)
        ylim_hi = top * 1.38 if top > 0 else 1.0
        ax.set_ylim(0, ylim_hi)
        tri_x, tri_y = 0.5, ylim_hi * 0.86
        ax.annotate("", xy=(tri_x, tri_y + ylim_hi * 0.09), xytext=(tri_x, tri_y),
                    arrowprops=dict(arrowstyle="-|>", color=GREEN if improved else RED,
                                    lw=1.6, mutation_scale=13), zorder=4)
        ax.annotate(f"{delta:g} {unit}", xy=(tri_x + 0.34, tri_y + ylim_hi * 0.045),
                    ha="left", va="center", fontsize=8, fontweight="bold",
                    color=GREEN if improved else RED, zorder=4)

        ax.set_title(label, fontsize=8.6, color=DARK, pad=10, loc="left")
        ax.text(0.5, -0.16, note, transform=ax.transAxes, ha="center",
                fontsize=7.2, color="#555555")

    fig.suptitle("Retrospective benchmark: approved therapeutic antibodies as the developability gold standard",
                 fontsize=11.5, fontweight="bold", color=DARK, y=1.02)
    fig.tight_layout()
    _save(fig, "fig2_benchmark")


# ═══════════════════════════════════════════════════════════════
# FIG 3 — CDRH3 position-sensitive model
# ═══════════════════════════════════════════════════════════════
def fig3_cdrh3() -> None:
    fig, ax = plt.subplots(figsize=(5.6, 4.1), facecolor="white")
    _style_axis(ax)

    labels = ["Production scorer\n(composition-based)", "Position-sensitive\ndipeptide model"]
    values = [0.5, 0.8844]
    errs = [0.0, 0.0246]
    colors = ["#D9D9D9", BLUE]

    bars = ax.bar(labels, values, yerr=errs, width=0.5, color=colors,
                  edgecolor=DARK, linewidth=0.7, zorder=3,
                  error_kw=dict(ecolor=DARK, lw=0.9, capsize=4))
    for bar, v in zip(bars, values):
        ax.annotate(f"{v:.2f}", xy=(bar.get_x() + bar.get_width() / 2, v + 0.03),
                    ha="center", fontsize=10.5, fontweight="bold", color=DARK, zorder=4)

    ax.axhline(0.5, color=DARK, lw=0.8, ls=(0, (3, 3)), zorder=1)
    ax.annotate("random level (AUC = 0.5)", xy=(1.62, 0.505), fontsize=7.2,
                color="#333333", va="bottom")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("AUC (approved vs composition-matched shuffled)", fontsize=8.2, color=DARK)
    ax.tick_params(axis="x", labelsize=7.8)
    ax.set_title("Position-sensitive CDRH3 model resolves the\ncompositional-scorer blind spot",
                 fontsize=9.6, color=DARK, pad=10, loc="left", fontweight="bold")

    ax.text(0.02, 0.035,
            "mean \u00b1 s.d. over 40 shuffle seeds (min 0.839, max 0.922)\n"
            "train 1,296 PDB heavy chains \u00b7 test 26 approved antibodies (held out)\n"
            "score = mean pointwise mutual information of adjacent residues",
            transform=ax.transAxes, fontsize=6.8, color="#333333", va="bottom",
            bbox={"boxstyle": "round,pad=0.4", "facecolor": "#FAFAFA",
                  "edgecolor": LIGHT_GREY, "linewidth": 0.6})
    fig.tight_layout()
    _save(fig, "fig3_cdrh3")


# ═══════════════════════════════════════════════════════════════
# FIG 4 — engineering quality
# ═══════════════════════════════════════════════════════════════
def fig4_engineering() -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.2, 3.9), facecolor="white",
                                   gridspec_kw={"width_ratios": [1.15, 1.0]})

    # ── panel (a): test suite ───────────────────────────────────
    _style_axis(ax1)
    ax1.set_xlim(0, 150); ax1.set_ylim(-0.6, 0.6)
    ax1.barh([0], [149], height=0.42, color=GREEN, edgecolor=DARK, linewidth=0.7, zorder=3)
    ax1.barh([0], [1], left=[149], height=0.42, color=LIGHT_GREY, edgecolor=DARK, linewidth=0.7, zorder=3)
    ax1.text(149 / 2, 0.18, "149 passed", ha="center", fontsize=8.5, fontweight="bold", color="white", zorder=4)
    ax1.text(149.5, 0.18, "1 skipped", ha="center", fontsize=7.2, color="#333333", zorder=4)
    ax1.set_yticks([])
    ax1.set_xlabel("tests (pytest)", fontsize=8.2, color=DARK)
    ax1.set_title("(a)  Test suite: 149 passed / 1 skipped", fontsize=9.2,
                  color=DARK, loc="left", pad=8, fontweight="bold")

    # ── panel (b): codebase composition ─────────────────────────
    _style_axis(ax2)
    modules = [
        ("antibody design pipeline (self)", 8402, BLUE),
        ("agent / service / LLM layers", 5703, SKY),
        ("UI (Streamlit / Gradio)", 3240, GREEN),
        ("utils / knowledge / schemas", 3407, ORANGE),
        ("scientific tools (upstream)", 32906, LIGHT_GREY),
    ]
    modules = modules[::-1]
    names = [m[0] for m in modules]
    vals = [m[1] for m in modules]
    cols = [m[2] for m in modules]

    ypos = np.arange(len(modules))
    ax2.barh(ypos, vals, height=0.58, color=cols, edgecolor="none", zorder=3)
    for y, v, name in zip(ypos, vals, names):
        if v >= 5000:
            ax2.text(v - 400, y, f"{v:,}", va="center", ha="right", fontsize=7.2,
                     color="white", fontweight="bold", zorder=4)
        else:
            ax2.text(v + 250, y, f"{v:,}", va="center", ha="left", fontsize=7.2,
                     color="#333333", zorder=4)
    ax2.set_yticks(ypos)
    ax2.set_yticklabels(names, fontsize=7.2, color=DARK)
    ax2.set_xlabel("lines of Python", fontsize=8.2, color=DARK)
    ax2.set_xlim(0, 36000)
    ax2.set_title("(b)  Codebase composition (53,658 LOC)", fontsize=9.2,
                  color=DARK, loc="left", pad=8, fontweight="bold")
    ax2.xaxis.set_major_formatter(lambda x, _: f"{int(x/1000)}k")

    fig.suptitle("Engineering quality: automated tests and codebase composition",
                 fontsize=11.5, fontweight="bold", color=DARK, y=1.02)
    fig.tight_layout()
    _save(fig, "fig4_engineering")


# ═══════════════════════════════════════════════════════════════
# FIG 5 — combined 2x2 for slides
# ═══════════════════════════════════════════════════════════════
def fig5_summary() -> None:
    from matplotlib.image import imread
    files = ["fig1_pipeline.png", "fig2_benchmark.png", "fig3_cdrh3.png", "fig4_engineering.png"]
    titles = ["(a) End-to-end design pipeline", "(b) Retrospective benchmark, before/after",
              "(c) Position-sensitive CDRH3 model", "(d) Engineering quality"]
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 8.6), facecolor="white")
    for ax, f, t in zip(axes.flat, files, titles):
        ax.imshow(imread(f"{FIG_DIR}/{f}"))
        ax.axis("off")
        ax.set_title(t, fontsize=11, color=DARK, loc="left", pad=7, fontweight="bold")
    fig.suptitle("Biochat: AI-agent antibody design & developability assessment",
                 fontsize=15, fontweight="bold", color=DARK, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    _save(fig, "fig5_summary")


if __name__ == "__main__":
    _setup_font()
    fig1_pipeline()
    fig2_benchmark()
    fig3_cdrh3()
    fig4_engineering()
    fig5_summary()
    print("ALL DONE")
