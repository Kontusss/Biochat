"""Code execution utilities — deprecated legacy wrappers.

The agent workflow routes all generated code through the
execution-policy boundary (``biochat.execution``); these helpers remain
only for direct legacy callers and delegate to a module-level trusted
``HostCodeExecutor`` so their behaviour stays identical.

.. warning::
   ``execute_with_thread_timeout`` uses ``ctypes`` to terminate a
   running Python thread, which is inherently unsafe.  It is retained
   only for backward compatibility; the executor boundary is the
   supported path.
"""

from __future__ import annotations

import ctypes
import os
import queue
import threading
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from biochat.execution.host import HostCodeExecutor

from biochat.execution import format_result
from biochat.execution.base import LEGACY_DEFAULT_TIMEOUT_SECONDS

# Shared trusted backend for the deprecated wrapper functions below.
# Created lazily so importing this module stays side-effect free.
_TRUSTED_HOST_EXECUTOR: "HostCodeExecutor | None" = None


def _get_trusted_host_executor() -> "HostCodeExecutor":
    global _TRUSTED_HOST_EXECUTOR
    if _TRUSTED_HOST_EXECUTOR is None:
        from biochat.execution.host import HostCodeExecutor as _Host

        _TRUSTED_HOST_EXECUTOR = _Host()
    return _TRUSTED_HOST_EXECUTOR


# ═══════════════════════════════════════════════════════════════
# R / Bash / CLI execution (deprecated wrappers)
# ═══════════════════════════════════════════════════════════════

def execute_r_script(code: str) -> str:
    """Deprecated: run *code* through ``Rscript`` via the trusted host executor."""
    result = _get_trusted_host_executor().execute_r(
        code, timeout=LEGACY_DEFAULT_TIMEOUT_SECONDS, session_id="legacy"
    )
    return format_result(result)


def execute_bash_script(script: str) -> str:
    """Deprecated: run *script* as a Bash script via the trusted host executor."""
    result = _get_trusted_host_executor().execute_bash(
        script, timeout=LEGACY_DEFAULT_TIMEOUT_SECONDS, session_id="legacy"
    )
    return format_result(result)


def execute_cli_command(command: str) -> str:
    """Deprecated: run a single CLI command via the trusted host executor."""
    result = _get_trusted_host_executor().execute_cli(
        command, timeout=LEGACY_DEFAULT_TIMEOUT_SECONDS, session_id="legacy"
    )
    return format_result(result)


# ═══════════════════════════════════════════════════════════════
# Timeout wrapper (thread-based — see warning in module docstring)
# ═══════════════════════════════════════════════════════════════

def execute_with_thread_timeout(
    func: Callable,
    args: list | None = None,
    kwargs: dict | None = None,
    timeout: int = 600,
) -> Any:
    """Run *func* in a daemon thread with a wall-clock timeout.

    .. warning::
       Thread termination uses ``ctypes.pythonapi.PyThreadState_SetAsyncExc``,
       which is inherently unsafe and can leave locks / resources in
       an inconsistent state.  This is preserved from the original
       implementation for backward compatibility.  For production,
       consider ``subprocess``-based isolation instead.

    Returns:
        ``func(*args, **kwargs)`` result, or an error string on timeout.
    """
    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}

    result_queue: queue.Queue = queue.Queue()

    def _worker() -> None:
        try:
            result_queue.put(("success", func(*args, **kwargs)))
        except Exception as exc:
            result_queue.put(("error", str(exc)))

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        # Unsafe termination (preserved from original)
        tid = thread.ident
        if tid is not None:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_long(tid), ctypes.py_object(SystemExit)
            )
        return (
            f"ERROR: Code execution timed out after {timeout} seconds. "
            f"Please try with simpler inputs or break your task into smaller steps."
        )

    try:
        status, result = result_queue.get(block=False)
        return result if status == "success" else f"Error in execution: {result}"
    except queue.Empty:
        return "Error: Execution completed but no result was returned"


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _safe_unlink(path: str) -> None:
    """Best-effort file deletion."""
    try:
        os.unlink(path)
    except OSError:
        pass


# ── Backward-compatible aliases ─────────────────────────────────
run_r_code = execute_r_script
run_bash_script = execute_bash_script
run_cli_command = execute_cli_command
run_with_timeout = execute_with_thread_timeout
