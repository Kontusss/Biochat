"""Ollama provider builder for local models."""

from __future__ import annotations

from biomni.llm.provider_config import ProviderConfig


def build_ollama_chat_model(config: ProviderConfig):
    """Create a ChatOllama instance for locally-served models."""
    try:
        from langchain_ollama import ChatOllama
    except ImportError:
        raise ImportError(
            "langchain-ollama package is required for Ollama models. "
            "Install with: pip install langchain-ollama"
        ) from None

    return ChatOllama(
        model=config.model,
        temperature=config.temperature,
    )
