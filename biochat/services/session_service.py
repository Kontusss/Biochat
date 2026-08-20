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

from biochat.core.logging import get_logger
from biochat.schemas.chat import ChatMessage, MessageRole, SessionInfo

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Storage backend protocol
# ═══════════════════════════════════════════════════════════════════

class SessionStore(Protocol):
    """Pluggable storage backend for chat sessions."""

    def list_sessions(self) -> list[SessionInfo]: ...
    def get_session(self, session_id: str) -> list[ChatMessage]: ...
    def save_session(self, session_id: str, messages: list[ChatMessage]) -> None: ...
    def get_session_info(self, session_id: str) -> SessionInfo | None: ...
    def save_session_info(self, info: SessionInfo) -> None: ...
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
        return list(self._sessions.get(session_id, []))

    def save_session(self, session_id: str, messages: list[ChatMessage]) -> None:
        self._sessions[session_id] = list(messages)
        previous = self._meta.get(session_id)
        now = datetime.now(timezone.utc).isoformat()
        self._meta[session_id] = SessionInfo(
            session_id=session_id,
            title=self._message_title(messages, previous.title if previous else "New Chat"),
            message_count=len(messages),
            created_at=previous.created_at if previous else now,
            updated_at=now,
            model_name=previous.model_name if previous else "",
        )

    def get_session_info(self, session_id: str) -> SessionInfo | None:
        return self._meta.get(session_id)

    def save_session_info(self, info: SessionInfo) -> None:
        self._meta[info.session_id] = info

    def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._meta.pop(session_id, None)

    @staticmethod
    def _message_title(messages: list[ChatMessage], fallback: str) -> str:
        for message in messages:
            if message.role == MessageRole.USER and message.content.strip():
                return message.content.strip()[:60]
        return fallback


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
        self._store.save_session(session_id, [])
        self._store.save_session_info(SessionInfo(
            session_id=session_id,
            title=title,
            created_at=now,
            updated_at=now,
        ))
        self._enforce_limits()
        return session_id

    def get_session(self, session_id: str) -> list[ChatMessage]:
        """Get all messages for a session."""
        return list(self._store.get_session(session_id))

    def add_message(self, session_id: str, message: ChatMessage) -> None:
        """Append a message to the session history."""
        messages = list(self._store.get_session(session_id))
        if len(messages) >= self.MAX_MESSAGES_PER_SESSION:
            messages = messages[-self.MAX_MESSAGES_PER_SESSION + 1:]
        messages.append(message)
        self._save_session(session_id, messages)

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
        self._save_session(session_id, [])

    def _save_session(self, session_id: str, messages: list[ChatMessage]) -> None:
        """Save messages and update their session metadata through the store protocol."""
        self._store.save_session(session_id, list(messages))
        previous = self._store.get_session_info(session_id)
        now = datetime.now(timezone.utc).isoformat()
        self._store.save_session_info(SessionInfo(
            session_id=session_id,
            title=self._message_title(messages, previous.title if previous else "New Chat"),
            message_count=len(messages),
            created_at=previous.created_at if previous else now,
            updated_at=now,
            model_name=previous.model_name if previous else "",
        ))

    @staticmethod
    def _message_title(messages: list[ChatMessage], fallback: str) -> str:
        for message in messages:
            if message.role == MessageRole.USER and message.content.strip():
                return message.content.strip()[:60]
        return fallback

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
