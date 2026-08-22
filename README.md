<p align="center">
  <img src="./figs/biochat_logo.png" alt="Biochat Logo" width="600px" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg?style=for-the-badge" alt="Python" />
  <img src="https://img.shields.io/badge/Streamlit-UI-red.svg?style=for-the-badge" alt="Streamlit" />
  <img src="https://img.shields.io/badge/LangChain-Agent-orange.svg?style=for-the-badge" alt="LangChain" />
  <img src="https://img.shields.io/badge/License-Apache%202.0-orange.svg?style=for-the-badge" alt="License" />
  <img src="https://img.shields.io/badge/Version-v2.0.0-red.svg?style=for-the-badge" alt="Version" />
  <img src="https://img.shields.io/badge/Tools-600+-brightgreen.svg?style=for-the-badge" alt="Tools" />
</p>

# Biochat: 通用生物医学 AI Agent

> 🧬 自主执行生物医学研究任务的 AI Agent — 600+ 专业工具、代码级推理、多模态 UI
>
> 规划 → 工具检索 → 代码执行 → 自我反思的完整 Agent 循环，加速你的科研发现

## ✨ 核心特性

- 🤖 **自主任务执行** — 规划 → 工具检索 → 代码执行 → 观察反思的完整 Agent 循环，端到端完成复杂研究任务
- 🧬 **600+ 生物医学工具** — 覆盖 20+ 子领域：基因组学、CRISPR 筛选设计、scRNA-seq 注释、ADMET 预测、罕见病诊断、文献挖掘等
- 💊 **抗体设计管线** — 扩散模型序列生成、结构预测、HDock 分子对接、可开发性评估、多维度候选排序的一站式工作流
- 📚 **知识库增强** — 内置 sgRNA 设计指南、单细胞注释等 know-how 文档，检索增强规划
- 🔌 **8 大 LLM 供应商** — Anthropic / OpenAI / Azure / Gemini / Groq / Bedrock / Ollama / 任意 OpenAI 兼容接口（DeepSeek、vLLM…）
- 💬 **现代化双 UI** — Streamlit（ChatGPT 风格，推荐）+ Gradio（旧版），支持多会话、流式输出、进度可视化、PDF 导出
- 🧩 **MCP 集成** — 通过 Model Context Protocol 接入外部工具服务
- 🔒 **安全可控** — 访问码验证（`hmac.compare_digest`）、回环默认绑定、商业/非商业数据集自动隔离；生成代码执行默认禁用，需显式开启

## 🛠️ 技术栈

- **框架**: LangChain + Pydantic + Streamlit / Gradio
- **Agent 引擎**: A1（规划-检索-执行-反思循环）
- **LLM**: Anthropic Claude / OpenAI GPT / Gemini / DeepSeek 等 8 种供应商
- **数据湖**: ~11GB 精选生物医学数据集（首次运行自动下载）
- **工具协议**: MCP (Model Context Protocol)
- **工程化**: ruff + pre-commit + pytest

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Conda（推荐，用于环境管理）
- ~15GB 可用磁盘空间（~11GB 数据湖 + 依赖）
- 至少一个 LLM 供应商的 API Key（Anthropic / OpenAI / DeepSeek 等）

### 安装与启动

#### macOS / Linux（一键启动）

```bash
# 1. 克隆项目
git clone <repository_url>
cd Biochat-main

# 2. 安装 Conda 环境（首次运行，含 R/CLI 工具，耗时较长）
cd biochat_env && bash setup.sh && cd ..
conda activate biomni_e1

# 3. 安装 Biochat（按需选择附加依赖）
pip install -e .                                  # 核心运行时（最小安装）
pip install -e ".[streamlit]"                     # + Streamlit UI
pip install -e ".[gradio]"                        # + Gradio UI（旧版）
pip install -e ".[providers]"                     # + 各 LLM 供应商 SDK
pip install -e ".[full-tools]"                    # + 科学计算工具栈
pip install -e ".[dev,streamlit,gradio,providers]" # 开发/CI 全套

# 4. 配置 API Key 与安全选项
cp .env.example .env
vim .env   # 填入你的 API Key，详见下方「配置说明」与「安全模型」

# 5. 一键启动 🚀
bash start.sh
```

启动成功后显示：

```
==========================================
  🧬 Biochat 启动中...
  引擎: Biochat
  模型: deepseek-chat
  Source: Custom
  数据: ./data
  UI: Streamlit (ChatGPT 风格)
  地址: http://localhost:8501
==========================================
```

> 首次启动会自动下载 ~11GB 数据湖，请耐心等待；后续启动秒开。

#### 手动启动（不依赖脚本）

```bash
conda activate biomni_e1

# 推荐：统一入口 CLI（默认绑定 127.0.0.1，未知模式退出码 2）
python -m biochat.ui.cli                          # Streamlit → http://127.0.0.1:8501
python -m biochat.ui.cli --ui gradio              # Gradio   → http://127.0.0.1:7860

# 直接使用 streamlit 时务必显式回环绑定并配置访问码：
streamlit run biochat/ui/biochat_streamlit.py --server.address 127.0.0.1
```

> ⚠️ 直接 `streamlit run` 而不设置 `--server.address` 会监听所有网卡；
> 在未配置访问码且未显式确认的情况下，应用将拒绝启动。

#### Windows 环境

项目未提供原生 Windows 启动脚本（`start.sh` 为 Bash），推荐使用 **WSL2**，在 WSL 内按上述 macOS/Linux 步骤操作即可。若需原生运行，请手动执行：安装依赖 → 复制 `.env` → 运行 `streamlit run biochat/ui/biochat_streamlit.py`。

### 访问服务

| 界面 | 地址 | 说明 |
|------|------|------|
| **Streamlit UI** | http://localhost:8501 | ChatGPT 风格，推荐 |
| **Gradio UI** | http://localhost:7860 | 旧版（ProtChat 风格） |

## 🐍 Python 接口

### 服务层 API（推荐）

| 功能 | 方法 | 说明 |
|------|------|------|
| 全局服务单例 | `get_agent_service()` | 懒加载 + 缓存，避免重复初始化 |
| 初始化 | `svc.ensure_initialized()` | 首次调用时初始化 A1 Agent |
| 单次任务 | `svc.run_task(ChatRequest)` | 结构化输出（答案 / 工具调用 / 状态） |
| 流式任务 | `svc.run_task_stream(...)` | 事件流 + 进度回调，实时更新 UI |
| 健康检查 | `svc.health_check()` | 服务状态检查 |
| 资源释放 | `svc.shutdown()` | 关闭 Agent、释放资源 |

```python
from biochat.services.agent_service import get_agent_service
from biochat.schemas.chat import ChatRequest

svc = get_agent_service()
svc.ensure_initialized()

response = svc.run_task(ChatRequest(message="Explain the EGFR signaling pathway"))
print(response.answer)        # 清洗后的最终答案（Markdown）
print(response.tool_calls)    # 使用过的工具: ['genomics.query_gene', ...]
print(response.status)        # AgentStatus.COMPLETED
```

### A1 Agent 直接使用

```python
from biochat.agent import A1

# 初始化（首次运行自动下载 ~11GB 数据湖）
agent = A1(path='./data', llm='claude-sonnet-4-5')

# 执行生物医学任务
agent.go("Plan a CRISPR screen to identify genes that regulate T cell exhaustion")
agent.go("Perform scRNA-seq annotation and generate hypotheses about cell populations")
agent.go("Predict ADMET properties for CC(C)CC1=CC=C(C=C1)C(C)C(=O)O")

# 流式输出
for event in agent.go_stream("Design sgRNA sequences targeting TP53"):
    print(event)
```

### MCP 集成

```python
agent = A1()
agent.add_mcp(config_path="./mcp_config.yaml")
agent.go("Find FDA active ingredient information for ibuprofen")
```

详见 [MCP 集成文档](docs/mcp_integration.md)。

## 🎯 Agent 工作流程

```
用户任务
   │
   ▼
┌─────────────────────────────────────────────────┐
│  ① 规划 Planning                                  │
│     结合任务模板与知识库制定分步执行计划              │
└────────────────────────┬────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────┐
│  ② 工具检索 Tool Retrieval                        │
│     从 600+ 生物医学工具中检索本次任务所需函数        │
└────────────────────────┬────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────┐
│  ③ 代码执行 Code Execution                        │
│     生成并运行分析代码（查询数据库 / 统计分析 / 建模）  │
└────────────────────────┬────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────┐
│  ④ 观察与反思 Observation & Self-critique         │
│     检查中间结果、修正假设、必要时重新规划            │
└────────────────────────┬────────────────────────┘
                         │
                         └──────► 迭代直至输出最终解决方案
```

### 典型任务示例

| 任务类型 | 示例提问 | 主要工具域 |
|----------|----------|-----------|
| 🧫 CRISPR 筛选设计 | Plan a CRISPR screen to identify genes that regulate T cell exhaustion | `synthetic_biology` `genomics` |
| 🔬 scRNA-seq 注释 | Perform scRNA-seq annotation and generate hypotheses | `cell_biology` `genomics` |
| 💊 ADMET 预测 | Predict ADMET properties for CC(C)CC1=CC=C(C=C1)C(C)C(=O)O | `pharmacology` |
| 🧪 抗体设计 | Design antibody candidates against HER2 with developability | `antibody_design` |
| 📖 文献挖掘 | Search PubMed for recent advances in CAR-T therapy | `literature` |
| 🩺 罕见病诊断 | Analyze phenotypes and variants for diagnostic hypotheses | `database` `pathology` |

## 📁 项目结构

```
Biochat-main/
├── biochat/                                 # 核心包
│   ├── agent/                              # Agent 引擎
│   │   ├── a1.py                           # A1 Agent 主类（推理循环）
│   │   ├── workflow.py                     # 任务工作流编排
│   │   ├── self_critic.py                  # 自我反思与结果校验
│   │   ├── retrieval.py                    # 工具检索
│   │   ├── mcp_server.py                   # MCP 服务构建
│   │   ├── resource_manager.py             # 数据湖资源管理
│   │   └── conversation_exporter.py        # 对话导出
│   ├── llm/                                # LLM 层
│   │   ├── factory.py                      # 多供应商模型工厂
│   │   ├── source_detector.py              # API Key 自动检测
│   │   └── providers/                      # anthropic/openai/azure/gemini/
│   │                                       #   groq/bedrock/ollama/custom
│   ├── tool/                               # 600+ 生物医学工具
│   │   ├── genomics.py / pharmacology.py … # 20+ 子领域工具模块
│   │   ├── tool_registry.py                # 工具注册中心
│   │   ├── tool_description/               # 工具描述与目录（catalog.yaml）
│   │   ├── antibody_design/                # 抗体设计管线（扩散/对接/可开发性）
│   │   └── data/                           # 工具数据文件
│   ├── knowledge/                          # 知识库（know-how 文档 + 加载器）
│   │   └── docs/                           # sgRNA 设计指南、单细胞注释等
│   ├── services/                           # 服务层
│   │   ├── agent_service.py                # BioAgentService（懒加载/结构化输出）
│   │   └── session_service.py              # 多会话历史管理
│   ├── schemas/                            # 数据模型
│   │   └── chat.py                         # ChatRequest/ChatResponse
│   ├── prompts/                            # Prompt 工程
│   │   ├── system_prompt.py                # 系统提示词构建
│   │   └── task_templates.py               # 任务模板
│   ├── core/                               # 核心基础设施
│   │   ├── settings.py                     # 统一配置（环境变量）
│   │   ├── logging.py                      # 结构化日志
│   │   └── errors.py                       # 类型化异常
│   ├── environment/                        # 环境/软件目录管理
│   ├── model/                              # 检索器与资源选择器
│   ├── ui/                                 # 用户界面
│   │   ├── biochat_streamlit.py            # Streamlit UI（ChatGPT 风格）
│   │   ├── biochat_ui.py                   # Gradio UI
│   │   └── biochat_theme.py                # 设计系统
│   └── utils/                              # 工具函数（代码执行/PDF 导出/文本清洗）
├── biochat_env/                             # Conda 环境搭建（setup.sh / yml）
├── scripts/                                # 脚本（demo / 审计 / 冒烟测试）
├── docs/                                   # 文档（配置 / MCP / 构建）
├── tutorials/                              # 示例 Notebook
├── tests/                                  # 测试套件（pytest）
├── data/                                   # 数据湖（~11GB，首次运行下载）
├── figs/                                   # 图片资源
├── third_party/                            # 第三方代码归档（不在运行时路径）
├── .env.example                            # 环境变量模板
├── start.sh                                # 一键启动脚本
├── pyproject.toml                          # 项目配置（依赖、ruff 规则）
├── CONTRIBUTION.md                         # 贡献指南
├── license_info.md                         # 数据集许可说明
└── LICENSE                                 # Apache 2.0
```

## ⚙️ 配置说明

通过 `.env` 文件配置（`start.sh` 每次启动自动加载）：

```bash
# ── LLM API Key（按需填写） ────────────────────────────────
ANTHROPIC_API_KEY=your_anthropic_api_key_here    # Claude 模型
OPENAI_API_KEY=your_openai_api_key_here          # GPT 模型
# GEMINI_API_KEY=your_gemini_api_key_here         # Gemini
# GROQ_API_KEY=your_groq_api_key_here             # Groq

# ── 自定义模型服务（如 DeepSeek） ───────────────────────────
LLM_SOURCE=Custom
CUSTOM_MODEL_BASE_URL=https://api.deepseek.com/v1
CUSTOM_MODEL_API_KEY=your_custom_api_key_here

# ── LLM 配置 ──────────────────────────────────────────────
# BIOCHAT_LLM=deepseek-chat            # 模型名称
# BIOCHAT_SOURCE=Custom                # 供应商
# BIOCHAT_TEMPERATURE=0.7              # 生成温度
# BIOCHAT_TIMEOUT_SECONDS=600          # 代码执行超时（秒）
# BIOCHAT_USE_TOOL_RETRIEVER=true      # 启用工具检索
# BIOCHAT_COMMERCIAL_MODE=false        # 排除非商业许可数据集

# ── 数据路径 ──────────────────────────────────────────────
# BIOCHAT_DATA_PATH=./data             # 数据湖位置（~11GB）

# ── UI 访问码（可选） ───────────────────────────────────────
# BIOCHAT_ACCESS_CODE=<set-your-own-secret-code>      # 留空则不校验
```

### 环境变量一览

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `BIOCHAT_LLM` | LLM 模型名称 | `claude-sonnet-4-5` |
| `BIOCHAT_SOURCE` | LLM 供应商（Anthropic/OpenAI/Gemini/Groq/Custom…） | 自动检测 |
| `BIOCHAT_DATA_PATH` | 数据湖目录 | `./data` |
| `BIOCHAT_TEMPERATURE` | 生成温度 | `0.7` |
| `BIOCHAT_TIMEOUT_SECONDS` | 代码执行超时 | `600` |
| `BIOCHAT_USE_TOOL_RETRIEVER` | 启用工具检索 | `true` |
| `BIOCHAT_COMMERCIAL_MODE` | 排除非商业许可数据集 | `false` |
| `BIOCHAT_CUSTOM_BASE_URL` | 自定义模型 API 地址 | — |
| `BIOCHAT_CUSTOM_API_KEY` | 自定义模型 API Key | — |
| `BIOCHAT_ACCESS_CODE` | UI 访问码（逗号分隔） | 未设置 |
| `BIOCHAT_ALLOW_HOST_CODE_EXECUTION` | 允许在宿主机执行生成代码 | `false` |
| `BIOCHAT_ALLOW_UNAUTHENTICATED_REMOTE` | 显式允许无鉴权远程绑定 | `false` |
| `BIOCHAT_HOST` | 启动绑定地址（经 `biochat.ui.cli`） | `127.0.0.1` |

> 所有 `BIOCHAT_*` 变量均向后兼容 `BIOMNI_*` 旧命名。

## 🛡️ 安全模型

Biochat 默认配置面向个人工作站，遵循以下原则：

1. **代码执行默认关闭。** Agent 生成的 Python/R/Bash 代码不会在你的机器上执行，
   除非你显式设置 `BIOCHAT_ALLOW_HOST_CODE_EXECUTION=true`。该模式**不是沙箱**——
   它以历史兼容语义直接使用宿主机资源。访问码校验与超时控制不能替代操作系统级隔离；
   需要强隔离请自行使用容器/虚拟机并仅暴露必要权限。
2. **UI 默认只绑定回环地址 `127.0.0.1`。** 绑定到非回环地址需要满足其一：
   已配置 `BIOCHAT_ACCESS_CODE` 访问码；或显式承认风险
   （`BIOCHAT_ALLOW_UNAUTHENTICATED_REMOTE=true`）。否则启动即被拒绝。
3. **无内置凭据。** 仓库与安装产物中不包含任何默认访问码或 API Key；
   访问码比较使用常数时间比较以规避时序侧信道。
4. **版本唯一来源。** 项目与 UI 显示版本统一取自 `biochat.version.__version__`
   （当前 `v2.0.0`），wheel 元数据与之保持一致。

### 依赖附加组（extras）

| 附加组 | 内容 |
|--------|------|
| `streamlit` / `gradio` | 对应 UI 前端 |
| `providers` | Anthropic / OpenAI / Gemini / Groq / Bedrock / Ollama SDK |
| `full-tools` | 科学计算工具栈（matplotlib/scipy/torch/scanpy/nibabel/SimpleITK 等） |
| `dev` | pytest / ruff / build / pre-commit / mcp（CI 同款） |

### 支持的 LLM 供应商

| 供应商 | 代表模型 | 配置 |
|--------|----------|------|
| **Anthropic** | Claude Sonnet 4.5 / Opus 4 / Haiku 4.5 | `ANTHROPIC_API_KEY` |
| **OpenAI** | GPT-4 / GPT-4o / o1 / o3 | `OPENAI_API_KEY` |
| **Azure OpenAI** | GPT-4 部署 | `OPENAI_API_KEY` + `OPENAI_ENDPOINT` |
| **Google Gemini** | gemini-2.5-pro / flash | `GEMINI_API_KEY` |
| **Groq** | Llama / Mixtral | `GROQ_API_KEY` |
| **AWS Bedrock** | Claude / Llama / Titan | AWS 凭证 |
| **Ollama** | 本地模型（Llama / Qwen / DeepSeek…） | 本地 Ollama 服务 |
| **Custom** | 任意 OpenAI 兼容接口（DeepSeek / SGLang / vLLM…） | `CUSTOM_MODEL_BASE_URL` + `CUSTOM_MODEL_API_KEY` |

> 💡 **推荐**：Claude Sonnet 4.5 或 GPT-4 生物医学推理能力最佳；DeepSeek 是高性价比选择。

## 📝 开发指南

### 常用命令

```bash
# 测试
python -m pytest tests/                          # 运行全部测试

# 代码质量
ruff check .                                     # 静态检查
ruff format .                                    # 格式化
pre-commit install                               # 安装提交前钩子

# 项目审计
python scripts/audit_import_usage.py             # 第三方代码引用审计
python scripts/audit_runtime_tools.py            # 运行时工具审计
python scripts/smoke_test_antibody_hdock.py      # 抗体设计冒烟测试

# 构建文档
cd docs && make html                             # Sphinx 文档
```

### 贡献

欢迎贡献！详见 [CONTRIBUTION.md](CONTRIBUTION.md)，重点关注方向：

- 新增生物医学工具与分析函数
- 精选数据集与知识库
- 软件集成
- know-how 文档与实验方案指南
- UI/UX 改进

## ⚠️ 安全与合规

### 代码执行警告

**Biochat 会以完整系统权限执行 LLM 生成的代码**，请务必注意：

- 生产环境请**始终在隔离 / 沙箱环境中运行**（Docker、VM 等）
- Agent 可访问文件、网络和系统命令
- **切勿**在包含敏感数据或凭据的环境中运行
- **切勿**在未严格沙箱化的情况下暴露给不受信任的用户

### 临床免责声明

> **Biochat 是研究工具，不是医疗设备。** 禁止用于：
> - 自主临床决策
> - 直接患者诊疗或诊断
> - 未经专家审核的医疗建议生成
>
> **任何结果在应用于实际问题前，都必须经过领域专家验证。**

### 数据许可

- **学术用途**：全部数据集可用于非商业研究
- **商业用途**：设置 `BIOCHAT_COMMERCIAL_MODE=true` 自动排除非商业许可数据集
- **部署前**：请务必审阅 [license_info.md](license_info.md)

## 🐛 常见问题

### 首次启动为什么很慢？

首次运行需自动下载 **~11GB 精选生物医学数据湖**，后续启动不再重复下载。

### 可以跳过数据湖下载吗？

可以，传入 `expected_data_lake_files=[]` 给 `A1()` 即可跳过，但部分工具将不可用。

### 修改 .env 后不生效？

`start.sh` 每次启动都会重新加载 `.env`，重启服务即可生效。若手动启动，请确保在启动命令前 `source .env` 或使用 `python-dotenv`。

### 端口被占用怎么办？

```bash
# 查看占用端口的进程
lsof -i :8501    # Streamlit
lsof -i :7860    # Gradio

# 结束进程（替换 PID 为实际进程 ID）
kill -9 <PID>
```

### 推荐使用什么 LLM？

Claude Sonnet 4.5 或 GPT-4 的生物医学推理能力最佳；预算有限可选 DeepSeek（`LLM_SOURCE=Custom`）。

### Biochat 可以处理 PHI（受保护健康信息）吗？

**不可以。** Biochat 未针对 PHI 设计，请仅在隔离环境中使用。

## 📚 参考资源

- [配置文档](docs/configuration.md)
- [MCP 集成文档](docs/mcp_integration.md)
- [已知冲突](docs/known_conflicts.md)
- [LangChain 文档](https://python.langchain.com/)
- [MCP 协议](https://modelcontextprotocol.io/)
- [Streamlit 文档](https://docs.streamlit.io/)

## 📄 许可证

Biochat 采用 **Apache License 2.0**，详见 [LICENSE](LICENSE)。

> **注意**：部分集成工具、数据库与数据集可能附带更严格的商业许可，商业使用前请仔细审阅 [license_info.md](license_info.md)。Biochat 不对任何第三方代码、数据或算法主张所有权。
