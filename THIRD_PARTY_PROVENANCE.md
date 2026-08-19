# Third-Party Provenance

Biochat is derived from **[Biomni](https://github.com/snap-stanford/Biomni)**
(Huang et al., 2025 — *Biomni: A General-Purpose Biomedical AI Agent*), a
biomedical AI agent platform released by the Stanford SNAP Group under the
**Apache License 2.0**.

This document records which parts of this repository come from upstream Biomni,
which parts have been replaced or archived, and where attribution lives.
It is maintained alongside `scripts/audit_import_usage.py` /
`reports/upstream_usage_audit.csv`.

## Upstream code still on the runtime path (kept with attribution)

| Path | Role | Note |
|---|---|---|
| `biomni/env_desc.py`, `biomni/env_desc_cm.py` | Data-lake & library descriptions | Data content, consumed by `biomni/agent/a1.py` |
| `biomni/agent/workflow.py` | LangGraph generate→execute loop | Extracted/refactored from upstream `a1.py` during the modularization refactor |
| `biomni/agent/a1.py`, `biomni/config.py`, `biomni/utils/*` | Agent facade, config, utilities | Partially rewritten (see `BIOCHAT_ORIGINAL_CONTRIBUTIONS.md`) |
| `biomni/tool/*` (excluding `antibody_design/`), `biomni/model/*`, `biomni/llm/providers/*` | Scientific tools, retrievers, LLM providers | Largely upstream; LLM layer modularized by Biochat. Tool *implementations* are never rewritten — profile-based loading (`minimal`/`full`) controls which modules get registered, see `reports/runtime_tool_usage.csv` |
| `biomni/prompts/system_prompt.py` | System prompt builder | Heavily modified by Biochat (XunZi output format, antibody addendum, sanitization) |

## Upstream code replaced by Biochat architectures

| Upstream | Replacement | Legacy path |
|---|---|---|
| `biomni/know_how/loader.py` | `biomni/knowledge/` — registry (`registry.py`), source model (`source.py`), loaders (`loaders/local.py`) | `biomni/know_how/` kept as a thin adapter (`adapter_active`) |
| `biomni/agent/react.py` (standalone ReAct agent) | LangGraph workflow (`biomni/agent/workflow.py`) + `biomni/services/agent_service.py` | None needed — zero importers found; file archived |
| `biomni/env_desc.py` / `biomni/env_desc_cm.py` (dict literals) | `biomni/environment/` — `catalog.yaml` + `schema.py` + `loader.py` + `registry.py`; commercial view = filtered projection with per-entry `commercial_allowed`/`license_note` | Both paths kept as thin adapters (field-level output identical, tested) |
| `biomni/tool/tool_description/*.py` (21 description modules) | `biomni/tool/tool_description/catalog.yaml` + `_catalog_loader.py` | Each field module is a thin adapter exposing the same `description` list (tested against the upstream reference) |
| `biomni/tool/tool_registry.py` | `biomni/tool/registry.py` — indexed registry (name/id maps, lazy document frame) | Thin adapter re-export |
| `biomni/model/retriever.py` | `biomni/model/resource_selector.py` — `ResourceSelector` with separated prompt builder + response parser | Thin adapter (`ToolRetriever` alias) |

## Upstream code archived (removed from runtime)

Moved to `third_party/biomni_upstream_archive/` on 2026-08-19 (git renames
preserve history). None of these were reachable from the Biochat runtime:

| Archived path | Reason (audit) |
|---|---|
| `biomni/agent/react.py` | 0 importers — superseded by `workflow.py` + `BioAgentService` |
| `biomni/agent/env_collection.py` | Only used by `biorxiv_scripts` (archived) |
| `biomni/agent/function_generator.py` | Only used by `biorxiv_scripts` (archived) |
| `biomni/agent/qa_llm.py` | 0 importers — used by the archived react.py |
| `biomni/biorxiv_scripts/` | Standalone paper-processing CLI scripts, 0 importers |
| `biomni/eval/biomni_eval1.py` | Benchmark runner, 0 importers; `biomni/eval/` now exposes Biochat's `evaluate_response_quality` |
| `biomni/task/{base_task,hle,lab_bench}.py` | Upstream benchmark task classes, 0 importers |
| `biomni/tool/example_mcp_tools/` | Example MCP tool, 0 importers |

The archived files remain under Apache 2.0 and may be imported explicitly from
`third_party/biomni_upstream_archive/` if ever needed.

## License retention

- `LICENSE` — Apache License 2.0 (unchanged).
- `license_info.md` — third-party data/tool licensing notes (unchanged).
- `third_party/biomni_upstream_archive/README.md` — archive manifest.
- Know-how documents (`biomni/knowledge/docs/*.md`) carry per-document
  `## Metadata` license fields (e.g. CC BY 4.0) enforced by
  `KnowledgeRegistry.exclude_non_commercial()` in commercial mode.

## Keeping this document honest

Biochat performs **no mechanical de-duplication** (no variable renaming,
comment translation, or string substitution purely to reduce similarity).
All upstream-footprint reduction in this repository is either:

1. **deletion/archival of unreachable code**, verified by
   `python scripts/audit_import_usage.py` (writes
   `reports/upstream_usage_audit.csv`), or
2. **architectural replacement** with behavior-compatible Biochat
   implementations (registry/adapter pattern above), covered by
   `tests/test_knowledge_registry.py`.
