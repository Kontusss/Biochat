"""
Provider configuration dataclass for LLM factory functions.

Replaces the ad-hoc parameter resolution at the top of the original
``get_llm()`` function (lines 36-54) with a structured, validated
configuration object.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderConfig:
    """Immutable configuration bundle for an LLM provider.

    All fields have sensible defaults matching the original
    ``get_llm()`` fallback logic.  ``frozen=True`` prevents
    accidental mutation after construction.
    """

    # ── Required ──────────────────────────────────────────────
    model: str = "claude-3-5-sonnet-20241022"

    # ── Generation parameters ─────────────────────────────────
    temperature: float = 0.7
    max_tokens: int = 8192
    stop_sequences: list[str] | None = None

    # ── Connection ────────────────────────────────────────────
    base_url: str | None = None
    api_key: str | None = None

    # ── Provider identity ─────────────────────────────────────
    source: str | None = None        # e.g. "Anthropic", "OpenAI", "Custom"

    # ── Provider-specific overrides ───────────────────────────
    azure_endpoint: str | None = None
    azure_api_version: str = "2024-12-01-preview"
    aws_region: str = "us-east-1"

    @classmethod
    def from_legacy_params(
        cls,
        model: str | None = None,
        temperature: float | None = None,
        stop_sequences: list[str] | None = None,
        source: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        *,
        legacy_config: object | None = None,
    ) -> ProviderConfig:
        """Build a ``ProviderConfig`` from the original ``get_llm()`` parameters.

        This provides a migration path: old code can keep calling
        ``get_llm(model=..., source=...)`` and the new factory
        converts them to ``ProviderConfig`` internally.

        Priority: explicit parameter > legacy_config attribute > default.
        """
        # Resolve from legacy BiochatConfig if provided
        cfg_model: str | None = model
        cfg_temp: float | None = temperature
        cfg_source: str | None = source
        cfg_base_url: str | None = base_url
        cfg_api_key: str | None = api_key

        if legacy_config is not None:
            lc = legacy_config  # type: ignore[union-attr]
            if cfg_model is None:
                cfg_model = getattr(lc, "llm_model", None) or getattr(lc, "llm", None)
            if cfg_temp is None:
                cfg_temp = getattr(lc, "temperature", None)
            if cfg_source is None:
                cfg_source = getattr(lc, "source", None)
            if cfg_base_url is None:
                cfg_base_url = getattr(lc, "base_url", None)
            if cfg_api_key is None:
                cfg_api_key = getattr(lc, "api_key", None)

        return cls(
            model=cfg_model or "claude-3-5-sonnet-20241022",
            temperature=cfg_temp if cfg_temp is not None else 0.7,
            stop_sequences=stop_sequences,
            source=cfg_source,
            base_url=cfg_base_url,
            api_key=cfg_api_key or "EMPTY",
        )
