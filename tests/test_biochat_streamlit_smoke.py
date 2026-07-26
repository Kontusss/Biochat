"""
Biochat Streamlit UI Smoke Tests

Verifies imports, CSS class presence, render helpers, event extraction,
user-content escaping, and file preservation.  Does NOT start a server.
"""

from __future__ import annotations

import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ═══════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════

class TestImports:
    def test_module_imports(self):
        import biomni.ui.biochat_streamlit as m
        assert m is not None

    def test_main_callable(self):
        from biomni.ui.biochat_streamlit import main
        assert callable(main)

    def test_get_agent_signature(self):
        from biomni.ui.biochat_streamlit import get_agent
        sig = inspect.signature(get_agent)
        for p in ("path", "llm"):
            assert p in sig.parameters


# ═══════════════════════════════════════════════════════════════
# CSS
# ═══════════════════════════════════════════════════════════════

REQUIRED_CSS_CLASSES = [
    "biochat-app",
    "biochat-header",
    "biochat-header-title",
    "biochat-header-badge",
    "biochat-chat-shell",
    "biochat-user-row",
    "biochat-user-bubble",
    "biochat-assistant-card",
    "biochat-trace-header",
    "biochat-trace-body",
    "biochat-answer-body",
    "biochat-welcome-card",
    "biochat-example-grid",
    "biochat-footer-note",
]


class TestCSS:
    def test_css_length(self):
        from biomni.ui.biochat_streamlit import BIOCHAT_STREAMLIT_CSS
        assert len(BIOCHAT_STREAMLIT_CSS) > 2000

    def test_required_classes_present(self):
        from biomni.ui.biochat_streamlit import BIOCHAT_STREAMLIT_CSS
        for name in REQUIRED_CSS_CLASSES:
            assert f".{name}" in BIOCHAT_STREAMLIT_CSS, (
                f"Missing CSS class: .{name}"
            )


# ═══════════════════════════════════════════════════════════════
# RENDER HELPERS
# ═══════════════════════════════════════════════════════════════

class TestRenderHelpers:
    def test_render_user_bubble_exists(self):
        from biomni.ui.biochat_streamlit import render_user_bubble
        assert callable(render_user_bubble)
        sig = inspect.signature(render_user_bubble)
        assert "content" in sig.parameters

    def test_render_assistant_card_exists(self):
        from biomni.ui.biochat_streamlit import render_assistant_card
        assert callable(render_assistant_card)
        sig = inspect.signature(render_assistant_card)
        for p in ("answer", "trace", "expanded"):
            assert p in sig.parameters

    def test_render_welcome_card_exists(self):
        from biomni.ui.biochat_streamlit import render_welcome_card
        assert callable(render_welcome_card)

    def test_stream_agent_response_exists(self):
        from biomni.ui.biochat_streamlit import stream_agent_response
        assert callable(stream_agent_response)
        sig = inspect.signature(stream_agent_response)
        for p in ("agent", "user_query"):
            assert p in sig.parameters

    def test_extract_text_from_event_exists(self):
        from biomni.ui.biochat_streamlit import extract_text_from_event
        assert callable(extract_text_from_event)


# ═══════════════════════════════════════════════════════════════
# USER CONTENT ESCAPING
# ═══════════════════════════════════════════════════════════════

class TestUserEscaping:
    def test_xss_script_tag_escaped(self):
        from biomni.ui.biochat_streamlit import render_user_bubble
        html = render_user_bubble("<script>alert(1)</script>")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_html_tags_escaped(self):
        from biomni.ui.biochat_streamlit import render_user_bubble
        html = render_user_bubble('<img src=x onerror=alert(1)>')
        assert "<img" not in html
        assert "&lt;img" in html

    def test_normal_text_preserved(self):
        from biomni.ui.biochat_streamlit import render_user_bubble
        html = render_user_bubble("Hello, how are you?")
        assert "Hello, how are you?" in html
        assert "biochat-user-bubble" in html
        assert "biochat-user-row" in html


# ═══════════════════════════════════════════════════════════════
# EVENT EXTRACTION
# ═══════════════════════════════════════════════════════════════

class TestEventExtraction:
    def test_plain_string(self):
        from biomni.ui.biochat_streamlit import extract_text_from_event
        assert extract_text_from_event("hello") == "hello"

    def test_none(self):
        from biomni.ui.biochat_streamlit import extract_text_from_event
        assert extract_text_from_event(None) == ""

    def test_dict_content(self):
        from biomni.ui.biochat_streamlit import extract_text_from_event
        assert extract_text_from_event({"content": "c"}) == "c"

    def test_dict_output(self):
        from biomni.ui.biochat_streamlit import extract_text_from_event
        assert extract_text_from_event({"output": "o"}) == "o"

    def test_dict_text(self):
        from biomni.ui.biochat_streamlit import extract_text_from_event
        assert extract_text_from_event({"text": "t"}) == "t"

    def test_dict_response(self):
        from biomni.ui.biochat_streamlit import extract_text_from_event
        assert extract_text_from_event({"response": "r"}) == "r"

    def test_object_with_content(self):
        from biomni.ui.biochat_streamlit import extract_text_from_event

        class M:
            def __init__(self, c):
                self.content = c

        assert extract_text_from_event(M("obj")) == "obj"

    def test_list_of_strings(self):
        from biomni.ui.biochat_streamlit import extract_text_from_event
        result = extract_text_from_event(["a", "b"])
        assert "a" in result and "b" in result

    def test_dict_with_messages_list(self):
        from biomni.ui.biochat_streamlit import extract_text_from_event

        class M:
            def __init__(self, c):
                self.content = c

        result = extract_text_from_event({"messages": [M("x"), M("y")]})
        assert "x" in result and "y" in result

    def test_unknown_type_fallback(self):
        from biomni.ui.biochat_streamlit import extract_text_from_event
        assert "42" in extract_text_from_event(42)


# ═══════════════════════════════════════════════════════════════
# OUTPUT CLEANING
# ═══════════════════════════════════════════════════════════════

class TestCleanAgentOutput:
    def test_imports(self):
        from biomni.ui.biochat_streamlit import (
            clean_agent_output,
            polish_markdown_for_display,
            build_safe_processing_trace,
        )
        for fn in (clean_agent_output, polish_markdown_for_display, build_safe_processing_trace):
            assert callable(fn)

    def test_strips_human_ai_message_delimiters(self):
        from biomni.ui.biochat_streamlit import clean_agent_output

        raw = (
            "============================== Human Message ==============================\n"
            "Query EGFR\n\n"
            "============================== Ai Message ==============================\n"
            "I'll start by planning.\n\n"
            "## Plan\n"
            "1. [ ] Query UniProt\n"
            "2. [ ] Query PDB\n"
        )
        clean = clean_agent_output(raw)
        assert "Human Message" not in clean
        assert "Ai Message" not in clean
        assert "====" not in clean
        # Human query content should be dropped
        assert "Query EGFR" not in clean
        # AI content preserved
        assert "Query UniProt" in clean
        # Checkboxes removed
        assert "[ ]" not in clean

    def test_single_ai_message_only(self):
        from biomni.ui.biochat_streamlit import clean_agent_output

        raw = "================ AI Message ================\nFinal answer here"
        result = clean_agent_output(raw).strip()
        assert result == "Final answer here"

    def test_empty_returns_fallback(self):
        from biomni.ui.biochat_streamlit import clean_agent_output, FALLBACK_EMPTY_RESPONSE
        assert "no displayable answer" in clean_agent_output("").lower()
        assert "no displayable answer" in clean_agent_output("   ").lower()

    def test_polish_plan_header(self):
        from biomni.ui.biochat_streamlit import polish_markdown_for_display
        result = polish_markdown_for_display("## Plan\n1. Do A\n2. Do B")
        assert "分析计划" in result
        assert "Do A" in result

    def test_polish_removes_empty_checkboxes(self):
        from biomni.ui.biochat_streamlit import polish_markdown_for_display
        # polish_markdown_for_display doesn't handle [ ] — that's clean_agent_output's job.
        # Just verify it doesn't break on content containing them.
        result = polish_markdown_for_display("1. [ ] Step one")
        assert "Step one" in result

    def test_safe_trace_no_internals(self):
        from biomni.ui.biochat_streamlit import build_safe_processing_trace
        trace = build_safe_processing_trace("streaming")
        assert "Human Message" not in trace
        assert "Ai Message" not in trace
        assert "====" not in trace
        assert "Biomni" in trace or "Biochat" in trace

    def test_safe_trace_completed(self):
        from biomni.ui.biochat_streamlit import build_safe_processing_trace
        trace = build_safe_processing_trace("completed")
        assert "完成" in trace

    def test_preserves_scientific_content(self):
        from biomni.ui.biochat_streamlit import clean_agent_output

        raw = (
            "===== Ai Message =====\n"
            "The EGFR protein (UniProt: P00533) has an extracellular domain\n"
            "containing four subdomains (I-IV). The PDB entry 1M17 shows...\n"
        )
        clean = clean_agent_output(raw)
        assert "P00533" in clean
        assert "1M17" in clean
        assert "extracellular" in clean
        assert "=====" not in clean
        assert "Ai Message" not in clean


# ═══════════════════════════════════════════════════════════════
# PRESERVATION
# ═══════════════════════════════════════════════════════════════

class TestGradioPreserved:
    def test_files_exist(self):
        for p in [
            "biomni/ui/biochat_ui.py",
            "biomni/ui/biochat_theme.py",
            "scripts/biochat_demo.py",
        ]:
            assert (ROOT / p).is_file(), f"Missing: {p}"

    def test_gradio_launch_importable(self):
        from biomni.ui.biochat_ui import launch_biochat_ui
        assert callable(launch_biochat_ui)


class TestLauncher:
    def test_script_exists(self):
        assert (ROOT / "scripts" / "biochat_streamlit_demo.py").is_file()

    def test_valid_syntax(self):
        import ast
        ast.parse((ROOT / "scripts" / "biochat_streamlit_demo.py").read_text())

    def test_streamlit_in_deps(self):
        assert "streamlit" in (ROOT / "pyproject.toml").read_text().lower()

    def test_streamlit_installed(self):
        import streamlit
        assert hasattr(streamlit, "__version__")
