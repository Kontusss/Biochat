"""Tool registry — original Biochat implementation.

Indexed registry over the tool-description schemas produced by
``load_all_tool_descriptions``.  Replaces the upstream
``biochat/tool/tool_registry.py`` (linear list scans + eager DataFrame)
with name/id index maps and a lazily-built document frame.

The legacy path ``biochat.tool.tool_registry`` remains as a thin adapter.
"""

from __future__ import annotations

import pickle

import pandas as pd

_REQUIRED_KEYS = ("name", "description", "required_parameters")


class ToolRegistry:
    """Ordered, indexed registry of tool schemas.

    Tool schemas are dicts carrying at least ``name``, ``description`` and
    ``required_parameters`` (the ``load_all_tool_descriptions`` shape).
    Each registered tool receives a stable integer ``id``.

    Args:
        tools: ``{module_key: [tool_schema, ...]}`` mapping.
        profile: ``"full"`` registers every module; ``"minimal"`` only the
                 modules listed in ``biochat/tool/profiles.py``.
    """

    def __init__(self, tools: dict[str, list[dict]] | None = None,
                 profile: str = "full"):
        self.profile = profile if profile in ("minimal", "full") else "full"
        self._tools: list[dict] = []
        self._by_name: dict[str, dict] = {}
        self._by_id: dict[int, dict] = {}
        self._next_id = 0
        self._document_df: pd.DataFrame | None = None
        for module_key, group in (tools or {}).items():
            if not self._module_allowed(module_key):
                continue
            for schema in group:
                self.register_tool(schema)

    def _module_allowed(self, module_key: str) -> bool:
        if self.profile == "full":
            return True
        from biochat.tool.profiles import MINIMAL_TOOL_MODULES
        return module_key in MINIMAL_TOOL_MODULES

    # ── Registration ──────────────────────────────────────────────

    @staticmethod
    def validate_tool(tool: dict) -> bool:
        return all(key in tool for key in _REQUIRED_KEYS)

    def register_tool(self, tool: dict) -> None:
        if not self.validate_tool(tool):
            raise ValueError(
                f"Invalid tool format — required keys: {_REQUIRED_KEYS}"
            )
        if tool["name"] in self._by_name:
            raise ValueError(f"Tool already registered: {tool['name']}")
        entry = dict(tool)
        entry["id"] = self._next_id
        self._next_id += 1
        self._tools.append(entry)
        self._by_name[entry["name"]] = entry
        self._by_id[entry["id"]] = entry
        self._document_df = None  # invalidate cached frame

    # ── Views ─────────────────────────────────────────────────────

    @property
    def tools(self) -> list[dict]:
        """Registered tools in registration order (each carries ``id``)."""
        return list(self._tools)

    @property
    def document_df(self) -> pd.DataFrame:
        """Document frame used by retrieval (built lazily, cached)."""
        if self._document_df is None:
            docs = [{"docid": t["id"], "document_content": t} for t in self._tools]
            self._document_df = pd.DataFrame(
                docs, columns=["docid", "document_content"]
            )
        return self._document_df

    @document_df.setter
    def document_df(self, value: pd.DataFrame) -> None:
        """Allow callers to replace the frame (upstream compat)."""
        self._document_df = value

    # ── Lookups ───────────────────────────────────────────────────

    def get_tool_by_name(self, name: str) -> dict | None:
        return self._by_name.get(name)

    def get_tool_by_id(self, tool_id: int) -> dict | None:
        return self._by_id.get(int(tool_id))

    def get_id_by_name(self, name: str) -> int | None:
        entry = self._by_name.get(name)
        return entry["id"] if entry else None

    def get_name_by_id(self, tool_id: int) -> str | None:
        entry = self._by_id.get(int(tool_id))
        return entry["name"] if entry else None

    def list_tools(self) -> list[dict]:
        return [{"name": t["name"], "id": t["id"]} for t in self._tools]

    # ── Removal ───────────────────────────────────────────────────

    def remove_tool_by_id(self, tool_id: int) -> bool:
        entry = self._by_id.pop(int(tool_id), None)
        if entry is None:
            return False
        self._tools = [t for t in self._tools if t["id"] != int(tool_id)]
        self._by_name.pop(entry["name"], None)
        self._document_df = None
        return True

    def remove_tool_by_name(self, name: str) -> bool:
        entry = self._by_name.pop(name, None)
        if entry is None:
            return False
        self._tools = [t for t in self._tools if t["name"] != name]
        self._by_id.pop(entry["id"], None)
        self._document_df = None
        return True

    # ── Persistence (upstream compat) ─────────────────────────────

    def save_registry(self, filename: str) -> None:
        with open(filename, "wb") as file:
            pickle.dump(self, file)

    @staticmethod
    def load_registry(filename: str) -> "ToolRegistry":
        with open(filename, "rb") as file:
            return pickle.load(file)
