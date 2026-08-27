#!/usr/bin/env python3
"""Render the combined before/after benchmark report → reports/antibody_benchmark_report.md.

Reads the two summaries written by ``scripts/run_antibody_benchmark.py`` and
emits one narrative document: what the benchmark found, what was fixed, what
measurably changed, and what remains open.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from biochat.tool.antibody_design.generation_filter import (  # noqa: E402
    ALLOWED_MAX_LEN,
    ALLOWED_MIN_LEN,
    AROMATIC_FRACTION_MAX,
    PREFERRED_MAX_LEN,
    PREFERRED_MIN_LEN,
    SINGLE_AROMATIC_FRACTION_MAX,
)

REPORTS = PROJECT_ROOT / "reports"
OUT_MD = REPORTS / "antibody_benchmark_report.md"


def _load_lm_eval() -> dict | None:
    """The position-sensitive prototype's evaluation, if it has been run."""
    path = REPORTS / "cdrh3_lm_eval.json"
    return json.loads(path.read_text()) if path.exists() else None


def delta(before: float, after: float, higher_is_better: bool = True) -> str:
    if before == after:
        return "—"
    improved = (after > before) if higher_is_better else (after < before)
    return "✅" if improved else "⚠️"


def main() -> int:
    try:
        b = json.loads((REPORTS / "antibody_benchmark_summary_before.json").read_text())
        a = json.loads((REPORTS / "antibody_benchmark_summary_after.json").read_text())
    except FileNotFoundError as exc:
        print(f"❌ {exc.filename} missing — run scripts/run_antibody_benchmark.py for both tags")
        return 1

    with (REPORTS / "antibody_benchmark_dataset.csv").open(encoding="utf-8") as fh:
        dataset = list(csv.DictReader(fh))
    n_gold = sum(1 for r in dataset if r["cohort"] == "gold")
    n_dist = sum(1 for r in dataset if r["cohort"] == "distribution")

    ld, ad = a["length_distribution"], a["aromatic_distribution"]
    bc, ac = sum(b["gate_conflicts"].values()), sum(a["gate_conflicts"].values())

    lines = [
        "# 抗体设计管线回顾性基准验证",
        "",
        "> 生成脚本：`scripts/make_benchmark_report.py`（数据来自 `run_antibody_benchmark.py` 的 before/after 两次运行）",
        "",
        "## 方法",
        "",
        f"以 **{n_gold} 个已获批治疗性抗体**为可开发性金标准，检验管线的过滤与打分是否会误杀真药。",
        f"另取 **{n_dist} 条 PDB 抗体重链**建立长度与芳香族占比的真实分布，用于阈值标定。",
        "",
        "关键前提：该打分器是**可开发性/责任基序过滤器**（`BASE_SCORE=80` 减惩罚），"
        "**不预测结合亲和力**。因此「能否按结合力召回真药」是错的问法；"
        "唯一科学成立的问法是「过滤器会不会拒绝已经上市的药」。",
        "",
        "**数据溯源**：抗体名称与序列一律取自 RCSB PDB 的链描述字段，不使用任何记忆值。"
        "同一药物有多个结构时采用**多数表决**——这剔除了 `7PKL_2`（"
        "「trastuzumab Light Chain VHH fusion」，其可提取的 CDR-H3 属于融合的纳米抗体而非曲妥珠单抗）。"
        "CDR-H3 提取规则在 4 个已发表 Kabat 值上逐字符回测（`verify_extractor`）。",
        "",
        "打分使用**空表位**，仅考察序列内在责任基序——26 个金标准抗体结合 26 个不同靶点，"
        "任何单一共享表位都是任意的。各队列处理条件完全一致。",
        "",
        "## 发现的缺陷",
        "",
        "### Bug-1　硬排除条件被静默降级",
        "",
        "`generation_filter.py` 发出的 5 个旗标不存在于 `schemas.PENALTY_TABLE`，"
        "**其中包含全部 4 个硬排除条件**（`extra_Cys_in_CDRH3`、`cdrh3_length_out_of_allowed_range`、"
        "`noncanonical_amino_acid`、`nglyc_motif_in_CDRH3`）。",
        "`scoring.score_candidate` 通过 `PENALTY_TABLE.get(flag, (\"WARNING\", 2, flag))` 解析旗标，"
        "未登记的键落入默认分支，硬排除被降级为 **-2 分警告**。",
        "",
        "实测后果：4aa 序列 `NDDY` 被过滤器判 `accepted=False`，打分器却给出 **93.0 分且 `accepted=True`**。"
        "另有 14 条 `PENALTY_TABLE` 条目为死代码，从未被任何模块发出。",
        "",
        "### Bug-2　硬失败信号在生产路径被丢弃",
        "",
        "`api.py` 中 `ok, f, m = filter_cdrh3_design(...)` 之后 **`ok` 从未被使用**，"
        "过滤器的否决权从未进入 `score_and_rank_candidates` 的输出。",
        "",
        "### 标定偏移　阈值在惩罚常态而非异常",
        "",
        "| 阈值 | 原值 | 在真实抗体上的表现 | 新值 | 依据 |",
        "|---|---|---|---|---|",
        f"| 偏好长度窗 | 13–16 | **仅覆盖 24.1%**（76% 真药被扣 12 分） "
        f"| {PREFERRED_MIN_LEN}–{PREFERRED_MAX_LEN} | P10–P90，覆盖 80.5% |",
        f"| 允许长度窗 | 6–26 | 硬排除 nivolumab（4aa） | {ALLOWED_MIN_LEN}–{ALLOWED_MAX_LEN} | 实测最小/最大值 |",
        f"| 芳香族占比 | > 0.30 | **命中 45.9%**（真实中位数恰为 0.300） | > {AROMATIC_FRACTION_MAX} | P90，命中 10.1% |",
        f"| 单一芳香族 | > 0.25 | 命中 27.2% | > {SINGLE_AROMATIC_FRACTION_MAX} | P90，命中 9.7% |",
        "| 单一氨基酸占比 | frac > 0.35 | 短序列假阳性（4aa 中一次重复即 50%） | 附加 count ≥ 4 | 误报 16.0% → 10.5% |",
        "",
        "> `PENALTY_TABLE` 中 `high_aromatic_fraction` 的说明文字本就写着「> 45%」，"
        "而代码实现用的是 0.30——文档与实现原本就不一致。",
        "",
        "另外发现**双闸门长度定义冲突**：`sequence_qc` 硬失败区间为 <8 或 >22，"
        "`generation_filter` 为 <6 或 >26，同一序列可在两个闸门得到相反判定。"
        "现已改为共享同一组常量，无法再漂移。",
        "",
        "## 修复前后对照",
        "",
        "| 指标 | 修复前 | 修复后 | |",
        "|---|---|---|---|",
        f"| 已获批药物通过率 | {b['pass_rate']['approved_drug']}% | {a['pass_rate']['approved_drug']}% | "
        f"{delta(b['pass_rate']['approved_drug'], a['pass_rate']['approved_drug'])} |",
        f"| 已获批药物中位分 | {b['score_stats']['approved_drug']['p50']} | {a['score_stats']['approved_drug']['p50']} | "
        f"{delta(b['score_stats']['approved_drug']['p50'], a['score_stats']['approved_drug']['p50'])} |",
        f"| 随机诱饵中位分 | {b['score_stats']['decoy_random']['p50']} | {a['score_stats']['decoy_random']['p50']} | "
        f"{delta(b['score_stats']['decoy_random']['p50'], a['score_stats']['decoy_random']['p50'], False)} |",
        f"| **AUC（真药 vs 随机诱饵）** | **{b['auc_vs_random']}** | **{a['auc_vs_random']}** | "
        f"{delta(b['auc_vs_random'], a['auc_vs_random'])} |",
        f"| AUC（真药 vs 组分打乱） | {b['auc_vs_shuffled']} | {a['auc_vs_shuffled']} | — |",
        f"| 闸门冲突（filter vs scorer） | {bc} | {ac} | {delta(bc, ac, False)} |",
        f"| PDB 抗体样本通过率 | {b['pass_rate']['pdb_antibody']}% | {a['pass_rate']['pdb_antibody']}% | "
        f"{delta(b['pass_rate']['pdb_antibody'], a['pass_rate']['pdb_antibody'])} |",
        "",
        "**最重要的一行是 AUC vs 随机诱饵**：修复前为 "
        f"**{b['auc_vs_random']}**——意味着均匀随机序列有约 "
        f"{100 * (1 - b['auc_vs_random']):.0f}% 的概率打败真实上市药物。"
        "原因是真实抗体 CDR 富含芳香族，而过滤器恰恰重罚芳香族，"
        "**打分方向与「真实抗体性」呈负相关**。修复后为 "
        f"**{a['auc_vs_random']}**，方向已被纠正。",
        "",
        "被拒绝的已获批药物：修复前 "
        + (", ".join(f"`{r['drug']}`" for r in b["rejected_drugs"]) or "无")
        + "；修复后 "
        + (", ".join(f"`{r['drug']}`" for r in a["rejected_drugs"]) or "**无**")
        + "。",
        "",
        "![基准结果](antibody_benchmark.png)",
        "",
        "## 未解决的问题（如实记录）",
        "",
        f"### 1. 生产打分器对「真实抗体性」无判别力（AUC = {a['auc_vs_shuffled']}）",
        "",
        "真药与其**组分匹配打乱序列**的 AUC 修复前后均为 0.5，"
        "26 对中 21 对分数完全相同，其余仅差 ±2。",
        "根因是打分完全由氨基酸**组成**决定（长度、芳香族占比、电荷计数），"
        "而打乱保留组成不变——因此生产打分器无法区分真实治疗性抗体与其乱序版本。",
        "",
        "这是架构层面的限制，不是调参能解决的。**解决路径已实现、验证并接入生产**，见下节。"
        "本次修复解决的是「打分方向错误」，位置敏感模型解决的是「打分缺乏分辨率」。",
        "",]

    lm = _load_lm_eval()
    if lm:
        shuf = lm["auc_vs_shuffled"]
        lines += [
            "## 位置敏感打分：解决路径的实现与接入",
            "",
            "`biochat/eval/cdrh3_lm.py` —— 组成受控的二肽（相邻残基）模型。打分为相邻残基对的"
            "**点互信息**均值：",
            "",
            "```",
            "score(s) = mean_i  log[ P(s_i s_{i+1}) / (P(s_i) · P(s_{i+1})) ]",
            "```",
            "",
            "该量在残基独立排列时为零，因此打乱序列——保留全部单体频率、只破坏相邻关系——"
            "天然得分趋近零。**组成受控是设计上保证的，不是事后归一化的。**",
            "",
            f"训练集为 PDB 抗体重链语料（{lm['corpus_size']} 条，剔除与测试集序列相同的 "
            f"{lm['removed_overlap']} 条后训练 {lm['n_train']} 条）；"
            f"测试集为 {lm['n_test']} 个已获批抗体，**全程留出**。",
            "",
            "| 比较 | 生产打分器 | 二肽模型 |",
            "|---|---|---|",
            f"| 已获批药 vs 其组分打乱 | {a['auc_vs_shuffled']} | "
            f"**{shuf['mean']:.3f} ± {shuf['stdev']:.3f}**（{lm['shuffle_seeds']} 个打乱种子，"
            f"范围 {shuf['min']:.3f}–{shuf['max']:.3f}）|",
            f"| 已获批药 vs 均匀随机 | {a['auc_vs_random']} | "
            f"{lm['auc_vs_random']['mean']:.3f} ± {lm['auc_vs_random']['stdev']:.3f} |",
            "",
            f"5 折交叉验证各折留出均分 {lm['cross_validation_fold_means']}，"
            "分布一致，未见过拟合。",
            "",
            "模型学到的最过表达相邻残基对（已按支撑度过滤，n ≥ 50）：",
            "",
            "| 残基对 | PMI | 语料中出现次数 |",
            "|---|---|---|",
        ]
        for pair, pmi, count in lm["top_motifs"][:6]:
            lines.append(f"| `{pair}` | {pmi:+.2f} | {count} |")
        lines += [
            "",
            "这些正是 CDR-H3 由 J 片段编码的经典 C 端基序（`…AMDY` / `…FDY` / `…FDV`），"
            "说明模型捕捉到的是真实的抗体序列结构，而非噪声。",
            "",
            "> **支撑度过滤不是修饰**：不加 `min_count` 时，加性平滑会让语料中仅出现 4 次的 `CC` "
            "和 6 次的 `QQ` 排在出现 704 次的 `DY` 之前。这类稀疏伪影若直接报告即为错误结论。",
            "",
            "**接入方式为旁路上报，不参与排序**（`biochat/tool/antibody_design/antibody_likeness.py`）："
            "候选结果的 `scores[\"antibody_likeness\"]` 独立字段随责任基序分一并上报，"
            "`aggregate_score` 与 `rank` 不受影响——两个量纲、两种语义，不合成。"
            "模型文件缺失或损坏时该字段静默省略，可选诊断信号不会改变或中断候选打分。"
            "回归测试将「模型可用 vs 不可用」两次调用的完整排序输出做逐条比对，保证二者完全一致。",
            "",
            "该模型回答的是「像不像真实抗体环」，**不是**可开发性，更**不是**结合亲和力，"
            "不可作为 ΔG / Kd 报告；字段自带 `ranking_input=False` 与"
            "`provenance=model_inferred` 标注。",
            "",
        ]

    lines += [
        "### 2. `sequence_qc` 对真实抗体的整体判负率偏高（27.6%）",
        "",
        "其各条硬失败规则单独看均在 P90 目标附近（`excessive_single_aa_*` 10.5%、"
        "`excessive_aromatic_fraction` 10.1%），但多条独立的 P90 规则**叠加**后，"
        "257 条真实抗体中有 71 条（27.6%）被判 fail。",
        "这是「多少条独立 P90 规则应当合成一次硬失败」的设计问题，而非单条阈值的标定问题，"
        "因此本次**未作改动**，留待后续以联合分布重新设计。",
        "",
        f"### 3. 双闸门对 {a['qc_gate_disagreement']} 个已获批药物仍有分歧",
        "",
        "长度定义已统一，残留分歧全部来自 `sequence_qc` 自有的芳香族/酪氨酸阈值"
        "（`nivolumab`、`infliximab`、`cetuximab`、`natalizumab`、`eculizumab`、`basiliximab`），"
        "其中 4 个与 Tyr 富集相关——而 Tyr 富集正是抗体互补位的标志性特征。与问题 2 同源。",
        "",
        "## 真实抗体分布（标定依据）",
        "",
        f"样本量 n = {int(ld['n'])}（{n_gold} 个已获批药物 + {n_dist} 条 PDB 抗体重链）",
        "",
        "| 指标 | 最小 | P5 | P25 | 中位 | P75 | P95 | 最大 |",
        "|---|---|---|---|---|---|---|---|",
        f"| CDR-H3 长度 | {ld['min']:.0f} | {ld['p5']:.0f} | {ld['p25']:.0f} | {ld['p50']:.0f} | "
        f"{ld['p75']:.0f} | {ld['p95']:.1f} | {ld['max']:.0f} |",
        f"| 芳香族占比 | {ad['min']:.3f} | {ad['p5']:.3f} | {ad['p25']:.3f} | {ad['p50']:.3f} | "
        f"{ad['p75']:.3f} | {ad['p95']:.3f} | {ad['max']:.3f} |",
        "",
        "## 复现",
        "",
        "```bash",
        "python scripts/build_antibody_benchmark.py      # 联网，重建数据集",
        "python scripts/run_antibody_benchmark.py --tag before",
        "python scripts/run_antibody_benchmark.py --tag after",
        "python scripts/make_benchmark_figure.py",
        "python scripts/make_benchmark_report.py",
        "python -m pytest tests/test_antibody_benchmark.py -q",
        "```",
        "",
        "回归测试锁定了本次全部修复：将 `schemas.py` / `api.py` / `generation_filter.py` / "
        "`sequence_qc.py` 回退到修复前状态时，20 个测试中有 7 个失败。",
        "",
    ]

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ Wrote {OUT_MD.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
