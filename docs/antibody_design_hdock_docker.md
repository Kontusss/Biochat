# Biochat Antibody Design — HDOCK Docker Runtime

## Overview

macOS Apple Silicon cannot execute Linux x86-64 HDOCK binaries directly.
The solution is Docker with `--platform linux/amd64`.

## Prerequisites

1. Docker Desktop installed and running (`docker info` succeeds).
2. HDOCK binary directory at a known host path.
3. `hdock-runner:latest` Docker image built.

## Building the Docker Image

```bash
cd /path/to/HDOCKlite-v1.1/..
docker build -t hdock-runner:latest -f Dockerfile.hdock .
```

The Dockerfile requires only:
```dockerfile
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y libc6 libstdc++6 libfftw3-3
WORKDIR /work
```

## Usage

### Check availability

```python
from biomni.tool.antibody_design.hdock_docker import check_hdock_docker_available
result = check_hdock_docker_available()
# {"available": true, "runtime": "docker", "platform": "linux/amd64"}
```

### Run docking via Docker

```python
from biomni.tool.antibody_design.hdock_docker import run_hdock_docker
result = run_hdock_docker(
    receptor_pdb="receptor.pdb",
    ligand_pdb="ligand.pdb",
    output_dir="output/",
    candidate_id="candidate_001",
)
# {"success": true, "docking_performed": true, "real_backend": true}
```

### Use the unified runner

```python
from biomni.tool.antibody_design.docking_runner import run_docking_jobs
result = run_docking_jobs(manifest, output_dir, runtime="docker")
```

### Inspect HDOCK output

```python
from biomni.tool.antibody_design.hdock_output import inspect_hdock_output
result = inspect_hdock_output("output/hdock.out")
# {"format_detected": true, "score_parsed": false, "ranking_performed": false}
```

### Plan createpl extraction (does NOT execute)

```python
from biomni.tool.antibody_design.hdock_output import plan_createpl_extraction
result = plan_createpl_extraction("hdock.out", "model_001.pdb", runtime="docker")
# {"planned": true, "extraction_performed": false}
```

## Important Notes

- All outputs are labeled `calibration: "uncalibrated"`.
- No score parsing is performed.
- No ranking is performed.
- No createpl extraction is executed by default.
- All results are computational predictions, NOT experimental measurements.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `docker: command not found` | Install Docker Desktop |
| `Cannot connect to Docker daemon` | Start Docker Desktop |
| `image not found` | Run `docker build` per above |
| `hdock_host_dir missing` | Set path to HDOCKlite-v1.1 directory |
| `hdock.out missing` | Check Docker WORKDIR; use `-w /output` |
