"""Custom provider builder for any OpenAI-compatible endpoint.

Used for self-hosted solutions (SGLang, vLLM, Ollama with OpenAI API,
DeepSeek, etc.) that expose an OpenAI-compatible ``/v1`` endpoint.
"""

from __future__ import annotations

from biomni.llm.provider_config import ProviderConfig
from biomni.llm.providers._openai_compat import build_openai_compatible_chat_model


def build_custom_chat_model(config: ProviderConfig):
    """Create a ChatOpenAI pointed at a custom OpenAI-compatible endpoint.

    A ``base_url`` MUST be provided — the original code asserts this
    at runtime (line 261: ``assert base_url is not None``).
    """
    if config.base_url is None:
        raise ValueError(
            "base_url must be provided for custom LLM endpoints. "
            "Set CUSTOM_MODEL_BASE_URL or pass base_url=..."
        )

    return build_openai_compatible_chat_model(
        config,
        base_url=config.base_url,
    )
