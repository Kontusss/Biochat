"""Resource selector tests — new implementation + legacy adapter parity."""

from __future__ import annotations

RESOURCES = {
    "tools": [
        {"name": "query_uniprot", "description": "Query UniProt"},
        {"name": "search_pubmed", "description": "Search PubMed"},
        {"name": "run_python_repl", "description": "Run Python code"},
    ],
    "data_lake": [
        {"name": "gene_info.parquet", "description": "Gene info"},
        {"name": "gwas_catalog.pkl", "description": "GWAS results"},
    ],
    "libraries": [
        {"name": "scanpy", "description": "scRNA analysis"},
        {"name": "biopython", "description": "Bio Python"},
    ],
    "know_how": [
        {"id": "k1", "name": "Guide A", "description": "Protocol A"},
        {"id": "k2", "name": "Guide B", "description": "Protocol B"},
    ],
}


class TestParseSelectionResponse:
    def test_plain_string(self):
        from biochat.model.resource_selector import parse_selection_response

        reply = "TOOLS: [0, 2]\nDATA_LAKE: [1]\nLIBRARIES: []\nKNOW_HOW: [0, 1]"
        assert parse_selection_response(reply) == {
            "tools": [0, 2],
            "data_lake": [1],
            "libraries": [],
            "know_how": [0, 1],
        }

    def test_content_blocks_list(self):
        from biochat.model.resource_selector import parse_selection_response

        reply = [
            {"type": "text", "text": "TOOLS: [1]\n"},
            {"type": "text", "text": "DATA_LAKE: [0, 1]"},
            {"type": "tool_call", "ignored": True},
        ]
        assert parse_selection_response(reply)["tools"] == [1]
        assert parse_selection_response(reply)["data_lake"] == [0, 1]

    def test_bad_indices_skipped(self):
        from biochat.model.resource_selector import parse_selection_response

        reply = "TOOLS: [0, x, 2]\nDATA_LAKE: [not-a-number]"
        assert parse_selection_response(reply)["tools"] == [0, 2]
        assert parse_selection_response(reply)["data_lake"] == []

    def test_missing_categories_empty(self):
        from biochat.model.resource_selector import parse_selection_response

        assert parse_selection_response("TOOLS: [0]")["know_how"] == []

    def test_know_how_hyphen_variant(self):
        from biochat.model.resource_selector import parse_selection_response

        assert parse_selection_response("KNOW-HOW: [1]")["know_how"] == [1]


class TestBuildSelectionPrompt:
    def test_prompt_contains_categories_and_format(self):
        from biochat.model.resource_selector import build_selection_prompt

        prompt = build_selection_prompt("Find EGFR pathways", RESOURCES)
        assert "USER QUERY: Find EGFR pathways" in prompt
        assert "AVAILABLE TOOLS" in prompt
        assert "0. query_uniprot: Query UniProt" in prompt
        assert "TOOLS: [list of indices]" in prompt
        assert "KNOW_HOW: [list of indices]" in prompt

    def test_prompt_without_know_how(self):
        from biochat.model.resource_selector import build_selection_prompt

        prompt = build_selection_prompt("q", {k: v for k, v in RESOURCES.items()
                                             if k != "know_how"})
        assert "KNOW_HOW" not in prompt
        assert "LIBRARIES: [list of indices]" in prompt

    def test_empty_resources_formatted(self):
        from biochat.model.resource_selector import format_resources

        assert format_resources([]) == "None available"


class TestResourceSelector:
    def test_end_to_end_with_fake_llm(self):
        from biochat.model.resource_selector import ResourceSelector

        class FakeLLM:
            def invoke(self, messages):
                class Reply:
                    content = "TOOLS: [0]\nDATA_LAKE: [1]\nLIBRARIES: [0]\nKNOW_HOW: [1]"

                return Reply()

        selector = ResourceSelector()
        selected = selector.prompt_based_retrieval(
            "test query", RESOURCES, llm=FakeLLM()
        )
        assert [t["name"] for t in selected["tools"]] == ["query_uniprot"]
        assert [d["name"] for d in selected["data_lake"]] == ["gwas_catalog.pkl"]
        assert [l["name"] for l in selected["libraries"]] == ["scanpy"]
        assert [k["id"] for k in selected["know_how"]] == ["k2"]

    def test_out_of_range_indices_dropped(self):
        from biochat.model.resource_selector import ResourceSelector

        class FakeLLM:
            def invoke(self, messages):
                class Reply:
                    content = "TOOLS: [99]\nDATA_LAKE: [0]\nLIBRARIES: []"

                return Reply()

        selected = ResourceSelector().prompt_based_retrieval(
            "q", RESOURCES, llm=FakeLLM()
        )
        assert selected["tools"] == []

    def test_callable_llm_interface(self):
        from biochat.model.resource_selector import ResourceSelector

        class PlainLLM:
            def __call__(self, prompt):
                return "TOOLS: [2]\nDATA_LAKE: []\nLIBRARIES: []"

        selected = ResourceSelector().prompt_based_retrieval(
            "q", RESOURCES, llm=PlainLLM()
        )
        assert [t["name"] for t in selected["tools"]] == ["run_python_repl"]


class TestLegacyAdapter:
    def test_old_path_imports_new_class(self):
        from biochat.model.resource_selector import ResourceSelector
        from biochat.model.retriever import ToolRetriever

        assert ToolRetriever is ResourceSelector

    def test_old_class_name_works(self):
        from biochat.model.retriever import ToolRetriever

        retriever = ToolRetriever()
        assert hasattr(retriever, "prompt_based_retrieval")
