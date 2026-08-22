"""Execution-policy boundary package.

Public surface::

    from biochat.execution import (
        CodeExecutor,           # runtime-checkable protocol
        ExecutionResult,        # immutable result value
        DisabledCodeExecutor,   # secure default
        HostCodeExecutor,       # explicit trusted-local backend
        create_code_executor,   # settings-driven factory
        format_result,          # ExecutionResult -> legacy observation text
    )

``HostCodeExecutor`` is resolved lazily so that default-disabled
installations never load the subprocess/ctypes machinery at import time.
"""

from biochat.execution.base import (
    CodeExecutor,
    DisabledCodeExecutor,
    ExecutionResult,
    create_code_executor,
    format_result,
)

__all__ = [
    "CodeExecutor",
    "ExecutionResult",
    "DisabledCodeExecutor",
    "HostCodeExecutor",
    "create_code_executor",
    "format_result",
]


def __getattr__(name: str):
    if name == "HostCodeExecutor":
        from biochat.execution.host import HostCodeExecutor

        return HostCodeExecutor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
