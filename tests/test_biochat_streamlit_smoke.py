"""
Biochat Streamlit UI Smoke Tests (current architecture)

Verifies imports, CSS class presence, render helpers, user-content
escaping, event extraction, and answer cleaning — against the APIs that
actually exist in ``biochat/ui/biochat_streamlit.py``, ``biochat/ui/sanitize.py``
and ``biochat/services/agent_service.py``.  Does NOT start a server.
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
        import biochat.ui.biochat_streamlit as m
        assert m is not None

    def test_main_callable(self):
        from biochat.ui.biochat_streamlit import main
        assert callable(main)

    def test_agent_service_factory(self):
        from biochat.services.agent_service import get_agent_service
        sig = inspect.signature(get_agent_service)
        assert "settings" in sig.parameters

    def test_stream_agent_response_signature(self):
        from biochat.ui.biochat_streamlit import stream_agent_response
        sig = inspect.signature(stream_agent_response)
        assert "user_query" in sig.parameters


# ═══════════════════════════════════════════════════════════════
# CSS
# ═══════════════════════════════════════════════════════════════

REQUIRED_CSS_CLASSES = [
    "biochat-header",
    "biochat-msg-user",
    "biochat-msg-assistant",
    "bc-answer-body",
    "bc-trace-toggle",
    "bc-trace-body",
    "biochat-welcome",
    "biochat-thinking",
    "bc-status-badge",
    "bc-stream-cursor",
]


class TestCSS:
    def test_css_length(self):
        from biochat.ui.biochat_streamlit import BIOCHAT_CSS
        assert len(BIOCHAT_CSS) > 2000

    def test_required_classes_present(self):
        from biochat.ui.biochat_streamlit import BIOCHAT_CSS
        for name in REQUIRED_CSS_CLASSES:
            assert f".{name}" in BIOCHAT_CSS, f"Missing CSS class: .{name}"


# ═══════════════════════════════════════════════════════════════
# RENDER HELPERS
# ═══════════════════════════════════════════════════════════════

class TestRenderHelpers:
    def test_render_user_bubble_exists(self):
        from biochat.ui.biochat_streamlit import render_user_bubble
        assert callable(render_user_bubble)
        sig = inspect.signature(render_user_bubble)
        assert "content" in sig.parameters

    def test_render_assistant_card_exists(self):
        from biochat.ui.biochat_streamlit import render_assistant_card
        assert callable(render_assistant_card)
        sig = inspect.signature(render_assistant_card)
        for p in ("answer", "trace", "trace_expanded"):
            assert p in sig.parameters

    def test_render_assistant_card_streaming_exists(self):
        from biochat.ui.biochat_streamlit import render_assistant_card_streaming
        assert callable(render_assistant_card_streaming)
        sig = inspect.signature(render_assistant_card_streaming)
        for p in ("answer_html", "trace_lines", "status"):
            assert p in sig.parameters

    def test_render_welcome_card_exists(self):
        from biochat.ui.biochat_streamlit import render_welcome_card
        assert callable(render_welcome_card)

    def test_simple_markdown_to_html_exists(self):
        from biochat.ui.biochat_streamlit import simple_markdown_to_html
        assert callable(simple_markdown_to_html)
        html = simple_markdown_to_html("**bold** and `code`")
        assert "<strong>bold</strong>" in html
        assert "<code>code</code>" in html

    def test_build_trace_text_exists(self):
        from biochat.ui.biochat_streamlit import build_trace_text
        assert callable(build_trace_text)
        assert build_trace_text("completed") != build_trace_text("running")

    def test_streaming_card_shows_answer_when_answering(self):
        from biochat.ui.biochat_streamlit import render_assistant_card_streaming
        card = render_assistant_card_streaming(
            answer_html="partial answer text",
            trace_lines=[],
            status="answering",
            current_step="✍️ 正在生成回答...",
        )
        assert "partial answer text" in card
        assert "bc-stream-cursor" in card


# ═══════════════════════════════════════════════════════════════
# USER CONTENT ESCAPING
# ═══════════════════════════════════════════════════════════════

class TestUserEscaping:
    def test_xss_script_tag_escaped(self):
        from biochat.ui.biochat_streamlit import render_user_bubble
        html = render_user_bubble("<script>alert(1)</script>")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_html_tags_escaped(self):
        from biochat.ui.biochat_streamlit import render_user_bubble
        html = render_user_bubble('<img src=x onerror=alert(1)>')
        assert "<img" not in html
        assert "&lt;img" in html

    def test_normal_text_preserved(self):
        from biochat.ui.biochat_streamlit import render_user_bubble
        html = render_user_bubble("Hello, how are you?")
        assert "Hello, how are you?" in html
        assert "biochat-msg-user" in html
        assert "bc-bubble" in html


# ═══════════════════════════════════════════════════════════════
# EVENT EXTRACTION (service layer)
# ═══════════════════════════════════════════════════════════════

class TestEventExtraction:
    @staticmethod
    def _extract(event):
        """Call the unbound service helper (self is unused)."""
        from biochat.services.agent_service import BioAgentService
        return BioAgentService._extract_text_from_event(None, event)

    def test_plain_string(self):
        assert self._extract("hello") == "hello"

    def test_none(self):
        assert self._extract(None) == ""

    def test_dict_content(self):
        assert self._extract({"content": "c"}) == "c"

    def test_dict_output(self):
        assert self._extract({"output": "o"}) == "o"

    def test_dict_text(self):
        assert self._extract({"text": "t"}) == "t"

    def test_dict_response(self):
        assert self._extract({"response": "r"}) == "r"

    def test_object_with_content(self):
        class M:
            def __init__(self, c):
                self.content = c

        assert self._extract(M("obj")) == "obj"

    def test_unknown_type_fallback(self):
        assert "42" in self._extract(42)


# ═══════════════════════════════════════════════════════════════
# ANSWER CLEANING
# ═══════════════════════════════════════════════════════════════

class TestCleanAgentOutput:
    def test_strips_human_ai_message_delimiters(self):
        from biochat.services.agent_service import BioAgentService

        raw = (
            "============================== Human Message ==============================\n"
            "Query EGFR\n\n"
            "============================== Ai Message ==============================\n"
            "I'll start by planning.\n\n"
            "## Plan\n"
            "1. [ ] Query UniProt\n"
            "2. [ ] Query PDB\n"
        )
        clean = BioAgentService._clean_agent_text(raw)
        assert "Human Message" not in clean
        assert "Ai Message" not in clean
        assert "====" not in clean
        # AI content preserved
        assert "Query UniProt" in clean
        # Checkboxes removed
        assert "[ ]" not in clean

    def test_single_ai_message_only(self):
        from biochat.services.agent_service import BioAgentService

        raw = "================ AI Message ================\nFinal answer here"
        result = BioAgentService._clean_agent_text(raw).strip()
        assert result == "Final answer here"

    def test_removes_execute_and_observation_blocks(self):
        from biochat.services.agent_service import BioAgentService

        raw = (
            "Let me compute.\n"
            "<execute>print(1+1)</execute>\n"
            "<observation>2</observation>\n"
            "The answer is 2."
        )
        clean = BioAgentService._clean_agent_text(raw)
        assert "<execute>" not in clean
        assert "<observation>" not in clean
        assert "print(1+1)" not in clean
        assert "The answer is 2." in clean

    def test_preserves_scientific_content(self):
        from biochat.services.agent_service import BioAgentService

        raw = (
            "===== Ai Message =====\n"
            "The EGFR protein (UniProt: P00533) has an extracellular domain\n"
            "containing four subdomains (I-IV). The PDB entry 1M17 shows...\n"
        )
        clean = BioAgentService._clean_agent_text(raw)
        assert "P00533" in clean
        assert "1M17" in clean
        assert "extracellular" in clean
        assert "=====" not in clean
        assert "Ai Message" not in clean


# ═══════════════════════════════════════════════════════════════
# SANITIZER (P0 UI filter)
# ═══════════════════════════════════════════════════════════════

class TestSanitizer:
    def test_removes_think_blocks(self):
        from biochat.ui.sanitize import sanitize_visible_text
        text = "Before\n<thinking>hidden chain of thought</thinking>\nAfter"
        result = sanitize_visible_text(text)
        assert "hidden chain of thought" not in result
        assert "Before" in result
        assert "After" in result

    def test_removes_xml_tags(self):
        from biochat.ui.sanitize import sanitize_visible_text
        assert "<solution>" not in sanitize_visible_text("a<solution>b</solution>c")

    def test_removes_self_talk_lines(self):
        from biochat.ui.sanitize import sanitize_visible_text
        text = "我需要重新生成回复。\n正常内容"
        result = sanitize_visible_text(text)
        assert "重新生成回复" not in result
        assert "正常内容" in result

    def test_fallback_message_exists(self):
        from biochat.ui.sanitize import FALLBACK_MESSAGE
        assert FALLBACK_MESSAGE.strip()


# ═══════════════════════════════════════════════════════════════
# PRESERVATION
# ═══════════════════════════════════════════════════════════════

class TestGradioPreserved:
    def test_files_exist(self):
        for p in [
            "biochat/ui/biochat_ui.py",
            "biochat/ui/biochat_theme.py",
            "scripts/biochat_demo.py",
        ]:
            assert (ROOT / p).is_file(), f"Missing: {p}"

    def test_gradio_launch_importable(self):
        from biochat.ui.biochat_ui import launch_biochat_ui
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
