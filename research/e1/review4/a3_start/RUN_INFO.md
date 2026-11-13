# Run information

The retained inputs are under `/private/tmp/tileseal-review4.EKJJXk`. The published grid audit is `v5.7-ieee/new_tests_posterior/scripts/a3_exact.py` and `csv/a3_cases.csv.gz`. The companion files for the shifted copies and padding controls are `v5.7-ieee/new_tests_padding/scripts/a3_padding.py`, `csv/cases_a3/`, `csv/a3_reproduction_caselevel.csv`, and `csv/a3_padding_pooled.csv`. The harder sets are in `scripts/a3_padding_stress.py` and `csv/cases_stress/` in that directory. The re-rendering and known-start replay is `v5.7-ieee/new_tests_review2/scripts/s234.py` with `csv/s2_rerender.csv` and `csv/s3_knownstart.csv`. The boundary check is `scripts/s1_boundary.py` with `csv/s1_boundary_sets.csv` in the same directory. The archived likelihood-weighted jitter results are `v5.7-ieee/new_tests_review3/scripts/d2jit_exact.py` and `csv/d2jit_pooled.csv`. The review4 start-aligned implementation is the checked-out `research/e1/review4/geometry.py`. It is an untracked artifact, so a copy in Git is NOT FOUND.

The main seed components are `[20261029, dictionary_index, font_index, size]`. Original 16 px shifted copies reuse the main RNG stream. Original padding jitter appends `128` to that seed. Harder offsets and jitter append `[128, 3]` and `[128, 4]`. Re-rendering uses `[20261120, 2, dictionary_index, size, scenario_index]`. The paired bootstrap uses 10,000 draws and seed 20261117.

The offline Docker run used Python 3.12.16, NumPy 2.5.4, pandas 3.1.1, Pillow 12.3.0, and RAQM 0.10.5. The container had read-only input mounts, an isolated output mount, and networking disabled. Font hashes were checked against the kit manifest. [Run log and wall time](run.log) · [Git before](git_before.txt) · [Git after](git_after.txt)

```sh
sh research/e1/review4/a3_start/run.sh > research/e1/review4/a3_start/run.log 2>&1
PYTHONPATH="$PWD/.venv-c2pa/lib/python3.13/site-packages" PYTHONDONTWRITEBYTECODE=1 \
  "$HOME/tileseal-t3-lm/venv/bin/python" research/e1/review4/a3_start/verify_inputs.py \
  /private/tmp/tileseal-review4.EKJJXk > research/e1/review4/a3_start/input_check.log 2>&1
"$HOME/tileseal-t3-lm/venv/bin/python" research/e1/review4/a3_start/report.py \
  research/e1/review4/a3_start /private/tmp/tileseal-review4.EKJJXk
```

The initial run's new-size rows used the 16 px seed unit. The 24 px seed unit used in Table X was replayed separately for both width classes. The report combines the corrected rows with the other conditions in `results_cases.csv.gz` and `results_summary.csv`. The verification recomputed the original bootstrap from the stored trial rows.

```sh
sh research/e1/review4/a3_start/run.sh --size-replay > research/e1/review4/a3_start/size_run.log 2>&1
"$HOME/tileseal-t3-lm/venv/bin/python" research/e1/review4/a3_start/finish_summary.py research/e1/review4/a3_start
```
