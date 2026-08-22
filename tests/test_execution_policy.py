"""Behavioral tests for the execution-policy boundary.

Every test names a production break: the default-disabled refusal, the
explicit opt-in selection, session-scoped Python namespaces, process-group
termination on bash timeout, per-session custom-function registration, and
namespace cleanup.
"""

from __future__ import annotations

import dataclasses
import os
import time
import uuid

import pytest

from biochat.core.settings import BiochatSettings
from biochat.execution import (
    CodeExecutor,
    DisabledCodeExecutor,
    ExecutionResult,
    HostCodeExecutor,
    create_code_executor,
    format_result,
)


# ── Factory selection: secure default vs explicit opt-in ──────────


def test_default_executor_refuses_python():
    """A default settings object must never yield an executing executor."""
    executor = create_code_executor(BiochatSettings())
    result = executor.execute_python("print('unsafe')", timeout=1, session_id="s1")
    assert result.status == "disabled"
    assert "BIOCHAT_ALLOW_HOST_CODE_EXECUTION" in result.message


def test_explicit_host_setting_selects_host_executor():
    settings = BiochatSettings(allow_host_code_execution=True)
    assert isinstance(create_code_executor(settings), HostCodeExecutor)


def test_disabled_executor_returns_structured_results_without_raising():
    executor = DisabledCodeExecutor()
    for call in (
        lambda: executor.execute_python("1", timeout=1, session_id="s"),
        lambda: executor.execute_r("1", timeout=1, session_id="s"),
        lambda: executor.execute_bash("true", timeout=1, session_id="s"),
        lambda: executor.execute_cli("true", timeout=1, session_id="s"),
    ):
        result = call()
        assert result.status == "disabled"
        assert result.stdout == ""


def test_executors_satisfy_the_code_executor_protocol():
    assert isinstance(HostCodeExecutor(), CodeExecutor)
    assert isinstance(DisabledCodeExecutor(), CodeExecutor)


# ── Immutable execution result ────────────────────────────────────


def test_execution_result_is_immutable():
    result = ExecutionResult(status="ok")
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.status = "error"


# ── Host executor: session-scoped Python namespaces ───────────────


def test_host_python_namespaces_are_session_scoped():
    executor = HostCodeExecutor()
    executor.execute_python("secret = 7", timeout=1, session_id="a")
    result = executor.execute_python(
        "print(globals().get('secret'))", timeout=1, session_id="b"
    )
    assert result.stdout.strip() == "None"


def test_host_python_state_persists_within_one_session():
    executor = HostCodeExecutor()
    executor.execute_python("counter = 41 + 1", timeout=1, session_id="a")
    result = executor.execute_python("print(counter)", timeout=1, session_id="a")
    assert result.stdout.strip() == "42"


def test_custom_functions_register_per_namespace():
    def double(value):
        return value * 2

    executor = HostCodeExecutor()
    executor.register_function("a", "double", double)

    ok = executor.execute_python("print(double(21))", timeout=1, session_id="a")
    assert ok.stdout.strip() == "42"

    missing = executor.execute_python("print(double(1))", timeout=1, session_id="b")
    assert missing.status == "error"


def test_clear_session_removes_the_namespace():
    executor = HostCodeExecutor()
    executor.execute_python("secret = 7", timeout=1, session_id="a")
    executor.clear_session("a")
    result = executor.execute_python(
        "print(globals().get('secret'))", timeout=1, session_id="a"
    )
    assert result.stdout.strip() == "None"


def test_host_python_captures_stdout_and_exceptions():
    executor = HostCodeExecutor()
    ok = executor.execute_python("print('hello')", timeout=1, session_id="a")
    assert ok.status == "ok"
    assert ok.stdout.strip() == "hello"

    bad = executor.execute_python("1 / 0", timeout=1, session_id="a")
    assert bad.status == "error"
    assert "ZeroDivisionError" in bad.message


# ── Host executor: subprocess timeouts kill the process group ─────


def _probe_process_alive(probe: str) -> bool:
    """True when any process carries the probe marker in its environment."""
    needle = f"_BIOCHAT_PROBE={probe}"
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/environ", "rb") as fh:
                environ = fh.read().decode("utf-8", "replace")
        except OSError:
            continue
        if needle in environ.split("\0")[0] or needle in environ:
            return True
    return False


def test_bash_timeout_terminates_process_group():
    executor = HostCodeExecutor()
    probe = uuid.uuid4().hex
    script = (
        f'_BIOCHAT_PROBE="{probe}" sleep 30 < /dev/null &\n'
        "wait\n"
    )
    result = executor.execute_bash(script, timeout=0.5, session_id="a")
    assert result.status == "timeout"

    deadline = time.monotonic() + 10
    while _probe_process_alive(probe) and time.monotonic() < deadline:
        time.sleep(0.2)
    assert not _probe_process_alive(probe), "timed-out bash group left live processes"


def test_cli_timeout_also_reports_timeout_status():
    executor = HostCodeExecutor()
    result = executor.execute_cli("sleep 30", timeout=0.4, session_id="a")
    assert result.status == "timeout"


def test_bash_failure_travels_as_error_with_stderr():
    executor = HostCodeExecutor()
    result = executor.execute_bash("echo boom >&2\nexit 3", timeout=5, session_id="a")
    assert result.status == "error"
    assert "boom" in result.stderr


# ── Observation-string conversion contract ────────────────────────


def test_format_result_maps_results_to_legacy_observation_text():
    assert format_result(ExecutionResult(status="ok", stdout="hi")) == "hi"
    assert format_result(
        ExecutionResult(status="disabled", message="BIOCHAT_ALLOW_HOST_CODE_EXECUTION=true enables it.")
    ).startswith("Code execution is disabled:")
    assert "timed out" in format_result(
        ExecutionResult(status="timeout", message="execution timed out after 1 seconds.")
    )
    assert format_result(
        ExecutionResult(status="error", stderr="kaput", message="kaput")
    ).startswith("Error")
