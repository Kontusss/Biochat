"""Behavioral tests for canonical runtime settings and legacy conversion."""

from biochat.config import BiochatConfig
from biochat.core.settings import BiochatSettings


def test_host_execution_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("BIOCHAT_ALLOW_HOST_CODE_EXECUTION", raising=False)
    assert BiochatSettings().allow_host_code_execution is False


def test_unauthenticated_remote_access_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("BIOCHAT_ALLOW_UNAUTHENTICATED_REMOTE", raising=False)
    assert BiochatSettings().allow_unauthenticated_remote is False


def test_security_flags_follow_boolean_environment_overrides(monkeypatch):
    monkeypatch.setenv("BIOCHAT_ALLOW_HOST_CODE_EXECUTION", "true")
    monkeypatch.setenv("BIOCHAT_ALLOW_UNAUTHENTICATED_REMOTE", "1")

    settings = BiochatSettings()

    assert settings.allow_host_code_execution is True
    assert settings.allow_unauthenticated_remote is True


def test_project_version_uses_package_version():
    from biochat import __version__
    from biochat.core.settings import PROJECT_VERSION

    assert PROJECT_VERSION == __version__


def test_mutable_legacy_config_converts_to_canonical_settings():
    config = BiochatConfig(llm="gpt-4o-mini", path="./legacy-data", source="OpenAI")
    config.timeout_seconds = 1200
    config.commercial_mode = True

    settings = config.to_settings()

    assert settings.llm_model == "gpt-4o-mini"
    assert settings.data_path == "./legacy-data"
    assert settings.llm_source == "OpenAI"
    assert settings.timeout_seconds == 1200
    assert settings.commercial_mode is True
