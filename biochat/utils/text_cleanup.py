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
    # Common tool/data emojis used in Biochat prompts
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


# ═══════════════════════════════════════════════════════════════
# Internal reasoning sanitization
# ═══════════════════════════════════════════════════════════════

# XML-like internal reasoning tags — content between these tags is
# hidden chain-of-thought and must NEVER reach the user.
_INTERNAL_REASONING_TAGS = (
    "think",
    "thinking",
    "reasoning",
    "analysis",
    "reflection",
    "scratchpad",
    "chain_of_thought",
    "chain-of-thought",
    "inner_monologue",
    "inner-monologue",
    "self_critique",
    "self-critique",
)

# Build one combined regex matching any internal reasoning block
_INTERNAL_TAG_RE = re.compile(
    r"</?(?:" + "|".join(_INTERNAL_REASONING_TAGS) + r")>",
    re.IGNORECASE | re.DOTALL,
)

# Paired-tag block removal (content between open and close tags)
_INTERNAL_BLOCK_PATTERNS = [
    re.compile(
        rf"<{tag}>(.*?)</{tag}>",
        re.IGNORECASE | re.DOTALL,
    )
    for tag in _INTERNAL_REASONING_TAGS
]

# Markdown / Chinese headings that introduce hidden reasoning sections
_REASONING_HEADINGS = (
    r"\*\*\s*思考过程\s*[:：]\*\*",
    r"\*\*\s*思考过程\*\*",
    r"思考过程\s*[:：]",
    r"内部推理\s*[:：]",
    r"推理过程\s*[:：]",
    r"草稿\s*[:：]",
    r"自我批评\s*[:：]",
    r"self-critique\s*[:：]",
    r"Chain.?of.?Thought\s*[:：]",
    r"CoT\s*[:：]",
    r"scratchpad\s*[:：]",
    r"内部独白\s*[:：]",
)

_REASONING_HEADING_RE = re.compile(
    r"(?:^|\n)\s*(?:" + "|".join(_REASONING_HEADINGS) + r")[^\n]*",
    re.IGNORECASE,
)

# Cleanup residue left by tag-stripping heuristics
_TAG_RESIDUE_PATTERNS = (
    r"标签\s*结尾\s*[。.]",
    r"标签\s*开始\s*[。.]",
    r"标签\s*结束\s*[。.]",
    r"<\s*/\s*(?:" + "|".join(_INTERNAL_REASONING_TAGS) + r")\s*>",
    r"<\s*(?:" + "|".join(_INTERNAL_REASONING_TAGS) + r")\s*>",
)

_TAG_RESIDUE_RE = re.compile(
    "|".join(_TAG_RESIDUE_PATTERNS),
    re.IGNORECASE,
)


def strip_internal_reasoning(text: str) -> str:
    """Remove hidden chain-of-thought / internal reasoning from *text*.

    Removes:
      - Paired internal tags (``<think>...</think>`` etc.) including content.
      - Reasoning section headings (``**思考过程:**``, ``内部推理：`` etc.)
        and the lines they introduce.
      - Leftover opening/closing tags.
      - Tag cleanup residue (``标签结尾。``, ``标签开始。``).

    Args:
        text: Raw assistant message text.

    Returns:
        Sanitized text with internal reasoning removed.
    """
    if not text:
        return ""

    result = text

    # 1. Remove paired internal blocks (tags + content)
    for pattern in _INTERNAL_BLOCK_PATTERNS:
        result = pattern.sub("", result)

    # 2. Remove reasoning headings and the lines they start.
    #    A reasoning heading runs until the next blank line or section
    #    marker; the following loop collapses leftover blank lines.
    result = _REASONING_HEADING_RE.sub("", result)

    # 3. Remove any remaining internal tags (open or close)
    result = _INTERNAL_TAG_RE.sub("", result)

    # 4. Remove tag cleanup residue phrases
    result = _TAG_RESIDUE_RE.sub("", result)

    # 5. Collapse 3+ newlines to at most 2
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()


def strip_xml_like_tags(text: str) -> str:
    """Remove all XML-like tags (``<tag>`` / ``</tag>``) from *text*.

    Unlike :func:`strip_internal_reasoning`, this removes EVERY tag
    regardless of name, but keeps the text content between them.
    """
    if not text:
        return ""
    result = re.sub(r"</?[a-zA-Z_][\w:-]*\s*/?>", "", text)
    return re.sub(r"\n{3,}", "\n\n", result).strip()


def sanitize_assistant_message(text: str) -> str:
    """Full sanitization for user-facing assistant messages.

    Order matters:
    1. Strip internal reasoning blocks (tags + content).
    2. Strip any remaining XML-like tags (keeping content).
    3. Remove reasoning headings and tag residue.
    4. Collapse excess whitespace.

    Args:
        text: Raw assistant message.

    Returns:
        Clean user-facing text.
    """
    if not text:
        return ""
    result = strip_internal_reasoning(text)
    result = strip_xml_like_tags(result)
    # Second pass to catch residue exposed by tag stripping
    result = _TAG_RESIDUE_RE.sub("", result)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


# ── Backward-compatible aliases ──────────────────────────────
clean_message_content = strip_ansi_escape_codes
should_skip_message = is_message_empty
remove_emojis_from_text = strip_emojis
create_parsing_error_html = build_parsing_error_html
