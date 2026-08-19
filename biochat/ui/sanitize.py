"""Final-exit sanitizer for all UI-visible agent text.

This is the LAST line of defense: every piece of text rendered in the
UI passes through :func:`sanitize_visible_text`.  It removes internal
reasoning blocks, self-talk about regeneration, parsing-error echoes,
and tag cleanup residue.

Must be applied at EVERY render exit (st.markdown, st.write,
placeholder.markdown, etc.) and also to streaming accumulators.
"""

from __future__ import annotations

import re
from typing import Any

# ═══════════════════════════════════════════════════════════════════
# XML internal-reasoning tags (paired block removal with content)
# ═══════════════════════════════════════════════════════════════════

_INTERNAL_TAGS = (
    "think", "thinking", "reasoning", "analysis", "reflection",
    "scratchpad", "chain_of_thought", "chain-of-thought",
    "self_critique", "self-critique", "inner_monologue",
    "inner-monologue",
)

_PAIRED_BLOCK_RE = re.compile(
    r"<(?:" + "|".join(_INTERNAL_TAGS) + r")>(.*?)</(?:" + "|".join(_INTERNAL_TAGS) + r")>",
    re.IGNORECASE | re.DOTALL,
)

_ANY_TAG_RE = re.compile(
    r"</?(?:" + "|".join(_INTERNAL_TAGS) + r")>",
    re.IGNORECASE,
)

_ALL_XML_TAG_RE = re.compile(r"</?[a-zA-Z_][\w:-]*\s*/?>")

# ═══════════════════════════════════════════════════════════════════
# Internal reasoning headings — removed WITH their following content
# ═══════════════════════════════════════════════════════════════════

_INTERNAL_HEADING_PATTERNS = (
    r"\*\*\s*思考过程\s*[:：]\*\*",
    r"思考过程\s*[:：]",
    r"内部推理\s*[:：]",
    r"推理过程\s*[:：]",
    r"推理草稿\s*[:：]",
    r"自我批评\s*[:：]",
    r"self-critique\s*[:：]",
    r"analysis\s*[:：]",
    r"reasoning\s*[:：]",
    r"chain\s*[- ]?of\s*[- ]?thought\s*[:：]",
    r"scratchpad\s*[:：]",
    r"内部独白\s*[:：]",
    r"think\s*[:：]",
)

# A heading line + its content runs until a blank line or a
# public-section marker.
_INTERNAL_SECTION_RE = re.compile(
    r"(?:^|\n)\s*(?:"
    + "|".join(_INTERNAL_HEADING_PATTERNS)
    + r")[^\n]*(?:\n(?!\n|#{1,6}\s|(?:结论|依据|方法|建议|不确定性|局限|安全|结论\s*[:：]))[^\n]*)*",
    re.IGNORECASE,
)

# ═══════════════════════════════════════════════════════════════════
# Self-talk / regeneration phrases — lines containing these are dropped
# ═══════════════════════════════════════════════════════════════════

_SELF_TALK_PATTERNS = (
    "用户要求我",
    "用户指出",
    "我需要",
    "我应该",
    "上一轮回复",
    "重新生成回复",
    "确保每次回复都包含思考过程",
    "ensure.*(think|thought|reasoning)",
    "include.*(thinking process|reasoning)",
    "标签结尾",
    "标签开始",
    r"标签\s*[。.]",
    "according to the instruction",
    "as instructed",
    "let me re-?generate",
    "let me think",
    "i need to (think|reason)",
    "i should (think|reason|include)",
)

_SELF_TALK_LINE_RE = re.compile(
    r"(?:^|\n)[^\n]*(?:"
    + "|".join(_SELF_TALK_PATTERNS)
    + r")[^\n]*",
    re.IGNORECASE,
)

# ═══════════════════════════════════════════════════════════════════
# Tag residue
# ═══════════════════════════════════════════════════════════════════

_TAG_RESIDUE_RE = re.compile(
    r"(?:^|\n)\s*标签\s*(?:结尾|开始|结束)?\s*[。.]?\s*",
    re.IGNORECASE,
)

_ORPHAN_RESIDUE_RE = re.compile(
    r"标签\s*(?:结尾|开始|结束)\s*[。.]?",
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════════════
# Fallback
# ═══════════════════════════════════════════════════════════════════

FALLBACK_MESSAGE = (
    "你好，我是 Biochat，一个基于 Biochat 改造的生物医学 AI Agent，"
    "可以帮助进行生物医学问题分析、工具调用、文献/数据库检索和抗体设计流程辅助。"
)


def sanitize_visible_text(text: Any) -> str:
    """Sanitize any UI-visible text from agent/LLM/tool output.

    Applies in order:
    1. Remove paired internal reasoning blocks (``<think>…</think>``).
    2. Remove internal reasoning heading sections (思考过程/内部推理/…).
    3. Remove self-talk lines (用户要求我/重新生成回复/…).
    4. Remove all remaining XML-like tags and residue.
    5. Collapse whitespace.

    Args:
        text: Any text-like value (str or coercible).

    Returns:
        Clean user-facing text.  Empty string if nothing visible remains.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return ""

    if not text.strip():
        return ""

    result = text

    # 1. Paired internal blocks (content removed)
    result = _PAIRED_BLOCK_RE.sub("", result)

    # 2. Internal heading sections (heading + following content)
    result = _INTERNAL_SECTION_RE.sub("", result)

    # 3. Self-talk / regeneration lines
    result = _SELF_TALK_LINE_RE.sub("", result)

    # 4. Remaining internal tags + all XML tags
    result = _ANY_TAG_RE.sub("", result)
    result = _ALL_XML_TAG_RE.sub("", result)

    # 5. Tag residue
    result = _TAG_RESIDUE_RE.sub("", result)
    result = _ORPHAN_RESIDUE_RE.sub("", result)

    # 6. Collapse blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()


# ═══════════════════════════════════════════════════════════════════
# Processing trace whitelist
# ═══════════════════════════════════════════════════════════════════

TRACE_EVENT_LABELS = {
    "planning": "🧭 正在规划任务...",
    "retrieving": "🔎 正在检索相关工具、数据库和知识库...",
    "executing": "🧪 正在执行工具...",
    "summarizing": "📝 正在生成摘要...",
    "done": "✅ 处理完成",
    "error": "⚠️ 处理遇到错误",
}

_TRACE_ALLOWED_KEYS = frozenset({"status", "status_detail"})


def render_trace_event(event: Any) -> str:
    """Render a trace event using the WHITELIST of status labels only.

    Never renders ``event["content"]``, ``event["message"]``,
    ``event["raw"]``, ``event["output"]``, or ``event["state"]``.

    Args:
        event: A dict-like event from the service layer, or a status
               string matching a key in :data:`TRACE_EVENT_LABELS`.

    Returns:
        A whitelisted label string.
    """
    if isinstance(event, str):
        return TRACE_EVENT_LABELS.get(event, event)

    if isinstance(event, dict):
        status = event.get("status", "")
        if status in TRACE_EVENT_LABELS:
            return TRACE_EVENT_LABELS[status]
        # Fallback: only use explicit whitelist-safe status_detail
        detail = event.get("status_detail", "")
        if isinstance(detail, str) and detail.strip():
            return sanitize_visible_text(detail)
        return TRACE_EVENT_LABELS.get("error", "")

    return ""
