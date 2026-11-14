# Evidence for the MDPI Computers manuscript

The manuscript is `manuscript/Vasa_MDPI_Computers_v8_5.docx` (What the Black Box Reveals: Geometry Leakage and Over-Redaction in Template-Controlled Image Redaction). `scripts/check_numbers.py` compares `out/tables/values.csv` with `manuscript/expected_numbers.json`, which was transcribed from that file. It does not read an IEEE Access PDF.

The k = 1 row of the jitter condition is one jittered release (0.36 bits). The canonical unjittered start-aligned DejaVu Sans 24 px mask is 0.285 bits. Five jittered releases give 0.64 bits.

| Result | Script | Input | Output | Status |
|---|---|---|---|---|
| Table 3, Figure 2, Figure 3 | `scripts/regenerate_tables.py`, `scripts/make_figures.py` | `research/e1/review4/pooled.csv` | `out/tables/table3.csv`, `out/figures/figure2.pdf`, `out/figures/figure3.pdf` | REPRODUCED |
| Table 4 | `scripts/regenerate_tables.py` | `research/e1/data/foia_geometry_summary.csv` | `out/tables/table4.csv` | REPRODUCED |
| Table A1 | `scripts/regenerate_tables.py` | cell matrix in `research/e1/e1_run.py` | `out/tables/table_a1.md` | REPRODUCED |
| Table A2, Figure 1 | `scripts/regenerate_tables.py`, `scripts/make_figures.py` | `research/e1/data/pooled_clean_dict_grid_attacker.csv`, `pooled.csv` | `out/tables/table_a2.csv`, `out/figures/figure1.pdf` | REPRODUCED |
| Table A3, Figure 6 | `scripts/regenerate_tables.py`, `scripts/make_figures.py` | `research/e1/data/forms/start_policy_summary.csv`, `start_vs_grid16_paired.csv` | `out/tables/table_a3.csv`, `out/figures/figure6.pdf` | REPRODUCED |
| Table A4, DejaVu exact and grids | `scripts/regenerate_tables.py` | `research/e1/cases/followup/e1_a4_cases.csv.gz` | `out/tables/table_a4.csv` | REPRODUCED |
| Table A4 Liberation Serif, 179/400, padding gain | — | `a4_reproduction.csv` is not in the repository | — | EXPLORATORY |
| Table A5 paired Holm count and pooled delta | `scripts/regenerate_tables.py` | `research/e1/data/paired_tests.csv` | `out/tables/table_a5.csv` | REPRODUCED |
| Table A5 number before the Holm arrow | — | not a column in `paired_tests.csv` | — | EXPLORATORY |
| Table A6 | `scripts/regenerate_tables.py` | `research/e1/data/per_font.csv`, `pooled.csv` | `out/tables/table_a6.csv` | REPRODUCED |
| Figure 4a grid copies | `scripts/regenerate_tables.py`, `scripts/make_figures.py` | `research/e1/cases/posterior/a3_cases.csv.gz` | `out/tables/figure4a.csv`, `out/figures/figure4.pdf` | REPRODUCED |
| Figure 4b jitter, unjittered mask, font change | `scripts/regenerate_tables.py`, `scripts/make_figures.py` | `research/e1/data/results_summary.csv`, `per_font.csv` | `out/figures/figure4.pdf` | REPRODUCED |
| Figure 4b edge-aligned 0.38 to 1.30 bits | — | no such row in `results_summary.csv` | — | EXPLORATORY |
| Figure 5 known, font-unknown, uniform prior | `scripts/regenerate_tables.py`, `scripts/make_figures.py` | `research/e1/cases/followup/test4_cases.csv.gz` | `out/tables/test4_fontcluster.csv`, `out/figures/figure5.pdf` | REPRODUCED |
| Figure 5 word-frequency prior | — | `s4_priors.csv` is not in the repository | — | EXPLORATORY |
| Figure 5 recalibrated 31/100 | — | not a row in the form summary | — | EXPLORATORY |
| `d2jit_pooled.csv` | `scripts/regenerate_tables.py` | `research/e1/cases/followup/d2jit_cases.csv.gz` | `out/tables/d2jit_pooled.csv` | REPRODUCED |
| `test4_fontcluster.csv` | `scripts/regenerate_tables.py` | `research/e1/cases/followup/test4_cases.csv.gz` | `out/tables/test4_fontcluster.csv` | REPRODUCED |
| `s2_rerender.csv` | — | raw file absent; 188 of 2,000 is in `results_summary.csv` | — | EXPLORATORY |
| Own-height cells (`w1_pooled.csv`) | — | not implemented; the manuscript says the variant is not reported | — | EXPLORATORY |
| Form pages | — | PDFs and scans are not in the repository | — | EXPLORATORY |
| v1.2 historical 128-px control | `scripts/run_v12.py` | Census 50,000, verified fonts and retained Noto Sans layout geometry | `research/e1/data/v1_2/paper_control.csv` | REPRODUCED |
| v1.2 surname policy sweep and box equality | `scripts/run_v12.py` | First 1,000 Census surnames and paired target draws | `research/e1/data/v1_2/summary.csv`, `box_check.csv`, `field_widths.csv`, `research/e1/cases/v1_2/` | NEW |
| v1.2 result table and padding-width plot | `scripts/regenerate_tables.py` | `research/e1/data/v1_2/summary.csv` | `out/tables/v1_2.md`, `out/figures/bits_vs_C.pdf` | NEW |
