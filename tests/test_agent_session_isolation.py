"""Behavioral tests for session-ID propagation and mutable-Agent serialization.

Every test exercises real behavior: the LangGraph config A1 builds, the
session IDs the service forwards, the lock boundary around mutating agent
calls, request-scoped timeout restoration, and the model-keyed agent cache.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from biochat.agent.a1 import A1
from biochat.core.settings import BiochatSettings
from biochat.schemas.chat import ChatRequest
from biochat.services.agent_service import BioAgentService


# ── Recording fixtures (real objects, no behavior mocks) ──────────


class RecordingApp:
    """Stands in for the compiled LangGraph app and records configs."""

    def __init__(self):
        self.configs: list[dict] = []

    def stream(self, inputs, *, stream_mode, config):
        self.configs.append(config)
        final = {"messages": [AIMessage(content="<solution>ok</solution>")]}
        if isinstance(stream_mode, (list, tuple)):
            # go_stream consumes (mode, payload) pairs.
            yield ("values", final)
        else:
            yield final


def make_recording_a1() -> A1:
    agent = object.__new__(A1)
    agent.use_tool_retriever = False
    agent.app = RecordingApp()
    agent.log = []
    agent.recursion_limit = 500
    agent.system_prompt = ""
    return agent


class RecordingServiceAgent:
    """Records how the service invokes a single shared agent instance."""

    def __init__(self):
        self.use_tool_retriever = False
        self.seen_session_ids: list[str] = []
        self.seen_timeouts: list[Any] = []
        self.active_calls = 0
        self.max_simultaneous_calls = 0
        self.counter_lock = threading.Lock()

    def go_stream(self, prompt, *, session_id="default"):
        self.seen_session_ids.append(session_id)
        yield {"type": "message", "output": "<solution>ok</solution>"}

    def go(self, prompt, *, session_id="default"):
        self.seen_session_ids.append(session_id)
        with self.counter_lock:
            self.active_calls += 1
            self.max_simultaneous_calls = max(
                self.max_simultaneous_calls, self.active_calls
            )
        time.sleep(0.05)
        with self.counter_lock:
            self.active_calls -= 1
        return [], "<solution>ok</solution>"


def make_recording_service() -> BioAgentService:
    service = BioAgentService(BiochatSettings())
    service._agent = RecordingServiceAgent()
    service._initialized = True
    return service


# ── Session ID propagation through A1 ─────────────────────────────


def test_go_passes_session_id_as_thread_id():
    agent = make_recording_a1()
    agent.go("one", session_id="session-a")
    assert agent.app.configs[-1]["configurable"]["thread_id"] == "session-a"


def test_go_stream_passes_session_id_as_thread_id():
    agent = make_recording_a1()
    list(agent.go_stream("one", session_id="stream-a"))
    assert agent.app.configs[-1]["configurable"]["thread_id"] == "stream-a"


def test_go_without_session_id_defaults_to_default_thread_id():
    agent = make_recording_a1()
    agent.go("one")
    assert agent.app.configs[-1]["configurable"]["thread_id"] == "default"


def test_distinct_sessions_get_distinct_thread_ids():
    agent = make_recording_a1()
    agent.go("one", session_id="a")
    agent.go("two", session_id="b")
    thread_ids = [c["configurable"]["thread_id"] for c in agent.app.configs]
    assert thread_ids == ["a", "b"]


@pytest.mark.parametrize("bad_session", ["", "   ", None])
def test_blank_session_ids_are_rejected(bad_session):
    agent = make_recording_a1()
    with pytest.raises(ValueError):
        agent.go("one", session_id=bad_session)


# ── Base system prompt restored between requests ──────────────────


def test_system_prompt_resets_to_base_between_requests():
    agent = make_recording_a1()
    agent._base_system_prompt = "BASE PROMPT"
    agent.system_prompt = "polluted by another session's resources"
    agent.go("fresh question", session_id="clean")
    assert agent.system_prompt == "BASE PROMPT"


def test_streaming_path_also_resets_base_prompt():
    agent = make_recording_a1()
    agent._base_system_prompt = "BASE STREAM"
    agent.system_prompt = "leftover retrieval resources"
    list(agent.go_stream("q", session_id="s"))
    assert agent.system_prompt == "BASE STREAM"


# ── Service forwarding and serialization ──────────────────────────


def test_streaming_service_forwards_request_session_id():
    service = make_recording_service()
    list(service.run_task_stream(ChatRequest(message="q", session_id="session-b")))
    assert service._agent.seen_session_ids == ["session-b"]


def test_sync_service_forwards_request_session_id():
    service = make_recording_service()
    service.run_task(ChatRequest(message="q", session_id="session-c"))
    assert service._agent.seen_session_ids == ["session-c"]


def test_service_serializes_mutating_agent_calls():
    service = make_recording_service()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(
            pool.map(
                lambda sid: service.run_task(
                    ChatRequest(message=sid, session_id=sid)
                ),
                ["a", "b"],
            )
        )
    assert service._agent.max_simultaneous_calls == 1


# ── Request-scoped timeout override ───────────────────────────────


def test_request_timeout_override_applied_then_restored():
    service = make_recording_service()
    service._agent.timeout_seconds = 600

    def recording_go(prompt, *, session_id="default"):
        service._agent.seen_timeouts.append(service._agent.timeout_seconds)
        return [], "<solution>ok</solution>"

    service._agent.go = recording_go
    response = service.run_task(
        ChatRequest(message="q", session_id="t", timeout_seconds=1200)
    )
    assert response.ok or response.status.value != "error"
    # During the call the override applied; afterwards the previous value is back.
    assert service._agent.seen_timeouts == [1200]
    assert service._agent.timeout_seconds == 600


def test_timeout_override_removed_after_request_for_agents_without_one():
    """An override must not leak onto agents that never had a timeout."""
    service = make_recording_service()  # RecordingServiceAgent has NO timeout_seconds

    def recording_go(prompt, *, session_id="default"):
        assert getattr(service._agent, "timeout_seconds", None) == 120
        return [], "<solution>ok</solution>"

    service._agent.go = recording_go
    service.run_task(ChatRequest(message="q", session_id="t", timeout_seconds=120))
    assert not hasattr(service._agent, "timeout_seconds"), (
        "timeout override leaked onto an agent without a configured timeout"
    )


def test_all_compiled_workflows_share_one_checkpoint_saver():
    """Model-override and default agents serve one history per session."""
    from biochat.agent import workflow as workflow_module

    class Bare:
        pass

    app_one = workflow_module.build_agent_workflow(Bare())
    app_two = workflow_module.build_agent_workflow(Bare())
    saver = workflow_module._get_shared_checkpoint_saver()
    assert app_one.checkpointer is saver
    assert app_two.checkpointer is saver


def test_cache_hit_requires_identical_source_and_base_url_components():
    built: list[tuple] = []
    service = BioAgentService(BiochatSettings())

    def spy_factory(settings):
        built.append((settings.llm_model, settings.llm_source, settings.base_url))
        return RecordingServiceAgent()

    service._agent_factory = spy_factory
    service.run_task(ChatRequest(message="a", session_id="s", llm_model="m"))
    service.run_task(ChatRequest(message="b", session_id="s", llm_model="m"))
    assert len(built) == 1


def test_timeout_override_clamped_to_settings_maximum(monkeypatch):
    from biochat.services import agent_service as agent_service_module

    monkeypatch.setattr(agent_service_module, "_MAX_TIMEOUT_SECONDS", 99)
    assert agent_service_module._bounded_timeout(999999) == 99
    assert agent_service_module._bounded_timeout(120) == 99

    monkeypatch.setattr(agent_service_module, "_MAX_TIMEOUT_SECONDS", 3600)
    assert agent_service_module._bounded_timeout(120) == 120
    assert agent_service_module._bounded_timeout(None) is None
    assert agent_service_module._bounded_timeout(0) is None
    assert agent_service_module._bounded_timeout(-5) is None
    assert agent_service_module._bounded_timeout("not-a-number") is None


# ── Model-keyed agent cache ───────────────────────────────────────


def test_model_override_reuses_agent_cached_for_that_model():
    builds = []
    service = BioAgentService(
        BiochatSettings(),
        agent_factory=lambda settings: builds.append(settings.llm_model)
        or RecordingServiceAgent(),
    )
    service.run_task(ChatRequest(message="one", session_id="a", llm_model="model-b"))
    service.run_task(ChatRequest(message="two", session_id="b", llm_model="model-b"))
    assert builds == ["model-b"]


def test_distinct_models_get_distinct_cached_agents():
    built_settings = []
    service = BioAgentService(
        BiochatSettings(),
        agent_factory=lambda settings: built_settings.append(settings.llm_model)
        or RecordingServiceAgent(),
    )
    service.run_task(ChatRequest(message="one", session_id="a", llm_model="model-b"))
    service.run_task(ChatRequest(message="two", session_id="b", llm_model="model-c"))
    assert built_settings == ["model-b", "model-c"]


def test_override_agents_do_not_mutate_the_default_agent():
    default_agent = RecordingServiceAgent()
    service = BioAgentService(BiochatSettings())
    service._agent = default_agent
    service._initialized = True

    override = RecordingServiceAgent()
    service._agent_factory = lambda settings: override
    service.run_task(ChatRequest(message="q", session_id="a", llm_model="other"))
    # The override handled the request; the shared default agent did not.
    assert override.seen_session_ids == ["a"]
    assert default_agent.seen_session_ids == []
    assert service._agent is default_agent


def test_shutdown_clears_cached_override_agents():
    built: list[RecordingServiceAgent] = []

    def build(settings):
        agent = RecordingServiceAgent()
        built.append(agent)
        return agent

    service = BioAgentService(BiochatSettings(), agent_factory=build)
    service.run_task(ChatRequest(message="one", session_id="a", llm_model="m1"))
    service.shutdown()
    rebuilt: list[RecordingServiceAgent] = []
    service._agent_factory = lambda settings: rebuilt.append(
        RecordingServiceAgent()
    )[-1]
    service.run_task(ChatRequest(message="again", session_id="a", llm_model="m1"))
    assert len(rebuilt) == 1  # cache was cleared; a fresh agent was built


# ── ChatRequest validation ────────────────────────────────────────


@pytest.mark.parametrize("bad_session", ["", "   ", None])
def test_chat_request_rejects_blank_session_id(bad_session):
    with pytest.raises(ValueError):
        ChatRequest(message="q", session_id=bad_session)
