#!/usr/bin/env python3
"""Generate biomni/tool/tool_description/catalog.yaml + adapter modules.

Imports every ``biomni.tool.tool_description.<field>`` module (the field
list comes from ``biomni.utils.io_utils._TOOL_FIELDS``), dumps the
``description`` lists into one YAML catalog, then rewrites each field
module as a thin adapter that loads its section from the catalog.

The dynamic-import contract of ``read_module2api`` (``mod.description``)
is preserved exactly — only the storage moves from Python literals to YAML.

Idempotent: safe to re-run.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DESC_DIR = PROJECT_ROOT / "biomni" / "tool" / "tool_description"
OUT_PATH = DESC_DIR / "catalog.yaml"

ADAPTER_TEMPLATE = '''"""Adapter — {field} tool descriptions now live in catalog.yaml.

The original Python literals were migrated to
``biomni/tool/tool_description/catalog.yaml`` by
``scripts/build_tool_catalog.py``; the upstream data is preserved there
verbatim (Apache-2.0, snap-stanford/Biomni).
"""

from biomni.tool.tool_description._catalog_loader import load_tool_description

description = load_tool_description("{field}")
'''


def collect_descriptions(fields: tuple[str, ...]) -> dict:
    catalog: dict = {"meta": {
        "source": "snap-stanford/Biomni (Apache-2.0)",
        "generator": "scripts/build_tool_catalog.py",
        "fields": list(fields),
    }}
    for field in fields:
        module = importlib.import_module(f"biomni.tool.tool_description.{field}")
        catalog[field] = module.description
    return catalog


def write_adapters(fields: tuple[str, ...]) -> None:
    for field in fields:
        target = DESC_DIR / f"{field}.py"
        target.write_text(ADAPTER_TEMPLATE.format(field=field))


def main() -> int:
    from biomni.utils.io_utils import _TOOL_FIELDS

    fields = tuple(_TOOL_FIELDS)
    catalog = collect_descriptions(fields)
    with open(OUT_PATH, "w") as f:
        yaml.safe_dump(catalog, f, allow_unicode=True, sort_keys=False,
                       default_flow_style=False)
    write_adapters(fields)
    total_entries = sum(len(catalog[f]) for f in fields)
    print(f"Wrote {OUT_PATH.relative_to(PROJECT_ROOT)} "
          f"({len(fields)} fields, {total_entries} tool descriptions) "
          f"+ {len(fields)} adapter modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
