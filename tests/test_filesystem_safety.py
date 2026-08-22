"""Behavior tests for filesystem-boundary helpers."""

from __future__ import annotations

import stat
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest

from biochat.tool.protocols import read_local_protocol
from biochat.utils.filesystem_safety import (
    ZipSafetyLimits,
    resolve_child_path,
    safe_extract_zip,
    verify_sha256,
)


def test_resolve_child_path_rejects_parent_escape(tmp_path: Path) -> None:
    """Removing containment validation would expose files outside the root."""
    with pytest.raises(ValueError, match="outside"):
        resolve_child_path(tmp_path / "root", "..", "secret.txt")


def test_resolve_child_path_returns_nested_child(tmp_path: Path) -> None:
    """A contained path remains available to callers without pre-creating it."""
    root = tmp_path / "root"
    assert resolve_child_path(root, "nested", "file.txt") == root / "nested" / "file.txt"


def test_protocol_reader_rejects_source_traversal() -> None:
    """Treating source as a raw path would let protocol reads escape their catalog."""
    with pytest.raises(ValueError, match="source"):
        read_local_protocol("pyproject.toml", source="../../..")


def test_safe_extract_rejects_zip_slip(tmp_path: Path) -> None:
    """Extracting a parent-traversal member would write beyond destination."""
    archive = tmp_path / "bad.zip"
    with ZipFile(archive, "w") as zf:
        zf.writestr("../escaped.txt", "secret")

    with pytest.raises(ValueError, match="outside"):
        safe_extract_zip(archive, tmp_path / "out")

    assert not (tmp_path / "escaped.txt").exists()


def test_safe_extract_rejects_symbolic_link_member(tmp_path: Path) -> None:
    """A symlink member could redirect later archive writes outside destination."""
    archive = tmp_path / "symlink.zip"
    link = ZipInfo("link")
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with ZipFile(archive, "w") as zf:
        zf.writestr(link, "../escaped.txt")

    with pytest.raises(ValueError, match="symbolic link"):
        safe_extract_zip(archive, tmp_path / "out")


def test_safe_extract_rejects_member_count_limit(tmp_path: Path) -> None:
    """Ignoring member-count limits permits archives to exhaust filesystem resources."""
    archive = tmp_path / "many.zip"
    with ZipFile(archive, "w") as zf:
        zf.writestr("one.txt", "one")
        zf.writestr("two.txt", "two")

    with pytest.raises(ValueError, match="members"):
        safe_extract_zip(archive, tmp_path / "out", ZipSafetyLimits(max_members=1))


def test_safe_extract_rejects_total_size_limit(tmp_path: Path) -> None:
    """Ignoring total uncompressed size permits decompression-bomb expansion."""
    archive = tmp_path / "large.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("large.bin", b"x" * 20)

    limits = ZipSafetyLimits(max_members=10, max_member_bytes=100, max_total_bytes=10)
    with pytest.raises(ValueError, match="total"):
        safe_extract_zip(archive, tmp_path / "out", limits=limits)


def test_safe_extract_rejects_member_size_limit(tmp_path: Path) -> None:
    """Ignoring per-member limits permits one expanded member to exhaust storage."""
    archive = tmp_path / "large-member.zip"
    with ZipFile(archive, "w") as zf:
        zf.writestr("large.bin", b"x" * 20)

    limits = ZipSafetyLimits(max_members=10, max_member_bytes=10, max_total_bytes=100)
    with pytest.raises(ValueError, match="member"):
        safe_extract_zip(archive, tmp_path / "out", limits=limits)


def test_safe_extract_writes_contained_members(tmp_path: Path) -> None:
    """Replacing extractall must preserve valid nested-file extraction."""
    archive = tmp_path / "valid.zip"
    with ZipFile(archive, "w") as zf:
        zf.writestr("nested/data.txt", "contents")

    extracted = safe_extract_zip(archive, tmp_path / "out")

    assert extracted == [tmp_path / "out" / "nested" / "data.txt"]
    assert (tmp_path / "out" / "nested" / "data.txt").read_text() == "contents"


def test_verify_sha256_rejects_mismatch(tmp_path: Path) -> None:
    """Skipping digest comparison would accept a tampered downloaded archive."""
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"trusted payload")

    with pytest.raises(ValueError, match="SHA-256"):
        verify_sha256(payload, "0" * 64)


def test_verify_sha256_accepts_matching_digest(tmp_path: Path) -> None:
    """Valid checksums remain accepted by optional download verification."""
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"trusted payload")

    verify_sha256(payload, "31b82bfc1d683791a3ecf4342690922db1f372dec048889d43529292d1431cde")
