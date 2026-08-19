"""Compatibility adapter — the registry now lives in biomni.tool.registry.

The upstream implementation (linear scans + eager DataFrame) was replaced
by the indexed ``ToolRegistry`` in ``biomni/tool/registry.py``.  This module
keeps the legacy import path working:

    from biomni.tool.tool_registry import ToolRegistry
"""

from biomni.tool.registry import ToolRegistry  # noqa: F401

__all__ = ["ToolRegistry"]
