"""
Agent resource management — tools, data, software, and MCP servers.

Extracted from the A1 methods for adding, listing, getting, and
removing custom resources.  Provides a ``ResourceRegistry`` helper
class that unifies the storage pattern previously duplicated across
``_custom_functions``, ``_custom_tools``, ``_custom_data``, and
``_custom_software`` dicts.
"""

from __future__ import annotations

import inspect
import os
import sys
import types as _types
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from biochat.agent.a1 import A1


# ═══════════════════════════════════════════════════════════════
# Tool management
# ═══════════════════════════════════════════════════════════════

def add_custom_tool(agent: "A1", api: callable) -> dict:
    """Register a callable as a Biochat tool.

    Replaces ``A1.add_tool()``.
    """
    try:
        function_code = inspect.getsource(api)
        module_name = getattr(api, "__module__", "custom_tools")
        function_name = getattr(api, "__name__", str(api))

        schema = agent._function_to_api_schema(function_code)

        if not isinstance(schema, dict):
            raise ValueError("Generated schema is not a dictionary")

        # Ensure required fields
        schema.setdefault("name", function_name)
        schema.setdefault("description", f"Custom tool: {function_name}")
        schema.setdefault("required_parameters", [])
        schema["module"] = module_name

        # Register in tool_registry
        if hasattr(agent, "tool_registry") and agent.tool_registry is not None:
            try:
                agent.tool_registry.register_tool(schema)
            except Exception as e:
                print(f"Warning: Failed to register tool in registry: {e}")

        # Add to module2api
        _ensure_module2api(agent)
        existing = _find_existing_tool(agent, module_name, schema["name"])
        if existing:
            existing.update(schema)
        else:
            agent.module2api.setdefault(module_name, []).append(schema)

        # Rebuild registry dataframe
        _rebuild_registry_dataframe(agent)

        # Store function for execution
        agent._custom_functions = getattr(agent, "_custom_functions", {})
        agent._custom_functions[schema["name"]] = api

        agent._custom_tools = getattr(agent, "_custom_tools", {})
        agent._custom_tools[schema["name"]] = {
            "name": schema["name"],
            "description": schema["description"],
            "module": module_name,
        }

        # Inject into builtins for REPL access
        import builtins
        if not hasattr(builtins, "_biochat_custom_functions"):
            builtins._biochat_custom_functions = {}
        builtins._biochat_custom_functions[schema["name"]] = api

        agent.configure()
        return schema
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise


# ═══════════════════════════════════════════════════════════════
# Data & software management (unified pattern)
# ═══════════════════════════════════════════════════════════════

def add_custom_data(agent: "A1", data: dict[str, str]) -> bool:
    """Register custom data items in the agent's data lake.

    Replaces ``A1.add_data()``.
    """
    if not isinstance(data, dict):
        raise ValueError("Data must be a dictionary with file path as key and description as value")

    agent._custom_data = getattr(agent, "_custom_data", {})
    for file_path, description in data.items():
        if not isinstance(file_path, str) or not isinstance(description, str):
            continue
        filename = os.path.basename(file_path) if "/" in file_path else file_path
        agent._custom_data[filename] = {"path": file_path, "description": description}
        agent.data_lake_dict[filename] = description

    agent.configure()
    return True


def add_custom_software(agent: "A1", software: dict[str, str]) -> bool:
    """Register custom software in the agent's library.

    Replaces ``A1.add_software()``.
    """
    if not isinstance(software, dict):
        raise ValueError("Software must be a dictionary with name as key and description as value")

    agent._custom_software = getattr(agent, "_custom_software", {})
    for sw_name, description in software.items():
        if not isinstance(sw_name, str) or not isinstance(description, str):
            continue
        agent._custom_software[sw_name] = {"name": sw_name, "description": description}
        agent.library_content_dict[sw_name] = description

    agent.configure()
    return True


# ═══════════════════════════════════════════════════════════════
# Unified removal
# ═══════════════════════════════════════════════════════════════

def remove_custom_tool(agent: "A1", name: str) -> bool:
    """Remove a custom tool from all registries.

    Replaces ``A1.remove_custom_tool()``.
    """
    removed = False

    # custom_functions
    if hasattr(agent, "_custom_functions") and name in agent._custom_functions:
        del agent._custom_functions[name]
        removed = True

    # custom_tools
    if hasattr(agent, "_custom_tools") and name in agent._custom_tools:
        del agent._custom_tools[name]
        removed = True

    # builtins
    import builtins
    if hasattr(builtins, "_biochat_custom_functions") and name in builtins._biochat_custom_functions:
        del builtins._biochat_custom_functions[name]

    # tool_registry
    if hasattr(agent, "tool_registry") and agent.tool_registry is not None:
        if agent.tool_registry.remove_tool_by_name(name):
            removed = True
            _rebuild_registry_dataframe(agent)

    # module2api
    if hasattr(agent, "module2api"):
        for tools in agent.module2api.values():
            for i, tool in enumerate(tools):
                if tool.get("name") == name:
                    del tools[i]
                    removed = True
                    break

    if removed:
        print(f"Custom tool '{name}' has been removed")
    else:
        print(f"Custom tool '{name}' was not found")
    return removed


def remove_custom_data(agent: "A1", name: str) -> bool:
    """Remove a custom data item."""
    removed = False
    if hasattr(agent, "_custom_data") and name in agent._custom_data:
        del agent._custom_data[name]
        removed = True
    if hasattr(agent, "data_lake_dict") and name in agent.data_lake_dict:
        del agent.data_lake_dict[name]
        removed = True
    return removed


def remove_custom_software(agent: "A1", name: str) -> bool:
    """Remove a custom software item."""
    removed = False
    if hasattr(agent, "_custom_software") and name in agent._custom_software:
        del agent._custom_software[name]
        removed = True
    if hasattr(agent, "library_content_dict") and name in agent.library_content_dict:
        del agent.library_content_dict[name]
        removed = True
    return removed


# ═══════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════

def _ensure_module2api(agent: "A1") -> None:
    if not hasattr(agent, "module2api") or agent.module2api is None:
        agent.module2api = {}


def _find_existing_tool(agent: "A1", module_name: str, tool_name: str) -> dict | None:
    for existing in agent.module2api.get(module_name, []):
        if existing.get("name") == tool_name:
            return existing
    return None


def _rebuild_registry_dataframe(agent: "A1") -> None:
    if not hasattr(agent, "tool_registry") or agent.tool_registry is None:
        return
    try:
        docs = [
            [int(tid), agent.tool_registry.get_tool_by_id(int(tid))]
            for tid in range(len(agent.tool_registry.tools))
        ]
        agent.tool_registry.document_df = pd.DataFrame(docs, columns=["docid", "document_content"])
    except Exception as e:
        print(f"Warning: Failed to rebuild registry dataframe: {e}")


def _function_to_api_schema(agent: "A1", function_string: str) -> Any:
    """Thin wrapper around the LLM-based schema generator.

    Kept here to avoid circular imports with the full utils module.
    """
    from biochat.utils.api_schema import generate_api_schema_from_code
    return generate_api_schema_from_code(function_string, agent.llm)
