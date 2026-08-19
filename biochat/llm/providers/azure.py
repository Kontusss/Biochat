"""Azure OpenAI provider builder."""

from __future__ import annotations

import os

from biochat.llm.provider_config import ProviderConfig


def build_azure_chat_model(config: ProviderConfig):
    """Create an AzureChatOpenAI instance.

    Removes the ``azure-`` prefix from the model name and reads
    ``OPENAI_ENDPOINT`` / ``OPENAI_API_KEY`` from the environment.
    """
    try:
        from langchain_openai import AzureChatOpenAI
    except ImportError:
        raise ImportError(
            "langchain-openai package is required for Azure OpenAI models. "
            "Install with: pip install langchain-openai"
        ) from None

    model_name = config.model.replace("azure-", "", 1)
    endpoint = os.getenv("OPENAI_ENDPOINT")
    api_key = os.getenv("OPENAI_API_KEY")

    return AzureChatOpenAI(
        openai_api_key=api_key,
        azure_endpoint=endpoint,
        azure_deployment=model_name,
        openai_api_version=config.azure_api_version,
        temperature=config.temperature,
    )
