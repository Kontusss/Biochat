"""
Chat and Agent Request / Response Schemas.

Defines the structured data types used between the UI layer and the
BioAgent service.  All models are plain dataclasses (no pydantic
dependency) for broad compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════

class AgentStatus(str, Enum):
    """Current state of an agent task execution."""

    IDLE = "idle"
    PLANNING = "planning"
    RETRIEVING_TOOLS = "retrieving_tools"
    RUNNING_CODE = "running_code"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    ERROR = "error"
    TIMEOUT = "timeout"


class MessageRole(str, Enum):
    """Chat message roles."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# ═══════════════════════════════════════════════════════════════════
# Chat schemas
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ChatMessage:
    """A single message in a chat conversation."""

    role: MessageRole
    content: str
    trace: str = ""          # High-level processing trace
    status: AgentStatus = AgentStatus.IDLE
    timestamp: str = ""      # ISO 8601
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "content": self.content,
            "trace": self.trace,
            "status": self.status.value,
            "timestamp": self.timestamp,
        }


@dataclass
class ChatRequest:
    """A chat request from the user."""

    message: str
    session_id: str = "default"
    stream: bool = False

    # Optional overrides for this specific request
    llm_model: str | None = None
    timeout_seconds: int | None = None

    def __post_init__(self) -> None:
        # The session id is the canonical conversation identifier; it must
        # be a real, non-empty string so it can never collide with unset.
        if not isinstance(self.session_id, str) or not self.session_id.strip():
            raise ValueError("session_id must be a non-empty string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "session_id": self.session_id,
            "stream": self.stream,
        }


# ═══════════════════════════════════════════════════════════════════
# Agent response schemas
# ═══════════════════════════════════════════════════════════════════

@dataclass
class AgentStep:
    """A single step in the agent's execution trace."""

    step_number: int
    step_type: str        # "thinking", "code_execution", "observation", "solution"
    content: str
    language: str = ""    # "python", "r", "bash"
    duration_ms: float = 0.0
    status: str = "completed"  # "pending", "running", "completed", "error"


@dataclass
class ThinkingStep:
    """A reasoning step extracted from the agent's thinking process."""

    content: str
    plan_items: list[str] = field(default_factory=list)


@dataclass
class AgentResponse:
    """Structured response from the BioAgent service.

    This is the **primary return type** for ``BioAgentService.run_task()``.
    Every field is optional except ``status`` — callers should always
    check ``status`` before consuming other fields.

    Attributes:
        status: Final execution status.
        answer: The cleaned final answer text (Markdown).
        reasoning_trace: High-level trace of the agent's reasoning steps.
        thinking_steps: Detailed step-by-step reasoning.
        tool_calls: List of tools the agent called.
        generated_files: Paths to files generated during execution.
        warnings: Non-fatal warnings collected during execution.
        error: Error message if status is ERROR or TIMEOUT.
        raw_log: The complete raw agent log (for debugging / export).
        execution_steps: Detailed execution step list.
    """

    status: AgentStatus = AgentStatus.IDLE
    answer: str = ""
    reasoning_trace: str = ""
    thinking_steps: list[ThinkingStep] = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)
    generated_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str = ""
    raw_log: str = ""
    execution_steps: list[AgentStep] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True if the task completed without an error."""
        return self.status == AgentStatus.COMPLETED

    @property
    def has_answer(self) -> bool:
        """True if a non-empty answer was produced."""
        return bool(self.answer and self.answer.strip())

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "answer": self.answer,
            "reasoning_trace": self.reasoning_trace,
            "tool_calls": self.tool_calls,
            "generated_files": self.generated_files,
            "warnings": self.warnings,
            "error": self.error,
        }

    # ── Factory methods ──────────────────────────────────────────

    @classmethod
    def error_response(cls, message: str, status: AgentStatus = AgentStatus.ERROR) -> AgentResponse:
        """Convenience constructor for error responses."""
        return cls(status=status, error=message)

    @classmethod
    def busy_response(cls, status: AgentStatus) -> AgentResponse:
        """Convenience constructor for in-progress status updates."""
        return cls(status=status)


# ═══════════════════════════════════════════════════════════════════
# Session schemas
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SessionInfo:
    """Metadata for a single chat session."""

    session_id: str
    title: str = "New Chat"
    message_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    model_name: str = ""
