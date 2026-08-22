"""Pure UI session-state, authentication, and exposure-boundary tests.

These cover the pure helpers exactly as the UIs consume them: full
message-list sessions, fresh ids for new chats, constant-time access-code
checks, and the remote-exposure acknowledgement boundary.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from biochat.core.errors import ConfigError
from biochat.core.settings import BiochatSettings


# ── Pure session-state helpers ────────────────────────────────────


def _state(active="a", messages=None, sessions=None):
    return {
        "active_session_id": active,
        "messages": list(messages or []),
        "sessions": dict(sessions or {}),
    }


def test_switch_session_saves_current_and_restores_target():
    from biochat.ui.session_state import switch_ui_session

    state = {
        "active_session_id": "a",
        "messages": [{"role": "user", "content": "A"}],
        "sessions": {
            "b": {"title": "B", "messages": [{"role": "user", "content": "B"}]}
        },
    }
    switch_ui_session(state, "b")
    assert state["sessions"]["a"]["messages"][0]["content"] == "A"
    assert state["messages"][0]["content"] == "B"
    assert state["active_session_id"] == "b"


def test_new_session_uses_a_fresh_id():
    from biochat.ui.session_state import create_ui_session

    state = {"active_session_id": "a", "messages": [], "sessions": {}}
    first = create_ui_session(state)
    second = create_ui_session(state)
    assert first != second


def test_create_session_saves_current_and_starts_empty():
    from biochat.ui.session_state import create_ui_session

    state = _state(
        active="a",
        messages=[{"role": "assistant", "content": "old"}],
        sessions={},
    )
    new_id = create_ui_session(state)
    # The old conversation was preserved under its own id...
    assert state["sessions"]["a"]["messages"][0]["content"] == "old"
    # ...and the UI now points at a fresh, empty session.
    assert state["active_session_id"] == new_id
    assert state["messages"] == []
    assert new_id in state["sessions"]


def test_save_ui_session_snapshots_current_messages():
    from biochat.ui.session_state import save_ui_session

    state = _state(active="a", messages=[{"role": "user", "content": "hi"}])
    save_ui_session(state)
    stored = state["sessions"]["a"]["messages"]
    assert stored == [{"role": "user", "content": "hi"}]
    # Stored list is a defensive copy, not the live object.
    assert stored is not state["messages"]
    state["messages"].append({"role": "user", "content": "mutated"})
    assert len(stored) == 1


def test_switch_to_unknown_session_is_rejected():
    from biochat.ui.session_state import switch_ui_session

    state = _state(active="a")
    with pytest.raises(KeyError):
        switch_ui_session(state, "missing")


# ── Authentication ────────────────────────────────────────────────


def test_access_code_comes_from_settings_not_literal():
    from biochat.ui.auth import verify_access_code

    assert verify_access_code("configured", ["configured"])
    assert not verify_access_code("Biochat2025", ["configured"])


def test_verify_access_code_handles_non_string_candidates():
    from biochat.ui.auth import verify_access_code

    assert not verify_access_code(None, ["configured"])
    assert not verify_access_code(123, ["configured"])
    assert not verify_access_code("x", [])


def test_verify_access_code_uses_constant_time_comparison(monkeypatch):
    """The helper must route through hmac.compare_digest, not == chains."""
    import hmac

    from biochat.ui import auth as auth_module

    calls = []
    real_compare = hmac.compare_digest

    def spy(a, b):
        calls.append((a, b))
        return real_compare(a, b)

    monkeypatch.setattr(auth_module.hmac, "compare_digest", spy)
    assert auth_module.verify_access_code("good", ["bad", "good"]) is True
    assert any(real_compare(c[0], c[1]) for c in calls)


# ── Remote exposure boundary ──────────────────────────────────────


def test_remote_host_requires_auth_or_explicit_acknowledgement():
    from biochat.ui.auth import validate_remote_exposure

    settings = BiochatSettings(access_codes=[], allow_unauthenticated_remote=False)
    with pytest.raises(ConfigError, match="remote"):
        validate_remote_exposure("0.0.0.0", settings)


def test_loopback_without_codes_is_allowed():
    from biochat.ui.auth import validate_remote_exposure

    settings = BiochatSettings(access_codes=[], allow_unauthenticated_remote=False)
    for host in ("127.0.0.1", "localhost", "::1", "[::1]", "127.9.9.9",
                 "0:0:0:0:0:0:0:1", "LocalHost"):
        assert validate_remote_exposure(host, settings) is None


def test_remote_host_with_configured_codes_is_allowed():
    from biochat.ui.auth import validate_remote_exposure

    settings = BiochatSettings(access_codes=["secret"], allow_unauthenticated_remote=False)
    assert validate_remote_exposure("0.0.0.0", settings) is None


def test_remote_host_allowed_with_explicit_acknowledgement():
    from biochat.ui.auth import validate_remote_exposure

    settings = BiochatSettings(access_codes=[], allow_unauthenticated_remote=True)
    assert validate_remote_exposure("192.168.1.10", settings) is None


# ── Launch defaults and CLI ───────────────────────────────────────


def test_launcher_defaults_are_loopback_only():
    import inspect

    from biochat.agent.a1 import A1
    from biochat.agent import ui_launcher
    from biochat.ui import biochat_about, biochat_ui, gradio_legacy

    launchers = [
        A1.launch_gradio_demo,
        A1.launch_biochat_ui,
        ui_launcher.launch_biochat_ui_from_agent,
        biochat_ui.launch_biochat_ui,
        gradio_legacy.launch_legacy_gradio_ui,
        biochat_about.launch_biochat_about,
    ]
    for func in launchers:
        sig = inspect.signature(func)
        assert sig.parameters["server_name"].default == "127.0.0.1", (
            f"{func.__qualname__} does not default to loopback"
        )


def test_effective_require_verification_follows_configured_codes():
    from biochat.ui.auth import effective_require_verification

    with_codes = BiochatSettings(access_codes=["k"])
    without_codes = BiochatSettings(access_codes=[])
    assert effective_require_verification(False, with_codes) is True
    assert effective_require_verification(True, without_codes) is True
    assert effective_require_verification(False, without_codes) is False


def test_chat_stream_forwards_session_and_applied_settings(monkeypatch):
    """The UI chat path must pass applied settings and the session id."""
    from biochat.ui import biochat_streamlit as streamlit_module

    captured: dict = {}

    class _StubService:
        def ensure_initialized(self):
            return None

        def run_task_stream(self, request, **kwargs):
            captured["request"] = request
            yield {
                "status": "completed",
                "content": "ok",
                "answer_so_far": "ok",
                "trace_line": "",
                "language": "",
            }

    def fake_get_agent_service(settings=None):
        captured["settings"] = settings
        return _StubService()

    monkeypatch.setattr(
        "biochat.services.agent_service.get_agent_service", fake_get_agent_service
    )

    sentinel_settings = object()
    events = list(
        streamlit_module.stream_agent_response(
            "question", session_id="ui-session-7", settings=sentinel_settings
        )
    )
    assert any(e.get("status") == "completed" for e in events)
    assert captured["settings"] is sentinel_settings
    assert captured["request"].session_id == "ui-session-7"


def test_settings_default_has_no_hard_coded_access_code():
    import os

    saved = {k: os.environ.get(k) for k in ("BIOCHAT_ACCESS_CODE", "BIOMNI_ACCESS_CODE")}
    for key, _value in saved.items():
        os.environ.pop(key, None)
    try:
        settings = BiochatSettings()
        assert "Biochat2025" not in settings.access_codes
    finally:
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value


def test_cli_rejects_unknown_ui_mode_with_exit_status_2(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "-m", "biochat.ui.cli", "--ui", "bogus"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    assert proc.returncode == 2
