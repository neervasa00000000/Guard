# B2: neighbouring words covered and local OCR accuracy

FUNSD only: no matching born-digital source PDFs for the 500 DocLayNet evaluation pages were available locally.

All 199 FUNSD forms were read. Every qualifying surname word is a separate redaction; forms with none are counted in skipped_forms.csv. Ground truth uses the supplied word-level annotations across all entity labels. No OCR-derived word boxes are treated as ground truth.

Policies and target selection execute the existing Table A9 functions. The first-1000 field is the original DejaVuSans/word-height surrogate and is only evaluated for in-list surnames; it is not an annotated native blank field. The FUNSD entity-level validation does not compute such a field, so its entity-level area summaries are not comparable to this word-target cohort. Paired Table A9 boxes and nominal ratios are checked directly; actual painting clips to image edges and any resulting ratio differences are reported.

One-to-one OCR matching uses descending IoU >= 0.5 with deterministic geometric ties, then exact NFKC text comparison, with a separate Unicode-casefold comparison. OCR runs locally with --oem 1 --psm 3, English, one OpenMP thread per process. All image transport uses temporary uncompressed TIFF with unchanged pixels and no invented DPI.

Covered-word denominators exclude the target. Visible-word accuracy excludes words >=50% covered. Its unredacted comparator uses exactly the same visible-word subset for each mask; full-page baseline accuracy is also saved. Per-page CSV rows represent individual target-policy redactions, with page-policy aggregates in a separate file. Pooled proportions count word observations across these separate redactions; complete pages are resampled 10,000 times, seed 20261121.

| Policy | Pages | Redactions | Median area ratio | >=50% words covered % [95% CI] | Any-overlap words % | OCR accuracy % [95% CI] | Case-insensitive % | OCR drop points [95% CI] |
|---|---:|---:|---:|---|---:|---|---:|---|
| exact | 192 | 2649 | 1.000 | 0.000 [0.000, 0.000] | 0.243 | 37.243 [34.530, 39.975] | 37.865 | 0.418 [0.048, 0.818] |
| grid-16 | 192 | 2649 | 2.731 | 0.238 [0.209, 0.268] | 1.340 | 36.430 [33.868, 39.103] | 37.009 | 1.237 [0.545, 2.014] |
| grid-64 | 192 | 2649 | 12.356 | 2.384 [2.231, 2.549] | 3.840 | 35.988 [33.411, 38.691] | 36.539 | 1.589 [0.710, 2.558] |
| start-aligned-128 | 192 | 2649 | 4.865 | 1.170 [1.012, 1.350] | 2.077 | 36.247 [33.700, 38.926] | 36.831 | 1.317 [0.461, 2.271] |
| field-1000 | 151 | 473 | 2.827 | 0.644 [0.490, 0.838] | 1.319 | 34.081 [31.571, 36.902] | 34.692 | 0.752 [-0.059, 1.693] |

Sanity: exact covers 0.000000 neighbouring words per redaction versus 4.246508 for the 64px grid.
Paired archive checks: 3198; box mismatches 0; nominal area-ratio mismatches 0; actual/nominal differences from clipping 6. See area_reference_checks.csv.

Limitations: the surname-list selector also admits ordinary words sharing surname spellings; no likely-name filter is added. FUNSD word transcriptions and boxes may be imperfect. Multiword annotation entries remain one annotated unit. Font/renderer properties of the scans are unknown. Field rows use a smaller bounded-list cohort. Loss of words and OCR accuracy on the remaining words are separate quantities. No original text, page images, PDFs or credentials are distributed.

## Reproduction check

Two runs used the same seed/settings; the second bypassed cached OCR for all 10971 unique images. Summary CSVs are byte-identical (SHA-256 d4313aef2d313d51e126db947513459f91e845b934956e8c4f562be0b8c8ec6b); per-target CSV byte identity: True. OCR output differences: 0. No numeric results were patched.

From the repository root, after installing the recorded local Tesseract version and Python requirements and providing the independently obtained FUNSD/Census inputs:

```sh
.venv/bin/python -B research/area_eval/run_area_eval.py --workers 8
.venv/bin/python -B research/area_eval/run_area_eval.py --workers 8 --force-ocr --out research/area_eval/.repeat
.venv/bin/python -B research/area_eval/validate_area_eval.py
```

Only the unused import of the unreleased DocLayNet downloader is omitted in memory so the archived selector/policy code can run from released files; their function bodies are unchanged. field_geometry.json releases the sufficient numeric first-1000 geometry parameters, verified against the archived receipt and paired boxes; no font files are distributed.

Area-reference checks compare identical test targets with the archived Table A9 boxes. Nominal medians all match. Image-edge clipping differences and their median effects are listed in area_reference_summary.csv; the existing entity-level FUNSD figures use different targets and do not provide a comparable field-box reference.

All 199 forms were inspected: 192 contain 2649 qualifying surname words; 7 forms have none and are skipped. Field-1000 has 473 in-list targets; the other 2176 targets have no field-1000 case. Ground-truth quality exclusions: 890 blank word records excluded; 62 multiword annotation entries retained as single annotated units; 3 rectangles clipped to image boundaries. These counts cover all 199 forms.

The unchanged archived field surrogate fails to fully cover the annotated target rectangle in 4 of 473 cases (coverage 85.56%–97.47%). These cases remain in the results and are listed by hashes in field_target_coverage.csv. Rectangle coverage alone does not establish whether target ink is exposed. All other policies fully cover each target rectangle.

Additional utility measures (confidence limits in summary.csv):

| Policy | Area median | Area p90 | Neighbour words >=50% covered/redaction | Unredacted accuracy on same visible set % |
|---|---:|---:|---:|---:|
| exact | 1.000 | 1.000 | 0.000 | 37.660 |
| grid-16 | 2.731 | 4.046 | 0.423 | 37.667 |
| grid-64 | 12.356 | 26.947 | 4.247 | 37.577 |
| start-aligned-128 | 4.865 | 14.378 | 2.084 | 37.564 |
| field-1000 | 2.827 | 6.936 | 1.144 | 34.833 |
