"""Environment registry — single source of truth for environment descriptors.

Replaces the two parallel upstream dict modules (``biochat/env_desc.py``
full view, ``biochat/env_desc_cm.py`` commercial view) with one catalog plus
a mode filter.  The commercial view is now a *projection* of the full
catalog rather than a hand-maintained copy.
"""

from __future__ import annotations

from functools import lru_cache

from biochat.environment.loader import load_catalog
from biochat.environment.schema import CatalogEntry


class EnvironmentCatalog:
    """Described data-lake and library resources, filterable by license mode.

    Usage::

        catalog = EnvironmentCatalog()
        catalog.data_lake_dict              # full view (all entries)
        catalog.data_lake_dict_cm           # commercial view
    """

    def __init__(self, path: str | None = None):
        doc = load_catalog(path)
        self.meta = doc.meta
        self.data_lake: list[CatalogEntry] = list(doc.data_lake)
        self.libraries: list[CatalogEntry] = list(doc.libraries)

    # ── Dict views (agent-facing, name → description) ─────────────

    @staticmethod
    def _as_dict(entries: list[CatalogEntry], commercial_only: bool) -> dict[str, str]:
        return {
            e.name: e.description
            for e in entries
            if not commercial_only or e.commercial_allowed
        }

    @property
    def data_lake_dict(self) -> dict[str, str]:
        """Full data-lake view (equivalent to upstream ``env_desc.py``)."""
        return self._as_dict(self.data_lake, commercial_only=False)

    @property
    def library_content_dict(self) -> dict[str, str]:
        """Full library view (equivalent to upstream ``env_desc.py``)."""
        return self._as_dict(self.libraries, commercial_only=False)

    @property
    def data_lake_dict_cm(self) -> dict[str, str]:
        """Commercial-mode data-lake view (equivalent to ``env_desc_cm.py``)."""
        return self._as_dict(self.data_lake, commercial_only=True)

    @property
    def library_content_dict_cm(self) -> dict[str, str]:
        """Commercial-mode library view (equivalent to ``env_desc_cm.py``)."""
        return self._as_dict(self.libraries, commercial_only=True)

    # ── Metadata / policy ─────────────────────────────────────────

    def commercial_allowed(self, name: str) -> bool:
        """License policy lookup for one resource name."""
        for e in self.data_lake + self.libraries:
            if e.name == name:
                return e.commercial_allowed
        return True  # unknown resources are not restricted by this catalog

    def license_note(self, name: str) -> str | None:
        for e in self.data_lake + self.libraries:
            if e.name == name:
                return e.license_note
        return None


@lru_cache(maxsize=1)
def get_environment_catalog() -> EnvironmentCatalog:
    """Process-wide cached catalog (the YAML is immutable configuration)."""
    return EnvironmentCatalog()
