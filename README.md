# How Much Does a Redaction Box Reveal?

Code and archived results for Neer Vasa, *How Much Does a Redaction Box Reveal? Geometry Leakage and Over-Redaction Under Matched-Renderer Attacks* (submitted to the *Journal of Cybersecurity and Privacy*, MDPI).

## What is where

| Path | Contents |
|---|---|
| `EVIDENCE.md` | Each result in the paper, with its status, archived input and script |
| `manuscript/expected_numbers.json` | The paper's numbers (344), each with its source and recomputed value |
| `manuscript/figures/` | Figure data (`figs_data.csv`) and figure scripts |
| `scripts/` | `make all` steps and the re-run scripts named in the paper's Table A10 |
| `scripts/locked_values.json` | Table values that `make all` checks |
| `research/e1/` | Synthetic study: renderer, padding policies, case archives, data, check scripts |
| `research/realworld_validation/`, `doclaynet_validation/`, `funsd_validation/`, `realworld_e1_eval/`, `area_eval/` | Real-page checks and their results |
| `data/anchor_margin/`, `data/email_digits/`, `results/reruns/` | Later re-runs and added sweeps, each with its configuration, seeds and validator |
| `tileseal/`, `grd*.py` | TileSeal, the tile-sealing tool. The study models its tile snapping and checks it against commit f8f2558; its optional `--pad-boxes` flag (centred 128-px width classes) is not one of the policies the paper evaluates |
| `tests/` | Smoke and unit tests |

## Folder map

- `research/e1/`: synthetic study.
- `research/e1/data/knowledge_matched/`: Table A4 sweep.
- `research/e1/data/per_person/`: Table 3 and Figure 4 class tails.
- `research/e1/data/template_errors/`: Appendix B.2 sensitivity checks.
- `research/e1/pooled/`: main-sweep pooled table.
- `research/realworld_validation/`, `research/doclaynet_validation/`, `research/funsd_validation/` and `research/realworld_e1_eval/`: real-page checks.
- `research/area_eval/`: readable-text loss and OCR checks.
- `results/reruns/`: re-runs listed in Table A10.
- `data/anchor_margin/`: Figure 5 sweep.
- `data/email_digits/`: Table A12 sweep.

## Reproduce

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
. .venv/bin/activate
./reproduce.sh
```

`./reproduce.sh` runs `make all`: it checks the archived inputs, rebuilds the tables (`out/tables/`) and figures (`out/figures/`) from the archived CSVs, and compares every locked value. It exits non-zero if any value differs. There is no model call on this path; `scripts/check_figures.py` downloads one figure font.

## Checks for the paper

Each script writes one CSV to the current directory, so run them from `out/` (ignored by git):

```sh
mkdir -p out/checks && cd out/checks
python ../../research/e1/scripts/truth_kept.py
E1_CENSUS=/path/to/Names_2010Census.csv python ../../research/e1/scripts/field_overflow.py
E1_CENSUS=/path/to/Names_2010Census.csv python ../../research/e1/scripts/margin_sensitivity.py
E1_CENSUS=/path/to/Names_2010Census.csv python ../../research/e1/scripts/anchor_offsets.py
python ../../research/e1/scripts/ocr_relative.py
```

- `truth_kept.py` splits the exact-box scores of Table A13 by whether the true name was kept (Section 7.3).
- `field_overflow.py` counts the 50,000 surnames that a field box sized from the 1,000-name list would not cover (Section 8.2). It stops unless all 18 field widths match `research/e1/data/knowledge_matched/field_widths.csv`.
- `margin_sensitivity.py` re-scores start-aligned padding with a 0-, 1- or 2-px box margin (Appendix B.2). It stops unless the 1-px rows match `research/e1/data/per_person/tail_summary.csv`.
- `anchor_offsets.py` moves the padding anchor left by every offset from 0 to C − 1 px and counts singletons (Section 6.2). It stops unless offset 0 matches `research/e1/data/per_person/tail_summary.csv` and offsets 2, 4, 8 and 16 match `data/anchor_margin/summary.csv`.
- `ocr_relative.py` gives each policy's FUNSD OCR drop relative to the exact box on the same redactions (Section 7.4). It stops unless every drop matches `research/area_eval/results/summary.csv`.

`field_overflow.py`, `margin_sensitivity.py` and `anchor_offsets.py` re-render the six study fonts. They need the full 2010 Census surname CSV (`scripts/fetch_data.py` downloads it to `data/census/Names_2010Census.csv`; SHA-256 checked) and the fonts named in `research/e1/data/fonts.json` (SHA-256 checked; set `E1_FONT_DIR` if they are elsewhere).

## Environment

`requirements.txt` and `environment.yml` pin Python 3.13.2 and numpy 2.5.4, pandas 3.1.1, matplotlib 3.10.7, Pillow 13.0.0, wordfreq 3.1.1 and pytest 8.4.2. The study rendered with Pillow 12.3.0 with RAQM; the checks above were re-run with Pillow 13.0.0 and accepted only because they reproduce the archived field widths and tail values exactly.

## Tests

```sh
.venv/bin/python -m pytest -q tests
```

## Citation

Neer Vasa. How Much Does a Redaction Box Reveal? Geometry Leakage and Over-Redaction Under Matched-Renderer Attacks. Submitted to the *Journal of Cybersecurity and Privacy*. Code: https://github.com/neervasa00000000/Guard, tag V1.

## Data layout and rendering environment

`research/e1/data/README.md` distinguishes routine table inputs from retained rerun evidence. Top-level `data/` holds the additional anchor-margin and e-mail/digit sweeps. `requirements.txt` is the table-rebuild environment; `research/e1/requirements-render.txt` records the original rendering dependencies. Earlier working files are in the Git history, not in this release.
