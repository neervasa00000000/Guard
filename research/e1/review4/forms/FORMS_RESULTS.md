# Start-aligned padding on mock forms

The full published-policy sanity check is blocked by missing Pillow scan-like controls. Start-aligned padding awaits that check. The kit contains the LibreOffice generator, measurements, and per-form scores. It also contains the Pillow layout replay in `new_tests_quick3/scripts/neighbour_coverage.py`, the Pillow surname A2 audit, and aggregate Pillow clean controls. The local Test 3 copy supplies the original `test3_docs.json`.

| Renderer and condition | Published coverage | Sanity check |
| --- | --- | --- |
| Pillow, clean, 16 px | Test 3 includes case number, surname, date of birth, e-mail and the surname repeated in Notes. | The available surname controls match. The kit lacks `mock_docs.py` and `test3_cases.csv`; the A2 edge-padding reference is absent. |
| Pillow, scan-like | The supplied Test 3 method and results describe clean Pillow forms. | Blocked pending the original Pillow scan-like generator, seed and hit-count references. |
| LibreOffice, clean and scan-like, 16 and 24 px | Renderer 2 scores the surname field with matched and mismatched A1 renderers. | The original generator reproduced every archived form and calibration record. All 400 archived form observations and dictionary table metadata matched. Nine calibration edges differed by one pixel. The matched and mismatched A1 hit counts matched in every published policy cell. |
| LibreOffice, fields other than surname | The generator lays out these fields; the published renderer-2 scorer and calibration target surnames. | Blocked pending published field-level controls and matching candidate geometry tables. |

The Pillow template specifies the value column at margin + 200 px and places the repeated surname after a visible text prefix with a known font. LibreOffice specifies the value column with a tab stop and exposes the text origin through the authored PDF. The margin plus tab stop matched the rounded surname start in 100 of 100 forms at each of 16 and 24 px. [Layout check](libreoffice_layout_start.csv) The scan experiment supplies the mapped origin using the known simulation transform. Recovery from a standalone scan was not tested in the archived protocol.

The available Pillow clean surname checks reproduced A1 counts of 52, 12, 8 and 10 and A2 counts of 51, 10 and 7, in exact, 16 px, 64 px and padding order where references exist. [Pillow sanity CSV](pillow_surname_sanity.csv)

LibreOffice matched (`b_lo_table`) and mismatched (`a_paper_renderer`) hit-count deltas were zero at both sizes in both conditions. Six auxiliary uniform-prior cells differed in unrounded expected hits. The largest difference was −0.020666 hits per 100, from 12.939693 to 12.919027 for clean 16 px exact boxes. These both round to 12.9 at the precision in the kit report. The replay checker exited on its stricter unrounded all-attacker comparison. The nine one-pixel calibration differences are listed separately from the scoring differences. [Hit-count comparison](libreoffice_hit_check.csv) · [Geometry differences](libreoffice_geometry_diff.csv)

## Reproduction

```sh
docker build -t guard-e1-review4-forms research/e1/review4/forms
sh research/e1/review4/forms/run_replay.sh \
  /private/tmp/tileseal-review4.EKJJXk "$PWD/Rerun/e1_fonts" \
  "$HOME/tileseal-t3-lm/csv/test3_docs.json" \
  > research/e1/review4/forms/replay.log 2>&1
python3 research/e1/review4/forms/check_layout.py \
  research/e1/review4/forms/replayed_forms_obs.csv \
  research/e1/review4/forms/libreoffice_layout_start.csv
```

The container reuses the review4 Python runtime. The forms Dockerfile takes LibreOffice and Poppler from Debian Trixie. The run recorded LibreOffice 25.2.3.2, Poppler 25.03.0, Python 3.12.16, Pillow 12.3.0, NumPy 2.5.4, pandas 3.1.1, PyMuPDF 2.1, RAQM 0.10.5, HarfBuzz 14.2.1, FriBidi 1.0.16 and FreeType 2.14.3. The replay log records the full commands and font hashes. [Replay log](replay.log)

The Pillow form seed is 20261109. The LibreOffice kit records 20261111 for form content and margins, 20261112 for calibration documents, `[20261113, doc, size]` for scan simulation on forms, `[20261114, font_index, size, doc_no]` for scan simulation on calibration documents, and `[20261115, font_index, size, is_scan]` for paper-renderer calibration. The original summary and paired bootstrap seeds are 20261116 and 20261117.
