"""
LangGraph workflow builder — extracted from ``A1.configure()``,
``generate()``, ``execute()``, and routing functions in ``a1.py``.

This is the most critical extraction: it defines the generate→execute
loop that drives the entire agent.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from biochat.agent.agent_state import AgentState
import logging

if TYPE_CHECKING:
    from biochat.agent.a1 import A1

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Node factory: generation (LLM → <execute> or <solution>)
# ═══════════════════════════════════════════════════════════════

def create_generation_node(agent: "A1") -> Callable[[AgentState], AgentState]:
    """Return the ``generate`` node function for the LangGraph workflow.

    This node:
    1. Assembles the conversation (system prompt + message history).
    2. Calls ``agent.llm.invoke()``.
    3. Parses the response for ``<execute>``, ``<solution>``, or ``<think>`` tags.
    4. Sets ``state["next_step"]`` accordingly.
    5. Handles parsing errors with up to 2 retries.
    """

    def generate(state: AgentState) -> AgentState:
        system_prompt = agent.system_prompt

        # OpenAI-specific formatting hint
        if hasattr(agent.llm, "model_name") and (
            "gpt" in str(agent.llm.model_name).lower()
            or "openai" in str(type(agent.llm)).lower()
        ):
            system_prompt += (
                "\n\nIMPORTANT FOR GPT MODELS: You MUST use XML tags <execute> or "
                "<solution> in EVERY response. Do not use markdown code blocks (```) "
                "— use <execute> tags instead."
            )

        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        response = agent.llm.invoke(messages)

        # Normalise content (list of blocks → plain string)
        msg = _normalise_llm_content(response.content)

        # Fix incomplete tags
        for tag in ("execute", "solution", "think"):
            if f"<{tag}>" in msg and f"</{tag}>" not in msg:
                msg += f"</{tag}>"

        # Parse tags
        execute_match = re.search(r"<execute>(.*?)</execute>", msg, re.DOTALL | re.IGNORECASE)
        answer_match = re.search(r"<solution>(.*?)</solution>", msg, re.DOTALL | re.IGNORECASE)
        think_match = re.search(r"<think>(.*?)</think>", msg, re.DOTALL | re.IGNORECASE)

        # Fallback: treat code blocks as execute (OpenAI quirk)
        if not execute_match:
            code_block = re.search(r"```(?:python|bash|r)?\s*(.*?)```", msg, re.DOTALL)
            if code_block and not answer_match:
                execute_match = code_block

        state["messages"].append(AIMessage(content=msg.strip()))

        # Route based on detected tags
        if answer_match:
            state["next_step"] = "end"
        elif execute_match:
            state["next_step"] = "execute"
        elif think_match:
            state["next_step"] = "generate"
        else:
            # Parsing error — retry or abort
            error_count = sum(
                1 for m in state["messages"]
                if isinstance(m, AIMessage) and "There are no tags" in str(m.content)
            )
            if error_count >= 2:
                logger.warning("Repeated parsing errors — ending conversation")
                state["next_step"] = "end"
                state["messages"].append(AIMessage(
                    content="Execution terminated due to repeated parsing errors."
                ))
            else:
                state["messages"].append(HumanMessage(
                    content="Each response must include thinking process followed by "
                            "either <execute> or <solution> tag. But there are no tags "
                            "in the current response. Please follow the instruction, "
                            "fix and regenerate the response again."
                ))
                state["next_step"] = "generate"

        return state

    return generate


# ═══════════════════════════════════════════════════════════════
# Node factory: execution (Python / R / Bash)
# ═══════════════════════════════════════════════════════════════

def create_execution_node(agent: "A1") -> Callable[[AgentState], AgentState]:
    """Return the ``execute`` node function.

    Extracts code from ``<execute>...</execute>``, dispatches by
    language marker (``#!R``, ``#!BASH``, ``#!CLI``, or Python default),
    runs with timeout, and appends ``<observation>...</observation>``
    to the conversation.
    """

    def execute(state: AgentState) -> AgentState:
        last_message = state["messages"][-1].content
        if "<execute>" in last_message and "</execute>" not in last_message:
            last_message += "</execute>"

        exec_match = re.search(r"<execute>(.*?)</execute>", last_message, re.DOTALL)
        if not exec_match:
            return state

        code = exec_match.group(1)
        timeout = agent.timeout_seconds

        # ── Language dispatch ──────────────────────────────────
        if code.strip().startswith(("#!R", "# R code", "# R script")):
            r_code = re.sub(r"^#!R|^# R code|^# R script", "", code, count=1).strip()
            result = agent._run_r_with_timeout(r_code, timeout)
        elif code.strip().startswith(("#!BASH", "# Bash script", "#!CLI")):
            if code.strip().startswith("#!CLI"):
                cli_cmd = re.sub(r"^#!CLI", "", code, count=1).strip().replace("\n", " ")
                result = agent._run_bash_with_timeout(cli_cmd, timeout)
            else:
                bash_script = re.sub(r"^#!BASH|^# Bash script", "", code, count=1).strip()
                result = agent._run_bash_with_timeout(bash_script, timeout)
        else:
            # Python
            agent._clear_execution_plots()
            agent._inject_custom_functions_to_repl()
            result = agent._run_python_with_timeout(code, timeout)

        # Truncate overly long results
        if len(result) > 10000:
            result = result[:10000] + "\n... [truncated]"

        # Store execution metadata
        if not hasattr(agent, "_execution_results"):
            agent._execution_results = []

        agent._execution_results.append({
            "triggering_message": last_message,
            "images": _capture_current_plots(),
            "timestamp": datetime.now().isoformat(),
        })

        state["messages"].append(AIMessage(content=f"\n<observation>{result}</observation>"))
        return state

    return execute


# ═══════════════════════════════════════════════════════════════
# Router factory
# ═══════════════════════════════════════════════════════════════

def create_router() -> Callable[[AgentState], Literal["execute", "generate", "end"]]:
    """Route based on ``state["next_step"]``."""
    _ROUTE_MAP: dict[str | None, str] = {
        "execute": "execute",
        "generate": "generate",
        "end": "end",
    }

    def router(state: AgentState) -> Literal["execute", "generate", "end"]:
        target = _ROUTE_MAP.get(state.get("next_step"))
        if target is None:
            raise ValueError(f"Unexpected next_step: {state.get('next_step')}")
        return target  # type: ignore[return-value]

    return router


def create_self_critic_router() -> Callable[[AgentState], Literal["generate", "end"]]:
    """Route for self-critic mode (no execute branch)."""
    def router(state: AgentState) -> Literal["generate", "end"]:
        target = state.get("next_step")
        if target == "generate":
            return "generate"
        if target == "end":
            return "end"
        raise ValueError(f"Unexpected next_step in self-critic: {target}")
    return router


# ═══════════════════════════════════════════════════════════════
# Workflow assembly
# ═══════════════════════════════════════════════════════════════

def build_agent_workflow(
    agent: "A1",
    self_critic: bool = False,
) -> StateGraph:
    """Build and return a compiled LangGraph ``StateGraph`` for the agent.

    Args:
        agent: The A1 agent instance (must have ``llm`` and ``system_prompt`` set).
        self_critic: If True, add a self-critic feedback loop after generation.

    Returns:
        A compiled LangGraph workflow ready for ``.stream()``.
    """
    workflow = StateGraph(AgentState)

    # Nodes
    workflow.add_node("generate", create_generation_node(agent))
    workflow.add_node("execute", create_execution_node(agent))

    if self_critic:
        from biochat.agent.self_critic import create_self_critic_node
        workflow.add_node("self_critic", create_self_critic_node(agent))
        workflow.add_conditional_edges(
            "generate",
            create_router(),
            path_map={"execute": "execute", "generate": "generate", "end": "self_critic"},
        )
        workflow.add_conditional_edges(
            "self_critic",
            create_self_critic_router(),
            path_map={"generate": "generate", "end": END},
        )
    else:
        workflow.add_conditional_edges(
            "generate",
            create_router(),
            path_map={"execute": "execute", "generate": "generate", "end": END},
        )

    workflow.add_edge("execute", "generate")
    workflow.add_edge(START, "generate")

    from langgraph.checkpoint.memory import MemorySaver
    compiled = workflow.compile()
    compiled.checkpointer = MemorySaver()
    return compiled


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _normalise_llm_content(content: Any) -> str:
    """Convert LLM response content (str or list of dicts) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                btype = block.get("type", "")
                if btype in ("text", "output_text", "redacted_text"):
                    text = block.get("text") or block.get("content") or ""
                    if isinstance(text, str):
                        parts.append(text)
        return "".join(parts)
    return str(content)


def _capture_current_plots() -> list[str]:
    """Retrieve base64-encoded plots from the execution environment."""
    try:
        from biochat.tool.support_tools import get_captured_plots
        return list(get_captured_plots())
    except Exception:
        return []
