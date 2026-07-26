<p align="center">
  <img src="./figs/biomni_logo.png" alt="Biochat Logo" width="600px" />
</p>

<p align="center">
  <a href="https://www.biorxiv.org/content/10.1101/2025.05.30.656746v1">
    <img src="https://img.shields.io/badge/Read-Paper-green?style=for-the-badge" alt="Paper" />
  </a>
  <img src="https://img.shields.io/badge/License-Apache%202.0-blue?style=for-the-badge" alt="License" />
  <img src="https://img.shields.io/badge/Python-3.11+-yellow?style=for-the-badge" alt="Python" />
</p>

# Biochat: A General-Purpose Biomedical AI Agent

> **Built on [Biomni](https://github.com/snap-stanford/Biomni)** — Biochat preserves Biomni's original scientific tooling and extends it with an enhanced user experience, modern design, and project-level engineering.

## Overview

Biochat is a general-purpose biomedical AI agent that autonomously executes research tasks across diverse biomedical subfields. It integrates large language model (LLM) reasoning with retrieval-augmented planning and code-based execution to help scientists accelerate research and generate testable hypotheses.

### What Biochat Can Do

- **Biomedical Q&A** — Answer complex questions using 30+ integrated databases (UniProt, Ensembl, PDB, ClinVar, KEGG, ChEMBL…)
- **CRISPR Screen Design** — Plan genome-wide screens, design sgRNA sequences, analyze gene essentiality
- **scRNA-seq Annotation** — Annotate cell types, identify markers, generate population hypotheses
- **ADMET Prediction** — Predict absorption, distribution, metabolism, excretion, and toxicity of compounds
- **Drug Repurposing** — Identify new therapeutic indications for existing drugs
- **Rare Disease Diagnosis** — Analyze phenotypes and variants for diagnostic hypotheses
- **Literature Mining** — Search PubMed / bioRxiv, extract and synthesize findings
- **Experimental Protocol Design** — Generate detailed protocols for cloning, cell culture, and more

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Interface                        │
│  ┌───────────────────┐  ┌─────────────────────────────┐ │
│  │   Streamlit UI    │  │   Gradio UI (legacy)        │ │
│  │  (ChatGPT-style)  │  │   (ProtChat-inspired)       │ │
│  └────────┬──────────┘  └──────────────┬──────────────┘ │
│           │                            │                 │
├───────────┼────────────────────────────┼─────────────────┤
│           │      Service Layer          │                 │
│  ┌────────┴────────────────────────────┴──────────────┐ │
│  │             BioAgentService                         │ │
│  │  • Lazy agent initialization & caching             │ │
│  │  • Unified run_task() with structured output       │ │
│  │  • Progress callbacks for real-time UI updates     │ │
│  └────────┬───────────────────────────────────────────┘ │
│           │                                              │
│  ┌────────┴───────────────────────────────────────────┐ │
│  │            SessionService                           │ │
│  │  • Multi-session chat history                      │ │
│  │  • Pluggable storage backend                       │ │
│  └────────┬───────────────────────────────────────────┘ │
│           │                                              │
├───────────┼──────────────────────────────────────────────┤
│           │      Core Infrastructure                      │
│  ┌────────┴───────────────────────────────────────────┐ │
│  │  BiochatSettings  │  Logging  │  Error Types       │ │
│  └────────┬───────────────────────────────────────────┘ │
│           │                                              │
├───────────┼──────────────────────────────────────────────┤
│           │      Biomni Engine (A1 Agent)                 │
│  ┌────────┴───────────────────────────────────────────┐ │
│  │  Planning → Tool Retrieval → Code Execution →       │ │
│  │  Observation → Iteration → Solution                 │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Key Components

| Layer | Component | Responsibility |
|-------|-----------|----------------|
| **Core** | `biomni.core.settings` | Unified configuration via env vars |
| **Core** | `biomni.core.logging` | Structured logging with levels |
| **Core** | `biomni.core.errors` | Typed exception hierarchy |
| **Service** | `BioAgentService` | Agent lifecycle, task execution, output parsing |
| **Service** | `SessionService` | Multi-session chat history management |
| **Prompts** | `SystemPromptBuilder` | Modular system prompt assembly |
| **Schemas** | `chat.py` | Structured request/response data types |
| **Engine** | `biomni.agent.A1` | Biomni's core agent (preserved unchanged) |
| **Tools** | `biomni.tool.*` | 200+ biomedical tool functions (preserved) |

## Quick Start

### Prerequisites

- Python 3.11+
- Conda (recommended for environment management)
- ~15GB free disk space (~11GB data lake + dependencies)
- API key for at least one LLM provider (Anthropic, OpenAI, DeepSeek, etc.)

### Installation

**Step 1: Set up the environment**

```bash
# Follow the environment setup guide
# See biomni_env/README.md for detailed instructions
cd biomni_env
bash setup.sh
conda activate biomni_e1
```

**Step 2: Install Biochat**

```bash
# From the Biomni-main directory
pip install -e .
```

**Step 3: Configure API keys**

```bash
# Copy the example env file
cp .env.example .env

# Edit .env with your API keys
# Required for your chosen provider:
ANTHROPIC_API_KEY=your_key_here      # for Claude models
# or
OPENAI_API_KEY=your_key_here         # for GPT models
# or
CUSTOM_MODEL_BASE_URL=...            # for DeepSeek / custom models
CUSTOM_MODEL_API_KEY=your_key_here
```

### Launch the UI

**Streamlit (Recommended):**

```bash
streamlit run biomni/ui/biochat_streamlit.py
# → http://localhost:8501
```

**Gradio (Legacy):**

```bash
python scripts/biochat_demo.py
# → http://localhost:7860
```

### Basic Python Usage

```python
from biomni.agent import A1

# Initialize (downloads ~11GB data lake on first run)
agent = A1(path='./data', llm='claude-sonnet-4-20250514')

# Execute biomedical tasks
agent.go("Plan a CRISPR screen to identify genes that regulate T cell exhaustion")
agent.go("Perform scRNA-seq annotation and generate hypotheses about cell populations")
agent.go("Predict ADMET properties for CC(C)CC1=CC=C(C=C1)C(C)C(=O)O")
```

### Using the Service Layer (New)

```python
from biomni.services.agent_service import get_agent_service
from biomni.schemas.chat import ChatRequest

svc = get_agent_service()
svc.ensure_initialized()

response = svc.run_task(ChatRequest(message="Explain EGFR signaling pathway"))
print(response.answer)       # Cleaned final answer (Markdown)
print(response.tool_calls)   # Tools used: ['genomics.query_gene', ...]
print(response.status)       # AgentStatus.COMPLETED
```

## Configuration

Biochat uses a unified settings system. All options can be set via environment variables.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BIOCHAT_LLM` | LLM model name | `claude-sonnet-4-5` |
| `BIOCHAT_DATA_PATH` | Data lake directory | `./data` |
| `BIOCHAT_TIMEOUT_SECONDS` | Code execution timeout | `600` |
| `BIOCHAT_TEMPERATURE` | LLM temperature | `0.7` |
| `BIOCHAT_SOURCE` | LLM provider (Anthropic/OpenAI/Gemini/Groq/Custom) | auto-detect |
| `BIOCHAT_USE_TOOL_RETRIEVER` | Enable tool retrieval | `true` |
| `BIOCHAT_COMMERCIAL_MODE` | Exclude non-commercial datasets | `false` |
| `BIOCHAT_CUSTOM_BASE_URL` | Custom model API URL | — |
| `BIOCHAT_CUSTOM_API_KEY` | Custom model API key | — |
| `BIOCHAT_ACCESS_CODE` | UI access code (comma-separated) | — |

All `BIOCHAT_*` vars have backward-compatible `BIOMNI_*` aliases.

### LLM Providers

Biochat supports Claude, GPT-4, Gemini, Groq, DeepSeek, Ollama, AWS Bedrock, and any OpenAI-compatible custom endpoint. See `biomni/llm.py` for the full list.

```python
from biomni.config import default_config

# Claude
default_config.llm = "claude-sonnet-4-20250514"

# GPT-4
default_config.llm = "gpt-4"

# DeepSeek (custom endpoint)
default_config.llm = "deepseek-chat"
default_config.source = "Custom"
default_config.base_url = "https://api.deepseek.com/v1"
default_config.api_key = "sk-..."
```

## Supported LLM Providers

| Provider | Models | Setup |
|----------|--------|-------|
| **Anthropic** | Claude Sonnet 4, Opus 4, Haiku 4.5 | `ANTHROPIC_API_KEY` |
| **OpenAI** | GPT-4, GPT-4o, o1, o3 | `OPENAI_API_KEY` |
| **Azure OpenAI** | GPT-4 deployments | `OPENAI_API_KEY` + `OPENAI_ENDPOINT` |
| **Google Gemini** | gemini-2.5-pro, gemini-2.5-flash | `GEMINI_API_KEY` |
| **Groq** | Llama, Mixtral via Groq | `GROQ_API_KEY` |
| **AWS Bedrock** | Claude, Llama, Titan via Bedrock | AWS credentials |
| **Ollama** | Local models (Llama, Qwen, DeepSeek…) | Local Ollama server |
| **Custom** | Any OpenAI-compatible API (DeepSeek, SGLang, vLLM…) | `CUSTOM_MODEL_BASE_URL` + `CUSTOM_MODEL_API_KEY` |

## Project Structure

```
Biomni-main/
├── biomni/                          # Main package
│   ├── agent/                       # Biomni agent engine
│   │   ├── a1.py                    # A1 agent class (core reasoning loop)
│   │   └── ...
│   ├── core/                        # ✨ NEW: Core infrastructure
│   │   ├── settings.py              #     Unified configuration
│   │   ├── logging.py               #     Structured logging
│   │   └── errors.py                #     Typed exceptions
│   ├── services/                    # ✨ NEW: Service layer
│   │   ├── agent_service.py         #     BioAgentService wrapper
│   │   └── session_service.py       #     Session management
│   ├── schemas/                     # ✨ NEW: Data schemas
│   │   └── chat.py                  #     Request/Response types
│   ├── prompts/                     # ✨ NEW: Prompt management
│   │   └── system_prompt.py         #     SystemPromptBuilder
│   ├── tool/                        # 200+ biomedical tools
│   ├── ui/                          # User interfaces
│   │   ├── biochat_streamlit.py     # Streamlit UI (ChatGPT-style)
│   │   ├── biochat_ui.py            # Gradio UI
│   │   └── biochat_theme.py         # Design system
│   ├── config.py                    # Legacy config (backward compat)
│   ├── llm.py                       # Multi-provider LLM factory
│   └── utils.py                     # Utility functions
├── scripts/                         # Launch scripts
├── docs/                            # Documentation
├── tutorials/                       # Example notebooks
├── tests/                           # Test suite
├── .env.example                     # Environment template
├── start.sh / start_streamlit.sh    # Convenience launchers
├── pyproject.toml                   # Project metadata
└── README.md                        # This file
```

## Safety & Security

### ⚠️ Code Execution Warning

**Biochat executes LLM-generated code with full system privileges.** This is a powerful capability that requires careful handling:

- **Always run in isolated / sandboxed environments** for production use
- The agent can access files, network, and system commands
- **Never run with access to sensitive data or credentials**
- **Never expose to untrusted users** without strict sandboxing
- Use Docker, VMs, or container isolation for production deployments

### Data Safety

- API keys are managed via **environment variables** — never hardcoded
- Uploaded files are processed locally and not sent to external services
- Database queries go directly to public APIs; Biochat stores no query data

### Clinical Disclaimer

> **Biochat is a research tool, NOT a medical device.** It is designed to enhance research productivity. It should NOT be used for:
> - Autonomous clinical decision-making
> - Direct patient care or diagnosis
> - Generating medical advice without expert review
>
> **Always validate results with qualified domain experts** before applying to real-world problems.

### Data Licensing

Biochat's data ecosystem includes datasets with varying licenses:

- **Academic use**: All datasets are available for non-commercial research
- **Commercial use**: Set `commercial_mode=True` to automatically exclude datasets with non-commercial licenses
- **Review required**: Always review `license_info.md` before commercial deployment

## MCP (Model Context Protocol) Support

Biochat supports MCP servers for external tool integration:

```python
agent = A1()
agent.add_mcp(config_path="./mcp_config.yaml")
agent.go("Find FDA active ingredient information for ibuprofen")
```

See [MCP Integration Docs](docs/mcp_integration.md) for details.

## Contributing

Biochat welcomes contributions! See [CONTRIBUTION.md](CONTRIBUTION.md) for guidelines. Areas of interest:

- **New biomedical tools and analysis functions**
- **Curated datasets and knowledge bases**
- **Software integrations**
- **Know-how documents and protocol guides**
- **UI/UX improvements**

## Attribution

Biochat is built on top of **[Biomni](https://github.com/snap-stanford/Biomni)**, an open-source biomedical AI platform developed by the Stanford SNAP Group. Biochat preserves all of Biomni's original scientific tooling while adding:

- Enhanced UI layer (ChatGPT-style Streamlit + ProtChat-inspired Gradio)
- Service layer with structured output and session management
- Unified configuration and logging
- Project-level documentation and packaging
- Modern design system and UX improvements

### Citing Biomni

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

## License

Biochat is licensed under the **Apache License 2.0**, same as the upstream Biomni project. See [LICENSE](LICENSE) for the full text.

> **Important**: Certain integrated tools, databases, and datasets may carry more restrictive commercial licenses. Review `license_info.md` carefully before commercial use. Biochat does not claim ownership of any third-party code, data, or algorithms.

## FAQ

**Q: Why is the first run so slow?**
A: Biochat downloads ~11GB of curated biomedical data on first run. Subsequent runs are fast.

**Q: Can I skip the data lake download?**
A: Yes — pass `expected_data_lake_files=[]` to `A1()`. Some tools will be unavailable.

**Q: What LLM should I use?**
A: Claude Sonnet 4.5 or GPT-4 provide the best biomedical reasoning. DeepSeek is a good budget option.

**Q: Is this safe for PHI (Protected Health Information)?**
A: **No.** Biochat is not designed for PHI. Use in isolated environments only.

**Q: How does Biochat differ from Biomni?**
A: Biochat is Biomni + engineering layer. Same engine, better UX, structured APIs, cleaner codebase.
