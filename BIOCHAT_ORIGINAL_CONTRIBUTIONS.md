# Biochat Original Contributions

What Biochat adds on top of [Biomni](https://github.com/snap-stanford/Biomni)
(Apache 2.0). Companion to [`THIRD_PARTY_PROVENANCE.md`](THIRD_PARTY_PROVENANCE.md).

## 1. Service & UI layer (original)

| Component | Path |
|---|---|
| Agent service (lifecycle, streaming task API, answer cleaning) | `biomni/services/agent_service.py` |
| Streamlit UI (ChatGPT-style, streaming final answer) | `biomni/ui/biochat_streamlit.py` |
| Gradio UI + theme | `biomni/ui/biochat_ui.py`, `biomni/ui/biochat_theme.py`, `biomni/ui/biochat_about.py` |
| P0 sanitizer (no internal reasoning may reach the UI) | `biomni/ui/sanitize.py` |
| Core settings / errors / logging | `biomni/core/` |
| Chat schemas | `biomni/schemas/` |
| Demo scripts | `scripts/biochat_demo.py`, `scripts/biochat_streamlit_demo.py` |

## 2. Prompt system — XunZi-inspired task templates (original)

- `biomni/prompts/task_templates.py` — structured task registry
  (general / target_discovery / antibody_design / literature_review)
- `biomni/prompts/system_prompt_v2.py` — task-type-aware system prompt
  builder with the six-section output format
  (结论 / 依据与原理 / 方法摘要 / 建议验证实验 / 不确定性与局限 / 安全声明)
  and hidden-chain-of-thought prohibition
- `biomni/eval/response_quality.py` — structural response quality
  evaluation for that format
- Integrated into `biomni/prompts/system_prompt.py` and `_clean_agent_text`
  sanitization paths

## 3. Knowledge registry (original architecture)

`biomni/knowledge/` — registry/source/loader architecture replacing the
upstream `know_how/loader.py`:

- `registry.py` — `KnowledgeRegistry` with license-policy exclusion
  (`exclude_non_commercial`)
- `source.py` — `KnowledgeSource` model + Markdown parser
- `loaders/local.py` — local Markdown loader
- Legacy path `biomni/know_how/` reduced to a compatibility adapter

## 3b. Environment & tool catalogs (configurization)

Static upstream descriptors moved from Python literals to YAML with
metadata and license policy:

- `biomni/environment/` — `catalog.yaml` (76 datasets + 113 libraries,
  37 non-commercial entries with license notes), `schema.py`,
  `loader.py`, `registry.py` (`EnvironmentCatalog` with full/commercial
  views).  Generator: `scripts/build_environment_catalog.py`.
- `biomni/tool/tool_description/catalog.yaml` — 226 tool schemas across
  23 fields; `_catalog_loader.py`; per-field adapter modules.
  Generator: `scripts/build_tool_catalog.py`.
- `biomni/tool/registry.py` — indexed `ToolRegistry` (name/id maps,
  lazy document frame) replacing the upstream linear-scan registry.
- `biomni/model/resource_selector.py` — `ResourceSelector` with
  separated prompt builder (`build_selection_prompt`) and response
  parser (`parse_selection_response`) replacing the upstream
  `ToolRetriever`.

## 3c. Audit tooling (original)

- `scripts/audit_import_usage.py` → `reports/upstream_usage_audit.csv`
- `scripts/audit_similarity_reduction.py` →
  `reports/similarity_reduction_candidates.csv` (similarity against the
  vendored reference `third_party/biomni_upstream_reference/`, usage
  classification incl. dynamic tool-registry imports)
- `check_safety.py` — offline safety checks (sanitizer, prompt
  guardrails, provenance files)
- `scripts/demo_biochat_competition.py --quick` — offline runtime demo

## 4. Antibody design pipeline (original)

`biomni/tool/antibody_design/` — the "Fusion Plan" phases 3A–3D
(CDRH3 scoring/filtering, DiffCDRH3 diffusion generation, NanoBodyBuilder2
structure prediction, HDOCK docking). See `FINAL_FUSION_STATUS.md` and
`docs/antibody_design_hdock_docker.md`.

## 5. Tool profiles — minimal vs full runtime (original)

`BIOCHAT_TOOL_PROFILE = "minimal" | "full"` (default `full`; the competition
demo defaults to `minimal`):

- `biomni/tool/profiles.py` — generated manifest listing the minimal
  modules (antibody design pipeline + demo-referenced tools + engine glue:
  antibody_design, database, literature, protocols, support_tools);
- `load_all_tool_descriptions(profile=...)` and `ToolRegistry(profile=...)`
  honor the profile; minimal = 57 of 226 tools across 5 of 23 modules;
- upstream scientific tool modules are untouched — the full profile loads
  every attributed Biomni tool, and the minimal profile merely does not
  register the optional ones;
- generator/audit: `scripts/audit_runtime_tools.py` →
  `reports/runtime_tool_usage.csv` (per-tool usage classification).

## 6. Streaming execution (original)

- `A1.go_stream()` dual-mode LangGraph streaming
  (`stream_mode=["messages", "values"]`) yielding token-level events
- Incremental `answering` events in `BioAgentService.run_task_stream`
  (final answer streams after `<solution>` opens; thinking tokens never
  leave the service layer)
- Throttled streaming card rendering in the Streamlit UI

## 6. Refactors of upstream code (real rewrites, not renaming)

| Upstream | Biochat result |
|---|---|
| 5669-line `a1.py` | `biomni/agent/a1.py` facade + `workflow.py`, `resource_manager.py`, `retrieval.py`, `conversation_exporter.py`, `mcp_server.py`, `ui_launcher.py`, `self_critic.py` (3628 lines total, similarity to upstream ≈ 7.5%) |
| Monolithic `llm.py` | `biomni/llm/` package (factory, provider registry, source detection) |
| Monolithic `utils.py` | `biomni/utils/` package |
| `config.py` | Structured `BiochatSettings` (similarity ≈ 60%) |

## Methodology

All reductions in upstream code similarity are the result of **deleting or
archiving unreachable code** (see `reports/upstream_usage_audit.csv`) and
**architectural replacement with behavior-compatible implementations** —
never mechanical rewriting (variable renaming, comment translation,
string substitution) performed for its own sake.
