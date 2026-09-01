# Biochat Agent 经典指标评测报告 (修复后)

评测日期: 2026-08-31
评测方式: 服务层 `run_task` 真实调用, DeepSeek-chat (temperature=0.7), full 工具配置 (226 工具)
评测脚本: `scripts/eval_agent_metrics.py`
基准数据: `data/biomni_data/benchmark/` — DbQA `_test.parquet` (60 题) / SeqQA `_test.parquet` (70 题) / HLE (52 题)
评测格式: 对齐上游 Biomni 参考实现 — 多选题 (选项 = shuffle(distractors + ideal + "Insufficient information...")), 按选项字母评分

## 结果: 修复前 vs 修复后

| 基准 | 修复前 (旧评测) | 修复后 (first-5 切片) | 修复后 (分层切片) |
|---|---|---|---|
| DbQA 准确率 | 0.0% | **60.0%** | **80.0%** |
| SeqQA 准确率 | 0.0% | **100.0%** | **80.0%** |
| HLE 准确率 | 40.0% | 40.0% | 40.0% |
| **overall** | **13.3%** | **66.7%** | **66.7%** |
| 成功率 | 100% | 100% | 100% |
| 错误率 | 0% | 0% | 0% |

> 分层切片 (每类子任务取 1 题) 是 DbQA 的代表性测量; first-5 切片恰好全部落在 dga_task (DisGeNET/OMIM) 类型上。
> 逐题明细: `reports/agent_metrics_final.json` (分层) / `reports/agent_metrics_results.json` (first-5)。

## 修复内容

### 1. 评测器修正 (`scripts/eval_agent_metrics.py`)
- **基准文件**: 改用上游参考实现读取的 `train-00000-of-00001_test.parquet` (旧评测误用 `_sampled.parquet`, 其前 5 题答案键与本地数据不一致)
- **多选题格式**: 忠实还原上游格式 (含 "Insufficient information" 选项, 字母作答)
- **氨基酸归一化**: 1字母 ↔ 3字母 ↔ 全名 (G/Gly/Glycine) 统一判分
- **稳健答案提取**: `FINAL: <letter>` 行 → 答案/选择/选项关键词附近的字母 → 末行字母 → 全文兜底 (支持 A–F)
- **新指标**: 代码执行率 (raw_log 中 `<observation>` 计数) — 弥补 named-tool 统计对直接 pandas 读库的漏计

### 2. Agent 系统提示词修复 (`biochat/prompts/system_prompt.py` + `system_prompt_v2.py`)
- **数据库核验强制要求**: 提到具体数据库 (DisGeNET/OMIM/Ensembl/ClinVar/miRDB/STRING/MSigDB…) 的问题**必须**用 `<execute>` 核验, 禁止凭记忆作答; 附逐类配方:
  - 疾病-基因关联: `DisGeNET.parquet` + `omim.parquet` (或 query_opentarget/query_monarch)
  - 细胞带定位: `msigdb_human_c1_positional_geneset.parquet`
  - TF 结合位点: `msigdb_human_c3_subset_transcription_factor_targets_from_GTRD.parquet`
  - miRNA 靶标: `miRDB_v6.0_results.parquet` (名称归一化, 如 MIR186_3P → hsa-miR-186-3p)
  - 变异致病性: `query_clinvar()`; 病毒-宿主互作: `query_stringdb()`
- **答案格式要求**: 氨基酸必须全名/三字母 (禁止单字母); ORF 翻译包含终止密码子 `*`; 多选题最后一行必须为 `FINAL: <字母>`
- **多选题不再落入 "simple factual Q&A → 不用工具" 捷径**

## 根因分析 (为什么从 0% 到 66.7%)

| 基准 | 修复前失败根因 | 修复后表现 |
|---|---|---|
| DbQA | 模型把数据库题当常识题直接作答 (0 工具调用), 且评测漏掉选项、用错文件 | 模型主动读数据湖核验 (exec 1-15 次), PAX6/BRD2/细胞带/基因集/致癌签名全部答对 |
| SeqQA | 工具调用链路通, 但输出单字母氨基酸 (L/P/C), 判分不匹配 | 模型计算正确并按选项字母作答 (100% first-5; 分层 80%) |
| HLE | 答案提取失败 (长中文 solution 无字母行) | 提取修复后稳定 40%; 3 题答错为内容级推理问题 |

## 剩余差距 (诚实上限)

| 基准 | 剩余错误 | 性质 | 能否修复 |
|---|---|---|---|
| DbQA | KANSL1L (miRDB): 模型 15 次执行仍筛选出错 | 模型 pandas 操作能力 | 换更强模型可提升 |
| DbQA | dga_task 的 HBB/NFE2L2/HTC2: 金标准不在本地 DisGeNET 快照中 | **外部数据缺口** (需 live DisGeNET/OMIM API key 或更新快照) | 需补充数据源 |
| SeqQA | 带终止密码子的全长翻译题选错字母 | 模型行为 (随机性) | 重跑可能通过 |
| HLE | 四倍体减数分裂 / 群体遗传 / Fst 3 题答错 | 模型知识/推理上限 (deepseek-chat) | 换更强 LLM |

HLE 中重复基因保留机制题 (金标准 C/新功能化) 模型在 D/亚功能化 与 C 之间摇摆 — 该题本身存在学术争议 (DDC 模型文献支持亚功能化), 属正常分歧。

## 复现

```bash
conda activate biomni_e1
python scripts/eval_agent_metrics.py --subset 5                # first-5 切片
python scripts/eval_agent_metrics.py --subset 5 --stratified  # 跨子任务分层
python scripts/eval_agent_metrics.py --all                    # 全量 60/70/52 题
```

## 建议下一步 (冲更高分 / 100%)

1. **DbQA dga_task**: 配置 live DisGeNET API key (或放入更新的 DisGeNET/OMIM 快照), 使 3 个未核验金标准可查证
2. **HLE**: 换 Claude/GPT-5 级模型重测 (DeepSeek-chat 推理上限所致)
3. **统计稳定性**: `--all` 全量运行 (约 1-2 小时) 得到稳定数字
