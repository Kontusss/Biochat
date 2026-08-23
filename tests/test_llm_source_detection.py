"""Behavioral tests for LLM provider auto-detection."""

import pytest

from biochat.llm.source_detector import detect_llm_source


@pytest.mark.parametrize("model", ["deepseek-chat", "qwen-plus", "llama-3-custom"])
def test_base_url_routes_openai_compatible_models_to_custom(model):
    """A caller-supplied endpoint takes precedence over model-name heuristics."""
    assert detect_llm_source(model, "https://example.test/v1") == "Custom"


def test_model_name_detection_remains_for_no_base_url():
    """Known local model names retain their provider inference without an endpoint."""
    assert detect_llm_source("deepseek-r1") == "Ollama"
