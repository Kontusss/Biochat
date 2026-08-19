"""Local-filesystem Markdown knowledge loader."""

from __future__ import annotations

import glob
import os
from pathlib import Path

from biomni.knowledge.source import KnowledgeSource, parse_markdown_source, should_load_file


class LocalMarkdownLoader:
    """Loads ``*.md`` know-how documents from a directory on disk."""

    def __init__(self, scan_dir: str | Path):
        self.scan_dir = str(scan_dir)

    def load(self) -> list[KnowledgeSource]:
        """Return parsed sources for every loadable ``*.md`` file."""
        sources: list[KnowledgeSource] = []
        for filepath in sorted(glob.glob(os.path.join(self.scan_dir, "*.md"))):
            filename = os.path.basename(filepath)
            if not should_load_file(filename):
                continue
            with open(filepath, encoding="utf-8") as fh:
                raw = fh.read()
            sources.append(parse_markdown_source(raw, filename, origin=filepath))
        return sources
