"""Code-to-tool-call parser.

Replaces ``parse_tool_calls_from_code``, ``parse_tool_calls_with_modules``,
``find_best_module_match``, and ``inject_custom_functions_to_repl``
from the original ``utils.py`` (lines 1131-1313).
"""

from __future__ import annotations

import re

# ── Pre-compiled patterns ────────────────────────────────────────
_FROM_IMPORT_RE = re.compile(r"from\s+([\w.]+)\s+import\s+([\w,\s]+)")
_IMPORT_RE = re.compile(r"import\s+([\w.]+)")
_FUNC_CALL_RE = re.compile(r"(\w+)\s*\(")


def detect_tool_imports_with_modules(
    code: str,
    module2api: dict,
    custom_functions: dict | None = None,
) -> list[tuple[str, str]]:
    """Parse Python code for imported tool functions and their modules.

    Returns:
        Sorted list of ``(tool_name, module_name)`` tuples.
    """
    detected: set[tuple[str, str]] = set()

    # Build lookup: tool_name → [module_name, ...]
    all_tools: dict[str, list[str]] = {}
    for mod_name, mod_tools in module2api.items():
        for tool in mod_tools:
            if isinstance(tool, dict) and "name" in tool:
                tn = tool["name"]
                all_tools.setdefault(tn, []).append(mod_name)

    if custom_functions:
        for tn in custom_functions:
            all_tools.setdefault(tn, []).append("custom_tools")

    # ── from X import Y ────────────────────────────────────
    for module_name, tools_str in _FROM_IMPORT_RE.findall(code):
        for tool in (t.strip() for t in tools_str.split(",")):
            if tool in all_tools:
                best = _best_module_match(module_name, all_tools[tool])
                detected.add((tool, best))
            elif "." in tool:
                parts = tool.split(".")
                if len(parts) == 2 and parts[1] in all_tools:
                    best = _best_module_match(parts[0], all_tools[parts[1]])
                    detected.add((parts[1], best))

    # ── import X ───────────────────────────────────────────
    for module_name in _IMPORT_RE.findall(code):
        for tn, modules in all_tools.items():
            if any(module_name in m for m in modules):
                if re.search(rf"\b{tn}\s*\(", code):
                    best = _best_module_match(module_name, modules)
                    detected.add((tn, best))

    # ── Direct function calls ──────────────────────────────
    for func in set(_FUNC_CALL_RE.findall(code)):
        if func in all_tools:
            detected.add((func, all_tools[func][0]))

    return sorted(detected)


def detect_tool_imports(
    code: str,
    module2api: dict,
    custom_functions: dict | None = None,
) -> list[str]:
    """Like ``detect_tool_imports_with_modules`` but returns tool names only."""
    return sorted({pair[0] for pair in detect_tool_imports_with_modules(
        code, module2api, custom_functions
    )})


def _best_module_match(target: str, available: list[str]) -> str:
    """Find the closest module match from *available*."""
    if target in available:
        return target
    for m in available:
        if target in m or m in target:
            return m
    return available[0] if available else "unknown"


def register_custom_functions_in_namespace(custom_functions: dict) -> None:
    """Inject custom functions into Python REPL execution namespace."""
    if not custom_functions:
        return

    from biomni.tool.support_tools import _persistent_namespace
    for name, func in custom_functions.items():
        _persistent_namespace[name] = func

    import builtins
    if not hasattr(builtins, "_biomni_custom_functions"):
        builtins._biomni_custom_functions = {}
    builtins._biomni_custom_functions.update(custom_functions)


# ── Backward-compatible aliases ─────────────────────────────────
parse_tool_calls_with_modules = detect_tool_imports_with_modules
parse_tool_calls_from_code = detect_tool_imports
find_best_module_match = _best_module_match
inject_custom_functions_to_repl = register_custom_functions_in_namespace
