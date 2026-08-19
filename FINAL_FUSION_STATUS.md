# Fusion Plan v1 — Final Status

**Date**: 2026-08-03

## Completed Phases

| Phase | Capability | Status | Backend |
|-------|-----------|--------|---------|
| 3A | Sequence scoring + anti-copy + penalty ranking | ✅ | Pure Python |
| 3B | DiffCDRH3 diffusion model CDRH3 generation | ✅ | PyTorch (nb2_biochat_env) |
| 3C-0 | Structure readiness pre-screening | ✅ | Pure Python |
| 3C-1 | Structure modeling interface (dry-run/mock) | ✅ | Pure Python |
| 3C-2 | Real NB2 backend detection + PDB validation | ✅ | ImmuneBuilder (nb2_biochat_env) |
| 3C-3 | Real NanoBodyBuilder2 structure prediction | ✅ | ImmuneBuilder.NanoBodyBuilder2 |
| 3C-4 | Docking input preparation (receptor/ligand/constraints) | ✅ | Pure Python |
| 3D-0 | Docking adapter scaffold (dry-run command construction) | ✅ | Pure Python |
| 3D-1a | HDOCK availability semantics (binary_present vs executable_usable) | ✅ | Pure Python |
| 3D-1b | Docking execution wrapper (fake-backend tests) | ✅ | Pure Python |
| 3D-1c | Docker HDOCK execution + integration | ✅ | Docker (linux/amd64) |
| 3D-1d | HDOCK output QC + createpl readiness/planning | ✅ | Pure Python |

## Validated Environments

| Environment | Python | Torch | ImmuneBuilder | HDOCK | Docker |
|------------|--------|-------|--------------|-------|--------|
| nb2_biochat_env | 3.11.13 | 2.2.2 | 1.2 | — | ✅ |
| openfold_m1 | 3.10.20 | — | ✅ | Linux ELF | — |

## Key Modules

```
biochat/tool/antibody_design/
├── __init__.py                  Public API
├── api.py                       design_vh_only_antibodies()
├── schemas.py                   Constants, penalty table
├── validators.py                Anti-copy, epitope validation
├── scoring.py                   Base80 penalty deduction
├── generation_filter.py         CDRH3 hard-rule filtering
├── developability_checks.py     N-glyc, properties
├── charge_complementarity.py    Electrostatic assessment
├── antibody_format.py           Sequence formatting
├── ranking.py                   Multi-factor ranking
├── model_inference.py           DiffCDRH3 model architecture
├── diffusion_pipeline.py        Phase 3B generation
├── structure_prep.py            Phase 3C-0 readiness
├── structure_modeling.py        Phase 3C-1/3C-2/3C-3 modeling
├── structure_validation.py      PDB validation
├── nanobodybuilder2_adapter.py  NB2 detection + prediction
├── docking_prep.py              Phase 3C-4 input prep
├── docking_runner.py            Phase 3D runner + HDOCK detect
├── hdock_docker.py              Docker HDOCK adapter
├── hdock_output.py              Output QC + createpl readiness
└── models/                      DiffCDRH3 weights (63MB)
```

## Final Status Table

| Metric | Value |
|--------|-------|
| Score parsed | **False** |
| Ranking performed | **False** |
| createpl extraction performed | **False** (planned only) |
| Docking performed (Docker) | **True** (real, uncalibrated) |
| Calibration | **uncalibrated** |
| Experimental claims | **None** |
| Forbidden terms | **0 detected** |
| Real structure prediction | **True** (ImmuneBuilder.NanoBodyBuilder2) |
| CDRH3 generation | **True** (DiffCDRH3 diffusion model) |
| Smoke test | **Passed** |

## Known Limitations

1. HDOCK is Linux x86-64 only; macOS requires Docker runtime.
2. `createpl` extraction is planned but not executed (Phase 3D-1e reserved).
3. No docking score parsing or candidate re-ranking implemented.
4. No experimental calibration of computational scores.
5. NanoBodyBuilder2 requires ~200MB model weight download on first use.
6. DiffCDRH3 requires torch and 63MB model weights.

## Out of Scope (not implemented)

- Score-to-energy calibration
- Candidate re-ranking from docking results
- createpl model extraction
- Experimental validation claims
- Production deployment hardening

## Recommended Next Phases

1. **Phase 3D-1e**: Execute createpl extraction via Docker
2. **Phase 3D-2**: Parse docking scores (with calibration warnings)
3. **Phase 3E**: Contact analysis from docked poses
4. **Phase 4**: Full pipeline integration test on known antibody-antigen pair
