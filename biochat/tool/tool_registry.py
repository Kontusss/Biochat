"""Compatibility adapter — the registry now lives in biochat.tool.registry.

The upstream implementation (linear scans + eager DataFrame) was replaced
by the indexed ``ToolRegistry`` in ``biochat/tool/registry.py``.  This module
keeps the legacy import path working:

    from biochat.tool.tool_registry import ToolRegistry
"""

from biochat.tool.registry import ToolRegistry

__all__ = ["ToolRegistry"]
