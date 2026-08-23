#!/usr/bin/env python3
"""Runtime tool usage audit → reports/runtime_tool_usage.csv + profile manifest.

Classifies every registered tool (from ``load_all_tool_descriptions``):

- ``used_by_demo`` — the tool name appears in Biochat-original code
  (scripts / examples / UI / prompts / services / tests);
- ``used_by_antibody_pipeline`` — the tool belongs to (or is statically
  imported by) ``biochat.tool.antibody_design``;
- ``used_by_registry`` — the tool's function module is statically imported
  by Biochat runtime code (beyond the dynamic registry itself);
- ``requires_external_dependency`` — the function module imports heavy
  optional dependencies at module level (torch / ImmuneBuilder / docker …).

Recommendations:
    keep_minimal            required by the minimal profile
                            (demo + antibody pipeline + engine glue)
    keep_with_attribution   upstream module Biochat runtime imports
                            statically — stays loadable in both profiles
    optional_full_profile   upstream scientific tool, full profile only
    archive_unused          registered nowhere (should be empty)

Also regenerates ``biochat/tool/profiles.py`` (the manifest consumed by
``ToolRegistry`` / ``load_all_tool_descriptions``).
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

OUT_CSV = PROJECT_ROOT / "reports" / "runtime_tool_usage.csv"
MANIFEST = PROJECT_ROOT / "biochat" / "tool" / "profiles.py"

# Biochat-original dirs whose mention of a tool name counts as demo usage.
# (tests/ is excluded — incidental name mentions there are not demo usage.)
DEMO_DIRS = ("scripts", "examples", "biochat/ui", "biochat/prompts",
             "biochat/services")

# Heavy optional dependencies (module-level import detection)
HEAVY_DEPS = ("torch", "ImmuneBuilder", "docker", "rdkit", "scanpy",
              "celltypist", "Bio", "anndata", "matplotlib", "seaborn")


def module_key_to_field(module_key: str) -> str:
    return module_key.removeprefix("biochat.tool.")


def function_module_files(field: str) -> list[Path]:
    """Candidate function-module files for one tool field."""
    base = PROJECT_ROOT / "biochat" / "tool" / field
    if base.is_dir():
        return sorted(base.rglob("*.py"))
    file = base.with_suffix(".py")
    return [file] if file.exists() else []


def static_importers_of(module_key: str, scope: Path) -> list[str]:
    """Rel-paths under *scope* that statically import *module_key*."""
    pattern = re.compile(
        rf"^\s*(?:from\s+{re.escape(module_key)}\s+import|import\s+{re.escape(module_key)}\b)",
        re.MULTILINE,
    )
    hits = []
    for py_file in scope.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        if pattern.search(py_file.read_text(errors="ignore")):
            hits.append(str(py_file.relative_to(PROJECT_ROOT)))
    return hits


def audit() -> tuple[list[dict], dict]:
    from biochat.utils.io_utils import load_all_tool_descriptions

    module2api = load_all_tool_descriptions()

    # Demo-referenced tool names (Biochat-original dirs only)
    demo_names: set[str] = set()
    for dirname in DEMO_DIRS:
        scope = PROJECT_ROOT / dirname
        if not scope.exists():
            continue
        for py_file in scope.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            source = py_file.read_text(errors="ignore")
            for _module_key, tools in module2api.items():
                for tool in tools:
                    name = tool["name"]
                    if re.search(rf"\b{re.escape(name)}\b", source):
                        demo_names.add(name)

    # Antibody pipeline modules
    pipeline_modules = {"biochat.tool.antibody_design"}
    ab_dir = PROJECT_ROOT / "biochat" / "tool" / "antibody_design"
    for field in module2api:
        for importer in static_importers_of(field, ab_dir):
            if importer.startswith("biochat/tool/antibody_design/"):
                pipeline_modules.add(field)

    # Statically imported by Biochat runtime (excluding biochat/tool itself)
    runtime_scope = PROJECT_ROOT / "biochat"
    rows: list[dict] = []
    for module_key, tools in module2api.items():
        field = module_key_to_field(module_key)
        files = function_module_files(field)
        sources = "\n".join(f.read_text(errors="ignore") for f in files)
        heavy = [dep for dep in HEAVY_DEPS
                 if re.search(rf"^\s*(?:import\s+{re.escape(dep)}\b|from\s+{re.escape(dep)}\b)",
                              sources, re.MULTILINE)]

        if module_key == "biochat.tool.antibody_design":
            runtime_importers = []
        else:
            runtime_importers = [
                p for p in static_importers_of(module_key, runtime_scope)
                if not p.startswith("biochat/tool/")
            ]

        for tool in tools:
            name = tool["name"]
            used_by_demo = name in demo_names
            used_by_pipeline = module_key in pipeline_modules
            used_by_registry = bool(runtime_importers)
            if used_by_demo or used_by_pipeline:
                recommendation = "keep_minimal"
            elif used_by_registry:
                recommendation = "keep_with_attribution"
            else:
                recommendation = "optional_full_profile"
            rows.append({
                "module": module_key,
                "tool_name": name,
                "used_by_demo": used_by_demo,
                "used_by_antibody_pipeline": used_by_pipeline,
                "used_by_registry": used_by_registry,
                "requires_external_dependency": ";".join(heavy),
                "recommendation": recommendation,
            })

    minimal_modules = sorted({
        r["module"] for r in rows
        if r["recommendation"] in ("keep_minimal", "keep_with_attribution")
    })
    manifest = {
        "minimal_modules": minimal_modules,
        "generator": "scripts/audit_runtime_tools.py",
    }
    rows.sort(key=lambda r: (r["module"], r["tool_name"]))
    return rows, manifest


def write_manifest(manifest: dict) -> None:
    modules = ",\n".join(f"    {m!r}" for m in manifest["minimal_modules"])
    MANIFEST.write_text(
        f'"""Tool profile manifests — GENERATED by scripts/audit_runtime_tools.py.\n'
        f'\n'
        f'MINIMAL_TOOL_MODULES lists the modules loaded by the minimal runtime\n'
        f'profile (competition demo + antibody design pipeline + engine glue).\n'
        f'The full profile loads every attributed Biochat tool module.\n'
        f'Regenerate with: python scripts/audit_runtime_tools.py\n'
        f'"""\n\n'
        f'MINIMAL_TOOL_MODULES: frozenset[str] = frozenset({{\n'
        f'{modules},\n'
        f'}})\n'
    )
    print(f"Wrote {MANIFEST.relative_to(PROJECT_ROOT)} "
          f"({len(manifest['minimal_modules'])} minimal modules)")


def main() -> int:
    rows, manifest = audit()
    OUT_CSV.parent.mkdir(exist_ok=True)
    fields = ["module", "tool_name", "used_by_demo", "used_by_antibody_pipeline",
              "used_by_registry", "requires_external_dependency", "recommendation"]
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    from collections import Counter
    counts = Counter(r["recommendation"] for r in rows)
    print(f"Wrote {OUT_CSV.relative_to(PROJECT_ROOT)} "
          f"({len(rows)} tools: {dict(counts)})")
    write_manifest(manifest)

    for module_key in manifest["minimal_modules"]:
        n = sum(1 for r in rows if r["module"] == module_key)
        print(f"  minimal: {module_key} ({n} tools)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
