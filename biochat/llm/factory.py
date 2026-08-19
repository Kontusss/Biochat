"""
LLM factory — creates LangChain chat model instances.

This is the single public entry point that replaces the ~180-line
``get_llm()`` function.  Source auto-detection and provider-specific
construction are delegated to sub-modules.

Usage::

    from biochat.llm.factory import create_llm

    chat_model = create_llm(
        model="claude-sonnet-4-20250514",
        temperature=0.7,
        source="Anthropic",
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.language_models.chat_models import BaseChatModel

from biochat.llm.provider_config import ProviderConfig
from biochat.llm.providers import PROVIDER_REGISTRY
from biochat.llm.source_detector import detect_llm_source

if TYPE_CHECKING:
    from biochat.config import BiochatConfig


def create_llm(
    model: str | None = None,
    temperature: float | None = None,
    stop_sequences: list[str] | None = None,
    source: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    *,
    legacy_config: "BiochatConfig | None" = None,
    config: "BiochatConfig | None" = None,  # backward-compat alias for legacy_config
) -> BaseChatModel:
    """Create a LangChain chat model for the given provider.

    Args:
        model: Model identifier (e.g. ``"claude-sonnet-4-20250514"``).
        temperature: Sampling temperature (0.0–1.0).
        stop_sequences: Optional list of stop tokens.
        source: Explicit provider name.  Auto-detected if ``None``.
        base_url: Custom endpoint URL (required for ``"Custom"`` source).
        api_key: API key for custom endpoints.
        legacy_config: Optional ``BiochatConfig`` for backward compatibility.
        config: Deprecated alias for *legacy_config*.

    Returns:
        A configured ``BaseChatModel`` instance.
    """
    # Resolve config/legacy_config — prefer legacy_config if both given
    resolved_config = legacy_config or config

    # 1. Build unified configuration
    provider_cfg = ProviderConfig.from_legacy_params(
        model=model,
        temperature=temperature,
        stop_sequences=stop_sequences,
        source=source,
        base_url=base_url,
        api_key=api_key,
        legacy_config=resolved_config,
    )

    # 2. Auto-detect source if not explicitly provided
    resolved_source = provider_cfg.source
    if resolved_source is None:
        resolved_source = detect_llm_source(provider_cfg.model, provider_cfg.base_url)

    # 3. Dispatch to the appropriate builder via registry
    builder = PROVIDER_REGISTRY.get(resolved_source)
    if builder is None:
        raise ValueError(
            f"Invalid LLM source: '{resolved_source}'. "
            f"Valid options: {sorted(PROVIDER_REGISTRY.keys())}."
        )

    return builder(provider_cfg)


# ── Backward-compatible alias ─────────────────────────────────────
# Keep the original function name available so existing ``from biochat.llm
# import get_llm`` calls continue to work.

get_llm = create_llm
