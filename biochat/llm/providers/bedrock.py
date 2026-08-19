"""AWS Bedrock provider builder."""

from __future__ import annotations

import os

from biochat.llm.provider_config import ProviderConfig


def build_bedrock_chat_model(config: ProviderConfig):
    """Create a ChatBedrock instance for AWS-hosted models."""
    try:
        from langchain_aws import ChatBedrock
    except ImportError:
        raise ImportError(
            "langchain-aws package is required for Bedrock models. "
            "Install with: pip install langchain-aws"
        ) from None

    region = os.getenv("AWS_REGION", config.aws_region)

    return ChatBedrock(
        model=config.model,
        temperature=config.temperature,
        stop_sequences=config.stop_sequences,
        region_name=region,
    )
