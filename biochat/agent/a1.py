"""
A1 Agent — slim composition layer over sub-modules.

All heavyweight logic has been extracted to dedicated modules:
- ``workflow.py``    — LangGraph node factories and compilation
- ``resource_manager.py`` — tool / data / software / MCP management
- ``retrieval.py``   — resource retrieval & system-prompt update
- ``conversation_exporter.py`` — Markdown generation & PDF export
- ``mcp_server.py``  — MCP server creation
- ``ui_launcher.py`` — Gradio / Biochat UI launch delegation
- ``self_critic.py`` — self-critic feedback node
- ``agent_state.py`` — AgentState TypedDict

Public method signatures are **fully preserved** for backward
compatibility with the original 3028-line monolithic ``a1.py``.
"""

from __future__ import annotations

import glob
import os
import re
from collections.abc import Generator
from typing import Any, Literal

import pandas as pd
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from biochat.agent.agent_state import AgentState  # noqa: F401 — re-exported for external use
from biochat.config import default_config
from biochat.core.settings import biochat_settings
from biochat.execution import CodeExecutor, create_code_executor, format_result
from biochat.knowledge import KnowledgeRegistry
from biochat.llm import SourceType, get_llm
from biochat.model.resource_selector import ResourceSelector
from biochat.tool.registry import ToolRegistry
from biochat.utils import (
    check_and_download_s3_files,
    format_execute_tags_in_content,
    format_lists_in_text,
    format_observation_as_terminal,
    function_to_api_schema,
    has_execution_results,
    parse_tool_calls_with_modules,
    pretty_print,
    read_module2api,
    textify_api_dict,
)

if os.path.exists(".env"):
    load_dotenv(".env", override=False)


# ═══════════════════════════════════════════════════════════════
# A1 — composition facade
# ═══════════════════════════════════════════════════════════════

class A1:
    """General-purpose biomedical AI agent.

    Public API preserved 1:1 with the original monolithic ``A1``.
    Internal implementation delegates to focused sub-modules.
    """

    def __init__(
        self,
        path: str | None = None,
        llm: str | None = None,
        source: SourceType | None = None,
        use_tool_retriever: bool | None = None,
        timeout_seconds: int | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        commercial_mode: bool | None = None,
        tool_profile: str | None = None,
        expected_data_lake_files: list | None = None,
        *,
        allow_host_code_execution: bool | None = None,
    ):
        # ── Resolve parameters from default_config ─────────────
        path = path or default_config.path
        llm = llm or default_config.llm
        source = source or default_config.source
        use_tool_retriever = (
            default_config.use_tool_retriever if use_tool_retriever is None
            else use_tool_retriever
        )
        timeout_seconds = timeout_seconds or default_config.timeout_seconds
        base_url = base_url or default_config.base_url
        api_key = api_key or default_config.api_key or "EMPTY"
        commercial_mode = (
            default_config.commercial_mode if commercial_mode is None
            else commercial_mode
        )
        tool_profile = (
            default_config.tool_profile if tool_profile is None
            else tool_profile
        )

        # ── Load environment descriptors ───────────────────────
        if commercial_mode:
            from biochat.env_desc_cm import data_lake_dict, library_content_dict
        else:
            from biochat.env_desc import data_lake_dict, library_content_dict

        self.data_lake_dict = data_lake_dict
        self.library_content_dict = library_content_dict
        self.commercial_mode = commercial_mode

        # ── Data lake ──────────────────────────────────────────
        self.path = path
        os.makedirs(path, exist_ok=True)
        data_lake_dir = os.path.join(path, "biomni_data", "data_lake")
        benchmark_dir = os.path.join(path, "biomni_data", "benchmark")
        os.makedirs(data_lake_dir, exist_ok=True)
        os.makedirs(benchmark_dir, exist_ok=True)

        if expected_data_lake_files is None:
            expected_data_lake_files = list(self.data_lake_dict.keys())
            check_and_download_s3_files(
                "https://biomni-release.s3.amazonaws.com",
                data_lake_dir, expected_data_lake_files, folder="data_lake",
            )
            if not (os.path.isdir(benchmark_dir) and
                    os.path.isdir(os.path.join(benchmark_dir, "hle"))):
                check_and_download_s3_files(
                    "https://biomni-release.s3.amazonaws.com",
                    benchmark_dir, [], folder="benchmark",
                )

        self.path = os.path.join(path, "biomni_data")

        # ── LLM ────────────────────────────────────────────────
        self.tool_profile = tool_profile
        self.module2api = read_module2api(profile=self.tool_profile)
        self.llm = get_llm(
            llm, stop_sequences=["</execute>", "</solution>"],
            source=source, base_url=base_url, api_key=api_key,
            config=default_config,
        )
        self.use_tool_retriever = use_tool_retriever

        if self.use_tool_retriever:
            self.tool_registry = ToolRegistry(self.module2api,
                                              profile=self.tool_profile)
            self.retriever = ResourceSelector()

        # ── Know-how ───────────────────────────────────────────
        self.know_how_loader = KnowledgeRegistry()
        if commercial_mode:
            self._filter_know_how_for_commercial_mode()

        # ── Execution config ───────────────────────────────────
        self.timeout_seconds = timeout_seconds
        self.self_critic = False
        self.critic_count = 0
        self.user_task = ""
        self._execution_results: list[dict] = []
        self.log: list[str] = []
        self.system_prompt: str = ""
        self.app: Any = None

        # ── Execution policy boundary ──────────────────────────
        # Host execution is only selected when explicitly enabled via
        # settings (BIOCHAT_ALLOW_HOST_CODE_EXECUTION / constructor).
        from biochat.core.settings import BiochatSettings as _BiochatSettings

        if allow_host_code_execution is None:
            executor_settings = biochat_settings
        else:
            executor_settings = _BiochatSettings(
                allow_host_code_execution=allow_host_code_execution
            )
        self.code_executor: CodeExecutor = create_code_executor(executor_settings)

        # ── Build workflow ─────────────────────────────────────
        self.configure()

    # ═══════════════════════════════════════════════════════════
    # Configuration & workflow
    # ═══════════════════════════════════════════════════════════

    def configure(self, self_critic: bool = False, test_time_scale_round: int = 0) -> None:
        """(Re-)build the agent's system prompt and LangGraph workflow.

        Delegates to ``workflow.build_agent_workflow()``.
        """
        self.self_critic = self_critic

        # Build system prompt (delegated to SystemPromptBuilder)
        data_lake_path = self.path + "/data_lake"
        data_lake_items = [
            x.split("/")[-1] for x in glob.glob(data_lake_path + "/*")
        ]
        data_lake_with_desc = [
            {"name": item, "description": self.data_lake_dict.get(item, f"Data lake item: {item}")}
            for item in data_lake_items
        ]
        # Include custom data
        if hasattr(self, "_custom_data") and self._custom_data:
            for name, info in self._custom_data.items():
                data_lake_with_desc.append({"name": name, "description": info["description"]})

        tool_desc = {
            mod: [t for t in tools if t.get("name") != "run_python_repl"]
            for mod, tools in self.module2api.items()
        }

        library_list = list(self.library_content_dict.keys())
        if hasattr(self, "_custom_software") and self._custom_software:
            for name in self._custom_software:
                if name not in library_list:
                    library_list.append(name)

        custom_tools = self._collect_custom_items("_custom_tools")
        custom_data = self._collect_custom_items("_custom_data")
        custom_software = self._collect_custom_items("_custom_software")
        know_how_docs = self._collect_know_how_docs()

        self.system_prompt = self._generate_system_prompt(
            tool_desc=tool_desc,
            data_lake_content=data_lake_with_desc,
            library_content_list=library_list,
            self_critic=self_critic,
            is_retrieval=False,
            custom_tools=custom_tools,
            custom_data=custom_data,
            custom_software=custom_software,
            know_how_docs=know_how_docs,
        )

        # Build LangGraph workflow via the extracted module
        from biochat.agent.workflow import build_agent_workflow
        self.app = build_agent_workflow(self, self_critic=self_critic)
        # Backward-compat: expose checkpointer on the agent instance
        self.checkpointer = getattr(self.app, "checkpointer", None)

    # ═══════════════════════════════════════════════════════════
    # Execution — go / go_stream
    # ═══════════════════════════════════════════════════════════

    def go(self, prompt: str):
        """Execute the agent synchronously.  Returns (log, final_text)."""
        self.critic_count = 0
        self.user_task = prompt

        if self.use_tool_retriever:
            self._run_retrieval(prompt)

        inputs = {"messages": [HumanMessage(content=prompt)], "next_step": None}
        config = {"recursion_limit": 500, "configurable": {"thread_id": 42}}
        self.log = []
        final_state = None

        for s in self.app.stream(inputs, stream_mode="values", config=config):
            message = s["messages"][-1]
            self.log.append(pretty_print(message))
            final_state = s

        self._conversation_state = final_state
        return self.log, message.content

    def go_stream(self, prompt) -> Generator[dict, None, None]:
        """Execute the agent with token-level streaming yields.

        Yields dicts:
          - ``{"type": "token", "content": str, "chunk_position": ...}``
            LLM token chunks, emitted live as the model generates
            (``chunk_position`` is ``"last"`` on the final chunk of each
            generation).
          - ``{"type": "message", "output": <pretty-printed text>}``
            Completed conversation messages (AI responses, retry prompts,
            observations) — same text shape as the legacy event stream.
        """
        self.critic_count = 0
        self.user_task = prompt

        if self.use_tool_retriever:
            self._run_retrieval(prompt)

        # Best-effort: enable token streaming on the underlying chat model.
        # ``invoke()`` still returns the full message, so models that do not
        # support streaming degrade gracefully (message events only).
        try:
            if hasattr(self.llm, "streaming"):
                self.llm.streaming = True
        except Exception:
            pass

        inputs = {"messages": [HumanMessage(content=prompt)], "next_step": None}
        config = {"recursion_limit": 500, "configurable": {"thread_id": 42}}
        self.log = []
        final_state = None

        for mode, payload in self.app.stream(
            inputs, stream_mode=["messages", "values"], config=config
        ):
            if mode == "messages":
                chunk, _meta = (
                    payload
                    if isinstance(payload, (tuple, list)) and len(payload) == 2
                    else (payload, {})
                )
                if not hasattr(chunk, "content"):
                    continue
                content = chunk.content
                if not isinstance(content, str):
                    # Normalise list-of-blocks content to plain text
                    if isinstance(content, list):
                        content = "".join(
                            str(b.get("text", "")) if isinstance(b, dict) else str(b)
                            for b in content
                        )
                    else:
                        content = str(content)
                yield {
                    "type": "token",
                    "content": content,
                    "chunk_position": getattr(chunk, "chunk_position", None),
                }
            else:  # "values" — full state snapshot after each node
                message = payload["messages"][-1]
                out = pretty_print(message)
                self.log.append(out)
                final_state = payload
                yield {"type": "message", "output": out}

        self._conversation_state = final_state

    # ═══════════════════════════════════════════════════════════
    # Retrieval
    # ═══════════════════════════════════════════════════════════

    def _run_retrieval(self, prompt: str) -> None:
        """Execute retrieval and update system prompt."""
        from biochat.agent.retrieval import retrieve_relevant_resources, apply_retrieval_results
        selected = retrieve_relevant_resources(self, prompt)
        if selected:
            apply_retrieval_results(self, selected)

    def _prepare_resources_for_retrieval(self, prompt: str):
        """Public API preserved: returns selected resource names."""
        from biochat.agent.retrieval import retrieve_relevant_resources
        return retrieve_relevant_resources(self, prompt)

    def update_system_prompt_with_selected_resources(self, selected_resources: dict) -> None:
        """Public API preserved: update prompt from retrieval results."""
        from biochat.agent.retrieval import apply_retrieval_results
        apply_retrieval_results(self, selected_resources)

    # ═══════════════════════════════════════════════════════════
    # System prompt generation
    # ═══════════════════════════════════════════════════════════

    def _generate_system_prompt(
        self, tool_desc, data_lake_content, library_content_list,
        self_critic=False, is_retrieval=False, custom_tools=None,
        custom_data=None, custom_software=None, know_how_docs=None,
    ) -> str:
        """Generate the system prompt (delegates to SystemPromptBuilder)."""
        from biochat.prompts.system_prompt import SystemPromptBuilder

        builder = SystemPromptBuilder(
            tool_desc=tool_desc,
            data_lake_content=data_lake_content,
            library_content_list=library_content_list,
            data_lake_path=self.path + "/data_lake",
            data_lake_dict=self.data_lake_dict,
            library_content_dict=self.library_content_dict,
            self_critic=self_critic,
            custom_tools=custom_tools,
            custom_data=custom_data,
            custom_software=custom_software,
            know_how_docs=know_how_docs,
        )
        return builder.build(is_retrieval=is_retrieval)

    # ═══════════════════════════════════════════════════════════
    # Resource management — delegated to resource_manager
    # ═══════════════════════════════════════════════════════════

    def add_tool(self, api) -> dict:
        from biochat.agent.resource_manager import add_custom_tool
        return add_custom_tool(self, api)

    def add_mcp(self, config_path: str = "./tutorials/examples/mcp_config.yaml") -> None:
        # MCP management is complex — keep inline for now, delegates internally
        import asyncio
        import types as _types
        from pathlib import Path

        import nest_asyncio
        import yaml
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        nest_asyncio.apply()

        def _discover(server_params):
            async def _run():
                async with stdio_client(server_params) as (reader, writer):
                    async with ClientSession(reader, writer) as session:
                        await session.initialize()
                        result = await session.list_tools()
                        tools = result.tools if hasattr(result, "tools") else result
                        return [
                            {"name": t.name, "description": t.description,
                             "inputSchema": t.inputSchema}
                            for t in tools if hasattr(t, "name")
                        ]
            return asyncio.run(_run())

        def _make_wrapper(cmd, args, tool_name, doc, env_vars=None):
            def _sync(**kwargs):
                try:
                    sp = StdioServerParameters(command=cmd, args=args, env=env_vars)
                    async def _call():
                        async with stdio_client(sp) as (r, w):
                            async with ClientSession(r, w) as session:
                                await session.initialize()
                                res = await session.call_tool(tool_name, kwargs)
                                c = res.content[0]
                                return c.json() if hasattr(c, "json") else c.text
                    try:
                        loop = asyncio.get_running_loop()
                        return loop.create_task(_call())
                    except RuntimeError:
                        return asyncio.run(_call())
                except Exception as e:
                    raise RuntimeError(f"MCP tool '{tool_name}' failed: {e}") from e
            _sync.__name__ = tool_name
            _sync.__doc__ = doc
            return _sync

        self._custom_functions = getattr(self, "_custom_functions", {})
        self._custom_tools = getattr(self, "_custom_tools", {})

        try:
            cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
        except FileNotFoundError:
            raise FileNotFoundError(f"MCP config not found: {config_path}") from None

        mcp_servers: dict = cfg.get("mcp_servers", {})
        if not mcp_servers:
            print("Warning: No MCP servers found in configuration")
            return

        for srv_name, srv_meta in mcp_servers.items():
            if not srv_meta.get("enabled", True):
                continue
            cmd_list = srv_meta.get("command", [])
            if not cmd_list or not isinstance(cmd_list, list):
                print(f"Warning: Invalid command configuration for server '{srv_name}'")
                continue

            cmd, *args = cmd_list
            env_vars = srv_meta.get("env", {})
            if env_vars:
                env_vars = {
                    k: os.getenv(v[2:-1], "") if isinstance(v, str) and v.startswith("${") and v.endswith("}")
                    else v for k, v in env_vars.items()
                }

            mcp_mod_name = f"mcp_servers.{srv_name}"
            if mcp_mod_name not in __import__("sys").modules:
                __import__("sys").modules[mcp_mod_name] = _types.ModuleType(mcp_mod_name)
            srv_mod = __import__("sys").modules[mcp_mod_name]

            tools_cfg = srv_meta.get("tools", [])
            if not tools_cfg:
                try:
                    sp = StdioServerParameters(command=cmd, args=args, env=env_vars)
                    tools_cfg = _discover(sp)
                    if tools_cfg:
                        print(f"Discovered {len(tools_cfg)} tools from {srv_name} MCP server")
                    else:
                        print(f"Warning: No tools discovered from {srv_name} MCP server")
                        continue
                except Exception as e:
                    print(f"Failed to discover tools for {srv_name}: {e}")
                    continue

            for tool_meta in tools_cfg:
                if isinstance(tool_meta, dict) and "biochat_name" in tool_meta:
                    tn = tool_meta["biochat_name"]
                    desc = tool_meta.get("description", f"MCP tool: {tn}")
                    params = tool_meta.get("parameters", {})
                    req_names = [pn for pn, ps in params.items() if ps.get("required", False)]
                else:
                    tn = tool_meta.get("name")
                    desc = tool_meta.get("description", f"MCP tool: {tn}")
                    schema = tool_meta.get("inputSchema", {})
                    params = schema.get("properties", {})
                    req_names = schema.get("required", [])

                if not tn:
                    continue

                wrapper = _make_wrapper(cmd, args, tn, desc, env_vars)
                setattr(srv_mod, tn, wrapper)

                req_params, opt_params = [], []
                for pn, ps in params.items():
                    pi = {"name": pn, "type": str(ps.get("type", "string")),
                          "description": ps.get("description", ""),
                          "default": ps.get("default")}
                    (req_params if pn in req_names else opt_params).append(pi)

                tool_schema = {
                    "name": tn, "description": desc,
                    "parameters": params,
                    "required_parameters": req_params,
                    "optional_parameters": opt_params,
                    "module": mcp_mod_name, "fn": wrapper,
                }

                self.tool_registry.register_tool(tool_schema)
                self.module2api.setdefault(mcp_mod_name, []).append(tool_schema)
                self._custom_functions[tn] = wrapper
                self._custom_tools[tn] = {"name": tn, "description": desc, "module": mcp_mod_name}

        self.configure()

    def add_data(self, data: dict) -> bool:
        from biochat.agent.resource_manager import add_custom_data
        return add_custom_data(self, data)

    def add_software(self, software: dict) -> bool:
        from biochat.agent.resource_manager import add_custom_software
        return add_custom_software(self, software)

    def remove_custom_tool(self, name: str) -> bool:
        from biochat.agent.resource_manager import remove_custom_tool as _rm
        return _rm(self, name)

    def remove_custom_data(self, name: str) -> bool:
        from biochat.agent.resource_manager import remove_custom_data as _rm
        return _rm(self, name)

    def remove_custom_software(self, name: str) -> bool:
        from biochat.agent.resource_manager import remove_custom_software as _rm
        return _rm(self, name)

    def get_custom_tool(self, name: str):
        return getattr(self, "_custom_functions", {}).get(name)

    def get_custom_data(self, name: str):
        return getattr(self, "_custom_data", {}).get(name)

    def get_custom_software(self, name: str):
        return getattr(self, "_custom_software", {}).get(name)

    def list_custom_tools(self) -> list[str]:
        return list(getattr(self, "_custom_functions", {}).keys())

    def list_custom_data(self) -> list:
        cd = getattr(self, "_custom_data", {})
        return [(n, i.get("description", "")) for n, i in cd.items()]

    def list_custom_software(self) -> list:
        cs = getattr(self, "_custom_software", {})
        return [(n, i.get("description", "")) for n, i in cs.items()]

    # ═══════════════════════════════════════════════════════════
    # Markdown generation & PDF export — delegated to conversation_exporter
    # ═══════════════════════════════════════════════════════════

    def _generate_markdown_content(self, include_images: bool = True) -> str:
        """Generate Markdown from conversation history."""
        from biochat.agent.conversation_exporter import ConversationMarkdownBuilder
        return ConversationMarkdownBuilder(self, include_images=include_images).build()

    def save_conversation_history(
        self, filepath: str, include_images: bool = True, save_pdf: bool = True
    ) -> None:
        from biochat.agent.conversation_exporter import export_conversation_to_pdf
        if not save_pdf:
            return
        export_conversation_to_pdf(self, filepath, include_images=include_images)

    def result_formatting(self, output_class, task_intention) -> dict:
        checker_llm = (
            ChatPromptTemplate.from_messages([
                ("system", f"You are evaluateGPT. Review the history. Output: {task_intention}"),
                ("placeholder", "{messages}"),
            ])
            | self.llm.with_structured_output(output_class)
        )
        return checker_llm.invoke({"messages": [("user", str(self.log))]}).dict()

    # ═══════════════════════════════════════════════════════════
    # MCP server — delegated to mcp_server
    # ═══════════════════════════════════════════════════════════

    def create_mcp_server(self, tool_modules=None):
        from biochat.agent.mcp_server import build_biochat_mcp_server
        return build_biochat_mcp_server(self, tool_modules)

    # ═══════════════════════════════════════════════════════════
    # UI launchers
    # ═══════════════════════════════════════════════════════════

    def launch_biochat_ui(
        self, thread_id=42, share=False, server_name="0.0.0.0", require_verification=False
    ) -> None:
        from biochat.agent.ui_launcher import launch_biochat_ui_from_agent
        launch_biochat_ui_from_agent(
            self, thread_id=thread_id, share=share,
            server_name=server_name, require_verification=require_verification,
        )

    def launch_gradio_demo(
        self, thread_id=42, share=False, server_name="0.0.0.0", require_verification=False
    ) -> None:
        """Legacy Gradio demo — preserved for backward compatibility.

        Note: this method contains ~375 lines of inlined Gradio UI code
        that has been moved to ``biochat/ui/gradio_legacy.py``.  We keep
        a thin wrapper here.
        """
        from biochat.ui.gradio_legacy import launch_legacy_gradio_ui
        launch_legacy_gradio_ui(
            self, thread_id=thread_id, share=share,
            server_name=server_name, require_verification=require_verification,
        )

    # ═══════════════════════════════════════════════════════════
    # Internal helpers (thin wrappers around utilities)
    # ═══════════════════════════════════════════════════════════

    def _parse_tool_calls_from_code(self, code: str) -> list[str]:
        from biochat.utils import parse_tool_calls_from_code as _p
        return _p(code, self.module2api, getattr(self, "_custom_functions", {}))

    def _parse_tool_calls_with_modules(self, code: str) -> list[tuple[str, str]]:
        return parse_tool_calls_with_modules(
            code, self.module2api, getattr(self, "_custom_functions", {})
        )

    def _inject_custom_functions_to_repl(self, session_id: str = "default") -> None:
        """Register custom callables into the executor's session namespace."""
        for name, function in getattr(self, "_custom_functions", {}).items():
            self.code_executor.register_function(session_id, name, function)

    def _clear_execution_plots(self) -> None:
        try:
            from biochat.tool.support_tools import clear_captured_plots
            clear_captured_plots()
        except Exception:
            pass

    def _run_python_with_timeout(self, code: str, timeout: int, session_id: str = "default") -> str:
        """Deprecated wrapper — the workflow calls ``self.code_executor`` directly."""
        self._inject_custom_functions_to_repl(session_id)
        return format_result(
            self.code_executor.execute_python(code, timeout=timeout, session_id=session_id)
        )

    def _run_r_with_timeout(self, code: str, timeout: int, session_id: str = "default") -> str:
        """Deprecated wrapper — the workflow calls ``self.code_executor`` directly."""
        return format_result(
            self.code_executor.execute_r(code, timeout=timeout, session_id=session_id)
        )

    def _run_bash_with_timeout(self, code: str, timeout: int, session_id: str = "default") -> str:
        """Deprecated wrapper — the workflow calls ``self.code_executor`` directly."""
        return format_result(
            self.code_executor.execute_bash(code, timeout=timeout, session_id=session_id)
        )

    def _filter_know_how_for_commercial_mode(self) -> None:
        for doc_id in self.know_how_loader.exclude_non_commercial():
            print(f"  ⚠️  Excluded know-how '{doc_id}' (non-commercial license)")

    def _collect_custom_items(self, attr: str) -> list[dict] | None:
        storage = getattr(self, attr, None)
        if not storage:
            return None
        result: list[dict] = []
        for name, info in storage.items():
            if isinstance(info, dict):
                result.append({"name": name, "description": info.get("description", ""),
                                "module": info.get("module", "custom")})
            else:
                result.append({"name": name, "description": str(info)})
        return result or None

    def _collect_know_how_docs(self) -> list[dict] | None:
        if not hasattr(self, "know_how_loader") or not self.know_how_loader.documents:
            return None
        return [
            {"id": d["id"], "name": d["name"], "description": d["description"],
             "content": d["content_without_metadata"], "metadata": d["metadata"]}
            for d in self.know_how_loader.documents.values()
        ] or None
