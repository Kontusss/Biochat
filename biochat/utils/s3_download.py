"""S3 / HTTP download utilities for the Biochat data lake.

Replaces ``check_and_download_s3_files`` and ``download_and_unzip``
from the original ``utils.py`` (lines 879-1018).
"""

from __future__ import annotations

import os
import tempfile
from typing import Any
from urllib.parse import urljoin

import requests
import tqdm

from biochat.utils.filesystem_safety import resolve_child_path, safe_extract_zip, verify_sha256


DEFAULT_MAX_DOWNLOAD_BYTES = 5 * 1024**3


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def fetch_and_extract_archive(
    url: str,
    dest_dir: str,
    *,
    expected_sha256: str | None = None,
    max_download_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
) -> str:
    """Download a zip archive from *url* and extract it to *dest_dir*.

    Returns:
        The destination directory path, or an error string prefix.
    """
    os.makedirs(dest_dir, exist_ok=True)

    tmp_path: str | None = None
    try:
        with requests.get(url, stream=True, timeout=(10, 120)) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            if total_size > max_download_bytes:
                raise ValueError("Download exceeds configured byte limit")

            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                tmp_path = tmp.name
                with tqdm.tqdm(
                    total=total_size / (1024 ** 3),
                    unit="GB", unit_scale=True, desc="Downloading", ncols=80,
                ) as pbar:
                    downloaded = 0
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            downloaded += len(chunk)
                            if downloaded > max_download_bytes:
                                raise ValueError("Download exceeds configured byte limit")
                            tmp.write(chunk)
                            pbar.update(len(chunk) / (1024 ** 3))

        if expected_sha256:
            verify_sha256(tmp_path, expected_sha256)
        safe_extract_zip(tmp_path, dest_dir)
        return dest_dir
    except Exception as exc:
        return f"Error: {exc}"
    finally:
        if tmp_path:
            _safe_remove(tmp_path)


def sync_data_lake_files(
    s3_bucket_url: str,
    local_data_lake_path: str,
    expected_files: list[str],
    folder: str = "data_lake",
    *,
    checksums: dict[str, str] | None = None,
    max_download_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
) -> dict[str, bool]:
    """Check local files against expected list; download any that are missing.

    Returns:
        ``{filename: success_bool}`` mapping.
    """
    os.makedirs(local_data_lake_path, exist_ok=True)
    results: dict[str, bool] = {}

    def _download_progress(url: str, dest: str, desc: str, expected_sha256: str | None = None) -> bool:
        try:
            with requests.get(url, stream=True, timeout=(10, 120)) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                if total > max_download_bytes:
                    raise ValueError("Download exceeds configured byte limit")
                downloaded = 0
                with open(dest, "wb") as fh:
                    if total:
                        with tqdm.tqdm(total=total, unit="B", unit_scale=True, desc=desc, ncols=80) as pbar:
                            for chunk in r.iter_content(8192):
                                if chunk:
                                    downloaded += len(chunk)
                                    if downloaded > max_download_bytes:
                                        raise ValueError("Download exceeds configured byte limit")
                                    fh.write(chunk)
                                    pbar.update(len(chunk))
                    else:
                        for chunk in r.iter_content(8192):
                            if chunk:
                                downloaded += len(chunk)
                                if downloaded > max_download_bytes:
                                    raise ValueError("Download exceeds configured byte limit")
                                fh.write(chunk)
            if expected_sha256:
                verify_sha256(dest, expected_sha256)
            return True
        except Exception:
            _safe_remove(dest)
            return False

    # ── Benchmark folder: download as zip ─────────────────────
    if folder == "benchmark":
        zip_url = urljoin(s3_bucket_url + "/", folder + ".zip")
        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                tmp_path = tmp.name

            if _download_progress(zip_url, tmp_path, f"{folder}.zip", (checksums or {}).get(f"{folder}.zip")):
                safe_extract_zip(tmp_path, local_data_lake_path)
                results = dict.fromkeys(expected_files, True)
            else:
                results = dict.fromkeys(expected_files, False)
        except Exception:
            results = dict.fromkeys(expected_files, False)
        finally:
            if tmp_path:
                _safe_remove(tmp_path)
        return results

    # ── Data lake: individual files ───────────────────────────
    for filename in expected_files:
        try:
            local = resolve_child_path(local_data_lake_path, filename)
        except ValueError:
            results[filename] = False
            continue
        expected_sha256 = (checksums or {}).get(filename)
        if os.path.exists(local):
            if not expected_sha256:
                results[filename] = True
                continue
            try:
                verify_sha256(local, expected_sha256)
                results[filename] = True
                continue
            except ValueError:
                pass

        s3_url = urljoin(s3_bucket_url + "/" + folder + "/", filename)
        os.makedirs(local.parent, exist_ok=True)
        results[filename] = _download_progress(s3_url, str(local), filename, expected_sha256)

    return results


# ── Backward-compatible aliases ─────────────────────────────────
download_and_unzip = fetch_and_extract_archive
check_and_download_s3_files = sync_data_lake_files
