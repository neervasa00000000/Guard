# Evidence for the submitted manuscript (Journal of Cybersecurity and Privacy)

Manuscript: `guard_v9_37.docx` (How Much Does a Redaction Box Reveal? Geometry Leakage and Over-Redaction Under Matched-Renderer Attacks). Archive: tag v1.5-artifact (adds check scripts and this number map to v1.4-artifact, commit 162567c2cfa0b6eaf35339b35f106aa9bca606bb; data unchanged). Generated 2026-11-23 for this manuscript. This file and `expected_numbers.json` were added in v1.5-artifact; the top-level `manuscript/expected_numbers.json` and `EVIDENCE.md` describe an earlier draft.

`expected_numbers.json` lists 338 numbers: table cells of the manuscript recomputed from the archive and compared within half a unit of the last printed digit, plus text claims traced by `verify_numbers.py`. Failures: 0.

## Checked numbers by location

| Location in the manuscript | Numbers | Pass |
|---|---|---|
| Table 3 | 24 | 24 |
| Table 4 | 11 | 11 |
| Table A13 | 20 | 20 |
| Table A2 | 12 | 12 |
| Table A4 | 63 | 63 |
| Table A6 | 50 | 50 |
| Table A9 | 12 | 12 |
| text (see claim) | 146 | 146 |

## Claims, status, inputs and scripts (Table A10 of the manuscript)

| Claim (where) | Status | Archived input | Script |
|---|---|---|---|
| Exact and grid leakage (5.1, 5.2, B.1; Figure 2; Tables A2, A6; scan-like row of Table 4) | Reproduced | review4/pooled.csv; data/per_font.csv | regenerate_tables.py |
| Paired tests, Holm counts (Table A3) | Reproduced | data/paired_tests.csv | regenerate_tables.py |
| Knowledge-matched sweep, Observation 1 check, field box (6.1; Figure 3; Table A4) | Re-run; Noto Sans re-rendered with the pinned binary (v1.4) | data/v1_2/summary.csv, box_check.csv, field_widths.csv; Noto Sans: results/v1_4_archive/noto_rerender/ | scripts/run_v12.py; scripts/run_archive_noto.py |
| Per-person leakage, incl. the 18.60-bit singleton (6.2; Figure 4; Table 3) | Re-scored | data/v1_3/tail_summary.csv, tail_per_class.csv | scripts/run_tail.py |
| Template errors (B.2) | Re-scored | data/v1_4/summary.csv | scripts/run_perturb.py |
| Repeated releases: A3 grid copies, changed releases, 188 of 2,000 class changes (5.2, B.3; Figure A1) | Re-scored; reproduced; re-run (v1.4) | cases/posterior/a3_cases.csv.gz; data/results_summary.csv; results/v1_4_archive/rerender_class_changes/ | a3_exact.py; regenerate_tables.py; scripts/run_archive_rerender.py |
| Attacker knowledge, synthetic and form rows of Table 4 (7.3); A4 (B.5; Table A7) | Reproduced | cases/followup/test4_cases.csv.gz, e1_a4_cases.csv.gz; data/forms/ | regenerate_tables.py |
| Mock forms; renderer-mismatch attackers (7.3, B.4; Table A5) | Reproduced; mismatch hits replayed‡; fresh rebuild differs (v1.4; B.4) | data/forms/start_policy_summary.csv, start_vs_grid16_paired.csv, libreoffice_hit_check.csv; results/v1_4_archive/mock_forms_reconstruction/ | regenerate_tables.py; – (replayed); scripts/run_lo_reconstruction.py |
| Real-world checks (7.1–7.3, C; Figure 6; PDF-writer and DocLayNet rows of Table 4; 585-field FUNSD check) | Reproduced | research/realworld_validation/results/, doclaynet_validation/results/summary.csv, funsd_validation/out/summary.csv | run_all.sh, run_experiment.py, run_funsd_validation.py |
| Original names on real pages; font consistency (7.3, C; Table A9) | Re-run | research/realworld_e1_eval/results/v2/, results/font_consistency/ (_notext files) | research/realworld_e1_eval/ |
| Real box geometry (B.4; Table A8) | Reproduced | data/foia_geometry_summary.csv | regenerate_tables.py |
| Anchor margins (6.2; Figure 5) | Re-scored (v1.4) | data/v1_5_anchor_margin/summary.csv | scripts/run_anchor_margin.py |
| Font-matched attackers on original names (7.3, C; Table A13) | Re-run (v1.4) | research/realworld_e1_eval/results/v4_fontmatched/ | research/realworld_e1_eval/run_v4_fontmatched.py |
| Text lost around the box, FUNSD (7.4; Table A14) | Re-run (v1.4) | research/area_eval/results/summary.csv | research/area_eval/run_area_eval.py |
| E-mail and digit sweep (B.1; Table A12) | Re-run (v1.4) | data/v1_6_email_digits/table_pooled.csv | scripts/run_email_digits.py |
| Font-build sensitivity (8.2) | Re-run (v1.4); earlier check unverified‡ | results/v1_4_archive/font_builds/ | scripts/run_archive_font_builds.py |
| TileSeal snapping model, 392 redactions (4, B.4) | Re-run (v1.4) | results/v1_4_archive/tileseal/ | e1_validate_guard.py; scripts/run_archive_tileseal.py |
| Truth-kept split (7.3); margin, overflow (B.2, 8.2) | Added in v1.5-artifact; m = 1 matches archive | v4_fontmatched/per_token.csv.gz; Census CSV | truth_kept.py; margin_sensitivity.py; field_overflow.py |

## Checks added in v1.5-artifact (scripts in research/e1/scripts/)

| Check | Script | Inputs | Validation |
|---|---|---|---|
| Truth-kept split of the exact-box score (Section 7.3; Table A13 note) | truth_kept.py | research/realworld_e1_eval/results/v4_fontmatched/per_token.csv.gz | reproduces the archived exact-box means (0.416, 0.654, 0.415, 0.020) |
| Box-margin sensitivity, 0/1/2 px, C = 128/192/256 (Appendix B.2) | margin_sensitivity.py | Census CSV (SHA-256 6b49…8708), Table A11 fonts (hashes match), research/e1 e1lib/policies | m = 1 reproduces data/v1_3/tail_summary.csv in all 54 cells |
| Field box sized from the 1,000-name list vs the 50,000-name list (Section 8.2) | field_overflow.py | as above | all 18 field widths and anchors match data/v1_2/field_widths.csv |
| Attainability of reported percentages (GRIM-style), run during preparation | not supplied | printed values and n | 58 checked; only the 585-field rates are non-whole counts (tie-expected, as stated) |

Re-renders for these checks used Python 3.13 and Pillow 13.0.0 with Raqm (the study used Pillow 12.3.0); their outputs were accepted only after matching the archived values above.

