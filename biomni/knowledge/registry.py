"""Knowledge registry — central store for agent know-how documents.

The registry is the successor to the upstream ``biomni/know_how/loader.py``.
It keeps the same *document dict shape* the agent consumes (``id``, ``name``,
``description``, ``content``, ``content_without_metadata``, ``filepath``,
``metadata``) while moving the storage model to :class:`KnowledgeSource`
objects loaded through pluggable loaders.  License policy (commercial-mode
exclusion) is enforced here rather than in the agent.
"""

from __future__ import annotations

import os
from pathlib import Path

from biomni.knowledge.loaders.local import LocalMarkdownLoader
from biomni.knowledge.source import KnowledgeSource

DEFAULT_DOCS_DIR = str(Path(__file__).resolve().parent / "docs")

_NON_COMMERCIAL_MARKERS = ("❌", "Not Allowed", "Non-Commercial")


class KnowledgeRegistry:
    """Loads, filters and serves knowledge sources for the agent."""

    def __init__(self, docs_dir: str | None = None, loaders: list | None = None):
        """Initialise the registry.

        Args:
            docs_dir: Directory scanned for ``*.md`` documents.  Defaults to
                      the bundled ``biomni/knowledge/docs``.
            loaders: Optional custom loaders (default: one LocalMarkdownLoader).
        """
        self.docs_dir = docs_dir or DEFAULT_DOCS_DIR
        self._loaders = loaders or [LocalMarkdownLoader(self.docs_dir)]
        self._sources: dict[str, KnowledgeSource] = {}
        self._load_documents()

    # ── Loading ────────────────────────────────────────────────────

    def _load_documents(self) -> None:
        self._sources = {}
        for loader in self._loaders:
            for source in loader.load():
                self._sources[source.id] = source

    def reload(self) -> None:
        """Re-scan all loaders from disk."""
        self._load_documents()

    # ── Document access (agent-compatible dict shape) ──────────────

    @property
    def documents(self) -> dict[str, dict]:
        """Documents as the dict shape consumed by ``A1`` / prompt builder."""
        return {sid: self._as_document(s) for sid, s in self._sources.items()}

    @staticmethod
    def _as_document(source: KnowledgeSource) -> dict:
        return {
            "id": source.id,
            "name": source.name,
            "description": source.description,
            "content": source.content,
            "content_without_metadata": source.content_without_metadata,
            "filepath": source.origin,
            "metadata": source.metadata,
        }

    def get_all_documents(self) -> list[dict]:
        """All documents (full content included)."""
        return list(self.documents.values())

    def get_document_by_id(self, doc_id: str) -> dict | None:
        """One document by id, or None."""
        return self.documents.get(doc_id)

    def get_document_summaries(self) -> list[dict]:
        """Summaries (id / name / description) without full content."""
        return [
            {"id": d["id"], "name": d["name"], "description": d["description"]}
            for d in self.documents.values()
        ]

    def get_document_metadata(self, doc_id: str) -> dict | None:
        """Metadata dict for one document, or None."""
        doc = self.documents.get(doc_id)
        return doc.get("metadata", {}) if doc else None

    # ── Mutation ───────────────────────────────────────────────────

    def add_custom_document(
        self,
        doc_id: str,
        name: str,
        description: str,
        content: str,
        metadata: dict | None = None,
    ) -> None:
        """Register a programmatic (non-file) knowledge document."""
        self._sources[doc_id] = KnowledgeSource(
            id=doc_id,
            name=name,
            description=description,
            content=content,
            metadata=metadata or {},
            origin=None,
            content_without_metadata=content,
        )

    def remove_document(self, doc_id: str) -> None:
        """Drop a document from the registry."""
        self._sources.pop(doc_id, None)

    # ── License policy ─────────────────────────────────────────────

    def exclude_non_commercial(self) -> list[str]:
        """Remove documents whose ``commercial_use`` metadata forbids
        commercial use.  Returns the ids that were excluded."""
        excluded: list[str] = []
        for doc_id, doc in list(self.documents.items()):
            commercial_use = doc.get("metadata", {}).get("commercial_use", "")
            if any(marker in commercial_use for marker in _NON_COMMERCIAL_MARKERS):
                self.remove_document(doc_id)
                excluded.append(doc_id)
        return excluded

    # ── Console output (kept for parity with the old loader) ───────

    def print_document_info(self, doc_id: str) -> None:
        """Print a formatted summary of one document."""
        doc = self.documents.get(doc_id)
        if not doc:
            print(f"Document '{doc_id}' not found")
            return

        print("=" * 70)
        print(f"📚 {doc['name']}")
        print("=" * 70)
        print(f"\nDescription: {doc['description']}")

        metadata = doc.get("metadata", {})
        if metadata:
            print("\n" + "-" * 70)
            print("METADATA")
            print("-" * 70)
            for key, label in (
                ("authors", "Authors"),
                ("affiliations", "Affiliations"),
                ("version", "Version"),
                ("last_updated", "Last Updated"),
                ("license", "License"),
                ("commercial_use", "Commercial Use"),
                ("status", "Status"),
            ):
                if key in metadata:
                    print(f"{label}: {metadata[key]}")
        print("=" * 70)
