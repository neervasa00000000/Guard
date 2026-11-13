# Release report

Branch: `paper-release-v1`, created from `7f3f73ad13a64d26ff617c2420ee9898e4041487` on `codex/e1-review4`.

Commit hash: `d9c596c2c213cb1437c389a85dd205f2ea0c7854`

## Inventory

Product, on this branch: `grd.py`, `grd_geometry.py`, `src/`, and `tileseal/` (a wrapper that calls `grd.main`). Seal, redact, and verify run. Tests: `tests/test_release_product.py`, `tests/test_padding.py`, `tests/test_vectors.py`.

`pad_box` from commit `eebdcfb` is still the centred grow with a 32 px minimum height. It is not the paper's start-aligned policy. Product decision pending. It was not changed.

Research on this branch:

| Part | Path | Runs from this checkout |
|---|---|---|
| E1 harness scripts | copied only as the stored result tables; the render harness stays in the local kit | Full rerun DOES NOT REPRODUCE (render harness is not in this checkout) |
| A1–A4, grids, padding, box height | `research/e1/review4`, kit CSVs under `results/paper/e1` | Tables regenerate from the CSVs |
| A3 start-aligned copies | `research/e1/review4/a3_start` | Result files present |
| Mock forms | `research/e1/review4/forms` | Result files present |
| Posterior check | `research/e1/mdpi_checks/posterior_toy` | Result files present |
| Paired tests | `research/e1/mdpi_checks/paired_stats` | Result files present |
| Number audit | `research/e1/mdpi_checks/number_audit` | Written from the printed PDF |
| Tool check 392/392 | `e1_validation_summary.json` in the local kit | The summary number is in the audit |

The v6.1 `.tex` was NOT FOUND. The printed PDF is committed as `paper_v6_1_ieeeaccess.pdf` (563 KB, SHA-256 `85b8a84f052bbdae861dbabf4eda718fb9d7bc8be8d62ee008f88db204006a6e`). That is the file the number audit already used.

## Excluded

- `research_e1_bundle.zip`: not in the tree, not added.
- Census surname file: downloaded by `scripts/fetch_data.py` from the Census Bureau zip. The CSV SHA-256 is the digest of the local file the study used. The CSV is not committed.
- Gutenberg texts: hashes are in `scripts/fetch_data.py`; the texts are not committed.
- Language-model weights: `scripts/fetch_data.py` checks Qwen2.5-0.5B `model.safetensors` against the local study file. The weights are not committed.
- van Heusden page images: not present. Derived box measurements are described in `DATA_LICENSE.md`.
- Private keys: none committed. `*.pem` and `*.key` stay ignored. The release test creates a demo Ed25519 key in a temporary directory and deletes it.
- No `.env` or API token was added.

## Tests

`pytest -q` on the Python tests in this checkout: 6 passed.

`scripts/regenerate_tables.py` wrote `out/tables` and `out/figures` from the committed CSVs. `table_clean.md` is the original feasible-set pool. The paper's Table II attacker-2 column matches the later exact-likelihood pool in `research/e1/review4/pooled.csv`. The three figures are rebuilt from the feasible-set pool.

`scripts/check_numbers.py`: MATCH 34, ROUNDING 4, MISMATCH 7, NO SOURCE FOUND 3. The mismatches are listed in `research/e1/mdpi_checks/number_audit/NUMBER_AUDIT.md`. They are printed-paper differences, not a failure of the table rebuild.

The 200-target test checks the stored A1 comparison (200 rows, all matching). A fresh render of that cell DOES NOT REPRODUCE here because the census file's SHA-256 is NOT FOUND. LibreOffice was NOT FOUND, so the LibreOffice form path was not rerun.

## Clean room

Clone of `paper-release-v1` at `f5f12134c4c55f8ee34db666b212fc7a97e5358d` into `/tmp/guard_clean`. Fresh virtualenv from `requirements.txt`.

`pytest -q`: 6 passed in 19.00 seconds.

`bash scripts/reproduce.sh`: exit 0. Tables and the three figures were written. Gutenberg downloads were NOT FOUND: Python's SSL store reported `CERTIFICATE_VERIFY_FAILED`. Census SHA-256 NOT FOUND. Language-model weights NOT FOUND. Wall time for clone, install, tests, and reproduce together: 82 seconds.

Release checkout is about 41 MB, of which `.git` is 21 MB. The packed history is 70 MB.

## What Neer does next

1. Review this branch.
2. `git push origin paper-release-v1`
3. Connect the repository to Zenodo and create a GitHub release.
4. Send the DOI and the commit hash back. The citation DOI is `PLACEHOLDER`.
