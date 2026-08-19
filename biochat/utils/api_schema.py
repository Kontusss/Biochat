"""
API schema generation and LangChain tool conversion.

Replaces ``function_to_api_schema``, ``get_all_functions_from_file``,
``get_tool_decorated_functions``, ``api_schema_to_langchain_tool``,
``CustomBaseModel``, ``api_schema(BaseModel)``, and
``safe_execute_decorator`` from the original ``utils.py``.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import os
from typing import Any, ClassVar

import pandas as pd
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, ValidationError


# ═══════════════════════════════════════════════════════════════
# Schema models
# ═══════════════════════════════════════════════════════════════

class ApiSchema(BaseModel):
    """API schema specification."""
    api_schema: str | None = Field(description="The API schema as a dictionary")


class EnhancedBaseModel(BaseModel):
    """BaseModel with enhanced validation error messages.

    Replaces ``CustomBaseModel`` from the original code.
    """

    api_schema: ClassVar[dict | None] = None
    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def set_api_schema(cls, schema: dict) -> None:
        cls.api_schema = schema

    @classmethod
    def model_validate(cls, obj: Any) -> Any:
        try:
            return super().model_validate(obj)
        except (ValidationError, AttributeError) as exc:
            if not cls.api_schema:
                raise

            error_msg_parts = ["Required Parameters:"]
            for param in cls.api_schema.get("required_parameters", []):
                error_msg_parts.append(
                    f"- {param['name']} ({param['type']}): {param['description']}"
                )
            error_msg_parts.append("\nErrors:")
            for err in getattr(exc, "errors", lambda: [])():
                field = err.get("loc", ["input"])[0] if err.get("loc") else "input"
                error_msg_parts.append(f"- {field}: {err.get('msg', '')}")

            raise ValidationError.from_exception_data(
                title="Validation Error",
                line_errors=[{
                    "type": "value_error",
                    "loc": ("input",),
                    "input": obj,
                    "ctx": {"error": "\n".join(error_msg_parts)},
                }],
            ) from None


# ═══════════════════════════════════════════════════════════════
# Schema generation
# ═══════════════════════════════════════════════════════════════

_SCHEMA_PROMPT = """\
Based on a code snippet and help me write an API docstring in the format like this:

{{'name': 'get_gene_set_enrichment',
'description': 'Given a list of genes, identify a pathway that is enriched for this gene set.',
'required_parameters': [{{'name': 'genes', 'type': 'List[str]',
'description': 'List of gene symbols', 'default': None}}],
'optional_parameters': [{{'name': 'top_k', 'type': 'int',
'description': 'Top K pathways to return', 'default': 10}}]}}

Strictly follow the input from the function — don't create fake optional parameters.
For variable without default values, set them as None, not null.
For variable with boolean values, use capitalized True or False, not true or false.
Do not add any return type in the docstring.
Be as clear and succinct as possible for the descriptions.
Here is the code snippet:
{code}"""


def generate_api_schema_from_code(function_string: str, llm: Any) -> dict | str:
    """Use an LLM to generate an API schema dict from a function's source code.

    Retries up to 7 times on parse failures.
    """
    structured_llm = llm.with_structured_output(ApiSchema)
    prompt = _SCHEMA_PROMPT.format(code=function_string)

    for _ in range(7):
        try:
            result = structured_llm.invoke(prompt).dict()
            return ast.literal_eval(result["api_schema"])
        except Exception:
            continue

    return "Error: Could not parse the API schema"


# ═══════════════════════════════════════════════════════════════
# AST extraction
# ═══════════════════════════════════════════════════════════════

def extract_top_level_functions(file_path: str) -> list[str]:
    """Extract source code of all public top-level functions from a Python file."""
    with open(file_path) as fh:
        source = fh.read()

    tree = ast.parse(source)
    functions: list[str] = []
    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and not node.name.startswith("_")
            and hasattr(node, "end_lineno")
        ):
            func_lines = source.splitlines()[node.lineno - 1 : node.end_lineno]
            functions.append("\n".join(func_lines))
    return functions


def extract_tool_decorated_functions(relative_path: str) -> list:
    """Find all @tool-decorated functions in a module and return them."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, relative_path)

    with open(file_path) as fh:
        tree = ast.parse(fh.read(), filename=file_path)

    tool_names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            is_tool = False
            if isinstance(decorator, ast.Name) and decorator.id == "tool":
                is_tool = True
            elif (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Name)
                and decorator.func.id == "tool"
            ):
                is_tool = True
            if is_tool:
                tool_names.append(node.name)
                break

    # Resolve module name and import
    rel = os.path.relpath(file_path, start=current_dir)
    module_name = rel.replace(os.path.sep, ".").rsplit(".", 1)[0]
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return [getattr(mod, name) for name in tool_names]
    return []


# ═══════════════════════════════════════════════════════════════
# LangChain tool conversion
# ═══════════════════════════════════════════════════════════════

_TYPE_MAP: dict[str, type] = {
    "string": str, "integer": int, "boolean": bool,
    "str": str, "int": int, "bool": bool,
    "pandas": pd.DataFrame,
    "List[str]": list[str], "List[int]": list[int],
    "Dict": dict, "Any": Any,
}


def wrap_with_safe_execution(func: Any) -> Any:
    """Decorator: catch exceptions and return their string representation."""
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            return str(exc)

    wrapper.__name__ = getattr(func, "__name__", "wrapped")
    wrapper.__doc__ = getattr(func, "__doc__", "")
    return wrapper


def convert_schema_to_langchain_tool(
    api_schema: dict,
    mode: str = "generated_tool",
    module_name: str | None = None,
) -> StructuredTool:
    """Convert a Biochat API schema dict into a LangChain ``StructuredTool``."""
    # Import the wrapped function
    if mode == "generated_tool":
        module = importlib.import_module(
            f"biochat.tool.generated_tool.{api_schema['tool_name']}.api"
        )
    elif mode == "custom_tool":
        assert module_name is not None
        module = importlib.import_module(module_name)
    else:
        raise ValueError(f"Unknown mode: {mode}")

    api_function = wrap_with_safe_execution(getattr(module, api_schema["name"]))

    # Build annotations and fields
    annotations: dict[str, type] = {}
    fields: dict[str, Any] = {}
    for param in api_schema["required_parameters"]:
        annotations[param["name"]] = _TYPE_MAP.get(param["type"], Any)
        fields[param["name"]] = Field(description=param["description"])

    InputModel = type(
        "Input",
        (EnhancedBaseModel,),
        {"__annotations__": annotations, **fields},
    )
    InputModel.set_api_schema(api_schema)

    return StructuredTool.from_function(
        func=api_function,
        name=api_schema["name"],
        description=api_schema["description"],
        args_schema=InputModel,
        return_direct=True,
    )


# ── Backward-compatible aliases ─────────────────────────────────
api_schema = ApiSchema
CustomBaseModel = EnhancedBaseModel
function_to_api_schema = generate_api_schema_from_code
get_all_functions_from_file = extract_top_level_functions
get_tool_decorated_functions = extract_tool_decorated_functions
safe_execute_decorator = wrap_with_safe_execution
api_schema_to_langchain_tool = convert_schema_to_langchain_tool
