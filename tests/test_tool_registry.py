"""Tool registry tests — new implementation + legacy adapter parity."""

from __future__ import annotations


def _schema(name: str) -> dict:
    return {
        "name": name,
        "description": f"desc of {name}",
        "required_parameters": [],
    }


class TestToolRegistry:
    def test_registration_assigns_ids(self):
        from biomni.tool.registry import ToolRegistry

        reg = ToolRegistry({"mod": [_schema("a"), _schema("b")]})
        assert reg.get_id_by_name("a") == 0
        assert reg.get_id_by_name("b") == 1
        assert reg.get_name_by_id(1) == "b"
        assert [t["id"] for t in reg.tools] == [0, 1]

    def test_lookups(self):
        from biomni.tool.registry import ToolRegistry

        reg = ToolRegistry({"mod": [_schema("x")]})
        assert reg.get_tool_by_name("x")["name"] == "x"
        assert reg.get_tool_by_id(0)["description"] == "desc of x"
        assert reg.get_tool_by_name("nope") is None
        assert reg.get_tool_by_id(99) is None

    def test_invalid_schema_raises(self):
        import pytest

        from biomni.tool.registry import ToolRegistry

        reg = ToolRegistry()
        with pytest.raises(ValueError):
            reg.register_tool({"name": "no_description"})

    def test_duplicate_name_raises(self):
        import pytest

        from biomni.tool.registry import ToolRegistry

        reg = ToolRegistry({"mod": [_schema("dup")]})
        with pytest.raises(ValueError):
            reg.register_tool(_schema("dup"))

    def test_removal_updates_indexes(self):
        from biomni.tool.registry import ToolRegistry

        reg = ToolRegistry({"mod": [_schema("a"), _schema("b")]})
        assert reg.remove_tool_by_name("a") is True
        assert reg.get_tool_by_name("a") is None
        assert reg.remove_tool_by_id(1) is True
        assert reg.get_name_by_id(1) is None
        assert reg.remove_tool_by_id(42) is False

    def test_document_df(self):
        from biomni.tool.registry import ToolRegistry

        reg = ToolRegistry({"mod": [_schema("a"), _schema("b")]})
        df = reg.document_df
        assert list(df.columns) == ["docid", "document_content"]
        assert len(df) == 2
        # invalidation on registration
        reg.register_tool(_schema("c"))
        assert len(reg.document_df) == 3

    def test_pickle_roundtrip(self, tmp_path):
        import pickle

        from biomni.tool.registry import ToolRegistry

        reg = ToolRegistry({"mod": [_schema("a")]})
        path = tmp_path / "registry.pkl"
        reg.save_registry(str(path))
        loaded = ToolRegistry.load_registry(str(path))
        assert loaded.get_tool_by_name("a")["id"] == 0


class TestLegacyAdapter:
    def test_old_path_imports_new_class(self):
        from biomni.tool.registry import ToolRegistry as NewRegistry
        from biomni.tool.tool_registry import ToolRegistry as OldImport

        assert OldImport is NewRegistry

    def test_old_path_works_with_module2api_shape(self):
        from biomni.tool.tool_registry import ToolRegistry
        from biomni.utils.io_utils import load_all_tool_descriptions

        module2api = load_all_tool_descriptions()
        reg = ToolRegistry(module2api)
        assert len(reg.tools) > 100
        names = {t["name"] for t in reg.list_tools()}
        assert reg.get_tool_by_name("annotate_celltype_scRNA")["id"] is not None
