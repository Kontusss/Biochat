#!/usr/bin/env python3
"""Similarity-reduction candidate scan — upstream footprint by payoff.

For every tracked Python file, computes:

- line-level similarity against the vendored upstream reference
  (``third_party/biomni_upstream_reference/``);
- usage counts by class (runtime / test / demo / legacy_internal)
  reusing the import audit in ``scripts/audit_import_usage.py``;
- a category + recommendation + estimated line reduction.

Output: reports/similarity_reduction_candidates.csv (sorted by
``matched_lines`` descending).

Categories:
    unused_upstream              no importers at all
    legacy_script                only demo/script importers
    static_catalog               static dict/list descriptors (env/data/tool)
    runtime_adapter_candidate    runtime-used, logic-heavy, high similarity
    runtime_core_dependency      runtime-used but already rewritten / data
    test_only                    only tests import it
    third_party_keep             lives under third_party/ (baseline only)

Usage:
    python scripts/audit_similarity_reduction.py
"""

from __future__ import annotations

import csv
import difflib
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT))

from audit_import_usage import (  # noqa: E402
    EXCLUDE_DIRS,
    classify_importer,
    module_name,
    target_patterns,
)


def dynamically_registered(rel_path: str) -> bool:
    """True if the module is pulled in at runtime via importlib by the tool
    registry (``read_module2api`` imports ``biomni.tool.tool_description.*``
    and ``api_schema_to_langchain_tool`` imports ``biomni.tool.*``)."""
    try:
        from biomni.utils.io_utils import _TOOL_FIELDS
    except ImportError:
        return False
    parts = Path(rel_path).parts
    if len(parts) < 3 or parts[0] != "biomni" or parts[1] != "tool":
        return False
    stem = parts[2].removesuffix(".py")
    if parts[2] == "tool_description" and len(parts) >= 4:
        stem = parts[3].removesuffix(".py")
    return stem in _TOOL_FIELDS

UPSTREAM_REF = PROJECT_ROOT / "third_party" / "biomni_upstream_reference"
OUT_PATH = PROJECT_ROOT / "reports" / "similarity_reduction_candidates.csv"

MIN_SIMILARITY = 0.5          # below this the file is "already rewritten"
ADAPTER_SIMILARITY = 0.9      # at/above this, runtime files are adapter candidates

_STATIC_CATALOG_NAMES = {"env_desc.py", "env_desc_cm.py"}


def norm_lines(path: Path) -> list[str]:
    text = path.read_text(errors="ignore")
    return [ln.rstrip() for ln in text.splitlines() if ln.strip()]


def similarity(a: list[str], b: list[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def usage_counts(rel_path: str, all_files: list[Path]) -> dict[str, list[str]]:
    """Return importer rel-paths by class (runtime / test / demo).

    Detects direct imports, relative imports from the same package, and
    package re-exports (``from biomni.pkg import name`` where
    ``biomni/pkg/__init__.py`` re-exports the module).
    """
    importers = {"runtime": [], "test": [], "demo": []}
    target = str(rel_path)
    same_dir = Path(target).parent
    mod = module_name(target)
    stem = Path(target).stem

    # Package re-export detection: biomni/pkg/__init__.py re-exports stem
    init_file = same_dir / "__init__.py"
    reexport = False
    if init_file.exists():
        init_src = init_file.read_text(errors="ignore")
        reexport = bool(
            re.search(rf"^\s*from\s+\.\s*{re.escape(stem)}\s+import", init_src, re.MULTILINE)
            or re.search(rf"^\s*from\s+{re.escape(mod)}\s+import", init_src, re.MULTILINE)
        )
    pkg_pattern = (
        re.compile(rf"^\s*from\s+{re.escape(mod.rsplit('.', 1)[0])}\s+import", re.MULTILINE)
        if reexport else None
    )

    for py_file in all_files:
        if str(py_file.relative_to(PROJECT_ROOT)) == target:
            continue  # don't count the file itself
        source = py_file.read_text(errors="ignore")
        found = False
        for pattern in target_patterns(target, py_file.parent == same_dir):
            if pattern.search(source):
                found = True
                break
        if not found and pkg_pattern is not None and pkg_pattern.search(source):
            found = True
        if not found:
            continue
        p = str(py_file.relative_to(PROJECT_ROOT))
        # Path-based class only; legacy_internal is derived in scan()
        kind = classify_importer(py_file.relative_to(PROJECT_ROOT), set())
        if kind == "legacy_internal":
            kind = "runtime"
        importers[kind].append(p)
    return importers


def categorise(rel_path: str, sim: float, counts: dict[str, int]) -> tuple[str, str]:
    """Return (category, recommendation) for one shared file."""
    r, t, d = counts["runtime"], counts["test"], counts["demo"]
    name = Path(rel_path).name
    dynamic = dynamically_registered(rel_path)

    # Package __init__ / version files are structural — never archived.
    if name == "__init__.py" or rel_path == "biomni/version.py":
        return ("runtime_core_dependency", "keep_with_attribution")
    if dynamic:
        # Tool registry modules — always runtime-used.  Descriptions are
        # static catalogs (configurize); implementations are core tooling.
        if "tool_description" in rel_path:
            return ("static_catalog", "configurize")
        return ("runtime_core_dependency", "keep_with_attribution")
    if r == 0 and t == 0 and d == 0:
        return ("unused_upstream", "archive")
    if r == 0 and d > 0 and t == 0:
        return ("legacy_script", "archive")
    if r == 0 and t > 0:
        return ("test_only", "keep_with_attribution")
    if name in _STATIC_CATALOG_NAMES:
        return ("static_catalog", "configurize")
    if sim >= ADAPTER_SIMILARITY:
        return ("runtime_adapter_candidate", "replace_with_adapter")
    return ("runtime_core_dependency", "keep_with_attribution")


def risk_level(counts: dict[str, int], sim: float) -> str:
    if counts["runtime"] == 0:
        return "low"
    if counts["runtime"] >= 3:
        return "high"
    return "medium"


def scan() -> list[dict]:
    upstream_files = {
        f.relative_to(UPSTREAM_REF): f
        for f in UPSTREAM_REF.rglob("*.py")
        if "__pycache__" not in f.parts
    }
    repo_files = [
        f for f in sorted(PROJECT_ROOT.rglob("*.py"))
        if not any(part in EXCLUDE_DIRS for part in f.relative_to(PROJECT_ROOT).parts)
        and f.parts  # ignore empty
    ]
    # Only repo files that have an upstream counterpart matter here
    shared_paths = {str(f.relative_to(PROJECT_ROOT)) for f in repo_files
                    if f.relative_to(PROJECT_ROOT) in upstream_files}

    # ── Pass 1: line counts, similarity, importer lists ─────────
    line_counts: dict[str, int] = {}
    sims: dict[str, float] = {}
    importer_map: dict[str, dict[str, list[str]]] = {}
    for py_file in repo_files:
        rel = str(py_file.relative_to(PROJECT_ROOT))
        if rel.startswith("third_party/"):
            continue
        if rel not in shared_paths:
            continue
        lines = norm_lines(py_file)
        line_counts[rel] = len(lines)
        sims[rel] = similarity(lines, norm_lines(upstream_files[Path(rel)]))
        if sims[rel] < MIN_SIMILARITY:
            continue
        importer_map[rel] = usage_counts(rel, repo_files)

    # ── Pass 2: derive legacy_internal + final counts ───────────
    # A shared file is "legacy" (not live runtime) when nothing outside the
    # legacy cluster imports it: runtime usage = static runtime importers
    # whose own runtime usage > 0, plus dynamic tool-registry registration.
    rows = []
    for rel, sim in sims.items():
        if sim < MIN_SIMILARITY:
            continue
        importers = importer_map[rel]
        dynamic = dynamically_registered(rel)

        # An importer is legacy-internal iff it is a shared (upstream-similar)
        # file whose own runtime importers are all shared files (i.e. it is
        # part of the legacy cluster, not reached from Biochat code) and it
        # is not dynamically registered by the tool registry.
        def _legacy(p: str) -> bool:
            if p not in shared_paths:
                return False
            # Already-rewritten files are Biochat originals — always live
            if sims.get(p, 0.0) < MIN_SIMILARITY:
                return False
            if dynamically_registered(p):
                return False
            own_importers = importer_map.get(p, {}).get("runtime", [])
            return all(i in shared_paths for i in own_importers)

        counts = {"runtime": 0, "test": 0, "demo": 0, "legacy_internal": 0}
        for imp in importers.get("runtime", []):
            counts["legacy_internal" if _legacy(imp) else "runtime"] += 1
        counts["test"] = len(importers.get("test", []))
        counts["demo"] = len(importers.get("demo", []))
        if dynamic:
            counts["runtime"] += 1  # importlib-based tool registry usage
        category, recommendation = categorise(rel, sim, counts)
        matched = int(line_counts[rel] * sim)
        estimated = matched if recommendation in ("archive", "configurize",
                                                  "replace_with_adapter") else 0
        rows.append({
            "path": rel,
            "line_count": line_counts[rel],
            "similarity": round(sim, 3),
            "matched_lines": matched,
            "runtime_used_by_count": counts["runtime"],
            "test_used_by_count": counts["test"],
            "demo_used_by_count": counts["demo"],
            "legacy_internal_used_by_count": counts["legacy_internal"],
            "category": category,
            "recommendation": recommendation,
            "estimated_reduction": estimated,
            "risk": risk_level(counts, sim),
        })
    rows.sort(key=lambda x: -x["matched_lines"])
    return rows


def main() -> int:
    rows = scan()
    OUT_PATH.parent.mkdir(exist_ok=True)
    fields = [
        "path", "line_count", "similarity", "matched_lines",
        "runtime_used_by_count", "test_used_by_count", "demo_used_by_count",
        "legacy_internal_used_by_count", "category", "recommendation",
        "estimated_reduction", "risk",
    ]
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    total_matched = sum(r["matched_lines"] for r in rows)
    reducible = sum(r["estimated_reduction"] for r in rows)
    print(f"{len(rows)} shared files, {total_matched} matched lines, "
          f"{reducible} reducible")
    for r in rows[:20]:
        print(f"{r['recommendation']:<22} {r['category']:<26} "
              f"{r['similarity']*100:5.1f}% {r['matched_lines']:>6}L "
              f"r={r['runtime_used_by_count']} t={r['test_used_by_count']} "
              f"d={r['demo_used_by_count']}  {r['path']}")
    print(f"\nWrote {OUT_PATH.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
