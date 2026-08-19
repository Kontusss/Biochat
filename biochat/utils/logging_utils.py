"""ANSI logging and LangChain callback utilities.

Replaces ``color_print``, ``PromptLogger``, and ``NodeLogger`` from the
original ``utils.py`` (lines 664-705).
"""

from __future__ import annotations

from langchain_core.callbacks import BaseCallbackHandler

# ── Color palette ───────────────────────────────────────────────
_TEXT_COLORS: dict[str, str] = {
    "blue":   "36;1",
    "yellow": "33;1",
    "pink":   "38;5;200",
    "green":  "32;1",
    "red":    "31;1",
}


def ansi_print(text: str, color: str = "blue") -> None:
    """Print *text* to stdout with ANSI color formatting.

    Args:
        text: The message to print.
        color: One of ``"blue"``, ``"yellow"``, ``"pink"``, ``"green"``, ``"red"``.
    """
    code = _TEXT_COLORS.get(color, "36;1")
    print(f"[{code}m\033[1;3m{text}[0m")


# ── LangChain callbacks ─────────────────────────────────────────

class PromptLogger(BaseCallbackHandler):
    """Log every prompt sent to the chat model (green)."""

    def on_chat_model_start(self, serialized, messages, **kwargs):
        for message in messages[0]:
            ansi_print(message.pretty_repr(), color="green")


class NodeLogger(BaseCallbackHandler):
    """Log LLM responses, agent actions, and tool calls."""

    def on_llm_end(self, response, **kwargs):
        for generations in response.generations:
            for generation in generations:
                ansi_print(generation.message.content, color="yellow")

    def on_agent_action(self, action, **kwargs):
        ansi_print(action.log, color="pink")

    def on_agent_finish(self, finish, **kwargs):
        ansi_print(finish, color="red")

    def on_tool_start(self, serialized, input_str, **kwargs):
        tool_name = serialized.get("name", "unknown")
        ansi_print(f"Calling {tool_name} with inputs: {input_str}", color="pink")

    def on_tool_end(self, output, **kwargs):
        ansi_print(str(output), color="blue")


# ── Backward-compatible aliases ─────────────────────────────────
color_print = ansi_print
