# Task A — v6.1 number audit

The LaTeX source was NOT FOUND. The audit uses the printed PDF `paper_v6_1_ieeeaccess.pdf` (14 pages, SHA-256 `85b8a84f052bbdae861dbabf4eda718fb9d7bc8be8d62ee008f88db204006a6e`). Extracted text is in `paper_text.txt`. Reference-list years and figure-axis ticks were not entered as claims. Headline cells and the known issues were recomputed from the CSVs named below.

Checked rows: 48. MATCH 34. ROUNDING 4. MISMATCH 7. NO SOURCE FOUND 3. One mismatch row is the older feasible-set file set beside Table II; the other six are printed claims.

## Mismatches

| Where | Printed | Recomputed | Source |
|---|---|---|---|
| Sec. IV-E, font unknown | surname exact-box hits 48.6% to 38.0% | 48.600% to 38.167% (prints as 38.2) | `results/e1-followup/test4/csv/test4_fontcluster.csv`, surnames, A1, exact, K to Fu |
| Sec. IV-E, drop | 10.6 points, CI 5.6–15.0 | A1 drop is 10.433 points, CI 5.60–14.97. The 10.6-point drop is the A2 row (10.633), whose starting rate is 47.3%, not 48.6% | `test4_drop_vs_K_fontcluster.csv` |
| Sec. IV-E, 16 px | 14.6% to 9.4% when font and size are unknown | Pooled font-and-size-unknown rate is 8.333%. 9.4% is the lowest single font for font-unknown only (`hit10_min` 0.094 on Fu) | same font-cluster file |
| Sec. IV-E, bits | 2.10 to 0.71 bits over 18 font–size options | A1 exact bits 2.096 to font-and-size-unknown 0.571. 0.71 was NOT FOUND on that row | same file |
| Sec. IV-E, no-box misinformed prior | 0.03% | Word-frequency no-box mean is 0.0167%. Shuffled-census no-box mean is 0.0250%, which prints as 0.03 | `s4_priors.csv`, six-font mean |
| Table V footnote upper end | 44.8 [40.0, 49.7] | 179/400 = 44.75%. Wilson upper is 49.6498, which is 49.6 at one decimal. 49.65 rounded half-up is 49.7 | count from the published protocol-B cell in `a4_reproduction.csv` (44.75%) |

## No source found

- `w1_pooled.csv`, the file named for the box-height rows. Those Table III cells were not recomputed.
- A box-height implementation. No function that keeps the box’s own height was found in the harness or in `research/e1/review4`.
- Per-target over-redaction rows for a fresh median. The geometry cache has bounding boxes, and this machine does not have the study fonts, so the 3.36× median was not rebuilt from pixels.
- The v6.1 `.tex` path.

## (a) The 4.25 and 4.50 point gaps

Table V’s main-run 64 px language-model cells are 49.8% and 50.0%. Those are 199/400 = 49.75% (DejaVu Sans, `a4_summary.csv`) and 200/400 (Liberation Serif, `a4_reproduction.csv` published column).

The sentence in Sec. IV-D was computed against the later padding rerun’s own 64 px cells, which are 198/400 = 49.50% in both fonts. Item-paired bootstrap, 10,000 resamples, seed 20261113, padding minus that 64 px cell:

| Font | Padding hits | Rerun 64 px hits | Gap (points) | 95% CI |
|---|---:|---:|---:|---|
| DejaVu Sans | 181/400 = 45.25% | 198/400 = 49.50% | −4.25 | −6.50 to −2.25 |
| Liberation Serif | 180/400 = 45.00% | 198/400 = 49.50% | −4.50 | −6.75 to −2.50 |

Those are the printed 4.25 and 4.50 point gaps and the printed intervals. Against Table V’s own 199/400 and 200/400 the gaps would be −4.50 and −5.00 points. The rerun file is `v5.7-ieee/new_tests_padding/csv/a4_padding_cases.csv`.

Other Table V language-model counts on the DejaVu main run (`a4_summary.csv`, rank within 10): exact 388/400, 8 px 321/400, 16 px 283/400, 32 px 235/400, 64 px 199/400. Context alone on the published protocol-B cell is 179/400.

## (b) Jitter row missing from Table X

`d2jit_pooled.csv` has no 16 px surname or word rows. The 24 px rows, likelihood column, are the missing Table X line. Bits 0.275 and 0.567 print as the cited 0.28 and 0.57. The attacker is A3.

| Setting | Top-10 k=1 | Top-10 k=5 | Bits k=1 | Bits k=5 | n |
|---|---:|---:|---:|---:|---:|
| Padding, jitter 0–16 px, surnames, 24 px, A3 | 7.975 | 9.100 | 0.275 | 0.567 | NOT FOUND (file has no n column) |
| Same, A1 | 8.050 | 9.750 | 0.317 | 0.663 | NOT FOUND |
| Words, 24 px, A3 | 24.700 | 25.125 | 0.206 | 0.358 | NOT FOUND |
| E-mails, 16 px, A3 | 1.150 | 1.400 | 0.021 | 0.121 | NOT FOUND |

## (c) Padded height

Main-run 128 px padding (`e1lib.bucket_transform`, `tight_box`, `PAD = 1`):

- Stored geometry: top = −ascent, bottom = descent. Width is the ink width plus 2 px, rounded up to a multiple of 128, then the stored right edge is pulled back by 2 px.
- Published box: `[pen + left − 1, pen + right + 1)` by `[baseline − ascent − 1, baseline + descent + 1)`.
- Height = ascent + descent + 2 px. Width = 128 × ceil((ink width + 2) / 128).
- Area denominator = tight ink box with the same 1 px pad, `(ink width + 2) × (ink height + 2)`.

Table III full-line sweep (`research/e1/review4/geometry.py`): every candidate box is expanded by 1 px. The shared line is `min(−ascent, lowest padded top) − 1` through `max(descent, highest padded bottom) + 1`. Edge alignment keeps each box’s left edge. Start alignment uses one left edge, `min(left) − 1`, for the whole list. The denominator is that candidate’s own padded box.

The pooled median for surnames, edge-aligned and start-aligned 128 px, layout boxes, is 3.358×, which prints as 3.36× (`research/e1/review4/pooled.csv`, `size_px = all`). A fresh median under the list-wide line was NOT FOUND.

## (d) Other confirmations

- Abstract “3.8 million” is 99 × 2,000 × 19 = 3,762,000, the body’s 3.76 million. ROUNDING.
- “1.4 to 2.3 bits” is the Table III box-height surname range 1.41–2.27 as printed. The named source `w1_pooled.csv` was NOT FOUND, so those two cells were not recomputed.
- Wilson footnote: see the mismatch table. The count 179/400 is the published 44.75% cell.
- The five ink-box cases where a width-only grid has fewer bits at no greater area, A1, pooled, all hold: surnames edge 128 (0.967 bits, 3.39×) against width-only 64 (0.621 bits, 3.03×); surnames edge 192 (0.903 bits, 5.08×) against width-only 64 and width-only 128 (0.310 bits, 4.59×); words edge 128 (0.846 bits, 5.79×) against width-only 64 (0.845 bits, 4.21×); words edge 192 (0.795 bits, 8.69×) against width-only 128 (0.445 bits, 7.16×).
- No square or width-only grid has fewer bits at equal or lower median area than start-aligned padding in any pooled cell (five lists, both box models, A1 and A2, `size_px = all`). Count of such grids: 0.
- `s4_priors.csv`, six-font mean, exact box: census prior 48.267% to word-frequency prior 21.211%. Prints as 48.3% to 21.2%. Shuffled census is 5.225% (printed 5.2). True-prior bits average 6.476 (printed 6.48).
- Fig. 2’s 48.6% is the A1 exact cell, 0.486. The 38.0% printed next to it is the mismatch above; the file’s font-unknown rate is 38.167%.

Table II’s A1 columns match the original clean pool. Its A2 columns match the later exact-likelihood pool (`square-*`, `size_px = all`), not the older feasible-set file. Example: surnames, 16 px, A2 is 12.17% and 1.536 bits, which print as 12.2 and 1.54. The older file has 10.7% and 1.33 bits.

Table III’s full-line rows match `pooled.csv` at printed precision. Surnames, layout, edge 128: 0.258 / 0.072 bits and 3.358×. Start 128: 0.079 / 0.079 bits and 3.358×.

[Checked rows](number_audit.csv)
