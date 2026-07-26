"""LangChain ↔ display message conversion.

Replaces ``pretty_print`` and ``langchain_to_gradio_message`` from
the original ``utils.py`` (lines 440-769).
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages.base import get_msg_title_repr
from langchain_core.utils.interactive_env import is_interactive_env


def format_langchain_message_for_display(message: Any, printout: bool = True) -> str:
    """Convert a LangChain message to a display-friendly string.

    Replaces the original ``pretty_print()`` with ``match/case``
    style dispatch (via isinstance checks for Python 3.10+).

    Args:
        message: A LangChain ``BaseMessage`` or a ``tuple``.
        printout: If True, also print to stdout.

    Returns:
        Formatted string representation.
    """
    title: str

    if isinstance(message, tuple):
        title = str(message)
        if printout:
            print(title)
        return title

    if isinstance(getattr(message, "content", None), list):
        title = get_msg_title_repr(
            message.type.title() + " Message", bold=is_interactive_env()
        )
        if message.name is not None:
            title += f"\nName: {message.name}"
        for item in message.content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    title += f"\n{item.get('text', '')}\n"
                elif item.get("type") == "tool_use":
                    title += f"\nTool: {item.get('name', '')}"
                    title += f"\nInput: {item.get('input', '')}"
    else:
        title = get_msg_title_repr(
            message.type.title() + " Message", bold=is_interactive_env()
        )
        if message.name is not None:
            title += f"\nName: {message.name}"
        title += f"\n\n{message.content}"

    if printout:
        print(title)
    return title


def convert_langchain_message_to_gradio(message: Any) -> list[dict[str, Any]]:
    """Convert a LangChain message to Gradio ``ChatMessage``-compatible dicts.

    Replaces ``langchain_to_gradio_message()``.
    """
    role = "user" if getattr(message, "type", None) == "human" else "assistant"

    if isinstance(getattr(message, "content", None), list):
        results: list[dict[str, Any]] = []
        for item in message.content:
            if not isinstance(item, dict):
                continue
            gradio_msg: dict[str, Any] = {"role": role, "content": "", "metadata": {}}
            if item.get("type") == "text":
                text = item.get("text", "").replace("<think>", "\n").replace("</think>", "\n")
                gradio_msg["content"] = text
                results.append(gradio_msg)
            elif item.get("type") == "tool_use":
                name = item.get("name", "unknown")
                if name == "run_python_repl":
                    gradio_msg["metadata"]["title"] = "🛠️ Writing code..."
                    gradio_msg["content"] = (
                        f"##### Code:\n```python\n{item['input'].get('command', '')}\n```\n"
                    )
                else:
                    gradio_msg["metadata"]["title"] = f"🛠️ Used tool `{name}`"
                    inputs = ";".join(f"{k}: {v}" for k, v in item.get("input", {}).items())
                    gradio_msg["metadata"]["log"] = f"🔍 Input -- {inputs}\n"
                gradio_msg["metadata"]["status"] = "pending"
                results.append(gradio_msg)
        return results

    content = str(message.content)
    content = (
        content.replace("<think>", "\n")
        .replace("</think>", "\n")
        .replace("<solution>", "\n")
        .replace("</solution>", "\n")
    )
    return [{"role": role, "content": content, "metadata": {}}]


# ── Backward-compatible aliases ─────────────────────────────────
pretty_print = format_langchain_message_for_display
langchain_to_gradio_message = convert_langchain_message_to_gradio
