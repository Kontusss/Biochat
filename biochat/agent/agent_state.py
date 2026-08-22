"""
Agent state type definition — extracted from the original ``a1.py``.

Defines the ``AgentState`` TypedDict used by the LangGraph workflow.

.. note::

   The ``messages`` field uses ``Annotated[..., add_messages]`` which
   tells LangGraph's checkpointer to **append** new messages rather
   than overwrite.  This is required for multi-turn conversation memory.
   The original code used a plain ``list[BaseMessage]`` which silently
   broke multi-turn state retention.
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """The state carried through each step of the agent's LangGraph workflow.

    Attributes:
        messages: Accumulated conversation messages.  ``add_messages``
                  reducer ensures new messages are appended (not overwritten)
                  when the checkpointer restores previous state.
        next_step: Routing key for the next workflow node.
        session_id: Validated conversation identifier supplied by
                    ``A1.go``/``A1.go_stream``; execution nodes forward it
                    to the code executor so namespaces stay per-session.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    next_step: str | None
    session_id: str
