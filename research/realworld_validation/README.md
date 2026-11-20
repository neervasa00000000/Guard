# Real-world validation

Fictional surnames set in court, hospital, government, and letter pages by ReportLab, PyMuPDF, and Pillow. The question is whether a redaction rectangle's geometry still identifies the surname when the page is a real PDF, and what the coarser masks cost in neighboring words.

These are not confidential documents. The Dutch FOIA page images are not in this repository and are not analyzed here.

## Run

```sh
research/realworld_validation/setup.sh
research/realworld_validation/run_all.sh
```

`setup.sh` installs into the repository `.venv` only. LibreOffice, Poppler, and Ghostscript are not required; if they are missing, the study records that and does not invent a third PDF writer.

The protocol is `PROTOCOL.md`. It was locked before the 1,200-page run. Results land in `results/`. The verifier reads those CSVs and recomputes the intervals without importing the scorer.

## Outputs

- `results/attacker_results.csv` — one row per test page, policy, and attacker
- `results/policy_measurements.csv` — rectangle, area, neighbor words
- `results/worst_case_results.csv` — all 1,000 surnames, prior-weighted
- `results/repeated_releases.csv` — cumulative feasible sets
- `results/scan_results.csv` — simulated scan, labeled as simulated
- `results/statistics.json` — intervals and the paired tests
- `results/verification.json` — independent recomputation
- `reports/FINAL_VALIDATION_REPORT.md` — the twenty questions
