#!/usr/bin/env python3
"""Biochat Agent 经典指标评测 (忠实多选题版): DbQA / SeqQA / HLE。

评测格式对齐上游 Biomni 参考实现 (third_party/biomni_upstream_reference):
  - DbQA / SeqQA 为多选题: 选项 = shuffle(distractors + [ideal] + ["Insufficient information..."])
  - 金标准 = 正确选项字母; 打分按字母匹配
  - HLE 为多选题 (题目自带 Answer Choices), 金标准为字母

覆盖 Agent 评测中最经典的几类指标:
  1. 准确率 Accuracy       — 答案与金标准匹配的题目占比 (任务质量)
  2. 任务成功率 Success    — 状态 COMPLETED 且产出非空答案的任务占比 (完成能力)
  3. 工具调用率 Tool Rate  — 至少调用过 1 次工具的任务占比 (自主性 / 工具使用)
  4. 平均工具调用数 Steps  — 平均每次任务调用工具次数 (步骤效率)
  5. 平均耗时 Latency      — 平均每次任务耗时秒数 (响应效率)
  6. 错误率 Error Rate     — ERROR / TIMEOUT 任务占比 (稳定性)

用法:
    python scripts/eval_agent_metrics.py --quick     # 每基准 1 题
    python scripts/eval_agent_metrics.py --subset 5  # 每基准 5 题 (默认)
    python scripts/eval_agent_metrics.py --all       # 全量
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from biochat.core.settings import biochat_settings
from biochat.schemas.chat import AgentStatus, ChatRequest
from biochat.services.agent_service import get_agent_service

# ═══════════════════════════════════════════════════════════════
# 氨基酸命名归一化 (1字母 / 3字母 / 全名)
# ═══════════════════════════════════════════════════════════════
AA_FULL = {
    "A": "Alanine", "R": "Arginine", "N": "Asparagine", "D": "Aspartic acid",
    "C": "Cysteine", "Q": "Glutamine", "E": "Glutamic acid", "G": "Glycine",
    "H": "Histidine", "I": "Isoleucine", "L": "Leucine", "K": "Lysine",
    "M": "Methionine", "F": "Phenylalanine", "P": "Proline", "S": "Serine",
    "T": "Threonine", "W": "Tryptophan", "Y": "Tyrosine", "V": "Valine",
}
AA_3LETTER = {
    "A": "Ala", "R": "Arg", "N": "Asn", "D": "Asp", "C": "Cys", "Q": "Gln",
    "E": "Glu", "G": "Gly", "H": "His", "I": "Ile", "L": "Leu", "K": "Lys",
    "M": "Met", "F": "Phe", "P": "Pro", "S": "Ser", "T": "Thr", "W": "Trp",
    "Y": "Tyr", "V": "Val",
}
AA_CANON = {}
for _one, _full in AA_FULL.items():
    AA_CANON[_one.upper()] = _full
    AA_CANON[AA_3LETTER[_one].lower()] = _full
    AA_CANON[AA_3LETTER[_one].upper()] = _full
    AA_CANON[_full.lower()] = _full
    AA_CANON[_full] = _full


def normalize_aa(value: str) -> str:
    """Normalize any amino-acid representation to the canonical full name."""
    v = str(value).strip()
    if not v:
        return v
    if len(v) == 1 and v.upper() in AA_CANON:
        return AA_CANON[v.upper()]
    if v.lower() in AA_CANON:
        return AA_CANON[v.lower()]
    return v


# ═══════════════════════════════════════════════════════════════
# 基准加载 / 多选题构造 (对齐 upstream lab_bench.py)
# ═══════════════════════════════════════════════════════════════

def load_benchmark(name: str) -> list[dict]:
    base = Path(biochat_settings.data_path) / "biomni_data" / "benchmark"
    if name == "DbQA":
        p = base / "DbQA" / "train-00000-of-00001_test.parquet"
        if not p.exists():
            p = base / "DbQA" / "train-00000-of-00001_sampled.parquet"
        df = pd.read_parquet(p)
    elif name == "SeqQA":
        p = base / "SeqQA" / "train-00000-of-00001_test.parquet"
        if not p.exists():
            p = base / "SeqQA" / "train-00000-of-00001_sampled.parquet"
        df = pd.read_parquet(p)
    elif name == "HLE":
        df = pd.read_parquet(base / "hle" / "test_sampled_biology_medicine.parquet")
    else:
        raise ValueError(name)
    return df.to_dict("records")


_TERSE = False  # set via --terse: model outputs only the answer letter
_TERSE_HINT = ("\nIMPORTANT: Do NOT write any explanation, analysis or reasoning. "
               "Only output the answer letter, prefixed with FINAL: (e.g. FINAL: B).")


def build_mcq(name: str, item: dict, index: int = 0) -> tuple[str, str]:
    """Return (prompt, gold_letter) in the reference multiple-choice format."""
    if name == "HLE":
        return (
            f"{item['question']}\n\n"
            "Put your final answer as the LAST line of your response, prefixed "
            "with FINAL: (exactly one letter, e.g. FINAL: B)."
            + (_TERSE_HINT if _TERSE else ""),
            str(item["answer"]).strip().upper(),
        )
    # Deterministic but varied shuffle per item (matches reference seeding spirit)
    np.random.seed(42 + index)
    distractors = list(item["distractors"]) if not isinstance(item["distractors"], str) else [item["distractors"]]
    options = list(distractors) + [item["ideal"], "Insufficient information to answer the question."]
    options = np.random.permutation(options).tolist()
    gold_letter = chr(ord("A") + options.index(item["ideal"]))
    options_text = "\n".join(f"{chr(ord('A') + i)}.{opt}" for i, opt in enumerate(options))
    prompt = (
        "The following is a multiple choice question about biology.\n"
        "Please answer by responding with the letter of the correct answer.\n\n"
        f"Question: {item['question']}\n"
        f"Options:\n{options_text}\n\n"
        "Put your final answer as the LAST line of your response, prefixed with FINAL: "
        "(exactly one letter, e.g. FINAL: B)."
        + (_TERSE_HINT if _TERSE else "")
    )
    return prompt, gold_letter


def extract_answer(text: str) -> str:
    """Extract the answer from the agent's response.

    Prefers a single MCQ option letter; falls back to the FINAL: token, then
    to a letter near 答案/answer markers, then to the whole text.
    """
    if not text:
        return ""
    t = text.strip()
    # 1. Explicit FINAL: marker
    m = re.search(r"FINAL:\s*([A-Fa-f])", t)
    if m:
        return m.group(1).upper()
    # 2. Letter near explicit answer markers (Chinese or English)
    m = re.search(
        r"(?:正确答案|答案为|答案是|正确选项|选择|选项|对应|correct answer|answer is|answer|choose)[^A-Fa-f]{0,20}?([A-Fa-f])\b",
        t,
    )
    if m:
        return m.group(1).upper()
    # 3. Single letter on the last non-empty line
    last_line = next((ln.strip() for ln in reversed(t.splitlines()) if ln.strip()), "")
    if re.fullmatch(r"[A-Fa-f]", last_line):
        return last_line.upper()
    # 4. Whole text (open-answer fallback, e.g. AA normalization path)
    return t


def score_item(name: str, item: dict, pred: str, gold: str) -> bool:
    if name == "HLE":
        return pred.strip().upper() == gold
    # 多选题: 字母直接比较
    if re.fullmatch(r"[A-F]", pred.strip().upper()):
        return pred.strip().upper() == gold
    # 兜底: 模型可能输出基因名/氨基酸名 — 与理想答案做归一化比较
    if name == "SeqQA":
        return normalize_aa(pred) == normalize_aa(item["ideal"])
    return pred.strip().upper() == str(item["ideal"]).strip().upper()


# ═══════════════════════════════════════════════════════════════
# 指标汇总
# ═══════════════════════════════════════════════════════════════

def summarize_metrics(name: str, rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {"n": 0}
    acc = sum(1 for r in rows if r["ok"]) / n
    success = sum(1 for r in rows if r["status"] == AgentStatus.COMPLETED and r["has_answer"]) / n
    tool_rate = sum(1 for r in rows if r["n_tools"] > 0) / n
    exec_rate = sum(1 for r in rows if r.get("n_exec", 0) > 0) / n
    steps = sum(r["n_tools"] for r in rows) / n
    execs = sum(r.get("n_exec", 0) for r in rows) / n
    latency = sum(r["seconds"] for r in rows) / n
    error_rate = sum(1 for r in rows if r["status"] in (AgentStatus.ERROR, AgentStatus.TIMEOUT)) / n
    top_tools = Counter(t for r in rows for t in r["tools"]).most_common(5)
    return {
        "n": n,
        "accuracy": round(acc * 100, 1),
        "success_rate": round(success * 100, 1),
        "tool_use_rate": round(tool_rate * 100, 1),
        "execution_rate": round(exec_rate * 100, 1),
        "avg_tool_calls": round(steps, 2),
        "avg_executions": round(execs, 2),
        "avg_seconds": round(latency, 1),
        "error_rate": round(error_rate * 100, 1),
        "top_tools": [{"tool": t, "calls": c} for t, c in top_tools],
    }


def select_items(name: str, items: list[dict], n: int, stratified: bool) -> list[dict]:
    """Select n items: first-n (default) or stratified across subtasks."""
    if n >= len(items) or not stratified:
        return items[:n]
    # round-robin across subtask types for a representative slice
    groups: dict[str, list[dict]] = {}
    for it in items:
        groups.setdefault(str(it.get("subtask") or "other"), []).append(it)
    picked: list[dict] = []
    keys = list(groups.keys())
    gi = 0
    while len(picked) < n and any(groups.values()):
        if not groups[keys[gi % len(keys)]]:
            gi += 1
            continue
        picked.append(groups[keys[gi % len(keys)]].pop(0))
        gi += 1
    return picked


def checkpoint(out_path: Path, result: dict) -> None:
    """Write partial results so a long run is not lost on failure."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    tmp.replace(out_path)


def load_checkpoint(out_path: Path) -> list[dict]:
    """Load previously completed rows (non-error) for resume support."""
    try:
        d = json.loads(out_path.read_text())
        rows = d.get("details", {}).get("items", [])
        return [r for r in rows if r.get("status") != "error"]
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════
# 并行评测 (--workers N): 每个 worker 进程独立初始化 Agent
# ═══════════════════════════════════════════════════════════════

_QTIMEOUT = 300  # per-question wall-clock cap (seconds), set via --qtimeout


def _run_one(name: str, gi: int, item: dict) -> dict:
    """Run a single question and return the result row."""
    prompt, gold = build_mcq(name, item, index=gi)
    t0 = time.time()
    import signal

    def _alarm(*_):
        raise TimeoutError(f"question exceeded {_QTIMEOUT}s")

    signal.signal(signal.SIGALRM, _alarm)
    signal.setitimer(signal.ITIMER_REAL, _QTIMEOUT)
    try:
        resp = get_agent_service().run_task(ChatRequest(message=prompt))
        seconds = round(time.time() - t0, 1)
        answer = getattr(resp, "answer", "") or ""
        tool_calls = getattr(resp, "tool_calls", None) or []
        n_exec = getattr(resp, "raw_log", "").count("<observation>")
        pred = extract_answer(answer)
        ok = score_item(name, item, pred, gold)
        row = {
            "benchmark": name, "id": item.get("id"),
            "status": resp.status.value,
            "has_answer": bool(answer.strip()),
            "ok": ok, "gold": gold,
            "pred": pred[:60], "ideal": str(item.get("ideal") or item.get("answer"))[:40],
            "n_tools": len(tool_calls), "tools": tool_calls[:8],
            "n_exec": n_exec,
            "seconds": seconds,
        }
        print(f"[{name}] {str(item.get('id'))[:8]} ok={ok} gold={gold} pred={pred[:15]!r} ({seconds}s)",
              flush=True)
        return row
    except Exception as e:  # noqa: BLE001
        print(f"[{name}] {str(item.get('id'))[:8]} ERROR: {e}", flush=True)
        return {"benchmark": name, "id": item.get("id"), "status": "error",
                "has_answer": False, "ok": False, "gold": gold, "pred": "",
                "ideal": str(item.get("ideal") or item.get("answer"))[:40],
                "n_tools": 0, "tools": [], "n_exec": 0,
                "seconds": round(time.time() - t0, 1), "error": str(e)[:200]}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def _worker_run(chunk: list[tuple]) -> list[dict]:
    """Worker entry: run a chunk of (bench, global_index, item) tasks."""
    svc = get_agent_service()
    svc.ensure_initialized()
    return [_run_one(name, gi, item) for name, gi, item in chunk]


def _run_parallel(args, names: list[str], done_keys: set, prev_rows: list[dict],
                  out_path: Path) -> int:
    import multiprocessing as mp

    tasks: list[tuple] = []
    for name in names:
        items = load_benchmark(name)
        n = 1 if args.quick else (len(items) if args.all else (args.subset or 5))
        items = select_items(name, items, n, args.stratified)
        for gi, it in enumerate(items):
            if (name, str(it.get("id"))) not in done_keys:
                tasks.append((name, gi, it))
    print(f"并行评测: 待跑 {len(tasks)} 题, {args.workers} workers", flush=True)

    ctx = mp.get_context("spawn")
    chunks = [tasks[i::args.workers] for i in range(args.workers)]
    rows: list[dict] = []
    with ctx.Pool(args.workers) as pool:
        for chunk_rows in pool.imap_unordered(_worker_run, chunks):
            rows.extend(chunk_rows)

    # 合并断点数据: 新结果覆盖旧记录, 保留未重跑的已完成记录
    final_rows = {(r.get("benchmark"), str(r.get("id"))): r for r in prev_rows}
    for r in rows:
        final_rows[(r.get("benchmark"), str(r.get("id")))] = r
    all_rows = list(final_rows.values())
    per_bench = {name: summarize_metrics(name, [r for r in all_rows if r["benchmark"] == name])
                 for name in names}
    overall = summarize_metrics("overall", all_rows)
    result = {"overall": overall, "per_benchmark": per_bench, "details": {"items": all_rows}}
    checkpoint(out_path, result)
    _print_summary(names, per_bench, overall)
    return 0


def _print_summary(names, per_bench, overall) -> None:
    print("\n" + "=" * 78)
    print(f"{'基准':<10}{'n':>4}{'准确率':>8}{'成功率':>8}{'工具率':>8}{'平均步骤':>9}{'平均耗时':>9}{'错误率':>8}")
    print("-" * 78)
    for name in names + ["overall"]:
        m = per_bench[name] if name != "overall" else overall
        print(f"{name:<10}{m['n']:>4}{m['accuracy']:>7}%{m['success_rate']:>7}%"
              f"{m['tool_use_rate']:>7}%{m['avg_tool_calls']:>9}{m['avg_seconds']:>8}s{m['error_rate']:>7}%")
    print("=" * 78)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subset", type=int, default=None)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--stratified", action="store_true",
                    help="sample across subtask types instead of first-n")
    ap.add_argument("--resume", action="store_true",
                    help="skip questions already completed in the output file")
    ap.add_argument("--workers", type=int, default=1,
                    help="run with N parallel worker processes (each own agent instance)")
    ap.add_argument("--qtimeout", type=int, default=300,
                    help="per-question wall-clock cap in seconds (default 300)")
    ap.add_argument("--terse", action="store_true",
                    help="low-token mode: model outputs only the answer letter")
    ap.add_argument("--out", default="reports/agent_metrics_results.json")
    args = ap.parse_args()
    global _QTIMEOUT, _TERSE
    _QTIMEOUT = args.qtimeout
    _TERSE = args.terse

    names = ["DbQA", "SeqQA", "HLE"]
    out_path = Path(args.out)
    prev_rows = load_checkpoint(out_path) if args.resume else []
    done_keys = {(r.get("benchmark"), str(r.get("id"))) for r in prev_rows}
    if done_keys:
        print(f"断点续跑: 已有 {len(done_keys)} 题完成, 将跳过", flush=True)

    if args.workers and args.workers > 1:
        return _run_parallel(args, names, done_keys, prev_rows, out_path)

    svc = get_agent_service()
    svc.ensure_initialized()
    print("Agent 服务已初始化", flush=True)

    final_rows: dict[tuple, dict] = {(r.get("benchmark"), str(r.get("id"))): r for r in prev_rows}

    per_bench: dict[str, dict] = {}
    for name in names:
        items = load_benchmark(name)
        n = 1 if args.quick else (len(items) if args.all else (args.subset or 5))
        items = select_items(name, items, n, args.stratified)
        todo = [it for it in items if (name, str(it.get("id"))) not in done_keys]
        print(f"\n=== {name}: 待跑 {len(todo)} 题 (共 {len(items)}) ===", flush=True)
        rows: list[dict] = []
        for i, item in enumerate(todo):
            prompt, gold = build_mcq(name, item, index=i)
            t0 = time.time()
            try:
                resp = svc.run_task(ChatRequest(message=prompt))
                seconds = round(time.time() - t0, 1)
                answer = getattr(resp, "answer", "") or ""
                tool_calls = getattr(resp, "tool_calls", None) or []
                n_exec = getattr(resp, "raw_log", "").count("<observation>")
                pred = extract_answer(answer)
                ok = score_item(name, item, pred, gold)
                rows.append({
                    "benchmark": name, "id": item.get("id"),
                    "status": resp.status.value,
                    "has_answer": bool(answer.strip()),
                    "ok": ok, "gold": gold,
                    "pred": pred[:60], "ideal": str(item.get("ideal") or item.get("answer"))[:40],
                    "n_tools": len(tool_calls), "tools": tool_calls[:8],
                    "n_exec": n_exec,
                    "seconds": seconds,
                })
                print(
                    f"  [{i+1}/{len(todo)}] status={resp.status.value} ok={ok} "
                    f"gold={gold} pred={pred[:25]!r} ideal={str(item.get('ideal') or item.get('answer'))[:20]!r} "
                    f"tools={len(tool_calls)} ({seconds}s)",
                    flush=True,
                )
            except Exception as e:  # noqa: BLE001
                rows.append({"benchmark": name, "id": item.get("id"), "status": "error",
                             "has_answer": False, "ok": False, "gold": gold, "pred": "",
                             "ideal": str(item.get("ideal") or item.get("answer"))[:40],
                             "n_tools": 0, "tools": [], "seconds": round(time.time() - t0, 1),
                             "error": str(e)[:200]})
                print(f"  [{i+1}/{len(todo)}] ERROR: {e}", flush=True)
        # 合并断点数据: 本轮结果覆盖旧记录, 保留已完成的旧记录
        for r in rows:
            final_rows[(name, str(r.get("id")))] = r
        bench_rows = [r for (bn, _), r in final_rows.items() if bn == name]
        per_bench[name] = summarize_metrics(name, bench_rows)
        m = per_bench[name]
        # 断点续写: 每个基准完成后保存部分结果
        all_rows = [r for (bn, _), r in final_rows.items()]
        checkpoint(out_path, {
            "overall": summarize_metrics("overall", all_rows),
            "per_benchmark": per_bench,
            "details": {"items": all_rows},
        })
        print(
            f"  -> acc={m['accuracy']}% success={m['success_rate']}% "
            f"tool_use={m['tool_use_rate']}% steps={m['avg_tool_calls']} "
            f"latency={m['avg_seconds']}s err={m['error_rate']}%",
            flush=True,
        )

    all_rows = [r for (bn, _), r in final_rows.items()]
    overall = summarize_metrics("overall", all_rows)
    result = {"overall": overall, "per_benchmark": per_bench,
              "details": {"items": all_rows}}
    checkpoint(out_path, result)
    print(f"\n结果已写入: {out_path}", flush=True)

    # ── 终端汇总表 ──────────────────────────────────────────────
    _print_summary(names, per_bench, overall)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
