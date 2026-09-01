"""System Prompt Builder for the Biochat / Biochat Agent.

Includes the Phase 3A antibody design addendum.
"""

from __future__ import annotations

from biochat.utils import textify_api_dict

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
- For MULTIPLE-CHOICE questions or questions that name a specific database
  (DisGeNET, OMIM, Ensembl, ClinVar, miRDB, STRING, ...): treat them as
  database queries — verify with <execute> whenever any tool or data-lake
  file can help. They are NOT "simple factual Q&A".
- NEVER append </execute> or </solution> as closing tags without opening tags.
- NEVER apologize for using the wrong format — just use the correct format.
"""

_DATABASE_VERIFICATION_ADDENDUM = """\
DATABASE VERIFICATION REQUIREMENT (数据库核验要求):
When the user's question references a specific database (e.g., DisGeNET, OMIM,
Ensembl, ClinVar, miRDB, STRING, Reactome, KEGG, MSigDB), asks "according to
<database>", or asks about facts that can only be confirmed by querying a
database or the data lake, you MUST verify with <execute> — never answer such
questions from memory alone.

Common recipes (load the data-lake files shown above with pandas):
- Gene-disease association (DisGeNET/OMIM): load DisGeNET.parquet (columns:
  Disorder, Genes) and omim.parquet (column: Phenotypes), or use
  query_opentarget() / query_monarch() against the live APIs. A gene counts as
  "associated with D per DisGeNET" if it appears in the Genes list of the
  DisGeNET row whose Disorder matches D; "per OMIM" if D appears in its
  Phenotypes column.
- Gene location by cytoband (Ensembl): load msigdb_human_c1_positional_geneset.parquet
  and look up the chromosome_id (e.g. "chr6q21") — its geneSymbols are the
  genes at that band.
- TF binding-site promoter targets (GTRD): load
  msigdb_human_c3_subset_transcription_factor_targets_from_GTRD.parquet and
  look up the <TF>_TARGET_GENES row.
- miRNA targets (miRDB): load miRDB_v6.0_results.parquet and filter by the
  miRNA column; normalize the miRNA name in the question to the file's format
  (e.g. "MIR186_3P" → "hsa-miR-186-3p": lowercase, dashes, species prefix)
  and match case-insensitively on the numeric ID.
- Gene-set membership (MSigDB / MouseMine / MP): load the msigdb_human_* /
  mousemine_* parquet files in the data lake and check membership.
- Variant pathogenicity (ClinVar): use query_clinvar().
- Viral-host protein interaction: use query_stringdb() or query_uniprot().

If the required data is genuinely unavailable, state that explicitly instead
of guessing. This overrides the "simple factual Q&A" shortcut: a question that
names a database is a database query and MUST be verified.
"""

_ANSWER_FORMAT_ADDENDUM = """\
ANSWER FORMAT REQUIREMENTS (答案格式要求):
- When reporting an amino acid, always give the full name (e.g., Glycine,
  Proline, Cysteine) or its standard three-letter code (Gly, Pro, Cys) — never
  a bare single letter (G, P, C).
- When reporting the translated AA sequence of an ORF, include the terminal
  stop codon as "*" (standard translation convention). If your ORF tool omits
  the trailing "*", append it (e.g. "...HLS" → "...HLS*").
- When the question is multiple-choice, the very LAST line of your final
  answer must be exactly "FINAL: <letter>" (e.g. "FINAL: D"), where <letter>
  is the single option letter you choose. No text may follow that line.
"""

_ANTIBODY_DESIGN_ADDENDUM = """\
ANTIBODY DESIGN REQUIREMENTS:
When the user requests antibody/CDR/nanobody/VH-only design:
1. DO NOT invent CDRH3 sequences from your training data.
2. Use design_vh_only_antibodies(epitope_sequence=..., num_candidates=...)
   from biochat.tool.antibody_design.
3. NEVER fabricate GRAVY, pI, docking scores, or binding affinity values.
4. Always include the safety disclaimer from the tool output.
5. If the tool is unavailable, clearly state limitations.
6. NEVER call any computed score "binding affinity", "ΔG", "Kd", or "ddG".
7. When reporting results, ALWAYS include score provenance.
8. If diffusion mode (pipeline_level="diffusion_sequence") reports a model
   problem, diagnose it ONLY with check_model_files() from
   biochat.tool.antibody_design.diffusion_pipeline — it reports which of the
   three weight files exist and their sizes in one call.
9. NEVER search the filesystem for model weights with glob, find, os.walk,
   or any recursive scan — especially from "/" (it can hang for tens of
   minutes and trigger permission errors). If BIOMNI_ANTIBODY_MODEL_DIR is
   not set and the design tool did not auto-locate the weights, report the
   missing environment variable instead of searching the disk.
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
                             _OUTPUT_FORMAT_ADDENDUM, _PROTOCOL_ADDENDUM,
                             _DATABASE_VERIFICATION_ADDENDUM,
                             _ANSWER_FORMAT_ADDENDUM]
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
