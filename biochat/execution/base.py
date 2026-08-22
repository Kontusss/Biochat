"""Execution-policy boundary: protocol, immutable results, disabled executor.

The agent workflow depends on the ``CodeExecutor`` protocol instead of
importing raw ``exec()`` helpers or subprocess utilities.  Two
implementations ship:

- ``DisabledCodeExecutor`` (secure default) returns structured,
  actionable results instead of executing anything.
- ``HostCodeExecutor`` (see ``biochat.execution.host``) preserves the
  legacy in-process/subprocess behaviour for explicitly opted-in
  trusted-local use.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


# ═══════════════════════════════════════════════════════════════
# Immutable execution result
# ═══════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ExecutionResult:
    """Immutable outcome of one execution attempt.

    Attributes:
        status: One of ``"ok"``, ``"error"``, ``"timeout"``,
            ``"disabled"``.
        stdout: Captured standard output (may be empty).
        stderr: Captured standard error (may be empty).
        message: Human-readable explanation for non-ok statuses.
    """

    status: str
    stdout: str = ""
    stderr: str = ""
    message: str = ""


def format_result(result: ExecutionResult) -> str:
    """Convert an :class:`ExecutionResult` to the legacy observation text.

    Downstream workflow parsing expects a plain string embedded in
    ``<observation>...</observation>`` tags, so this conversion keeps
    the historical shapes: bare stdout for success, an ``Error:``
    prefix for failures, an explicit disabled explanation, and a
    timeout notice.
    """
    if result.status == "disabled":
        return f"Code execution is disabled: {result.message}"
    if result.status == "timeout":
        return (
            f"ERROR: {result.message} "
            f"Please try with simpler inputs or break your task into smaller steps."
        )
    if result.status == "error":
        detail = result.stderr or result.message
        return f"Error: {detail}"
    output = result.stdout
    if result.stderr:
        output += result.stderr
    return output


# ═══════════════════════════════════════════════════════════════
# Executor protocol
# ═══════════════════════════════════════════════════════════════

@runtime_checkable
class CodeExecutor(Protocol):
    """Boundary every execution backend must satisfy."""

    def execute_python(self, code: str, *, timeout: float, session_id: str) -> ExecutionResult: ...

    def execute_r(self, code: str, *, timeout: float, session_id: str) -> ExecutionResult: ...

    def execute_bash(self, code: str, *, timeout: float, session_id: str) -> ExecutionResult: ...

    def execute_cli(self, command: str, *, timeout: float, session_id: str) -> ExecutionResult: ...

    def clear_session(self, session_id: str) -> None: ...


# ═══════════════════════════════════════════════════════════════
# Disabled executor (secure default)
# ═══════════════════════════════════════════════════════════════

_DISABLED_MESSAGE = (
    "{language} execution is disabled by default because generated code "
    "runs unsandboxed on this host. A trusted local operator can enable "
    "it explicitly by setting BIOCHAT_ALLOW_HOST_CODE_EXECUTION=true "
    "(or constructing BiochatSettings(allow_host_code_execution=True))."
)


class DisabledCodeExecutor:
    """Secure-default executor: refuses every language without raising."""

    def execute_python(self, code: str, *, timeout: float, session_id: str) -> ExecutionResult:
        return self._refuse("Python")

    def execute_r(self, code: str, *, timeout: float, session_id: str) -> ExecutionResult:
        return self._refuse("R")

    def execute_bash(self, code: str, *, timeout: float, session_id: str) -> ExecutionResult:
        return self._refuse("Bash")

    def execute_cli(self, command: str, *, timeout: float, session_id: str) -> ExecutionResult:
        return self._refuse("CLI command")

    def clear_session(self, session_id: str) -> None:
        """No state is ever held, so clearing is a no-op."""

    def _refuse(self, language: str) -> ExecutionResult:
        return ExecutionResult(status="disabled", message=_DISABLED_MESSAGE.format(language=language))


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════

def create_code_executor(settings: object) -> CodeExecutor:
    """Select the executor purely from the explicit security setting.

    Host execution is created **only** when
    ``settings.allow_host_code_execution`` is true; every other case —
    including missing attributes — falls back to the disabled executor.
    """
    if bool(getattr(settings, "allow_host_code_execution", False)):
        from biochat.execution.host import HostCodeExecutor

        return HostCodeExecutor()
    return DisabledCodeExecutor()


__all__ = [
    "CodeExecutor",
    "ExecutionResult",
    "DisabledCodeExecutor",
    "create_code_executor",
    "format_result",
]
