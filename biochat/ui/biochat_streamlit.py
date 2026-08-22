"""
Biochat Streamlit UI — ChatGPT-style biomedical AI chat.

A polished, modern chat interface powered by the Biochat engine through
the BioAgentService layer.  All agent logic is delegated to the service;
this module handles only rendering and user interaction.

Launch
------
    streamlit run biochat/ui/biochat_streamlit.py
"""

from __future__ import annotations

import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure `biochat` is importable regardless of cwd.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from biochat.ui.sanitize import sanitize_visible_text, render_trace_event

# ═══════════════════════════════════════════════════════════════════
# Page configuration
# ═══════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Biochat — Biomedical AI Agent",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════════
# CSS — ChatGPT-inspired design system with light/dark support
# ═══════════════════════════════════════════════════════════════════

BIOCHAT_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Design tokens ────────────────────────────────────────── */
:root {
  --bc-bg: #f9fafb;
  --bc-sidebar-bg: #f3f4f6;
  --bc-card-bg: #ffffff;
  --bc-text: #111827;
  --bc-text-secondary: #4b5563;
  --bc-text-muted: #9ca3af;
  --bc-border: #e5e7eb;
  --bc-accent: #4f46e5;
  --bc-accent-hover: #4338ca;
  --bc-accent-light: rgba(79, 70, 229, 0.08);
  --bc-user-bubble: linear-gradient(135deg, #6366f1, #4f46e5);
  --bc-user-text: #ffffff;
  --bc-code-bg: #1e1e2e;
  --bc-code-text: #cdd6f4;
  --bc-radius: 14px;
  --bc-radius-sm: 8px;
  --bc-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --bc-shadow-lg: 0 4px 16px rgba(0,0,0,0.08);
  --bc-font: 'Inter', system-ui, -apple-system, sans-serif;
  --bc-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, monospace;
  --bc-green: #16a34a;
  --bc-amber: #f59e0b;
  --bc-red: #dc2626;
}

/* ── Layout ──────────────────────────────────────────────── */
body, .stApp {
  background: var(--bc-bg) !important;
  font-family: var(--bc-font) !important;
  color: var(--bc-text) !important;
}
.stApp > header { background: transparent !important; }
section[data-testid="stSidebar"] {
  background: var(--bc-sidebar-bg) !important;
  border-right: 1px solid var(--bc-border) !important;
}

/* ── Main chat container ─────────────────────────────────── */
.biochat-main {
  max-width: 860px;
  margin: 0 auto;
  padding: 0 16px;
}

/* ── Header bar ──────────────────────────────────────────── */
.biochat-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 18px;
  margin: 6px 0 16px;
  background: var(--bc-card-bg);
  border: 1px solid var(--bc-border);
  border-radius: var(--bc-radius);
}
.biochat-header .bc-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--bc-text);
}
.biochat-header .bc-version {
  font-size: 10px;
  font-weight: 600;
  color: var(--bc-text-muted);
  background: var(--bc-accent-light);
  padding: 2px 8px;
  border-radius: 8px;
}
.biochat-header .bc-model {
  font-size: 10px;
  color: var(--bc-text-muted);
  margin-left: auto;
  background: rgba(156,163,175,0.12);
  padding: 3px 10px;
  border-radius: 8px;
}
.biochat-header .bc-status {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 600;
  color: var(--bc-green);
}
.biochat-header .bc-status-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: var(--bc-green);
  animation: bc-pulse 2s ease-in-out infinite;
}
.biochat-header .bc-status-dot-processing {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: var(--bc-amber);
  animation: bc-pulse-fast 0.8s ease-in-out infinite;
}
@keyframes bc-pulse { 0%,100%{opacity:1} 50%{opacity:0.35} }
@keyframes bc-pulse-fast { 0%,100%{opacity:1} 50%{opacity:0.2} }

/* ── Welcome card ────────────────────────────────────────── */
.biochat-welcome {
  text-align: center;
  padding: 40px 24px 32px;
  background: var(--bc-card-bg);
  border: 1px solid var(--bc-border);
  border-radius: var(--bc-radius);
  box-shadow: var(--bc-shadow);
  margin: 12px 0 24px;
}
.biochat-welcome .bcw-icon { font-size: 42px; margin-bottom: 10px; }
.biochat-welcome h1 { font-size: 22px; font-weight: 700; margin: 0 0 4px; }
.biochat-welcome .bcw-subtitle {
  font-size: 14px; color: var(--bc-text-secondary); margin-bottom: 14px;
}
/* ── Chat messages ───────────────────────────────────────── */
.biochat-chat { display: flex; flex-direction: column; gap: 2px; }

/* User message */
.biochat-msg-user {
  display: flex;
  justify-content: flex-end;
  margin: 12px 0;
}
.biochat-msg-user .bc-bubble {
  background: var(--bc-user-bubble);
  color: var(--bc-user-text);
  font-weight: 500;
  font-size: 15px;
  line-height: 1.6;
  border-radius: 18px 18px 4px 18px;
  padding: 12px 18px;
  max-width: 75%;
  box-shadow: 0 2px 8px rgba(79,70,229,0.14);
}

/* Assistant message card */
.biochat-msg-assistant {
  margin: 12px 0 20px;
}
.biochat-msg-assistant .bc-card {
  background: var(--bc-card-bg);
  border: 1px solid var(--bc-border);
  border-radius: var(--bc-radius);
  box-shadow: var(--bc-shadow);
  overflow: hidden;
}

/* Trace toggle (collapsible) */
.bc-trace-toggle {
  border: 2px solid #3b82f6;
  border-left: 5px solid #7c3aed;
  border-radius: var(--bc-radius-sm);
  background: #fbfaff;
  color: #7c3aed;
  font-weight: 600;
  font-size: 13px;
  padding: 10px 16px;
  margin: 12px 12px 0 12px;
  cursor: pointer;
  user-select: none;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 8px;
}
.bc-trace-toggle::-webkit-details-marker { display: none; }
.bc-trace-toggle::before {
  content: '▶';
  font-size: 10px;
  transition: transform 0.2s;
  color: #7c3aed;
}
details[open] > .bc-trace-toggle::before { transform: rotate(90deg); }

.bc-trace-body {
  border-left: 4px solid #7c3aed;
  margin: 0 16px 8px 24px;
  padding: 4px 0 4px 16px;
  color: #4b5563;
  font-size: 12.5px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}

/* Answer body */
.bc-answer-body {
  padding: 6px 22px 20px 22px;
  font-size: 15.5px;
  line-height: 1.85;
  color: var(--bc-text);
}
.bc-answer-body p { margin: 0 0 10px; }
.bc-answer-body p:last-child { margin-bottom: 0; }
.bc-answer-body h2 { margin: 18px 0 8px; font-size: 17px; font-weight: 700; }
.bc-answer-body h3 { margin: 14px 0 6px; font-size: 15px; font-weight: 700; }
.bc-answer-body h4 { margin: 12px 0 4px; font-size: 14px; font-weight: 600; }
.bc-answer-body ul, .bc-answer-body ol { padding-left: 22px; margin: 6px 0; }
.bc-answer-body li { margin: 2px 0; }
.bc-answer-body blockquote {
  border-left: 3px solid var(--bc-accent);
  padding-left: 12px;
  color: var(--bc-text-secondary);
  margin: 8px 0;
}
.bc-answer-body table {
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0;
  font-size: 13px;
}
.bc-answer-body th, .bc-answer-body td {
  border: 1px solid var(--bc-border);
  padding: 6px 10px;
  text-align: left;
}
.bc-answer-body th {
  background: #f3f4f6;
  font-weight: 600;
}
/* Dedicated table class for markdown-rendered tables */
table.bc-table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 13px;
}
table.bc-table th {
  background: #f0f0ff;
  font-weight: 600;
  border: 1px solid var(--bc-border);
  padding: 8px 12px;
  text-align: left;
  white-space: nowrap;
}
table.bc-table td {
  border: 1px solid var(--bc-border);
  padding: 7px 12px;
  text-align: left;
  vertical-align: top;
}
table.bc-table tr:nth-child(even) td {
  background: #fafafa;
}
table.bc-table tr:hover td {
  background: #f0f0ff;
}
.bc-answer-body pre {
  background: var(--bc-code-bg);
  color: var(--bc-code-text);
  padding: 14px;
  border-radius: var(--bc-radius-sm);
  font-family: var(--bc-mono);
  font-size: 13px;
  overflow-x: auto;
  margin: 10px 0;
}
.bc-answer-body code {
  font-family: var(--bc-mono);
  font-size: 12.5px;
  background: rgba(0,0,0,0.06);
  padding: 2px 5px;
  border-radius: 4px;
}
.bc-answer-body pre code {
  background: transparent;
  padding: 0;
}

/* Thinking indicator */
.biochat-thinking {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 22px;
  font-size: 14px;
  color: var(--bc-text-secondary);
}
.biochat-thinking .bc-spinner {
  width: 18px; height: 18px;
  border: 2px solid var(--bc-border);
  border-top-color: var(--bc-accent);
  border-radius: 50%;
  animation: bc-spin 0.7s linear infinite;
}
@keyframes bc-spin { to { transform: rotate(360deg); } }

/* Streaming cursor (shown while the answer is still being generated) */
.bc-stream-cursor {
  display: inline-block;
  width: 8px; height: 17px;
  margin-left: 2px;
  vertical-align: text-bottom;
  background: var(--bc-accent);
  animation: bc-blink 1s steps(2) infinite;
}
@keyframes bc-blink { 0%,100%{opacity:1} 50%{opacity:0} }

/* Status badge */
.bc-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 500;
  padding: 4px 10px;
  border-radius: 10px;
  margin-right: 6px;
}
.bc-status-badge.planning { background: #ede9fe; color: #7c3aed; }
.bc-status-badge.retrieving { background: #dbeafe; color: #2563eb; }
.bc-status-badge.running { background: #fef3c7; color: #d97706; }
.bc-status-badge.completed { background: #dcfce7; color: #16a34a; }
.bc-status-badge.error { background: #fee2e2; color: #dc2626; }

/* ── Chat input ──────────────────────────────────────────── */
div[data-testid="stChatInput"] textarea {
  border-radius: var(--bc-radius) !important;
  border-color: var(--bc-border) !important;
  font-family: var(--bc-font) !important;
  font-size: 15px !important;
  padding: 12px 16px !important;
}
div[data-testid="stChatInput"] textarea:focus {
  border-color: var(--bc-accent) !important;
  box-shadow: 0 0 0 3px rgba(79,70,229,0.09) !important;
}

/* ── Sidebar buttons ─────────────────────────────────────── */
.stButton > button {
  border-radius: 10px !important;
  font-family: var(--bc-font) !important;
  font-weight: 500 !important;
  font-size: 13px !important;
  border: 1px solid var(--bc-border) !important;
  background: var(--bc-card-bg) !important;
  color: var(--bc-text) !important;
  transition: all 0.14s !important;
}
.stButton > button:hover {
  border-color: var(--bc-accent) !important;
  color: var(--bc-accent) !important;
  background: var(--bc-accent-light) !important;
}

/* ── Footer ──────────────────────────────────────────────── */
.biochat-footer {
  text-align: center;
  padding: 14px 0 20px;
  font-size: 11px;
  color: var(--bc-text-muted);
}
.biochat-footer a {
  color: var(--bc-accent);
  text-decoration: none;
  font-weight: 500;
}

/* ── Mobile responsive ───────────────────────────────────── */
@media (max-width: 768px) {
  .biochat-main { padding: 0 8px; }
  .biochat-msg-user .bc-bubble { max-width: 88%; }
  .biochat-header { padding: 8px 12px; }
  .bc-answer-body { padding: 0 14px 14px; }
}
</style>
"""

# ═══════════════════════════════════════════════════════════════════
# HTML rendering helpers
# ═══════════════════════════════════════════════════════════════════

import html as _html


def _escape(text: str) -> str:
    return _html.escape(text)


def render_user_bubble(content: str) -> str:
    """Right-aligned purple gradient bubble for user messages."""
    safe = _escape(content)
    return (
        '<div class="biochat-msg-user">'
        f'<div class="bc-bubble">{safe}</div>'
        '</div>'
    )


def render_assistant_card(
    answer: str,
    trace: str = "",
    trace_expanded: bool = False,
    status_label: str = "",
    status_class: str = "",
) -> str:
    """White card for assistant responses with optional processing trace.

    Args:
        answer: Final / in-progress answer (HTML-rendered Markdown).
        trace: Processing trace text shown inside a collapsible block.
        trace_expanded: Whether the trace starts open.
        status_label: Optional status badge text.
        status_class: CSS class for the status badge.
    """
    trace_html = ""
    if trace and trace.strip():
        open_attr = " open" if trace_expanded else ""
        trace_html = (
            f"<details{open_attr}>"
            '<summary class="bc-trace-toggle">🧠 Processing Trace</summary>'
            f'<div class="bc-trace-body">{_escape(trace)}</div>'
            '</details>'
        )

    status_html = ""
    if status_label:
        status_html = (
            f'<span class="bc-status-badge {status_class}">{status_label}</span>'
        )

    return (
        '<div class="biochat-msg-assistant">'
        '<div class="bc-card">'
        + trace_html
        + (f'<div style="padding:12px 22px 0">{status_html}</div>' if status_html else "")
        + f'<div class="bc-answer-body">{answer}</div>'
        + '</div>'
        '</div>'
    )


def simple_markdown_to_html(text: str) -> str:
    """Convert Markdown to clean HTML for card rendering.

    Handles: headings, bold, italic, inline code, fenced code blocks,
    pipe tables (multi-row), unordered/ordered lists, blockquotes,
    horizontal rules, and paragraphs.

    Processing order matters — code fences and tables are extracted
    before inline formatting to avoid conflicts.
    """
    if not text or not text.strip():
        return ""

    # ── Placeholder system: protect complex blocks from inline regex ─
    placeholders: dict[str, str] = {}
    _ph_counter: int = 0

    def _stash(pattern: str, text_to_stash: str, flags: int = 0) -> str:
        """Replace matches with placeholders, store originals."""
        nonlocal _ph_counter

        def _replacer(m: re.Match) -> str:
            nonlocal _ph_counter
            key = f"__PH_{_ph_counter}__"
            _ph_counter += 1
            placeholders[key] = m.group(0)
            return key

        return re.sub(pattern, _replacer, text_to_stash, flags=flags)

    def _restore(text_to_restore: str) -> str:
        """Restore all placeholders."""
        result = text_to_restore
        for key, value in placeholders.items():
            result = result.replace(key, value)
        return result

    # ── Step 1: Stash fenced code blocks ─────────────────────────
    text = _stash(r"```(?:\w+)?\s*\n.*?```", text, flags=re.DOTALL)

    # ── Step 2: Stash inline code ────────────────────────────────
    text = _stash(r"`[^`]+`", text)

    # ── Step 3: Detect and convert pipe tables ───────────────────
    lines = text.split("\n")
    output_lines: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # A table starts with a pipe line, followed by a separator line
        if re.match(r"^\|.+\|$", line) and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if re.match(r"^[\|\s\-:]+$", next_line):
                # We have a table header + separator
                table_rows: list[str] = []
                # Header row
                header_cells = [c.strip() for c in line.strip("|").split("|")]
                table_rows.append(
                    "<thead><tr>"
                    + "".join(f"<th>{_escape(c)}</th>" for c in header_cells)
                    + "</tr></thead>"
                )
                i += 2  # skip header and separator

                # Body rows
                body_rows: list[str] = []
                while i < len(lines) and re.match(r"^\|.+\|$", lines[i].strip()):
                    row_line = lines[i].strip()
                    cells = [c.strip() for c in row_line.strip("|").split("|")]
                    body_rows.append(
                        "<tr>"
                        + "".join(f"<td>{_escape(c)}</td>" for c in cells)
                        + "</tr>"
                    )
                    i += 1

                if body_rows:
                    table_html = (
                        '<table class="bc-table">'
                        + "".join(table_rows)
                        + "<tbody>" + "".join(body_rows) + "</tbody>"
                        + "</table>"
                    )
                    output_lines.append(table_html)
                continue

        output_lines.append(lines[i])
        i += 1

    text = "\n".join(output_lines)

    # ── Step 4: Headings ─────────────────────────────────────────
    text = re.sub(r"^#### (.+)$", r"<h4>\1</h4>", text, flags=re.MULTILINE)
    text = re.sub(r"^### (.+)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)
    text = re.sub(r"^## (.+)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
    text = re.sub(r"^# (.+)$", r"<h1>\1</h1>", text, flags=re.MULTILINE)

    # ── Step 5: Horizontal rules ─────────────────────────────────
    text = re.sub(r"^---+$", "<hr>", text, flags=re.MULTILINE)

    # ── Step 6: Bold / Italic ────────────────────────────────────
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)

    # ── Step 7: Blockquote ───────────────────────────────────────
    text = re.sub(
        r"^&gt; (.+)$", r"<blockquote>\1</blockquote>",
        text, flags=re.MULTILINE,
    )

    # ── Step 8: Ordered lists (1. 2. 3.) ────────────────────────
    # Group consecutive numbered items
    text = re.sub(
        r"((?:^\d+\.\s+.+$\n?)+)",
        lambda m: "<ol>" + re.sub(
            r"^\d+\.\s+(.+)$", r"<li>\1</li>",
            m.group(1).strip(), flags=re.MULTILINE
        ) + "</ol>",
        text,
        flags=re.MULTILINE,
    )

    # ── Step 9: Unordered lists (- item) ────────────────────────
    text = re.sub(
        r"((?:^-\s+.+$\n?)+)",
        lambda m: "<ul>" + re.sub(
            r"^-\s+(.+)$", r"<li>\1</li>",
            m.group(1).strip(), flags=re.MULTILINE
        ) + "</ul>",
        text,
        flags=re.MULTILINE,
    )

    # ── Step 10: Restore code blocks and inline code ─────────────
    # Convert stashed fenced code blocks
    for key, value in list(placeholders.items()):
        if value.startswith("```"):
            # Extract language and code
            match = re.match(r"```(\w+)?\s*\n(.*?)```", value, re.DOTALL)
            if match:
                lang = match.group(1) or ""
                code = _escape(match.group(2).rstrip())
                placeholders[key] = f'<pre><code class="language-{lang}">{code}</code></pre>'
        elif value.startswith("`") and value.endswith("`"):
            inner = value[1:-1]
            placeholders[key] = f"<code>{_escape(inner)}</code>"

    text = _restore(text)

    # ── Step 11: Paragraphs ──────────────────────────────────────
    # Split on double newlines and wrap each block
    blocks = text.split("\n\n")
    wrapped: list[str] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        # Don't wrap blocks that are already HTML tags
        if re.match(r"^<(h[1-4]|table|ul|ol|pre|blockquote|hr)", block):
            wrapped.append(block)
        else:
            # Replace single newlines with <br> within paragraphs
            block = block.replace("\n", "<br>")
            wrapped.append(f"<p>{block}</p>")

    return "\n".join(wrapped)


def build_trace_text(status: str = "running") -> str:
    """Build a safe, high-level processing trace message (Chinese)."""
    if status == "running":
        return (
            "已接收用户提问。\n"
            "正在调用 Biochat agent 引擎。\n"
            "检索相关工具和数据库中...\n"
            "正在生成回答..."
        )
    return (
        "已接收用户提问。\n"
        "已调用 Biochat agent 引擎。\n"
        "已按需查询工具和数据库。\n"
        "回答生成完成。"
    )


# ═══════════════════════════════════════════════════════════════════
# Sidebar
# ═══════════════════════════════════════════════════════════════════

def _session_view() -> dict[str, Any]:
    """Mirror Streamlit session state into the pure-helper dict shape."""
    return {
        "active_session_id": st.session_state.get("active_session_id", "default"),
        "messages": st.session_state.get("messages", []),
        "sessions": st.session_state.get("ui_sessions", {}),
    }


def _writeback_session_view(view: dict[str, Any]) -> None:
    """Write the helper-dict results back into Streamlit session state."""
    st.session_state["ui_sessions"] = view["sessions"]
    st.session_state["messages"] = view["messages"]
    st.session_state["active_session_id"] = view["active_session_id"]


def render_sidebar() -> dict[str, Any]:
    """Render the sidebar and return settings selected by the user."""
    from biochat.core.settings import PROJECT_VERSION

    st.sidebar.markdown(
        '<div style="font-size:18px;font-weight:700;margin-bottom:2px">🧬 Biochat</div>'
        f'<div style="font-size:11px;color:#9ca3af;margin-bottom:12px">'
        f'Biomedical AI Agent · v{PROJECT_VERSION}</div>',
        unsafe_allow_html=True,
    )

    # ── Session management ──────────────────────────────────
    from biochat.ui.session_state import create_ui_session, save_ui_session, switch_ui_session

    if st.sidebar.button("➕ 新建对话", use_container_width=True, key="sb_new_chat"):
        view = _session_view()
        create_ui_session(view)
        _writeback_session_view(view)
        st.session_state.pending_prompt = None
        st.rerun()

    if st.sidebar.button("🗑️ 清空当前对话", use_container_width=True, key="sb_clear"):
        st.session_state.messages = []
        st.rerun()

    st.sidebar.markdown("---")

    # ── History sessions ────────────────────────────────────
    st.sidebar.caption("📋 最近会话")
    if "sessions" not in st.session_state:
        st.session_state.sessions = {}
    if "active_session_id" not in st.session_state:
        st.session_state.active_session_id = "default"

    # Auto-track current conversation as a full-message session
    view = _session_view()
    msgs = view["messages"]
    if msgs:
        first_user_msg = next((m["content"] for m in msgs if m["role"] == "user"), "新对话")
        title = first_user_msg[:40] + ("..." if len(first_user_msg) > 40 else "")
        save_ui_session(view)
        view["sessions"][view["active_session_id"]]["title"] = title

    # Render session list; switching saves current and restores target.
    if view["sessions"]:
        for sid, sinfo in sorted(
            view["sessions"].items(),
            key=lambda x: x[1].get("message_count", 0), reverse=True
        ):
            is_active = sid == view["active_session_id"]
            prefix = "▸ " if is_active else "  "
            label = f"{prefix}{sinfo['title']} ({sinfo.get('message_count', 0)})"
            if st.sidebar.button(
                label, key=f"session_{sid}",
                use_container_width=True,
                help=f"切换到: {sinfo['title']}",
            ):
                switch_ui_session(view, sid)
                _writeback_session_view(view)
                st.rerun()
        _writeback_session_view(view)
    else:
        st.sidebar.caption("  暂无历史会话")

    st.sidebar.markdown("---")

    # ── Status indicators ───────────────────────────────────
    st.sidebar.caption("📊 系统状态")
    status_items = [
        ("ok", "✅ 结构工具 — 已验证"),
        ("ok", "✅ 30+ 数据库 — 已加载"),
        ("ok", "✅ 安全过滤 — 已启用"),
    ]
    for cls, label in status_items:
        color = {"ok": "#16a34a", "warn": "#f59e0b", "off": "#9ca3af"}[cls]
        st.sidebar.markdown(
            f'<div style="font-size:11px;padding:2px 0;color:{color}">{label}</div>',
            unsafe_allow_html=True,
        )

    # ── Settings (applied only via explicit Apply action) ────
    with st.sidebar.expander("⚙️ 设置"):
        from biochat.core.settings import BiochatSettings, biochat_settings as _s
        from biochat.services.agent_service import reset_agent_service

        with st.form("sb_settings_form"):
            data_path = st.text_input(
                "数据路径", _s.data_path, key="sb_path",
                help="本地数据湖目录 (~11GB)。",
            )
            llm_model = st.text_input(
                "LLM 模型", _s.llm_model, key="sb_llm",
                help="模型名称 (如 claude-sonnet-4-5, deepseek-chat, gpt-4)。",
            )
            applied = st.form_submit_button("✅ 应用并重启 Agent")

        if applied:
            try:
                new_settings = BiochatSettings(
                    data_path=data_path or None,
                    llm_model=llm_model or None,
                )
            except Exception as exc:
                st.error(f"配置无效: {exc}")
            else:
                reset_agent_service()
                # The next get_agent_service() call constructs with these.
                st.session_state["applied_settings"] = new_settings
                st.success(f"已应用: {new_settings.model_display_name}")

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        '<div style="font-size:10px;color:#9ca3af;line-height:1.5">'
        'Powered by Biochat Engine'
        ' · <a href="https://github.com/snap-stanford/Biomni">Apache 2.0</a>'
        '</div>',
        unsafe_allow_html=True,
    )

    return {"data_path": data_path, "llm_model": llm_model}


# ═══════════════════════════════════════════════════════════════════
# Welcome screen
# ═══════════════════════════════════════════════════════════════════

def render_welcome_card() -> None:
    """Show the welcome card when no messages exist."""
    st.markdown(
        '<div class="biochat-welcome">'
        '<div class="bcw-icon">🧬</div>'
        '<h1>你好，我是 Biochat</h1>'
        '<p class="bcw-subtitle">您的生物医学 AI 研究助手</p>'
        '</div>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════
# Agent interaction (streaming via service layer)
# ═══════════════════════════════════════════════════════════════════

def stream_agent_response(user_query: str, session_id: str = "default"):
    """Stream agent execution with real-time incremental updates.

    Uses ``BioAgentService.run_task_stream()`` which calls
    ``agent.go_stream()`` internally.  Each yield contains the
    current state (thinking / executing / answering / completed / error)
    so the UI can update in real time instead of freezing.

    Yields:
        dict with keys: status, answer_so_far, trace_lines, current_step
    """
    from biochat.services.agent_service import get_agent_service
    from biochat.schemas.chat import ChatRequest

    svc = get_agent_service()

    try:
        svc.ensure_initialized()
    except Exception as exc:
        yield {
            "status": "error",
            "answer_so_far": f"⚠️ Agent 初始化失败: {exc}",
            "trace_lines": [],
            "current_step": "",
        }
        return

    request = ChatRequest(message=user_query, session_id=session_id)
    trace_lines: list[str] = []
    answer_so_far: str = ""
    current_step: str = ""

    try:
        for event in svc.run_task_stream(request):
            status = event.get("status", "thinking")
            content = event.get("content", "")

            if event.get("trace_line"):
                trace_lines.append(event["trace_line"])

            if status == "completed":
                answer_so_far = event.get("answer_so_far", content)
                break
            elif status == "error":
                answer_so_far = event.get("answer_so_far", content)
                break
            elif status == "answering":
                answer_so_far = event.get("answer_so_far", content)
                current_step = "✍️ 正在生成回答..."
            elif status == "thinking":
                current_step = "🤔 分析思考中..."
            elif status == "retrieving":
                current_step = "🔍 检索工具和数据库中..."
            elif status == "executing":
                lang = event.get("language", "python")
                current_step = f"💻 执行 {lang.upper()} 代码中..."
            elif status == "observing":
                current_step = "📋 获取执行结果..."

            yield {
                "status": status,
                "answer_so_far": answer_so_far,
                "trace_lines": list(trace_lines),
                "current_step": current_step,
            }

        # Final yield with complete data
        yield {
            "status": status,
            "answer_so_far": answer_so_far,
            "trace_lines": list(trace_lines),
            "current_step": "✅ 完成" if status == "completed" else "❌ 出错",
        }

    except Exception as exc:
        traceback.print_exc()
        yield {
            "status": "error",
            "answer_so_far": f"❌ 执行出错: {exc}",
            "trace_lines": trace_lines,
            "current_step": "❌ 错误",
        }


def render_assistant_card_streaming(
    answer_html: str,
    trace_lines: list[str],
    status: str,
    current_step: str,
    trace_expanded: bool = True,
) -> str:
    """Render an assistant card that updates in real-time during streaming.

    Unlike ``render_assistant_card`` which shows a static card, this
    renders different content based on the current streaming status.
    """
    trace_text = "\n".join(trace_lines) if trace_lines else ""

    # Build trace HTML
    trace_html = ""
    if trace_text.strip():
        open_attr = " open" if trace_expanded else ""
        trace_html = (
            f"<details{open_attr}>"
            '<summary class="bc-trace-toggle">🧠 处理轨迹</summary>'
            f'<div class="bc-trace-body">{_escape(trace_text)}</div>'
            '</details>'
        )

    # Build status badge
    status_map = {
        "thinking": ("分析中", "planning"),
        "retrieving": ("检索工具中", "retrieving"),
        "executing": ("执行代码中", "running"),
        "observing": ("获取结果中", "running"),
        "answering": ("生成回答中", "running"),
        "completed": ("已完成", "completed"),
        "error": ("出错", "error"),
    }
    label, css_class = status_map.get(status, ("处理中", "planning"))

    # Build the card body based on status
    if status in ("thinking", "retrieving", "executing", "observing"):
        # Show spinner + current step during execution
        body_html = (
            f'<div class="biochat-thinking">'
            f'<div class="bc-spinner"></div>'
            f'<div>'
            f'<div style="font-weight:600;margin-bottom:4px">{_escape(current_step)}</div>'
            f'<div style="font-size:12px;color:var(--bc-text-muted)">'
            f'请耐心等待，复杂任务可能需要几分钟...</div>'
            f'</div>'
            f'</div>'
        )
    elif status == "answering" and answer_html:
        # Incremental answer text — plain pre-wrap (no markdown) so the
        # card streams smoothly without re-layout flicker; a blinking
        # cursor conveys that generation is still in progress.
        body_html = (
            f'<div style="white-space:pre-wrap;word-break:break-word">{answer_html}'
            f'<span class="bc-stream-cursor"></span></div>'
        )
    elif status == "completed" and answer_html:
        body_html = answer_html
    elif status == "error" and answer_html:
        body_html = answer_html
    else:
        body_html = (
            f'<div class="biochat-thinking">'
            f'<div class="bc-spinner"></div>'
            f'正在处理您的请求...</div>'
        )

    return (
        '<div class="biochat-msg-assistant">'
        '<div class="bc-card">'
        + trace_html
        + f'<div style="padding:12px 22px 0">'
        f'<span class="bc-status-badge {css_class}">{label}</span>'
        f'<span style="font-size:12px;color:var(--bc-text-muted)">{_escape(current_step)}</span>'
        f'</div>'
        + f'<div class="bc-answer-body">{body_html}</div>'
        + '</div>'
        '</div>'
    )


# ═══════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════

def main() -> None:
    """Biochat Streamlit UI main function."""

    # ── Session state init ───────────────────────────────────
    defaults = {
        "messages": [],
        "pending_prompt": None,
        "is_processing": False,
        "streaming_prompt": None,   # prompt text while streaming is active
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default

    # ── Inject CSS ───────────────────────────────────────────
    st.markdown(BIOCHAT_CSS, unsafe_allow_html=True)

    # ── Access gate (before any Agent initialization) ────────
    from biochat.core.settings import PROJECT_VERSION
    from biochat.core.settings import biochat_settings as _gate_cfg
    from biochat.ui.auth import verify_access_code as _verify_access_code

    if _gate_cfg.require_verification and not st.session_state.get("bc_authenticated"):
        st.markdown('<div class="biochat-main">', unsafe_allow_html=True)
        st.markdown('<div class="biochat-welcome"><div class="bcw-icon">🔒</div>'
                    '<h1>Biochat 访问验证</h1>'
                    '<p class="bcw-subtitle">请输入访问码以继续</p></div>',
                    unsafe_allow_html=True)
        candidate = st.text_input("访问码", type="password", key="bc_access_input")
        if st.button("解锁", key="bc_access_btn", use_container_width=True):
            if _verify_access_code(candidate, _gate_cfg.access_codes):
                st.session_state["bc_authenticated"] = True
                st.rerun()
            st.error("访问码错误")
        st.stop()

    # ── Sidebar ──────────────────────────────────────────────
    settings = render_sidebar()

    # ═══════════════════════════════════════════════════════════
    # Phase 1: Accept user input — append to messages + rerun
    #           so the user message renders BEFORE streaming starts.
    # ═══════════════════════════════════════════════════════════

    prompt = st.session_state.pending_prompt
    if prompt and not st.session_state.is_processing:
        # Clear pending; store for streaming phase after rerun
        st.session_state.pending_prompt = None
        st.session_state.streaming_prompt = prompt
        # Append user message so it renders now
        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        st.rerun()

    # ═══════════════════════════════════════════════════════════
    # Phase 2: Streaming trigger — set flag only.  Actual streaming
    #           happens inside the chat rendering area below, so the
    #           processing card flows naturally after user messages.
    # ═══════════════════════════════════════════════════════════

    streaming_prompt = st.session_state.streaming_prompt
    if streaming_prompt and not st.session_state.is_processing:
        st.session_state.is_processing = True

    # ═══════════════════════════════════════════════════════════
    # Render UI
    # ═══════════════════════════════════════════════════════════

    st.markdown('<div class="biochat-main">', unsafe_allow_html=True)

    # ── Header ──────────────────────────────────────────────
    from biochat.core.settings import biochat_settings as _cfg

    # Dynamic status: show "就绪" when idle, "处理中" when busy
    status_text = "处理中..." if st.session_state.is_processing else "就绪"
    status_dot_class = "bc-status-dot" if not st.session_state.is_processing else "bc-status-dot-processing"

    st.markdown(
        '<div class="biochat-header">'
        '<span class="bc-title">🧬 Biochat</span>'
        f'<span class="bc-version">v{PROJECT_VERSION}</span>'
        f'<span class="bc-model">{_cfg.llm_model}</span>'
        f'<span class="bc-status">'
        f'<span class="{status_dot_class}"></span> {status_text}'
        '</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Chat messages ───────────────────────────────────────
    st.markdown('<div class="biochat-chat">', unsafe_allow_html=True)

    # Only show welcome card when truly idle (no messages AND not processing)
    if not st.session_state.messages and not st.session_state.is_processing:
        render_welcome_card()

    for msg in st.session_state.messages:
        role = msg["role"]
        content = msg.get("content", "")
        trace = msg.get("trace", "")

        if role == "user":
            st.markdown(render_user_bubble(content), unsafe_allow_html=True)
        else:
            # P0: sanitize before rendering — no internal reasoning may reach UI
            content = sanitize_visible_text(content)
            trace = sanitize_visible_text(trace)
            answer_html = simple_markdown_to_html(content)
            st.markdown(
                render_assistant_card(
                    answer=answer_html,
                    trace=trace,
                    trace_expanded=False,
                ),
                unsafe_allow_html=True,
            )

    # ── Streaming response: INSIDE chat area, below all messages ──
    streaming_prompt = st.session_state.get("streaming_prompt")
    if streaming_prompt and st.session_state.is_processing:
        st.session_state.streaming_prompt = None

        card_placeholder = st.empty()
        card_placeholder.markdown(
            render_assistant_card_streaming(
                answer_html="", trace_lines=[],
                status="thinking",
                current_step="🔍 正在初始化 Agent 引擎...",
                trace_expanded=True,
            ),
            unsafe_allow_html=True,
        )

        final_answer = ""
        final_trace_lines: list[str] = []
        final_status = "thinking"
        last_stream_render = 0.0  # throttle card updates during token streaming

        for update in stream_agent_response(
            streaming_prompt,
            session_id=st.session_state.get("active_session_id", "default"),
        ):
            final_status = update["status"]
            # P0: sanitize trace lines — whitelist status events only
            final_trace_lines = [
                sanitize_visible_text(line) for line in update.get("trace_lines", [])
                if sanitize_visible_text(line)
            ]

            if update["status"] == "completed":
                # P0: real-time sanitize of accumulated answer
                final_answer = sanitize_visible_text(update["answer_so_far"])
                card_placeholder.markdown(
                    render_assistant_card_streaming(
                        answer_html=simple_markdown_to_html(final_answer),
                        trace_lines=final_trace_lines,
                        status="completed", current_step="✅ 完成",
                        trace_expanded=False,
                    ),
                    unsafe_allow_html=True,
                )
                break
            elif update["status"] == "error":
                final_answer = sanitize_visible_text(update["answer_so_far"])
                card_placeholder.markdown(
                    render_assistant_card_streaming(
                        answer_html=simple_markdown_to_html(final_answer),
                        trace_lines=final_trace_lines,
                        status="error", current_step="❌ 出错",
                        trace_expanded=True,
                    ),
                    unsafe_allow_html=True,
                )
                break
            elif update["status"] == "answering":
                # Stream the final answer token-by-token as it is generated.
                # Render as plain pre-wrap text (no markdown) so the card
                # grows smoothly without re-layout flicker; throttle updates
                # so the browser isn't flooded on every token.
                partial = sanitize_visible_text(update.get("answer_so_far", ""))
                # Trim a trailing half-written tag (e.g. `<` or `</sol`)
                # so it doesn't flash in the streamed text.
                partial = re.sub(r"</?(?:[a-zA-Z_][\w:-]*)?$", "", partial)
                now = time.time()
                if partial and now - last_stream_render >= 0.2:
                    card_placeholder.markdown(
                        render_assistant_card_streaming(
                            answer_html=_escape(partial),
                            trace_lines=final_trace_lines,
                            status="answering",
                            current_step="✍️ 正在生成回答...",
                            trace_expanded=False,
                        ),
                        unsafe_allow_html=True,
                    )
                    last_stream_render = now
            else:
                card_placeholder.markdown(
                    render_assistant_card_streaming(
                        answer_html="", trace_lines=final_trace_lines,
                        status=update["status"],
                        current_step=update.get("current_step", "处理中..."),
                        trace_expanded=True,
                    ),
                    unsafe_allow_html=True,
                )

        # Final settled card (P0: answer + trace both sanitized)
        final_answer = sanitize_visible_text(final_answer)
        trace_str = "\n".join(final_trace_lines) if final_trace_lines else ""
        if not final_answer:
            from biochat.ui.sanitize import FALLBACK_MESSAGE
            final_answer = FALLBACK_MESSAGE
        if final_status == "completed":
            card_placeholder.markdown(
                render_assistant_card(
                    answer=simple_markdown_to_html(final_answer),
                    trace=trace_str, trace_expanded=False,
                    status_label="已完成", status_class="completed",
                ),
                unsafe_allow_html=True,
            )
        elif final_status == "error":
            card_placeholder.markdown(
                render_assistant_card(
                    answer=simple_markdown_to_html(final_answer),
                    trace=trace_str, trace_expanded=True,
                    status_label="错误", status_class="error",
                ),
                unsafe_allow_html=True,
            )

        st.session_state.messages.append({
            "role": "assistant",
            "content": final_answer,
            "trace": trace_str,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        st.session_state.is_processing = False
        st.rerun()

    # Auto-scroll anchor: JS scrolls to this element after every render
    st.markdown('<div id="biochat-bottom"></div>', unsafe_allow_html=True)
    st.markdown(
        """<script>
        var bottom = window.parent.document.getElementById('biochat-bottom');
        if (bottom) { bottom.scrollIntoView({behavior: 'smooth', block: 'end'}); }
        </script>""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)  # close chat

    # ── Chat input ──────────────────────────────────────────
    user_input = st.chat_input(
        "提出您的生物医学研究问题…",
        disabled=st.session_state.is_processing,
    )
    if user_input and user_input.strip() and not st.session_state.is_processing:
        st.session_state.pending_prompt = user_input.strip()
        st.rerun()

    # ── Footer ──────────────────────────────────────────────
    st.markdown(
        '<div class="biochat-footer">'
        '<strong>Biochat</strong> · Apache 2.0'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)  # close biochat-main


if __name__ == "__main__":
    main()
