"""OpenAI provider builder.

Handles both standard Chat Completions and the newer Responses API
(required by gpt-5-* models).
"""

from __future__ import annotations

from biochat.llm.provider_config import ProviderConfig


def _requires_responses_api(model: str) -> bool:
    """Return True if *model* requires OpenAI's Responses API.

    gpt-5-* models reject legacy Chat Completions parameters like
    ``stop`` and ``temperature``, returning HTTP 400:
    "Unsupported parameter: 'stop'".
    """
    return model.startswith("gpt-5")


def build_openai_chat_model(config: ProviderConfig):
    """Create a ChatOpenAI instance for standard or Responses-API models.

    For gpt-5-* models:
        * Uses ``use_responses_api=True``.
        * Drops ``stop`` and ``temperature`` from the payload to avoid
          HTTP 400 errors (handled by a payload-override subclass).

    For all other models:
        * Standard ``ChatOpenAI`` with legacy parameters.
    """
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        raise ImportError(
            "langchain-openai package is required for OpenAI models. "
            "Install with: pip install langchain-openai"
        ) from None

    if _requires_responses_api(config.model):
        return _build_responses_api_model(config)
    else:
        return ChatOpenAI(
            model=config.model,
            temperature=config.temperature,
            stop_sequences=config.stop_sequences,
        )


def _build_responses_api_model(config: ProviderConfig):
    """Build a ChatOpenAI subclass that strips incompatible params for gpt-5."""
    from langchain_openai import ChatOpenAI

    class _OpenAIResponsesCompat(ChatOpenAI):
        """Drop ``stop`` and ``temperature`` when using the Responses API.

        gpt-5-* models reject these parameters entirely.  We override
        ``_get_request_payload`` to strip them before the request is sent.
        """

        def _get_request_payload(self, input_, *, stop=None, **kwargs):  # type: ignore[override]
            payload = super()._get_request_payload(input_, stop=stop, **kwargs)
            try:
                if (
                    hasattr(self, "_use_responses_api")
                    and self._use_responses_api(payload)  # type: ignore[attr-defined]
                ):
                    payload.pop("stop", None)
                    payload.pop("temperature", None)
            except Exception:
                # Conservative: if anything goes wrong, still strip.
                payload.pop("stop", None)
                payload.pop("temperature", None)
            return payload

    return _OpenAIResponsesCompat(
        model=config.model,
        temperature=1,  # gpt-5 default; stripped from payload above
        stop_sequences=config.stop_sequences,
        use_responses_api=True,
        output_version="v0",
    )
