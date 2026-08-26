#!/usr/bin/env python3
"""Run the retrospective antibody benchmark → reports/antibody_benchmark_results_<tag>.csv.

Approved therapeutic antibodies are ground truth for "developable": a
liability filter that rejects them is mis-calibrated.  This script pushes the
gold cohort and two decoy cohorts through the *production* scoring path
(``filter_cdrh3_design`` → ``score_candidate``) and reports:

1. gold pass rate and the flags responsible for rejections
2. score separation between real drugs and composition-matched decoys
3. disagreement between the ``generation_filter`` and ``sequence_qc`` gates
4. the real CDR-H3 length / aromatic-fraction distributions

Network-free: it reads the dataset CSV produced by
``scripts/build_antibody_benchmark.py``.

Scoring is run with an empty epitope so that only sequence-intrinsic
liabilities are measured — the gold antibodies bind 26 different targets, so
any single shared epitope would be arbitrary.  Both cohorts get identical
treatment, keeping the comparison fair.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from biochat.eval.antibody_benchmark import (  # noqa: E402
    aromatic_fraction,
    describe,
    flag_frequency,
    mann_whitney_u,
    normalise_flag,
    random_decoys,
    shuffled_decoys,
)
from biochat.tool.antibody_design.generation_filter import filter_cdrh3_design  # noqa: E402
from biochat.tool.antibody_design.scoring import score_candidate  # noqa: E402
from biochat.tool.antibody_design.sequence_qc import run_full_qc  # noqa: E402

DEFAULT_DATASET = PROJECT_ROOT / "reports" / "antibody_benchmark_dataset.csv"
REPORTS_DIR = PROJECT_ROOT / "reports"

FIELDNAMES = [
    "cohort",
    "label",
    "cdrh3",
    "length",
    "aromatic_fraction",
    "filter_accepted",
    "score",
    "score_accepted",
    "gate_conflict",
    "seq_qc_status",
    "flags",
]

EMPTY_EPITOPE = ""


def evaluate(cdrh3: str) -> dict:
    """Run one CDR-H3 through the production path plus the parallel QC gate."""
    filter_ok, flags, metrics = filter_cdrh3_design(cdrh3, EMPTY_EPITOPE)
    scored = score_candidate(cdrh3, EMPTY_EPITOPE, "", flags, metrics)
    qc = run_full_qc(cdrh3, epitope=EMPTY_EPITOPE)
    qc_status = (qc.get("sequence_qc") or {}).get("status", "unknown")

    return {
        "cdrh3": cdrh3,
        "length": len(cdrh3),
        "aromatic_fraction": round(aromatic_fraction(cdrh3), 4),
        "filter_accepted": filter_ok,
        "score": scored["aggregate_score"],
        "score_accepted": scored["accepted"],
        # The filter and the scorer must agree on whether a candidate survives.
        "gate_conflict": filter_ok != scored["accepted"],
        "seq_qc_status": qc_status,
        "flags": [normalise_flag(f) for f in flags],
    }


def load_dataset(path: Path) -> tuple[list[dict], list[dict]]:
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    gold = [r for r in rows if r["cohort"] == "gold"]
    dist = [r for r in rows if r["cohort"] == "distribution"]
    return gold, dist


def build_rows(gold: list[dict], dist: list[dict]) -> list[dict]:
    """Evaluate the gold cohort, its two decoy sets, and the distribution cohort."""
    gold_seqs = [r["cdrh3"] for r in gold]
    rows: list[dict] = []

    for rec, seq in zip(gold, gold_seqs, strict=True):
        rows.append({"cohort": "approved_drug", "label": rec["drug"], **evaluate(seq)})

    for i, seq in enumerate(shuffled_decoys(gold_seqs, seed=42)):
        rows.append({"cohort": "decoy_shuffled", "label": f"shuffle_{i:02d}", **evaluate(seq)})

    for i, seq in enumerate(random_decoys([len(s) for s in gold_seqs], seed=42)):
        rows.append({"cohort": "decoy_random", "label": f"random_{i:02d}", **evaluate(seq)})

    for rec in dist:
        rows.append({"cohort": "pdb_antibody", "label": rec["pdb_entity"], **evaluate(rec["cdrh3"])})

    return rows


def summarise(rows: list[dict]) -> dict:
    by_cohort: dict[str, list[dict]] = {}
    for r in rows:
        by_cohort.setdefault(r["cohort"], []).append(r)

    drugs = by_cohort.get("approved_drug", [])
    shuffled = by_cohort.get("decoy_shuffled", [])
    random_ = by_cohort.get("decoy_random", [])
    pdb_ab = by_cohort.get("pdb_antibody", [])

    def pass_rate(group: list[dict]) -> float:
        return 100.0 * sum(1 for r in group if r["filter_accepted"]) / len(group) if group else 0.0

    def scores(group: list[dict]) -> list[float]:
        return [r["score"] for r in group]

    _, auc_shuffled = mann_whitney_u(scores(drugs), scores(shuffled))
    _, auc_random = mann_whitney_u(scores(drugs), scores(random_))

    calibration_pool = drugs + pdb_ab
    return {
        "pass_rate": {c: round(pass_rate(g), 1) for c, g in by_cohort.items()},
        "score_stats": {c: {k: round(v, 2) for k, v in describe(scores(g)).items()} for c, g in by_cohort.items()},
        "auc_vs_shuffled": round(auc_shuffled, 3),
        "auc_vs_random": round(auc_random, 3),
        "rejected_drugs": [
            {"drug": r["label"], "cdrh3": r["cdrh3"], "length": r["length"], "flags": r["flags"]}
            for r in drugs
            if not r["filter_accepted"]
        ],
        "gate_conflicts": {c: sum(1 for r in g if r["gate_conflict"]) for c, g in by_cohort.items()},
        "qc_gate_disagreement": sum(
            1 for r in drugs if r["filter_accepted"] != (r["seq_qc_status"] != "fail")
        ),
        "gold_flag_frequency": flag_frequency(r["flags"] for r in drugs),
        "length_distribution": {k: round(v, 2) for k, v in describe([r["length"] for r in calibration_pool]).items()},
        "aromatic_distribution": {
            k: round(v, 4) for k, v in describe([r["aromatic_fraction"] for r in calibration_pool]).items()
        },
        "n_calibration_pool": len(calibration_pool),
    }


def render_report(summary: dict, tag: str) -> str:
    lines = [
        f"# 抗体管线回顾性基准 — `{tag}`",
        "",
        "已获批治疗性抗体是「可开发性」的金标准。过滤器若拒绝它们，说明标定有问题。",
        "打分使用空表位，仅考察序列内在责任基序；各组处理条件完全一致。",
        "",
        "## 1. 通过率",
        "",
        "| 队列 | 通过率 | 中位分 | n |",
        "|---|---|---|---|",
    ]
    labels = {
        "approved_drug": "已获批药物",
        "decoy_shuffled": "组分打乱诱饵",
        "decoy_random": "均匀随机诱饵",
        "pdb_antibody": "PDB 抗体样本",
    }
    for cohort, label in labels.items():
        if cohort not in summary["pass_rate"]:
            continue
        st = summary["score_stats"][cohort]
        lines.append(f"| {label} | {summary['pass_rate'][cohort]}% | {st['p50']} | {int(st['n'])} |")

    lines += [
        "",
        "## 2. 判别力",
        "",
        f"- 真药 vs 组分打乱诱饵：**AUC = {summary['auc_vs_shuffled']}**",
        f"- 真药 vs 均匀随机诱饵：**AUC = {summary['auc_vs_random']}**",
        "",
        "> AUC = 0.5 表示打分器无法区分真实抗体与同组分的随机序列。",
        "",
        "## 3. 被拒绝的已获批药物",
        "",
    ]
    if summary["rejected_drugs"]:
        lines += ["| 药物 | CDR-H3 | 长度 | 触发旗标 |", "|---|---|---|---|"]
        for r in summary["rejected_drugs"]:
            lines.append(f"| {r['drug']} | `{r['cdrh3']}` | {r['length']} | {', '.join(r['flags'])} |")
    else:
        lines.append("无 —— 所有已获批药物均通过过滤器。")

    lines += [
        "",
        "## 4. 闸门一致性",
        "",
        f"- `filter_cdrh3_design` 与 `score_candidate` 判定冲突：**{sum(summary['gate_conflicts'].values())}** 条",
        f"- `generation_filter` 与 `sequence_qc` 对已获批药物判定不一致：**{summary['qc_gate_disagreement']}** 个",
        "",
        "> 两处均应为 0。冲突意味着硬失败信号未能贯通打分路径。",
        "",
        "## 5. 已获批药物上的旗标触发频次",
        "",
        "| 旗标 | 触发次数 |",
        "|---|---|",
    ]
    for flag, count in summary["gold_flag_frequency"]:
        lines.append(f"| `{flag}` | {count} |")

    ld, ad = summary["length_distribution"], summary["aromatic_distribution"]
    lines += [
        "",
        "## 6. 真实抗体分布（用于重标定）",
        "",
        f"样本量 n = {summary['n_calibration_pool']}（已获批药物 + PDB 抗体）",
        "",
        "| 指标 | P5 | P25 | P50 | P75 | P95 |",
        "|---|---|---|---|---|---|",
        f"| CDR-H3 长度 | {ld['p5']} | {ld['p25']} | {ld['p50']} | {ld['p75']} | {ld['p95']} |",
        f"| 芳香族占比 | {ad['p5']} | {ad['p25']} | {ad['p50']} | {ad['p75']} | {ad['p95']} |",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="before", help="label for the output files (e.g. before / after)")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="dataset CSV path")
    args = parser.parse_args()

    if not args.dataset.exists():
        print(f"❌ dataset not found: {args.dataset}")
        print("   run: python scripts/build_antibody_benchmark.py")
        return 1

    gold, dist = load_dataset(args.dataset)
    print(f"📥 Loaded {len(gold)} approved antibodies + {len(dist)} PDB antibodies")

    rows = build_rows(gold, dist)
    summary = summarise(rows)

    REPORTS_DIR.mkdir(exist_ok=True)
    csv_path = REPORTS_DIR / f"antibody_benchmark_results_{args.tag}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in rows:
            writer.writerow({**r, "flags": ";".join(r["flags"])})

    json_path = REPORTS_DIR / f"antibody_benchmark_summary_{args.tag}.json"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    md_path = REPORTS_DIR / f"antibody_benchmark_report_{args.tag}.md"
    md_path.write_text(render_report(summary, args.tag), encoding="utf-8")

    print(f"\n💊 已获批药物通过率 : {summary['pass_rate'].get('approved_drug', 0)}%")
    print(f"   中位分            : {summary['score_stats']['approved_drug']['p50']}")
    print(f"   AUC vs 组分打乱   : {summary['auc_vs_shuffled']}  (0.5 = 无判别力)")
    print(f"   闸门冲突          : {sum(summary['gate_conflicts'].values())} 条")
    if summary["rejected_drugs"]:
        print("   被拒药物          : " + ", ".join(r["drug"] for r in summary["rejected_drugs"]))

    top = Counter(dict(summary["gold_flag_frequency"])).most_common(3)
    if top:
        print("   高频旗标          : " + ", ".join(f"{f}×{c}" for f, c in top))

    for p in (csv_path, json_path, md_path):
        print(f"✅ Wrote {p.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
