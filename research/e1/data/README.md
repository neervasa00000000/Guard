# Synthetic-study data: what is needed

## Routine rebuild inputs

`make all` reads baselines_nobox.csv, foia_geometry_summary.csv,
forms/start_policy_summary.csv, forms/start_vs_grid16_paired.csv,
paired_tests.csv, per_font.csv, pooled_clean_dict_grid_attacker.csv,
pooled_clean_feasible_set.csv, results_summary.csv, surnames_head1000.csv,
and v1_2/summary.csv. CI also reads real_comparison.csv.
The archived case files are in ../cases/ and review aggregates in ../review4/.
The active numerical locks are in ../../../scripts/locked_values.json;
the manuscript number map is in ../../../manuscript/expected_numbers.json.

## Retained rerun inputs and evidence

- v1_2/: knowledge-matched sweep summaries, box/field-width controls,
  configuration and checksums. Its SHA256SUMS also covers all four
  ../cases/v1_2/ archives. The three size archives are read by
  scripts/run_archive_noto.py. These are distinct from the 25 main archives.
- v1_3/: per-person class tails, geometry receipts, controls and checksums.
- v1_4/: template-error sensitivity results and configuration notes.
- results_cases.csv.gz: read by scripts/run_tail.py when checking the
  available candidate-count fields. It is not an unused duplicate.
- forms/libreoffice_hit_check.csv and forms/replayed_forms_obs.csv:
  inputs to the cited LibreOffice reconstruction/validation scripts.
- forms/replayed_calib_obs.csv and libreoffice_geometry_diff.csv:
  retained historical reconstruction evidence.
- foia_boxes.csv: underlying geometry for foia_geometry_summary.csv.
- fonts.json, check_fonts.py, build_wordlist.py, email_spec.md and
  DATA_LICENSE.md: input specifications, preparation and licensing.

## Removed redundant outputs

Unreferenced earlier a3/fig3/size tables and archives, published_a1/a2_controls,
matched_overredaction, padding_minus_64, paired_per_font, and four superseded
form outputs were removed in this cleanup. They remain in the earlier Git
commits. No per-token real-world evidence or Bucket 3b raw data was removed.
The five audit-listed files with live readers or checksum coverage were kept.
