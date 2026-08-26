"""Order-sensitive CDR-H3 scoring — a composition-controlled bigram model.

The pipeline's existing liability score is a pure function of amino-acid
*composition* (length, aromatic fraction, charge counts).  Shuffling a CDR-H3
preserves composition, so that score cannot tell a real therapeutic antibody
from a scramble of its own residues — measured AUC 0.5, see
``reports/antibody_benchmark_report.md``.

This module adds the missing axis.  It scores residue **adjacency** against
what composition alone would predict:

    score(s) = mean_i  log[ P(s_i s_{i+1}) / (P(s_i) · P(s_{i+1})) ]

That ratio is pointwise mutual information.  It is zero when residues are
arranged independently, so a shuffled sequence — which keeps every unigram
frequency but destroys adjacency — scores near zero by construction.  The
quantity is therefore composition-controlled *by design* rather than by
after-the-fact normalisation.

The model is trained on antibody CDR-H3s and is **not** a developability
score: it answers "does this look like a real antibody loop", not "is this
manufacturable" and certainly not "does this bind".  Never report it as an
affinity, ΔG, or Kd.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Iterable, Sequence

AAS = "ACDEFGHIKLMNPQRSTVWY"

# Add-alpha smoothing.  With 400 bigram cells and a corpus of order 10^4
# observations many cells are legitimately unseen; alpha=0.5 (Jeffreys) keeps
# their log-odds finite without swamping the observed counts.
DEFAULT_ALPHA = 0.5

MIN_LENGTH = 2  # a bigram model needs at least one adjacent pair


class CDRH3BigramModel:
    """Composition-controlled adjacency model over CDR-H3 sequences."""

    def __init__(
        self,
        unigram: dict[str, float],
        bigram: dict[str, float],
        n_train: int = 0,
        alpha: float = DEFAULT_ALPHA,
        bigram_counts: dict[str, int] | None = None,
    ):
        self.unigram = unigram
        self.bigram = bigram
        self.n_train = n_train
        self.alpha = alpha
        # Raw counts are retained so callers can tell a well-supported motif
        # from one whose log-odds are an artefact of add-alpha smoothing.
        self.bigram_counts = bigram_counts or {}

    # ── training ────────────────────────────────────────────────
    @classmethod
    def fit(cls, sequences: Iterable[str], alpha: float = DEFAULT_ALPHA) -> "CDRH3BigramModel":
        seqs = [s.strip().upper() for s in sequences if s and len(s.strip()) >= MIN_LENGTH]
        uni: Counter[str] = Counter()
        bi: Counter[str] = Counter()
        for seq in seqs:
            uni.update(c for c in seq if c in AAS)
            bi.update(seq[i : i + 2] for i in range(len(seq) - 1) if seq[i] in AAS and seq[i + 1] in AAS)

        total_u = sum(uni.values())
        total_b = sum(bi.values())
        unigram = {a: (uni[a] + alpha) / (total_u + alpha * len(AAS)) for a in AAS}
        bigram = {a + b: (bi[a + b] + alpha) / (total_b + alpha * len(AAS) ** 2) for a in AAS for b in AAS}
        return cls(unigram, bigram, len(seqs), alpha, {k: v for k, v in bi.items() if v})

    # ── scoring ─────────────────────────────────────────────────
    def score(self, sequence: str) -> float:
        """Mean pointwise mutual information across adjacent residue pairs.

        Returns 0.0 for sequences too short to contain a pair, and skips pairs
        containing a non-canonical residue.
        """
        seq = (sequence or "").strip().upper()
        pairs = [seq[i : i + 2] for i in range(len(seq) - 1)]
        usable = [p for p in pairs if p[0] in AAS and p[1] in AAS]
        if not usable:
            return 0.0
        total = sum(
            math.log(self.bigram[p] / (self.unigram[p[0]] * self.unigram[p[1]])) for p in usable
        )
        return total / len(usable)

    def score_many(self, sequences: Iterable[str]) -> list[float]:
        return [self.score(s) for s in sequences]

    # ── persistence ─────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "model": "cdrh3_bigram_pmi",
            "version": 1,
            "alpha": self.alpha,
            "n_train": self.n_train,
            "unigram": self.unigram,
            "bigram": self.bigram,
            "bigram_counts": self.bigram_counts,
        }

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str | Path) -> "CDRH3BigramModel":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("model") != "cdrh3_bigram_pmi":
            raise ValueError(f"not a CDR-H3 bigram model: {data.get('model')!r}")
        return cls(
            data["unigram"],
            data["bigram"],
            data.get("n_train", 0),
            data.get("alpha", DEFAULT_ALPHA),
            data.get("bigram_counts", {}),
        )


def top_motifs(model: CDRH3BigramModel, n: int = 12, min_count: int = 50) -> list[tuple[str, float, int]]:
    """Residue pairs the model finds over-represented, filtered by support.

    ``min_count`` is not cosmetic.  With add-alpha smoothing a pair seen 4 times
    can outrank one seen 400 times: on a 1.3k-sequence corpus ``CC`` (n=4) and
    ``QQ`` (n=6) both surface above ``DY`` (n=704) without it.  Only pairs with
    real support are reported, which is what leaves the canonical
    J-segment C-terminal motifs (``MD``, ``FD``, ``DY``, ``DV``, ``AM`` — the
    ``…AMDY`` / ``…FDY`` / ``…FDV`` endings) at the top.
    """
    scored = [
        (pair, math.log(model.bigram[pair] / (model.unigram[pair[0]] * model.unigram[pair[1]])), count)
        for pair, count in model.bigram_counts.items()
        if count >= min_count
    ]
    return sorted(scored, key=lambda kv: kv[1], reverse=True)[:n]


def cross_validate(sequences: Sequence[str], folds: int = 5, alpha: float = DEFAULT_ALPHA) -> list[float]:
    """Per-fold held-out mean score, to check the model is not memorising.

    Sequences are partitioned deterministically by index (no RNG, so results are
    reproducible); each fold trains on the rest and scores its own held-out set.
    """
    seqs = [s for s in sequences if len(s) >= MIN_LENGTH]
    if folds < 2 or len(seqs) < folds:
        return []
    out = []
    for k in range(folds):
        test = [s for i, s in enumerate(seqs) if i % folds == k]
        train = [s for i, s in enumerate(seqs) if i % folds != k]
        model = CDRH3BigramModel.fit(train, alpha=alpha)
        scores = model.score_many(test)
        out.append(sum(scores) / len(scores) if scores else 0.0)
    return out
