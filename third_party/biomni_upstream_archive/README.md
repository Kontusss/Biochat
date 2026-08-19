# Biomni Upstream Archive

This directory preserves unmodified (or minimally modified) source files from the
original [snap-stanford/Biomni](https://github.com/snap-stanford/Biomni) project
(Apache License 2.0) that are **no longer on the Biochat runtime path**.

They were moved here (2026-08-19) during the upstream-footprint reduction, based on
`scripts/audit_import_usage.py` — see `reports/upstream_usage_audit.csv` and
`THIRD_PARTY_PROVENANCE.md` for the full audit.

## Contents

| Archived path | Original path | Why archived |
|---|---|---|
| `biomni/agent/react.py` | `biomni/agent/react.py` | Orphaned ReAct agent — zero imports; replaced in runtime by the LangGraph workflow (`biomni/agent/workflow.py`) + `BioAgentService` |
| `biomni/agent/env_collection.py` | `biomni/agent/env_collection.py` | Only used by `biorxiv_scripts` (also archived) |
| `biomni/agent/function_generator.py` | `biomni/agent/function_generator.py` | Only used by `biorxiv_scripts` (also archived) |
| `biomni/agent/qa_llm.py` | `biomni/agent/qa_llm.py` | Zero imports — used by the archived react.py |
| `biomni/biorxiv_scripts/` | `biomni/biorxiv_scripts/` | Standalone paper-processing CLI scripts; zero runtime imports |
| `biomni/eval/biomni_eval1.py` | `biomni/eval/biomni_eval1.py` | Benchmark runner; zero runtime imports. `biomni/eval/` now exposes `evaluate_response_quality` (Biochat original) |
| `biomni/task/{base_task,hle,lab_bench}.py` | `biomni/task/` | Upstream benchmark task classes; zero runtime imports |
| `biomni/tool/example_mcp_tools/` | `biomni/tool/example_mcp_tools/` | Example MCP tool; zero runtime imports |

## License

All files in this directory are © the original Biomni authors, licensed under the
[Apache License 2.0](../LICENSE) (see `../license_info.md` in the upstream project).
They are preserved here for attribution and reference; they are not executed by
Biochat at runtime.

If you need any of these modules, import them explicitly from this archive
directory rather than from `biomni/`.
