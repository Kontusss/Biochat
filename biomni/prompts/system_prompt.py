"""System Prompt Builder for the Biomni / Biochat Agent.

Includes the Phase 3A antibody design addendum.
"""

from __future__ import annotations

from biomni.utils import textify_api_dict

_BASE_INSTRUCTION = """\
You are a helpful biomedical assistant assigned with the task of problem-solving.
To achieve this, you will be using an interactive coding environment equipped with a \
variety of tool functions, data, and softwares to assist you throughout the process.

CRITICAL LANGUAGE REQUIREMENT:
You MUST respond in Chinese (简体中文). All your thinking, planning, code comments, \
and final answers must be written in Chinese. Only code syntax, variable names, \
function names, and technical terms (like gene names, protein names, database names) \
should remain in English. Your <solution> final answer must be entirely in Chinese.

Given a task, make a plan first. The plan should be a numbered list of steps that you \
will take to solve the task. Be specific and detailed.
Format your plan as a checklist with empty checkboxes like this:
1. [ ] First step
2. [ ] Second step

Follow the plan step by step. After completing each step, update the checklist by \
replacing the empty checkbox with a checkmark:
1. [✓] First step (completed)
2. [ ] Second step

At each turn, you should first provide your thinking and reasoning given the \
conversation history. After that, you have two options:

1) Interact with a programming environment using <execute> tag.
2) Provide a solution using <solution> tag.

IMPORTANT — WHEN TO USE EACH TAG:
- For simple factual Q&A: use <solution> directly WITHOUT going through <execute>.
- For computation / database queries: first use <execute>, then <solution>.
- NEVER append </execute> or </solution> as closing tags without opening tags.
- NEVER apologize for using the wrong format — just use the correct format.
"""

_ANTIBODY_DESIGN_ADDENDUM = """\
ANTIBODY DESIGN REQUIREMENTS:
When the user requests antibody/CDR/nanobody/VH-only design:
1. DO NOT invent CDRH3 sequences from your training data.
2. Use design_vh_only_antibodies(epitope_sequence=..., num_candidates=...)
   from biomni.tool.antibody_design.
3. NEVER fabricate GRAVY, pI, docking scores, or binding affinity values.
4. Always include the safety disclaimer from the tool output.
5. If the tool is unavailable, clearly state limitations.
6. NEVER call any computed score "binding affinity", "ΔG", "Kd", or "ddG".
7. When reporting results, ALWAYS include score provenance.
"""

_OUTPUT_FORMAT_ADDENDUM = """\
OUTPUT FORMAT REQUIREMENTS (回复格式要求):
1. Start with a clear **结论 (Conclusion)** section.
2. Follow with **依据与原理 (Evidence & Rationale)**.
3. Include **分析步骤 (Analysis Steps)**.
4. Add **不确定性与注意事项 (Uncertainties & Caveats)**.
5. Include **安全声明 (Safety Disclaimer)** when applicable.
"""

_PROTOCOL_ADDENDUM = """\
PROTOCOL GENERATION:
If the user requests an experimental protocol, use search_protocols(), \
advanced_web_search_claude(), list_local_protocols(), and read_local_protocol() \
to generate an accurate protocol.
"""

_CUSTOM_RESOURCES_HEADER = """\
PRIORITY CUSTOM RESOURCES
===============================
IMPORTANT: The following custom resources have been specifically added for your use.
    PRIORITIZE using these resources as they are directly relevant to your task.
"""

_ENV_RESOURCES_TEMPLATE = """\
Environment Resources:

- Function Dictionary:
{function_intro}
---
{tool_desc}
---

{import_instruction}

- Biological data lake at: {data_lake_path}.
{data_lake_intro}
----
{data_lake_content}
----

- Software Library:
{library_intro}
----
{library_content_formatted}
----
"""


class SystemPromptBuilder:
    """Assemble the agent's system prompt from configuration and resources."""

    def __init__(
        self, *, tool_desc, data_lake_content, library_content_list,
        data_lake_path, data_lake_dict, library_content_dict,
        self_critic=False, custom_tools=None, custom_data=None,
        custom_software=None, know_how_docs=None,
    ):
        self.tool_desc = tool_desc
        self.data_lake_content = data_lake_content
        self.library_content_list = library_content_list
        self.data_lake_path = data_lake_path
        self.data_lake_dict = data_lake_dict
        self.library_content_dict = library_content_dict
        self.self_critic = self_critic
        self.custom_tools = custom_tools or []
        self.custom_data = custom_data or []
        self.custom_software = custom_software or []
        self.know_how_docs = know_how_docs or []

    def build(self, is_retrieval: bool = False) -> str:
        parts: list[str] = [_BASE_INSTRUCTION, _ANTIBODY_DESIGN_ADDENDUM,
                             _OUTPUT_FORMAT_ADDENDUM, _PROTOCOL_ADDENDUM]
        custom = self._render_custom_resources()
        if custom:
            parts.append(custom)
        parts.append(self._render_env_resources(is_retrieval))
        return "\n\n".join(parts)

    def _render_custom_resources(self) -> str | None:
        has_any = any([self.know_how_docs, self.custom_tools,
                       self.custom_data, self.custom_software])
        if not has_any:
            return None
        blocks = [_CUSTOM_RESOURCES_HEADER]
        if self.know_how_docs:
            blocks.append(self._format_know_how())
        if self.custom_tools:
            blocks.append(self._format_custom_tools())
        if self.custom_data:
            blocks.append(self._format_custom_data())
        if self.custom_software:
            blocks.append(self._format_custom_software())
        blocks.append("=" * 31)
        return "\n".join(blocks)

    def _render_env_resources(self, is_retrieval: bool) -> str:
        if is_retrieval:
            function_intro = "Based on your query, the most relevant functions:"
            data_lake_intro = "Most relevant datasets:"
            library_intro = "Most relevant libraries:"
            import_instruction = "IMPORTANT: import from its module. Example: from [module_name] import [function_name]"
        else:
            function_intro = "Available functions (import from their module):"
            data_lake_intro = "Available datasets:"
            library_intro = "Available libraries:"
            import_instruction = ""

        data_lake_fmt = self._format_data_lake()
        lib_fmt = self._format_libraries()
        tool_text = textify_api_dict(self.tool_desc) if isinstance(self.tool_desc, dict) else str(self.tool_desc)

        return _ENV_RESOURCES_TEMPLATE.format(
            function_intro=function_intro, tool_desc=tool_text,
            import_instruction=import_instruction,
            data_lake_path=self.data_lake_path, data_lake_intro=data_lake_intro,
            data_lake_content=data_lake_fmt, library_intro=library_intro,
            library_content_formatted=lib_fmt,
        )

    def _format_data_lake(self) -> str:
        lines = []
        for item in self.data_lake_content:
            if isinstance(item, dict):
                name, desc = item.get("name", ""), item.get("description", "")
            else:
                name, desc = str(item), self.data_lake_dict.get(str(item), "")
            lines.append(f"{name}: {desc}" if desc else name)
        return "\n".join(lines) if lines else "(none)"

    def _format_libraries(self) -> str:
        lines = []
        for lib in self.library_content_list:
            if isinstance(lib, dict):
                name, desc = lib.get("name", ""), lib.get("description", "")
            else:
                name, desc = str(lib), self.library_content_dict.get(str(lib), "")
            lines.append(f"{name}: {desc}" if desc else name)
        return "\n".join(lines) if lines else "(none)"

    def _format_know_how(self) -> str:
        docs = []
        for doc in self.know_how_docs:
            if isinstance(doc, dict):
                docs.append(f"📚 {doc.get('name', 'Unknown')}:\n{doc.get('content', '')}")
        return "\n\n".join(docs)

    def _format_custom_tools(self) -> str:
        items = [f"🔧 {t.get('name', '?')} ({t.get('module', '?')}): {t.get('description', '')}"
                 if isinstance(t, dict) else f"🔧 {t}" for t in self.custom_tools]
        return "🔧 CUSTOM TOOLS:\n" + "\n".join(items)

    def _format_custom_data(self) -> str:
        items = [f"📊 {d.get('name', '?')}: {d.get('description', '')}"
                 if isinstance(d, dict) else f"📊 {d}" for d in self.custom_data]
        return "📊 CUSTOM DATA:\n" + "\n".join(items)

    def _format_custom_software(self) -> str:
        items = [f"⚙️ {s.get('name', '?')}: {s.get('description', '')}"
                 if isinstance(s, dict) else f"⚙️ {s}" for s in self.custom_software]
        return "⚙️ CUSTOM SOFTWARE:\n" + "\n".join(items)
