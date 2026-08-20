# Biochat Security and Reliability Hardening Design

## Status

Approved approach: Option A — repair the reproducible correctness and packaging defects, make local execution secure by default, and introduce an execution boundary that can later host a container implementation without requiring a container control plane in this change.

## Goals

1. Prevent one chat session from reusing another session's LangGraph state, messages, or Python execution state.
2. Remove path traversal and unsafe archive extraction from bundled tools and download helpers.
3. Make UI launch defaults safe for a workstation and remove hard-coded credentials.
4. Stop presenting unrestricted host execution as a sandbox. Preserve it only as an explicit trusted-local compatibility mode.
5. Produce a wheel that contains the Biochat package and its required resources, excludes repository archives and development scripts, and declares the dependencies required by its supported installation profiles.
6. Repair the session-store abstraction, custom-endpoint routing, inactive UI settings, and configuration/version drift identified by review.
7. Add automated regression tests and CI checks that exercise source installs and built-wheel installs.

## Non-goals

- Building a Docker/Kubernetes job scheduler or remote execution service.
- Making every one of the 600+ scientific tools available in a minimal installation.
- Redesigning the visual appearance of either UI.
- Removing legacy public imports in this release.
- Moving the existing model weights to a new hosting provider without an approved, stable download URL and checksum manifest.

## Compatibility Policy

- Existing imports such as `from biochat.agent import A1`, `BiochatConfig`, and `get_agent_service()` remain available.
- `A1.go(prompt)` and `A1.go_stream(prompt)` keep working; a keyword-only `session_id` is added and defaults to `"default"` rather than using a process-wide numeric constant.
- Trusted users can restore legacy unrestricted execution with `BIOCHAT_ALLOW_HOST_CODE_EXECUTION=true`. The default is false.
- Gradio and Streamlit bind to `127.0.0.1` by default. Remote binding requires explicit launch configuration and an access code.
- Package version `biochat.version.__version__` is the canonical version displayed by both UIs and project metadata.

## Execution Security Boundary

Introduce a focused executor module with this interface:

```python
class CodeExecutor(Protocol):
    def execute_python(self, code: str, *, timeout: int, session_id: str) -> str: ...
    def execute_r(self, code: str, *, timeout: int, session_id: str) -> str: ...
    def execute_bash(self, code: str, *, timeout: int, session_id: str) -> str: ...
    def execute_cli(self, command: str, *, timeout: int, session_id: str) -> str: ...
```

Two implementations are included:

- `DisabledCodeExecutor` returns a clear, structured message explaining that code execution is disabled and how a trusted local operator can enable it.
- `HostCodeExecutor` preserves the current behavior for trusted local use. It is created only when `allow_host_code_execution` is true. Bash, R, and CLI subprocesses use argument lists where possible, process groups, wall-clock timeouts, and group termination on timeout. Python compatibility execution remains in-process because custom callable injection cannot safely cross a process boundary; it is explicitly labeled unsafe and is never selected by default.

The agent workflow depends on the interface rather than importing raw execution helpers. Session ID is passed to every execution call. Host Python namespaces are keyed by session ID and protected by locks. Resetting or deleting a session removes its namespace.

No UI should claim that a safety sandbox is active merely because text filtering or timeouts are enabled.

## Session Isolation and Concurrency

`ChatRequest.session_id` becomes the canonical conversation identifier throughout the service and agent layers:

```text
Streamlit/Gradio session
        -> ChatRequest.session_id
        -> BioAgentService task lock
        -> A1.go(..., session_id=...)
        -> LangGraph configurable.thread_id
        -> CodeExecutor session_id
```

The service retains one expensive Agent instance but serializes mutations of that instance with a task lock. This prevents concurrent requests from racing over `system_prompt`, `log`, retrieval state, and execution-result fields. LangGraph state is separated by session ID. Retrieval starts from an immutable base system prompt for each task so one session's selected resources do not leak into the next.

The Streamlit sidebar stores complete message lists per session, creates a fresh UUID for “new chat,” saves before switching, and restores after switching. It no longer keeps metadata-only pseudo-sessions.

## Session Store Contract

Replace private `_meta` access with protocol methods:

```python
class SessionStore(Protocol):
    def list_sessions(self) -> list[SessionInfo]: ...
    def get_session(self, session_id: str) -> list[ChatMessage]: ...
    def save_session(self, session_id: str, messages: list[ChatMessage]) -> None: ...
    def get_session_info(self, session_id: str) -> SessionInfo | None: ...
    def save_session_info(self, info: SessionInfo) -> None: ...
    def delete_session(self, session_id: str) -> None: ...
```

`create_session(title)` preserves the title and creation timestamp. Subsequent message saves update title, count, and `updated_at` while retaining `created_at`. Returned message lists are copies so callers cannot mutate stored state without saving.

## Filesystem and Archive Safety

Add reusable helpers for safe child-path resolution and ZIP extraction.

Path resolution rejects absolute user paths, `..` traversal, symlink escapes, and unknown protocol source directories. Protocol reads accept only regular files under `biochat/tool/protocols/<known-source>/`.

ZIP extraction validates every member before writing:

- resolved destination remains under the requested root;
- symlink entries are rejected;
- member count, individual uncompressed size, and total uncompressed size have configurable upper bounds;
- partial downloads and temporary archives are removed in `finally` blocks;
- HTTP calls include connect/read timeouts and optional maximum download size;
- callers may provide a SHA-256 checksum, which is verified before extraction.

The same helper replaces every direct `ZipFile.extractall()` call in the reviewed runtime paths.

## UI Exposure and Authentication

- Gradio launchers default to `127.0.0.1`, obtain codes from `BiochatSettings.access_codes`, and contain no literal shared password.
- Streamlit implements an early access gate when `require_verification` is true.
- Empty access-code configuration disables verification only for loopback use. Startup rejects a non-loopback bind without configured authentication unless an explicit `BIOCHAT_ALLOW_UNAUTHENTICATED_REMOTE=true` acknowledgement is present.
- Access-code comparisons use `hmac.compare_digest`.
- `start.sh` validates the selected UI mode, avoids embedding user-controlled paths in Python source, and passes safe server-address flags.

## LLM and Runtime Configuration

- Explicit `source` remains highest priority.
- When `base_url` is supplied and source is absent, routing selects `Custom` before generic model-name matchers such as `deepseek` or `qwen`.
- Streamlit settings are applied only through an explicit “Apply and restart agent” action. This builds validated settings, resets the service, and displays the effective configuration.
- `ChatRequest.timeout_seconds` is validated and applied for the duration of a serialized request, then restored. `llm_model` overrides use a separately cached agent keyed by model rather than mutating an in-flight global agent.
- `BiochatSettings` is canonical. `BiochatConfig` remains a compatibility adapter and delegates conversion to the canonical settings model.

## Packaging

Setuptools discovery is restricted to `biochat` and `biochat.*`. Explicit package data includes:

- environment and tool-description YAML catalogs;
- knowledge Markdown/CSV/TXT resources;
- bundled protocol TXT files;
- schema pickle files;
- existing antibody `.pth` weights for this release.

`third_party`, `scripts`, `docs`, `reports`, and `biochat_env` are not wheel packages. Model weights remain bundled temporarily because no approved external artifact location exists; a later release can replace them with checksum-verified on-demand assets.

Dependency groups are separated into minimal runtime, UI, provider, scientific-tool, and development extras. The default package contains dependencies needed to import and run the core agent and catalogs. Optional scientific libraries remain lazy imports and are documented by tool profile.

The broad `.*` ignore rule is removed. `.env` remains ignored, while `.env.example`, `.github/`, `.pre-commit-config.yaml`, and other project configuration files are trackable.

## Testing and CI

Regression tests cover:

- distinct session IDs reaching distinct LangGraph thread IDs;
- no shared Python namespace between sessions;
- service serialization around mutable Agent state;
- Streamlit session creation/switch/save/restore logic as pure helper functions;
- custom `SessionStore` operation without private attributes;
- title and timestamp preservation;
- protocol traversal and symlink escape rejection;
- malicious ZIP traversal, symlink, size, and member-count rejection;
- DeepSeek/Qwen custom endpoints routing to `Custom`;
- host execution disabled by default and enabled only by explicit settings;
- no hard-coded UI access code and loopback launch defaults;
- built wheel contains required resources and excludes `third_party`;
- built wheel installs into a clean environment and imports core modules.

GitHub Actions runs compile checks, Ruff, focused unit tests, full tests for the minimal profile, wheel build, and wheel-content/install smoke tests on supported Python versions. Network- and model-dependent tests are marked and excluded from default CI.

## Error Handling and Observability

Security rejections return typed exceptions or structured executor results without leaking secrets. Logs include session IDs in hashed/truncated form, executor type, timeout decisions, and archive validation failures. API keys, access codes, complete prompts, and generated code are not logged at info level.

## Acceptance Criteria

1. The previously reproduced protocol traversal cannot read `pyproject.toml` or any file outside the protocol root.
2. A protocol-conforming custom session store can create, update, list, clear, and delete sessions without implementation-specific attributes.
3. `deepseek-chat` with a custom base URL resolves to `Custom`.
4. Two session IDs never share LangGraph thread state, message history, or host Python variables.
5. Host code execution is disabled in a default configuration.
6. Gradio defaults to loopback and neither UI contains a hard-coded access code.
7. A built wheel contains all declared runtime resources and no `third_party` files.
8. The repository provides a usable `.env.example`, pre-commit configuration, and CI workflow.
9. Focused regression tests, the existing test suite available in the project environment, Ruff, compile checks, and wheel smoke checks pass before completion is claimed.
