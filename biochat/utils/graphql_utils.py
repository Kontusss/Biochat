"""GraphQL, HPO parsing, and code-generation utilities.

Replaces ``execute_graphql_query``, ``parse_hpo_obo``,
``process_bio_retrieval_ducoment``, and ``write_python_code``
from the original ``utils.py``.
"""

from __future__ import annotations

import json

import pandas as pd
import requests


# ═══════════════════════════════════════════════════════════════
# GraphQL
# ═══════════════════════════════════════════════════════════════

def execute_graphql_query(
    query: str,
    variables: dict,
    api_address: str = "https://api.genetics.opentargets.org/graphql",
) -> dict:
    """Execute a GraphQL query and return the JSON response."""
    resp = requests.post(
        api_address,
        json={"query": query, "variables": variables},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json()
    resp.raise_for_status()


# ═══════════════════════════════════════════════════════════════
# HPO parsing
# ═══════════════════════════════════════════════════════════════

def parse_hpo_obo(file_path: str) -> dict[str, str]:
    """Parse an HPO OBO file into ``{HP_id: phenotype_name}``."""
    hp_dict: dict[str, str] = {}
    current_id: str | None = None
    current_name: str | None = None

    with open(file_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("[Term]"):
                if current_id and current_name:
                    hp_dict[current_id] = current_name
                current_id = None
                current_name = None
            elif line.startswith("id: HP:"):
                current_id = line.split(": ", 1)[1]
            elif line.startswith("name:"):
                current_name = line.split(": ", 1)[1]

        if current_id and current_name:
            hp_dict[current_id] = current_name

    return hp_dict


# ═══════════════════════════════════════════════════════════════
# Retrieval corpus builder
# ═══════════════════════════════════════════════════════════════

def build_retrieval_corpus(
    documents_df: pd.DataFrame,
) -> tuple[dict[int, str], dict[str, str]]:
    """Build an IR corpus and corpus→tool mapping from tool documents."""
    ir_corpus: dict[int, str] = {}
    corpus2tool: dict[str, str] = {}

    for row in documents_df.itertuples():
        doc = row.document_content
        key = (
            f"{doc.get('name', '')}, {doc.get('description', '')}, "
            f"{doc.get('url', '')}, , required_params: "
            f"{json.dumps(doc.get('required_parameters', ''))}"
            f", optional_params: "
            f"{json.dumps(doc.get('optional_parameters', ''))}"
        )
        ir_corpus[row.docid] = key
        corpus2tool[key] = doc.get("name", "")

    return ir_corpus, corpus2tool


# ═══════════════════════════════════════════════════════════════
# Code generation (LLM-based)
# ═══════════════════════════════════════════════════════════════

def generate_python_code_with_llm(request: str) -> str:
    """Generate Python code using an LLM (hardcoded to Claude for now).

    .. note::
       This function was present in the original ``utils.py`` and
       is preserved for backward compatibility.  It hardcodes
       ``ChatAnthropic(model="claude-3-5-sonnet-20240620")``.
    """
    from langchain_anthropic import ChatAnthropic
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    model = ChatAnthropic(model="claude-3-5-sonnet-20240620")
    template = (
        "Write some python code to solve the user's problem.\n\n"
        "Return only python code in Markdown format, e.g.:\n\n"
        "```python\n....\n```"
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", template),
        ("human", "{input}"),
    ])

    def _sanitize(text: str) -> str:
        _, after = text.split("```python", 1)
        return after.split("```", 1)[0]

    chain = prompt | model | StrOutputParser() | _sanitize
    return chain.invoke({"input": "write a code that " + request})


# ── Backward-compatible aliases ─────────────────────────────────
process_bio_retrieval_ducoment = build_retrieval_corpus
write_python_code = generate_python_code_with_llm
