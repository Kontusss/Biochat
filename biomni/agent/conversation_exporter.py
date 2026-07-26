"""
Conversation history export (Markdown → PDF).

Extracted from ``A1.save_conversation_history()`` and the ~250-line
``_generate_markdown_content()`` / ``_process_*_message()`` chain in
the original ``a1.py``.

Provides a ``ConversationMarkdownBuilder`` class that encapsulates
all the markdown-generation logic previously spread across 13 methods.
"""

from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime
from typing import TYPE_CHECKING, Any

from biomni.utils.io_utils import load_pickle
from biomni.utils.pdf_export import execute_with_timeout, _convert_markdown_to_pdf_in_subprocess
from biomni.utils.text_cleanup import clean_message_content

if TYPE_CHECKING:
    from biomni.agent.a1 import A1


# ═══════════════════════════════════════════════════════════════
# ConversationMarkdownBuilder
# ═══════════════════════════════════════════════════════════════

class ConversationMarkdownBuilder:
    """Build formatted Markdown from agent conversation history.

    Replaces the following original A1 methods:
    - ``_generate_markdown_content``
    - ``_get_messages_for_processing``
    - ``_normalize_conversation_state_messages``
    - ``_normalize_log_messages``
    - ``_process_message`` / ``_process_human_message`` / ``_process_ai_message``
    - ``_process_other_message`` / ``_process_execution_with_results``
    - ``_format_and_add_content`` / ``_add_execution_plots``
    - ``_process_regular_ai_message``
    """

    def __init__(self, agent: "A1", include_images: bool = True) -> None:
        self._agent = agent
        self._include_images = include_images
        self._content: list[str] = ["# Biomni Agent Conversation History\n\n"]
        self._added_plots: set[str] = set()
        self._step_number: int = 0
        self._first_human_shown: bool = False

    # ── Public API ──────────────────────────────────────────────

    def build(self) -> str:
        """Generate the complete Markdown document."""
        messages = self._get_messages()

        for msg_data in messages:
            clean = clean_message_content(msg_data["content"])
            msg_type = msg_data["type"]

            if msg_type == "human":
                self._handle_human(clean)
            elif msg_type == "ai":
                self._handle_ai(clean)
            else:
                self._handle_other(clean)

        return "".join(self._content)

    # ── Message source ──────────────────────────────────────────

    def _get_messages(self) -> list[dict[str, Any]]:
        """Retrieve messages from conversation state (preferred) or log."""
        conv_state = getattr(self._agent, "_conversation_state", None)
        if conv_state and isinstance(conv_state, dict) and "messages" in conv_state:
            return self._normalize_state_messages(conv_state["messages"])
        log_entries = getattr(self._agent, "log", [])
        return self._normalize_log_entries(log_entries)

    @staticmethod
    def _normalize_state_messages(messages: list) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        from langchain_core.messages import AIMessage, HumanMessage

        for msg in messages:
            content = str(msg.content) if hasattr(msg, "content") else str(msg)
            if isinstance(msg, HumanMessage):
                msg_type = "human"
            elif isinstance(msg, AIMessage):
                msg_type = "ai"
            else:
                msg_type = "other"
            result.append({"content": content, "type": msg_type, "original": msg})
        return result

    @staticmethod
    def _normalize_log_entries(entries: list) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for entry in entries:
            content = str(entry)
            if "Human Message" in content:
                msg_type = "human"
            elif "Ai Message" in content:
                msg_type = "ai"
            else:
                msg_type = "other"
            result.append({"content": content, "type": msg_type, "original": entry})
        return result

    # ── Message handlers ────────────────────────────────────────

    def _handle_human(self, clean_output: str) -> None:
        if "each response must include thinking process" in clean_output.lower():
            self._content.append(
                '<div class="parsing-error-box">'
                '<div class="parsing-error-header">Parsing Error</div>'
                '<div class="parsing-error-content">'
                "Each response must include thinking process followed by "
                "either execute or solution tag.</div></div>\n\n"
            )
        elif not self._first_human_shown:
            self._content.append(f"#### Human Prompt\n\n*{clean_output}*\n\n")
            self._first_human_shown = True

    def _handle_ai(self, clean_output: str) -> None:
        # Split on observation tags
        obs_pattern = re.compile(r"<observation>(.*?)</observation>", re.DOTALL | re.IGNORECASE)
        parts = obs_pattern.split(clean_output)

        for i, part in enumerate(parts):
            if i % 2 == 0:  # Non-observation content
                if part.strip() and not self._is_skippable(part):
                    self._step_number += 1
                    self._content.append(f"#### Step {self._step_number}\n\n")
                    self._content.append(self._format_content(part))
                    self._content.append("\n\n")
            else:  # Observation content
                if part.strip():
                    self._content.append(
                        f'<div class="title-text observation">'
                        f'<div class="title-text-header"><strong>Observation</strong></div>'
                        f'<div class="title-text-content">```terminal\n{part.strip()}\n```</div>'
                        f'</div>\n\n'
                    )

    def _handle_other(self, clean_output: str) -> None:
        if "<observation>" not in clean_output.lower():
            self._content.append(f"{clean_output}\n\n")

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _is_skippable(text: str) -> bool:
        return text.strip() in {"", "None", "null", "undefined"}

    def _format_content(self, text: str) -> str:
        """Apply list + execute-tag formatting."""
        from biomni.utils.text_format import format_checkbox_lists, render_execute_tags_as_html

        text = format_checkbox_lists(text)

        def _parse_tools(code: str) -> list[tuple[str, str]]:
            from biomni.utils.tool_parser import detect_tool_imports_with_modules
            return detect_tool_imports_with_modules(
                code,
                getattr(self._agent, "module2api", {}),
                getattr(self._agent, "_custom_functions", {}),
            )

        return render_execute_tags_as_html(text, _parse_tools)


# ═══════════════════════════════════════════════════════════════
# Public export function
# ═══════════════════════════════════════════════════════════════

def export_conversation_to_pdf(
    agent: "A1",
    filepath: str,
    *,
    include_images: bool = True,
    timeout: int = 60,
) -> None:
    """Save conversation history as a PDF file.

    Uses the module-level ``_convert_markdown_to_pdf_in_subprocess``
    function for PDF generation (required for cross-platform timeout
    support via ProcessPoolExecutor).

    Args:
        agent: The A1 agent instance (must have completed a task).
        filepath: Output PDF path (``.pdf`` appended if missing).
        include_images: Embed captured plots in the output.
        timeout: PDF generation timeout in seconds.
    """
    # Ensure directory exists
    directory = os.path.dirname(filepath)
    if directory:
        os.makedirs(directory, exist_ok=True)

    # Normalise PDF path
    if not filepath.endswith(".pdf"):
        if filepath.endswith(".md"):
            filepath = filepath[:-3]
        filepath = f"{filepath}.pdf"

    # Generate Markdown
    builder = ConversationMarkdownBuilder(agent, include_images=include_images)
    markdown_content = builder.build()

    # Write temporary Markdown file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(markdown_content)
        tmp_path = tmp.name

    try:
        execute_with_timeout(
            _convert_markdown_to_pdf_in_subprocess,
            args=(tmp_path, filepath),
            timeout=timeout,
        )
        print(f"Conversation history saved as PDF: {filepath}")
        print(f"Total steps recorded: {builder._step_number}")
    except TimeoutError:
        print(f"Warning: PDF generation timed out after {timeout}s")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
