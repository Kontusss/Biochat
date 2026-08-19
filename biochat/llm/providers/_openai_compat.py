"""Shared helper for providers that use OpenAI-compatible endpoints.

Gemini, Groq, and Custom providers all create ``ChatOpenAI`` instances
with different ``base_url`` values.  This module centralises that
common construction pattern.
"""

from __future__ import annotations

import os

from biochat.llm.provider_config import ProviderConfig


def build_openai_compatible_chat_model(
    config: ProviderConfig,
    *,
    base_url: str,
    api_key_env_var: str | None = None,
) -> object:
    """Create a ``ChatOpenAI`` pointed at an OpenAI-compatible endpoint.

    Args:
        config: Standard provider configuration.
        base_url: The API base URL (required).
        api_key_env_var: If provided, the environment variable name to
                         read the API key from (e.g. ``"GEMINI_API_KEY"``).
                         Falls back to ``config.api_key``.

    Returns:
        A configured ``ChatOpenAI`` instance.
    """
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        raise ImportError(
            "langchain-openai package is required. "
            "Install with: pip install langchain-openai"
        ) from None

    # Resolve API key: explicit env var takes priority over config
    api_key: str | None = config.api_key
    if api_key_env_var:
        env_val = os.getenv(api_key_env_var)
        if env_val:
            api_key = env_val

    return ChatOpenAI(
        model=config.model,
        temperature=config.temperature,
        api_key=api_key,
        base_url=base_url,
        stop_sequences=config.stop_sequences,
    )
