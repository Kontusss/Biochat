"""
Resource retrieval — extracted from ``A1._prepare_resources_for_retrieval()``
and ``A1.update_system_prompt_with_selected_resources()``.

Orchestrates tool / data-lake / library / know-how retrieval using
the agent's LLM for semantic relevance scoring.
"""

from __future__ import annotations

import glob
from typing import TYPE_CHECKING, Any

import logging

if TYPE_CHECKING:
    from biochat.agent.a1 import A1

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════

def retrieve_relevant_resources(agent: "A1", prompt: str) -> dict | None:
    """Query the tool retriever for resources relevant to *prompt*.

    Returns a dict with keys ``"tools"``, ``"data_lake"``,
    ``"libraries"``, ``"know_how"`` — each a list of selected items.
    Returns ``None`` if ``use_tool_retriever`` is disabled.
    """
    if not agent.use_tool_retriever:
        return None

    # Gather all available resources
    all_tools = agent.tool_registry.tools if hasattr(agent, "tool_registry") else []

    data_lake_path = agent.path + "/data_lake"
    data_lake_files = glob.glob(data_lake_path + "/*")
    data_lake_items = [x.split("/")[-1] for x in data_lake_files]

    # Build data lake descriptions
    data_lake_descriptions = _build_data_lake_descriptions(agent, data_lake_items)

    # Build library descriptions
    library_descriptions = _build_library_descriptions(agent)

    # Know-how summaries
    know_how_summaries = agent.know_how_loader.get_document_summaries()

    resources = {
        "tools": all_tools,
        "data_lake": data_lake_descriptions,
        "libraries": library_descriptions,
        "know_how": know_how_summaries,
    }

    selected = agent.retriever.prompt_based_retrieval(prompt, resources, llm=agent.llm)

    # Normalise selected resources
    result = _normalise_selected_resources(agent, selected)
    _print_retrieval_summary(result)
    return result


def apply_retrieval_results(agent: "A1", selected_resources: dict) -> None:
    """Update the agent's system prompt to reflect retrieved resources."""
    tool_desc = _build_tool_desc_from_selection(agent, selected_resources["tools"])
    data_lake_with_desc = _build_data_lake_desc_from_selection(
        agent, selected_resources["data_lake"]
    )

    custom_tools = _get_custom_items(agent, "_custom_tools")
    custom_data = _get_custom_items(agent, "_custom_data")
    custom_software = _get_custom_items(agent, "_custom_software")
    know_how_docs = selected_resources.get("know_how", [])

    agent.system_prompt = agent._generate_system_prompt(
        tool_desc=tool_desc,
        data_lake_content=data_lake_with_desc,
        library_content_list=selected_resources["libraries"],
        self_critic=getattr(agent, "self_critic", False),
        is_retrieval=True,
        custom_tools=custom_tools if custom_tools else None,
        custom_data=custom_data if custom_data else None,
        custom_software=custom_software if custom_software else None,
        know_how_docs=know_how_docs if know_how_docs else None,
    )


# ═══════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════

def _build_data_lake_descriptions(agent: "A1", items: list[str]) -> list[dict]:
    result: list[dict] = []
    for item in items:
        desc = agent.data_lake_dict.get(item, f"Data lake item: {item}")
        result.append({"name": item, "description": desc})
    if hasattr(agent, "_custom_data") and agent._custom_data:
        for name, info in agent._custom_data.items():
            result.append({"name": name, "description": info.get("description", "")})
    return result


def _build_library_descriptions(agent: "A1") -> list[dict]:
    result = [
        {"name": name, "description": desc}
        for name, desc in agent.library_content_dict.items()
    ]
    if hasattr(agent, "_custom_software") and agent._custom_software:
        for name, info in agent._custom_software.items():
            if not any(lib["name"] == name for lib in result):
                result.append({"name": name, "description": info.get("description", "")})
    return result


def _normalise_selected_resources(agent: "A1", selected: dict) -> dict:
    """Convert retrieval results to standardised format."""
    result: dict[str, Any] = {
        "tools": selected["tools"],
        "data_lake": [],
        "libraries": [
            lib["name"] if isinstance(lib, dict) else lib
            for lib in selected["libraries"]
        ],
        "know_how": [],
    }

    for item in selected["data_lake"]:
        if isinstance(item, dict):
            result["data_lake"].append(item["name"])
        elif isinstance(item, str) and ": " in item:
            result["data_lake"].append(item.split(": ")[0])
        else:
            result["data_lake"].append(str(item))

    if "know_how" in selected and selected["know_how"]:
        for item in selected["know_how"]:
            if isinstance(item, dict):
                doc_id = item["id"]
                doc = agent.know_how_loader.get_document_by_id(doc_id)
                if doc:
                    result["know_how"].append({
                        "id": doc["id"],
                        "name": doc["name"],
                        "description": doc["description"],
                        "content": doc["content_without_metadata"],
                        "metadata": doc["metadata"],
                    })

    return result


def _print_retrieval_summary(resources: dict) -> None:
    """Log a human-readable retrieval summary."""
    logger.info("Resource retrieval complete — "
                 "tools=%d, data=%d, libs=%d, know_how=%d",
                 len(resources.get("tools", [])),
                 len(resources.get("data_lake", [])),
                 len(resources.get("libraries", [])),
                 len(resources.get("know_how", [])),
                 )


def _build_tool_desc_from_selection(agent: "A1", tools: list) -> dict:
    """Build a ``{module: [tool_schema, ...]}`` dict from selected tools."""
    tool_desc: dict[str, list] = {}
    for tool in tools:
        if isinstance(tool, dict):
            module_name = tool.get("module") or _find_module_for_tool(agent, tool.get("name"))
            if not module_name:
                module_name = "biochat.tool.scRNA_tools"
                tool["module"] = module_name
            tool_desc.setdefault(module_name, []).append(tool)
        else:
            module_name = getattr(tool, "module_name", None) or _find_module_for_tool(
                agent, getattr(tool, "name", str(tool))
            )
            if not module_name:
                module_name = "biochat.tool.scRNA_tools"
                tool.module_name = module_name
            tool_dict = {
                "name": getattr(tool, "name", str(tool)),
                "description": getattr(tool, "description", ""),
                "parameters": getattr(tool, "parameters", {}),
                "module": module_name,
            }
            tool_desc.setdefault(module_name, []).append(tool_dict)
    return tool_desc


def _find_module_for_tool(agent: "A1", tool_name: str | None) -> str | None:
    """Search ``module2api`` for the module containing *tool_name*."""
    if not tool_name or not hasattr(agent, "module2api"):
        return None
    for mod, apis in agent.module2api.items():
        for api in apis:
            if api.get("name") == tool_name:
                return mod
    return None


def _build_data_lake_desc_from_selection(agent: "A1", items: list) -> list[dict]:
    return [
        {"name": item, "description": agent.data_lake_dict.get(item, f"Data lake item: {item}")}
        for item in items
    ]


def _get_custom_items(agent: "A1", attr: str) -> list[dict] | None:
    """Safely extract custom items from agent attributes."""
    if not hasattr(agent, attr):
        return None
    storage = getattr(agent, attr)
    if not storage:
        return None

    result: list[dict] = []
    for name, info in storage.items():
        if isinstance(info, dict):
            result.append({"name": name, "description": info.get("description", ""),
                            "module": info.get("module", "custom_tools")})
        else:
            result.append({"name": name, "description": str(info)})
    return result or None
