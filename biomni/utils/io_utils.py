"""File I/O, serialization, and module-loading utilities.

Replaces the scattered I/O functions from the original ``utils.py``:
``save_pkl``, ``load_pkl``, ``load_pickle``, ``check_or_create_path``,
``textify_api_dict``, ``read_module2api``.
"""

from __future__ import annotations

import importlib
import os
import pickle as _pickle
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Serialization
# ═══════════════════════════════════════════════════════════════

def load_pickle(filepath: str) -> Any:
    """Deserialise a Python object from a pickled file.

    Args:
        filepath: Path to the ``.pkl`` file.

    Returns:
        The deserialised Python object.

    Raises:
        FileNotFoundError: If *filepath* does not exist.
        pickle.UnpicklingError: If the file is corrupt.
    """
    with open(filepath, "rb") as fh:
        return _pickle.load(fh)


def save_pickle(obj: Any, filepath: str) -> None:
    """Serialise *obj* to a pickled file."""
    with open(filepath, "wb") as fh:
        _pickle.dump(obj, fh)


# ── Backward-compatible aliases (original utils.py had two names
#    for the same function — consolidated here as a single source
#    of truth with aliases).
load_pkl = load_pickle
save_pkl = save_pickle


# ═══════════════════════════════════════════════════════════════
# Path utilities
# ═══════════════════════════════════════════════════════════════

def ensure_directory_exists(path: str | None = None) -> str:
    """Create a directory if it doesn't exist.

    Args:
        path: Directory path.  Defaults to ``./tmp_directory``.

    Returns:
        The absolute path to the existing directory.
    """
    if path is None:
        path = os.path.join(os.getcwd(), "tmp_directory")
    os.makedirs(path, exist_ok=True)
    return os.path.abspath(path)


# ═══════════════════════════════════════════════════════════════
# Tool description formatting
# ═══════════════════════════════════════════════════════════════

def format_api_dict_as_text(api_dict: dict) -> str:
    """Convert a nested ``{category: [method_schema, ...]}`` dict into
    a human-readable multi-line string for inclusion in system prompts.
    """
    lines: list[str] = []
    for category, methods in api_dict.items():
        lines.append(f"Import file: {category}")
        lines.append("=" * (len("Import file: ") + len(category)))
        for method in methods:
            lines.append(f"Method: {method.get('name', 'N/A')}")
            lines.append(
                f"  Description: {method.get('description', 'No description provided.')}"
            )
            for label, key in [("Required Parameters", "required_parameters"),
                               ("Optional Parameters", "optional_parameters")]:
                params = method.get(key, [])
                if params:
                    lines.append(f"  {label}:")
                    for param in params:
                        pn = param.get("name", "N/A")
                        pt = param.get("type", "N/A")
                        pd = param.get("description", "No description")
                        pdef = param.get("default", "None")
                        lines.append(f"    - {pn} ({pt}): {pd} [Default: {pdef}]")
            lines.append("")
        lines.append("")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Tool module loader
# ═══════════════════════════════════════════════════════════════

_TOOL_FIELDS: tuple[str, ...] = (
    "literature", "biochemistry", "bioimaging", "bioengineering",
    "biophysics", "glycoengineering", "cancer_biology", "cell_biology",
    "molecular_biology", "genetics", "genomics", "immunology",
    "microbiology", "pathology", "pharmacology", "physiology",
    "synthetic_biology", "systems_biology", "support_tools",
    "database", "lab_automation", "protocols",
)


def load_all_tool_descriptions() -> dict:
    """Import all ``biomni.tool.tool_description.*`` modules and
    return a ``{module_name: description_list}`` mapping.

    Replaces the original ``read_module2api()`` with a slightly
    more defensive implementation.
    """
    module2api: dict[str, list] = {}
    for field in _TOOL_FIELDS:
        module_name = f"biomni.tool.tool_description.{field}"
        try:
            mod = importlib.import_module(module_name)
            module2api[f"biomni.tool.{field}"] = mod.description
        except ImportError:
            continue  # gracefully skip missing tool modules
    return module2api


# ── Backward-compatible aliases ─────────────────────────────────
check_or_create_path = ensure_directory_exists
textify_api_dict = format_api_dict_as_text
read_module2api = load_all_tool_descriptions
