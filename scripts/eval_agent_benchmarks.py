#!/usr/bin/env python3
"""Biochat Agent 端到端评测: DbQA / SeqQA / HLE。

通过服务层 run_task 获取结构化答案 + 工具调用记录, 输出:
  - 每基准准确率
  - 平均工具调用次数 (证明 Agent 真实调用工具解题)
  - 平均耗时

用法:
    python scripts/eval_agent_benchmarks.py --quick
    python scripts/eval_agent_benchmarks.py --subset 5
    python scripts/eval_agent_benchmarks.py --all
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from biochat.services.agent_service import get_agent_service
from biochat.schemas.chat import ChatRequest
from biochat.core.settings import biochat_settings


def load_benchmark(name: str) -> list[dict]:
    base = Path(biochat_settings.data_path) / "biomni_data" / "benchmark"
    if name == "DbQA":
        df = pd.read_parquet(base / "DbQA" / "train-00000-of-00001_sampled.parquet")
    elif name == "SeqQA":
        df = pd.read_parquet(base / "SeqQA" / "train-00000-of-00001_sampled.parquet")
    elif name == "HLE":
        df = pd.read_parquet(base / "hle" / "test_sampled_biology_medicine.parquet")
    else:
        raise ValueError(name)
    return df.to_dict("records")


def build_prompt(name: str, item: dict) -> str:
    if name == "HLE":
        return f"{item['question']}\n\nAnswer with a single letter (A-E) in your final line."
    return (
        f"{item['question']}\n\n"
        f"Use the available bioinformatics tools and data to solve this precisely. "
        f"Put your final answer as the LAST line of your response, prefixed with FINAL: "
        f"(exactly one answer, no list)."
    )


def extract_answer(text: str) -> str:
    if not text:
        return ""
    m = re.search(r"FINAL:\s*([A-Za-z0-9\-]+)", text)
    if m:
        return m.group(1)
    return text.strip()


def score_item(name: str, item: dict, pred: str) -> bool:
    if name == "HLE":
        return pred.strip().upper() == str(item["answer"]).strip().upper()
    gold = str(item["ideal"]).strip()
    return pred == gold or gold.lower() in pred.lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subset", type=int, default=None)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", default="reports/agent_benchmark_results.json")
    args = ap.parse_args()

    names = ["DbQA", "SeqQA", "HLE"]
    svc = get_agent_service()
    svc.ensure_initialized()
    print("Agent 服务已初始化", flush=True)

    results: dict = {}
    for name in names:
        items = load_benchmark(name)
        n = 1 if args.quick else (len(items) if args.all else (args.subset or min(5, len(items))))
        items = items[:n]
        correct, total, tool_total, time_total, details = 0, 0, 0, 0.0, []
        print(f"\n=== {name}: {n} 题 ===", flush=True)
        for i, item in enumerate(items):
            t0 = time.time()
            try:
                resp = svc.run_task(ChatRequest(message=build_prompt(name, item)))
                t = time.time() - t0
                answer = getattr(resp, "answer", "") or ""
                tool_calls = getattr(resp, "tool_calls", None) or []
                pred = extract_answer(answer)
                gold = item.get("answer") or item.get("ideal")
                ok = score_item(name, item, pred)
                correct += ok
                total += 1
                tool_total += len(tool_calls)
                time_total += t
                details.append({"id": item.get("id"), "pred": pred[:50], "gold": str(gold)[:50], "ok": ok, "n_tools": len(tool_calls), "tools": tool_calls[:5], "seconds": round(t, 1)})
                print(f"  [{i+1}/{n}] ok={ok} pred={pred[:30]!r} gold={str(gold)[:30]!r} tools={len(tool_calls)} ({t:.0f}s)", flush=True)
            except Exception as e:
                print(f"  [{i+1}/{n}] ERROR: {e}", flush=True)
        acc = 100.0 * correct / total if total else 0.0
        results[name] = {
            "n": total, "correct": correct, "accuracy": round(acc, 1),
            "avg_tool_calls": round(tool_total / total, 2) if total else 0,
            "avg_seconds": round(time_total / total, 1) if total else 0,
            "details": details,
        }
        print(f"  {name}: 准确率 {correct}/{total} = {acc:.1f}% | 平均工具调用 {results[name]['avg_tool_calls']} | 平均 {results[name]['avg_seconds']}s", flush=True)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n结果已写入: {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
