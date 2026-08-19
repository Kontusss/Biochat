"""Deprecated adapter — delegates to :mod:`biochat.knowledge`.

The original upstream loader implementation has been replaced by the
knowledge registry architecture (``biochat/knowledge/registry.py``).
This adapter keeps the old constructor signature and document dict
shape so pre-existing callers work unchanged.
"""

from __future__ import annotations

from biochat.knowledge import KnowledgeRegistry


class KnowHowLoader(KnowledgeRegistry):
    """Compatibility wrapper for the old ``KnowHowLoader`` entry point.

    Args:
        know_how_dir: Optional directory override.  Defaults to the bundled
                      ``biochat/knowledge/docs``.
    """

    def __init__(self, know_how_dir: str | None = None):
        super().__init__(docs_dir=know_how_dir)
