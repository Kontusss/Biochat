"""
Phase 3D-1d: HDOCK output QC + createpl readiness detection.

Inspects HDOCK output files and checks createpl availability.
Does NOT parse scores, does NOT rank, does NOT perform extraction.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Dict, List

DEFAULT_IMAGE = "hdock-runner:latest"
DEFAULT_PLATFORM = "linux/amd64"


# ═══════════════════════════════════════════════════════════════
# HDOCK output inspection
# ═══════════════════════════════════════════════════════════════

def inspect_hdock_output(
    hdock_out: str,
    min_size_bytes: int = 1024,
) -> Dict[str, Any]:
    """Inspect an HDOCK output file for basic QC.

    Does NOT parse docking scores or perform ranking.
    """
    result: Dict[str, Any] = {
        "exists": False,
        "nonempty": False,
        "size_bytes": 0,
        "format_detected": False,
        "format_type": None,
        "contains_models": False,
        "model_count_estimate": None,
        "score_parsed": False,
        "ranking_performed": False,
        "calibration": "uncalibrated",
        "provenance": "computed",
        "warnings": [],
    }

    if not os.path.isfile(hdock_out):
        result["warnings"].append("file_not_found")
        return result

    result["exists"] = True
    result["size_bytes"] = os.path.getsize(hdock_out)

    if result["size_bytes"] == 0:
        result["warnings"].append("empty_file")
        return result

    result["nonempty"] = True

    if result["size_bytes"] < min_size_bytes:
        result["warnings"].append(f"below_min_size: {result['size_bytes']} < {min_size_bytes}")

    # Lightweight format detection: read first few lines
    try:
        with open(hdock_out, errors="replace") as fh:
            head = "".join(fh.readline() for _ in range(20))
    except Exception as exc:
        result["warnings"].append(f"read_error: {exc}")
        return result

    # HDOCK output markers (HDOCKlite format)
    hdock_markers = ["Grid spacing", "Angle step", "rotation"]
    score_lines_count = 0
    total_line_count = 0
    for line in head.splitlines():
        line_stripped = line.strip()
        if not line_stripped:
            continue
        total_line_count += 1
        if any(m.lower() in line_stripped.lower() for m in hdock_markers):
            score_lines_count += 1
        # Detect PDB model blocks (after createpl extraction)
        if line_stripped.startswith("MODEL "):
            result["contains_models"] = True

    # HDOCKlite format: header + tabular rotation lines with 9 columns
    # Detect by checking if data lines have ~9 whitespace-separated fields
    data_lines = [l for l in head.splitlines() if l.strip() and not any(
        m.lower() in l.lower() for m in ["grid", "angle", "rotation", "spacing", "dimension", "start", "actual"])]
    if len(data_lines) >= 2:
        fields = data_lines[-1].split()
        if 5 <= len(fields) <= 12:
            score_lines_count += 1

    if score_lines_count >= 2:
        result["format_detected"] = True
        result["format_type"] = "HDOCK"

    # Quick scan for actual PDB MODEL blocks
    try:
        with open(hdock_out, errors="replace") as fh:
            model_count = sum(1 for line in fh if line.startswith("MODEL "))
        if model_count > 0:
            result["contains_models"] = True
            result["model_count_estimate"] = model_count // 2
    except Exception:
        pass

    # If HDOCKlite format detected but no PDB models, estimate from line count
    if result["format_detected"] and not result["contains_models"]:
        try:
            with open(hdock_out, errors="replace") as fh:
                total = sum(1 for l in fh if l.strip())
            # Each rotation is one line; top 100 models typically extracted
            result["model_count_estimate"] = min(total, 100)
        except Exception:
            pass

    return result


# ═══════════════════════════════════════════════════════════════
# createpl readiness
# ═══════════════════════════════════════════════════════════════

def check_createpl_ready(
    createpl_binary: str = "createpl",
    runtime: str = "local",
    docker_image: str = DEFAULT_IMAGE,
    hdock_host_dir: str | None = None,
    platform: str = DEFAULT_PLATFORM,
    timeout_sec: int = 30,
) -> Dict[str, Any]:
    """Check if createpl is available for top-model extraction.

    Does NOT perform extraction.  Planned-only mode.
    """
    hd_dir = hdock_host_dir or "/Users/walker/Desktop/core/tools/HDOCKlite-v1.1"

    result: Dict[str, Any] = {
        "available": False,
        "runtime": runtime,
        "binary_present": False,
        "executable_usable": False,
        "planned_only": True,
        "extraction_performed": False,
        "provenance": "computed",
    }

    if runtime == "docker":
        # Check Docker + image
        docker_ok = shutil.which("docker") is not None
        if not docker_ok:
            result["error"] = "docker not available"
            return result
        try:
            proc = subprocess.run(
                ["docker", "images", "-q", docker_image],
                capture_output=True, text=True, timeout=timeout_sec,
            )
            image_ok = bool(proc.stdout.strip())
        except Exception:
            image_ok = False
        if not image_ok:
            result["error"] = f"docker image '{docker_image}' not found"
            return result
        cp_path = os.path.join(hd_dir, "createpl")
        result["binary_present"] = os.path.isfile(cp_path)
        result["executable_usable"] = result["binary_present"]  # Docker handles ELF
        result["available"] = result["binary_present"] and image_ok
    else:
        cp_path = shutil.which(createpl_binary)
        if cp_path is None:
            cp_path = os.path.join(hd_dir, "createpl")
        result["binary_present"] = cp_path is not None and os.path.isfile(cp_path)
        if result["binary_present"]:
            try:
                subprocess.run([cp_path], capture_output=True, text=True, timeout=timeout_sec)
                result["executable_usable"] = True
            except OSError as exc:
                msg = str(exc)
                if "exec format error" in msg.lower():
                    result["error_type"] = "ExecFormatError"
                result["error"] = msg
            except Exception:
                pass
        result["available"] = result["binary_present"] and result["executable_usable"]

    return result


# ═══════════════════════════════════════════════════════════════
# Extraction planning
# ═══════════════════════════════════════════════════════════════

def plan_createpl_extraction(
    hdock_out: str,
    output_pdb: str,
    model_index: int = 1,
    runtime: str = "docker",
    docker_image: str = DEFAULT_IMAGE,
    hdock_host_dir: str | None = None,
    platform: str = DEFAULT_PLATFORM,
) -> Dict[str, Any]:
    """Plan createpl extraction WITHOUT executing it.

    Returns a command preview and metadata.  Phase 3D-1e would execute.
    """
    hd_dir = hdock_host_dir or "/Users/walker/Desktop/core/tools/HDOCKlite-v1.1"
    hdock_abs = os.path.abspath(hdock_out) if os.path.exists(hdock_out) else hdock_out
    pdb_abs = os.path.abspath(output_pdb)
    pdb_dir = os.path.dirname(pdb_abs)

    cmd_preview: List[str] = []

    if runtime == "docker":
        cmd_preview = [
            "docker", "run", "--rm",
            "--platform", platform,
            "-w", "/work",
            "-v", f"{os.path.dirname(hdock_abs)}:/input:ro",
            "-v", f"{pdb_dir}:/output:rw",
            "-v", f"{hd_dir}:/opt/hdock:ro",
            docker_image,
            "/opt/hdock/createpl",
            f"/input/{os.path.basename(hdock_abs)}",
            f"/output/{os.path.basename(pdb_abs)}",
        ]
    else:
        cp_path = shutil.which("createpl") or os.path.join(hd_dir, "createpl")
        cmd_preview = [cp_path, hdock_out, output_pdb]

    return {
        "planned": True,
        "extraction_performed": False,
        "model_index": model_index,
        "input_file": hdock_abs,
        "output_pdb": pdb_abs,
        "runtime": runtime,
        "docker_image": docker_image if runtime == "docker" else None,
        "command_preview": cmd_preview,
        "score_parsed": False,
        "ranking_performed": False,
        "calibration": "uncalibrated",
        "provenance": "computed",
    }
