"""
LLM source auto-detection from model name.

Replaces the 40-line if/elif chain in the original ``get_llm()``
(lines 56-95) with a data-driven ordered matcher.
"""

from __future__ import annotations

import os

from biochat.llm.types import ALLOWED_SOURCES


# ── Ordered matcher table ────────────────────────────────────────
# Each entry is (source_name, matcher_predicate).
# The FIRST matching entry wins — order matters.
# "matcher" can be:
#   - str  → model name starts with this prefix (case-insensitive)
#   - list → model contains any of these substrings (case-insensitive)
#   - callable → (model, base_url) → bool

def _model_starts_with(model: str, prefix: str) -> bool:
    return model.lower().startswith(prefix.lower())


def _model_contains_any(model: str, substrings: list[str]) -> bool:
    lower = model.lower()
    return any(s.lower() in lower for s in substrings)


_SOURCE_MATCHERS: list[tuple[str, object]] = [
    # Format: (source_name, matcher)
    ("Anthropic",   "claude-"),
    ("Ollama",      "gpt-oss"),
    ("OpenAI",      "gpt-"),
    ("AzureOpenAI", "azure-"),
    ("Gemini",      "gemini-"),
    ("Groq",        lambda m, _: "groq" in m.lower()),
    (
        "Ollama",
        [
            "llama", "mistral", "qwen", "gemma", "phi",
            "dolphin", "orca", "vicuna", "deepseek",
        ],
    ),
    (
        "Bedrock",
        [
            "anthropic.claude-", "amazon.titan-", "meta.llama-",
            "mistral.", "cohere.", "ai21.", "us.",
        ],
    ),
]

# ── Public API ───────────────────────────────────────────────────

def detect_llm_source(
    model: str,
    base_url: str | None = None,
) -> str:
    """Infer the LLM provider source from the model name.

    Detection priority (first match wins):

    1. ``LLM_SOURCE`` environment variable (if valid).
    2. Model name prefix / substring matching against recognized providers.
    3. If *base_url* is set → ``"Custom"``.
    4. If no match → raises ``ValueError``.

    Args:
        model: The LLM model identifier (e.g. ``"claude-sonnet-4-20250514"``).
        base_url: An optional custom base URL.  If the model name doesn't
                  match any known provider and *base_url* is set, the
                  source is inferred as ``"Custom"``.

    Returns:
        One of ``ALLOWED_SOURCES``.

    Raises:
        ValueError: If the source cannot be determined.
    """
    # 1. Explicit env var takes highest priority
    env_source = os.getenv("LLM_SOURCE")
    if env_source and env_source in ALLOWED_SOURCES:
        return env_source

    # 2. Ordered matching against known providers
    for source_name, matcher in _SOURCE_MATCHERS:
        if _try_match(model, matcher):
            return source_name

    # 3. Fallback: custom endpoint
    if base_url is not None:
        return "Custom"

    raise ValueError(
        f"Unable to determine model source for '{model}'. "
        f"Please specify the 'source' parameter explicitly. "
        f"Valid options: {sorted(ALLOWED_SOURCES)}."
    )


# ── Internal helpers ─────────────────────────────────────────────

def _try_match(model: str, matcher: object) -> bool:
    """Test whether *model* satisfies *matcher*."""
    if isinstance(matcher, str):
        return _model_starts_with(model, matcher)
    if isinstance(matcher, list):
        return _model_contains_any(model, matcher)
    if callable(matcher):
        return matcher(model, None)  # type: ignore[no-any-return]
    return False
