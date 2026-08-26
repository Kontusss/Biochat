#!/usr/bin/env python3
"""Train and evaluate the CDR-H3 adjacency model → reports/cdrh3_bigram_model.json.

Answers the open question left by the retrospective benchmark: the production
liability score is composition-only, so it cannot separate a real antibody from
a scramble of its own residues (AUC 0.5).  This trains an order-sensitive model
and measures whether that gap actually closes.

Evaluation protocol — the approved therapeutic antibodies are **held out**:

    train  : PDB antibody heavy chains, minus any CDR-H3 that also appears in
             the approved cohort (exact-sequence overlap is removed)
    test   : the approved antibodies vs composition-matched shuffles of
             themselves, repeated over many shuffle seeds

Because a shuffle preserves every unigram frequency, an AUC above 0.5 on that
comparison can only come from residue order.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from biochat.eval.antibody_benchmark import (  # noqa: E402
    aromatic_fraction,
    extract_cdrh3,
    fetch_entities,
    is_plausible_cdrh3,
    mann_whitney_u,
    random_decoys,
    search_antibody_entities,
    shuffled_decoys,
)
from biochat.eval.cdrh3_lm import CDRH3BigramModel, cross_validate, top_motifs  # noqa: E402

REPORTS = PROJECT_ROOT / "reports"
DATASET = REPORTS / "antibody_benchmark_dataset.csv"
CORPUS = REPORTS / "cdrh3_corpus.csv"
MODEL_PATH = REPORTS / "cdrh3_bigram_model.json"
EVAL_PATH = REPORTS / "cdrh3_lm_eval.json"

SHUFFLE_SEEDS = 40


def build_corpus(target: int) -> list[dict]:
    """Fetch a training corpus of antibody CDR-H3s from the PDB."""
    entity_ids = search_antibody_entities(rows=target * 3)
    print(f"   search returned {len(entity_ids)} entities")
    records = fetch_entities(entity_ids, progress=True)
    print(f"   fetched {len(records)} sequences")

    rows: list[dict] = []
    seen: set[str] = set()
    for eid, rec in sorted(records.items()):
        cdrh3 = extract_cdrh3(rec["sequence"])
        if not is_plausible_cdrh3(cdrh3) or cdrh3 in seen:
            continue
        seen.add(cdrh3)
        rows.append(
            {
                "pdb_entity": eid,
                "chain_description": rec["description"],
                "cdrh3": cdrh3,
                "cdrh3_length": len(cdrh3),
                "aromatic_fraction": round(aromatic_fraction(cdrh3), 4),
            }
        )
        if len(rows) >= target:
            break
    return rows


def load_gold() -> list[str]:
    with DATASET.open(encoding="utf-8") as fh:
        return [r["cdrh3"] for r in csv.DictReader(fh) if r["cohort"] == "gold"]


def evaluate(model: CDRH3BigramModel, gold: list[str]) -> dict:
    """AUC of the model on held-out approved drugs vs their own shuffles."""
    real = model.score_many(gold)

    shuffle_aucs = []
    for seed in range(SHUFFLE_SEEDS):
        decoys = model.score_many(shuffled_decoys(gold, seed=seed))
        shuffle_aucs.append(mann_whitney_u(real, decoys)[1])

    random_aucs = []
    for seed in range(SHUFFLE_SEEDS):
        decoys = model.score_many(random_decoys([len(s) for s in gold], seed=seed))
        random_aucs.append(mann_whitney_u(real, decoys)[1])

    return {
        "n_test": len(gold),
        "n_train": model.n_train,
        "shuffle_seeds": SHUFFLE_SEEDS,
        "auc_vs_shuffled": {
            "mean": round(statistics.mean(shuffle_aucs), 4),
            "stdev": round(statistics.stdev(shuffle_aucs), 4),
            "min": round(min(shuffle_aucs), 4),
            "max": round(max(shuffle_aucs), 4),
        },
        "auc_vs_random": {
            "mean": round(statistics.mean(random_aucs), 4),
            "stdev": round(statistics.stdev(random_aucs), 4),
        },
        "mean_score_real": round(statistics.mean(real), 4),
        "mean_score_shuffled": round(
            statistics.mean(model.score_many(shuffled_decoys(gold, seed=0))), 4
        ),
        "top_motifs": [[p, round(v, 3), c] for p, v, c in top_motifs(model, 12)],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-size", type=int, default=2000, help="target training corpus size")
    parser.add_argument("--refresh-corpus", action="store_true", help="re-fetch the corpus from the PDB")
    args = parser.parse_args()

    if args.refresh_corpus or not CORPUS.exists():
        print(f"🧬 Building a CDR-H3 corpus (target {args.corpus_size})")
        rows = build_corpus(args.corpus_size)
        CORPUS.parent.mkdir(exist_ok=True)
        with CORPUS.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=["pdb_entity", "chain_description", "cdrh3", "cdrh3_length", "aromatic_fraction"]
            )
            writer.writeheader()
            writer.writerows(rows)
        print(f"   → {len(rows)} unique CDR-H3s\n")

    with CORPUS.open(encoding="utf-8") as fh:
        corpus = [r["cdrh3"] for r in csv.DictReader(fh)]

    gold = load_gold()
    if not gold:
        print("❌ no approved-antibody cohort — run scripts/build_antibody_benchmark.py")
        return 1

    # Held-out discipline: any corpus sequence identical to an approved CDR-H3
    # must not train the model that is then tested on it.
    held_out = set(gold)
    train = [s for s in corpus if s not in held_out]
    removed = len(corpus) - len(train)
    print(f"📚 corpus {len(corpus)} · removed {removed} overlapping with the test set · training on {len(train)}")

    model = CDRH3BigramModel.fit(train)
    model.save(MODEL_PATH)

    folds = cross_validate(train, folds=5)
    result = evaluate(model, gold)
    result["cross_validation_fold_means"] = [round(f, 4) for f in folds]
    result["corpus_size"] = len(corpus)
    result["removed_overlap"] = removed
    EVAL_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    shuf, rand = result["auc_vs_shuffled"], result["auc_vs_random"]
    print(f"\n🎯 留出集 AUC（已获批药 vs 其组分打乱）: {shuf['mean']:.3f} ± {shuf['stdev']:.3f}"
          f"  范围 {shuf['min']:.3f}–{shuf['max']:.3f}")
    print(f"   AUC（已获批药 vs 均匀随机）        : {rand['mean']:.3f} ± {rand['stdev']:.3f}")
    print(f"   现有组成型打分器在同一比较上       : 0.500（无判别力）")
    print(f"\n   真药平均分 {result['mean_score_real']:.3f} vs 打乱 {result['mean_score_shuffled']:.3f}")
    print(f"   5 折交叉验证各折均分: {result['cross_validation_fold_means']}")
    print("   最过表达的相邻残基对: " + ", ".join(f"{p}({v:+.2f},n={c})" for p, v, c in result["top_motifs"][:6]))

    for p in (MODEL_PATH, EVAL_PATH, CORPUS):
        print(f"✅ Wrote {p.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
