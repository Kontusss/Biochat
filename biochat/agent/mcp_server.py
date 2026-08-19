"""
MCP server creation — extracted from ``A1.create_mcp_server()`` and
``A1._generate_mcp_wrapper_from_biochat_schema()``.

Exposes internal Biochat tools as an MCP (Model Context Protocol) server
for external client integration.
"""

from __future__ import annotations

import importlib
import inspect
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from biochat.agent.a1 import A1


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════

def build_biochat_mcp_server(agent: "A1", tool_modules: list[str] | None = None) -> Any:
    """Create and return a FastMCP server exposing Biochat internal tools.

    Args:
        agent: The initialised A1 agent instance.
        tool_modules: Optional list of module names to expose.
                      Defaults to all modules in ``agent.module2api``.

    Returns:
        A ``FastMCP`` server object (call ``.run()`` to start).
    """
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("BiochatTools")
    modules = tool_modules or list(agent.module2api.keys())
    registered = 0

    for module_name in modules:
        try:
            module = importlib.import_module(module_name)
            module_tools = agent.module2api.get(module_name, [])

            for tool_schema in module_tools:
                tool_name = tool_schema.get("name")
                if not tool_name:
                    continue

                try:
                    fn = getattr(module, tool_name, None)
                    if fn is None:
                        fn = getattr(agent, "_custom_functions", {}).get(tool_name)
                    if fn is None:
                        continue

                    required = tool_schema.get("required_parameters", [])
                    optional = tool_schema.get("optional_parameters", [])
                    wrapper = _create_schema_aware_wrapper(fn, tool_name, required, optional)

                    mcp.tool()(wrapper)
                    registered += 1
                except Exception as e:
                    print(f"Warning: Failed to register tool '{tool_name}': {e}")
        except ImportError as e:
            print(f"Warning: Could not import module '{module_name}': {e}")

    print(f"Created MCP server with {registered} tools")
    return mcp


# ═══════════════════════════════════════════════════════════════
# Schema-aware wrapper generator
# ═══════════════════════════════════════════════════════════════

_TYPE_MAP: dict[str, type] = {
    "str": str, "int": int, "float": float, "bool": bool,
    "List[str]": list[str], "dict": dict,
}


def _create_schema_aware_wrapper(
    original_func: callable,
    func_name: str,
    required_params: list[dict],
    optional_params: list[dict],
) -> callable:
    """Generate a function wrapper with a signature matching Biochat schema.

    Returns a wrapper that:
    - Accepts ``**kwargs`` matching the declared parameters.
    - Filters out None values for optional params.
    - Calls *original_func* and wraps the result in ``{"result": ...}``.
    """
    all_params = required_params + optional_params

    if not all_params:
        def _no_param_wrapper() -> dict:
            try:
                result = original_func()
                return result if isinstance(result, dict) else {"result": result}
            except Exception as exc:
                return {"error": str(exc)}

        _no_param_wrapper.__name__ = func_name
        _no_param_wrapper.__doc__ = original_func.__doc__
        return _no_param_wrapper

    def _wrapper(**kwargs: Any) -> dict:
        try:
            filtered: dict[str, Any] = {}

            for param_info in required_params:
                pname = param_info["name"]
                if pname in kwargs and kwargs[pname] is not None:
                    filtered[pname] = kwargs[pname]

            for param_info in optional_params:
                pname = param_info["name"]
                if pname in kwargs and kwargs[pname] is not None:
                    filtered[pname] = kwargs[pname]

            result = original_func(**filtered)
            return result if isinstance(result, dict) else {"result": result}
        except Exception as exc:
            return {"error": str(exc)}

    _wrapper.__name__ = func_name
    _wrapper.__doc__ = original_func.__doc__

    # Build proper inspect.Signature
    new_params: list[inspect.Parameter] = []
    for param_info in required_params:
        pname = param_info["name"]
        ptype = _TYPE_MAP.get(param_info.get("type", "str"), str)
        new_params.append(inspect.Parameter(pname, inspect.Parameter.KEYWORD_ONLY, annotation=ptype))

    for param_info in optional_params:
        pname = param_info["name"]
        ptype = _TYPE_MAP.get(param_info.get("type", "str"), str)
        new_params.append(inspect.Parameter(
            pname, inspect.Parameter.KEYWORD_ONLY, default=None, annotation=ptype | None
        ))

    _wrapper.__signature__ = inspect.Signature(new_params, return_annotation=dict)
    return _wrapper
