"""
Session Service for Biochat.

Manages multi-session chat history with a pluggable storage backend.
The default backend is in-memory (Python dict).  For persistence,
inject a backend that writes to disk, SQLite, or Redis.

Designed to be used by both Streamlit (via session_state) and a future
FastAPI backend.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Protocol

from biomni.core.logging import get_logger
from biomni.schemas.chat import ChatMessage, MessageRole, SessionInfo

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Storage backend protocol
# ═══════════════════════════════════════════════════════════════════

class SessionStore(Protocol):
    """Pluggable storage backend for chat sessions."""

    def list_sessions(self) -> list[SessionInfo]: ...
    def get_session(self, session_id: str) -> list[ChatMessage]: ...
    def save_session(self, session_id: str, messages: list[ChatMessage]) -> None: ...
    def delete_session(self, session_id: str) -> None: ...


# ═══════════════════════════════════════════════════════════════════
# In-memory store (default)
# ═══════════════════════════════════════════════════════════════════

class InMemorySessionStore:
    """Simple dict-backed session store.  Data lost on process restart."""

    def __init__(self) -> None:
        self._sessions: dict[str, list[ChatMessage]] = {}
        self._meta: dict[str, SessionInfo] = {}

    def list_sessions(self) -> list[SessionInfo]:
        return sorted(
            self._meta.values(),
            key=lambda s: s.updated_at,
            reverse=True,
        )

    def get_session(self, session_id: str) -> list[ChatMessage]:
        return self._sessions.get(session_id, [])

    def save_session(self, session_id: str, messages: list[ChatMessage]) -> None:
        self._sessions[session_id] = messages
        title = "New Chat"
        for msg in messages:
            if msg.role == MessageRole.USER and msg.content.strip():
                title = msg.content.strip()[:60]
                break
        self._meta[session_id] = SessionInfo(
            session_id=session_id,
            title=title,
            message_count=len(messages),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

    def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._meta.pop(session_id, None)


# ═══════════════════════════════════════════════════════════════════
# SessionService
# ═══════════════════════════════════════════════════════════════════

class SessionService:
    """High-level session management for Biochat conversations.

    Usage::

        sessions = SessionService()
        sid = sessions.create_session()
        sessions.add_message(sid, ChatMessage(role=MessageRole.USER, content="..."))
        history = sessions.get_history(sid)
    """

    MAX_SESSIONS: int = 50
    MAX_MESSAGES_PER_SESSION: int = 200

    def __init__(self, store: SessionStore | None = None) -> None:
        self._store = store or InMemorySessionStore()

    # ── CRUD ─────────────────────────────────────────────────────

    def create_session(self, title: str = "New Chat") -> str:
        """Create a new empty session and return its ID."""
        session_id = str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()
        self._store._meta[session_id] = SessionInfo(  # type: ignore[union-attr]
            session_id=session_id,
            title=title,
            created_at=now,
            updated_at=now,
        )
        self._store.save_session(session_id, [])
        self._enforce_limits()
        return session_id

    def get_session(self, session_id: str) -> list[ChatMessage]:
        """Get all messages for a session."""
        return self._store.get_session(session_id)

    def add_message(self, session_id: str, message: ChatMessage) -> None:
        """Append a message to the session history."""
        messages = self._store.get_session(session_id)
        if len(messages) >= self.MAX_MESSAGES_PER_SESSION:
            messages = messages[-self.MAX_MESSAGES_PER_SESSION + 1:]
        messages.append(message)
        self._store.save_session(session_id, messages)

    def delete_session(self, session_id: str) -> None:
        """Delete a session and all its messages."""
        self._store.delete_session(session_id)

    def list_sessions(self) -> list[SessionInfo]:
        """List all sessions, most recent first."""
        return self._store.list_sessions()

    def get_history(self, session_id: str) -> list[dict]:
        """Return session history as a list of dicts (suitable for JSON)."""
        messages = self._store.get_session(session_id)
        return [m.to_dict() for m in messages]

    def clear_session(self, session_id: str) -> None:
        """Remove all messages from a session but keep the session."""
        self._store.save_session(session_id, [])

    # ── Limits ───────────────────────────────────────────────────

    def _enforce_limits(self) -> None:
        """Drop oldest sessions if we exceed MAX_SESSIONS."""
        sessions = self._store.list_sessions()
        if len(sessions) > self.MAX_SESSIONS:
            for old in sessions[self.MAX_SESSIONS:]:
                self._store.delete_session(old.session_id)
            logger.info(
                "Pruned %d old sessions (limit: %d)",
                len(sessions) - self.MAX_SESSIONS,
                self.MAX_SESSIONS,
            )
