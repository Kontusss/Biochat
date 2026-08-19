"""Groq provider builder.

Connects to Groq models through the OpenAI-compatible endpoint at
``https://api.groq.com/openai/v1``.
"""

from __future__ import annotations

from biochat.llm.provider_config import ProviderConfig
from biochat.llm.providers._openai_compat import build_openai_compatible_chat_model


_GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def build_groq_chat_model(config: ProviderConfig):
    """Create a ChatOpenAI pointed at Groq's OpenAI-compatible endpoint."""
    return build_openai_compatible_chat_model(
        config,
        base_url=_GROQ_BASE_URL,
        api_key_env_var="GROQ_API_KEY",
    )
