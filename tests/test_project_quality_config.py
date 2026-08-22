"""Tests for the tracked quality-gate configuration.

These pin the pre-commit and CI configuration files: they must exist,
parse as YAML, declare the mandated gates, and cover the supported
Python versions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

_REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def precommit_config() -> dict:
    return yaml.safe_load((_REPO_ROOT / ".pre-commit-config.yaml").read_text())


@pytest.fixture(scope="module")
def workflow_config() -> dict:
    return yaml.safe_load(
        (_REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    )


def test_project_quality_files_exist_and_parse(
    precommit_config: dict, workflow_config: dict
):
    assert precommit_config["repos"]
    assert workflow_config["jobs"]


def test_ci_contains_distribution_and_test_gates(workflow_config: dict):
    text = (_REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    for command in (
        "ruff check",
        "pytest",
        "python -m build",
        "test_distribution_contents",
    ):
        assert command in text


def test_ci_runs_on_supported_python_versions(workflow_config: dict):
    jobs = workflow_config["jobs"]
    versions: set[str] = set()
    for job in jobs.values():
        matrix = job.get("strategy", {}).get("matrix", {})
        value = matrix.get("python-version")
        if isinstance(value, list):
            versions.update(str(v) for v in value)
        elif value is not None:
            versions.add(str(value))
    assert {"3.11", "3.12"} <= versions


def test_ci_installs_dev_extra_for_tooling(workflow_config: dict):
    text = (_REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "[dev," in text or 'pip install -e ".[dev]' in text


def test_ci_has_clean_wheel_install_smoke(workflow_config: dict):
    text = (_REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "venv" in text  # smoke installs the wheel into a fresh environment
    assert "import biochat" in text


def test_precommit_enforces_ruff_check_and_format(precommit_config: dict):
    hook_ids = [
        hook["id"]
        for repo in precommit_config["repos"]
        for hook in repo.get("hooks", [])
    ]
    assert "ruff" in hook_ids
    assert "ruff-format" in hook_ids
    assert "trailing-whitespace" in hook_ids
    assert "end-of-file-fixer" in hook_ids
    assert "check-yaml" in hook_ids
