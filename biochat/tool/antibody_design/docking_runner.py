"""
Phase 3D-0: Docking adapter scaffold — dry-run command construction.

Prepares HDOCK command scripts and run manifests WITHOUT executing
docking.  All scores labeled as uncalibrated computational predictions.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from biochat.tool.antibody_design.structure_validation import validate_pdb_for_docking

FORBIDDEN = ["ddg", "Kd", "binding_affinity", "validated",
             "experimentally confirmed", "high affinity"]

_CMD_TEMPLATE = """#!/usr/bin/env bash
set -euo pipefail
# ============================================================
# Phase 3D-0 dry-run generated HDOCK command
# Candidate: {candidate_id}
# Receptor:  {receptor_pdb}
# Ligand:    {ligand_pdb}
# Output:    {result_dir}
# ============================================================
# WARNING: Docking scores are computational and uncalibrated.
# DO NOT interpret as calibrated experimental measurements.
# ============================================================

hdock \\
  "{receptor_pdb}" \\
  "{ligand_pdb}" \\
  -out "{result_dir}/hdock.out"

echo "Docking completed. Results in {result_dir}/"
echo "REMINDER: Scores are uncalibrated computational predictions."
"""


def prepare_docking_runs(
    docking_input_manifest: Dict[str, Any],
    output_dir: str,
    method: str = "hdock",
    dry_run: bool = True,
    mock: bool = False,
    hdock_binary: str = "hdock",
) -> Dict[str, Any]:
    """Prepare docking run scripts from a Phase 3C-4 input manifest.

    Phase 3D-0: Does NOT execute docking.  Only constructs commands
    and writes planned.json for each run.

    Args:
        docking_input_manifest: Output from prepare_docking_inputs().
        output_dir: Directory for command scripts and manifests.
        method: Docking method name (default: hdock).
        dry_run: Must be True for 3D-0 (enforced).
        mock: If True, generate mock result stubs.
        hdock_binary: Path or name of HDOCK binary.

    Returns:
        Docking run manifest dict.
    """
    os.makedirs(output_dir, exist_ok=True)
    cmds_dir = os.path.join(output_dir, "commands")
    results_dir = os.path.join(output_dir, "results")
    os.makedirs(cmds_dir, exist_ok=True)

    # Safety: reject if upstream already performed docking
    if docking_input_manifest.get("docking_performed", False):
        return _error_manifest(output_dir, "upstream_docking_performed is true; refusing to re-plan")

    receptors = docking_input_manifest.get("receptors", [])
    ligands = docking_input_manifest.get("ligands", [])
    constraints_list = docking_input_manifest.get("constraints", [])

    if not ligands:
        return _error_manifest(output_dir, "no ligands in input manifest")

    ligand = ligands[0]
    ligand_pdb = ligand.get("output_pdb", "")

    runs: List[Dict[str, Any]] = []
    planned = 0; skipped = 0; failed = 0

    for rx in receptors:
        cid = rx.get("candidate_id") or rx.get("cdrh3_sequence", "unknown")
        safe_id = _sanitize(cid)
        run: Dict[str, Any] = {
            "candidate_id": cid, "status": "planned",
            "receptor_pdb": rx.get("output_pdb", ""),
            "ligand_pdb": ligand_pdb,
            "docking_performed": False, "provenance": "computed",
        }

        # Skip mock
        if rx.get("mock", False):
            run["status"] = "skipped"; run["reason"] = "mock_structure"
            skipped += 1; runs.append(run); continue

        # Skip non-eligible
        if not rx.get("eligible_for_docking", False):
            run["status"] = "skipped"; run["reason"] = "not_eligible"
            skipped += 1; runs.append(run); continue

        # Validate receptor PDB
        rx_pdb = rx.get("output_pdb", "")
        if not rx_pdb or not os.path.isfile(rx_pdb):
            run["status"] = "failed"; run["reason"] = "receptor_pdb_missing"
            failed += 1; runs.append(run); continue

        pdb_val = validate_pdb_for_docking(rx_pdb)
        if not pdb_val.get("eligible_for_docking", False):
            run["status"] = "failed"
            run["reason"] = f"receptor_pdb_validation: {pdb_val.get('issues', [])}"
            failed += 1; runs.append(run); continue

        # Validate ligand PDB
        if not ligand_pdb or not os.path.isfile(ligand_pdb):
            run["status"] = "failed"; run["reason"] = "ligand_pdb_missing"
            failed += 1; runs.append(run); continue

        lig_val = validate_pdb_for_docking(ligand_pdb)
        # Short peptides naturally have <100 atoms — accept if file exists and is valid format
        lig_ok = lig_val.get("eligible_for_docking", False) or (
            os.path.getsize(ligand_pdb) > 0 and
            "mock_or_placeholder" not in str(lig_val.get("issues", []))
        )
        if not lig_ok:
            run["status"] = "failed"
            run["reason"] = f"ligand_pdb_validation: {lig_val.get('issues', [])}"
            failed += 1; runs.append(run); continue

        # Build result dir and command
        run_dir = os.path.join(results_dir, safe_id)
        os.makedirs(run_dir, exist_ok=True)
        run["result_dir"] = run_dir

        script_path = os.path.join(cmds_dir, f"{safe_id}_hdock_command.sh")
        script = _CMD_TEMPLATE.format(
            candidate_id=cid, receptor_pdb=rx_pdb,
            ligand_pdb=ligand_pdb, result_dir=run_dir,
        )
        with open(script_path, "w") as fh:
            fh.write(script)
        os.chmod(script_path, 0o755)

        run["command_script"] = script_path

        # Find matching constraint
        cdrh3 = ""
        for ct in constraints_list:
            if ct.get("candidate_id") == cid:
                run["constraints_json"] = ct
                cdrh3 = ct.get("cdrh3_sequence", "")
                break

        # Write planned.json
        planned_json = {
            "candidate_id": cid, "status": "planned",
            "docking_performed": False, "method": method,
            "dry_run": dry_run,
            "receptor_pdb": rx_pdb, "ligand_pdb": ligand_pdb,
            "cdrh3_sequence": cdrh3, "calibration": "uncalibrated",
            "score_semantics": "docking score only; not calibrated to experimental measurements",
            "provenance": "computed",
        }
        with open(os.path.join(run_dir, "planned.json"), "w") as fh:
            json.dump(planned_json, fh, indent=2)
        planned += 1
        runs.append(run)

    # Build manifest
    manifest: Dict[str, Any] = {
        "manifest_version": "3D-0",
        "phase": "Phase 3D-0",
        "capability": "docking_adapter_scaffold",
        "docking_performed": False,
        "method": method, "dry_run": dry_run, "mock": mock,
        "calibration": "uncalibrated",
        "score_semantics": "docking score only; not calibrated to experimental measurements",
        "runs": runs,
        "summary": {
            "input_receptors": len(receptors),
            "planned": planned, "skipped": skipped, "failed": failed,
        },
    }

    manifest_path = os.path.join(output_dir, "docking_run_manifest.json")
    with open(manifest_path, "w") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)

    # Safety: check no forbidden terms in output
    j = json.dumps(manifest).lower()
    for t in FORBIDDEN:
        if t.lower() in j:
            manifest["warnings"] = manifest.get("warnings", []) + [f"forbidden_term_detected: {t}"]

    return manifest


# ═══════════════════════════════════════════════════════════════
# HDOCK environment detection
# ═══════════════════════════════════════════════════════════════

def check_hdock_available(
    hdock_binary: str = "hdock",
    createpl_binary: str = "createpl",
    timeout_sec: int = 10,
) -> dict:
    """Detect HDOCK and createpl executables on PATH.

    Distinguishes binary-presence from actual executability.
    Does NOT execute docking.  All output labeled as uncalibrated.
    """
    import shutil, subprocess

    result: dict = {
        "available": False,
        "binary_present": False,
        "executable_usable": False,
        "backend": "HDOCK",
        "binary": hdock_binary,
        "resolved_path": None,
        "version": None,
        "error_type": None,
        "error_message": None,
        "toolchain": {},
        "warnings": [],
        "provenance": "computed",
    }

    # ── Detect hdock ─────────────────────────────────────────
    hdock_path = shutil.which(hdock_binary)
    if hdock_path is None:
        result.update({
            "error_type": "ExecutableNotFound",
            "error_message": f"HDOCK executable '{hdock_binary}' not found on PATH.",
            "install_hint": (
                "Install HDOCK from the official distribution and "
                "add the executable directory to PATH."
            ),
        })
    else:
        result["binary_present"] = True
        result["resolved_path"] = hdock_path

        # Probe executability
        try:
            proc = subprocess.run(
                [hdock_path], capture_output=True, text=True,
                timeout=timeout_sec,
            )
            output = (proc.stdout + proc.stderr).strip()
            if output:
                result["version"] = output.splitlines()[0][:120]
            result["executable_usable"] = True
        except subprocess.TimeoutExpired:
            result["error_type"] = "ProbeTimeout"
            result["error_message"] = f"hdock probe timed out after {timeout_sec}s"
            result["warnings"].append(result["error_message"])
        except OSError as exc:
            msg = str(exc)
            if "exec format error" in msg.lower() or "cannot execute binary" in msg.lower():
                result["error_type"] = "ExecFormatError"
                result["error_message"] = f"HDOCK binary is not executable on this platform: {msg}"
                result["recommended_runtime"] = "Linux x86_64 or Docker container"
            elif "permission denied" in msg.lower():
                result["error_type"] = "PermissionDenied"
                result["error_message"] = f"HDOCK binary permission denied: {msg}"
            else:
                result["error_type"] = "OSError"
                result["error_message"] = msg
            result["warnings"].append(result["error_message"])
        except Exception as exc:
            result["error_type"] = type(exc).__name__
            result["error_message"] = str(exc)
            result["warnings"].append(f"hdock probe failed: {exc}")

    # ── Set final availability ───────────────────────────────
    result["available"] = result["binary_present"] and result["executable_usable"]

    # ── Detect createpl (same semantics) ─────────────────────
    cp_path = shutil.which(createpl_binary)
    cp_info: dict = {
        "binary_present": cp_path is not None,
        "available": False,
        "executable_usable": False,
        "binary": createpl_binary,
        "resolved_path": cp_path,
    }
    if cp_path is not None:
        try:
            subprocess.run([cp_path], capture_output=True, text=True, timeout=timeout_sec)
            cp_info["executable_usable"] = True
        except subprocess.TimeoutExpired:
            cp_info["error_type"] = "ProbeTimeout"
        except OSError as exc:
            msg = str(exc)
            if "exec format error" in msg.lower():
                cp_info["error_type"] = "ExecFormatError"
            elif "permission denied" in msg.lower():
                cp_info["error_type"] = "PermissionDenied"
            else:
                cp_info["error_type"] = "OSError"
            cp_info["error_message"] = msg
        except Exception as exc:
            cp_info["error_type"] = type(exc).__name__
    cp_info["available"] = cp_info["binary_present"] and cp_info.get("executable_usable", False)
    result["toolchain"]["createpl"] = cp_info

    if not cp_info["available"]:
        result["warnings"].append("createpl not available; top model extraction may be unavailable.")

    return result


# ═══════════════════════════════════════════════════════════════
# Docking execution wrapper
# ═══════════════════════════════════════════════════════════════

def run_docking_jobs(
    docking_run_manifest: dict,
    output_dir: str,
    method: str = "hdock",
    runtime: str = "local",
    hdock_binary: str = "hdock",
    createpl_binary: str = "createpl",
    docker_image: str = "hdock-runner:latest",
    hdock_host_dir: str | None = None,
    platform: str = "linux/amd64",
    dry_run: bool = False,
    timeout_sec: int = 600,
    test_backend: bool = False,
) -> dict:
    """Execute docking jobs from a Phase 3D-0 run manifest.

    Args:
        runtime: "local" (native binary) or "docker" (Linux container).
        hdock_binary/createpl_binary: Used when runtime="local".
        docker_image/hdock_host_dir/platform: Used when runtime="docker".
    """
    import subprocess

    os.makedirs(output_dir, exist_ok=True)
    results_base = os.path.join(output_dir, "results")
    os.makedirs(results_base, exist_ok=True)

    # Determine backend status based on runtime
    if runtime == "docker":
        from biochat.tool.antibody_design.hdock_docker import check_hdock_docker_available
        avail = check_hdock_docker_available(
            docker_image=docker_image, platform=platform,
            hdock_host_dir=hdock_host_dir, timeout_sec=min(30, timeout_sec),
        )
        backend_ok = avail["available"]
    else:
        avail = check_hdock_available(hdock_binary=hdock_binary, createpl_binary=createpl_binary)
        backend_ok = avail["available"]

    real_backend = (not dry_run and not test_backend and backend_ok)

    runs_out: list[dict] = []
    executed = 0; failed = 0; skipped = 0; planned = 0

    for run in docking_run_manifest.get("runs", []):
        cid = run.get("candidate_id", "unknown")
        safe_id = _sanitize(cid)
        rx_pdb = run.get("receptor_pdb", "")
        lig_pdb = run.get("ligand_pdb", "")
        run_dir = os.path.join(results_base, safe_id)
        os.makedirs(run_dir, exist_ok=True)

        entry: dict = {
            "candidate_id": cid,
            "receptor_pdb": rx_pdb, "ligand_pdb": lig_pdb,
            "result_dir": run_dir,
            "status": "planned",
            "docking_performed": False,
            "real_backend": False,
            "test_backend": test_backend,
            "calibration": "uncalibrated",
            "provenance": "computed",
        }

        # ── Pre-flight checks ─────────────────────────────────
        if run.get("status") == "skipped":
            entry["status"] = "skipped"; entry["reason"] = run.get("reason","")
            skipped += 1; runs_out.append(entry); continue

        if not rx_pdb or not os.path.isfile(rx_pdb):
            entry["status"] = "failed"; entry["reason"] = "receptor_pdb_missing"
            failed += 1; runs_out.append(entry); continue
        if not lig_pdb or not os.path.isfile(lig_pdb):
            entry["status"] = "failed"; entry["reason"] = "ligand_pdb_missing"
            failed += 1; runs_out.append(entry); continue

        # ── Dry run ───────────────────────────────────────────
        if dry_run:
            entry["status"] = "planned"
            with open(os.path.join(run_dir, "execution.json"), "w") as fh:
                json.dump(entry, fh, indent=2)
            planned += 1; runs_out.append(entry); continue

        # ── Real / test execution ─────────────────────────────
        if not test_backend and not backend_ok:
            entry["status"] = "failed"
            entry["error_type"] = avail.get("error_type", "BackendUnavailable")
            entry["error_message"] = avail.get("error_message", str(avail))
            failed += 1; runs_out.append(entry); continue

        if runtime == "docker":
            # Docker HDOCK execution
            from biochat.tool.antibody_design.hdock_docker import run_hdock_docker as _docker_run
            dr = _docker_run(
                receptor_pdb=rx_pdb, ligand_pdb=lig_pdb,
                output_dir=run_dir, candidate_id=cid,
                hdock_host_dir=hdock_host_dir,
                docker_image=docker_image, platform=platform,
                timeout_sec=timeout_sec,
            )
            entry["status"] = "success" if dr.get("success") else "failed"
            entry["returncode"] = dr.get("returncode")
            entry["docking_performed"] = dr.get("docking_performed", False)
            entry["real_backend"] = dr.get("real_backend", False)
            entry["runtime"] = {
                "type": "docker", "platform": platform,
                "docker_image": docker_image,
                "hdock_host_dir": hdock_host_dir or "default",
                "readonly_hdock_mount": True,
            }
            entry["output_file"] = dr.get("output_file")
            entry["stdout_file"] = dr.get("stdout_file")
            entry["stderr_file"] = dr.get("stderr_file")
            if dr.get("error"):
                entry["error"] = dr["error"]
            if dr.get("success"):
                executed += 1
            else:
                failed += 1
        else:
            # Local subprocess execution
            out_file = os.path.join(run_dir, "hdock.out")
            stdout_file = os.path.join(run_dir, "stdout.txt")
            stderr_file = os.path.join(run_dir, "stderr.txt")

            try:
                cmd = [hdock_binary, rx_pdb, lig_pdb, "-out", out_file]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
                with open(stdout_file, "w") as fh: fh.write(proc.stdout or "")
                with open(stderr_file, "w") as fh: fh.write(proc.stderr or "")
                entry["status"] = "success" if proc.returncode == 0 else "failed"
                entry["returncode"] = proc.returncode
                entry["docking_performed"] = real_backend
                entry["real_backend"] = real_backend
                entry["output_file"] = out_file
                if test_backend:
                    entry["not_scientific_output"] = True
                executed += 1
            except subprocess.TimeoutExpired:
                entry["status"] = "failed"
                entry["error_type"] = "ProbeTimeout"
                entry["error_message"] = f"Job timed out after {timeout_sec}s"
                failed += 1
            except OSError as exc:
                entry["status"] = "failed"
                entry["error_type"] = "OSError"
                entry["error_message"] = str(exc)
                failed += 1
            except Exception as exc:
                entry["status"] = "failed"
                entry["error_type"] = type(exc).__name__
                entry["error_message"] = str(exc)
                failed += 1

        with open(os.path.join(run_dir, "execution.json"), "w") as fh:
            json.dump(entry, fh, indent=2)
        runs_out.append(entry)

    # ── Build manifest ────────────────────────────────────────
    manifest: dict = {
        "manifest_version": "3D-1c",
        "phase": "Phase 3D-1c",
        "capability": "docking_execution_wrapper",
        "method": method,
        "runtime": runtime,
        "dry_run": dry_run,
        "test_backend": test_backend,
        "real_backend": real_backend,
        "docking_performed": any(r.get("docking_performed", False) for r in runs_out),
        "calibration": "uncalibrated",
        "score_semantics": "computational docking output only; uncalibrated; not an experimental measurement",
        "runs": runs_out,
        "summary": {
            "total": len(runs_out), "planned": planned,
            "executed": executed, "skipped": skipped, "failed": failed,
        },
    }

    manifest_path = os.path.join(output_dir, "docking_execution_manifest.json")
    with open(manifest_path, "w") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)

    return manifest


def _sanitize(raw: str) -> str:
    import re
    return re.sub(r'[^a-zA-Z0-9_-]', '_', str(raw))[:60] or "unknown"


def _error_manifest(output_dir: str, reason: str) -> Dict[str, Any]:
    return {
        "manifest_version": "3D-0", "phase": "Phase 3D-0",
        "capability": "docking_adapter_scaffold",
        "docking_performed": False, "dry_run": True,
        "calibration": "uncalibrated",
        "error": reason, "runs": [],
        "summary": {"planned": 0, "skipped": 0, "failed": 0},
    }
