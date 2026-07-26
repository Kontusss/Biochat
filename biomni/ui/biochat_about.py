"""
Biochat About & Landing Page

Provides a standalone Gradio page with project information,
capabilities overview, and attribution. This is original Biochat
content that does not modify core Biomni functionality.
"""

from __future__ import annotations


def launch_biochat_about(server_name: str = "0.0.0.0", share: bool = False):
    """Launch the Biochat About & Landing page.

    This standalone page provides project information, capability
    descriptions, safety policy, and attribution without requiring
    the full agent to be initialized.
    """
    try:
        import gradio as gr
    except ImportError:
        raise ImportError("Gradio is not installed. Install with: pip install gradio>=5.0,<6.0")

    from biomni.ui.biochat_theme import BiochatTheme

    with gr.Blocks(
        css=BiochatTheme.CUSTOM_CSS,
        title="Biochat — About",
        theme=gr.themes.Soft(primary_hue="indigo", neutral_hue="slate").set(
            body_background_fill="#f7f8fb",
            button_primary_background_fill="#4f46e5",
            button_primary_background_fill_hover="#4338ca",
            block_background_fill="#ffffff",
            block_radius="12px",
        ),
    ) as demo:
        gr.HTML("""
        <div class="biochat-header">
            <span class="logo">🧬 Biochat</span>
            <span class="version-badge">v2.0</span>
            <span class="engine-badge">Biomni Engine</span>
        </div>
        """)

        with gr.Tabs():
            with gr.TabItem("🏠 About"):
                gr.Markdown("""
                # 🧬 Biochat — Biomedical AI Agent

                **Biochat** is a general-purpose biomedical AI agent designed to autonomously
                execute a wide range of research tasks across diverse biomedical subfields.

                ### What Biochat Does

                - **Autonomous Research**: Plan and execute multi-step biomedical analyses
                - **Literature Mining**: Search, extract, and synthesize knowledge from biomedical literature
                - **Database Queries**: Query 30+ biomedical databases (UniProt, Ensembl, PDB, ClinVar…)
                - **Computational Biology**: Run domain-specific analyses across biochemistry, genomics,
                  pharmacology, cell biology, and more
                - **Protocol Execution**: Follow and adapt lab protocols for experimental design
                - **Hypothesis Generation**: Generate testable hypotheses from integrated data analysis

                ### Built on Biomni

                Biochat is built on top of the [Biomni](https://github.com/snap-stanford/Biomni) open-source
                biomedical AI platform. Biochat preserves all of Biomni's original scientific tooling while
                adding an enhanced user interface, modern design, and original project-level components.

                ### License

                Biochat is licensed under the **Apache License 2.0**, same as the upstream Biomni project.
                See the [LICENSE](https://github.com/snap-stanford/Biomni/blob/main/LICENSE) file for details.

                > **Important**: Certain integrated tools, databases, and datasets may carry more restrictive
                > commercial licenses. Review `license_info.md` carefully before any commercial use.
                """)

            with gr.TabItem("🔬 Capabilities"):
                gr.Markdown("""
                # 🔬 Biochat Capability Dashboard

                ## Scientific Domains

                | Domain | Key Capabilities |
                |:---|:---|
                | **Biochemistry** | Protein structure analysis, enzyme kinetics, binding affinity prediction |
                | **Genomics** | Variant annotation, GWAS analysis, sequence alignment, gene set enrichment |
                | **Pharmacology** | ADMET prediction, drug-drug interactions, target identification |
                | **Cell Biology** | scRNA-seq annotation, pathway analysis, cell-type deconvolution |
                | **Microbiology** | Pathogen genomics, antimicrobial resistance, microbiome analysis |
                | **Immunology** | Epitope prediction, TCR/BCR analysis, immune repertoire profiling |
                | **Cancer Biology** | Somatic variant analysis, driver gene identification, tumor evolution |
                | **Systems Biology** | Metabolic modeling, network analysis, dynamical simulation |

                ## Integrated Databases (30+)

                - **Protein**: UniProt, PDB, InterPro, STRING
                - **Genomic**: Ensembl, UCSC, gnomAD, ClinVar, dbSNP
                - **Pharmacology**: ChEMBL, PubChem, DrugBank, OpenFDA
                - **Literature**: PubMed, bioRxiv, GWAS Catalog
                - **Pathways**: KEGG, Reactome, Gene Ontology
                - **Clinical**: ClinicalTrials.gov, DailyMed, DisGeNET
                - **Specialized**: DepMap, GTEx, ENCODE, GEO, PRIDE

                ## Execution Modes

                1. **Chat Mode** — Interactive Q&A with tool-augmented reasoning
                2. **Autonomous Research** — Multi-step research with planning and execution
                3. **Code Execution** — Secure Python/R/Bash execution for custom analyses
                4. **MCP Integration** — Connect external tools via Model Context Protocol
                """)

            with gr.TabItem("🛡️ Safety"):
                gr.Markdown("""
                # 🛡️ Biochat Safety Policy

                ## Code Execution Safety

                **Biochat executes LLM-generated code with full system privileges.**
                This is a powerful capability that comes with important safety considerations:

                - Use in **isolated/sandboxed environments** for production use
                - The agent can access files, network, and system commands
                - Be careful with **sensitive data or credentials**
                - Never run Biochat with unrestricted access to critical systems

                ## Data Safety

                - API keys are managed via **environment variables**, never hardcoded
                - Uploaded files are processed locally and not sent to external services
                - Database queries go directly to public APIs; no data is stored by Biochat

                ## Data Licensing & Commercial Use

                Biochat's data ecosystem includes datasets with varying licenses:

                - **Academic use**: All datasets are available for non-commercial research
                - **Commercial use**: Set `commercial_mode=True` to automatically exclude
                  datasets with non-commercial licenses (CC-BY-NC, CC-BY-NC-SA, etc.)
                - **Review required**: Always review `license_info.md` before commercial deployment

                ### Commercial Mode

                ```python
                from biomni.agent import A1
                agent = A1(commercial_mode=True)  # Excludes non-commercial datasets
                ```

                ## Responsible Use

                Biochat is designed for **research productivity enhancement**, not for:
                - Autonomous clinical decision-making
                - Direct patient care
                - Generating medical advice without expert review

                Always validate results with domain experts before applying to real-world problems.
                """)

            with gr.TabItem("📖 Workflow"):
                gr.Markdown("""
                # 📖 Biochat Workflow

                ## How Biochat Processes Your Query

                ```
                User Query
                    │
                    ▼
                ┌─────────────────────┐
                │ 1. Tool Retrieval   │  ← Finds relevant tools, databases & know-how
                └─────────┬───────────┘
                          │
                          ▼
                ┌─────────────────────┐
                │ 2. Planning         │  ← LLM plans multi-step analysis
                └─────────┬───────────┘
                          │
                          ▼
                ┌─────────────────────┐
                │ 3. Execution Loop   │  ← Execute code, query databases
                │   ┌───────────────┐ │
                │   │ Think → Act   │ │     Iterative reasoning
                │   │ → Observe     │ │     with self-correction
                │   └───────────────┘ │
                └─────────┬───────────┘
                          │
                          ▼
                ┌─────────────────────┐
                │ 4. Synthesis        │  ← Results, analysis & hypotheses
                └─────────────────────┘
                ```

                ## Key Components

                1. **Tool Retriever** — Semantic search over 200+ biomedical tools
                2. **Know-How Library** — Curated protocols, best practices, guides
                3. **Data Lake** — ~11GB of integrated biomedical datasets
                4. **LLM Reasoning** — Claude, GPT-4, DeepSeek, or custom models
                5. **Code Executor** — Python, R, and Bash execution sandbox

                ## Example Workflow: CRISPR Screen Design

                1. **Query**: "Plan a CRISPR screen for T cell exhaustion genes"
                2. **Retrieval**: Loads genomics tools, DepMap data, sgRNA design guides
                3. **Planning**: Identifies steps — gene selection → sgRNA design → validation
                4. **Execution**: Queries databases, runs statistical analyses, designs sequences
                5. **Synthesis**: Returns ranked gene list, sgRNA sequences, experimental rationale
                """)

            with gr.TabItem("⚙️ Configuration"):
                gr.Markdown("""
                # ⚙️ Biochat Configuration

                ## Quick Start

                ```python
                from biomni.config import default_config
                from biomni.agent import A1

                # Set global configuration
                default_config.llm = "claude-sonnet-4-20250514"
                default_config.timeout_seconds = 1200

                # Initialize agent
                agent = A1(path='./data')
                agent.go("Your biomedical research question")
                ```

                ## Environment Variables

                Biochat supports both `BIOMNI_*` (original) and `BIOCHAT_*` (new) env var prefixes:

                ```bash
                # Both work — BIOCHAT_ takes priority when both are set
                export BIOMNI_LLM=claude-sonnet-4-20250514     # Original name
                export BIOCHAT_LLM=gpt-4                         # New name (preferred)
                ```

                ## Available Settings

                | Setting | Env Var (new) | Env Var (original) | Default |
                |:---|:---|:---|:---|
                | LLM Model | `BIOCHAT_LLM` | `BIOMNI_LLM` | `claude-sonnet-4-5` |
                | Data Path | `BIOCHAT_PATH` | `BIOMNI_DATA_PATH` | `./data` |
                | Timeout | `BIOCHAT_TIMEOUT_SECONDS` | `BIOMNI_TIMEOUT_SECONDS` | `600` |
                | Temperature | `BIOCHAT_TEMPERATURE` | `BIOMNI_TEMPERATURE` | `0.7` |
                | Tool Retriever | `BIOCHAT_USE_TOOL_RETRIEVER` | `BIOMNI_USE_TOOL_RETRIEVER` | `true` |
                | Commercial Mode | `BIOCHAT_COMMERCIAL_MODE` | `BIOMNI_COMMERCIAL_MODE` | `false` |
                | LLM Source | `BIOCHAT_SOURCE` | `BIOMNI_SOURCE` | auto-detect |
                """)

            with gr.TabItem("📝 Attribution"):
                gr.Markdown("""
                # 📝 Attribution

                ## Built on Biomni

                Biochat is built on top of [Biomni](https://github.com/snap-stanford/Biomni),
                an open-source biomedical AI platform developed by the Stanford SNAP Group.

                **Biochat preserves all of Biomni's original scientific tooling**. The Biochat
                project adds an enhanced user interface, modern design language, project-level
                documentation, and original components without modifying core algorithms.

                ## Citing Biomni

                If you use Biochat in your research, please cite the underlying Biomni work:

                ```bibtex
                @article{huang2025biomni,
                  title={Biomni: A General-Purpose Biomedical AI Agent},
                  author={Huang, Kexin and Zhang, Serena and Wang, Hanchen and
                          Qu, Yuanhao and Lu, Yingzhou and Roohani, Yusuf and
                          Li, Ryan and Qiu, Lin and Zhang, Junze and Di, Yin and others},
                  journal={bioRxiv},
                  pages={2025--05},
                  year={2025},
                  publisher={Cold Spring Harbor Laboratory}
                }
                ```

                ## Upstream License

                - Biomni: Apache License 2.0
                - Biochat additions: Apache License 2.0
                - See [LICENSE](https://github.com/snap-stanford/Biomni/blob/main/LICENSE)

                ## Third-Party Data

                Biochat integrates data from many sources. See `license_info.md` for a
                complete list of data sources, their licenses, and commercial use terms.

                > Biochat does not claim ownership of any third-party code, data, or
                > algorithms. All third-party components retain their original licenses.
                > Biochat's original contributions are limited to the UI layer,
                > documentation, branding, and project configuration.
                """)

        gr.HTML("""
        <div class="biochat-attribution">
            <strong>Biochat</strong> — Built on <a href="https://github.com/snap-stanford/Biomni" target="_blank">Biomni</a>.
            Licensed under <a href="https://www.apache.org/licenses/LICENSE-2.0" target="_blank">Apache 2.0</a>.
        </div>
        """)

    print(f"🧬 Launching Biochat About page on {server_name}:7860")
    demo.launch(share=share, server_name=server_name)
