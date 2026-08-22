"""Trusted-local host execution backend.

``HostCodeExecutor`` preserves the legacy behaviour for operators who
explicitly enable ``allow_host_code_execution``:

- Python runs **in-process** (custom callables cannot cross a process
  boundary) in per-session namespaces guarded by per-session locks.
  In-process timeout enforcement reuses the legacy unsafe thread-kill
  approach and is explicitly labelled; it is never selected by default.
- R / Bash / CLI run as subprocesses started with
  ``start_new_session=True`` so the whole process group can be killed
  with ``os.killpg()`` on wall-clock timeout.

This module must not be imported by default code paths — only the
factory in :mod:`biochat.execution.base` instantiates it, and only for
explicitly opted-in settings.
"""

from __future__ import annotations

import io
import os
import queue
import shlex
import signal
import subprocess
import sys
import tempfile
import threading
import ctypes

from biochat.execution.base import LEGACY_DEFAULT_TIMEOUT_SECONDS, ExecutionResult


class HostCodeExecutor:
    """Execute code on the host for explicitly trusted local use.

    State is keyed by session id and held on the *instance* (never at
    module scope): ``_namespaces`` maps a session to its Python globals
    dict and ``_locks`` maps a session to its re-entrant lock.
    """

    # Serialises every in-process Python execution across ALL instances
    # (the agent's executor plus the two legacy wrappers) because the
    # in-process capture swaps the process-global ``sys.stdout``.
    _stdout_gate: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._namespaces: dict[str, dict] = {}
        self._locks: dict[str, threading.RLock] = {}
        self._registry_guard = threading.Lock()

    # ── Session registry helpers ────────────────────────────────

    def _session_lock(self, session_id: str) -> threading.RLock:
        with self._registry_guard:
            return self._locks.setdefault(session_id, threading.RLock())

    def _namespace(self, session_id: str) -> dict:
        with self._registry_guard:
            namespace = self._namespaces.setdefault(session_id, {})
            namespace.setdefault("__name__", f"__biochat_session_{session_id}__")
            return namespace

    def clear_session(self, session_id: str) -> None:
        """Forget the namespace and lock belonging to *session_id*."""
        with self._registry_guard:
            self._namespaces.pop(session_id, None)
            self._locks.pop(session_id, None)

    def register_function(self, session_id: str, name: str, function: object) -> None:
        """Explicitly register a custom callable into one session namespace."""
        if not callable(function):
            raise TypeError(f"Cannot register non-callable '{name}'")
        namespace = self._namespace(session_id)
        namespace[name] = function

    # ── Python (in-process compatibility mode — unsafe) ─────────

    def execute_python(self, code: str, *, timeout: float, session_id: str) -> ExecutionResult:
        """Exec *code* inside this session's namespace.

        UNSAFE BY DESIGN (compatibility mode): execution happens
        in-process because custom callable injection cannot safely
        cross a process boundary.  Timeout enforcement uses the legacy
        asynchronous thread-kill trick, which can leave resources in an
        inconsistent state.  Only reached when host execution was
        explicitly enabled.
        """
        with self._session_lock(session_id), HostCodeExecutor._stdout_gate:
            # The session lock serialises execution, so mutating the live
            # namespace directly preserves the legacy REPL semantics:
            # variables defined in one call persist to the next.
            namespace = self._namespace(session_id)
            buffer = io.StringIO()
            done: queue.Queue[tuple[str, str]] = queue.Queue()

            # Idempotent legacy plot capture; applied outside the timed
            # region so a cold matplotlib import cannot eat the budget.
            _apply_plot_capture_patches()

            previous_stdout = sys.stdout

            def _worker() -> None:
                sys.stdout = buffer
                try:
                    exec(compile(code, "<biochat-host-exec>", "exec"), namespace)  # noqa: S102
                    done.put(("ok", ""))
                except BaseException as exc:  # noqa: BLE001 - boundary reports, never raises
                    done.put(("error", f"{type(exc).__name__}: {exc}"))
                finally:
                    # Only reclaim the global if we still own it — a timed-
                    # out worker whose kill was swallowed by user code must
                    # not re-hijack stdout after the parent restored it.
                    if sys.stdout is buffer:
                        sys.stdout = previous_stdout

            thread = threading.Thread(target=_worker, daemon=True)
            thread.start()
            thread.join(timeout)

            if thread.is_alive():
                # Reclaim the process-global stream immediately so an
                # immortal worker (user code that swallows BaseException)
                # cannot keep it deflected to a dead buffer.
                if sys.stdout is buffer:
                    sys.stdout = previous_stdout
                # Legacy in-process termination (unsafe; preserved for compat).
                tid = thread.ident
                if tid is not None:
                    ctypes.pythonapi.PyThreadState_SetAsyncExc(
                        ctypes.c_long(tid), ctypes.py_object(SystemExit)
                    )
                return ExecutionResult(
                    status="timeout",
                    stdout=buffer.getvalue(),
                    message=f"Python code execution timed out after {timeout} seconds.",
                )

            if done.empty():
                return ExecutionResult(
                    status="error",
                    stdout=buffer.getvalue(),
                    message="execution produced no result",
                )
            status, error_message = done.get_nowait()
            return ExecutionResult(
                status=status,
                stdout=buffer.getvalue(),
                message=error_message,
            )

    # ── Subprocess-backed languages ─────────────────────────────

    def execute_r(self, code: str, *, timeout: float, session_id: str) -> ExecutionResult:
        if not code.strip():
            return ExecutionResult(status="error", message="Empty R script")

        with tempfile.NamedTemporaryFile(
            suffix=".R", mode="w", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(code)
            tmp_path = fh.name
        try:
            return self._run_process(["Rscript", tmp_path], timeout=timeout)
        finally:
            _safe_unlink(tmp_path)

    def execute_bash(self, code: str, *, timeout: float, session_id: str) -> ExecutionResult:
        script = code.strip()
        if not script:
            return ExecutionResult(status="error", message="Empty script")

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
            return self._run_process([tmp_path], timeout=timeout)
        finally:
            _safe_unlink(tmp_path)

    def execute_cli(self, command: str, *, timeout: float, session_id: str) -> ExecutionResult:
        command = command.strip()
        if not command:
            return ExecutionResult(status="error", message="Empty command")

        try:
            args = shlex.split(command)
        except ValueError as exc:
            return ExecutionResult(
                status="error",
                message=f"Invalid command: {exc}",
            )
        return self._run_process(args, timeout=timeout)

    def _run_process(self, args: list[str], *, timeout: float) -> ExecutionResult:
        """Run *args* in its own process group and enforce the wall clock."""
        proc = subprocess.Popen(  # noqa: S603 - args are tokenised above, explicit opt-in
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",  # never fail the boundary on non-UTF8 child output
            start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._terminate_process_group(proc)
            return ExecutionResult(
                status="timeout",
                stdout="",
                stderr="",
                message=f"Code execution timed out after {timeout} seconds.",
            )
        if proc.returncode != 0:
            return ExecutionResult(
                status="error",
                stdout=stdout,
                stderr=stderr,
                message=f"exit code {proc.returncode}: {stderr or ''}".strip(),
            )
        return ExecutionResult(status="ok", stdout=stdout, stderr=stderr)

    @staticmethod
    def _terminate_process_group(proc: subprocess.Popen) -> None:
        """Kill the whole process group, then reap the direct child."""
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        try:
            proc.communicate(timeout=5)
        except Exception:
            try:
                proc.kill()
                proc.communicate(timeout=5)
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _apply_plot_capture_patches() -> None:
    """Best-effort matplotlib capture patches (legacy UI behaviour).

    The legacy REPL monkey-patched ``plt.show``/``plt.savefig`` so the
    UIs could display generated plots; keep that observable behaviour
    for host-mode Python without coupling this module at import time.
    """
    try:
        from biochat.tool.support_tools import _apply_matplotlib_patches

        _apply_matplotlib_patches()
    except Exception:
        pass


def _safe_unlink(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass
