"""HTML text formatting for agent outputs.

Replaces the formatting chain from the original ``utils.py``:
``format_execute_tags_in_content``, ``format_observation_as_terminal``,
``format_lists_in_text``, and all their sub-functions.
"""

from __future__ import annotations

import re
from typing import Callable

# ═══════════════════════════════════════════════════════════════
# Pre-compiled patterns
# ═══════════════════════════════════════════════════════════════

_EXECUTE_RE = re.compile(r"<execute>(.*?)</execute>", re.DOTALL)
_SOLUTION_RE = re.compile(r"<solution>(.*?)</solution>", re.DOTALL)
_OBSERVATION_RE = re.compile(r"<observation>(.*?)</observation>", re.DOTALL)

# ═══════════════════════════════════════════════════════════════
# Execute tag formatting
# ═══════════════════════════════════════════════════════════════

def _detect_language_and_tool(code: str) -> tuple[str, str]:
    """Return (language, tool_label) from code markers."""
    if code.startswith(("#!R", "# R code", "# R script")):
        return "r", "R REPL"
    if code.startswith(("#!BASH", "# Bash script")):
        return "bash", "Bash Script"
    if code.startswith("#!CLI"):
        return "bash", "CLI Command"
    return "python", "Python REPL"


def _strip_language_marker(code: str, language: str) -> str:
    """Remove language-specific marker lines from *code*."""
    if language == "r":
        return re.sub(r"^#!R|^# R code|^# R script", "", code, count=1).strip()
    if language == "bash":
        return re.sub(r"^#!BASH|^# Bash script|^#!CLI", "", code, count=1).strip()
    return code


def _format_detected_tool_names(detected: list[tuple[str, str]]) -> str:
    """Join (tool_name, module_name) pairs into a display string."""
    parts: list[str] = []
    for tool_name, module_name in detected:
        if tool_name in ("python_repl", "r_repl"):
            parts.append(tool_name.replace("_", " ").title())
        elif "bash" in tool_name.lower():
            parts.append("Bash Script")
        else:
            display_mod = module_name.split(".")[-1] if "." in module_name else module_name
            parts.append(f"{display_mod} → {tool_name}")
    return ", ".join(sorted(parts))


def _default_tool_html(language: str, tool_name: str) -> str:
    """Return default tools-used HTML when no specific tools are detected."""
    if language == "r":
        label = "R REPL"
    elif language == "bash":
        label = "CLI Command" if tool_name == "CLI Command" else "Bash Script"
    else:
        label = "Python REPL"
    return f'<div class="tools-used"><strong>Tools Used:</strong> {label}</div>'


def _build_tool_call_html(
    code: str, language: str, tool_name: str,
    detected: list[tuple[str, str]],
) -> str:
    """Assemble the HTML for a single <execute> block."""
    block = (
        '<div class="tool-call-highlight">'
        '<div class="tool-call-header"><strong>Code Execution</strong></div>'
        f'<div class="tool-call-input">```{language}\n{code}\n```</div>'
    )
    if detected:
        block += (
            '<div class="tools-used">'
            f'<strong>Tools Used:</strong> {_format_detected_tool_names(detected)}'
            '</div>'
        )
    else:
        block += _default_tool_html(language, tool_name)
    block += "</div>"
    return block


def render_execute_tags_as_html(
    content: str,
    parse_tool_calls_func: Callable[[str], list[tuple[str, str]]],
) -> str:
    """Replace all ``<execute>...</execute>`` blocks with styled HTML.

    Args:
        content: Raw agent output.
        parse_tool_calls_func: A callable that takes code (str) and returns
                               a list of ``(tool_name, module_name)`` tuples.

    Returns:
        Content with execute/solution tags converted to HTML blocks.
    """

    def _replace_execute(match: re.Match) -> str:
        code = match.group(1).strip()
        language, tool_name = _detect_language_and_tool(code)
        code = _strip_language_marker(code, language)
        detected = parse_tool_calls_func(code)
        return _build_tool_call_html(code, language, tool_name, detected)

    result = _EXECUTE_RE.sub(_replace_execute, content)
    # Also format solution tags in the same pass
    result = _render_solution_tags(result)
    return result


def _render_solution_tags(content: str) -> str:
    """Convert ``<solution>...</solution>`` to styled summary blocks."""

    def _replace(match: re.Match) -> str:
        text = match.group(1).strip()
        return (
            '<div class="title-text summary">'
            '<div class="title-text-header"><strong>Summary and Solution</strong></div>'
            f'<div class="title-text-content">{text}</div>'
            '</div>'
        )

    return _SOLUTION_RE.sub(_replace, content)


# ═══════════════════════════════════════════════════════════════
# Observation formatting
# ═══════════════════════════════════════════════════════════════

_MAX_OBS_LENGTH = 10000


def _split_observation_images(content: str) -> tuple[str, list[str]]:
    """Separate text and base64 images in observation content."""
    if "data:image/" not in content:
        return content, []

    parts = content.split("data:image/")
    texts: list[str] = []
    images: list[str] = []

    for i, part in enumerate(parts):
        if i == 0:
            if part.strip():
                texts.append(part.strip())
        else:
            # Find end of base64 data
            end_pos = len(part)
            for marker in ("\n", "\r", " ", "\t", ">", "<", "]", ")", "}"):
                pos = part.find(marker)
                if pos != -1 and pos < end_pos:
                    end_pos = pos
            images.append("data:image/" + part[:end_pos])
            remaining = part[end_pos:].strip()
            if remaining:
                texts.append(remaining)

    return "\n".join(texts), images


def render_observation_block(content: str) -> str | None:
    """Format ``<observation>...</observation>`` content as an HTML terminal block.

    Returns None if the observation is empty / meaningless.
    """
    match = _OBSERVATION_RE.search(content)
    obs = match.group(1).strip() if match else content.strip()

    if not obs or obs in {"", "None", "null", "undefined"}:
        return None

    if len(obs) > _MAX_OBS_LENGTH:
        obs = (
            obs[:_MAX_OBS_LENGTH]
            + f"\n\n[Output truncated — {len(obs)} characters total]"
        )

    text_part, image_parts = _split_observation_images(obs)

    inner = ""
    if text_part:
        inner += f"```terminal\n{text_part}\n```\n\n"
    for img in image_parts:
        inner += f"![Plot]({img})\n\n"

    return (
        '<div class="title-text observation">'
        '<div class="title-text-header"><strong>Observation</strong></div>'
        f'<div class="title-text-content">{inner}</div>'
        '</div>'
    )


# ═══════════════════════════════════════════════════════════════
# Plan / list formatting
# ═══════════════════════════════════════════════════════════════

_CHECKBOX_RE = re.compile(r"^\d+\.\s*\[[ ✓✗]\]")


def _identify_checkbox_blocks(lines: list[str]) -> list[tuple[str, bool]]:
    """Group lines into blocks, flagging checkbox-list blocks."""
    blocks: list[tuple[str, bool]] = []
    current: list[str] = []
    in_checkbox = False

    for line in lines:
        stripped = line.strip()
        if _CHECKBOX_RE.match(stripped):
            if not in_checkbox:
                if current:
                    blocks.append(("\n".join(current), False))
                current = [line]
                in_checkbox = True
            else:
                current.append(line)
        else:
            if in_checkbox:
                if current:
                    blocks.append(("\n".join(current), True))
                current = []
                in_checkbox = False
            current.append(line)

    if current:
        blocks.append(("\n".join(current), in_checkbox))
    return blocks


def _render_checkbox_list(text: str) -> str:
    """Format a single checkbox-list block into an HTML ul."""
    items: list[str] = []
    has_items = False
    plan_title = "Plan"

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if re.match(r"^(Plan|Updated Plan|Completed Plan)$", line, re.IGNORECASE):
            plan_title = line
            continue
        if _CHECKBOX_RE.match(line):
            has_items = True
            content = re.sub(r"^\d+\.\s*\[[ ✓✗]\]\s*", "", line)
            if "[✓]" in line:
                items.append(f"<li><strong>[x]</strong> {content}</li>")
            elif "[✗]" in line:
                items.append(f"<li><strong>[ ]</strong> {content}</li>")
            else:
                items.append(f"<li><strong>[ ]</strong> {content}</li>")
        else:
            items.append(line)

    if has_items and items:
        return (
            '<div class="title-text plan">'
            f'<div class="title-text-header"><span class="plan-title">{plan_title}</span></div>'
            '<div class="title-text-content"><ul>'
            + "\n".join(items)
            + '</ul></div></div>'
        )
    return "\n".join(items)


def format_checkbox_lists(text: str) -> str:
    """Pre-process and format checkbox lists in agent output.

    1. Removes bold formatting from plan titles.
    2. Strips emojis (for PDF output).
    3. Identifies checkbox blocks and converts to HTML.
    """
    from biomni.utils.text_cleanup import strip_emojis

    # Pre-process: strip bold from plan titles
    for pattern in (
        r"\*\*([Pp]lan|Updated [Pp]lan|Completed [Pp]lan|Final [Pp]lan):\*\*",
        r"\*\*([Pp]lan|Updated [Pp]lan|Completed [Pp]lan|Final [Pp]lan)\*\*",
    ):
        text = re.sub(pattern, r"\1", text)

    text = strip_emojis(text)
    lines = text.split("\n")
    blocks = _identify_checkbox_blocks(lines)

    result: list[str] = []
    for block_text, is_checkbox in blocks:
        result.append(
            _render_checkbox_list(block_text) if is_checkbox else block_text
        )
    return "\n".join(result)


# ═══════════════════════════════════════════════════════════════
# Execution results helpers
# ═══════════════════════════════════════════════════════════════

def has_execution_results(clean_output: str, execution_results: list | None) -> bool:
    """Return True if *clean_output* contains <execute> and has results."""
    return (
        "<execute>" in clean_output
        and execution_results is not None
        and bool(execution_results)
    )


def find_matching_execution(
    clean_output: str, execution_results: list[dict],
) -> dict | None:
    """Find the execution result matching *clean_output* (bidirectional match)."""
    for exec_result in execution_results:
        trigger = exec_result.get("triggering_message", "")
        if trigger in clean_output or clean_output in trigger:
            return exec_result
    return None


# ── Backward-compatible aliases ─────────────────────────────────
format_execute_tags_in_content = render_execute_tags_as_html
format_observation_as_terminal = render_observation_block
format_lists_in_text = format_checkbox_lists
format_solution_tags_in_content = _render_solution_tags
detect_code_language_and_tool = _detect_language_and_tool
clean_code_content = _strip_language_marker
create_tool_call_block = _build_tool_call_html
format_detected_tools = _format_detected_tool_names
format_default_tool_name = _default_tool_html
process_observation_with_images = _split_observation_images
identify_list_blocks = _identify_checkbox_blocks
format_single_list = _render_checkbox_list
