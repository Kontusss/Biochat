"""Tool profile tests — minimal vs full runtime profiles."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestProfileManifest:
    def test_manifest_lists_only_valid_modules(self):
        from biochat.tool.profiles import MINIMAL_TOOL_MODULES
        from biochat.utils.io_utils import _TOOL_FIELDS

        all_modules = {f"biochat.tool.{f}" for f in _TOOL_FIELDS}
        assert MINIMAL_TOOL_MODULES <= all_modules
        assert "biochat.tool.antibody_design" in MINIMAL_TOOL_MODULES

    def test_minimal_is_proper_subset_of_full(self):
        from biochat.utils.io_utils import load_all_tool_descriptions

        full = load_all_tool_descriptions(profile="full")
        minimal = load_all_tool_descriptions(profile="minimal")
        assert set(minimal) < set(full)
        assert len(full) == 23
        assert 2 <= len(minimal) < len(full)


class TestToolRegistryProfiles:
    def test_full_profile_registers_every_tool(self):
        from biochat.tool.registry import ToolRegistry
        from biochat.utils.io_utils import load_all_tool_descriptions

        registry = ToolRegistry(load_all_tool_descriptions(profile="full"),
                                profile="full")
        assert len(registry.tools) == 226

    def test_minimal_profile_registers_only_manifest_modules(self):
        from biochat.tool.profiles import MINIMAL_TOOL_MODULES
        from biochat.tool.registry import ToolRegistry
        from biochat.utils.io_utils import load_all_tool_descriptions

        module2api = load_all_tool_descriptions(profile="minimal")
        registry = ToolRegistry(module2api, profile="minimal")
        assert set(module2api) == MINIMAL_TOOL_MODULES
        expected = sum(len(v) for v in module2api.values())
        assert len(registry.tools) == expected
        assert len(registry.tools) < 226

    def test_invalid_profile_falls_back_to_full(self):
        from biochat.tool.registry import ToolRegistry

        registry = ToolRegistry({"mod": [
            {"name": "t", "description": "d", "required_parameters": []},
        ]}, profile="bogus")
        assert registry.profile == "full"
        assert len(registry.tools) == 1


class TestAntibodyPipelineInMinimal:
    def test_antibody_tools_available_in_minimal(self):
        from biochat.tool.registry import ToolRegistry
        from biochat.utils.io_utils import load_all_tool_descriptions

        registry = ToolRegistry(load_all_tool_descriptions(profile="minimal"),
                                profile="minimal")
        for name in ("design_vh_only_antibodies", "score_and_rank_candidates"):
            assert registry.get_tool_by_name(name) is not None, name

    def test_antibody_package_imports(self):
        from biochat.tool.antibody_design import (
            design_vh_only_antibodies,
            score_and_rank_candidates,
        )
        assert callable(design_vh_only_antibodies)
        assert callable(score_and_rank_candidates)

    def test_database_and_protocol_tools_available(self):
        from biochat.tool.registry import ToolRegistry
        from biochat.utils.io_utils import load_all_tool_descriptions

        registry = ToolRegistry(load_all_tool_descriptions(profile="minimal"),
                                profile="minimal")
        assert registry.get_tool_by_name("query_uniprot") is not None
        assert registry.get_tool_by_name("search_protocols") is not None
        assert registry.get_tool_by_name("run_python_repl") is not None


class TestSettingsProfile:
    def test_default_is_full(self):
        from biochat.core.settings import BiochatSettings

        assert BiochatSettings(tool_profile=None).tool_profile == "full"

    def test_minimal_accepted_and_normalised(self):
        from biochat.core.settings import BiochatSettings

        assert BiochatSettings(tool_profile="MINIMAL").tool_profile == "minimal"
        assert BiochatSettings(tool_profile="bogus").tool_profile == "full"

    def test_env_var_override(self):
        from biochat.core.settings import BiochatSettings

        os.environ["BIOCHAT_TOOL_PROFILE"] = "minimal"
        try:
            assert BiochatSettings().tool_profile == "minimal"
        finally:
            del os.environ["BIOCHAT_TOOL_PROFILE"]


class TestCompetitionDemo:
    def test_demo_quick_uses_minimal_profile(self):
        env = dict(os.environ)
        env.pop("BIOCHAT_TOOL_PROFILE", None)
        result = subprocess.run(
            [sys.executable, "scripts/demo_biochat_competition.py", "--quick"],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, result.stderr[-800:]
        assert "Demo passed" in result.stdout
        assert "active profile: minimal" in result.stdout

    def test_demo_respects_full_profile_env(self):
        env = dict(os.environ)
        env["BIOCHAT_TOOL_PROFILE"] = "full"
        result = subprocess.run(
            [sys.executable, "scripts/demo_biochat_competition.py", "--quick"],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, result.stderr[-800:]
        assert "active profile: full" in result.stdout
