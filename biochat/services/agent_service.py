"""
BioAgent Service — clean wrapper around the Biochat A1 agent.

Responsibilities:
- Lazy, cached agent initialisation (no blocking on page load)
- Unified ``run_task()`` interface returning structured ``AgentResponse``
- Progress callbacks for real-time UI updates
- Graceful error handling with typed exceptions
- Agent lifecycle management (start, stop, health check)

Security note:
    The underlying A1 agent executes LLM-generated code.  Always run
    in a sandboxed or isolated environment.  Never expose to untrusted
    users without appropriate safeguards.
"""

from __future__ import annotations

import threading
from typing import Any, Callable

from biochat.core.errors import (
    AgentError,
    AgentInitError,
)
from biochat.core.logging import get_logger
from biochat.core.settings import (
    SAFETY_POLICY,
    BiochatSettings,
    biochat_settings,
)
from biochat.schemas.chat import (
    AgentResponse,
    AgentStatus,
    ChatRequest,
)

logger = get_logger(__name__)

# ── Type aliases ──────────────────────────────────────────────────
ProgressCallback = Callable[[AgentStatus, str], None]
"""Called with (status, detail_message) on each state transition."""

# Upper bound for request-scoped timeout overrides.
_MAX_TIMEOUT_SECONDS: int = int(SAFETY_POLICY.get("max_timeout_seconds", 3600))


def _bounded_timeout(value: Any) -> int | None:
    """Validate a request timeout override.

    Returns the clamped positive integer value, or ``None`` when the
    override is absent/invalid (in which case the agent keeps its
    configured timeout).
    """
    if value is None:
        return None
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return None
    if seconds < 1:
        return None
    return min(seconds, _MAX_TIMEOUT_SECONDS)


# ═══════════════════════════════════════════════════════════════════
# BioAgentService
# ═══════════════════════════════════════════════════════════════════

class BioAgentService:
    """Manages a Biochat A1 agent instance with lazy init and caching.

    This service is designed to be used as a **singleton** within a
    Streamlit or FastAPI process.  It holds one A1 instance and
    reuses it across requests.

    Usage::

        svc = BioAgentService()
        svc.ensure_initialized()

        response: AgentResponse = svc.run_task(
            ChatRequest(message="Explain EGFR function"),
            on_progress=lambda status, detail: print(f"[{status}] {detail}"),
        )
        print(response.answer)
    """

    # ── Constructor ──────────────────────────────────────────────

    def __init__(
        self,
        settings: BiochatSettings | None = None,
        *,
        agent_factory: Callable[[BiochatSettings], Any] | None = None,
    ):
        """Initialise the service.

        Args:
            settings: Optional settings override.  If None, uses the
                      global ``biochat_settings`` singleton.
            agent_factory: Optional callable used to construct agent
                      instances (receives the effective settings).
                      Defaults to the standard ``A1`` construction path.
        """
        self._settings = settings or biochat_settings
        self._agent: Any = None            # A1 instance (lazy)
        self._agent_lock = threading.Lock()
        self._task_lock = threading.RLock()
        # Cache key: effective (llm_model, llm_source, base_url) tuple.
        self._agent_cache: dict[tuple[str | None, str | None, str | None], Any] = {}
        self._initialized = False
        self._agent_factory = agent_factory

    # ── Public properties ────────────────────────────────────────

    @property
    def is_initialized(self) -> bool:
        """True if the underlying A1 agent has been created."""
        return self._initialized and self._agent is not None

    @property
    def model_display_name(self) -> str:
        """Human-readable model name for UI display."""
        return self._settings.model_display_name

    # ── Lifecycle ────────────────────────────────────────────────

    def ensure_initialized(self, force: bool = False) -> None:
        """Create or return the cached A1 agent instance.

        Thread-safe.  Blocks only on first call (or when ``force=True``).

        Args:
            force: If True, discard the cached instance and re-create.

        Raises:
            AgentInitError: If agent creation fails.
        """
        if self._initialized and not force and self._agent is not None:
            return

        with self._agent_lock:
            # Double-check pattern
            if self._initialized and not force and self._agent is not None:
                return

            logger.info(
                "Initializing BioAgent (model=%s, path=%s)",
                self._settings.llm_model,
                self._settings.data_path,
            )

            try:
                self._agent = self._construct_agent(self._settings)
                self._initialized = True
                logger.info("BioAgent initialized successfully")
            except AgentInitError:
                raise
            except Exception as exc:
                logger.error("Failed to initialize BioAgent: %s", exc)
                raise AgentInitError(
                    f"Failed to initialize the biomedical AI agent: {exc}"
                ) from exc

    def _construct_agent(self, settings: BiochatSettings) -> Any:
        """Build an agent instance for *settings*.

        Uses the injectable factory when supplied; otherwise follows the
        legacy A1 construction path (syncing the backward-compat config).
        """
        if self._agent_factory is not None:
            return self._agent_factory(settings)

        from biochat.agent import A1
        from biochat.config import default_config

        # Sync the legacy config for backward compat
        default_config.llm = settings.llm_model
        default_config.source = settings.llm_source
        default_config.path = settings.data_path
        default_config.timeout_seconds = settings.timeout_seconds
        default_config.use_tool_retriever = settings.use_tool_retriever
        default_config.tool_profile = settings.tool_profile
        default_config.commercial_mode = settings.commercial_mode
        default_config.base_url = settings.base_url
        default_config.api_key = settings.api_key

        return A1(
            path=settings.data_path,
            llm=settings.llm_model,
            source=settings.llm_source,
            timeout_seconds=settings.timeout_seconds,
            use_tool_retriever=settings.use_tool_retriever,
            tool_profile=settings.tool_profile,
            base_url=settings.base_url,
            api_key=settings.api_key,
            commercial_mode=settings.commercial_mode,
            allow_host_code_execution=settings.allow_host_code_execution,
        )

    def _resolve_agent(self, request: ChatRequest) -> Any:
        """Return the agent that should serve *request*.

        Requests carrying an ``llm_model`` override are served by a
        separately cached agent keyed by the effective
        (model, source, base URL) tuple — the shared default agent is
        never mutated.  Cache access happens under the task lock.
        """
        override_model = getattr(request, "llm_model", None)
        if not override_model:
            self.ensure_initialized()
            return self._agent

        cache_key = (
            override_model,
            self._settings.llm_source,
            self._settings.base_url,
        )
        with self._task_lock:
            cached = self._agent_cache.get(cache_key)
            if cached is not None:
                return cached

            override_settings = self._override_settings(override_model)
            agent = self._construct_agent(override_settings)
            self._agent_cache[cache_key] = agent
            return agent

    def _override_settings(self, model: str) -> BiochatSettings:
        """Effective settings copy for a model-override agent."""
        s = self._settings
        return BiochatSettings(
            data_path=s.data_path,
            timeout_seconds=s.timeout_seconds,
            use_tool_retriever=s.use_tool_retriever,
            tool_profile=s.tool_profile,
            commercial_mode=s.commercial_mode,
            recursion_limit=s.recursion_limit,
            llm_model=model,
            llm_source=s.llm_source,
            temperature=s.temperature,
            base_url=s.base_url,
            api_key=s.api_key,
            max_tokens=s.max_tokens,
            access_codes=list(s.access_codes),
            require_verification=s.require_verification,
            allow_host_code_execution=s.allow_host_code_execution,
            allow_unauthenticated_remote=s.allow_unauthenticated_remote,
        )

    def shutdown(self) -> None:
        """Release the default agent and every cached override agent."""
        with self._agent_lock:
            agents: list[Any] = []
            if self._agent is not None:
                agents.append(self._agent)
            agents.extend(self._agent_cache.values())

            for agent in agents:
                shutdown_hook = getattr(agent, "shutdown", None)
                if callable(shutdown_hook):
                    try:
                        shutdown_hook()
                    except Exception as exc:
                        logger.warning("Agent shutdown raised: %s", exc)

            self._agent = None
            self._agent_cache.clear()
            self._initialized = False
            logger.info("BioAgent shut down")

    # ── Task execution (synchronous) ──────────────────────────────

    def run_task(
        self,
        request: ChatRequest,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> AgentResponse:
        """Execute a biomedical task and return a structured response.

        Args:
            request: The user's chat request (message + optional overrides).
            on_progress: Optional callback for real-time status updates.

        Returns:
            ``AgentResponse`` with answer, trace, tool calls, and metadata.

        Raises:
            AgentInitError: If the agent is not initialized and cannot be created.
        """
        if not self.is_initialized and not getattr(request, "llm_model", None):
            # Override requests resolve lazily to cached agents instead.
            self.ensure_initialized()

        try:
            return self._execute_task(request, on_progress)
        except AgentError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error during task execution")
            return AgentResponse.error_response(
                f"An unexpected error occurred: {exc}",
                status=AgentStatus.ERROR,
            )

    # ── Task execution (streaming) ────────────────────────────────

    def run_task_stream(
        self,
        request: ChatRequest,
        *,
        on_progress: ProgressCallback | None = None,
    ):
        """Execute a biomedical task with real-time streaming updates.

        Uses ``agent.go_stream()`` to yield incremental execution steps
        instead of blocking until completion.  The generator yields a
        dict at each step that the UI can render immediately.

        Yields:
            dict with keys:
            - status (str): 'thinking' | 'executing' | 'observing' | 'answering' | 'completed' | 'error'
            - content (str): The current event text (thinking, code, observation, or answer)
            - answer_so_far (str): Accumulated cleaned answer text (only for 'answering' / 'completed')
            - trace_line (str): A single line for the trace panel
            - language (str): 'python' | 'r' | 'bash' (only for 'executing')
        """
        import re as _re

        if not self.is_initialized and not getattr(request, "llm_model", None):
            # Override requests resolve lazily to cached agents instead.
            self.ensure_initialized()

        def _report(status: AgentStatus, detail: str = "") -> None:
            if on_progress:
                try:
                    on_progress(status, detail)
                except Exception:
                    pass

        _report(AgentStatus.PLANNING, "正在分析问题并制定计划...")
        logger.info("Starting streaming task: %s", request.message[:100])

        # Resolve the serving agent (model override → cached agent) before
        # entering the serialized region.  The request-scoped timeout is
        # snapshotted inside the lock so a concurrent request on the same
        # cached agent can never capture an in-flight override.
        agent = self._resolve_agent(request)
        bounded_timeout = _bounded_timeout(getattr(request, "timeout_seconds", None))

        # Track state across streaming steps
        accumulated_answer: str = ""
        trace_lines: list[str] = []
        step_count: int = 0
        solution_found: bool = False
        gen_buffer: str = ""
        """Raw tokens of the current LLM generation (reset at each run boundary)."""

        # Serialize retrieval mutation plus the full go_stream consumption
        # behind the re-entrant task lock; restore any request-scoped
        # timeout override when the request finishes.
        self._task_lock.acquire()
        override_applied = False
        if bounded_timeout is not None:
            had_previous_timeout = hasattr(agent, "timeout_seconds")
            previous_timeout = getattr(agent, "timeout_seconds", None)
            agent.timeout_seconds = bounded_timeout
            override_applied = True
        try:
            # ── Phase 1: Tool retrieval (if enabled) ──────────────
            if agent.use_tool_retriever:
                _report(AgentStatus.RETRIEVING_TOOLS, "正在检索相关工具和数据库...")
                yield {
                    "status": "retrieving",
                    "content": "",
                    "answer_so_far": "",
                    "trace_line": "🔍 正在检索相关工具、数据库和知识库...",
                    "language": "",
                }
                try:
                    selected = agent._prepare_resources_for_retrieval(request.message)
                    if selected:
                        agent.update_system_prompt_with_selected_resources(selected)
                        tool_count = len(selected.get("tools", []))
                        data_count = len(selected.get("data_lake", []))
                        lib_count = len(selected.get("libraries", []))
                        trace_lines.append(
                            f"✅ 已选择 {tool_count} 个工具, {data_count} 个数据集, {lib_count} 个库"
                        )
                except Exception as e:
                    trace_lines.append(f"⚠️ 工具检索跳过: {e}")

            # ── Phase 2: Agent execution stream ──────────────────
            _report(AgentStatus.RUNNING_CODE, "Agent 正在执行任务...")

            if not hasattr(agent, "go_stream"):
                # Fallback: use synchronous go() and yield once
                log_entries, final_output = agent.go(request.message, session_id=request.session_id)
                response = self._parse_agent_output(log_entries, final_output, request.message)
                _report(AgentStatus.COMPLETED, "任务完成")
                yield {
                    "status": "completed",
                    "content": response.answer,
                    "answer_so_far": response.answer,
                    "trace_line": "",
                    "language": "",
                }
                return

            for event in agent.go_stream(request.message, session_id=request.session_id):
                step_count += 1

                # ── Token-level events: stream the final answer live ──
                # Tokens are buffered per LLM generation.  As soon as the
                # model opens the <solution> tag, everything after it is
                # forwarded incrementally as `answering` events so the UI
                # can stream the final answer token-by-token.  Tokens
                # before the tag (thinking) never leave this service layer.
                if event.get("type") == "token":
                    token = event.get("content", "")
                    if not isinstance(token, str):
                        token = str(token)

                    gen_buffer += token

                    if not solution_found and "<solution>" in gen_buffer:
                        incremental = gen_buffer.split("<solution>", 1)[1]
                        if "</solution>" in incremental:
                            incremental = incremental.split("</solution>", 1)[0]
                        # Trim a trailing half-written tag (e.g. "<" or
                        # "</sol") so it doesn't flash in the streamed text.
                        incremental = _re.sub(r"</?(?:[a-zA-Z_][\w:-]*)?$", "", incremental)
                        incremental = incremental.strip()
                        if incremental:
                            yield {
                                "status": "answering",
                                "content": "",
                                "answer_so_far": incremental,
                                "trace_line": "",
                                "language": "",
                            }

                    if event.get("chunk_position") == "last":
                        gen_buffer = ""  # end of this LLM run
                    continue

                # ── Message-level events (legacy parsing path) ──
                if event.get("type") == "message":
                    gen_buffer = ""  # node boundary — token buffer is stale

                text = self._extract_text_from_event(event)

                if not text or not text.strip():
                    continue

                text_stripped = text.strip()

                # ── Detect <solution> tag ────────────────────────
                solution_match = _re.search(
                    r"<solution>(.*?)</solution>", text_stripped, _re.DOTALL
                )
                if solution_match and not solution_found:
                    solution_found = True
                    answer_text = solution_match.group(1).strip()
                    accumulated_answer = self._clean_agent_text(answer_text)
                    _report(AgentStatus.COMPLETED, "任务完成")
                    trace_lines.append("✅ 生成最终答案")
                    yield {
                        "status": "completed",
                        "content": answer_text,
                        "answer_so_far": accumulated_answer,
                        "trace_line": "",
                        "language": "",
                    }
                    continue

                # ── Detect <execute> tag ─────────────────────────
                execute_match = _re.search(
                    r"<execute>(.*?)</execute>", text_stripped, _re.DOTALL
                )
                if execute_match:
                    code = execute_match.group(1).strip()
                    language = "python"
                    if code.startswith("#!R"):
                        language = "r"
                        code = _re.sub(r"^#!R", "", code, count=1).strip()
                    elif code.startswith("#!BASH") or code.startswith("#!CLI"):
                        language = "bash"
                        code = _re.sub(r"^#!BASH|^#!CLI", "", code, count=1).strip()

                    trace_lines.append(f"💻 执行 {language.upper()} 代码 (步骤 {step_count})...")
                    yield {
                        "status": "executing",
                        "content": "",  # do NOT leak generated code content
                        "answer_so_far": "",
                        "trace_line": f"💻 正在执行 {language.upper()} 代码...",
                        "language": language,
                    }
                    continue

                # ── Detect <observation> tag ─────────────────────
                observation_match = _re.search(
                    r"<observation>(.*?)</observation>", text_stripped, _re.DOTALL
                )
                if observation_match:
                    obs = observation_match.group(1).strip()
                    # SECURITY: trace panel shows event status only, not
                    # the raw execution output content.
                    yield {
                        "status": "observing",
                        "content": "",  # do NOT leak observation content
                        "answer_so_far": "",
                        "trace_line": f"📋 获取执行结果 ({len(obs)} 字符)",
                        "language": "",
                    }
                    continue

                # ── Thinking / reasoning text (before first tag) ──
                tag_positions = []
                for tag_name in ("<execute>", "<solution>", "<observation>"):
                    p = text_stripped.find(tag_name)
                    if p != -1:
                        tag_positions.append(p)

                if tag_positions:
                    thinking = text_stripped[: min(tag_positions)].strip()
                else:
                    thinking = text_stripped

                if thinking and len(thinking) > 10:
                    # SECURITY: never expose model thinking content in the
                    # trace panel — record a status line only.  The raw
                    # thinking text stays internal to the service layer.
                    yield {
                        "status": "thinking",
                        "content": "",  # do NOT leak reasoning text
                        "answer_so_far": "",
                        "trace_line": f"🤔 推理中... (步骤 {step_count})",
                        "language": "",
                    }

            # ── Phase 3: Fallback if no explicit <solution> ───────
            if not solution_found:
                log_entries = getattr(agent, "log", [])
                final_state = getattr(agent, "_conversation_state", None)
                final_text = ""
                if final_state and "messages" in final_state:
                    msgs = final_state["messages"]
                    if msgs:
                        last_content = msgs[-1].content if hasattr(msgs[-1], "content") else str(msgs[-1])
                        final_text = str(last_content)

                # Try one more time to find solution
                sm2 = _re.search(r"<solution>(.*?)</solution>", final_text, _re.DOTALL)
                if sm2:
                    accumulated_answer = self._clean_agent_text(sm2.group(1).strip())
                else:
                    cleaned = _re.sub(r"<execute>.*?</execute>", "", final_text, flags=_re.DOTALL)
                    cleaned = _re.sub(r"<observation>.*?</observation>", "", cleaned, flags=_re.DOTALL)
                    cleaned = _re.sub(r"\n\s*\n", "\n\n", cleaned).strip()
                    accumulated_answer = cleaned or "任务已完成，但未能生成可显示的答案。请查看处理轨迹了解详情。"

                _report(AgentStatus.COMPLETED, "任务完成")
                yield {
                    "status": "completed",
                    "content": accumulated_answer,
                    "answer_so_far": accumulated_answer,
                    "trace_line": "",
                    "language": "",
                }

        except Exception as exc:
            error_msg = str(exc)
            if "timeout" in error_msg.lower():
                _report(AgentStatus.TIMEOUT, error_msg)
                yield {
                    "status": "error",
                    "content": f"⏱️ 任务超时 ({self._settings.timeout_seconds}秒)。请尝试简化您的问题。",
                    "answer_so_far": accumulated_answer,
                    "trace_line": "",
                    "language": "",
                }
            else:
                _report(AgentStatus.ERROR, error_msg)
                logger.error("Streaming task failed: %s", error_msg)
                yield {
                    "status": "error",
                    "content": f"❌ 执行出错: {error_msg}",
                    "answer_so_far": accumulated_answer,
                    "trace_line": "",
                    "language": "",
                }
        finally:
            if override_applied:
                # Symmetric restore: delete the attribute when the agent
                # never carried a configured timeout of its own.
                if had_previous_timeout:
                    agent.timeout_seconds = previous_timeout
                else:
                    delattr(agent, "timeout_seconds")
            self._task_lock.release()

        # Store trace for later retrieval
        self._last_trace_lines = trace_lines

    def _extract_text_from_event(self, event) -> str:
        """Extract text content from a go_stream() event.

        Handles strings, dicts (with content/output keys), and objects
        with .content attributes.
        """
        if event is None:
            return ""
        if isinstance(event, str):
            return event
        if isinstance(event, dict):
            # go_stream yields {"output": out}
            for key in ("output", "content", "text", "response"):
                if key in event and event[key]:
                    val = event[key]
                    return val if isinstance(val, str) else str(val)
            return ""
        if hasattr(event, "content"):
            content = event.content
            return content if isinstance(content, str) else str(content)
        return str(event)

    def _execute_task(
        self,
        request: ChatRequest,
        on_progress: ProgressCallback | None,
    ) -> AgentResponse:
        """Internal task execution with progress reporting."""

        def _report(status: AgentStatus, detail: str = "") -> None:
            if on_progress:
                try:
                    on_progress(status, detail)
                except Exception:
                    pass  # Never let a callback crash the agent

        _report(AgentStatus.PLANNING, "Analyzing query and planning approach...")
        logger.info("Starting task: %s", request.message[:100])

        # Resolve the serving agent (model override → cached agent).
        agent = self._resolve_agent(request)
        bounded_timeout = _bounded_timeout(getattr(request, "timeout_seconds", None))

        try:
            # ── Run the agent (serialized; request-scoped timeout) ──
            _report(AgentStatus.RUNNING_CODE, "Agent is working on your task...")

            with self._task_lock:
                override_applied = False
                if bounded_timeout is not None:
                    had_previous_timeout = hasattr(agent, "timeout_seconds")
                    previous_timeout = getattr(agent, "timeout_seconds", None)
                    agent.timeout_seconds = bounded_timeout
                    override_applied = True
                try:
                    log_entries, final_output = agent.go(
                        request.message, session_id=request.session_id
                    )
                finally:
                    if override_applied:
                        if had_previous_timeout:
                            agent.timeout_seconds = previous_timeout
                        else:
                            delattr(agent, "timeout_seconds")

            # ── Extract structured data from raw output ───────
            response = self._parse_agent_output(
                log_entries=log_entries,
                final_output=final_output,
                user_message=request.message,
            )

            _report(AgentStatus.COMPLETED, "Task completed successfully")
            logger.info("Task completed (status=%s)", response.status.value)
            return response

        except Exception as exc:
            error_msg = str(exc)
            if "timeout" in error_msg.lower():
                _report(AgentStatus.TIMEOUT, error_msg)
                return AgentResponse.error_response(
                    f"Task timed out after {self._settings.timeout_seconds}s. "
                    f"Try simplifying your query.",
                    status=AgentStatus.TIMEOUT,
                )

            _report(AgentStatus.ERROR, error_msg)
            logger.error("Task failed: %s", error_msg)
            return AgentResponse.error_response(error_msg)

    # ── Output parsing ───────────────────────────────────────────

    def _parse_agent_output(
        self,
        log_entries: list[str],
        final_output: str,
        user_message: str,
    ) -> AgentResponse:
        """Convert raw A1.go() output into a structured AgentResponse.

        This is where the "raw text → structured data" transformation
        happens.  The logic is intentionally conservative — it prefers
        a partial but correct answer over a complete but hallucinated one.
        """
        import re

        response = AgentResponse(status=AgentStatus.COMPLETED)
        response.raw_log = "\n".join(log_entries) if log_entries else ""

        # ── Extract final answer ──────────────────────────────
        answer_text = self._clean_agent_text(final_output or "")

        # ── Extract tool calls from log ───────────────────────
        tool_names: set[str] = set()
        for entry in log_entries:
            # Match patterns like "from biochat.tool.genomics import ..."
            matches = re.findall(r"from\s+biochat\.tool\.(\w+)\s+import\s+(\w+)", entry)
            for module, func in matches:
                tool_names.add(f"{module}.{func}")

        response.tool_calls = sorted(tool_names)

        # ── Extract warnings ──────────────────────────────────
        for entry in log_entries:
            if "warning" in entry.lower() or "⚠" in entry:
                response.warnings.append(entry.strip()[:200])

        # ── Build reasoning trace ─────────────────────────────
        trace_parts: list[str] = []
        for i, entry in enumerate(log_entries):
            if i > 20:
                trace_parts.append("... (trace truncated)")
                break
            # Keep only substantial lines
            clean = entry.strip()
            if clean and len(clean) > 10:
                trace_parts.append(clean[:300])

        response.reasoning_trace = "\n".join(trace_parts) if trace_parts else (
            "Agent completed the task. See the answer for details."
        )

        # ── Set answer ────────────────────────────────────────
        response.answer = answer_text if answer_text else (
            "The agent completed the task but did not produce a displayable answer. "
            "Check the processing trace for details."
        )

        return response

    # ── Text cleaning ────────────────────────────────────────────

    @staticmethod
    def _clean_agent_text(text: str) -> str:
        """Strip internal tags and render user-facing Markdown.

        Removes ALL raw XML tags (execute, observation, solution, think,
        thinking, reasoning, scratchpad, etc.), role delimiters,
        parsing-error retries, agent apologies, and hidden chain-of-thought
        sections.  Only the final answer content reaches the chat bubble.
        """
        import re

        if not text or not text.strip():
            return ""

        # 1. Strip apology / retry prefixes (agent self-correction noise)
        text = re.sub(
            r"^(抱歉|I'm sorry|I apologize|Apologies)[^。\n]*[。\n]\s*",
            "", text, flags=re.IGNORECASE | re.DOTALL,
        )
        text = re.sub(
            r"^(好的|OK|Let me|我来)[^。\n]*重新[^。\n]*[。\n]\s*",
            "", text, flags=re.DOTALL,
        )

        # 2. Strip agent meta-talk about tags / format requirements
        text = re.sub(
            r"由于当前没有需要执行的具体任务[^。\n]*[。\n]\s*",
            "", text,
        )
        text = re.sub(
            r"Please follow the instruction[^。\n]*[。\n]\s*",
            "", text, flags=re.IGNORECASE,
        )

        # 3. Remove role delimiters
        for pattern in [
            r"=+\s*(?:Human|Ai|AI|Tool|System)\s+Message\s*=+",
            r"^(?:Human|Ai|AI|Tool|System)\s+Message\s*:?\s*",
        ]:
            text = re.sub(pattern, "", text, flags=re.MULTILINE | re.IGNORECASE)

        # 4. Strip <execute>...</execute> blocks (code, not for user display)
        text = re.sub(r"<execute>.*?</execute>", "", text, flags=re.DOTALL)
        # 5. Strip <observation>...</observation> blocks
        text = re.sub(r"<observation>.*?</observation>", "", text, flags=re.DOTALL)

        # 6. Full internal-reasoning sanitization — removes <think>,
        #    <thinking>, <reasoning>, <scratchpad>, self-critique headings,
        #    tag residue ("标签结尾。") and all leftover XML-like tags.
        from biochat.utils.text_cleanup import sanitize_assistant_message
        text = sanitize_assistant_message(text)

        # 7. Remove plan checkboxes
        text = re.sub(r"\[ \]\s*", "", text)

        # 8. Collapse excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)

        # 9. Remove separator lines
        text = re.sub(r"={3,}", "", text)

        return text.strip()

    # ── Health check ─────────────────────────────────────────────

    def health_check(self) -> dict[str, Any]:
        """Return a health status dict for monitoring endpoints."""
        return {
            "status": "healthy" if self.is_initialized else "not_initialized",
            "model": self._settings.llm_model,
            "source": self._settings.llm_source or "auto",
            "data_path": self._settings.data_path,
            "timeout_seconds": self._settings.timeout_seconds,
        }


# ═══════════════════════════════════════════════════════════════════
# Module-level singleton (for Streamlit's @st.cache_resource)
# ═══════════════════════════════════════════════════════════════════

_global_service: BioAgentService | None = None
_service_lock = threading.Lock()


def get_agent_service(settings: BiochatSettings | None = None) -> BioAgentService:
    """Return a process-level singleton BioAgentService.

    Thread-safe — safe to call from any Streamlit thread.
    """
    global _global_service
    if _global_service is None:
        with _service_lock:
            if _global_service is None:
                _global_service = BioAgentService(settings=settings)
    return _global_service


def reset_agent_service() -> None:
    """Reset the global service (useful in tests or config changes)."""
    global _global_service
    with _service_lock:
        if _global_service is not None:
            _global_service.shutdown()
        _global_service = None
