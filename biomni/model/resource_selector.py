"""Resource selector — original Biochat implementation.

Prompt-based relevance selection over the agent's available resources
(tools / data-lake / libraries / know-how).  Replaces the upstream
``biomni/model/retriever.py`` with separated, testable pieces:

- :func:`build_selection_prompt` — constructs the selection prompt;
- :func:`parse_selection_response` — extracts category indices from the
  LLM reply (plain string or Responses-API content blocks);
- :class:`ResourceSelector` — orchestrates the two around one LLM call.

The legacy path ``biomni.model.retriever`` remains as a thin adapter.
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import HumanMessage

_CATEGORIES = ("tools", "data_lake", "libraries", "know_how")
_CATEGORY_LABELS = {
    "tools": ("AVAILABLE TOOLS", "TOOLS"),
    "data_lake": ("AVAILABLE DATA LAKE ITEMS", "DATA_LAKE"),
    "libraries": ("AVAILABLE SOFTWARE LIBRARIES", "LIBRARIES"),
    "know_how": ("AVAILABLE KNOW-HOW DOCUMENTS (Best Practices & Protocols)",
                 "KNOW_HOW"),
}

_INDEX_RE = {
    "tools": re.compile(r"TOOLS:\s*\[(.*?)\]", re.IGNORECASE),
    "data_lake": re.compile(r"DATA_LAKE:\s*\[(.*?)\]", re.IGNORECASE),
    "libraries": re.compile(r"LIBRARIES:\s*\[(.*?)\]", re.IGNORECASE),
    "know_how": re.compile(r"KNOW[-_]HOW:\s*\[(.*?)\]", re.IGNORECASE),
}


def _describe_resource(index: int, resource: Any) -> str:
    """'i. name: description' line for one resource (dict / str / object)."""
    if isinstance(resource, dict):
        name = resource.get("name", f"Resource {index}")
        description = resource.get("description", "")
    elif isinstance(resource, str):
        return f"{index}. {resource}"
    else:
        name = getattr(resource, "name", str(resource))
        description = getattr(resource, "description", "")
    return f"{index}. {name}: {description}"


def format_resources(resources: Any) -> str:
    """Format one category's resources as numbered prompt lines."""
    lines = [_describe_resource(i, r) for i, r in enumerate(resources)]
    return "\n".join(lines) if lines else "None available"


def build_selection_prompt(query: str, resources: dict) -> str:
    """Build the relevance-selection prompt for one query.

    The model answers with index lists per category, e.g.::

        TOOLS: [0, 3, 5]
        DATA_LAKE: [1, 2]
        LIBRARIES: [0, 2, 4]
        KNOW_HOW: [0, 1]        # only when know_how is offered
    """
    has_know_how = bool(resources.get("know_how"))

    sections = [
        (
            "You are an expert biomedical research assistant. Your task is "
            "to select the relevant resources to help answer a user's query."
            f"\n\nUSER QUERY: {query}"
            "\n\nBelow are the available resources. For each category, select "
            "items that are directly or indirectly relevant to answering the "
            "query. Be generous in your selection - include resources that "
            "might be useful for the task, even if they're not explicitly "
            "mentioned in the query. It's better to include slightly more "
            "resources than to miss potentially useful ones."
        ),
        f"{_CATEGORY_LABELS['tools'][0]}:\n{format_resources(resources.get('tools', []))}",
        f"{_CATEGORY_LABELS['data_lake'][0]}:\n{format_resources(resources.get('data_lake', []))}",
        f"{_CATEGORY_LABELS['libraries'][0]}:\n{format_resources(resources.get('libraries', []))}",
    ]
    if has_know_how:
        sections.append(
            f"{_CATEGORY_LABELS['know_how'][0]}:\n{format_resources(resources['know_how'])}"
        )

    response_format = [
        "For each category, respond with ONLY the indices of the relevant "
        "items in the following format:",
        "TOOLS: [list of indices]",
        "DATA_LAKE: [list of indices]",
        "LIBRARIES: [list of indices]",
    ]
    if has_know_how:
        response_format.append("KNOW_HOW: [list of indices]")
    response_format += [
        "",
        "For example:",
        "TOOLS: [0, 3, 5, 7, 9]",
        "DATA_LAKE: [1, 2, 4]",
        "LIBRARIES: [0, 2, 4, 5, 8]",
    ]
    if has_know_how:
        response_format.append("KNOW_HOW: [0, 1]")
    response_format += [
        "",
        "If a category has no relevant items, use an empty list, e.g., "
        "DATA_LAKE: []",
        "",
        "IMPORTANT GUIDELINES:",
        "1. Be generous but not excessive - aim to include all potentially "
        "relevant resources",
        "2. ALWAYS prioritize database tools for general queries - include as "
        "many database tools as possible",
        "3. Include all literature search tools",
        "4. For wet lab sequence type of queries, ALWAYS include molecular "
        "biology tools",
        "5. For data lake items, include datasets that could provide useful "
        "information",
        "6. For libraries, include those that provide functions needed for "
        "analysis",
        "7. For know-how documents, include those that provide relevant "
        "protocols, best practices, or troubleshooting guidance",
        "8. Don't exclude resources just because they're not explicitly "
        "mentioned in the query",
        "9. When in doubt about a database tool or molecular biology tool, "
        "include it rather than exclude it",
    ]

    return "\n".join(sections) + "\n\n" + "\n".join(response_format)


def parse_selection_response(response: Any) -> dict[str, list[int]]:
    """Extract ``{category: [indices]}`` from an LLM reply.

    Accepts a plain string or a Responses-API list of content blocks.
    Unparseable entries are skipped; unknown categories yield empty lists.
    """
    text = _normalise_response(response)
    selected: dict[str, list[int]] = {c: [] for c in _CATEGORIES}
    for category, pattern in _INDEX_RE.items():
        match = pattern.search(text)
        if not match or not match.group(1).strip():
            continue
        indices: list[int] = []
        for piece in match.group(1).split(","):
            piece = piece.strip()
            try:
                indices.append(int(piece))
            except ValueError:
                continue
        selected[category] = indices
    return selected


def _normalise_response(response: Any) -> str:
    """Coerce an LLM reply (str / content-block list / other) to text."""
    if isinstance(response, str):
        return response
    if isinstance(response, list):
        parts: list[str] = []
        for item in response:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(p for p in parts if p)
    return str(response)


class ResourceSelector:
    """Selects relevant resources for a query using one LLM call."""

    def prompt_based_retrieval(self, query: str, resources: dict, llm=None) -> dict:
        """Return ``resources`` filtered to the LLM-selected subsets.

        Args:
            query: The user's query.
            resources: Dict with keys ``tools`` / ``data_lake`` /
                ``libraries`` (required) and ``know_how`` (optional).
            llm: LangChain-style model with ``invoke`` (defaults to
                ``ChatOpenAI(model="gpt-4o")`` when omitted).

        Returns:
            The same keys, each mapped to the selected items only.
        """
        if llm is None:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model="gpt-4o")

        prompt = build_selection_prompt(query, resources)
        if hasattr(llm, "invoke"):
            response = llm.invoke([HumanMessage(content=prompt)])
            reply = response.content
        else:
            reply = llm(prompt)

        indices = parse_selection_response(reply)

        def take(category: str) -> list:
            pool = resources.get(category, [])
            return [pool[i] for i in indices.get(category, []) if i < len(pool)]

        selected = {
            "tools": take("tools"),
            "data_lake": take("data_lake"),
            "libraries": take("libraries"),
        }
        if "know_how" in resources and resources["know_how"]:
            selected["know_how"] = take("know_how")
        return selected
