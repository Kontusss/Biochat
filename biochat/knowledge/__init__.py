"""Knowledge layer — registry of know-how sources injected into the agent.

This package replaces the upstream ``biochat/know_how/loader.py``.  The old
``biochat.know_how`` path is preserved as a thin compatibility adapter.
"""

from biochat.knowledge.registry import KnowledgeRegistry
from biochat.knowledge.source import KnowledgeSource, parse_markdown_source

__all__ = ["KnowledgeRegistry", "KnowledgeSource", "parse_markdown_source"]
