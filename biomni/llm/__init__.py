"""
Biochat LLM module — multi-provider language model factory.

Replaces the monolithic ``biomni/llm.py`` with a modular architecture:
- ``types.py`` — canonical provider type definitions
- ``provider_config.py`` — structured ``ProviderConfig`` dataclass
- ``source_detector.py`` — automatic provider detection from model name
- ``providers/`` — one builder module per provider
- ``factory.py`` — single public ``create_llm()`` entry point

Backward-compatible alias ``get_llm`` is preserved.
"""

from biomni.llm.factory import create_llm, get_llm
from biomni.llm.types import ALLOWED_SOURCES, SourceType

__all__ = [
    "ALLOWED_SOURCES",
    "SourceType",
    "create_llm",
    "get_llm",
]
