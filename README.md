# Black Box Redaction

This folder holds the paper **What the Black Box Reveals: Measuring Redaction-Geometry Leakage and the Tile-Snapping Trade-off in Images** and TileSeal, the tool that seals an image, black out a rectangle on a tile grid, and checks the result. The printed paper is `paper_v6_1_ieeeaccess.pdf`.

## Install

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Reproduce the paper

The printed manuscript is `paper_v6_1_ieeeaccess.pdf` (SHA-256 `85b8a84f052bbdae861dbabf4eda718fb9d7bc8be8d62ee008f88db204006a6e`). Claim-level files and rebuild commands are in [EVIDENCE.md](EVIDENCE.md). `scripts/check_numbers.py` checks this manuscript's A2 column against `research/e1/review4/pooled.csv`. It does not read the IEEE PDF. The earlier PDF transcript at `research/e1/mdpi_checks/number_audit/NUMBER_AUDIT.md` is historical and is not replayed.

### Versions

Offline tables, on the machine that prepared this release: Python 3.13.2 and the root `requirements.txt` pins (`cryptography` 50.0.2, Pillow 13.0.0, NumPy 2.5.4, pandas 3.1.1, matplotlib 3.10.7, pytest 8.4.2). This environment has no RAQM.

Study renders and the review container: Python 3.12.16, Pillow 12.3.0, NumPy 2.5.4, pandas 3.1.1, wordfreq 3.1.1, RAQM 0.10.5, HarfBuzz 14.2.1, FriBiDi 1.0.16, FreeType 2.14.3. One review container reported FriBiDi 1.0.8. The language-model ranks used torch 2.15.0 and transformers 5.22.2. Those packages are not required for the offline command.

### Commands

| Result | Command | Inputs | Outputs | Seed |
|---|---|---|---|---|
| Table II and the Fig. 1–3 sources | `bash scripts/reproduce.sh` | `results/paper/e1/pooled_clean_feasible_set.csv`, `baselines_nobox.csv`, `research/e1/cases/posterior/phase_cases.csv.gz`, `phase_cases_digits.csv.gz` | `out/tables/table_clean.md`, `out/figures/fig1_bits.png`, `fig2_top10.png`, `fig3_tradeoff.png` | 10,000 font-cluster draws, seed `20261101` |
| Table III padding sweep, including start-aligned 12/16/24 px | `sh research/e1/review4/run_sanity.sh "$KIT" Rerun/e1_fonts.tar.gz Rerun/e1_fonts sweep` | External review kit and the six font files | Archived summary `research/e1/review4/pooled.csv`. Per-target sweep units are not archived | `[20261029, dictionary_index, font_index, size]`; interval seed `20261110` |
| Table IV A3 copies | `sh research/e1/review4/a3_start/run.sh` | Review kit, fonts, Docker image `guard-e1-review4-forms` | Archived `research/e1/cases/posterior/a3_cases.csv.gz` and `research/e1/review4/a3_start/results_cases.csv.gz` | Main seed, then offsets on 0–63 px. Harder sets append `[128, 3]` |
| Table V language-model plot from the archive | `/tmp/e1-venv/bin/python research/e1/scripts/e1_extra_figs.py` after `pip install -r research/e1/requirements.txt` | `research/e1/cases/followup/e1_a4_cases.csv.gz`, `research/e1/csv/foia_boxes.csv`, wordfreq | `out/e1-rerun/figures/fig_e1_a4_context.png`, `fig_foia_geometry.png` | Archived ranks. The model call is not repeated |
| Table VII real-box figure | The same `e1_extra_figs.py` command | `foia_boxes.csv`, `foia_geometry_summary.csv` | `out/e1-rerun/figures/fig_foia_geometry.png` | None. Pages are not remeasured |
| Full 12/16/24 px sweep, including D1 jitter | `bash scripts/rerun_full.sh` | Census CSV, six fonts, Pillow 12.3.0 with RAQM | `out/e1-rerun/csv/` | `[20261029, dictionary_index, font_index, size]`, `E1_N=2000` |

Dictionary index order is surnames, words, digits, dates, emails. Font index order is DejaVu Sans, DejaVu Serif, Liberation Sans, Liberation Serif, Noto Sans, Liberation Mono. The offline command is the one that runs without the kit:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
. .venv/bin/activate
bash scripts/reproduce.sh
```

### Hashes

Regenerated outputs from that command:

- `2456d0af883168bbafc6277779c99a2c4d1fa8368893ae5d73074576ff117d1c` `out/tables/table_clean.md`
- `ecc5c0395ed456c6470ee18ff77afc8ae5a4f846d4084c337beb4935ad8efe67` `out/figures/fig1_bits.png`
- `5ff37ad746a220168447e41dbf71fd776332752843f5ee808a75d0fa47b65d0d` `out/figures/fig2_top10.png`
- `0def3ae5cc74e7c5dd806e4311de8cccdeafc4b9497a43c0a3ec20a067802fc1` `out/figures/fig3_tradeoff.png`

Inputs to that command, and the other archives named above:

- `eaa52738c266093fdfe33b9ab27e161734c924d962a565b58babad7b95d86f63` `results/paper/e1/pooled_clean_feasible_set.csv`
- `6f037a837c1856b1219f4526e50aeca19410daf13a9735ceb61ae32d3b007e5d` `results/paper/e1/baselines_nobox.csv`
- `5bcdc714339f7bd8e6d7678a2d7b0be22baacf601dc2a0050e6ec3375d2b0cad` `results/paper/e1/pooled_clean_dict_grid_attacker.csv`
- `22c25e04d79a2afb2b7950638bf074c716f5fa077c845a4ce6d9f6be4418ba9c` `research/e1/cases/posterior/phase_cases.csv.gz`
- `39f3a596ab8fe734664e8ee497e545db6b2076a19a3e467a206279c02516b998` `research/e1/cases/posterior/phase_cases_digits.csv.gz`
- `53ed035651579a97ebc31905e56e333ff5abd93ab844684dab6791c55e8da6bf` `research/e1/cases/posterior/a3_cases.csv.gz`
- `f67d6a2031b2d2dbb0a33e8b405e7184299a8dd4ce2f4b2726c76af0a06786a5` `research/e1/cases/followup/e1_a4_cases.csv.gz`
- `ecacaad8d2e5df0f7d470ff2b62042ba9dfd58d5dddaa3343ca484fb70ff1204` `research/e1/csv/foia_boxes.csv`
- `e97786171127088486c97838072b28c915dbecb01703e336c921b64ab203b190` `research/e1/csv/foia_geometry_summary.csv`
- `7f670003c170639b8ed3ad96bd1c5691f9830708c0e810ac0c3ad5e51d15cf75` `research/e1/review4/pooled.csv`
- `e1d7004ecfa81a891ebf9a08ad1c0160286d7dd0dd8d7fa5afed0f75b2e32e5c` `research/e1/review4/a3_start/results_summary.csv`
- `1f61c9bcc7aadd02ea99dbf06f9b82d1117052c3ef729d0c562260ca488ef528` `research/e1/review4/a3_start/results_cases.csv.gz`

`MANIFEST.sha256` lists every other tracked file, including the 25 case archives under `research/e1/cases/`. Census CSV SHA-256 `6b4933178060b4e5ac8dd9a611ec15472d35eab98fe9027474bc5ccc5b7a8708`. Font SHA-256 values are in `research/e1/inputs/fonts.json`. Gutenberg text hashes are in `scripts/fetch_data.py`.

### What cannot be regenerated

- Language-model ranks. The DejaVu box ranks are archived; the model weights, the Liberation follow-up, and both sentence-alone files (`a4_reproduction.csv`, `a4_padding_cases.csv`) are not. Multi-threaded CPU ranks already disagreed by up to 0.5 points.
- The 179/400 sentence-alone count. It is not a column in `e1_a4_cases.csv.gz`.
- Own-height cells. `w1_pooled.csv` is absent, and no script keeps each box's own height.
- Attacker-knowledge summaries (`test4_fontcluster.csv`, `s4_priors.csv`) and `d2jit_pooled.csv`. The per-target `test4_cases.csv.gz` is archived.
- FOIA page images, mock-form PDFs, and the six font binaries.
- The original full per-target directory. Four main-sweep cells and their target lists are under `research/e1/cases/main-subset/`.
- The v6.1 LaTeX source. It was not in the tree the audit searched.

## Tests

```sh
.venv/bin/python -m pytest -q
```

## Website

The TileSeal page is `index.html`. Rebuild it after a change to `src/`, then open it:

```sh
node scripts/build.mjs
python3 -m http.server 4195 --bind 127.0.0.1
```

Open http://127.0.0.1:4195/. Images and keys stay in the browser.

## Use TileSeal

```sh
.venv/bin/python -m tileseal seal in.png --key key.pem --no-visual -o out.GRD
.venv/bin/python -m tileseal redact out.GRD --rect 8,8,20,12 --granularity 64 -o redacted.GRD
.venv/bin/python -m tileseal verify redacted.GRD
```

Create the key when you need it. Do not commit it.

## Citation

Neer Vasa. What the Black Box Reveals: Measuring Redaction-Geometry Leakage and the Tile-Snapping Trade-off in Images. DOI: PLACEHOLDER.

The same fields are in `CITATION.cff`.
