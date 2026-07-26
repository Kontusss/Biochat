"""Google Gemini provider builder.

Connects to Gemini models through the OpenAI-compatible endpoint at
``https://generativelanguage.googleapis.com/v1beta/openai/``.
"""

from __future__ import annotations

from biomni.llm.provider_config import ProviderConfig
from biomni.llm.providers._openai_compat import build_openai_compatible_chat_model


_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def build_gemini_chat_model(config: ProviderConfig):
    """Create a ChatOpenAI pointed at Gemini's OpenAI-compatible endpoint."""
    return build_openai_compatible_chat_model(
        config,
        base_url=_GEMINI_BASE_URL,
        api_key_env_var="GEMINI_API_KEY",
    )
