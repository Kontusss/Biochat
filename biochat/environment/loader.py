"""YAML loader for the environment catalog."""

from __future__ import annotations

from pathlib import Path

import yaml

from biochat.environment.schema import EnvironmentCatalogSchema

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parent / "catalog.yaml"


def load_catalog(path: str | Path | None = None) -> EnvironmentCatalogSchema:
    """Load and validate the environment catalog YAML.

    Args:
        path: Optional catalog path override (defaults to the bundled
              ``biochat/environment/catalog.yaml``).
    """
    with open(path or DEFAULT_CATALOG_PATH, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return EnvironmentCatalogSchema.model_validate(raw)
