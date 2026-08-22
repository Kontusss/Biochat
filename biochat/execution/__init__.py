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
"""

from biochat.execution.base import (
    CodeExecutor,
    DisabledCodeExecutor,
    ExecutionResult,
    create_code_executor,
    format_result,
)
from biochat.execution.host import HostCodeExecutor

__all__ = [
    "CodeExecutor",
    "ExecutionResult",
    "DisabledCodeExecutor",
    "HostCodeExecutor",
    "create_code_executor",
    "format_result",
]
