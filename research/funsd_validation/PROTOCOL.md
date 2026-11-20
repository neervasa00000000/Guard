# Protocol: FUNSD real-document validation

This protocol was written in the same working session as the code, after a diagnostic look at image mode, box bounds, text/word consistency, ink, and form-rule spill. It was not pre-registered. It was locked before attack scores were computed. The diagnostic quantities that were seen before lock are listed in the methodology report. Thresholds below were not retuned after recovery accuracies were known.

This experiment applies controlled solid-black rectangles to FUNSD scans. It is not an evaluation of redactions that already existed on the pages.

## Dataset

- Local copy of FUNSD under `dataset/training_data` and `dataset/testing_data`.
- Official split only: 149 training documents, 50 test documents. Stems must be disjoint.
- No document is moved between splits.

## Population

Filled answer entities (`label == "answer"`). Questions, headers, and other regions are counted and then left out of redaction scoring. They are labels and page furniture, not the filled values the synthetic study treats as the secret.

## Ground truth

The ground-truth string is the whitespace-normalized entity text, `" ".join(text.split())`. Word texts must normalize to the same string. The three-way disagreement case is excluded rather than repaired. No OCR engine is used. Tesseract is not installed in this environment, so an independent transcription was not run.

FUNSD boxes are stored as `[x0, y0, x1, y1]`. The primary geometry treats those edges as inclusive pixel indices, because a probe found dark pixels on the stored right and bottom edges. The half-open rectangle used for painting and area is `[x0, x1+1) × [y0, y1+1)`. A sensitivity analysis repeats the width–length correlation with the opposite reading, half-open `[x0, x1) × [y0, y1)`, and does not replace the primary definition.

## Eligibility, first failure wins

An answer is eligible only if every item below holds.

1. Normalized text is non-empty.
2. Normalized entity text equals the normalized concatenation of its word texts.
3. At least one word box is present.
4. The stored box has positive area and lies inside the image under the inclusive reading.
5. The entity is horizontal: width greater than or equal to height.
6. Every word box is horizontal.
7. The words form one line: after sorting by left edge, each consecutive pair overlaps vertically by at least half the shorter word height.
8. The normalized string has at most 80 characters.
9. The inclusive rectangle contains at least 8 pixels with gray value below 140, and those pixels are at least 2% of the rectangle.

Side ink is recorded and does not exclude a field. Side ink is the count of pixels below 140 in the two-pixel columns immediately left and right of the box, restricted to the central half of the box height, so that underlines and table rules are not counted as leaked glyphs. A field has side spill if that count is at least 6.

## Policies that are applied

Rectangles are painted solid black on a copy of the original grayscale image. Pixels outside the rectangle are not modified.

- Exact box. The inclusive annotation rectangle. Required knowledge: the annotation. This is available because the redactor in this controlled experiment is given the FUNSD box.
- Square grids of 8, 16, 32, and 64 pixels. The half-open exact rectangle is expanded outward onto the image pixel grid. Required knowledge: image coordinates and the grid. No font and no pen position.
- Annotation-anchored width grids of 32, 64, and 128 pixels. The left edge stays on the annotation left; the width rounds up to a multiple of the class; the top and bottom stay on the annotation. Required knowledge: the annotation left edge, used as a local anchor for that field.
- The same rectangles are also recorded under the name start-aligned padding. Under this anchor they are the same map as the width grid. They are not the manuscript's start-aligned policy: the manuscript also replaces the vertical extent with a known font line, and it anchors a shared typesetting pen across a candidate list. Neither the font line nor a shared pen is known on these scans.
- Fixed field boxes are not applied. FUNSD does not annotate the blank field rectangle, and this protocol does not invent one from the longest string on the page.

## What is refused

- No matched-renderer attack. The scans do not name a font, a size, or a renderer. The six study fonts are not on this machine.
- No claim that a box leaks zero bits merely because an attack was not identified.
- No pooling of FUNSD rows with the surname or word archives.
- Top-1, top-10, the no-box baseline, and bits are computed only inside an explicitly extra-knowledge regime with a candidate distribution and a probabilistic observation model.
- The realistic regime, in which the attacker sees only the redacted image, does not have a candidate distribution. Its recovery metrics stay unidentified.

## Extra-knowledge regimes that are computed

Both regimes are attacks only under additional assumptions. Training documents alone build the candidate list and fit the observation model. Test documents are scored after the fit is frozen.

Candidate strings are the distinct normalized texts of eligible training answers. The prior probability of a string is its share of eligible training fields. Test strings are not inserted into the list.

1. Length–width model. On training fields, ordinary least squares fits inclusive width on a constant plus character length. Residual standard deviation uses `n - 2` degrees of freedom. The regime is failed, not patched, if the slope is not positive or the residual scale is below `0.001` pixel. A string of length `L` has predictive mean `a + bL`. The likelihood of an observed integer width bin is the normal probability of that bin.
2. Mismatched renderers. Arial, Times New Roman, and Courier New, each at sizes 8, 10, 12, 14, 16, 18, 20, 22, and 24. For each font, the size with the smallest training median absolute error is frozen. Ties take the smaller size. These fonts are not the font on the page. The study fonts are not substituted in.

The exact-box observation is the unit bin around the inclusive width. A square grid contributes the integer widths still compatible with outward snapping. A width grid contributes the integer widths that round up to the observed class. Likelihoods are bin probabilities, so exact and quantized policies stay on one scale.

Top-1 and top-10 use expected tie resolution: if `g` candidates are strictly more probable and `e` are tied with the truth, the hit at `k` is `min(1, max(0, (k-g)/e))` when the truth is in the list, and 0 otherwise. The no-box baseline ranks the same prior and ignores the rectangle.

Two bit quantities are reported, and they are not interchangeable with the manuscript's mutual information:

- Dictionary entropy reduction is `H(prior) - H(posterior)` on the training candidate list. It is defined for every test field. It measures concentration, including concentration on the wrong string.
- Pointwise truth information gain is `log2 posterior(truth) - log2 prior(truth)`. It is defined only when the true string is in the training list. It is the quantity used when this report says leakage about the true string. It can be negative when the model moves probability away from the truth.

Unconditional top-1 includes test fields whose text was never seen in training. Conditional top-1 is the in-list subgroup and is labeled as a subgroup.

## Uncertainty and exposure

Primary 95% intervals are percentile cluster bootstraps that resample test documents with replacement, 2000 times, seed `20261116`. Fields on one page stay together. Intervals for the truth-information-gain mean use only in-list fields. Median area ratios use the same document resampling.

Worst-case area exposure is the maximum area ratio on the test fields. Worst-case identity exposure is the maximum pointwise truth information gain and the maximum top-candidate posterior, with the document and entity id retained.

## Coverage checks

For every eligible field, a copy of the page is painted black on the policy rectangle, clipped to the image. The check passes only if every previously dark pixel inside the exact inclusive rectangle is black and every pixel outside the painted rectangle is unchanged. This confirms that the implementation covers the annotation. It does not confirm that the annotation contains every glyph. Side spill is the separate residual-ink measurement.

## Independence

Evaluation code that ranks candidates receives bin endpoints, candidate strings, predictive means, the prior, and the residual scale. It receives the true string only when the score of that string is read out for scoring. The observation table written for the verifier has no text and no length column. The verifier recomputes the metrics with a separate implementation.
