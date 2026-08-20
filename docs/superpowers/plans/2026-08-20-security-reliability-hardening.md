# Biochat Security and Reliability Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair Biochat's verified security, session-isolation, packaging, configuration, and deployment defects while retaining its existing public Python APIs.

**Architecture:** Route all generated code through a policy-selected executor, propagate a canonical session ID through UI → service → agent → LangGraph/executor, and centralize reusable filesystem safety checks. Keep the expensive agent singleton but serialize its mutable operations, make host execution explicitly opt-in, and verify the distributable wheel rather than relying on source-tree behavior.

**Tech Stack:** Python 3.11+, LangChain/LangGraph, Streamlit, Gradio, setuptools, pytest, Ruff, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-20-security-reliability-hardening-design.md`

## Global Constraints

- Preserve `from biochat.agent import A1`, `BiochatConfig`, `get_agent_service()`, `A1.go(prompt)`, and `A1.go_stream(prompt)`.
- Host execution defaults to disabled and is enabled only by `BIOCHAT_ALLOW_HOST_CODE_EXECUTION=true` or an explicit settings argument.
- UI server defaults are `127.0.0.1`; non-loopback unauthenticated exposure requires `BIOCHAT_ALLOW_UNAUTHENTICATED_REMOTE=true`.
- `biochat.version.__version__` is the sole project and UI version source.
- Do not introduce a Docker/Kubernetes scheduler in this change.
- Every production behavior change follows RED → GREEN → REFACTOR and gets a focused regression test.
- Network- and model-dependent tests are excluded from default CI.

---

### Task 1: Repair the session-store contract

**Files:**
- Create: `tests/test_session_service.py`
- Modify: `biochat/services/session_service.py:28-155`
- Modify: `biochat/schemas/chat.py:180-195`

**Interfaces:**
- Consumes: `ChatMessage`, `SessionInfo`, `MessageRole` from `biochat.schemas.chat`.
- Produces: `SessionStore.get_session_info(session_id)`, `SessionStore.save_session_info(info)`, copy-safe `get_session()`, and metadata-preserving `SessionService` CRUD.

- [ ] **Step 1: Write failing tests for a protocol-only custom store**

```python
class DictSessionStore:
    def __init__(self):
        self.messages = {}
        self.info = {}
    def list_sessions(self):
        return sorted(self.info.values(), key=lambda item: item.updated_at, reverse=True)
    def get_session(self, session_id):
        return list(self.messages.get(session_id, []))
    def save_session(self, session_id, messages):
        self.messages[session_id] = list(messages)
    def get_session_info(self, session_id):
        return self.info.get(session_id)
    def save_session_info(self, info):
        self.info[info.session_id] = info
    def delete_session(self, session_id):
        self.messages.pop(session_id, None)
        self.info.pop(session_id, None)

def test_custom_store_does_not_require_private_meta():
    service = SessionService(DictSessionStore())
    session_id = service.create_session("Wanted title")
    info = service.list_sessions()[0]
    assert info.session_id == session_id
    assert info.title == "Wanted title"
    assert info.created_at
```

- [ ] **Step 2: Write failing tests for title/timestamp preservation and defensive copies**

```python
def test_message_save_preserves_created_at_and_updates_title():
    service = SessionService()
    session_id = service.create_session("Initial")
    created_at = service.list_sessions()[0].created_at
    service.add_message(session_id, ChatMessage(role=MessageRole.USER, content="First question"))
    info = service.list_sessions()[0]
    assert info.title == "First question"
    assert info.created_at == created_at

def test_get_session_returns_a_copy():
    service = SessionService()
    session_id = service.create_session()
    leaked = service.get_session(session_id)
    leaked.append(ChatMessage(role=MessageRole.USER, content="unsaved"))
    assert service.get_session(session_id) == []
```

- [ ] **Step 3: Run the focused tests and verify RED**

Run: `python -m pytest tests/test_session_service.py -q`

Expected: failure from private `_meta` access, overwritten title/creation time, and list aliasing.

- [ ] **Step 4: Extend the protocol and implement metadata-preserving storage**

Implement `get_session_info()` and `save_session_info()` on the protocol and in-memory store. Make all message reads/writes copy lists. Have `create_session()` save messages and metadata only through public methods. Have `add_message()`, `clear_session()`, and `save_session()` preserve the existing `created_at` while updating count/title/time.

- [ ] **Step 5: Run focused and related tests and verify GREEN**

Run: `python -m pytest tests/test_session_service.py tests/test_biochat_ui_smoke.py -q`

- [ ] **Step 6: Commit the session-store repair**

```bash
git add biochat/services/session_service.py biochat/schemas/chat.py tests/test_session_service.py
git commit -m "fix: honor pluggable session stores"
```

---

### Task 2: Add safe path resolution and ZIP extraction

**Files:**
- Create: `biochat/utils/filesystem_safety.py`
- Create: `tests/test_filesystem_safety.py`
- Modify: `biochat/tool/protocols.py:173-305`
- Modify: `biochat/utils/s3_download.py:19-121`
- Modify: `biochat/tool/bioimaging.py:245-267`

**Interfaces:**
- Produces: `resolve_child_path(root, *parts) -> Path`, `safe_extract_zip(archive, destination, limits=ZipSafetyLimits()) -> list[Path]`, `verify_sha256(path, expected) -> None`.
- Consumes: standard-library `pathlib`, `zipfile`, `hashlib`, and `stat`; no new dependency.

- [ ] **Step 1: Write failing path-containment tests**

```python
def test_resolve_child_path_rejects_parent_escape(tmp_path):
    with pytest.raises(ValueError, match="outside"):
        resolve_child_path(tmp_path / "root", "..", "secret.txt")

def test_protocol_reader_rejects_source_traversal():
    with pytest.raises(ValueError, match="source"):
        read_local_protocol("pyproject.toml", source="../../..")
```

- [ ] **Step 2: Write failing ZIP traversal, symlink, and size-limit tests**

```python
def test_safe_extract_rejects_zip_slip(tmp_path):
    archive = tmp_path / "bad.zip"
    with ZipFile(archive, "w") as zf:
        zf.writestr("../escaped.txt", "secret")
    with pytest.raises(ValueError, match="outside"):
        safe_extract_zip(archive, tmp_path / "out")
    assert not (tmp_path / "escaped.txt").exists()

def test_safe_extract_rejects_total_size_limit(tmp_path):
    archive = tmp_path / "large.zip"
    with ZipFile(archive, "w") as zf:
        zf.writestr("large.bin", b"x" * 20)
    limits = ZipSafetyLimits(max_members=10, max_member_bytes=100, max_total_bytes=10)
    with pytest.raises(ValueError, match="total"):
        safe_extract_zip(archive, tmp_path / "out", limits=limits)
```

- [ ] **Step 3: Run the safety tests and verify RED**

Run: `python -m pytest tests/test_filesystem_safety.py -q`

Expected: import failures because the safety module does not exist and traversal still succeeds.

- [ ] **Step 4: Implement containment, symlink rejection, limits, and checksum verification**

Use `Path.resolve(strict=False)` plus `target.is_relative_to(root)` for containment. Interpret ZIP mode bits from `ZipInfo.external_attr`; reject symbolic links before extraction. Stream each member into a destination file after validation instead of calling `extractall()`.

- [ ] **Step 5: Replace runtime `extractall()` calls and harden downloads**

Use request timeouts `(10, 120)`, enforce a configurable byte ceiling while streaming, remove temporary archives in `finally`, and call `verify_sha256()` when a checksum is supplied. Replace the reviewed `s3_download.py` and nnUNet extraction calls with `safe_extract_zip()`.

- [ ] **Step 6: Run focused tests and the protocol catalog tests**

Run: `python -m pytest tests/test_filesystem_safety.py tests/test_tool_catalog.py -q`

- [ ] **Step 7: Commit filesystem hardening**

```bash
git add biochat/utils/filesystem_safety.py biochat/utils/s3_download.py biochat/tool/protocols.py biochat/tool/bioimaging.py tests/test_filesystem_safety.py
git commit -m "fix: contain protocol and archive paths"
```

---

### Task 3: Correct provider routing and canonical settings

**Files:**
- Create: `tests/test_llm_source_detection.py`
- Create: `tests/test_settings_security.py`
- Modify: `biochat/llm/source_detector.py:58-100`
- Modify: `biochat/core/settings.py:200-412`
- Modify: `biochat/config.py:20-144`
- Modify: `biochat/biochat_config.py`
- Modify: `biochat/version.py`

**Interfaces:**
- Produces: `BiochatSettings.allow_host_code_execution`, `allow_unauthenticated_remote`, canonical `project_version`, and correct `detect_llm_source(model, base_url)` behavior.

- [ ] **Step 1: Write failing custom-endpoint routing tests**

```python
@pytest.mark.parametrize("model", ["deepseek-chat", "qwen-plus", "llama-3-custom"])
def test_base_url_routes_openai_compatible_models_to_custom(model):
    assert detect_llm_source(model, "https://example.test/v1") == "Custom"

def test_model_name_detection_remains_for_no_base_url():
    assert detect_llm_source("deepseek-r1") == "Ollama"
```

- [ ] **Step 2: Write failing secure-default and version tests**

```python
def test_host_execution_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("BIOCHAT_ALLOW_HOST_CODE_EXECUTION", raising=False)
    assert BiochatSettings().allow_host_code_execution is False

def test_project_version_uses_package_version():
    from biochat import __version__
    from biochat.core.settings import PROJECT_VERSION
    assert PROJECT_VERSION == __version__
```

- [ ] **Step 3: Run tests and verify RED**

Run: `python -m pytest tests/test_llm_source_detection.py tests/test_settings_security.py -q`

- [ ] **Step 4: Implement routing precedence and settings fields**

Place the `base_url -> Custom` branch before generic matchers but after explicit source handling in the factory. Add boolean env mappings for `BIOCHAT_ALLOW_HOST_CODE_EXECUTION` and `BIOCHAT_ALLOW_UNAUTHENTICATED_REMOTE`. Import `__version__` for project identity instead of duplicating `2.0.0`.

- [ ] **Step 5: Reduce legacy configuration drift**

Keep `BiochatConfig` mutable for compatibility, add `to_settings()` as the one conversion path, and make bridging code delegate through that method. Re-export canonical identity constants from `biochat_config.py` instead of defining copies.

- [ ] **Step 6: Verify existing compatibility tests remain green**

Run: `python -m pytest tests/test_llm_source_detection.py tests/test_settings_security.py tests/test_biochat_ui_smoke.py tests/test_tool_profiles.py -q`

- [ ] **Step 7: Commit routing and settings repairs**

```bash
git add biochat/llm/source_detector.py biochat/core/settings.py biochat/config.py biochat/biochat_config.py biochat/version.py tests/test_llm_source_detection.py tests/test_settings_security.py
git commit -m "fix: secure runtime defaults and provider routing"
```

---

### Task 4: Introduce the execution-policy boundary

**Files:**
- Create: `biochat/execution/__init__.py`
- Create: `biochat/execution/base.py`
- Create: `biochat/execution/host.py`
- Create: `tests/test_execution_policy.py`
- Modify: `biochat/tool/support_tools.py:6-44`
- Modify: `biochat/utils/code_execution.py:28-167`
- Modify: `biochat/agent/workflow.py:117-170`
- Modify: `biochat/agent/a1.py:61-170, 638-647`

**Interfaces:**
- Produces: `CodeExecutor`, `DisabledCodeExecutor`, `HostCodeExecutor`, `create_code_executor(settings)`, `clear_session(session_id)`.
- `A1` owns `self.code_executor`; workflow code never calls raw `exec()` or subprocess helpers directly.

- [ ] **Step 1: Read the test quality rules before writing executor tests**

Run: `sed -n '1,320p' /home/cq/.codex/plugins/cache/claude-plugins-official/superpowers/6.3.0/skills/test-driven-development/writing-good-tests.md`

- [ ] **Step 2: Write failing disabled-by-default tests**

```python
def test_default_executor_refuses_python():
    executor = create_code_executor(BiochatSettings())
    result = executor.execute_python("print('unsafe')", timeout=1, session_id="s1")
    assert result.status == "disabled"
    assert "BIOCHAT_ALLOW_HOST_CODE_EXECUTION" in result.message

def test_explicit_host_setting_selects_host_executor():
    settings = BiochatSettings(allow_host_code_execution=True)
    assert isinstance(create_code_executor(settings), HostCodeExecutor)
```

- [ ] **Step 3: Write failing namespace-isolation and timeout tests**

```python
def test_host_python_namespaces_are_session_scoped():
    executor = HostCodeExecutor()
    executor.execute_python("secret = 7", timeout=1, session_id="a")
    result = executor.execute_python("print(globals().get('secret'))", timeout=1, session_id="b")
    assert result.stdout.strip() == "None"

def test_bash_timeout_terminates_process_group():
    executor = HostCodeExecutor()
    result = executor.execute_bash("sleep 30", timeout=0.1, session_id="a")
    assert result.status == "timeout"
```

- [ ] **Step 4: Run executor tests and verify RED**

Run: `python -m pytest tests/test_execution_policy.py -q`

- [ ] **Step 5: Implement the protocol, result type, disabled executor, and factory**

Use an immutable `ExecutionResult(status, stdout="", stderr="", message="")`. The disabled executor returns results rather than raising. The factory selects host execution only from the explicit setting.

- [ ] **Step 6: Implement host compatibility execution with session locks**

Maintain `_namespaces: dict[str, dict]` and `_locks: dict[str, threading.RLock]` inside `HostCodeExecutor`, not at module scope. Use `start_new_session=True` for subprocesses and `os.killpg()` on timeout. Keep custom-function registration explicit per namespace.

- [ ] **Step 7: Route the agent workflow through `self.code_executor`**

Pass the active session ID from state/config into the executor. Convert `ExecutionResult` to the existing observation string format so downstream parsing remains compatible. Retain old helper functions as deprecated wrappers around a trusted host executor only for direct legacy callers.

- [ ] **Step 8: Run executor and existing UI sanitization tests**

Run: `python -m pytest tests/test_execution_policy.py tests/test_biochat_streamlit_smoke.py -q`

- [ ] **Step 9: Commit the execution boundary**

```bash
git add biochat/execution biochat/tool/support_tools.py biochat/utils/code_execution.py biochat/agent/workflow.py biochat/agent/a1.py tests/test_execution_policy.py
git commit -m "feat: gate generated code behind execution policy"
```

---

### Task 5: Propagate session IDs and serialize mutable Agent use

**Files:**
- Create: `tests/test_agent_session_isolation.py`
- Modify: `biochat/agent/a1.py:230-320`
- Modify: `biochat/agent/agent_state.py`
- Modify: `biochat/agent/workflow.py:117-257`
- Modify: `biochat/services/agent_service.py:69-536, 680-703`
- Modify: `biochat/schemas/chat.py:66-83`

**Interfaces:**
- Produces: `A1.go(prompt, *, session_id="default")`, `A1.go_stream(prompt, *, session_id="default")`, request-scoped timeout handling, a service task lock, and a model-keyed Agent cache.

- [ ] **Step 1: Define real-behavior recording fixtures and failing session propagation tests**

```python
class RecordingApp:
    def __init__(self):
        self.configs = []
    def stream(self, inputs, *, stream_mode, config):
        self.configs.append(config)
        yield {"messages": [AIMessage(content="<solution>ok</solution>")]}

def make_recording_a1():
    agent = object.__new__(A1)
    agent.use_tool_retriever = False
    agent.app = RecordingApp()
    agent.log = []
    agent.recursion_limit = 500
    return agent

class RecordingServiceAgent:
    def __init__(self):
        self.use_tool_retriever = False
        self.seen_session_ids = []
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
            self.max_simultaneous_calls = max(self.max_simultaneous_calls, self.active_calls)
        time.sleep(0.05)
        with self.counter_lock:
            self.active_calls -= 1
        return [], "<solution>ok</solution>"

def make_recording_service():
    service = BioAgentService(BiochatSettings())
    service._agent = RecordingServiceAgent()
    service._initialized = True
    return service

def test_go_passes_session_id_as_thread_id():
    agent = make_recording_a1()
    agent.go("one", session_id="session-a")
    assert agent.app.configs[-1]["configurable"]["thread_id"] == "session-a"

def test_streaming_service_forwards_request_session_id():
    service = make_recording_service()
    list(service.run_task_stream(ChatRequest(message="q", session_id="session-b")))
    assert service._agent.seen_session_ids == ["session-b"]
```

- [ ] **Step 2: Write a failing concurrency test with a real lock boundary**

```python
def test_service_serializes_mutating_agent_calls():
    service = make_recording_service()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda sid: service.run_task(ChatRequest(message=sid, session_id=sid)), ["a", "b"]))
    assert service._agent.max_simultaneous_calls == 1

def test_model_override_reuses_agent_cached_for_that_model():
    builds = []
    service = BioAgentService(BiochatSettings(), agent_factory=lambda settings: builds.append(settings.llm_model) or RecordingServiceAgent())
    service.run_task(ChatRequest(message="one", session_id="a", llm_model="model-b"))
    service.run_task(ChatRequest(message="two", session_id="b", llm_model="model-b"))
    assert builds == ["model-b"]
```

- [ ] **Step 3: Run isolation tests and verify RED**

Run: `python -m pytest tests/test_agent_session_isolation.py -q`

- [ ] **Step 4: Add keyword-only session IDs and remove hard-coded `42`**

Build LangGraph config with the validated non-empty session ID and the configured recursion limit. Store the active ID in `AgentState` only if execution nodes need it; do not derive it from user content.

- [ ] **Step 5: Add service serialization and per-request timeout restoration**

Wrap retrieval, prompt mutation, and `go`/`go_stream` consumption inside a re-entrant task lock. Save the previous timeout, apply a validated request override bounded by settings maximum, and restore it in `finally`.

- [ ] **Step 6: Add injectable construction and a model-keyed Agent cache**

Accept an optional `agent_factory: Callable[[BiochatSettings], Any]` in `BioAgentService.__init__`, defaulting to the existing A1 construction path. Cache Agents by their effective model/source/base URL tuple. Route `ChatRequest.llm_model` to the cached override Agent without mutating the default Agent. Keep cache access under the service lock and shut down every cached Agent on reset.

- [ ] **Step 7: Reset retrieval prompt state per request**

Capture the base system prompt after Agent configuration and restore it before applying selected resources, ensuring that tools selected for one request do not persist into another session.

- [ ] **Step 8: Run isolation, service, and resource-selection tests**

Run: `python -m pytest tests/test_agent_session_isolation.py tests/test_resource_selector.py tests/test_biochat_streamlit_smoke.py -q`

- [ ] **Step 9: Commit session propagation**

```bash
git add biochat/agent/a1.py biochat/agent/agent_state.py biochat/agent/workflow.py biochat/services/agent_service.py biochat/schemas/chat.py tests/test_agent_session_isolation.py
git commit -m "fix: isolate agent work by session"
```

---

### Task 6: Repair UI sessions, authentication, and launch defaults

**Files:**
- Create: `biochat/ui/session_state.py`
- Create: `biochat/ui/auth.py`
- Create: `biochat/ui/cli.py`
- Create: `tests/test_ui_sessions_and_auth.py`
- Modify: `biochat/ui/biochat_streamlit.py:674-825, 963-1217`
- Modify: `biochat/ui/biochat_ui.py:145-206, 579-604`
- Modify: `biochat/ui/gradio_legacy.py:23-49, 279-280`
- Modify: `biochat/ui/biochat_about.py:12-278`
- Modify: `biochat/agent/a1.py:591-612`
- Modify: `biochat/agent/ui_launcher.py`
- Modify: `start.sh`

**Interfaces:**
- Produces pure `create_ui_session`, `save_ui_session`, and `switch_ui_session` helpers; `verify_access_code(candidate, configured_codes)`; `validate_remote_exposure(host, settings)`.

- [ ] **Step 1: Write failing pure session-state tests**

```python
def test_switch_session_saves_current_and_restores_target():
    state = {
        "active_session_id": "a",
        "messages": [{"role": "user", "content": "A"}],
        "sessions": {"b": {"title": "B", "messages": [{"role": "user", "content": "B"}]}}
    }
    switch_ui_session(state, "b")
    assert state["sessions"]["a"]["messages"][0]["content"] == "A"
    assert state["messages"][0]["content"] == "B"

def test_new_session_uses_a_fresh_id():
    state = {"active_session_id": "a", "messages": [], "sessions": {}}
    first = create_ui_session(state)
    second = create_ui_session(state)
    assert first != second
```

- [ ] **Step 2: Write failing auth and loopback-default tests**

```python
def test_access_code_comes_from_settings_not_literal():
    assert verify_access_code("configured", ["configured"])
    assert not verify_access_code("Biochat2025", ["configured"])

def test_remote_host_requires_auth_or_explicit_acknowledgement():
    settings = BiochatSettings(access_codes=[], allow_unauthenticated_remote=False)
    with pytest.raises(ConfigError, match="remote"):
        validate_remote_exposure("0.0.0.0", settings)
```

- [ ] **Step 3: Run UI tests and verify RED**

Run: `python -m pytest tests/test_ui_sessions_and_auth.py -q`

- [ ] **Step 4: Implement pure helpers and integrate Streamlit session IDs**

Save a full copy of messages before switching. Pass `active_session_id` into `ChatRequest`. Add an explicit Apply button for model/path changes that constructs validated settings, calls `reset_agent_service()`, and does not mutate configuration on every rerun.

- [ ] **Step 5: Implement Streamlit and Gradio authentication from settings**

Use `hmac.compare_digest`; never render configured codes. Apply the gate before Agent initialization. Remove all literal access codes. Thread settings into Gradio constructors and launchers.

- [ ] **Step 6: Make launch defaults loopback-only and remove Python interpolation from `start.sh`**

Use `127.0.0.1` defaults throughout. Implement `python -m biochat.ui.cli --ui gradio --host 127.0.0.1`, with `argparse` choices for UI and host and configuration read through `BiochatSettings`. Have `start.sh` invoke that module instead of embedding `${DATA}` into `python -c`. Reject unknown UI modes with exit status 2.

- [ ] **Step 7: Run UI regression tests**

Run: `python -m pytest tests/test_ui_sessions_and_auth.py tests/test_biochat_ui_smoke.py tests/test_biochat_streamlit_smoke.py -q`

- [ ] **Step 8: Commit UI hardening**

```bash
git add biochat/ui biochat/agent/a1.py biochat/agent/ui_launcher.py start.sh tests/test_ui_sessions_and_auth.py
git commit -m "fix: secure and isolate UI sessions"
```

---

### Task 7: Repair package metadata and verify built artifacts

**Files:**
- Create: `tests/test_distribution_contents.py`
- Modify: `pyproject.toml`
- Modify: `MANIFEST.in`
- Modify: `.gitignore`
- Create: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Produces setuptools configuration restricted to `biochat*`, explicit package resources, and extras named `streamlit`, `gradio`, `providers`, `full-tools`, and `dev`.

- [ ] **Step 1: Write a wheel builder fixture and failing content test**

```python
@pytest.fixture(scope="session")
def built_wheel(tmp_path_factory):
    output = tmp_path_factory.mktemp("wheel")
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(output)],
        check=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    wheels = list(output.glob("biochat-*.whl"))
    assert len(wheels) == 1
    return wheels[0]

REQUIRED = {
    "biochat/environment/catalog.yaml",
    "biochat/tool/tool_description/catalog.yaml",
    "biochat/knowledge/docs/sgRNA_design_guide.md",
    "biochat/tool/antibody_design/models/cdrh3_vae_model_best.pth",
}

def test_wheel_contains_runtime_resources_and_excludes_repository_archives(built_wheel):
    with ZipFile(built_wheel) as zf:
        names = set(zf.namelist())
    assert REQUIRED <= names
    assert not any(name.startswith("third_party/") for name in names)
    assert not any(name.startswith("scripts/") for name in names)
```

- [ ] **Step 2: Run the distribution test and verify RED**

Run: `python -m pytest tests/test_distribution_contents.py -q`

Expected: missing catalogs/docs/models and unexpected `third_party` entries.

- [ ] **Step 3: Restrict discovery and enumerate package data**

Set `[tool.setuptools.packages.find] include = ["biochat", "biochat.*"]` and exclude tests/tutorials/third-party namespaces. Add explicit glob entries for YAML, Markdown, CSV, TXT, JSON, pickle, SVG/PNG if imported, and antibody `.pth` files. Remove non-package recursive includes from `MANIFEST.in`.

- [ ] **Step 4: Define dependency extras and dev tooling**

Declare core imports needed by `A1` and catalog loading in base dependencies, provider integrations under `providers`, UI dependencies under their named extras, scientific dependencies under `full-tools`, and `pytest`, `ruff`, `build`, and `pre-commit` under `dev`. Use compatible lower/upper bounds matching the validated environment rather than unconstrained latest versions.

- [ ] **Step 5: Replace broad dotfile ignore and add an environment template**

Remove `.*`; explicitly ignore `.env`, caches, editor state, build output, and worktree directories. Add `.env.example` with placeholders, safe execution disabled, loopback launch guidance, and no real credentials.

- [ ] **Step 6: Update installation and security documentation**

Make README commands match tracked files, explain extras, document the host-execution opt-in warning, and use the canonical version. Remove claims that access filtering or timeouts constitute a sandbox.

- [ ] **Step 7: Rebuild and verify the wheel**

Run: `python -m build --wheel`

Run: `python -m pytest tests/test_distribution_contents.py tests/test_environment_catalog.py tests/test_knowledge_registry.py -q`

- [ ] **Step 8: Commit packaging repairs**

```bash
git add pyproject.toml MANIFEST.in .gitignore .env.example README.md tests/test_distribution_contents.py
git commit -m "fix: ship complete Biochat distributions"
```

---

### Task 8: Add automated quality gates and perform final verification

**Files:**
- Create: `tests/test_project_quality_config.py`
- Create: `.pre-commit-config.yaml`
- Create: `.github/workflows/ci.yml`
- Modify: `CONTRIBUTION.md`
- Modify: `docs/configuration.md`
- Modify: `docs/known_conflicts.md`

**Interfaces:**
- Produces repeatable local and CI commands for format/lint, focused tests, full minimal-profile tests, wheel build/content checks, and clean wheel installation.

- [ ] **Step 1: Write failing tests for tracked quality configuration**

```python
def test_project_quality_files_exist_and_parse():
    root = Path(__file__).resolve().parents[1]
    precommit = yaml.safe_load((root / ".pre-commit-config.yaml").read_text())
    workflow = yaml.safe_load((root / ".github/workflows/ci.yml").read_text())
    assert precommit["repos"]
    assert workflow["jobs"]

def test_ci_contains_distribution_and_test_gates():
    text = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
    for command in ("ruff check", "pytest", "python -m build", "test_distribution_contents"):
        assert command in text
```

- [ ] **Step 2: Run the configuration test and verify RED**

Run: `python -m pytest tests/test_project_quality_config.py -q`

Expected: missing `.pre-commit-config.yaml` and `.github/workflows/ci.yml`.

- [ ] **Step 3: Add pre-commit hooks with exact commands**

Configure Ruff check/fix and Ruff format using the project's pinned dev version, plus trailing-whitespace, end-of-file, YAML, and large-file checks. Exclude `third_party/` and generated catalogs only where formatting would alter attributed archives.

- [ ] **Step 4: Add CI jobs for Python 3.11 and 3.12**

CI steps:

```yaml
- run: python -m pip install -e ".[dev,streamlit,gradio,providers]"
- run: python -m compileall -q biochat tests scripts
- run: ruff check biochat tests scripts
- run: pytest -q -m "not network and not model"
- run: python -m build --wheel
- run: pytest -q tests/test_distribution_contents.py
```

Add a clean-wheel smoke step that installs the wheel into a new virtual environment and imports `biochat`, environment catalogs, knowledge registry, and source detection without using the repository root on `PYTHONPATH`.

- [ ] **Step 5: Update contribution and configuration docs**

Document `.[dev]`, test markers, safe host execution opt-in, remote exposure rules, and the wheel smoke-test command. Correct the contribution base branch from `main` to the repository's actual default branch if it remains `master`.

- [ ] **Step 6: Run the complete local verification gate**

Run:

```bash
python -m compileall -q biochat tests scripts
ruff check biochat tests scripts
python -m pytest -q -m "not network and not model"
python -m build --wheel
python -m pytest -q tests/test_distribution_contents.py
git diff --check
```

Expected: every command exits 0 with no test failures or Ruff violations.

- [ ] **Step 7: Re-run the original manual reproductions**

Verify:

```text
protocol ../../.. traversal -> rejected
custom SessionStore -> session created without AttributeError
deepseek-chat + custom base URL -> Custom
default executor -> disabled
two session IDs -> distinct thread IDs and namespaces
wheel third_party count -> 0
wheel required-resource missing count -> 0
```

- [ ] **Step 8: Review the diff for scope and secrets**

Run: `git diff --stat 849c82d..HEAD` and `rg -n "Biochat2025|api[_-]?key\s*=\s*['\"][^$]" biochat .env.example start.sh`

Expected: no hard-coded access code or credential; only files named in this plan plus generated lock/build metadata approved during execution.

- [ ] **Step 9: Commit quality gates and final documentation**

```bash
git add .pre-commit-config.yaml .github/workflows/ci.yml CONTRIBUTION.md docs/configuration.md docs/known_conflicts.md tests/test_project_quality_config.py
git commit -m "ci: verify hardened Biochat distributions"
```
