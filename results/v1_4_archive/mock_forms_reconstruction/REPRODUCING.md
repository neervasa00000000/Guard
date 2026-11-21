# Reproducing and interpreting the LibreOffice reconstruction

The exact local image used was `sha256:5dbe864977e1277e1d20c30166f53796026ca247d8049c789929967cca490da7`. Its LibreOffice version is LibreOffice 25.2.3.2 520(Build:2). The historical runtime build recipes were recovered unchanged from commit 733d48a and are archived with source hashes under ../recovered_sources/. They install operating-system packages from moving repositories, so they do not guarantee the identical image digest; the experiment rejects a different LibreOffice version and checks both font binaries.

```sh
docker build -t guard-e1-review4 -f results/v1_4_archive/recovered_sources/Dockerfile.review4 .
docker build -t guard-e1-review4-forms -f results/v1_4_archive/recovered_sources/Dockerfile.forms .
research/realworld_e1_eval/.venv/bin/python -B scripts/run_lo_reconstruction.py
research/realworld_e1_eval/.venv/bin/python -B scripts/validate_lo_reconstruction.py
```

Use `--image LOCAL_IMAGE` to select a compatible local image; the resolved image ID is recorded. No image is pulled automatically. The host uses the pinned E1 Python/font/Census dependencies. The local container receives only the two checked font files, scripts and an ignored working folder, and runs with `--network none`. Generated documents, PDFs, glyph images and text requests remain in ignored out/v14-lo-reconstruction/.

The no-text candidate_geometry.csv.gz is sufficient to recompute all candidate feasibility/ranking without LibreOffice or font binaries. The independent validator uses full 50000-element arrays and original E.metrics rather than the grouped scoring implementation. It also rebuilds every box, calibration interval, mean and bootstrap CI.

## Exact-box comparison

Rates are percentages. New 95% CIs use 10000 form-bootstrap draws, seed 20261121. Historical rates are fixed archived comparisons, not uncertainty estimates. The template and local-word scan differ from the original lost template/full-page scan; deltas do not isolate a single cause.

| Size px | Condition | Attacker | New truth-in % | New top-10 % [95% CI] | Historical top-10 % | Difference pp |
|---:|---|---|---:|---|---:|---:|
| 16 | clean | libreoffice_matched | 100.0 | 36.0 [27.0, 46.0] | 63.0 | -27.0 |
| 16 | clean | pillow_lo_calibrated | 100.0 | 31.0 [22.0, 40.0] | 31.0 | +0.0 |
| 16 | clean | pillow_mismatch | 0.0 | 0.0 [0.0, 0.0] | 0.0 | +0.0 |
| 16 | scan | libreoffice_matched | 97.0 | 27.0 [19.0, 36.0] | 22.0 | +5.0 |
| 16 | scan | pillow_lo_calibrated | 97.0 | 26.0 [18.0, 35.0] | 22.0 | +4.0 |
| 16 | scan | pillow_mismatch | 99.0 | 26.0 [18.0, 35.0] | 23.0 | +3.0 |
| 24 | clean | libreoffice_matched | 100.0 | 49.0 [39.0, 59.0] | 73.0 | -24.0 |
| 24 | clean | pillow_lo_calibrated | 100.0 | 40.0 [30.0, 50.0] | 40.0 | +0.0 |
| 24 | clean | pillow_mismatch | 2.0 | 1.0 [0.0, 3.0] | 3.0 | -2.0 |
| 24 | scan | libreoffice_matched | 99.0 | 34.0 [25.0, 44.0] | 34.0 | +0.0 |
| 24 | scan | pillow_lo_calibrated | 99.0 | 32.0 [23.0, 41.0] | 31.0 | +1.0 |
| 24 | scan | pillow_mismatch | 84.0 | 25.0 [17.0, 34.0] | 35.0 | -10.0 |

All 72 rows, including other policies, entropy-based attacker-performance scores, area and coverage, are in summary.csv. No-box area/coverage fields are explicitly blank. The old results and manuscript numbers remain unchanged; this new run is not a historical replication.
