"""Knowledge registry tests — new architecture + legacy adapter parity."""

from __future__ import annotations


class TestRegistry:
    def test_default_registry_loads_bundled_docs(self):
        from biochat.knowledge import KnowledgeRegistry

        reg = KnowledgeRegistry()
        assert "sgRNA_design_guide" in reg.documents
        assert "single_cell_annotation" in reg.documents

    def test_document_shape_for_agent(self):
        """A1 relies on these exact keys."""
        from biochat.knowledge import KnowledgeRegistry

        reg = KnowledgeRegistry()
        doc = reg.documents["single_cell_annotation"]
        for key in ("id", "name", "description", "content",
                    "content_without_metadata", "filepath", "metadata"):
            assert key in doc, f"missing key: {key}"

    def test_metadata_parsing(self):
        from biochat.knowledge import KnowledgeRegistry

        reg = KnowledgeRegistry()
        metadata = reg.documents["single_cell_annotation"]["metadata"]
        assert metadata["short_description"].startswith("Best practices")
        assert metadata["license"] == "CC BY 4.0"
        assert "✅" in metadata["commercial_use"]

    def test_content_without_metadata_excludes_block(self):
        from biochat.knowledge import KnowledgeRegistry

        reg = KnowledgeRegistry()
        body = reg.documents["single_cell_annotation"]["content_without_metadata"]
        assert "## Metadata" not in body
        assert "Short Description" not in body
        assert "## Overview" in body

    def test_custom_document_roundtrip(self):
        from biochat.knowledge import KnowledgeRegistry

        reg = KnowledgeRegistry()
        reg.add_custom_document("custom_1", "My Doc", "desc", "content", {"license": "MIT"})
        doc = reg.get_document_by_id("custom_1")
        assert doc["name"] == "My Doc"
        assert doc["content_without_metadata"] == "content"
        assert reg.get_document_metadata("custom_1")["license"] == "MIT"

        reg.remove_document("custom_1")
        assert reg.get_document_by_id("custom_1") is None

    def test_summaries(self):
        from biochat.knowledge import KnowledgeRegistry

        reg = KnowledgeRegistry()
        summaries = reg.get_document_summaries()
        assert {"id", "name", "description"} == set(summaries[0].keys())
        assert all("content" not in s for s in summaries)

    def test_exclude_non_commercial(self):
        from biochat.knowledge import KnowledgeRegistry

        reg = KnowledgeRegistry()
        reg.add_custom_document(
            "free_doc", "Free", "d", "c", {"commercial_use": "✅ Allowed"},
        )
        reg.add_custom_document(
            "paid_doc", "Paid", "d", "c", {"commercial_use": "❌ Not Allowed"},
        )
        excluded = reg.exclude_non_commercial()
        assert excluded == ["paid_doc"]
        assert "paid_doc" not in reg.documents
        assert "free_doc" in reg.documents

    def test_reload(self):
        from biochat.knowledge import KnowledgeRegistry

        reg = KnowledgeRegistry()
        reg.add_custom_document("temp", "Temp", "d", "c")
        reg.reload()
        assert "temp" not in reg.documents
        assert "sgRNA_design_guide" in reg.documents


class TestLegacyAdapter:
    def test_old_import_path_still_works(self):
        from biochat.know_how import KnowHowLoader
        from biochat.knowledge import KnowledgeRegistry

        loader = KnowHowLoader()
        assert isinstance(loader, KnowledgeRegistry)
        assert "sgRNA_design_guide" in loader.documents
        assert "single_cell_annotation" in loader.documents

    def test_old_constructor_with_dir(self):
        import os
        from pathlib import Path

        from biochat.know_how import KnowHowLoader

        docs_dir = Path(__file__).resolve().parents[1] / "biochat" / "knowledge" / "docs"
        loader = KnowHowLoader(know_how_dir=str(docs_dir))
        assert os.path.isdir(docs_dir)
        assert loader.documents

    def test_document_dicts_match_between_paths(self):
        """Adapter and registry expose identical document data."""
        from biochat.know_how import KnowHowLoader
        from biochat.knowledge import KnowledgeRegistry

        old = KnowHowLoader().documents
        new = KnowledgeRegistry().documents
        assert set(old) == set(new)
        for doc_id in old:
            assert old[doc_id]["content"] == new[doc_id]["content"]
            assert old[doc_id]["content_without_metadata"] == new[doc_id]["content_without_metadata"]
            assert old[doc_id]["metadata"] == new[doc_id]["metadata"]
