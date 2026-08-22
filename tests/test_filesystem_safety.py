"""Behavior tests for filesystem-boundary helpers."""

from __future__ import annotations

import importlib
import io
import hashlib
import stat
import sys
import tempfile
import types
from pathlib import Path
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile, ZipInfo

import pytest

from biochat.tool.protocols import read_local_protocol
from biochat.utils.filesystem_safety import (
    ZipSafetyLimits,
    resolve_child_path,
    safe_extract_zip,
    verify_sha256,
)
from biochat.utils.s3_download import fetch_and_extract_archive, sync_data_lake_files


class _ArchiveResponse:
    """Small HTTP-boundary fake that streams a supplied archive payload."""

    def __init__(self, payload: bytes) -> None:
        self.headers = {"content-length": str(len(payload))}
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        del chunk_size
        yield self._payload


@pytest.fixture
def bioimaging_module(monkeypatch):
    """Import the real caller while replacing unavailable optional imaging imports."""
    nibabel = types.ModuleType("nibabel")
    simpleitk = types.ModuleType("SimpleITK")
    simpleitk.Image = type("Image", (), {})
    simpleitk.Transform = type("Transform", (), {})
    simpleitk.ImageRegistrationMethod = type("ImageRegistrationMethod", (), {})
    nnunet = types.ModuleType("nnunet")
    inference = types.ModuleType("nnunet.inference")
    predict = types.ModuleType("nnunet.inference.predict")
    predict.predict_from_folder = lambda *args, **kwargs: None
    for name, module in {
        "nibabel": nibabel,
        "SimpleITK": simpleitk,
        "nnunet": nnunet,
        "nnunet.inference": inference,
        "nnunet.inference.predict": predict,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    sys.modules.pop("biochat.tool.bioimaging", None)
    return importlib.import_module("biochat.tool.bioimaging")


def _empty_zip_payload() -> bytes:
    payload = io.BytesIO()
    with ZipFile(payload, "w"):
        pass
    return payload.getvalue()


def _zip_payload(filename: str, content: bytes) -> bytes:
    payload = io.BytesIO()
    with ZipFile(payload, "w") as zf:
        zf.writestr(filename, content)
    return payload.getvalue()


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


@pytest.mark.parametrize(
    ("task_id", "model_type"),
    [("../protected", "3d_fullres"), ("task", "../protected")],
)
def test_nnunet_model_download_rejects_identifier_path_escape(
    tmp_path: Path, monkeypatch, bioimaging_module, task_id: str, model_type: str
) -> None:
    """Interpolated model identifiers must not reach paths outside nnUNet."""
    protected_archive = tmp_path / "protected_temp.zip"
    protected_archive.write_text("do not overwrite")
    monkeypatch.setenv("nnUNet_RESULTS_FOLDER", str(tmp_path))
    monkeypatch.setattr(
        bioimaging_module.requests,
        "get",
        lambda *args, **kwargs: _ArchiveResponse(_empty_zip_payload()),
    )

    with pytest.raises(ValueError, match="outside"):
        bioimaging_module.SegmentationTool()._download_and_extract_model(task_id, model_type=model_type)

    assert protected_archive.read_text() == "do not overwrite"


def test_sync_data_lake_redownloads_existing_file_with_bad_checksum(
    tmp_path: Path, monkeypatch
) -> None:
    """Treating cached files as successful without a digest check preserves tampered data."""
    target = tmp_path / "data.txt"
    target.write_bytes(b"tampered")
    trusted = b"trusted"
    requests = []

    def get(url, **kwargs):
        requests.append((url, kwargs))
        return _ArchiveResponse(trusted)

    monkeypatch.setattr("biochat.utils.s3_download.requests.get", get)
    result = sync_data_lake_files(
        "https://example.test",
        str(tmp_path),
        ["data.txt"],
        checksums={"data.txt": hashlib.sha256(trusted).hexdigest()},
    )

    assert result == {"data.txt": True}
    assert target.read_bytes() == trusted
    assert requests == [
        ("https://example.test/data_lake/data.txt", {"stream": True, "timeout": (10, 120)})
    ]


def test_fetch_archive_rejects_declared_download_limit_before_extraction(
    tmp_path: Path, monkeypatch
) -> None:
    """A declared oversized response must not be extracted despite its archive bytes being valid."""
    payload = _zip_payload("data.txt", b"trusted")
    requests = []

    def get(url, **kwargs):
        requests.append((url, kwargs))
        return _ArchiveResponse(payload)

    monkeypatch.setattr("biochat.utils.s3_download.requests.get", get)
    destination = tmp_path / "out"
    result = fetch_and_extract_archive(
        "https://example.test/archive.zip", str(destination), max_download_bytes=1
    )

    assert result.startswith("Error: Download exceeds configured byte limit")
    assert list(destination.iterdir()) == []
    assert requests == [
        ("https://example.test/archive.zip", {"stream": True, "timeout": (10, 120)})
    ]


def test_fetch_archive_removes_temporary_file_after_streamed_limit_failure(
    tmp_path: Path, monkeypatch
) -> None:
    """An unknown-length oversized stream must leave neither archive nor extracted output behind."""
    class UnknownLengthResponse(_ArchiveResponse):
        def __init__(self) -> None:
            self.headers = {}
            self._payload = b"too-large"

    monkeypatch.setattr(
        "biochat.utils.s3_download.requests.get",
        lambda *args, **kwargs: UnknownLengthResponse(),
    )
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    destination = tmp_path / "out"

    result = fetch_and_extract_archive(
        "https://example.test/archive.zip", str(destination), max_download_bytes=1
    )

    assert result.startswith("Error: Download exceeds configured byte limit")
    assert list(destination.iterdir()) == []
    assert list(tmp_path.glob("*.zip")) == []


def test_fetch_archive_verifies_checksum_before_extraction(tmp_path: Path, monkeypatch) -> None:
    """A checksum mismatch must reject a valid ZIP before it can publish any member."""
    monkeypatch.setattr(
        "biochat.utils.s3_download.requests.get",
        lambda *args, **kwargs: _ArchiveResponse(_zip_payload("data.txt", b"trusted")),
    )
    destination = tmp_path / "out"

    result = fetch_and_extract_archive(
        "https://example.test/archive.zip", str(destination), expected_sha256="0" * 64
    )

    assert result.startswith("Error: SHA-256 mismatch")
    assert list(destination.iterdir()) == []


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


def test_safe_extract_leaves_destination_unchanged_after_late_crc_error(tmp_path: Path) -> None:
    """Writing directly to destination leaves early members behind after a later corrupt member."""
    archive = tmp_path / "corrupt.zip"
    corrupt_content = b"corrupt-member"
    with ZipFile(archive, "w") as zf:
        zf.writestr("early.txt", "early")
        zf.writestr("late.txt", corrupt_content)
    archive.write_bytes(archive.read_bytes().replace(corrupt_content, b"x" * len(corrupt_content), 1))

    destination = tmp_path / "out"
    destination.mkdir()
    preserved = destination / "preserved.txt"
    preserved.write_text("preserved")

    with pytest.raises(BadZipFile, match="CRC"):
        safe_extract_zip(archive, destination)

    assert preserved.read_text() == "preserved"
    assert not (destination / "early.txt").exists()
    assert not (destination / "late.txt").exists()


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
