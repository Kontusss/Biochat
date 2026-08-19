"""
HDOCK Docker adapter — Linux x86_64 runtime via Docker on macOS.

Requires: Docker daemon, hdock-runner image, HDOCK binary directory.
Output explicitly labeled as uncalibrated computational predictions.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any, Dict

DEFAULT_IMAGE = "hdock-runner:latest"
DEFAULT_PLATFORM = "linux/amd64"
DEFAULT_HDOCK_HOST_DIR = "/Users/walker/Desktop/core/tools/HDOCKlite-v1.1"


# ═══════════════════════════════════════════════════════════════
# Availability check
# ═══════════════════════════════════════════════════════════════

def check_hdock_docker_available(
    docker_binary: str = "docker",
    docker_image: str = DEFAULT_IMAGE,
    platform: str = DEFAULT_PLATFORM,
    hdock_host_dir: str | None = None,
    timeout_sec: int = 30,
) -> Dict[str, Any]:
    """Verify Docker daemon + image + HDOCK binary dir are ready."""
    result: Dict[str, Any] = {
        "available": False,
        "runtime": "docker",
        "platform": platform,
        "docker_binary": docker_binary,
        "docker_image": docker_image,
        "hdock_host_dir": hdock_host_dir or DEFAULT_HDOCK_HOST_DIR,
        "provenance": "computed",
        "checks": {},
    }

    # 1. Docker binary
    result["checks"]["docker_binary"] = shutil.which(docker_binary) is not None
    if not result["checks"]["docker_binary"]:
        result["error"] = f"'{docker_binary}' not found on PATH"
        return result

    # 2. Docker daemon
    try:
        subprocess.run([docker_binary, "info"], capture_output=True, timeout=timeout_sec, check=True)
        result["checks"]["docker_daemon"] = True
    except Exception as exc:
        result["checks"]["docker_daemon"] = False
        result["error"] = f"Docker daemon unavailable: {exc}"
        return result

    # 3. Docker image
    try:
        proc = subprocess.run(
            [docker_binary, "images", "-q", docker_image],
            capture_output=True, text=True, timeout=timeout_sec,
        )
        result["checks"]["docker_image"] = bool(proc.stdout.strip())
    except Exception as exc:
        result["checks"]["docker_image"] = False
        result["error"] = str(exc)
        return result

    if not result["checks"]["docker_image"]:
        result["error"] = f"Docker image '{docker_image}' not found"
        hd = hdock_host_dir or DEFAULT_HDOCK_HOST_DIR
        result["build_hint"] = (
            f"cd {os.path.dirname(hd)} && "
            f"docker build -t {docker_image} -f Dockerfile.hdock ."
        )
        return result

    # 4. HDOCK host directory
    hd_dir = hdock_host_dir or DEFAULT_HDOCK_HOST_DIR
    result["checks"]["hdock_host_dir"] = os.path.isdir(hd_dir) and os.path.isfile(os.path.join(hd_dir, "hdock"))
    if not result["checks"]["hdock_host_dir"]:
        result["error"] = f"HDOCK binary not found in host directory: {hd_dir}"
        return result

    result["available"] = True
    return result


# ═══════════════════════════════════════════════════════════════
# Docker execution
# ═══════════════════════════════════════════════════════════════

def run_hdock_docker(
    receptor_pdb: str,
    ligand_pdb: str,
    output_dir: str,
    candidate_id: str = "unknown",
    hdock_host_dir: str | None = None,
    docker_image: str = DEFAULT_IMAGE,
    platform: str = DEFAULT_PLATFORM,
    docker_binary: str = "docker",
    timeout_sec: int = 1800,
) -> Dict[str, Any]:
    """Execute HDOCK via Docker with Linux x86_64 runtime.

    All output labeled as uncalibrated.  No score parsing, no ranking.
    """
    result: Dict[str, Any] = {
        "candidate_id": candidate_id,
        "success": False,
        "status": "failed",
        "method": "hdock",
        "runtime": "docker",
        "platform": platform,
        "docker_image": docker_image,
        "real_backend": True,
        "docking_performed": True,
        "returncode": None,
        "output_file": None,
        "stdout_file": None,
        "stderr_file": None,
        "calibration": "uncalibrated",
        "score_semantics": (
            "computational docking output only; "
            "uncalibrated; not an experimental measurement"
        ),
        "provenance": "computed",
    }

    hd_dir = hdock_host_dir or DEFAULT_HDOCK_HOST_DIR
    os.makedirs(output_dir, exist_ok=True)

    # Pre-flight checks
    if not os.path.isfile(receptor_pdb):
        result["error"] = f"receptor PDB missing: {receptor_pdb}"; return result
    if not os.path.isfile(ligand_pdb):
        result["error"] = f"ligand PDB missing: {ligand_pdb}"; return result
    if not os.path.isdir(hd_dir) or not os.path.isfile(os.path.join(hd_dir, "hdock")):
        result["error"] = f"HDOCK binary not found at {hd_dir}/hdock"; return result

    rx_abs = os.path.abspath(receptor_pdb)
    lig_abs = os.path.abspath(ligand_pdb)
    out_abs = os.path.abspath(output_dir)
    hd_abs = os.path.abspath(hd_dir)
    rx_name = os.path.basename(rx_abs)
    lig_name = os.path.basename(lig_abs)

    cmd = [
        docker_binary, "run", "--rm",
        "--platform", platform,
        "-w", "/output",
        "-v", f"{os.path.dirname(rx_abs)}:/input_rx:ro",
        "-v", f"{os.path.dirname(lig_abs)}:/input_lig:ro",
        "-v", f"{hd_abs}:/opt/hdock:ro",
        "-v", f"{out_abs}:/output:rw",
        docker_image,
        "/opt/hdock/hdock",
        f"/input_rx/{rx_name}",
        f"/input_lig/{lig_name}",
        "-out", "/output/hdock.out",
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
        result["returncode"] = proc.returncode

        stdout_file = os.path.join(output_dir, "stdout.txt")
        stderr_file = os.path.join(output_dir, "stderr.txt")
        with open(stdout_file, "w") as fh: fh.write(proc.stdout or "")
        with open(stderr_file, "w") as fh: fh.write(proc.stderr or "")
        result["stdout_file"] = stdout_file
        result["stderr_file"] = stderr_file

        out_file = os.path.join(output_dir, "hdock.out")
        if proc.returncode == 0:
            if os.path.exists(out_file) and os.path.getsize(out_file) > 0:
                result["success"] = True
                result["status"] = "success"
                result["output_file"] = out_file
            else:
                result["error"] = "hdock.out missing or empty despite returncode 0"
        else:
            result["error"] = f"container exit code {proc.returncode}"

    except subprocess.TimeoutExpired:
        result["error"] = f"HDOCK Docker job timed out after {timeout_sec}s"
    except Exception as exc:
        result["error"] = str(exc)

    # Write execution.json
    with open(os.path.join(output_dir, "execution.json"), "w") as fh:
        json.dump(result, fh, indent=2)

    return result
