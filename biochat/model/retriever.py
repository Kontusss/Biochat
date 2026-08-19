"""Compatibility adapter — the retriever now lives in
biochat.model.resource_selector.

The upstream ``ToolRetriever`` was replaced by ``ResourceSelector`` in
``biochat/model/resource_selector.py``.  This module keeps the legacy import
path working:

    from biochat.model.retriever import ToolRetriever
"""

from biochat.model.resource_selector import ResourceSelector

ToolRetriever = ResourceSelector

__all__ = ["ToolRetriever"]
