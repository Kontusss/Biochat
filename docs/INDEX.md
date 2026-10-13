# Biochat 文档索引

> 本文件是 Biochat **全部文档的唯一导航入口**。
> 整理日期：2026-10-13 ｜ 覆盖：根目录文档、`docs/`、包内知识库文档、第三方来源说明。

---

## 建议阅读顺序

| 目的 | 读什么 |
|---|---|
| 了解项目 / 跑起来 | [`../README.md`](../README.md) —— 特性、技术栈、安装启动、配置、安全模型 |
| 查配置项 | [`configuration.md`](configuration.md) |
| 排查依赖冲突 | [`known_conflicts.md`](known_conflicts.md) |
| 接 MCP | [`mcp_integration.md`](mcp_integration.md) |
| 抗体设计管线 | [`antibody_design_hdock_docker.md`](antibody_design_hdock_docker.md) + [`FINAL_FUSION_STATUS.md`](FINAL_FUSION_STATUS.md) |
| 确认代码来源与许可 | [`../THIRD_PARTY_PROVENANCE.md`](../THIRD_PARTY_PROVENANCE.md) + [`../BIOCHAT_ORIGINAL_CONTRIBUTIONS.md`](../BIOCHAT_ORIGINAL_CONTRIBUTIONS.md) |

---

## 1. 项目入口

| 文档 | 用途 |
|---|---|
| [`../README.md`](../README.md) | 项目定位、核心特性、8 大 LLM 供应商、快速开始、环境变量一览、安全模型、常见问题 |
| [`../CONTRIBUTION.md`](../CONTRIBUTION.md) | 贡献指南（根目录，社区约定位置） |
| [`../license_info.md`](../license_info.md) | 数据源许可说明（学术/商业用途差异），README 多处引用 |

## 2. 根目录必须保留的文件

以下文件**按设计留在仓库根目录**，不要移动：

| 文件 | 为什么留在根目录 |
|---|---|
| `LICENSE` | 标准位置 |
| `THIRD_PARTY_PROVENANCE.md` | `check_safety.py` 的 `check_provenance()` 按根路径校验其存在 |
| `BIOCHAT_ORIGINAL_CONTRIBUTIONS.md` | 同上，`check_safety.py` 按根路径校验 |
| `CONTRIBUTION.md` | 社区约定位置，README 引用 |
| `license_info.md` | README 多处引用（19 处） |

> `check_safety.py` 还会校验 `third_party/biomni_upstream_archive/README.md`、
> `third_party/biomni_upstream_reference/LICENSE`、`reports/upstream_usage_audit.csv`、
> `reports/similarity_reduction_candidates.csv` 的存在；移动这些文件会直接让安全检查失败。

## 3. `docs/` 文档

| 文档 | 用途 |
|---|---|
| [`configuration.md`](configuration.md) | 配置指南：`.env` 各项、LLM 供应商、数据路径、UI 访问码 |
| [`mcp_integration.md`](mcp_integration.md) | MCP（Model Context Protocol）集成方式 |
| [`known_conflicts.md`](known_conflicts.md) | 已知依赖冲突（Groq / Bedrock SDK 与 `langchain-core` 1.x）与手动安装办法 |
| [`building_documentation.md`](building_documentation.md) | Sphinx 文档构建（配合 `Makefile` / `make.bat`） |
| [`antibody_design_hdock_docker.md`](antibody_design_hdock_docker.md) | 抗体设计管线的 HDOCK Docker 运行环境 |
| [`biochat_submission_notes.md`](biochat_submission_notes.md) | 竞赛提交说明：相对上游 Biomni 的增量 |
| [`FINAL_FUSION_STATUS.md`](FINAL_FUSION_STATUS.md) | Fusion Plan v1（3A–3D 阶段）完成状态表 |
| [`HER2_antibody_design_report.md`](HER2_antibody_design_report.md) | HER2/ERBB2 胞外域候选抗体设计完整报告 |
| [`DETAILS.md`](DETAILS.md) | 由 Detailer 工具生成的代码库通览（外部工具产物，供参考） |

### 3.1 设计文档（`docs/superpowers/`）

| 文档 | 用途 |
|---|---|
| [`superpowers/specs/2026-08-20-security-reliability-hardening-design.md`](superpowers/specs/2026-08-20-security-reliability-hardening-design.md) | 安全性与可靠性加固设计 |
| [`superpowers/plans/2026-08-20-security-reliability-hardening.md`](superpowers/plans/2026-08-20-security-reliability-hardening.md) | 对应的执行计划（分支 `fix/security-reliability-hardening`） |

### 3.2 Sphinx 文档源码

| 路径 | 说明 |
|---|---|
| `docs/source/index.rst`、`docs/source/conf.py` | Sphinx 配置与入口，构建产物 `docs/build/` 与 `docs/source/api/` 不入库 |

## 4. 包内知识库文档

| 文档 | 用途 |
|---|---|
| [`../biochat/knowledge/docs/sgRNA_design_guide.md`](../biochat/knowledge/docs/sgRNA_design_guide.md) | sgRNA 设计指南（供 Agent 检索的 know-how） |
| [`../biochat/knowledge/docs/single_cell_annotation.md`](../biochat/knowledge/docs/single_cell_annotation.md) | 单细胞注释指南 |

## 5. 环境与第三方

| 路径 | 说明 |
|---|---|
| [`../biochat_env/README.md`](../biochat_env/README.md) | Conda 环境搭建（`setup.sh` / `*.yml`，含 R 与 CLI 工具） |
| `../third_party/biomni_upstream_reference/` | 上游 Biomni 参考快照（含 LICENSE） |
| `../third_party/biomni_upstream_archive/` | 上游 Biomni 归档 |
| `../.worktrees/security-reliability-hardening/` | 独立工作树（分支 `fix/security-reliability-hardening`），已被 `.gitignore` 排除 |

---

## 6. 不入版本控制的内容

| 路径 | 体积 | 原因 |
|---|---|---|
| `movie/` | ~20 GB | 演示视频素材 |
| `Biochat.pptx` | 25 MB | 演示文稿 |
| `未命名文件夹.zip` | 25 MB | 临时压缩包 |
| `data/` | ~11 GB | 数据湖，首次运行自动下载 |
| `docs/build/`、`docs/source/api/` | — | Sphinx 构建产物 |
| `.worktrees/` | — | Git worktree 检出 |
| `outputs/`、`antibody_design_results*/` | — | 运行时分析产物 |

> 完整规则见 [`../.gitignore`](../.gitignore)。

---

## 7. 文档维护约定

1. 根目录只保留 README 与社区/合规必需文件（见第 2 节）；其余说明性 Markdown 归入 `docs/`。
2. **移动文档前必须核查引用**：`check_safety.py` 按根路径校验来源文件，README 也大量引用 `license_info.md`。
3. 新增文档后在同一提交中补进本索引。
4. 涉及结论或性能的描述必须标明来源与边界，避免把集成能力表述为已验证的科研结果。
5. 数据许可相关改动需同步更新 [`license_info.md`](../license_info.md) 与 [`THIRD_PARTY_PROVENANCE.md`](../THIRD_PARTY_PROVENANCE.md)。
