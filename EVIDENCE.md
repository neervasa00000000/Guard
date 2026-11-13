# Evidence for the printed manuscript

The manuscript is `paper_v6_1_ieeeaccess.pdf`. Each section names the files in this tree, whether they are the archived result or only a summary, and the command that rebuilds the result. A rebuild that needs the external review kit uses that kit at the path recorded in [research/e1/review4/a3_start/RUN_INFO.md](research/e1/review4/a3_start/RUN_INFO.md). Those kit scripts are not in this repository. `scripts/check_numbers.py` recomputes the cells this tree can check.

## Padding sweep

Archived summary, not the per-target sweep. `research/e1/review4/pooled.csv` has the five lists at 12, 16, and 24 px, plus the size-pooled `all` rows, for exact boxes, square grids, width-only grids, edge-aligned padding (`ink-anchored`), and start-aligned padding (`pen-anchored`). Companion files are `per_font.csv`, `padding_minus_64.csv`, and `matched_overredaction.csv`. The per-target `.npz` units written by the sweep are not archived.

Rebuild, after the surname sanity check has passed and the font archive has been checked:

```sh
docker build -t guard-e1-review4 research/e1/review4
sh research/e1/review4/run_sanity.sh "$KIT" "$PWD/Rerun/e1_fonts.tar.gz" \
  "$PWD/Rerun/e1_fonts" sweep
```

Seed `[20261029, dictionary_index, font_index, size]`. Dictionary order is surnames, words, digits, dates, emails. Font order is DejaVu Sans, DejaVu Serif, Liberation Sans, Liberation Serif, Noto Sans, Liberation Mono. Percentile intervals resample the six font clusters 10,000 times with seed `20261110`.

## Start-aligned padding at 12, 16, and 24 px

Archived in `pooled.csv` as `pen-anchored-*`. For surnames, LAYOUT-BOX, A1, class 128, n = 12,000:

| Size | Top-10 | Bits | Median area |
|---:|---:|---:|---:|
| 12 px | 0.061333 | 0 | 4.317× |
| 16 px | 0.056833 | 0.002504 | 3.446× |
| 24 px | 0.068833 | 0.233226 | 2.424× |

The same file has the other classes (32, 64, 96, 192, 256), both box models, and A2. The 24 px seed replay is a separate archive: `research/e1/review4/a3_start/size_summary.csv` and `size_cases.csv.gz` (16,000 case rows). That replay is 24 px only. There is no 12 px case archive in `a3_start/`.

The sweep command above rebuilds the 12/16/24 summary. The 24 px seed correction is:

```sh
sh research/e1/review4/a3_start/run.sh --size-replay
.venv/bin/python research/e1/review4/a3_start/finish_summary.py research/e1/review4/a3_start
```

`run.sh` needs the Docker image `guard-e1-review4-forms`, the review kit, and the checked fonts. Its default kit path is the one in `RUN_INFO.md`.

## Jitter, re-renders, and the unjittered 24 px value

Three archives, plus the start-aligned replay:

- `research/e1/cases/followup/d1_cases.csv.gz` — main-sweep jitter, 288,000 rows. D1 extends each side by 0–16 px and then snaps. The full raw unit directory is not archived.
- `research/e1/cases/followup/d2jit_cases.csv.gz` — likelihood-weighted jitter, 96,000 rows. `research/e1/cases/posterior/d2jit16_cases.csv.gz` — 64,000 rows at 16 px. `d2jit_pooled.csv` is not in this tree. The number audit found no 16 px surname or word row in that missing summary; the 24 px likelihood bits 0.275 and 0.567 are the printed 0.28 and 0.57.
- `research/e1/review4/a3_start/results_cases.csv.gz` — 1,096,000 case rows for shifted copies, jitter, harder sets, font, size, and renderer. `results_summary.csv` is the cell summary. Both are archived.

The unjittered 24 px DejaVu Sans start-aligned cell is the `k = 1` row, not the `k = 5` end of the jitter comparison. In `results_summary.csv`, condition `jitter`, surnames, DejaVu Sans, 24 px, layout, class 128, grid 1, A1, k = 1: top-10 9.25%, bits 0.357191, median area 2.334×, n = 2,000. The same row at k = 5 is the jittered value, 10.25% and 0.638399 bits. The ink-box twin at k = 1 is 9.25% and 0.342669 bits.

`scripts/rerun_full.sh` regenerates the original D1 jitter cells inside the main sweep. The start-aligned jitter replay is `sh research/e1/review4/a3_start/run.sh`. Jitter appends `[128, 4]` to `[20261029, dictionary_index, font_index, size]`. Re-rendering uses `[20261120, 2, dictionary_index, size, scenario_index]`. The paired bootstrap uses 10,000 draws and seed `20261117`. The re-render script in the kit is `v5.7-ieee/new_tests_review2/scripts/s234.py`; it is not in this tree. Its archived outputs `s2_rerender.csv` and `s3_knownstart.csv` are not in this tree either. The class-change count from that re-render, 171 of 2,000 at 24 px, is the archived `font` row of `results_summary.csv`.

## A3 copies per case

Archived. `research/e1/cases/posterior/a3_cases.csv.gz` has 128,000 rows with dictionary, font, size, grid, copy count `k`, and case index. That is the published A3 row count. The generator `a3_exact.py` is in the kit at `v5.7-ieee/new_tests_posterior/scripts/a3_exact.py` and is not in this tree.

The in-tree replay writes one row per case and copy count to `research/e1/review4/a3_start/cases.csv.gz` (1,088,000 rows) and `results_cases.csv.gz`. Rebuild:

```sh
sh research/e1/review4/a3_start/run.sh
.venv/bin/python research/e1/review4/a3_start/report.py \
  research/e1/review4/a3_start "$KIT"
```

Copy offsets are uniform on 0–63 px. The first copy has offset zero, so k = 1 matches A2 on the same target. The main-sweep seed continues after the 2,000 targets and the 400 calibration strings. Original 16 px shifted copies reuse that stream. Harder offsets append `[128, 3]`.

## Mock forms

Archived tables and case scores, not the rendered pages. Under `research/e1/review4/forms/`: `start_policy_summary.csv`, `start_vs_grid16_paired.csv`, `libreoffice_start_cases.csv`, `pillow_start_cases.csv`, `libreoffice_layout_start.csv`, `libreoffice_hit_check.csv`, `libreoffice_geometry_diff.csv`, `replayed_forms_obs.csv`, and `replayed_calib_obs.csv`. The form PDFs, scans, and LibreOffice profile are not in this tree.

```sh
sh research/e1/review4/forms/run_replay.sh \
  "$KIT" "$PWD/Rerun/e1_fonts" \
  "$HOME/tileseal-t3-lm/csv/test3_docs.json" start \
  > research/e1/review4/forms/start_replay.log 2>&1
python3 research/e1/review4/forms/report_start.py research/e1/review4/forms
```

The paired bootstrap resamples forms 4,000 times with seed `20261117`. LibreOffice was not present on the machine that prepared this release. Start recovery from a standalone scan was not tested.

## Language-model test

The printed language-model table is Table V. Its sentence-alone baseline is **179/400**, not 180/400.

179/400 = 44.75%. The Wilson interval is [39.950%, 49.650%], which the footnote prints as 44.8 [40.0, 49.7] after rounding 49.65 half-up. 180/400 = 45.0% with Wilson [40.2, 49.9]. That 45.0% is the sentence-alone rate in the later padding rerun, the comparison printed next to 45.25% and 45.0% with the box. It is not the Table V footnote.

`research/e1/cases/followup/e1_a4_cases.csv.gz` is the DejaVu Sans main run, 400 items by five grids. Full-sentence top-10 counts are exact 388, 8 px 321, 16 px 283, 32 px 235, and 64 px 199. Those print as 97.0, 80.3, 70.8, 58.8, and 49.8. `rank_lm_nobox` is filled for 100 of the 400 items, and 25 of those 100 are inside the top 10. That column is not 179/400 or 180/400. `a4_reproduction.csv`, `a4_summary.csv`, and `a4_padding_cases.csv` are not in this tree, so the 179 and 180 counts cannot be recounted here. The Liberation Serif follow-up (200/400 at 64 px) is in the same missing reproduction file.

Replot the archived DejaVu run:

```sh
python3 -m venv /tmp/e1-venv
/tmp/e1-venv/bin/python -m pip install -r research/e1/requirements.txt
/tmp/e1-venv/bin/python research/e1/scripts/e1_extra_figs.py
```

Outputs go to `out/e1-rerun/figures/` (`fig_e1_a4_context`, `e1_a4_summary.csv`, `e1_a4_baselines.json`). This does not call the model. Regenerating ranks needs Qwen2.5-0.5B `model.safetensors` SHA-256 `88c142557820ccad55bb59756bfcfcf891de9cc6202816bd346445188a0ed342`, fetched by `scripts/fetch_data.py`, and the original scoring script, which is not in this tree. Single-threaded reruns of 12 items matched; multi-threaded ones did not. The paper treats that as about ±0.5 points.

## Attacker-knowledge tests

Archived per target, not as the cluster summaries. `research/e1/cases/followup/test4_cases.csv.gz` has 276,000 rows and the ten variants K, Fu, Su, FSu, Fw, Fw_tol2, Sw, Dn_top5000, Dd_drop50, and Pu_uniform_prior. `test4_fontcluster.csv`, `test4_drop_vs_K_fontcluster.csv`, and `s4_priors.csv` are not in this tree. The Fig. 3 known-font, known-size baseline is archived as `research/e1/review4/fig3_baseline.csv` and `fig3_cases.csv.gz` (96,000 rows).

```sh
sh research/e1/review4/run_sanity.sh "$KIT" "$PWD/Rerun/e1_fonts.tar.gz" \
  "$PWD/Rerun/e1_fonts" fig3
```

That runs the kit script `results/e1-followup/test4/test4_imperfect.py` through `research/e1/review4/fig3.py`. The Fig. 3 seed is `[20261110, dictionary_index, font_index]`.

## Real-box geometry

Archived derived tables. Page images are not included. `research/e1/csv/foia_boxes.csv` is the box list. `research/e1/csv/foia_geometry_summary.csv`, subset `all`, grid 1: n = 11,351, median width 228 px, median height 49 px. The 25–90 px single-line subset has 10,619 boxes. Black-only boxes are 3,914. Median height is the `median_h` column of the exact-grid row; snapping does not change it.

`e1_extra_figs.py` plots these files and does not remeasure the pages. There is no command in this tree that rebuilds `foia_boxes.csv` from images.

## Own-height cells

Not archived. The manuscript names `w1_pooled.csv` for the cells that pad width and keep the box's own height, printed as 1.41 to 2.27 bits. That file is not in this tree, and no script here implements that policy. `research/e1/review4/geometry.py` pads start-aligned and edge-aligned boxes to the shared line, not to each box's own height. Those cells cannot be rebuilt from this checkout.

## How surname ties are broken

The list cut-off and the score ties are different.

The surname list is the first 50,000 alphabetic names in `Names_2010Census.csv`, in file order, with no further sort (`census()` in `research/e1/scripts/e1lib.py`). The manuscript says the 50,000th place falls inside names with count 419, and that tie is broken by census file order. The CSV is not in the repository. Its SHA-256 is `6b4933178060b4e5ac8dd9a611ec15472d35eab98fe9027474bc5ccc5b7a8708`, checked by `scripts/fetch_data.py`.

Score ties are not broken by file order or by a seed. `metrics()` counts a top-k hit in expectation: if the truth is tied with others of equal prior, the hit is `(k - number strictly ahead) / number tied`, clipped to [0, 1]. A published seed for assigning each tied target to one side was not found, so the paired tests do not run McNemar.
