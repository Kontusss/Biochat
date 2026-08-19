"""Tool-description catalog tests — adapters must match the upstream data."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "third_party" / "biomni_upstream_reference" / "biomni"
sys.path.insert(0, str(ROOT))


def _reference_description(field: str) -> list:
    """Import the vendored upstream reference module and return its data."""
    path = REFERENCE / "tool" / "tool_description" / f"{field}.py"
    spec = importlib.util.spec_from_file_location(f"ref_tool_desc_{field}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.description


class TestAdapterEquivalence:
    def test_all_fields_match_upstream_reference(self):
        from biomni.utils.io_utils import _TOOL_FIELDS

        mismatches = []
        checked = 0
        for field in _TOOL_FIELDS:
            ref_path = REFERENCE / "tool" / "tool_description" / f"{field}.py"
            if not ref_path.exists():
                continue  # Biochat-original field (no upstream counterpart)
            checked += 1
            ref = _reference_description(field)
            adapter = importlib.import_module(
                f"biomni.tool.tool_description.{field}"
            )
            if adapter.description != ref:
                mismatches.append(field)
        assert checked >= 20, f"expected >=20 upstream fields, checked {checked}"
        assert not mismatches, f"fields with data drift: {mismatches}"

    def test_dynamic_import_contract_preserved(self):
        """read_module2api imports these modules via importlib — each must
        still expose a ``description`` list attribute."""
        from biomni.utils.io_utils import load_all_tool_descriptions

        module2api = load_all_tool_descriptions()
        assert "biomni.tool.genomics" in module2api
        assert isinstance(module2api["biomni.tool.genomics"], list)
        assert len(module2api) >= 20
        for module_key, entries in module2api.items():
            assert isinstance(entries, list) and entries, module_key
            for entry in entries:
                assert isinstance(entry, dict)
                assert "name" in entry and "description" in entry

    def test_catalog_loader_raises_on_unknown_field(self):
        import pytest

        from biomni.tool.tool_description._catalog_loader import (
            load_tool_description,
        )

        with pytest.raises(KeyError):
            load_tool_description("does_not_exist")
