"""Text cleanup and sanitization utilities.

Replaces the scattered string-cleanup functions from the original
``utils.py`` (lines 1021-1128).
"""

from __future__ import annotations

import re

# ═══════════════════════════════════════════════════════════════
# Pre-compiled patterns for performance
# ═══════════════════════════════════════════════════════════════

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")

_EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001F9FF"    # Misc symbols, emoticons, etc.
    r"\U0001FA00-\U0001FA6F"     # Chess symbols
    r"\U0001FA70-\U0001FAFF"     # Symbols extended-A
    r"\U00002600-\U000027BF"     # Misc symbols
    r"\U0001F600-\U0001F64F"     # Emoticons
    r"]",
    re.UNICODE,
)


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════

def strip_ansi_escape_codes(content: str) -> str:
    """Remove ANSI escape sequences (color codes, cursor movements, etc.).

    Args:
        content: Raw terminal output potentially containing ANSI codes.

    Returns:
        Clean plain-text string.

    Example:
        >>> strip_ansi_escape_codes("Hello \\x1b[31mworld\\x1b[0m!")
        "Hello world!"
    """
    return _ANSI_ESCAPE_RE.sub("", content)


def is_message_empty(clean_output: str) -> bool:
    """Return True if the processed message should be skipped.

    Skips messages whose content is empty or semantically equivalent
    to "no content" (``None``, ``null``, ``undefined``).

    Deliberately does NOT skip parsing-error messages — those need to
    be shown to the user.
    """
    return clean_output.strip() in {"", "None", "null", "undefined"}


def strip_emojis(text: str) -> str:
    """Remove common emoji characters from *text*.

    Used when generating plain-text output (e.g. PDF conversion) where
    emoji rendering is unreliable.
    """
    # Common tool/data emojis used in Biomni prompts
    for pattern in (r"🔧\s*", r"📊\s*", r"⚙️\s*", r"📋\s*", r"🤖\s*"):
        text = re.sub(pattern, "", text)
    return _EMOJI_RE.sub("", text).strip()


def build_parsing_error_html() -> str:
    """Return an HTML snippet for displaying LLM parsing errors."""
    return (
        '<div class="parsing-error-box">'
        '<div class="parsing-error-header">Parsing Error</div>'
        '<div class="parsing-error-content">'
        "Each response must include thinking process followed by either "
        "execute or solution tag. But there are no tags in the current response."
        "</div></div>"
    )


# ── Backward-compatible aliases ──────────────────────────────
clean_message_content = strip_ansi_escape_codes
should_skip_message = is_message_empty
remove_emojis_from_text = strip_emojis
create_parsing_error_html = build_parsing_error_html
