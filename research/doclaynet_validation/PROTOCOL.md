# Protocol: DocLayNet real-document validation

Frozen before evaluation scores are read. Thresholds below are not retuned to improve agreement with the manuscript. Implementation bugs found by the pilot are recorded in `results/pilot/CORRECTIONS.md` and the pilot is repeated. This experiment does not edit the manuscript, the archived surname results, or files under `dataset/`.

## Question

Do the geometry-leakage and over-redaction findings from the synthetic surname study still appear when the same policies and the same attacker are applied on real DocLayNet page layouts?

Two tracks stay separate:

- `controlled_insertion`. A census surname drawn from the existing 1,000-name prior is painted into a real page. The string, font, size, pen, and baseline are known because this protocol inserted them. They are never described as text that was printed on the source page.
- `verified_original`. A string already on the page is used only after OCR proposes it and a font-bank render matches the ink. Unverified OCR is not ground truth. Policies that need a field template or a closed candidate list are not applied on this track unless that information is actually present. It is not present for an arbitrary DocLayNet line, so width-only, start-aligned, and field-wide masks are not scored there.

## Sample

- Source: `dataset/DocLayNet_core` (COCO `train.json`, `val.json`, `test.json`, and `PNG/`).
- Seed: `20261118`.
- Evaluation target: 500 pages, quotas 84, 84, 83, 83, 83, 83 for financial reports, manuals, laws and regulations, scientific articles, patents, government tenders, in that order for the two extra pages.
- Calibration: 20 pages in each category, from documents that are not in the evaluation set.
- Document key: `doc_name`. At most 2 pages from one document.
- Role: SHA-256 of `doclaynet-validation-v1:{doc_name}` (full run) or `doclaynet-validation-pilot-v1:{doc_name}` (pilot). The first byte below 51 assigns calibration.
- A page with no paintable text line, a missing PNG, or a PNG size other than the COCO size is excluded and the walk continues.
- Pilot: 2 evaluation pages and 1 calibration page in each category. Pilot rows are not copied into the full-run results.

## Insertion

- Font file: matplotlib `DejaVuSans.ttf`. Its SHA-256 is recorded. It is not assumed to be the font binary used for the archived v1.2 tables.
- Sizes: 16 px is primary. 12 px is a sensitivity. Both use the same sampled surname when both fit on the page.
- Prior: Census counts in `research/e1/data/surnames_head1000.csv`, normalized.
- Anchor: 8 px inside the left of the first detected text band of an eligible layout region (Caption, List-item, Section-header, Text, Title), shifted left only to keep the ink on the page.
- Eligible region: width 140–980 px, height 10–220 px, inside the page, picture overlap at most 30% of the region.
- Text band: first run of rows whose dark fraction exceeds 0.012, extended while the fraction exceeds 0.008, capped at 36 px. Dark means luminance below 150.
- The surname is drawn with Pillow, anchor `ls`, after filling the ink rectangle expanded by 2 px with the local light background. The original PNG is not modified.

## Policies

Applied through `research/realworld_validation/src/guard_rw.py` (`exact_box`, `snap_out`, `candidate_boxes`, `shared_frame`).

| Policy | Redactor must know | Scored on insertion | Scored on verified original text |
| --- | --- | --- | --- |
| Exact box | The glyph ink | Yes | Yes |
| Square grid, 16 px | The glyph ink and the page grid | Yes | Yes |
| Square grid, 64 px | The glyph ink and the page grid | Yes | Yes |
| Width-only grid, 64 px | Shared list start `x_L` and the shared line | Yes, because the insertion defines them | No |
| Start-aligned padding, 128 px | The same template as the width-only grid | Yes, because the insertion defines them | No |
| Fixed field-wide box | The bounded 1,000-name list, `x_L`, and the shared line | Yes, because both exist by construction | No |

Boxes are clipped to the page after the policy is applied. A policy is not treated as equally deployable with the others when it needs template or list knowledge the page does not provide.

## Attacker

Candidate list: the same 1,000 surnames and Census prior. Conditions:

- `matched_template_known`. Pillow raster of the true font and size. Pen and baseline known. This is the comparison with the synthetic matched-renderer attack.
- `renderer_mismatch`. Same font file and nominal size, but the attacker’s ink boxes come from a PyMuPDF raster, not Pillow. Pen and baseline known.
- `font_mismatch`. Pillow raster of Arial at the true size. Pen and baseline known.
- `font_unknown`. A name is feasible if any font in {DejaVu Sans, DejaVu Serif, Arial, Times New Roman, Georgia, Courier New} at any size in {12, 14, 16, 18, 20} produces the observed box at the true pen and baseline.
- `start_unknown`. Exact: feasible when the padded width and height match. Square grids: feasible when some integer placement snaps and clips to the observed rectangle. Width-only, start-aligned, and field policies are not scored, because those masks are defined by a start the attacker is not given.

Hits use `guard_rw.possibilistic` and `expected_hit`, including ties. An empty feasible set keeps the prior hit. A non-empty set that excludes the truth has hit 0. Entropy reduction is `H(prior) - H(posterior)`. Pointwise leakage is `-log2` of the feasible prior mass, and only when the truth is feasible. Headline leakage for a mismatch condition is that pointwise quantity when the truth remains feasible, reported together with the rate at which the truth is excluded.

## Utility

On the original pixels, before insertion:

- Neighbor ink fraction: dark pixels inside the mask and outside the cleared insertion rectangle, divided by dark pixels in the scope outside that rectangle. Scope is the host region expanded by 12 px, union every other readable layout region the mask meets.
- Unrelated-region rate: the mask meets a readable layout region other than the host. Readable categories are every COCO category except Picture.
- OCR word and character counts, when Vision returns lines: whitespace tokens, boxes split in proportion to character count. These are estimates. Ink and layout-region counts do not depend on OCR.

Area ratio is mask area divided by that target’s exact-box area. Over-area is the difference. Summaries report the median and the 90th percentile.

## Original-text verification

A Vision line is a candidate only if confidence is at least 0.80, the normalized text is one Latin token of 4–24 letters, the box is 8–48 px tall, and width/height is at least 2.5. It is verified only if some font and size in the bank, aligned to the dark ink, has recall at least 0.75, precision at least 0.45, and width error at most 3 px. Privacy is scored only when the verified token is in the 1,000-name list and one font is the unique best match within 0.02 recall. Otherwise the reason is recorded and no attack accuracy is filled in.

Calibration negative control, frozen: if more than 2% of wrong surname proposals are accepted, verified-original privacy rows are not used. If fewer than 95% of the known insertions are accepted on their own crops, the verifier is treated as broken and the pilot fails until the implementation is corrected.

## Uncertainty

Evaluation documents are resampled with replacement, 10,000 times. Targets from one `doc_name` stay together. The bootstrap stream for a reported slice is keyed by the slice name, seed `20261118`. Means use every target in the drawn documents. Medians and 90th percentiles are bootstrapped for the primary matched condition. Category slices are reported when a category has at least 15 evaluation documents; smaller slices are marked as too small for an interval. Multiple targets on one document are not treated as independent samples. Calibration is not pooled into the evaluation estimates.

## Pilot failures

The pilot stops the full run unless every item below holds:

- Every matched mask covers every painted surname pixel.
- Every matched exact observation contains the true surname.
- Every matched field box is identical across the 1,000 names, and the entropy reduction is 0.
- Square-grid edges lie on the grid or on the page boundary.
- Snapping matches `guard_rw.snap_out`.
- No row is labeled both as verified original text and as a controlled insertion.
- Calibration and evaluation share no `doc_name`.
- A second catalog build has the same boxes.
- The Vision box for a synthetic surname overlaps the pixels that were drawn.
