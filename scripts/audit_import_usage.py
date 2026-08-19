#!/usr/bin/env python3
"""Upstream footprint audit — who actually imports the legacy upstream modules?

Scans every Python file in the repository for imports of the audited
upstream modules and classifies each usage:

- ``runtime``         — imported from the biochat package (the live agent path)
- ``test``            — imported from tests/
- ``demo``            — imported from scripts/ / examples/ / tutorials/
- ``legacy_internal`` — imported by another audited module (self-referencing
                        cluster, e.g. biorxiv_scripts -> env_collection)

Recommendation rules:
- no usage, or only demo/legacy-internal usage  -> ``archive_to_third_party``
- runtime usage                                 -> ``keep_with_attribution``
- runtime usage, module slated for replacement  -> ``replace_with_adapter``

Output: reports/upstream_usage_audit.csv

Usage:
    python scripts/audit_import_usage.py [--verbose]
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ── Audited upstream targets ──────────────────────────────────────────
AUDIT_TARGETS: list[str] = [
    "biomni/biorxiv_scripts/",
    "biomni/eval/biomni_eval1.py",
    "biomni/agent/react.py",
    "biomni/know_how/loader.py",
    "biomni/agent/env_collection.py",
    "biomni/env_desc.py",
    "biomni/env_desc_cm.py",
    # Additional finding: upstream agent helper only used by biorxiv_scripts
    "biomni/agent/function_generator.py",
]

# Targets slated for architectural replacement instead of archiving.
# ``react.py`` was archived directly (audit found zero importers, so no
# adapter was required); ``know_how/loader.py`` now delegates to
# ``biochat/knowledge`` — the legacy path is an active adapter.
REPLACE_TARGETS: set[str] = {
    "biomni/know_how/loader.py",
}

EXCLUDE_DIRS = {"__pycache__", ".git", "third_party", ".venv", "venv", "node_modules"}


def module_name(path: str) -> str:
    """'biochat/agent/react.py' -> 'biochat.agent.react'"""
    return path.replace("/", ".").removesuffix(".py")


def target_patterns(target: str, same_dir: bool) -> list[re.Pattern]:
    """Regexes matching any import statement that pulls in the target.

    Covers absolute imports and, when the importer lives in the same
    package, relative imports (e.g. ``from .biochat_eval1 import ...``).
    """
    if target.endswith("/"):
        base = "biochat." + target.strip("/").replace("/", ".")
        return [
            re.compile(rf"^\s*(from|import)\s+{re.escape(base)}(\.|$|\s)", re.MULTILINE),
        ]
    mod = module_name(target)
    stem = Path(target).stem
    patterns = [
        re.compile(rf"^\s*from\s+{re.escape(mod)}\s+import", re.MULTILINE),
        re.compile(rf"^\s*import\s+{re.escape(mod)}\b", re.MULTILINE),
    ]
    if same_dir:
        patterns += [
            re.compile(rf"^\s*from\s+\.\s*{re.escape(stem)}\s+import", re.MULTILINE),
            re.compile(rf"^\s*from\s+\.\s+import\s+[^\n]*\b{re.escape(stem)}\b", re.MULTILINE),
        ]
    # 'from biochat.know_how import KnowHowLoader' hits know_how/__init__,
    # which re-exports loader — count the package import too.
    if target.endswith("loader.py"):
        patterns.append(
            re.compile(rf"^\s*from\s+{re.escape(mod.rsplit('.', 1)[0])}\s+import", re.MULTILINE)
        )
    return patterns


def classify_importer(rel_path: Path, targets: set[str]) -> str:
    """Classify a file that imports an audited target."""
    p = str(rel_path)
    if p in targets or any(p.startswith(t) for t in targets if t.endswith("/")):
        return "legacy_internal"
    # The package __init__ that (re-)exports a file target
    if any(p == str(Path(t).parent / "__init__.py") for t in targets if not t.endswith("/")):
        return "legacy_internal"
    if p.startswith("tests/") or p.endswith("_test.py") or p.startswith("test_"):
        return "test"
    if p.startswith(("scripts/", "examples/", "tutorials/")):
        return "demo"
    return "runtime"


def scan() -> list[dict]:
    targets = set(AUDIT_TARGETS)
    importers: dict[str, list[tuple[str, str]]] = {t: [] for t in AUDIT_TARGETS}

    for py_file in sorted(PROJECT_ROOT.rglob("*.py")):
        rel = py_file.relative_to(PROJECT_ROOT)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        source = py_file.read_text(errors="ignore")
        for target in AUDIT_TARGETS:
            if str(rel) == target:
                continue
            same_dir = not target.endswith("/") and rel.parent == Path(target).parent
            for pattern in target_patterns(target, same_dir):
                if pattern.search(source):
                    kind = classify_importer(rel, targets)
                    importers[target].append((str(rel), kind))
                    break  # one match per target is enough

    rows = []
    for target in AUDIT_TARGETS:
        usages = sorted(set(importers[target]))
        kinds = {k for _, k in usages}
        runtime_used = "runtime" in kinds
        if target in REPLACE_TARGETS:
            # Replaced targets: still needed at runtime -> replace; otherwise
            # the replacement is complete and the legacy path is an adapter.
            rec = "replace_with_adapter" if runtime_used else "adapter_active"
        elif not usages or kinds <= {"legacy_internal", "demo", "test"}:
            rec = "archive_to_third_party"
        else:
            rec = "keep_with_attribution"
        rows.append(
            {
                "path": target,
                "used_by_count": len(usages),
                "used_by": "; ".join(f"{rel} ({kind})" for rel, kind in usages),
                "recommendation": rec,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit upstream module usage.")
    parser.add_argument("--verbose", action="store_true", help="also print per-target details")
    args = parser.parse_args()

    rows = scan()

    out_dir = PROJECT_ROOT / "reports"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "upstream_usage_audit.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "used_by_count", "used_by", "recommendation"])
        writer.writeheader()
        writer.writerows(rows)

    for row in rows:
        print(f"{row['recommendation']:<24} {row['path']:<42} used_by={row['used_by_count']}")
        if args.verbose and row["used_by"]:
            print(f"      -> {row['used_by']}")
    print(f"\nWrote {out_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
