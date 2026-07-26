"""Anthropic (Claude) provider builder.

Includes automatic API key resolution from ``~/.bash_profile`` as a
best-effort fallback when ``ANTHROPIC_API_KEY`` is not set in the
current environment.
"""

from __future__ import annotations

import os

from biomni.llm.provider_config import ProviderConfig


def _try_load_api_key_from_shell_profile(key_name: str) -> str | None:
    """Attempt to read an environment variable from ``~/.bash_profile``.

    Pure function — does **not** modify ``os.environ``.  Only probes
    when *key_name* is not already present in the current environment.

    Args:
        key_name: The environment variable to look for (e.g. ``"ANTHROPIC_API_KEY"``).

    Returns:
        The value if found, or ``None``.
    """
    if os.environ.get(key_name):
        return None  # already set — no need to probe

    try:
        import subprocess

        result = subprocess.run(
            [
                "bash", "-c",
                f"source ~/.bash_profile 2>/dev/null && echo ${key_name}",
            ],
            capture_output=True, text=True, timeout=5,
        )
        value = result.stdout.strip()
        if value:
            return value
    except Exception:
        pass
    return None


def build_anthropic_chat_model(config: ProviderConfig):
    """Create a ChatAnthropic instance.

    1. If ``ANTHROPIC_API_KEY`` is not in the current environment,
       attempts to load it from ``~/.bash_profile`` (best-effort).
    2. Creates ``ChatAnthropic`` with ``max_tokens=8192``.
    """
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        raise ImportError(
            "langchain-anthropic package is required for Anthropic models. "
            "Install with: pip install langchain-anthropic"
        ) from None

    # Best-effort key resolution from shell profile.
    # Side-effect preserved: write key into os.environ if found.
    shell_key = _try_load_api_key_from_shell_profile("ANTHROPIC_API_KEY")
    if shell_key:
        os.environ["ANTHROPIC_API_KEY"] = shell_key
        print("✓ Loaded ANTHROPIC_API_KEY from ~/.bash_profile")

    return ChatAnthropic(
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        stop_sequences=config.stop_sequences,
    )
