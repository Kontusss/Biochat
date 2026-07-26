"""S3 / HTTP download utilities for the Biomni data lake.

Replaces ``check_and_download_s3_files`` and ``download_and_unzip``
from the original ``utils.py`` (lines 879-1018).
"""

from __future__ import annotations

import os
import tempfile
import zipfile
from typing import Any
from urllib.parse import urljoin

import requests
import tqdm


def fetch_and_extract_archive(url: str, dest_dir: str) -> str:
    """Download a zip archive from *url* and extract it to *dest_dir*.

    Returns:
        The destination directory path, or an error string prefix.
    """
    os.makedirs(dest_dir, exist_ok=True)

    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))

            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                with tqdm.tqdm(
                    total=total_size / (1024 ** 3),
                    unit="GB", unit_scale=True, desc="Downloading", ncols=80,
                ) as pbar:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            tmp.write(chunk)
                            pbar.update(len(chunk) / (1024 ** 3))
                tmp_path = tmp.name

        with zipfile.ZipFile(tmp_path, "r") as zf:
            zf.extractall(dest_dir)
        os.unlink(tmp_path)
        return dest_dir
    except Exception as exc:
        return f"Error: {exc}"


def sync_data_lake_files(
    s3_bucket_url: str,
    local_data_lake_path: str,
    expected_files: list[str],
    folder: str = "data_lake",
) -> dict[str, bool]:
    """Check local files against expected list; download any that are missing.

    Returns:
        ``{filename: success_bool}`` mapping.
    """
    os.makedirs(local_data_lake_path, exist_ok=True)
    results: dict[str, bool] = {}

    def _download_progress(url: str, dest: str, desc: str) -> bool:
        try:
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                with open(dest, "wb") as fh:
                    if total:
                        with tqdm.tqdm(total=total, unit="B", unit_scale=True, desc=desc, ncols=80) as pbar:
                            for chunk in r.iter_content(8192):
                                if chunk:
                                    fh.write(chunk)
                                    pbar.update(len(chunk))
                    else:
                        for chunk in r.iter_content(8192):
                            if chunk:
                                fh.write(chunk)
            return True
        except Exception:
            _safe_remove(dest)
            return False

    def _safe_remove(path: str) -> None:
        try:
            os.remove(path)
        except OSError:
            pass

    # ── Benchmark folder: download as zip ─────────────────────
    if folder == "benchmark":
        zip_url = urljoin(s3_bucket_url + "/", folder + ".zip")
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp_path = tmp.name

        if _download_progress(zip_url, tmp_path, f"{folder}.zip"):
            try:
                with zipfile.ZipFile(tmp_path, "r") as zf:
                    zf.extractall(local_data_lake_path)
                results = dict.fromkeys(expected_files, True)
            except Exception:
                results = dict.fromkeys(expected_files, False)
            finally:
                _safe_remove(tmp_path)
        else:
            results = dict.fromkeys(expected_files, False)
        return results

    # ── Data lake: individual files ───────────────────────────
    for filename in expected_files:
        local = os.path.join(local_data_lake_path, filename)
        if os.path.exists(local):
            results[filename] = True
            continue

        s3_url = urljoin(s3_bucket_url + "/" + folder + "/", filename)
        results[filename] = _download_progress(s3_url, local, filename)

    return results


# ── Backward-compatible aliases ─────────────────────────────────
download_and_unzip = fetch_and_extract_archive
check_and_download_s3_files = sync_data_lake_files
