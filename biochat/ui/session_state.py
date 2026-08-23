"""Pure UI session-state helpers.

The Streamlit sidebar keeps complete message lists per session: switching
saves the current conversation first, restoring loads the target's copy,
and every new chat gets a fresh UUID.  These helpers are pure functions
over a plain ``dict`` so they are testable without Streamlit.
"""

from __future__ import annotations

import copy
import uuid


def save_ui_session(state: dict) -> None:
    """Snapshot the current messages into ``state["sessions"]``.

    The stored list is a defensive deep copy, so later mutation of the
    live conversation cannot rewrite saved history.
    """
    active_id = state.get("active_session_id")
    if not active_id:
        return
    sessions = state.setdefault("sessions", {})
    entry = sessions.setdefault(active_id, {"title": "New Chat"})
    messages = state.get("messages", [])
    entry["messages"] = copy.deepcopy(list(messages))
    entry["message_count"] = len(entry["messages"])


def create_ui_session(state: dict) -> str:
    """Start a fresh session: save the current one, return the new id."""
    save_ui_session(state)
    new_id = uuid.uuid4().hex
    sessions = state.setdefault("sessions", {})
    sessions[new_id] = {"title": "New Chat", "messages": [], "message_count": 0}
    state["messages"] = []
    state["active_session_id"] = new_id
    return new_id


def switch_ui_session(state: dict, target_id: str) -> None:
    """Save the current conversation and restore *target_id*'s history."""
    sessions = state.setdefault("sessions", {})
    if target_id not in sessions:
        raise KeyError(target_id)
    save_ui_session(state)
    target = sessions[target_id]
    state["messages"] = copy.deepcopy(target.get("messages", []))
    state["active_session_id"] = target_id
