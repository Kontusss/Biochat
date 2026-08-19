"""Shared loader for tool-description catalog sections."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

CATALOG_PATH = Path(__file__).resolve().parent / "catalog.yaml"


@lru_cache(maxsize=1)
def _catalog() -> dict:
    with open(CATALOG_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_tool_description(field: str) -> list:
    """Return the ``description`` list for one tool field."""
    catalog = _catalog()
    if field not in catalog:
        raise KeyError(f"Unknown tool field '{field}' in {CATALOG_PATH}")
    return catalog[field]
