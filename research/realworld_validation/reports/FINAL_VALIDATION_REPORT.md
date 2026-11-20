# Final validation report

Fictional surnames from the shipped census head-1,000, set in invented pages. These are not confidential documents. The Dutch FOIA page images are not in this checkout and were not scored.

The independent check of the CSV summaries is `results/verification.json`: 0 failures, 19584 attack rows, median glyph-edge error 0.0000 px, maximum 0.000107 px. Every number below is read from `results/`.

## 1. What was implemented

Six policies from the manuscript's geometry: exact box with a 1 px margin, square grids at 16 and 64 px, a width-only grid at 64 px anchored at the shared text start, start-aligned padding at 128 px, and one field box covering the whole shipped list. The integer maps were checked against `research/e1/policies.py`.

Four attackers, all told the pen and the policy. Matched uses the page's engine and font. Unknown renderer takes the union of ReportLab, MuPDF, and Pillow for that font and does not drop the true engine. Unknown font takes the union of Times and Arial and does not look at the page's font. Held-out font uses only Courier and Georgia. A candidate stays in if its predicted rectangle matches the observed rectangle within half a pixel. Ties in the census prior are expected hits. A field box is defined to leave the whole list feasible.

## 2. How many documents were generated

1200 pages. 100 surnames, probability proportional to census count, seed 20261116, reused across 4 layouts and 3 engines. The split is by surname: 384 calibration pages and 816 test pages (68 test surnames). Attack averages use the test pages only.

## 3. How many valid redactions were created

0 sanitizer failures and 0 masks that missed the glyph. All 1200 pages and all six policies on the test pages entered the attack. Text pages, 800 of them, were redacted with PyMuPDF `apply_redactions`, written, and opened again in PyMuPDF and pypdf. The surname was absent from both extractors, from metadata, and from the raw ASCII of the saved file. The redacted clip averaged 3.00 on a 0–255 scale (maximum 9.28). Pillow's 400 pages are image-only PDFs with the surname painted out. An empty text layer on those files is not a PDF text redaction.

## 4. Which PDF engines were used

ReportLab  5.1.0 wrote 400 PDFs. PyMuPDF 2.1 wrote 400 and rasterized both when a raster was needed. Pillow 13.0.0 drew 400 pages. LibreOffice, Poppler, Ghostscript, and WeasyPrint were not installed (`environment.json`). ReportLab and MuPDF are different writers sharing a reader and the same TrueType files. They are not two independent typesetting systems.

Court and hospital pages are Times New Roman. Government and letter pages are Arial. Courier New and Georgia are held out. Body size is 12 pt. Raster scale is 144 dpi.

## 5. Which attackers were evaluated

Matched, unknown renderer, unknown font, and held-out font, on all six policies, plus the no-box prior. The simulated-scan attacker is separate and uses a width tolerance fit on calibration pages only.

## 6. Actual top-1 and top-10

Test pages, surname-cluster 95% intervals, 2000 draws, seed 20261116. No-box top-10 on these pages is 8.8%. That is the mean over the sampled test surnames. The prior-weighted no-box top-10 on all 1,000 names is 12.0%, which is the field-box row because a field box leaves the prior unchanged. The manuscript's 5.932% is the no-box rate of the 50,000-name list and is not this number.

Matched attacker, test pages:

| Policy | Top-1 | Top-10 | Difference from no-box | Holm p |
| --- | ---: | ---: | ---: | ---: |
| Exact | 36.3% | 87.0% [80.6, 93.1] | 78.2 percentage points [70.1, 86.5] | 0.006 |
| Square 16 | 5.9% | 30.8% [20.3, 41.2] | 21.9 percentage points [13.2, 31.7] | 0.006 |
| Square 64 | 2.2% | 13.8% [7.0, 21.1] | 5.0 percentage points [1.7, 9.2] | 0.008 |
| Width 64 | 1.5% | 14.7% [7.4, 23.5] | 5.9 percentage points [1.5, 11.8] | 0.042 |
| Start 128 | 1.5% | 11.8% [5.1, 20.6] | 2.9 percentage points [0.0, 6.6] | 0.188 |
| Field | 1.5% | 8.8% [2.9, 16.2] | 0.0 percentage points | 1.000 |

The p-value adds one to the numerator and the denominator, so a run in which no bootstrap mean crossed zero is reported as about 0.001 before Holm, not as zero. Holm is over the six matched policies.

PDF writers only, matched exact, unweighted over their test pages: top-10 83.8%, top-1 32.7%, 544 pages. Pillow alone is higher: top-10 93.4%.

## 7. Did exact-box leakage transfer to real PDF pipelines

Yes, for these fonts and this list. The measured glyph rectangle and the engine's own catalog rectangle differ by at most 0.000107 px. The matched attacker placed the true name in the feasible set on every test page. ReportLab Times, prior-weighted over all 1,000 names: top-1 35.6%, top-10 88.2%, 21 singleton widths, 119 width classes. MuPDF Times top-10 is 85.9%. Pillow Times top-10 is 98.6%, with 65 singletons. FreeType's integer widths are finer than the PDF writers' widths. Pooling the three engines hides that.

This is not the manuscript's 50.2% top-10. That figure is 36,000 surname trials on a 50,000-name list rendered with the study fonts. The full census file is not in this checkout. A 1,000-name list has fewer collisions, so identification is higher. The transferred fact is the geometry, not the published percentage.

## 8. Did start-aligned padding remain effective

On the test pages the matched start-128 top-10 is 11.8%, 2.9 percentage points above the no-box rate. The paired interval is [0.0, 6.6] and includes zero. Holm p is 0.188. The prior-weighted top-10 on Times is 16.6% against the no-box 12.0%. The point estimate is a small lift. This experiment does not separate it from the prior after the multiplicity correction.

Width-64 does separate: difference 5.9 percentage points, interval [1.5, 11.8], Holm p 0.042. It is a small effect next to the exact box.

These two policies need the shared text start and the candidate list. Exact and square policies do not. The comparison is not a claim that one is better under the same knowledge.

## 9. Did any individual remain uniquely identifiable

Yes, on the shipped list. The sample not containing a singleton would not have been evidence that none exists. The exhaustive table does.

Times, ReportLab, exact box: 21 surnames are alone in their rectangle. Their prior mass is 1.5%. The largest pointwise value is 11.73 bits. One singleton, not necessarily the largest, is PRICE. Arial exact: 30 singletons, prior mass 3.2%, one of them LEE. Classes smaller than 10 hold 27.9% of the Times prior and 34.1% of the Arial prior.

Coarser policies do not wipe this out. Arial square-16 has 1 singleton (MONTGOMERY, 10.03 bits). Arial square-64 still has that singleton: prior mass 0.1%, 10.03 bits. Times square-64 and both start-128 rows have no singletons. Rare-name prior-weighted top-10 under Times exact is 49.3%; under Times start-128 it is 0.0%. Long names (10 or 11 letters; the list has none longer) have Times exact top-10 100.0%.

This is a guarantee for the shipped 1,000 names under these fonts. It is not a guarantee for the unpublished 50,000.

## 10. How much neighboring information was lost

Only the 64 px square covered a neighboring word. Containment of the surname glyph was 1 for every policy and layout.

| Layout | Square-64 median area ratio | Mean neighboring words | Pages with any loss |
| --- | ---: | ---: | ---: |
| court | 7.20 | 2.82 | 66.7% |
| government | 6.87 | 1.31 | 66.7% |
| hospital | 9.64 | 0.33 | 33.3% |
| letter | 3.55 | 0.00 | 0.0% |

Exact boxes have area ratio 1 and cover no neighbor. Start-128 median area ratios are between 1.44 and 1.49, and the neighbor count is zero. Width-64 is the same. The surname is on its own line in these templates, and a mask that only widens that line does not reach the next one. The 64 px square does: on the court page it covers the label above the surname and the first line of the paragraph. The figure is `figures/example_boxes.png`, surname SMITH, which is a census name on an invented page.

So, on these templates, the policy that actually reduces identification without a detectable neighbor cost is the start-aligned or width-only mask, and the neighbor cost shows up when the mask grows vertically. A denser form could change the neighbor counts. This study did not rebuild the templates after seeing that.

## 11. Renderer and font mismatch

Unknown renderer, exact box: top-1 36.3% (interval [26.7, 45.8]), top-10 87.0% (interval [80.4, 92.9]), no-box top-10 8.8%, difference 78.2 percentage points (interval [69.4, 86.3]), entropy reduction 6.23 bits (interval [6.0, 6.4] bits), true name inside the feasible set on 100.0% of pages, median feasible set 13.

That matches the matched exact attack. It matches because a candidate is kept only when some engine reproduces the whole rectangle. MuPDF's exact rectangle never equalled the ReportLab rectangle on the 200 repeated-release pages (mean feasible set 0.0, true name inside on 0.0%). Pillow did not either. The union therefore collapses to the true engine. This is not evidence that a renderer mismatch is harmless. It is evidence that exact rectangle equality is a strict test, and these engines do not meet it for one another's boxes. A fuzzy cross-renderer attacker was not the predeclared primary test.

Unknown font, the union of Times and Arial, exact box: top-1 31.6% (interval [22.8, 40.9]), top-10 79.4% (interval [71.8, 86.3]), no-box top-10 8.8%, difference 70.6 percentage points (interval [61.5, 79.4]), entropy reduction 5.70 bits (interval [5.5, 5.9] bits), true name inside the feasible set on 100.0% of pages, median feasible set 21. The true name stayed feasible on every page. Top-10 fell from 87.0% to 79.4%. Mixing the two fonts used in the study widens the set and does not remove the leak.

Held-out Courier and Georgia, exact box: top-1 2.0% (interval [0.2, 4.2]), top-10 7.4% (interval [4.2, 10.8]), no-box top-10 8.8%, difference -1.5 percentage points (interval [-8.1, 4.4]), entropy reduction 5.17 bits (interval [5.0, 5.3] bits), true name inside the feasible set on 7.4% of pages, median feasible set 10. The true name is inside on only 7.4% of pages. The paired difference from no-box includes zero. The 5.17 bits of entropy reduction are mostly concentration on the wrong surnames. On the pages where the true name is inside, the mean entropy reduction is 5.68 bits (60 pages). Those bits are not the headline.

Held-out square-16 still raises top-10: top-1 3.6% (interval [0.4, 7.7]), top-10 21.8% (interval [14.0, 30.4]), no-box top-10 8.8%, difference 13.0 percentage points (interval [6.9, 19.7]), entropy reduction 2.02 bits (interval [1.9, 2.2] bits), true name inside the feasible set on 85.5% of pages, median feasible set 246. A coarse cell is large enough that the wrong font often still contains the truth, and the prior then ranks inside that cell. Font mismatch is much more protective for an exact box than for a 16 px grid.

## 12. Scanned or scan-like documents

No page was printed or scanned. The arm is a simulated degradation of 40 calibration and 80 test ReportLab pages: rotation ±0.6 degrees, blur radius 0.6, noise standard deviation 6, JPEG quality 40. The tolerance is the calibration 95th percentile, 0.98 px. Calibration median absolute width error was 0.36 px. Test labels were not used to set the tolerance.

On the test pages, top-1 is 25.0%, top-10 is 63.7% with interval [47.5, 80.0], no-box top-10 on this subset is 5.0%, and the true width is inside the tolerance on 85.0% of pages. This mild simulated scan did not remove the width attack. It says nothing about a copier, a phone photograph, or a skew of several degrees.

## 13. Did repeated releases increase leakage

Two hundred ReportLab test pages. Publishing the same exact mask five times leaves top-10 at 85.5% and the median feasible set at 15. A second rendering by MuPDF, with the attacker told that the second page is MuPDF, leaves top-10 at 85.5% and the median feasible set at 15. A 7 px shift of the square-16 grid does not shrink the exact-width class, because names that share an exact width still share the coarser cell. Top-10 stays 85.5%.

A second release in the other in-distribution font does change the set. Median feasible size falls from 15 to 2. Top-1 rises from 33.0% to 76.5%, and top-10 rises from 85.5% to 100.0%. Entropy reduction rises from 6.05 to 8.36 bits. The true name stayed feasible. Adding the start-128 mask on top of that does not move the averages further.

The new information is a second font. A second PDF writer of the same font, a shifted coarser grid, and a duplicate of the same mask are not.

## 14. Which comparisons were statistically supported

Supported after Holm, matched top-10 minus no-box: exact, square-16, square-64, and width-64. Not supported: start-128 and the field box. The field difference is exactly zero on every page, which is the definition of that policy, not a failed experiment.

The bootstrap is surname clusters, because each test surname appears in 12 pages. It is not a permutation test.

## 15. Which findings contradict the original manuscript

None of these results contradict the synthetic mechanism. Exact rectangles carry the width class. Coarser classes carry less. A field box carries none. Singletons survive inside average rates that look modest.

What this study does not do is reproduce Table 3's 50.2% or 6.66 bits. Those belong to another list, other fonts, and another renderer. Quoting them as the PDF result would be a contradiction of this file, not of the manuscript. The FUNSD study's roughly 4.7% top-10 is a third estimand and is not pooled here.

## 16. What evidence is missing

A typesetter other than ReportLab and MuPDF. A physical print-and-scan. The study fonts and the 50,000-name list. Dense forms in which a widened line would cover the next field. An attacker who is fuzzy across renderers rather than requiring exact rectangle equality. Any real confidential page.

## 17. What is suitable for a journal article

Suitable, with the limits written next to them: the sub-pixel agreement of PDF glyph boxes with the attacker's catalog; the prior-weighted class table on the shipped list, including the singletons; the held-out-font collapse of the exact box and the failure of that protection under a 16 px grid; the field box matching the prior; the Holm table; the neighbor counts, which are zero except for the 64 px square; the repeated-release contrast between a second font and a duplicate mask; and the simulated scan, labeled as simulated.

Not suitable as a reprint of the 50.2% result.

## 18. What limitations remain

The list is the head 1,000, so common surnames dominate both the prior and the sample. The templates put one surname on its own line. Two of the writers share MuPDF. The scan is synthetic and mild. Held-out entropy without the truth-in-set rate would overstate what the attacker learned. See `LIMITATIONS.md`.

## 19. Can an independent researcher reproduce it

Yes, on a machine with these fonts, by `run_all.sh`. The protocol, seed, package versions, and catalog cache are in the directory. `verify_results.py` recomputes the intervals from the CSVs and does not import the scorer. It passed. Fonts are macOS system fonts. A Linux machine without Times New Roman and Arial cannot reproduce the rectangles without those files. The script does not download them.

## 20. The strongest defensible conclusion

When the attacker knows the engine, the font, and the pen, the exact redaction rectangle of a 12 pt surname in a real PDF is the same rectangle the attacker's catalog predicts, to well under a tenth of a pixel. On the shipped 1,000-name list that rectangle's prior-weighted top-10 is about 88.2% for Times in ReportLab, against about 12.0% from the prior alone, and some surnames are alone in the class. A field box removes that advantage by construction. A 128 px start-aligned mask reduces it to a lift this experiment cannot separate from zero after a Holm correction, and on these pages it covers no neighboring word. A held-out font removes the exact-box identification. A second release in a different font brings it back. A duplicate of the same mask does not.

Matched exact, in one line: top-1 36.3% (interval [27.0, 46.1]), top-10 87.0% (interval [80.6, 93.1]), no-box top-10 8.8%, difference 78.2 percentage points (interval [70.1, 86.5]), entropy reduction 6.23 bits (interval [6.0, 6.4] bits), true name inside the feasible set on 100.0% of pages, median feasible set 13.
