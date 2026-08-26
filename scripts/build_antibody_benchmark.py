#!/usr/bin/env python3
"""Build the antibody benchmark dataset → reports/antibody_benchmark_dataset.csv.

Two cohorts are assembled from the RCSB PDB:

* **gold** — approved therapeutic antibodies.  Each INN is used as a full-text
  query against the PDB; a hit is only accepted when the PDB's own
  ``pdbx_description`` names the drug.  The drug→structure mapping is therefore
  made by the PDB text index, never hard-coded from memory.
* **distribution** — a broad sample of antibody heavy chains, used to measure
  the real CDR-H3 length / aromatic-fraction distributions that the pipeline
  thresholds are calibrated against.

Raw API responses are cached under ``smoke_outputs/pdb_cache/`` (gitignored).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from biochat.eval.antibody_benchmark import (  # noqa: E402
    EXTRACTION_REFERENCES,
    SEARCH_URL,
    aromatic_fraction,
    extract_cdrh3,
    extraction_span,
    fetch_entities,
    is_plausible_cdrh3,
    search_antibody_entities,
    verify_extractor,
)

OUT_CSV = PROJECT_ROOT / "reports" / "antibody_benchmark_dataset.csv"
CACHE_DIR = PROJECT_ROOT / "smoke_outputs" / "pdb_cache"

FIELDNAMES = [
    "cohort",
    "drug",
    "pdb_entity",
    "chain_description",
    "chain_length",
    "cdrh3",
    "cdrh3_length",
    "aromatic_fraction",
    "extraction_start",
    "extraction_end",
    "n_structures",
    "n_agreeing",
]

# Approved therapeutic antibody INNs.  These are only *queries* — the accepted
# structure and its CDR-H3 always come back from the PDB, so a wrong or
# unstructured name simply yields no rows rather than a bad record.
APPROVED_INNS = [
    "trastuzumab", "bevacizumab", "rituximab", "adalimumab", "nivolumab",
    "pembrolizumab", "infliximab", "cetuximab", "ipilimumab", "ustekinumab",
    "tocilizumab", "omalizumab", "palivizumab", "natalizumab", "eculizumab",
    "denosumab", "ramucirumab", "atezolizumab", "durvalumab", "alemtuzumab",
    "panitumumab", "golimumab", "canakinumab", "secukinumab", "evolocumab",
    "alirocumab", "dupilumab", "mepolizumab", "daratumumab", "obinutuzumab",
    "ofatumumab", "pertuzumab", "vedolizumab", "belimumab", "basiliximab",
]


def _cached_get(url: str, cache_key: str, timeout: int = 40) -> dict:
    """GET ``url`` with an on-disk JSON cache keyed by ``cache_key``.

    The PDB search API answers a zero-hit query with ``204 No Content`` and an
    empty body, which is a valid answer rather than an error — it is cached and
    returned as ``{}``.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{cache_key}.json"
    if path.exists():
        return json.loads(path.read_text())
    with urllib.request.urlopen(url, timeout=timeout) as fh:
        body = fh.read()
    data = json.loads(body) if body.strip() else {}
    path.write_text(json.dumps(data))
    return data


def search_by_name(name: str, rows: int = 12) -> list[str]:
    """Return polymer-entity ids whose full text mentions ``name``."""
    payload = {
        "query": {"type": "terminal", "service": "full_text", "parameters": {"value": name}},
        "return_type": "polymer_entity",
        "request_options": {
            "paginate": {"start": 0, "rows": rows},
            "results_content_type": ["experimental"],
        },
    }
    url = f"{SEARCH_URL}?json={urllib.parse.quote(json.dumps(payload))}"
    try:
        data = _cached_get(url, f"search_{name}")
    except Exception as exc:  # noqa: BLE001 - network failure is reported, not fatal
        print(f"   ⚠️  {name}: search error ({type(exc).__name__})")
        return []
    return [hit["identifier"] for hit in data.get("result_set", [])]


def build_gold_cohort() -> list[dict]:
    """One row per approved antibody, confirmed by the PDB description text.

    A drug is frequently deposited several times.  Rather than trusting any
    single structure, the CDR-H3 is decided by **majority vote across
    independent entries**; the winning sequence and its agreement count are
    recorded.  This is what rejects contaminants such as ``7PKL_2``
    ("trastuzumab Light Chain VHH fusion"), whose extractable CDR-H3 belongs to
    the fused nanobody rather than to trastuzumab.
    """
    rows: list[dict] = []
    notes: list[str] = []

    for inn in APPROVED_INNS:
        entity_ids = search_by_name(inn)
        if not entity_ids:
            print(f"   ⏭️  {inn}: no PDB hits")
            continue

        records = fetch_entities(entity_ids)
        # Keep only chains whose own description names the drug and yields a CDR-H3.
        hits = []
        for eid, rec in sorted(records.items()):
            if inn not in rec["description"].lower():
                continue
            cdrh3 = extract_cdrh3(rec["sequence"])
            if is_plausible_cdrh3(cdrh3):
                hits.append((eid, rec, cdrh3))

        if not hits:
            print(f"   ⏭️  {inn}: no heavy chain with an extractable CDR-H3")
            continue

        tally = Counter(c for _, _, c in hits)
        (winner, n_agree), *rest = tally.most_common()
        if rest and rest[0][1] == n_agree:
            notes.append(f"{inn}: tie between {sorted(tally)} — excluded")
            print(f"   ⏭️  {inn}: no majority CDR-H3 across {len(hits)} structures")
            continue
        if rest:
            outliers = ", ".join(f"{seq}×{n}" for seq, n in rest)
            notes.append(f"{inn}: kept {winner}×{n_agree}, rejected {outliers}")

        eid, rec, _ = next(h for h in hits if h[2] == winner)
        span = extraction_span(rec["sequence"]) or (-1, -1)
        rows.append(
            {
                "cohort": "gold",
                "drug": inn,
                "pdb_entity": eid,
                "chain_description": rec["description"],
                "chain_length": len(rec["sequence"]),
                "cdrh3": winner,
                "cdrh3_length": len(winner),
                "aromatic_fraction": round(aromatic_fraction(winner), 4),
                "extraction_start": span[0],
                "extraction_end": span[1],
                "n_structures": len(hits),
                "n_agreeing": n_agree,
            }
        )
        print(f"   ✅ {inn}: {winner} ({len(winner)}aa, {n_agree}/{len(hits)} structures agree)")
        time.sleep(0.1)

    if notes:
        print("\n   ⚠️  majority-vote adjudications:")
        for n in notes:
            print(f"      {n}")
    return rows


def build_distribution_cohort(target: int = 400) -> list[dict]:
    """A broad sample of antibody heavy chains for distribution statistics."""
    entity_ids = search_antibody_entities(rows=target * 2)
    print(f"   search returned {len(entity_ids)} entities")
    records = fetch_entities(entity_ids)

    rows: list[dict] = []
    seen: set[str] = set()
    for eid, rec in sorted(records.items()):
        cdrh3 = extract_cdrh3(rec["sequence"])
        if not is_plausible_cdrh3(cdrh3) or cdrh3 in seen:
            continue
        seen.add(cdrh3)
        span = extraction_span(rec["sequence"]) or (-1, -1)
        rows.append(
            {
                "cohort": "distribution",
                "drug": "",
                "pdb_entity": eid,
                "chain_description": rec["description"],
                "chain_length": len(rec["sequence"]),
                "cdrh3": cdrh3,
                "cdrh3_length": len(cdrh3),
                "aromatic_fraction": round(aromatic_fraction(cdrh3), 4),
                "extraction_start": span[0],
                "extraction_end": span[1],
                "n_structures": 1,
                "n_agreeing": 1,
            }
        )
        if len(rows) >= target:
            break
    return rows


def print_fixture_block() -> int:
    """Emit the ``_REFERENCE_CHAINS`` literal from live PDB data, for pasting."""
    records = fetch_entities([eid for eid, _ in EXTRACTION_REFERENCES.values()])
    print("_REFERENCE_CHAINS: dict[str, str] = {")
    for name, (eid, _) in EXTRACTION_REFERENCES.items():
        seq = records[eid]["sequence"]
        print(f'    # {name} — "{records[eid]["description"]}"  (CDR-H3: {extract_cdrh3(seq)})')
        print(f'    "{eid}": (')
        for i in range(0, len(seq), 96):
            print(f'        "{seq[i : i + 96]}"')
        print("    ),")
    print("}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--distribution-size", type=int, default=400, help="distribution cohort target size")
    parser.add_argument("--gold-only", action="store_true", help="skip the distribution cohort")
    parser.add_argument("--refresh-fixtures", action="store_true", help="print the _REFERENCE_CHAINS literal and exit")
    args = parser.parse_args()

    if args.refresh_fixtures:
        return print_fixture_block()

    print("🔬 Verifying the CDR-H3 extractor against published references…")
    failures = verify_extractor()
    if failures:
        print("❌ extractor regression — refusing to build a dataset on a broken extractor:")
        for f in failures:
            print(f"   {f}")
        return 1
    print(f"   ✅ {len(EXTRACTION_REFERENCES)}/{len(EXTRACTION_REFERENCES)} reference CDR-H3s match\n")

    print("💊 Gold cohort — approved therapeutic antibodies")
    gold = build_gold_cohort()
    print(f"   → {len(gold)} antibodies\n")

    dist: list[dict] = []
    if not args.gold_only:
        print(f"📊 Distribution cohort — target {args.distribution_size} heavy chains")
        dist = build_distribution_cohort(args.distribution_size)
        print(f"   → {len(dist)} unique CDR-H3s\n")

    rows = gold + dist
    if not rows:
        print("❌ no rows collected")
        return 1

    OUT_CSV.parent.mkdir(exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Wrote {OUT_CSV.relative_to(PROJECT_ROOT)} ({len(gold)} gold + {len(dist)} distribution)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
