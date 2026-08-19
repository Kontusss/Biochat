"""Compatibility adapter — the retriever now lives in
biomni.model.resource_selector.

The upstream ``ToolRetriever`` was replaced by ``ResourceSelector`` in
``biomni/model/resource_selector.py``.  This module keeps the legacy import
path working:

    from biomni.model.retriever import ToolRetriever
"""

from biomni.model.resource_selector import ResourceSelector

ToolRetriever = ResourceSelector

__all__ = ["ToolRetriever"]
