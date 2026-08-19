"""Knowledge layer — registry of know-how sources injected into the agent.

This package replaces the upstream ``biomni/know_how/loader.py``.  The old
``biomni.know_how`` path is preserved as a thin compatibility adapter.
"""

from biomni.knowledge.registry import KnowledgeRegistry
from biomni.knowledge.source import KnowledgeSource, parse_markdown_source

__all__ = ["KnowledgeRegistry", "KnowledgeSource", "parse_markdown_source"]
