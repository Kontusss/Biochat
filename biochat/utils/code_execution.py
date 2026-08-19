"""Code execution utilities — Python / R / Bash with timeout support.

Replaces ``run_r_code``, ``run_bash_script``, ``run_cli_command``,
and ``run_with_timeout`` from the original ``utils.py`` (lines 25-242).

.. warning::
   ``execute_with_thread_timeout`` uses ``ctypes`` to terminate a
   running Python thread, which is inherently unsafe.  Prefer
   subprocess-based isolation for production use.
"""

from __future__ import annotations

import ctypes
import os
import queue
import shlex
import subprocess
import tempfile
import threading
from typing import Any, Callable


# ═══════════════════════════════════════════════════════════════
# R / Bash / CLI execution
# ═══════════════════════════════════════════════════════════════

def execute_r_script(code: str) -> str:
    """Run *code* through ``Rscript``.

    Writes the code to a temporary ``.R`` file, executes it, and
    returns stdout (or stderr on non-zero exit).
    """
    if not code.strip():
        return "Error: Empty R script"

    with tempfile.NamedTemporaryFile(
        suffix=".R", mode="w", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(code)
        tmp_path = fh.name

    try:
        result = subprocess.run(
            ["Rscript", tmp_path],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return f"Error running R code:\n{result.stderr}"
        return result.stdout
    finally:
        _safe_unlink(tmp_path)


def execute_bash_script(script: str) -> str:
    """Run *script* as a Bash script.

    Writes to a temporary ``.sh`` file, makes it executable, and runs
    it in the current working directory with the current environment.
    """
    script = script.strip()
    if not script:
        return "Error: Empty script"

    lines: list[str] = []
    if not script.startswith("#!"):
        lines.append("#!/bin/bash")
    if "set -e" not in script:
        lines.append("set -e")
    lines.append(script)

    with tempfile.NamedTemporaryFile(
        suffix=".sh", mode="w", delete=False, encoding="utf-8"
    ) as fh:
        fh.write("\n".join(lines))
        tmp_path = fh.name

    os.chmod(tmp_path, 0o755)

    try:
        result = subprocess.run(
            [tmp_path],
            shell=True, capture_output=True, text=True,
            env=os.environ.copy(), cwd=os.getcwd(),
        )
        if result.returncode != 0:
            return (
                f"Error running Bash script "
                f"(exit code {result.returncode}):\n{result.stderr}"
            )
        return result.stdout
    finally:
        _safe_unlink(tmp_path)


def execute_cli_command(command: str) -> str:
    """Run a single CLI command via ``subprocess``.

    Uses ``shlex.split`` for proper argument tokenisation.
    """
    command = command.strip()
    if not command:
        return "Error: Empty command"

    args = shlex.split(command)
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        return f"Error running command '{command}':\n{result.stderr}"
    return result.stdout


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
