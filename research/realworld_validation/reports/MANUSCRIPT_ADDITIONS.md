# Manuscript additions

Draft text for a later revision. The manuscript was not edited. Numbers are from this run only.

## Design

We set 100 surnames, drawn with probability proportional to census count from the shipped head-1,000, into four invented layouts and three text engines (ReportLab, MuPDF, and Pillow/FreeType), 1,200 pages. Court and hospital text is Times New Roman; government and letter text is Arial. Courier New and Georgia are held out. LibreOffice and Poppler were not available. ReportLab and MuPDF share a reader. The attack averages use the 68 surnames in the test split (816 pages). A separate table weights all 1,000 names by the census prior and does not depend on the sample.

Redaction of the 800 text PDFs used PyMuPDF's redaction operator. The saved file was opened in PyMuPDF and pypdf; the surname was not extracted. Pillow pages are rasters with no text layer.

## Transfer

The page's glyph rectangle and the same engine's catalog rectangle differ by at most 0.0001 px. Under a matched attacker the true surname is feasible on every test page. For Times set by ReportLab, the prior-weighted top-10 of the exact box is 88.2% and the top-1 is 35.6%, against a no-box top-10 of 12.0%. 21 surnames are the only member of their class (prior mass 1.5%; maximum pointwise leakage 11.73 bits). These rates are not the 50.2% and 6.66 bits of the 50,000-name study. The list is shorter, so collisions are fewer.

On the test pages the matched exact top-10 is 87.0% (interval [80.6, 93.1]), 78.2 percentage points above the sample no-box rate of 8.8%. The paired interval excludes zero (Holm p 0.006).

## Mismatch

Replacing the font by a mixture of Times and Arial lowers exact top-10 to 79.4%. Restricting the attacker to Courier and Georgia, which never generated a page, lowers it to 7.4%, with the true name feasible on only 7.4% of pages. The difference from no-box includes zero. Entropy reduction of 5.17 bits on that arm is concentration on the wrong names and is not reported as information about the secret.

The same held-out attacker facing a 16 px square still has top-10 21.8% (difference 13.0 percentage points, interval [6.9, 19.7]). The coarser cell keeps the true name feasible on 85.5% of pages.

An attacker who unions exact rectangles from all three engines, without being told which engine was used, matches the matched-engine top-10 of 87.0%. The other engines' rectangles are not equal to the observed one, so the union does not add them. This is the strict rule stated in the protocol. It is not a fuzzy cross-renderer attack.

## Utility and worst case

Start-aligned 128 px padding has test top-10 11.8%. The paired difference from no-box is 2.9 percentage points (interval [0.0, 6.6], Holm p 0.188). It covers no neighboring word on these templates. The 64 px square does: on court pages it covers 2.82 neighboring words on average and touches another word on 66.7% of pages, at a median area ratio of 7.20. The field box matches the prior on every page.

Arial's square-64 grid still isolates MONTGOMERY (pointwise 10.03 bits, prior mass 0.1%). Average leakage near the prior is compatible with a unique surname.

## Repeated release and simulated scan

Republication of one mask does not change the feasible set (top-10 85.5%). A second PDF engine of the same font does not either (top-10 85.5%). A second font cuts the median feasible set from 15 to 2 and raises top-10 to 100.0%.

A simulated scan (rotation, blur, noise, JPEG; not a physical scan) leaves top-10 at 63.7% (interval [47.5, 80.0]) under a tolerance of 0.98 px taken from calibration pages.

## Conclusion paragraph

Geometry leakage of an exact surname box survives passage through ReportLab and MuPDF when the attacker shares the font and the pen. On this 1,000-name list the resulting top-10 is high, and it is not the previously published 50.2%. A held-out font removes that exact-box advantage. A field-wide box removes it by construction. Start-aligned padding reduces it to a difference this sample does not separate from zero, without covering neighboring words on these sparse lines. A 64 px square is the mask that does cover neighboring text, and even that grid leaves at least one Arial surname in a class by itself.
