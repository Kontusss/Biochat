"""
Biochat UI Smoke Tests

Verifies that Biochat additions are importable, backward-compatible,
and correctly configured — without launching any servers.

These tests ensure competition readiness:
- All Biochat modules import cleanly
- Original Biomni API surface is preserved
- Configuration constants are consistent
- Theme tokens are complete
"""

from __future__ import annotations

import inspect


# ═══════════════════════════════════════════════════════════════
# BIOCHAT UI MODULE IMPORTS
# ═══════════════════════════════════════════════════════════════

class TestBiochatUIImports:
    """Verify all Biochat UI modules import correctly."""

    def test_create_biochat_ui_importable(self):
        """create_biochat_ui is importable and has correct signature."""
        from biomni.ui.biochat_ui import create_biochat_ui
        sig = inspect.signature(create_biochat_ui)
        params = list(sig.parameters.keys())
        assert "agent" in params
        assert "thread_id" in params
        assert "require_verification" in params

    def test_import_biomni_ui(self):
        """biomni.ui package imports."""
        import biomni.ui
        assert hasattr(biomni.ui, "BiochatTheme")
        assert hasattr(biomni.ui, "launch_biochat_ui")
        assert hasattr(biomni.ui, "launch_biochat_about")

    def test_import_biochat_theme(self):
        """BiochatTheme class and tokens."""
        from biomni.ui.biochat_theme import BiochatTheme, get_biochat_theme
        assert BiochatTheme is not None

        # get_biochat_theme may return None if gradio not installed
        theme = get_biochat_theme()
        # Just verify it's callable; Gradio may or may not be installed
        assert theme is not None or theme is None  # tautology, just checking no exception

    def test_import_biochat_ui_function(self):
        """launch_biochat_ui is importable and has correct signature."""
        from biomni.ui.biochat_ui import launch_biochat_ui
        sig = inspect.signature(launch_biochat_ui)
        params = list(sig.parameters.keys())
        assert "agent" in params
        assert "thread_id" in params
        assert "share" in params
        assert "server_name" in params
        assert "require_verification" in params

    def test_import_biochat_about_function(self):
        """launch_biochat_about is importable and has correct signature."""
        from biomni.ui.biochat_about import launch_biochat_about
        sig = inspect.signature(launch_biochat_about)
        params = list(sig.parameters.keys())
        assert "server_name" in params
        assert "share" in params

    def test_import_biochat_config(self):
        """biochat_config module is importable."""
        import biomni.biochat_config as cfg
        assert cfg.PROJECT_NAME == "Biochat"
        assert cfg.PROJECT_VERSION == "2.0.0"
        assert cfg.PROJECT_ENGINE == "Biomni"
        assert cfg.PROJECT_LICENSE == "Apache-2.0"


# ═══════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY
# ═══════════════════════════════════════════════════════════════

class TestBackwardCompatibility:
    """Verify that Biochat changes do not break the original Biomni API."""

    def test_agent_class_preserved(self):
        """A1 agent class still importable."""
        from biomni.agent import A1
        assert A1 is not None

    def test_launch_gradio_demo_exists(self):
        """Original launch_gradio_demo method still present."""
        from biomni.agent import A1
        assert hasattr(A1, "launch_gradio_demo")
        sig = inspect.signature(A1.launch_gradio_demo)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "thread_id" in params
        assert "share" in params
        assert "server_name" in params
        assert "require_verification" in params

    def test_launch_biochat_ui_exists(self):
        """New launch_biochat_ui method is present alongside original."""
        from biomni.agent import A1
        assert hasattr(A1, "launch_biochat_ui")
        sig = inspect.signature(A1.launch_biochat_ui)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "thread_id" in params
        assert "share" in params
        assert "server_name" in params
        assert "require_verification" in params

    def test_biomni_config_class_unchanged(self):
        """BiomniConfig class name and attributes preserved."""
        from biomni.config import BiomniConfig, default_config
        assert BiomniConfig is not None
        assert hasattr(default_config, "llm")
        assert hasattr(default_config, "timeout_seconds")
        assert hasattr(default_config, "path")
        assert hasattr(default_config, "commercial_mode")

    def test_package_name_unchanged(self):
        """Package is still named biomni (internal name preserved)."""
        import biomni
        assert hasattr(biomni, "__version__")

    def test_env_var_aliases(self):
        """BIOCHAT_* env vars are checked alongside BIOMNI_*."""
        import os
        from biomni.config import BiomniConfig

        # Set BIOCHAT_* var only
        os.environ["BIOCHAT_TIMEOUT_SECONDS"] = "777"
        config = BiomniConfig()
        assert config.timeout_seconds == 777
        del os.environ["BIOCHAT_TIMEOUT_SECONDS"]

        # Set BIOMNI_* var only (backward compat)
        os.environ["BIOMNI_TIMEOUT_SECONDS"] = "999"
        config = BiomniConfig()
        assert config.timeout_seconds == 999
        del os.environ["BIOMNI_TIMEOUT_SECONDS"]

        # Both set: BIOCHAT_* takes priority
        os.environ["BIOMNI_TIMEOUT_SECONDS"] = "999"
        os.environ["BIOCHAT_TIMEOUT_SECONDS"] = "777"
        config = BiomniConfig()
        assert config.timeout_seconds == 777
        del os.environ["BIOMNI_TIMEOUT_SECONDS"]
        del os.environ["BIOCHAT_TIMEOUT_SECONDS"]


# ═══════════════════════════════════════════════════════════════
# CONFIGURATION INTEGRITY
# ═══════════════════════════════════════════════════════════════

class TestBiochatConfigIntegrity:
    """Verify biochat_config.py contains valid, consistent constants."""

    def test_project_identity(self):
        """Project identity fields."""
        import biomni.biochat_config as cfg
        assert isinstance(cfg.PROJECT_NAME, str)
        assert len(cfg.PROJECT_NAME) > 0
        assert isinstance(cfg.PROJECT_VERSION, str)
        assert isinstance(cfg.PROJECT_ENGINE, str)

    def test_theme_tokens(self):
        """Theme token dictionary is complete."""
        import biomni.biochat_config as cfg
        required_keys = [
            "primary_color", "primary_hover", "background",
            "sidebar_bg", "card_bg", "text_primary", "text_secondary",
            "text_muted", "border", "border_radius",
            "font_family", "font_mono", "green", "amber", "red",
        ]
        for key in required_keys:
            assert key in cfg.THEME, f"Missing theme token: {key}"
            assert cfg.THEME[key], f"Empty theme token: {key}"

    def test_capabilities_registry(self):
        """Capability registry has required fields."""
        import biomni.biochat_config as cfg
        assert len(cfg.CAPABILITIES) >= 8
        for domain, cap in cfg.CAPABILITIES.items():
            assert "name" in cap, f"Missing 'name' in capability: {domain}"
            assert "icon" in cap, f"Missing 'icon' in capability: {domain}"
            assert "description" in cap, f"Missing 'description' in capability: {domain}"

    def test_quick_actions(self):
        """Quick actions are well-formed."""
        import biomni.biochat_config as cfg
        assert len(cfg.QUICK_ACTIONS) >= 4
        for action in cfg.QUICK_ACTIONS:
            assert "label" in action
            assert "query" in action
            assert len(action["label"]) > 0
            assert len(action["query"]) > 0

    def test_safety_policy(self):
        """Safety policy flags are boolean."""
        import biomni.biochat_config as cfg
        assert isinstance(cfg.SAFETY_POLICY["code_execution_warning"], bool)
        assert isinstance(cfg.SAFETY_POLICY["requires_sandbox"], bool)
        assert isinstance(cfg.SAFETY_POLICY["commercial_mode_supported"], bool)
        assert isinstance(cfg.SAFETY_POLICY["default_timeout_seconds"], int)
        assert cfg.SAFETY_POLICY["default_timeout_seconds"] > 0


# ═══════════════════════════════════════════════════════════════
# THEME CONSISTENCY
# ═══════════════════════════════════════════════════════════════

class TestThemeConsistency:
    """Verify BiochatTheme and biochat_config THEME tokens are consistent."""

    def test_theme_tokens_match_css(self):
        """Theme token values match CSS variable definitions."""
        from biomni.ui.biochat_theme import BiochatTheme

        assert BiochatTheme.BG_PRIMARY == "#f7f8fb"
        assert BiochatTheme.ACCENT == "#4f46e5"
        assert BiochatTheme.RADIUS == "14px"
        assert BiochatTheme.GREEN == "#16a34a"
        assert BiochatTheme.AMBER == "#f59e0b"
        assert BiochatTheme.RED == "#dc2626"
        assert BiochatTheme.BORDER_SOLID == "#e5e7eb"

    def test_custom_css_not_empty(self):
        """Custom CSS string is non-empty and contains key ProtChat-style classes."""
        from biomni.ui.biochat_theme import BiochatTheme

        css = BiochatTheme.CUSTOM_CSS
        assert len(css) > 2000  # Substantial CSS block with all components

        # Shell & layout
        assert ".biochat-shell" in css
        assert ".biochat-main" in css
        assert ".biochat-header" in css
        assert ".biochat-sidebar" in css
        assert ".biochat-content" in css
        assert ".biochat-chat-panel" in css

        # Cards & containers
        assert ".biochat-card" in css or "--bc-card" in css
        assert ".biochat-welcome" in css

        # Status badges
        assert ".biochat-status-badge" in css
        assert ".bc-ok" in css
        assert ".bc-warn" in css
        assert ".bc-off" in css

        # Input & buttons
        assert ".biochat-input-row" in css
        assert ".biochat-send-btn" in css
        assert ".biochat-example-btn" in css

        # Footer & attribution
        assert ".biochat-footer-bar" in css
        assert ".biochat-attribution" in css

        # Chatbot styling
        assert ".biochat-chatbot" in css

    def test_config_theme_matches_class_theme(self):
        """biochat_config THEME dict values match BiochatTheme class attributes."""
        from biomni.ui.biochat_theme import BiochatTheme
        import biomni.biochat_config as cfg

        assert cfg.THEME["primary_color"] == BiochatTheme.ACCENT
        assert cfg.THEME["primary_hover"] == BiochatTheme.ACCENT_HOVER
        assert cfg.THEME["background"] == BiochatTheme.BG_PRIMARY
        assert cfg.THEME["card_bg"] == BiochatTheme.BG_CARD
        assert cfg.THEME["border_radius"] == BiochatTheme.RADIUS
        assert cfg.THEME["green"] == BiochatTheme.GREEN
        assert cfg.THEME["amber"] == BiochatTheme.AMBER
        assert cfg.THEME["red"] == BiochatTheme.RED


# ═══════════════════════════════════════════════════════════════
# GRADIO BLOCKS BUILD (no server launch)
# ═══════════════════════════════════════════════════════════════

class TestBiochatUIBuild:
    """Verify the Gradio Blocks object builds without runtime errors.

    Does NOT call demo.launch() — only constructs the UI object.
    """

    def test_create_biochat_ui_builds_blocks(self):
        """create_biochat_ui returns a Gradio Blocks object without launching."""
        from biomni.ui.biochat_ui import create_biochat_ui

        class DummyAgent:
            main_history_copy = []
            use_tool_retriever = False

            def _prepare_resources_for_retrieval(self, text):
                return None

        demo = create_biochat_ui(agent=DummyAgent())
        assert demo is not None
        assert hasattr(demo, "launch"), "Returned object must have .launch() method"
        # Do NOT call demo.launch() — this test only verifies construction


# ═══════════════════════════════════════════════════════════════
# LICENSE & ATTRIBUTION PRESERVATION
# ═══════════════════════════════════════════════════════════════

class TestLicensePreservation:
    """Verify attribution and license files are intact."""

    def test_license_file_exists(self):
        """LICENSE file exists and is Apache 2.0."""
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        license_path = os.path.join(root, "LICENSE")
        assert os.path.exists(license_path), "LICENSE file missing!"

        with open(license_path) as f:
            content = f.read()
        assert "Apache License" in content
        assert "Version 2.0" in content

    def test_license_info_exists(self):
        """license_info.md exists and describes data sources."""
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        info_path = os.path.join(root, "license_info.md")
        assert os.path.exists(info_path), "license_info.md missing!"

        with open(info_path) as f:
            content = f.read()
        assert "Biomni Data Source License Information" in content

    def test_readme_has_attribution(self):
        """README contains Biochat attribution to Biomni."""
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        readme_path = os.path.join(root, "README.md")
        assert os.path.exists(readme_path), "README.md missing!"

        with open(readme_path) as f:
            content = f.read()
        assert "## Attribution" in content
        assert "Built on top of" in content or "Built on Biomni" in content
        assert "Biomni" in content
        assert "Biochat" in content

    def test_submission_notes_exist(self):
        """docs/biochat_submission_notes.md exists."""
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        notes_path = os.path.join(root, "docs", "biochat_submission_notes.md")
        assert os.path.exists(notes_path), "biochat_submission_notes.md missing!"
