# Biochat Agent 端到端基准评测报告

评测日期: 2026-08-30
评测方式: 服务层 run_task 真实调用, DeepSeek-chat (temperature=0.7), minimal 工具配置 (57 工具)
评测脚本: scripts/eval_agent_benchmarks.py
基准数据: data/biomni_data/benchmark/ (DbQA 65 题 / SeqQA 75 题 / HLE 52 题)

## 结果汇总 (每基准前 3 题)

| 基准 | 准确率 | 平均工具调用 | 平均耗时 | 任务类型 |
|---|---|---|---|---|
| DbQA | 0/3 (0%) | 0.0 | 22s | 数据库问答(需查 DisGeNET/OMIM 等) |
| SeqQA | 0/3 (0%) | 1.0 | 44s | 序列分析(需 ORF 计算) |
| HLE | 2/3 (66.7%) | 0.0 | 15s | 生物医学知识选择 |

## 关键发现

### 发现 1: DbQA 工具调用为 0 — 真正的短板
数据库问答任务中, Agent 全程未调用任何 database 工具, 直接凭 LLM 常识作答 (猜出 PDE6C/TGFBI, 与金标准 NBAS/IL10/IL6 不符)。
- 工具实际已注册: minimal 配置含 biochat.tool.database 40 个工具
- 工具检索器已启用: use_tool_retriever=True, ResourceSelector 在运行
- 结论: **检索→调用链路存在断点**——可能是检索器未选中工具, 或模型在无显式引导时倾向直接作答

### 发现 2: SeqQA 工具调用路径是通的, 但答案提取有偏差
3 题全部正确调用了 annotate_open_reading_frames 工具, 说明**工具执行链路正常**。但提取答案失败 (pred=L/P/C, gold=Gly/Proline/Cysteine) —— 需要确认工具返回与提取逻辑的匹配。

### 发现 3: HLE 表现正常
纯知识问答 2/3, 符合该基准难度预期。

## 建议下一步
1. 在 DbQA 提示词中显式引导 "先检索并调用数据库工具", 复测工具调用率
2. 增大样本量 (--subset 10 或 --all) 得到更稳定的准确率
3. 对比 full 工具配置 (226 工具) 与 minimal 的差异
4. 若配置 Claude/OpenAI key 后重测, 可与 DeepSeek 结果对比模型影响
