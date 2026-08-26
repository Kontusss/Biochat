"""Retrospective benchmark helpers — validate the antibody pipeline against approved drugs.

The antibody scoring path (``generation_filter`` → ``scoring``) is a
*developability / liability* filter, not a binding predictor.  The only
scientifically valid retrospective question is therefore:

    Does the filter reject antibodies that are already approved drugs?

Approved therapeutics are ground truth for "manufacturable and developable",
so a filter that rejects them is mis-calibrated.  This module provides the
data-side primitives (CDRH3 extraction, PDB fetching, decoy construction,
distribution statistics); the runner scripts live in ``scripts/``.

Pure stdlib.  Network access is confined to :func:`fetch_entities` and
:func:`search_antibody_entities`; everything else runs offline.
"""

from __future__ import annotations

import json
import random
import re
import urllib.parse
import urllib.request
from collections import Counter
from typing import Any, Iterable, Sequence

GRAPHQL_URL = "https://data.rcsb.org/graphql"
SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"

VALID_AAS = "ACDEFGHIKLMNPQRSTVWY"

# ═══════════════════════════════════════════════════════════════════
# CDRH3 extraction
# ═══════════════════════════════════════════════════════════════════

# Kabat CDR-H3 is bounded by two highly conserved anchors:
#   * the second conserved Cys of the VH domain (Kabat H92), followed by
#     exactly two residues (the "AR"/"AK"/"SR"/"AT"… position 93-94), and
#   * the FR4 motif W-G-x-G (Kabat H103-H106).
# The capture between them is CDR-H3 by the Kabat definition.
_CDRH3_RE = re.compile(r"C[A-Z]{2}([A-Z]{1,32}?)WG[QKRGAES]G")

# The conserved Cys sits near residue 92 of the VH domain.  Fab heavy chains
# in the PDB also contain CH1, which can harbour spurious C..WGxG matches, so
# candidate matches are restricted to a window around the expected position.
_CYS_WINDOW = (70, 130)

# Published Kabat CDR-H3 sequences used as regression fixtures for the
# extractor.  Each was cross-checked against the sequence independently
# obtained from the cited PDB entry — the two agree character-for-character.
# If the extraction rule is ever changed, these assertions fail first.
EXTRACTION_REFERENCES: dict[str, tuple[str, str]] = {
    # name: (pdb_entity, expected Kabat CDR-H3)
    "Trastuzumab": ("1N8Z_2", "WGGDGFYAMDY"),
    "Bevacizumab": ("1BJ1_2", "YPHYYGSSHWYFDV"),
    "Rituximab": ("2OSL_2", "STYYGGDWYFNV"),
    "Adalimumab": ("3WD5_3", "VSYLSTASSLDY"),
}


def extract_cdrh3(sequence: str) -> str | None:
    """Return the Kabat CDR-H3 of an antibody heavy chain, or ``None``.

    Uses the conserved ``C-x-x … WG[QKRGAES]G`` anchors.  Among matches whose
    anchoring Cys falls inside :data:`_CYS_WINDOW`, the last is returned;
    this avoids matching into the CH1 domain of a Fab construct while still
    tolerating unusually long CDR-H1/H2 loops that shift the VH numbering.
    """
    seq = (sequence or "").strip().upper()
    if not seq:
        return None

    in_window = [m for m in _CDRH3_RE.finditer(seq) if _CYS_WINDOW[0] <= m.start() <= _CYS_WINDOW[1]]
    matches = in_window or list(_CDRH3_RE.finditer(seq))
    if not matches:
        return None
    return matches[-1].group(1)


def extraction_span(sequence: str) -> tuple[int, int] | None:
    """Return the ``(start, end)`` offsets of the extracted CDR-H3, for provenance."""
    seq = (sequence or "").strip().upper()
    if not seq:
        return None
    in_window = [m for m in _CDRH3_RE.finditer(seq) if _CYS_WINDOW[0] <= m.start() <= _CYS_WINDOW[1]]
    matches = in_window or list(_CDRH3_RE.finditer(seq))
    if not matches:
        return None
    return matches[-1].span(1)


def verify_extractor() -> list[str]:
    """Check the extractor against :data:`EXTRACTION_REFERENCES` using offline fixtures.

    Returns a list of failure descriptions; empty means all references matched.
    Callers that have network access should prefer
    :func:`verify_extractor_online`, which re-derives the chains from the PDB.
    """
    failures = []
    for name, (entity, expected) in EXTRACTION_REFERENCES.items():
        fixture = _REFERENCE_CHAINS.get(entity)
        if fixture is None:
            failures.append(f"{name}: no offline fixture for {entity}")
            continue
        got = extract_cdrh3(fixture)
        if got != expected:
            failures.append(f"{name} ({entity}): expected {expected!r}, got {got!r}")
    return failures


def verify_extractor_online() -> list[str]:
    """Re-fetch the reference chains from the PDB and re-run the extractor."""
    entities = fetch_entities([e for e, _ in EXTRACTION_REFERENCES.values()])
    failures = []
    for name, (entity, expected) in EXTRACTION_REFERENCES.items():
        rec = entities.get(entity)
        if rec is None:
            failures.append(f"{name}: {entity} not returned by PDB")
            continue
        got = extract_cdrh3(rec["sequence"])
        if got != expected:
            failures.append(f"{name} ({entity}): expected {expected!r}, got {got!r}")
    return failures


# Offline fixtures for the reference antibodies, so the extractor can be
# regression-tested without network access.  These are the canonical
# one-letter SEQRES of the cited PDB polymer entity, retrieved verbatim from
# the RCSB GraphQL API — never transcribed by hand.  Regenerate with:
#     python scripts/build_antibody_benchmark.py --refresh-fixtures
_REFERENCE_CHAINS: dict[str, str] = {
    # Trastuzumab — "Herceptin Fab (antibody) - heavy chain"  (CDR-H3: WGGDGFYAMDY)
    "1N8Z_2": (
        "EVQLVESGGGLVQPGGSLRLSCAASGFNIKDTYIHWVRQAPGKGLEWVARIYPTNGYTRYADSVKGRFTISADTSKNTAYLQMNSLRAEDTAVYYC"
        "SRWGGDGFYAMDYWGQGTLVTVSSASTKGPSVFPLAPSSKSTSGGTAALGCLVKDYFPEPVTVSWNSGALTSGVHTFPAVLQSSGLYSLSSVVTVP"
        "SSSLGTQTYICNVNHKPSNTKVDKKVEP"
    ),
    # Bevacizumab — "Fab fragment, heavy chain"  (CDR-H3: YPHYYGSSHWYFDV)
    "1BJ1_2": (
        "EVQLVESGGGLVQPGGSLRLSCAASGYTFTNYGMNWVRQAPGKGLEWVGWINTYTGEPTYAADFKRRFTFSLDTSKSTAYLQMNSLRAEDTAVYYC"
        "AKYPHYYGSSHWYFDVWGQGTLVTVSSASTKGPSVFPLAPSSKSTSGGTAALGCLVKDYFPEPVTVSWNSGALTSGVHTFPAVLQSSGLYSLSSVV"
        "TVPSSSLGTQTYICNVNHKPSNTKVDKKVEPKSCDKTHT"
    ),
    # Rituximab — "heavy chain of the Rituximab Fab fragment"  (CDR-H3: STYYGGDWYFNV)
    "2OSL_2": (
        "QVQLQQPGAELVKPGASVKMSCKASGYTFTSYNMHWVKQTPGRGLEWIGAIYPGNGDTSYNQKFKGKATLTADKSSSTAYMQLSSLTSEDSAVYYC"
        "ARSTYYGGDWYFNVWGAGTTVTVSAASTKGPSVFPLAPSSKSTSGGTAALGCLVKDYFPEPVTVSWNSGALTSGVHTFPAVLQSSGLYSLSSVVTV"
        "PSSSLGTQTYICNVNHKPSNTKVDKKVEPKSC"
    ),
    # Adalimumab — "Adalimumab Heavy Chain"  (CDR-H3: VSYLSTASSLDY)
    "3WD5_3": (
        "EVQLVESGGGLVQPGRSLRLSCAASGFTFDDYAMHWVRQAPGKGLEWVSAITWNSGHIDYADSVEGRFTISRDNAKNSLYLDMNSLRAEDTAVYYC"
        "AKVSYLSTASSLDYWGQGTLVTVSSASTKGPSVFPLAPSSKSTSGGTAALGCLVKDYFPEPVTVSWNSGALTSGVHTFPAVLQSSGLYSLSSVVTV"
        "PSSSLGTQTYICNVNHKPSNTKVDKKI"
    ),
}


# ═══════════════════════════════════════════════════════════════════
# PDB access
# ═══════════════════════════════════════════════════════════════════


def _post_json(url: str, payload: dict, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return json.load(fh)


def fetch_entities(entity_ids: Sequence[str], batch_size: int = 50, timeout: int = 30) -> dict[str, dict]:
    """Fetch polymer-entity sequences from the PDB GraphQL API.

    Args:
        entity_ids: ``"<PDB_ID>_<ENTITY_ID>"`` identifiers, e.g. ``"1N8Z_2"``.

    Returns:
        ``{rcsb_id: {"description": str, "sequence": str}}``.

    The API does **not** preserve request order, so results are indexed by the
    ``rcsb_id`` each record reports rather than by request position.
    """
    out: dict[str, dict] = {}
    ids = list(entity_ids)
    for start in range(0, len(ids), batch_size):
        chunk = ids[start : start + batch_size]
        query = (
            "{polymer_entities(entity_ids:%s){rcsb_id "
            "rcsb_polymer_entity{pdbx_description} "
            "entity_poly{pdbx_seq_one_letter_code_can}}}" % json.dumps(chunk)
        )
        data = _post_json(GRAPHQL_URL, {"query": query}, timeout=timeout)
        for rec in (data.get("data") or {}).get("polymer_entities") or []:
            if not rec:
                continue
            entity = (rec.get("rcsb_polymer_entity") or {}).get("pdbx_description") or ""
            seq = (rec.get("entity_poly") or {}).get("pdbx_seq_one_letter_code_can") or ""
            out[rec["rcsb_id"]] = {"description": entity, "sequence": seq.strip().upper()}
    return out


def search_antibody_entities(rows: int = 400, timeout: int = 40) -> list[str]:
    """Return polymer-entity ids for antibody heavy chains via the PDB search API."""
    payload = {
        "query": {
            "type": "group",
            "logical_operator": "and",
            "nodes": [
                {
                    "type": "terminal",
                    "service": "full_text",
                    "parameters": {"value": "immunoglobulin Fab heavy chain"},
                },
                {
                    "type": "terminal",
                    "service": "text",
                    "parameters": {
                        "attribute": "entity_poly.rcsb_entity_polymer_type",
                        "operator": "exact_match",
                        "value": "Protein",
                    },
                },
            ],
        },
        "return_type": "polymer_entity",
        "request_options": {
            "paginate": {"start": 0, "rows": rows},
            "results_content_type": ["experimental"],
        },
    }
    url = f"{SEARCH_URL}?json={urllib.parse.quote(json.dumps(payload))}"
    with urllib.request.urlopen(url, timeout=timeout) as fh:
        data = json.load(fh)
    return [hit["identifier"] for hit in data.get("result_set", [])]


# ═══════════════════════════════════════════════════════════════════
# Decoys
# ═══════════════════════════════════════════════════════════════════


def shuffled_decoys(sequences: Iterable[str], seed: int = 42) -> list[str]:
    """Composition-matched decoys: same amino-acid multiset, scrambled order.

    This is the controlled comparison — any score difference against these
    cannot be attributed to amino-acid composition alone.
    """
    rng = random.Random(seed)
    out = []
    for seq in sequences:
        chars = list(seq)
        for _ in range(8):  # re-draw if the shuffle reproduces the input
            rng.shuffle(chars)
            if "".join(chars) != seq:
                break
        out.append("".join(chars))
    return out


def random_decoys(lengths: Iterable[int], seed: int = 42) -> list[str]:
    """Length-matched decoys drawn uniformly from the canonical amino acids."""
    rng = random.Random(seed + 1)
    return ["".join(rng.choice(VALID_AAS) for _ in range(n)) for n in lengths]


# ═══════════════════════════════════════════════════════════════════
# Distribution statistics
# ═══════════════════════════════════════════════════════════════════


def percentile(values: Sequence[float], pct: float) -> float:
    """Linear-interpolated percentile (``pct`` in 0-100). Empty input returns 0.0."""
    vals = sorted(float(v) for v in values)
    if not vals:
        return 0.0
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * (pct / 100.0)
    low = int(pos)
    high = min(low + 1, len(vals) - 1)
    frac = pos - low
    return vals[low] * (1 - frac) + vals[high] * frac


def aromatic_fraction(seq: str) -> float:
    """Fraction of F/W/Y residues — the quantity ``generation_filter`` thresholds on."""
    if not seq:
        return 0.0
    return sum(1 for c in seq if c in "FWY") / len(seq)


def describe(values: Sequence[float]) -> dict[str, float]:
    """P5 / P25 / P50 / P75 / P95 plus mean, min, max."""
    vals = [float(v) for v in values]
    if not vals:
        return {k: 0.0 for k in ("n", "mean", "min", "p5", "p25", "p50", "p75", "p95", "max")}
    return {
        "n": float(len(vals)),
        "mean": sum(vals) / len(vals),
        "min": min(vals),
        "p5": percentile(vals, 5),
        "p25": percentile(vals, 25),
        "p50": percentile(vals, 50),
        "p75": percentile(vals, 75),
        "p95": percentile(vals, 95),
        "max": max(vals),
    }


def mann_whitney_u(a: Sequence[float], b: Sequence[float]) -> tuple[float, float]:
    """Mann-Whitney U and the common-language effect size ``AUC = U / (n_a * n_b)``.

    ``AUC`` is the probability that a random draw from ``a`` exceeds one from
    ``b`` (0.5 = no discrimination).  Ties contribute 0.5.  Pure stdlib, no scipy.
    """
    if not a or not b:
        return 0.0, 0.5
    wins = 0.0
    for x in a:
        for y in b:
            if x > y:
                wins += 1.0
            elif x == y:
                wins += 0.5
    return wins, wins / (len(a) * len(b))


def flag_frequency(flag_lists: Iterable[Sequence[str]]) -> list[tuple[str, int]]:
    """Count how often each filter flag fires, most frequent first."""
    counter: Counter[str] = Counter()
    for flags in flag_lists:
        counter.update(flags)
    return counter.most_common()


def normalise_flag(flag: str) -> str:
    """Collapse the dynamic ``high_single_<AA>_fraction`` flags into one family."""
    return re.sub(r"^high_single_[A-Z]_fraction$", "high_single_aa_fraction", flag)


def is_plausible_cdrh3(seq: Any) -> bool:
    """True if ``seq`` looks like a usable CDR-H3 (canonical residues, sane length)."""
    if not isinstance(seq, str) or not seq:
        return False
    return 3 <= len(seq) <= 40 and all(c in VALID_AAS for c in seq)
