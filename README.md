# What the Black Box Reveals

This repository is the artifact for Neer Vasa, *What the Black Box Reveals: Geometry Leakage and Over-Redaction in Template-Controlled Image Redaction* (MDPI *Computers*). The manuscript file is `manuscript/Vasa_MDPI_Computers_v8_5.docx`.

TileSeal, the seal and padding code used by the study, is `tileseal/` together with `grd.py` and `grd_geometry.py`.

## Reproduce

One command, from a clean checkout, after the pinned environment exists:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
. .venv/bin/activate
./reproduce.sh
```

`./reproduce.sh` runs `make all`: check the 25 case archives, rebuild the clean A2 summary from those archives, write Tables 3, 4 and A1–A7, draw Figures 1–6, then compare every locked number with the manuscript. It exits non-zero if any locked number disagrees. Items with no archive are printed as `EXPLORATORY` and do not by themselves fail the run.

There is no download and no model call on this path.

On the machine that prepared version 1.1 (Apple M-series, Python 3.13.2), `./reproduce.sh` finished in 12 seconds after the packages were installed. Installing the pinned packages takes longer than the rebuild. The command is I/O bound on the gzipped case archives. It does not need a GPU.

## What each result uses

| Result | Script | Output |
|---|---|---|
| Tables 3, 4, A1–A7 | `scripts/regenerate_tables.py` | `out/tables/table3.csv`, `table4.csv`, `table_a1.md`, `table_a2.csv`, `table_a3.csv`, `table_a4.csv`, `table_a5.csv`, `table_a6.csv`, `table_a7.md` |
| Figures 1–6 | `scripts/make_figures.py` | `out/figures/figure1.pdf` through `figure6.pdf` (and `.png`) |
| Manuscript check | `scripts/check_numbers.py` | compares `out/tables/values.csv` with `manuscript/expected_numbers.json` |

The input map, including exploratory rows, is [EVIDENCE.md](EVIDENCE.md).

## Environment

`requirements.txt` and `environment.yml` pin Python 3.13.2 and the packages used to rebuild the tables: numpy 2.5.4, pandas 3.1.1, matplotlib 3.10.7, Pillow 13.0.0, wordfreq 3.1.1, pytest 8.4.2. wordfreq is used only by `research/e1/data/build_wordlist.py`, which `make all` does not call. A full re-render, which this command does not do, needs Pillow 12.3.0 with RAQM and the six fonts named in `research/e1/data/fonts.json`.

## Tests

```sh
.venv/bin/python -m pytest -q tests/test_smoke_archives.py tests/test_stored_a1_cell.py
```

The smoke test reads one archive header and the 1,000-name census head. It does not score the 3.4 million case rows.

## Citation

Neer Vasa. What the Black Box Reveals: Geometry Leakage and Over-Redaction in Template-Controlled Image Redaction. *Computers*. Version 1.1. DOI: PLACEHOLDER.
