"""
System Prompt Builder for the Biomni / Biochat Agent.

Encapsulates the logic that was previously in
``A1._generate_system_prompt()`` (~400 lines) into a focused,
testable class.  The prompt instructs the LLM to act as a
biomedical research assistant with access to tools, data, and
code execution.

Usage::

    builder = SystemPromptBuilder(
        tool_desc=module2api,
        data_lake_content=data_lake_items,
        library_content_list=libraries,
        data_lake_path="/data/biomni_data/data_lake",
        data_lake_dict=env_desc.data_lake_dict,
        library_content_dict=env_desc.library_content_dict,
    )
    prompt = builder.build(is_retrieval=False)
"""

from __future__ import annotations

from biomni.utils import textify_api_dict


# ═══════════════════════════════════════════════════════════════════
# Constants — the core prompt structure
# ═══════════════════════════════════════════════════════════════════

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
3. [ ] Third step

Follow the plan step by step. After completing each step, update the checklist by \
replacing the empty checkbox with a checkmark:
1. [✓] First step (completed)
2. [ ] Second step
3. [ ] Third step

If a step fails or needs modification, mark it with an X and explain why:
1. [✓] First step (completed)
2. [✗] Second step (failed because...)
3. [ ] Modified second step
4. [ ] Third step

Always show the updated plan after each step so the user can track progress.

At each turn, you should first provide your thinking and reasoning given the \
conversation history.
After that, you have two options:

1) Interact with a programming environment and receive the corresponding output within \
<observe></observe>. Your code should be enclosed using "<execute>" tag, for example: \
<execute> print("Hello World!") </execute>. IMPORTANT: You must end the code block \
with </execute> tag.
   - For Python code (default): <execute> print("Hello World!") </execute>
   - For R code: <execute> #!R\\nlibrary(ggplot2)\\nprint("Hello from R") </execute>
   - For Bash scripts and commands: <execute> #!BASH\\necho "Hello from Bash"\\nls -la </execute>
   - For CLI softwares, use Bash scripts.

2) When you think it is ready, directly provide a solution that adheres to the required \
format for the given task to the user. Your solution should be enclosed using \
"<solution>" tag, for example: The answer is <solution> A </solution>. \
IMPORTANT: You must end the solution block with </solution> tag.

You have many chances to interact with the environment to receive the observation. \
So you can decompose your code into multiple steps.
Don't overcomplicate the code. Keep it simple and easy to understand.
When writing the code, please print out the steps and results in a clear and concise \
manner, like a research log.
When calling the existing python functions in the function dictionary, \
YOU MUST SAVE THE OUTPUT and PRINT OUT the result.
For example, result = understand_scRNA(XXX) print(result)
Otherwise the system will not be able to know what has been done.

For R code, use the #!R marker at the beginning of your code block to indicate \
it's R code.
For Bash scripts and commands, use the #!BASH marker at the beginning of your code block. \
This allows for both simple commands and multi-line scripts with variables, loops, \
conditionals, and other Bash features.

In each response, you must include EITHER <execute> or <solution> tag. \
Not both at the same time. Do not respond with messages without any tags. No empty \
messages.
"""

_SELF_CRITIC_ADDENDUM = """\
You may or may not receive feedbacks from human. If so, address the feedbacks by \
following the same procedure of multiple rounds of thinking, execution, and then \
coming up with a new solution.
"""

_PROTOCOL_ADDENDUM = """\
PROTOCOL GENERATION:
If the user requests an experimental protocol, use search_protocols(), \
advanced_web_search_claude(), list_local_protocols(), and read_local_protocol() to \
generate an accurate protocol. Include details such as reagents (with catalog numbers \
if available), equipment specifications, replicate requirements, error handling, and \
troubleshooting - but ONLY include information found in these resources. Do not make up \
specifications, catalog numbers, or equipment details. Prioritize accuracy over \
completeness.
"""

_OUTPUT_FORMAT_ADDENDUM = """\
OUTPUT FORMAT REQUIREMENTS (回复格式要求):
When providing your final answer, structure it as follows:
1. Start with a clear **结论 (Conclusion)** section summarizing your key findings
2. Follow with **依据与原理 (Evidence & Rationale)** supporting your conclusion
3. Include **分析步骤 (Analysis Steps)** detailing your methodology
4. Add **不确定性与注意事项 (Uncertainties & Caveats)** noting limitations
5. If your response involves clinical interpretation, drug recommendations, or \
experimental protocols, you MUST include a **安全声明 (Safety Disclaimer)**:
   "⚠️ **安全声明**: 本分析由 AI 代理生成，仅供研究参考。不得作为医疗建议、临床指导或专业判断的替代品。\
所有结果在实际应用前须经合格专家验证。"
"""

_CUSTOM_RESOURCES_HEADER = """\
PRIORITY CUSTOM RESOURCES
===============================
IMPORTANT: The following custom resources have been specifically added for your use.
    PRIORITIZE using these resources as they are directly relevant to your task.
    Always consider these FIRST before using default resources.

"""

_ENV_RESOURCES_TEMPLATE = """\
Environment Resources:

- Function Dictionary:
{function_intro}
---
{tool_desc}
---

{import_instruction}

- Biological data lake
You can access a biological data lake at the following path: {data_lake_path}.
{data_lake_intro}
Each item is listed with its description to help you understand its contents.
----
{data_lake_content}
----

- Software Library:
{library_intro}
Each library is listed with its description to help you understand its functionality.
----
{library_content_formatted}
----

- Note on using R packages and Bash scripts:
  - R packages: Use subprocess.run(['Rscript', '-e', 'your R code here']) in Python, \
or use the #!R marker in your execute block.
  - Bash scripts and commands: Use the #!BASH marker in your execute block for both \
simple commands and complex shell scripts with variables, loops, conditionals, etc.
"""


# ═══════════════════════════════════════════════════════════════════
# SystemPromptBuilder
# ═══════════════════════════════════════════════════════════════════

class SystemPromptBuilder:
    """Assemble the agent's system prompt from configuration and resources.

    This class replaces the ~400-line ``A1._generate_system_prompt()``
    method with a modular, testable implementation.  Call ``build()``
    to produce the final prompt string.

    All parameters are injected — the builder has no knowledge of the
    agent or its internals.
    """

    # ── Constructor ──────────────────────────────────────────────

    def __init__(
        self,
        *,
        tool_desc: dict,
        data_lake_content: list,
        library_content_list: list,
        data_lake_path: str,
        data_lake_dict: dict[str, str],
        library_content_dict: dict[str, str],
        self_critic: bool = False,
        custom_tools: list[dict] | None = None,
        custom_data: list[dict] | None = None,
        custom_software: list[dict] | None = None,
        know_how_docs: list[dict] | None = None,
    ):
        """Initialise the builder with all available resources.

        Args:
            tool_desc: Dict mapping module_name → [tool_schema, ...].
            data_lake_content: List of data lake items (strings or dicts).
            library_content_list: List of library names or dicts.
            data_lake_path: Absolute path to the data lake directory.
            data_lake_dict: Mapping of filename → description.
            library_content_dict: Mapping of library name → description.
            self_critic: Enable self-critic mode.
            custom_tools: Custom user-added tools.
            custom_data: Custom user-added data items.
            custom_software: Custom user-added software.
            know_how_docs: Know-how documents to include.
        """
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

    # ── Public API ───────────────────────────────────────────────

    def build(self, is_retrieval: bool = False) -> str:
        """Build the complete system prompt.

        Args:
            is_retrieval: If True, use "retrieval mode" text (narrower
                          tool/data/library listings).  If False, use
                          "initial configuration" text (full listings).

        Returns:
            The complete system prompt string, ready to pass to the LLM.
        """
        parts: list[str] = []

        # 1. Core instruction
        parts.append(_BASE_INSTRUCTION)

        # 2. Optional addenda
        if self.self_critic:
            parts.append(_SELF_CRITIC_ADDENDUM)
        parts.append(_PROTOCOL_ADDENDUM)
        parts.append(_OUTPUT_FORMAT_ADDENDUM)

        # 3. Custom resources (if any)
        custom_section = self._render_custom_resources()
        if custom_section:
            parts.append(custom_section)

        # 4. Environment resources (tools, data lake, software)
        parts.append(self._render_env_resources(is_retrieval))

        return "\n\n".join(parts)

    # ── Section renderers ────────────────────────────────────────

    def _render_custom_resources(self) -> str | None:
        """Render the PRIORITY CUSTOM RESOURCES section."""
        has_any = any([
            self.know_how_docs,
            self.custom_tools,
            self.custom_data,
            self.custom_software,
        ])
        if not has_any:
            return None

        blocks: list[str] = [_CUSTOM_RESOURCES_HEADER]

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
        """Render the Environment Resources section."""
        # Intro text varies by mode
        if is_retrieval:
            function_intro = (
                "Based on your query, I've identified the following most relevant "
                "functions that you can use in your code:"
            )
            data_lake_intro = (
                "Based on your query, I've identified the following most relevant datasets:"
            )
            library_intro = (
                "Based on your query, I've identified the following most relevant "
                "libraries that you can use:"
            )
            import_instruction = (
                "IMPORTANT: When using any function, you MUST first import it from "
                "its module. For example:\nfrom [module_name] import [function_name]"
            )
        else:
            function_intro = (
                "In your code, you will need to import the function location using "
                "the following dictionary of functions:"
            )
            data_lake_intro = (
                "You can write code to understand the data, process and utilize it "
                "for the task. Here is the list of datasets:"
            )
            library_intro = (
                "The environment supports a list of libraries that can be directly "
                "used. Do not forget the import statement:"
            )
            import_instruction = ""

        # Format lists
        data_lake_formatted = self._format_data_lake()
        libraries_formatted = self._format_libraries()
        tool_desc_text = (
            textify_api_dict(self.tool_desc)
            if isinstance(self.tool_desc, dict)
            else str(self.tool_desc)
        )

        return _ENV_RESOURCES_TEMPLATE.format(
            function_intro=function_intro,
            tool_desc=tool_desc_text,
            import_instruction=import_instruction,
            data_lake_path=self.data_lake_path,
            data_lake_intro=data_lake_intro,
            data_lake_content=data_lake_formatted,
            library_intro=library_intro,
            library_content_formatted=libraries_formatted,
        )

    # ── Formatters ───────────────────────────────────────────────

    def _format_data_lake(self) -> str:
        """Format data lake items as name: description lines."""
        lines: list[str] = []
        for item in self.data_lake_content:
            if isinstance(item, dict):
                name = item.get("name", "")
                desc = item.get("description", "")
            elif isinstance(item, str):
                name = item
                desc = self.data_lake_dict.get(item, f"Data lake item: {item}")
            else:
                continue

            if desc:
                lines.append(f"{name}: {desc}")
            else:
                lines.append(name)
        return "\n".join(lines) if lines else "(no data lake items available)"

    def _format_libraries(self) -> str:
        """Format library list as name: description lines."""
        lines: list[str] = []
        for lib in self.library_content_list:
            if isinstance(lib, dict):
                name = lib.get("name", "")
                desc = lib.get("description", "")
            elif isinstance(lib, str):
                name = lib
                desc = self.library_content_dict.get(lib, f"Software library: {lib}")
            else:
                continue

            if desc:
                lines.append(f"{name}: {desc}")
            else:
                lines.append(name)
        return "\n".join(lines) if lines else "(no libraries available)"

    def _format_know_how(self) -> str:
        """Format know-how documents section."""
        header = (
            "📚 KNOW-HOW DOCUMENTS (BEST PRACTICES & PROTOCOLS - ALREADY LOADED):\n"
            "{docs}\n\n"
            "IMPORTANT: These documents are ALREADY AVAILABLE in your context. You do "
            "NOT need to retrieve them or 'review' them as a separate step. You can "
            "DIRECTLY reference and use the information from these documents."
        )
        doc_texts = []
        for doc in self.know_how_docs:
            if isinstance(doc, dict):
                doc_texts.append(f"📚 {doc.get('name', 'Unknown')}:\n{doc.get('content', '')}")
        return header.format(docs="\n\n".join(doc_texts))

    def _format_custom_tools(self) -> str:
        """Format custom tools section."""
        items = []
        for tool in self.custom_tools:
            if isinstance(tool, dict):
                name = tool.get("name", "Unknown")
                desc = tool.get("description", "")
                module = tool.get("module", "custom_tools")
                items.append(f"🔧 {name} (from {module}): {desc}")
            else:
                items.append(f"🔧 {tool}")
        return "🔧 CUSTOM TOOLS (USE THESE FIRST):\n{custom_tools}\n".format(
            custom_tools="\n".join(items),
        )

    def _format_custom_data(self) -> str:
        """Format custom data section."""
        items = []
        for item in self.custom_data:
            if isinstance(item, dict):
                name = item.get("name", "Unknown")
                desc = item.get("description", "")
                items.append(f"📊 {name}: {desc}")
            else:
                items.append(f"📊 {item}")
        return "📊 CUSTOM DATA (PRIORITIZE THESE DATASETS):\n{custom_data}\n".format(
            custom_data="\n".join(items),
        )

    def _format_custom_software(self) -> str:
        """Format custom software section."""
        items = []
        for item in self.custom_software:
            if isinstance(item, dict):
                name = item.get("name", "Unknown")
                desc = item.get("description", "")
                items.append(f"⚙️ {name}: {desc}")
            else:
                items.append(f"⚙️ {item}")
        return "⚙️ CUSTOM SOFTWARE (USE THESE LIBRARIES):\n{custom_software}\n".format(
            custom_software="\n".join(items),
        )
