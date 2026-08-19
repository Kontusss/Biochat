"""Environment catalog tests — adapters must match the upstream data exactly."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "third_party" / "biomni_upstream_reference" / "biomni"


def _load_reference_module(name: str):
    """Import a vendored upstream reference module from its file path."""
    path = REFERENCE / name
    spec = importlib.util.spec_from_file_location(f"ref_{name.replace('/', '_')}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestAdapterEquivalence:
    def test_full_view_matches_upstream_env_desc(self):
        ref = _load_reference_module("env_desc.py")
        from biochat.env_desc import data_lake_dict, library_content_dict

        assert data_lake_dict == ref.data_lake_dict
        assert library_content_dict == ref.library_content_dict

    def test_commercial_view_matches_upstream_env_desc_cm(self):
        ref = _load_reference_module("env_desc_cm.py")
        from biochat.env_desc_cm import data_lake_dict, library_content_dict

        assert data_lake_dict == ref.data_lake_dict
        assert library_content_dict == ref.library_content_dict

    def test_cm_is_subset_of_full(self):
        from biochat.env_desc import data_lake_dict, library_content_dict
        from biochat.env_desc_cm import data_lake_dict as dl_cm
        from biochat.env_desc_cm import library_content_dict as lib_cm

        assert set(dl_cm) <= set(data_lake_dict)
        assert set(lib_cm) <= set(library_content_dict)


class TestCatalogMetadata:
    def test_catalog_loads_and_filters(self):
        from biochat.environment import EnvironmentCatalog

        catalog = EnvironmentCatalog()
        assert len(catalog.data_lake) == 76
        assert len(catalog.libraries) == 113
        assert catalog.data_lake_dict_cm == {
            e.name: e.description
            for e in catalog.data_lake
            if e.commercial_allowed
        }

    def test_license_metadata_present(self):
        from biochat.environment import EnvironmentCatalog

        catalog = EnvironmentCatalog()
        assert catalog.commercial_allowed("BindingDB_All_202409.tsv") is False
        note = catalog.license_note("ddinter_antineoplastic.csv")
        assert note and "CC BY-NC-SA" in note
        assert catalog.commercial_allowed("gene_info.parquet") is True

    def test_schema_fields(self):
        from biochat.environment import EnvironmentCatalog

        catalog = EnvironmentCatalog()
        entry = catalog.data_lake[0]
        assert entry.name and entry.description
        assert isinstance(entry.commercial_allowed, bool)
