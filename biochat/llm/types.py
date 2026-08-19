"""
LLM type definitions for Biochat.

Defines the canonical set of supported LLM providers and helper
utilities for working with them.

Requires Python >= 3.11 (project minimum).
"""

from __future__ import annotations

from typing import Literal

# ── Canonical source type ────────────────────────────────────────
SourceType = Literal[
    "OpenAI",
    "AzureOpenAI",
    "Anthropic",
    "Ollama",
    "Gemini",
    "Bedrock",
    "Groq",
    "Custom",
]

# ── Immutable set for fast membership testing ────────────────────
ALLOWED_SOURCES: frozenset[str] = frozenset({
    "OpenAI",
    "AzureOpenAI",
    "Anthropic",
    "Ollama",
    "Gemini",
    "Bedrock",
    "Groq",
    "Custom",
})
