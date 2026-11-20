# Baseline audit

This file records what already existed before the PDF-pipeline run. None of it is new evidence.

## Manuscript and release

`guard_v9_14(2).pdf` is not in the checkout. Local manuscripts include `manuscript/guard_v9_11.pdf`, `manuscript/guard_v9_11_corrected_working.docx`, and `manuscript/Vasa_MDPI_Computers_v9_4.pdf`. The tag `v1.2-artifact` and commit `05dc3f5cab9bb139cd814cc0d2340599346b36cf` were not re-verified in this run. Archived tables are.

`out/tables/table3.csv` is the synthetic surname table this study compares against and does not recompute:

| Policy | Layout bits | Top-10 | Area | n |
| --- | ---: | ---: | ---: | ---: |
| Exact box | 6.6557 | 50.197% | 1.00 | 36000 |
| Square 16 px | 2.1880 | 14.864% | 2.45 | 36000 |
| Square 64 px | 0.6656 | 8.242% | 10.04 | 36000 |
| Width-only 64 px | 0.6111 | 8.069% | 3.01 | 36000 |
| Start-aligned 128 px | 0.0786 | 6.233% | 3.36 | 36000 |

Those rates use the study fonts, Pillow 12.3 with RAQM, and the 50,000-name list. This checkout has the head-1,000 file only. `research/e1/e1lib.py` records the full-file SHA-256 `6b4933178060b4e5ac8dd9a611ec15472d35eab98fe9027474bc5ccc5b7a8708` and refuses to render without it. The no-box top-10 of 5.932% cited for that 50,000-name prior is a manuscript figure for that list. It is not the no-box rate of the head-1,000 prior, which is more concentrated. The two are not pooled.

## Code that this study reuses

- `research/e1/policies.py`: `ceil_multiple`, `start_aligned_padding`, `square_grid`, `field_box`, `class_attack`. The new integer maps were checked against these functions. The file was not modified.
- `research/e1/data/surnames_head1000.csv`: the only surname list used. Columns `name`, `rank`, `count`.
- `research/e1/data/v1_2/`: archived summaries. Not overwritten.
- `research/funsd_validation/`: a finished scan-form study. Not overwritten and not pooled. Its test top-10 was about 4.67% against a no-box 3.87% under a length model, which is a different estimand.

## What was not available

`research/e1/data/DATA_LICENSE.md` and `foia_boxes.csv` describe 11,351 redaction rectangles from van Heusden, Marx, and Meijer. The page images are not shipped. No identity was recovered from them, and none is claimed here.

Study fonts (DejaVu, Liberation, Noto) are not installed. The fonts used here are macOS Times New Roman, Arial, Courier New, and Georgia. Substituting them for the study fonts would be a different experiment; they are used as this machine's real fonts and labeled as such.

LibreOffice, Poppler, Ghostscript, and a working WeasyPrint were not found. The third pipeline is Pillow, and the reduction is stated in the protocol.

## What is new

Everything under `research/realworld_validation/` except this audit's description of the old files: the catalogs, the 1,200 generated pages, the attacks, the utility counts, the simulated scans, and the repeated-release intersection. Production code, the manuscript, the FUNSD outputs, and the v1.2 archives were not edited.
