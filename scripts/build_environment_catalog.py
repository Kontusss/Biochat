#!/usr/bin/env python3
"""Generate biomni/environment/catalog.yaml from the upstream descriptors.

Reads ``biomni/env_desc.py`` (full catalog) and ``biomni/env_desc_cm.py``
(commercial-mode variant) — the latter comments out non-commercial entries
and annotates them with license notes.  Emits a single YAML catalog with
per-entry ``commercial_allowed`` / ``license_note`` metadata, so the
commercial view becomes a filtered projection of the full catalog.

Idempotent: safe to re-run.  The generated catalog carries provenance
metadata (source project + license).
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

OUT_PATH = PROJECT_ROOT / "biomni" / "environment" / "catalog.yaml"

# "# \"key\": \"desc\",  # license note" — commented entry in env_desc_cm.py
_COMMENTED_ENTRY_RE = re.compile(
    r'^\s*#\s*"([^"]+)":\s*"(.*)",?\s*(?:#\s*(.*))?$', re.MULTILINE
)


def extract_cm_annotations() -> dict[str, str]:
    """{dataset_name: license_note} from commented entries in env_desc_cm.py."""
    source = (PROJECT_ROOT / "biomni" / "env_desc_cm.py").read_text()
    annotations: dict[str, str] = {}
    for match in _COMMENTED_ENTRY_RE.finditer(source, re.MULTILINE):
        key, _desc, note = match.groups()
        annotations[key] = (note or "").strip()
    return annotations


def build_catalog() -> dict:
    from biomni.env_desc import data_lake_dict as full_dl
    from biomni.env_desc import library_content_dict as full_lib
    from biomni.env_desc_cm import data_lake_dict as cm_dl
    from biomni.env_desc_cm import library_content_dict as cm_lib

    # Keys absent from the commercial-mode variant are non-commercial.
    # The commented annotations in env_desc_cm.py provide the license note.
    excluded = (set(full_dl) - set(cm_dl)) | (set(full_lib) - set(cm_lib))
    cm_notes = extract_cm_annotations()

    def entry(name: str, description: str) -> dict:
        item: dict = {"name": name, "description": description}
        if name in excluded:
            item["commercial_allowed"] = False
            if cm_notes.get(name):
                item["license_note"] = cm_notes[name]
        else:
            item["commercial_allowed"] = True
        return item

    return {
        "meta": {
            "source": "snap-stanford/Biomni (Apache-2.0)",
            "generated_from": [
                "biomni/env_desc.py",
                "biomni/env_desc_cm.py",
            ],
            "generator": "scripts/build_environment_catalog.py",
        },
        "data_lake": [entry(k, v) for k, v in full_dl.items()],
        "libraries": [entry(k, v) for k, v in full_lib.items()],
    }


def main() -> int:
    catalog = build_catalog()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        yaml.safe_dump(
            catalog, f, allow_unicode=True, sort_keys=False, default_flow_style=False
        )
    n_dl = len(catalog["data_lake"])
    n_lib = len(catalog["libraries"])
    n_nc = sum(1 for e in catalog["data_lake"] + catalog["libraries"]
               if e.get("commercial_allowed") is False)
    print(f"Wrote {OUT_PATH.relative_to(PROJECT_ROOT)} "
          f"({n_dl} data-lake entries, {n_lib} libraries, {n_nc} non-commercial)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
