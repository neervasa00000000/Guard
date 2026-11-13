# E1 study artifacts

The release includes the original rendering, validation, attack and plotting scripts in [scripts/](scripts/), with local input and output paths. [RELEASE_FIXES.md](../../RELEASE_FIXES.md) lists the released records and documents the clean-table correction. The paper's snapping implementation is pinned to commit `f8f2558`.

## Rebuild the clean table offline

From the repository root, activate a virtual environment with the root `requirements.txt` installed and run:

```sh
bash scripts/reproduce.sh
```

This recomputes clean A2 from the archived posterior case rows, checks the tracked CSV, and writes tables and plots to `out/`. The original feasible-set summary remains available alongside the corrected CSV. The input fetcher is a separate command in `scripts/fetch_data.py`.

## Re-render the main sweep

Use Linux with Pillow 12.3.0 and RAQM. [The study Dockerfile](review4/Dockerfile) shows the library setup. The pinned Python requirements for this harness are separate from the product environment.

```sh
python3 -m venv /tmp/e1-venv
/tmp/e1-venv/bin/python -m pip install -r research/e1/requirements.txt
export PYTHON=/tmp/e1-venv/bin/python
export E1_FONT_DIR=/path/to/the/extracted/study/fonts
export E1_OUTPUT="$PWD/out/e1-rerun"
bash scripts/rerun_full.sh
```

Place the U.S. Census CSV at `data/census/Names_2010Census.csv` or set `E1_CENSUS`. Obtain it from the Census archive pinned in `scripts/fetch_data.py`. Use the six exact fonts listed in [fonts.json](inputs/fonts.json). If `E1_FONT_DIR` is unset, the harness checks the original absolute paths. The harness verifies the Census and font hashes and prints the actual rasterizer versions. The original versions were RAQM 0.10.5, HarfBuzz 14.2.1, FriBiDi 1.0.16 and FreeType 2.14.3. The font binaries are supplied separately.

`rerun_full.sh` regenerates the 12/16/24 px sweep and the nine 42 px units with the original seed scheme and 2,000 targets per unit, then runs the original feasible-set analysis and plots. Set `E1_PROCS` to control CPU workers. Completed units are reused. Use a fresh `E1_OUTPUT` directory if changing sample size, renderer inputs or environment. For a smaller smoke run, invoke `e1_run.py surnames` directly with `E1_N` set to a small count and use a separate output directory.

`phase_exact.py` rescores clean A2 after the full sweep using the regenerated observations and calibrated tolerances. Its output goes into the run's `csv/` directory. The offline table rebuild uses the archived posterior rows under `cases/posterior/`. Mock forms, language-model inference and FOIA collection have separate workflows. The extra figure script uses the archived FOIA geometry and A4 scores. Set `E1_GUARD` to a checkout of `f8f2558` to run the historical Guard validation.

To rebuild the extra figures from the archived A4 and FOIA results, run `"$PYTHON" research/e1/scripts/e1_extra_figs.py`. The A4 plot also uses the wordfreq prior.

## Released inputs and outputs

- [cases/](cases/) contains gzip-compressed per-target archives. `main-subset/` has the four retained original cells and target manifests. `posterior/` has the A2 likelihood rescoring, A3, and follow-up checks. `stress/` and `followup/` contain archived follow-up rows. Several files record alternative scores for the same targets.
- [csv/](csv/) contains the validation receipt and the derived FOIA geometry used by the extra plots. No FOIA page images are included.
- [review4/](review4/) and [mdpi_checks/](mdpi_checks/) contain later results, scripts, font-cluster statistics and run logs.
- The kit excluded the full original main per-target directory. See the full-rerun command above for regenerating those cells.
