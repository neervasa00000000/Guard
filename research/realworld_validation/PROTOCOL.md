# Protocol

Locked before the 1,200-document run. The two-name pilot checked that pages open, fonts embed, redaction removes text, and glyph edges match the catalog. It is not a result.

## What this study is

Fictional surnames from the shipped US Census head-1,000 list, set into four invented page layouts by three text engines. The pages are not confidential records and they are not the Dutch FOIA scans. Those page images are not in this repository.

## Engines

1. ReportLab writes a PDF. PyMuPDF reads it back and, when a raster is needed, renders it at 144 dpi.
2. PyMuPDF writes a PDF with `insert_font` and `insert_text`, then reads it back. The same library rasterizes it.
3. Pillow draws the page with FreeType at 24 px (12 pt at 144 dpi) and wraps the raster in an image-only PDF.

LibreOffice, Poppler, Ghostscript, and WeasyPrint were not available. Engines 1 and 2 share the MuPDF reader and the same TrueType files. They are different PDF writers. They are not two independent typesetting systems, and this protocol does not call them that. Pillow is a third rasterizer, not a third PDF text engine.

## Fonts and layouts

Court and hospital pages use Times New Roman. Government and letter pages use Arial. Courier New and Georgia are held out: no study page is set in them. Size is 12 pt for body and surname, 14 pt for the title. The pen positions are in `layout_tokens`.

## Sample and split

One hundred surnames are drawn without replacement with probability proportional to census count (Efraimidis–Spirakis, seed 20261116). The same hundred are used in every layout and engine: 4 × 3 × 100 = 1,200 pages.

A name is calibration if the first byte of SHA-256(`guard-rw-split:{name}`) is below 77, and test otherwise. About 30 percent are calibration. Attack averages are computed on test pages only. The calibration split is reserved for the simulated-scan tolerance.

Frequency bands use position in the shipped file, which is count order: 1–100 common, 101–500 medium, 501–1000 rare. The rank column is not a row number; six values are shared by two rows. Long means 10 or 11 letters. The shipped list has no longer name. Its maximum length is CHRISTENSEN.

## Policies

Page pixels are at 144 dpi, so 1 px = 0.5 pt. The exact box is the glyph edge expanded by 1 px. Square grids snap that box outward onto a 16 px or 64 px page grid. Width-only 64 px and start-aligned 128 px keep the shared left edge `x_L` (one pixel left of the leftmost glyph in the candidate list) and round the width up. The field box is the single rectangle that covers every name in the shipped list at that font and engine.

Width, start-aligned, and field policies need the candidate list. Exact and square policies need only the rendered glyph. Comparisons across those groups are not claims that one policy dominates under the same knowledge.

The integer maps were checked against `research/e1/policies.py` on integer glyphs.

## Sanitization

Text PDFs are redacted with PyMuPDF `apply_redactions` on the glyph box expanded by 1 pt, written, and opened again. PyMuPDF and pypdf must not return the surname, metadata must not contain it, and no annotation may remain. A page that fails is dropped from the attack and listed in `redaction_failures.csv`. Pillow pages have no text layer. The surname is painted out and the raster is embedded. An empty text extraction on that file shows there was no text layer. It is not a claim about a PDF text redaction.

A drawn black rectangle over extractable text is not used as a sanitized file.

## Attacker

The attacker is the manuscript's possibilistic attacker: every candidate whose predicted rectangle matches the observed rectangle within 0.51 px stays in, with its census prior, and the others go out. Ties in the prior are expected hits. The match tolerance is half a pixel because the policy edges are integers. It was not fit on test pages.

The predicted rectangle is the policy applied to that engine's own measured glyph catalog, placed at the known pen. The catalog is a batch rendering of all 1,000 names, not `stringWidth` alone.

- Matched: the page's engine and font.
- Unknown renderer: the union of ReportLab, MuPDF, and Pillow for the page's font. The true engine is not removed.
- Unknown font: the union of Times and Arial for the page's engine. The page's font is not selected.
- Held-out font: the union of Courier and Georgia for the page's engine. Times and Arial are not used.

All four are told the pen and the policy. A field policy therefore leaves the whole list feasible for every attacker. Whether a held-out font's own field rectangle equals the observed rectangle is recorded separately (`rectangle_covers_truth`) and is not turned into an identification.

An empty feasible set is a model miss. The hit falls back to the no-box hit and the entropy reduction is zero. A non-empty set that excludes the true name scores a hit of zero. Entropy reduction on a non-empty set is concentration of the prior on that set, including concentration on the wrong name. Pointwise bits are `-log2` of the feasible prior mass, and only when the true name is inside.

The no-box attacker ranks the census prior and ignores the rectangle.

## What is population and what is a sample

The exhaustive table applies the same rectangles to all 1,000 shipped names and weights hits by the census prior. It is a property of the font and the policy under a perfect observation. It is not a 50,000-name result. The unpublished full census file is not in this checkout.

The test-page averages are means over the probability-proportional sample, which over-represents frequent surnames. They answer whether the PDF pages realize the catalog classes. They are not reweighted to the 1,000-name prior. If a page's rectangle matches the catalog, that page's hit equals the class hit of its surname.

## Scans

No page was printed or scanned. The scan arm is simulated: rotation uniform on ±0.6 degrees, Gaussian blur of radius 0.6, pixel noise of standard deviation 6, JPEG quality 40. Seed `simulated-scan`. Forty calibration pages and eighty test pages, balanced across layouts, ReportLab only. The attack tolerance is the 95th percentile of absolute width error on the calibration pages. Test errors are not used to choose it. If fewer than eight calibration detections succeed, the arm is not scored.

## Repeated releases

Up to 200 test ReportLab pages, in layout then name order. The cumulative feasible set intersects, in order: the exact box, the MuPDF exact prediction on that same box, a square-16 grid after a 7 px horizontal shift, the exact box in the other in-distribution font, and the 128 px start-aligned box. A control repeats the exact mask five times. Repeating one mask does not add a likelihood.

The shift and the second font are calculated from the measured glyph catalog. They are not second print runs. The unit of the shift check is the same policy function that builds the study boxes.

## Statistics

Bootstrap resamples surnames, keeps every test page of each drawn surname, and takes the mean. Two thousand draws. Each interval has its own generator, seeded by SHA-256 of `20261116:{key}`. The interval is the 2.5 and 97.5 percentiles.

The paired estimand is top-10 minus the no-box top-10 on the same page. The p-value is twice the share of bootstrap means on the non-positive side, with one added to the numerator and the denominator, and capped at 1. Holm adjustment is applied inside the family of six matched policies. It is a percentile bootstrap p-value, not a permutation p-value.

## Exclusion

A page whose sanitizer fails, or a policy rectangle that does not contain the measured glyph, is out of the attack means and is counted in the failure files.
