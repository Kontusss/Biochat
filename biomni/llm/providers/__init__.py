"""
LLM provider registry — maps source names to builder functions.

To add a new provider, register its builder here and create the
corresponding module in this package.  No changes to ``factory.py``
are needed.
"""

from __future__ import annotations

from typing import Callable

from biomni.llm.providers.anthropic import build_anthropic_chat_model
from biomni.llm.providers.azure import build_azure_chat_model
from biomni.llm.providers.bedrock import build_bedrock_chat_model
from biomni.llm.providers.custom import build_custom_chat_model
from biomni.llm.providers.gemini import build_gemini_chat_model
from biomni.llm.providers.groq import build_groq_chat_model
from biomni.llm.providers.ollama import build_ollama_chat_model
from biomni.llm.providers.openai import build_openai_chat_model

# ── Registry: source name → builder callable ─────────────────────
# Each builder accepts a ``ProviderConfig`` and returns a
# ``BaseChatModel`` instance.
PROVIDER_REGISTRY: dict[str, Callable] = {
    "OpenAI":       build_openai_chat_model,
    "AzureOpenAI":  build_azure_chat_model,
    "Anthropic":    build_anthropic_chat_model,
    "Gemini":       build_gemini_chat_model,
    "Groq":         build_groq_chat_model,
    "Ollama":       build_ollama_chat_model,
    "Bedrock":      build_bedrock_chat_model,
    "Custom":       build_custom_chat_model,
}

__all__ = ["PROVIDER_REGISTRY"]
