"""Helpers for keeping archive and file operations within explicit roots."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import shutil
import stat
import tempfile
from typing import Union
from zipfile import ZipFile, ZipInfo


PathLike = Union[str, Path]


@dataclass(frozen=True)
class ZipSafetyLimits:
    """Maximum uncompressed archive sizes accepted by :func:`safe_extract_zip`."""

    max_members: int = 10_000
    max_member_bytes: int = 1 * 1024**3
    max_total_bytes: int = 5 * 1024**3


def resolve_child_path(root: PathLike, *parts: PathLike) -> Path:
    """Resolve *parts* below *root* or raise if they escape that directory."""
    resolved_root = Path(root).resolve(strict=False)
    target = resolved_root.joinpath(*parts).resolve(strict=False)
    if not target.is_relative_to(resolved_root):
        raise ValueError(f"Path resolves outside allowed root: {target}")
    return target


def verify_sha256(path: PathLike, expected: str) -> None:
    """Raise when *path* does not match its expected SHA-256 hex digest."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)

    if digest.hexdigest() != expected.lower():
        raise ValueError(f"SHA-256 mismatch for {path}")


def _is_symbolic_link(info: ZipInfo) -> bool:
    return stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK


def _validate_archive_members(
    members: list[ZipInfo], destination: Path, limits: ZipSafetyLimits
) -> list[tuple[ZipInfo, Path]]:
    if len(members) > limits.max_members:
        raise ValueError(f"Archive contains too many members ({len(members)})")

    total_bytes = 0
    validated: list[tuple[ZipInfo, Path]] = []
    for info in members:
        if _is_symbolic_link(info):
            raise ValueError(f"Archive member is a symbolic link: {info.filename}")
        if info.file_size > limits.max_member_bytes:
            raise ValueError(f"Archive member exceeds size limit: {info.filename}")
        total_bytes += info.file_size
        if total_bytes > limits.max_total_bytes:
            raise ValueError("Archive total uncompressed size exceeds limit")
        validated.append((info, resolve_child_path(destination, info.filename)))
    return validated


def safe_extract_zip(
    archive: PathLike, destination: PathLike, limits: ZipSafetyLimits = ZipSafetyLimits()
) -> list[Path]:
    """Extract a ZIP after validating containment, links, and size limits.

    Members are fully validated before files are created, then streamed to their
    validated destinations.  The return value contains extracted files only.
    """
    output_root = Path(destination).resolve(strict=False)
    with ZipFile(archive, "r") as zip_file:
        validated = _validate_archive_members(zip_file.infolist(), output_root, limits)
        output_root.parent.mkdir(parents=True, exist_ok=True)
        staging_root = Path(tempfile.mkdtemp(prefix=".biochat-zip-", dir=output_root.parent))
        try:
            written_total = 0
            for info, target in validated:
                staged_target = resolve_child_path(staging_root, target.relative_to(output_root))
                if info.is_dir():
                    staged_target.mkdir(parents=True, exist_ok=True)
                    continue

                staged_target.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                with zip_file.open(info, "r") as source, staged_target.open("wb") as output:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        written += len(chunk)
                        written_total += len(chunk)
                        if written > limits.max_member_bytes:
                            raise ValueError(f"Archive member exceeds size limit: {info.filename}")
                        if written_total > limits.max_total_bytes:
                            raise ValueError("Archive total uncompressed size exceeds limit")
                        output.write(chunk)

            output_root.mkdir(parents=True, exist_ok=True)
            extracted: list[Path] = []
            for info, target in validated:
                staged_target = resolve_child_path(staging_root, target.relative_to(output_root))
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue

                target.parent.mkdir(parents=True, exist_ok=True)
                staged_target.replace(target)
                extracted.append(target)
            return extracted
        finally:
            shutil.rmtree(staging_root, ignore_errors=True)
