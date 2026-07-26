"""
Unified Error Hierarchy for Biochat.

Provides typed exceptions that make error handling predictable across
the application.  Every error raised in Biochat should subclass
``BiochatError`` so callers can write ``except BiochatError`` as a
catch-all.

Usage:
    from biomni.core.errors import ConfigError, AgentError

    raise ConfigError("ANTHROPIC_API_KEY is required when source is Anthropic")
"""

from __future__ import annotations


# ═══════════════════════════════════════════════════════════════════
# Base
# ═══════════════════════════════════════════════════════════════════

class BiochatError(Exception):
    """Base class for all Biochat-specific exceptions."""

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.detail = detail


# ═══════════════════════════════════════════════════════════════════
# Configuration errors
# ═══════════════════════════════════════════════════════════════════

class ConfigError(BiochatError):
    """Raised when required configuration is missing or invalid.

    Examples:
        - Missing API key for the selected provider
        - Invalid data path
        - Conflicting configuration options
    """


class MissingApiKeyError(ConfigError):
    """Raised when a required API key is not set."""

    def __init__(self, provider: str) -> None:
        super().__init__(
            f"API key not found for provider '{provider}'. "
            f"Set the appropriate environment variable (see .env.example).",
            detail=f"provider={provider}",
        )


# ═══════════════════════════════════════════════════════════════════
# Agent errors
# ═══════════════════════════════════════════════════════════════════

class AgentError(BiochatError):
    """Base for errors that occur during agent operation."""


class AgentInitError(AgentError):
    """Raised when the agent fails to initialize."""


class AgentTaskError(AgentError):
    """Raised when a task fails during execution."""

    def __init__(
        self,
        message: str,
        *,
        detail: str | None = None,
        task_id: str | None = None,
        partial_output: str | None = None,
    ) -> None:
        super().__init__(message, detail=detail)
        self.task_id = task_id
        self.partial_output = partial_output


class AgentTimeoutError(AgentError):
    """Raised when agent execution exceeds the configured timeout."""


# ═══════════════════════════════════════════════════════════════════
# Execution errors
# ═══════════════════════════════════════════════════════════════════

class ExecutionError(BiochatError):
    """Raised when code execution (Python / R / Bash) fails."""

    def __init__(
        self,
        message: str,
        *,
        detail: str | None = None,
        language: str = "python",
        exit_code: int | None = None,
        stderr: str | None = None,
    ) -> None:
        super().__init__(message, detail=detail)
        self.language = language
        self.exit_code = exit_code
        self.stderr = stderr


# ═══════════════════════════════════════════════════════════════════
# Parsing errors
# ═══════════════════════════════════════════════════════════════════

class ParsingError(BiochatError):
    """Raised when the LLM response cannot be parsed."""


# ═══════════════════════════════════════════════════════════════════
# LLM errors
# ═══════════════════════════════════════════════════════════════════

class LLMError(BiochatError):
    """Raised when the LLM API returns an error."""

    def __init__(
        self,
        message: str,
        *,
        detail: str | None = None,
        provider: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message, detail=detail)
        self.provider = provider
        self.status_code = status_code


# ═══════════════════════════════════════════════════════════════════
# UI errors
# ═══════════════════════════════════════════════════════════════════

class UIError(BiochatError):
    """Raised when a UI operation fails."""
