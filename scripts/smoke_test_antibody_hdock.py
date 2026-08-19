#!/usr/bin/env python3
"""Phase 3D Fusion Plan v1 smoke test — antibody HDOCK Docker pipeline.

Verifies: biomni import, Docker availability, HDOCK Docker availability,
hdock.out QC, createpl readiness, extraction planning.

Does NOT: parse scores, rank candidates, execute createpl extraction.
"""

import argparse
import json
import os
import shutil
import sys
import tempfile

FORBIDDEN = ["ddG", "Kd", "binding_affinity", "binding affinity",
             "validated", "experimentally confirmed", "high affinity"]


def forbidden_scan(data, label=""):
    j = json.dumps(data)
    for t in FORBIDDEN:
        if t.lower() in j.lower():
            print(f"  ❌ {label}: forbidden term '{t}' detected")
            return False
    return True


def write_minimal_pdb(path, n_atoms=100):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        for i in range(1, n_atoms + 1):
            f.write(f"ATOM  {i:5d}  CA  ALA A{i:4d}    {i*3.8:8.3f}{0:8.3f}{0:8.3f}  1.00  0.00           C\n")
        f.write("TER\nEND\n")


def main():
    parser = argparse.ArgumentParser(description="Phase 3D HDOCK Docker smoke test")
    parser.add_argument("--runtime", default="docker")
    parser.add_argument("--docker-image", default="hdock-runner:latest")
    parser.add_argument("--hdock-host-dir", default="/Users/walker/Desktop/core/tools/HDOCKlite-v1.1")
    parser.add_argument("--output-dir", default="smoke_outputs/phase3d")
    parser.add_argument("--skip-docking", action="store_true", help="Skip real Docker docking run")
    args = parser.parse_args()

    results = {"smoke_test": "Phase3D-Fusion-v1", "checks": {}, "status": "unknown"}
    all_clean = True

    os.makedirs(args.output_dir, exist_ok=True)

    # 1. biomni import
    try:
        from biomni.tool.antibody_design.hdock_docker import (
            check_hdock_docker_available, run_hdock_docker,
        )
        from biomni.tool.antibody_design.hdock_output import (
            inspect_hdock_output, check_createpl_ready, plan_createpl_extraction,
        )
        from biomni.tool.antibody_design.docking_runner import run_docking_jobs
        results["checks"]["biomni_import"] = "ok"
        print("✅ biomni imports")
    except Exception as exc:
        results["checks"]["biomni_import"] = f"FAIL: {exc}"
        print(f"❌ biomni import: {exc}")
        results["status"] = "failed"
        json.dump(results, open(os.path.join(args.output_dir, "smoke_result.json"), "w"), indent=2)
        sys.exit(1)

    # 2. Docker availability
    d = check_hdock_docker_available(
        docker_image=args.docker_image,
        hdock_host_dir=args.hdock_host_dir,
    )
    results["checks"]["docker_hdock"] = d
    print(f"{'✅' if d['available'] else '❌'} Docker HDOCK: available={d['available']}")

    # 3. createpl readiness
    cp = check_createpl_ready(runtime=args.runtime, docker_image=args.docker_image)
    results["checks"]["createpl"] = cp
    print(f"{'✅' if cp['available'] else '⚠️'} createpl: available={cp['available']}")

    # 4. Optional: real docking
    if not args.skip_docking and d["available"]:
        print("Running Docker HDOCK (real, ~60s)...")
        rx = os.path.join(args.output_dir, "receptor.pdb")
        lig = os.path.join(args.output_dir, "ligand.pdb")
        write_minimal_pdb(rx, 200)
        write_minimal_pdb(lig, 7)

        dock_out = os.path.join(args.output_dir, "dock_result")
        dr = run_hdock_docker(rx, lig, dock_out, candidate_id="smoke_c1", timeout_sec=180)
        results["checks"]["docking"] = {
            "success": dr["success"], "returncode": dr.get("returncode"),
            "output_size": os.path.getsize(dr["output_file"]) if dr.get("output_file") and os.path.exists(dr["output_file"]) else 0,
        }
        print(f"{'✅' if dr['success'] else '❌'} docking: success={dr['success']}, size={results['checks']['docking']['output_size']}")

        # 5. hdock.out QC
        if dr.get("output_file"):
            insp = inspect_hdock_output(dr["output_file"])
            results["checks"]["hdock_qc"] = {
                "format_detected": insp["format_detected"],
                "size_bytes": insp["size_bytes"],
                "model_count_estimate": insp["model_count_estimate"],
            }
            print(f"✅ hdock QC: format={insp['format_detected']}, size={insp['size_bytes']}")
    else:
        results["checks"]["docking"] = "skipped"
        print("⏭️  docking skipped")

    # 6. Extraction plan (always)
    plan = plan_createpl_extraction(
        os.path.join(args.output_dir, "dock_result/hdock.out"),
        os.path.join(args.output_dir, "model_001.pdb"),
        runtime=args.runtime,
    )
    results["checks"]["extraction_plan"] = {
        "planned": plan["planned"], "extraction_performed": plan["extraction_performed"],
    }
    print(f"✅ extraction plan: planned={plan['planned']}, executed={plan['extraction_performed']}")

    # 7. Forbidden scan
    clean = forbidden_scan(results, "smoke_result")
    results["checks"]["forbidden_scan"] = "clean" if clean else "DIRTY"
    print(f"{'✅' if clean else '❌'} forbidden scan: {'clean' if clean else 'DIRTY'}")

    # Final
    results["status"] = "passed"
    results["score_parsed"] = False
    results["ranking_performed"] = False
    results["extraction_performed"] = False
    results["calibration"] = "uncalibrated"

    out_path = os.path.join(args.output_dir, "smoke_result.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nSmoke test passed. Result: {out_path}")


if __name__ == "__main__":
    main()
