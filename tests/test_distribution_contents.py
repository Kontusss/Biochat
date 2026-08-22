"""Distribution-content tests: the built wheel must be complete and clean.

The session fixture builds one wheel via ``python -m build`` and the
tests assert required runtime resources are present while repository
archives and development trees stay out.

Run these serially (not under pytest-xdist): the fixture mutates the
shared ``build/`` cache directory. Build isolation downloads setuptools
and wheel from PyPI, so offline environments need ``--no-isolation``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Runtime resources that MUST ship inside the wheel.
REQUIRED = {
    "biochat/environment/catalog.yaml",
    "biochat/tool/tool_description/catalog.yaml",
    "biochat/knowledge/docs/sgRNA_design_guide.md",
    "biochat/tool/antibody_design/models/cdrh3_vae_model_best.pth",
}

# Dependency extras the package must declare.
REQUIRED_EXTRAS = ("streamlit", "gradio", "providers", "full-tools", "dev")


@pytest.fixture(scope="session")
def built_wheel(tmp_path_factory):
    # setuptools reuses build/lib without cleaning; stale trees from older
    # builds would leak forbidden paths into the fresh wheel.
    shutil.rmtree(_REPO_ROOT / "build", ignore_errors=True)
    output = tmp_path_factory.mktemp("wheel")
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(output)],
        check=True,
        cwd=_REPO_ROOT,
    )
    wheels = list(output.glob("biochat-*.whl"))
    assert len(wheels) == 1
    return wheels[0]


def _wheel_names(wheel: Path) -> set[str]:
    with zipfile.ZipFile(wheel) as zf:
        return set(zf.namelist())


def _wheel_metadata(wheel: Path) -> str:
    with zipfile.ZipFile(wheel) as zf:
        meta_name = next(n for n in zf.namelist() if n.endswith(".dist-info/METADATA"))
        return zf.read(meta_name).decode("utf-8")


def test_wheel_contains_runtime_resources_and_excludes_repository_archives(built_wheel):
    names = _wheel_names(built_wheel)
    missing = REQUIRED - names
    assert not missing, f"required runtime resources missing from wheel: {sorted(missing)}"
    assert not any(name.startswith("third_party/") for name in names)
    assert not any(name.startswith("scripts/") for name in names)
    assert not any(name.startswith("tutorials/") for name in names)
    assert not any(name.startswith("docs/") for name in names)


def test_wheel_ships_schema_pickles_and_protocol_resources(built_wheel):
    names = _wheel_names(built_wheel)
    assert any(name.startswith("biochat/tool/schema_db/") and name.endswith(".pkl") for name in names), (
        "schema pickle database missing from wheel"
    )
    assert any(name.startswith("biochat/tool/protocols/") and name.endswith(".txt") for name in names), (
        "bundled protocol resources missing from wheel"
    )


def test_wheel_declares_all_documented_dependency_extras(built_wheel):
    metadata = _wheel_metadata(built_wheel)
    for extra in REQUIRED_EXTRAS:
        assert f"Provides-Extra: {extra}" in metadata, f"missing extra: {extra}"


def test_wheel_version_matches_canonical_source(built_wheel):
    # Parse the checkout's version file directly so an unrelated installed
    # copy of biochat can never satisfy this assertion.
    import re

    source = (_REPO_ROOT / "biochat" / "version.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"(.*?)"', source)
    assert match, "cannot parse canonical version from biochat/version.py"
    expected = match.group(1)

    assert built_wheel.name.startswith(f"biochat-{expected}-")
    metadata = _wheel_metadata(built_wheel)
    assert f"Version: {expected}" in metadata
