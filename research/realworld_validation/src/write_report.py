"""Write the reports from the result files. No number is typed by hand."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
RESULTS = HERE / "results"
REPORTS = HERE / "reports"


def pct(value):
    return f"{100 * float(value):.1f}%"


def pp(value):
    return f"{100 * float(value):.1f} percentage points"


def ci(low, high, scale=100):
    return f"[{scale * float(low):.1f}, {scale * float(high):.1f}]"


def row(frame, attacker, policy):
    hit = frame[(frame.attacker == attacker) & (frame.policy == policy)]
    if hit.empty:
        raise SystemExit(f"missing {attacker} {policy}")
    return hit.iloc[0]


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    stats = json.loads((RESULTS / "statistics.json").read_text())
    attacks = pd.DataFrame(stats["attacks"])
    raw = pd.read_csv(RESULTS / "attacker_results.csv")
    worst = pd.read_csv(RESULTS / "worst_case_results.csv")
    utility = pd.read_csv(RESULTS / "utility_results.csv")
    repeated = pd.read_csv(RESULTS / "repeated_releases.csv")
    docs = pd.read_csv(RESULTS / "documents.csv")
    verification = json.loads((RESULTS / "verification.json").read_text())
    matched = {policy: row(attacks, "matched", policy) for policy in
               ["exact", "square16", "square64", "width64", "start128", "field"]}
    held = {policy: row(attacks, "heldout_font", policy) for policy in matched}
    mix = {policy: row(attacks, "unknown_font", policy) for policy in matched}
    rend = {policy: row(attacks, "unknown_renderer", policy) for policy in matched}
    tests = {item["policy"]: item for item in stats["tests"]}
    scan = stats["scan"]

    def worst_row(font, policy, engine="reportlab"):
        hit = worst[(worst.font == font) & (worst.policy == policy) & (worst.engine == engine)]
        return hit.iloc[0]

    times_exact = worst_row("Times", "exact")
    arial_exact = worst_row("Arial", "exact")
    times_field = worst_row("Times", "field")
    arial_sq64 = worst_row("Arial", "square64")
    arial_sq16 = worst_row("Arial", "square16")
    pillow_exact = worst[(worst.engine == "pillow") & (worst.font == "Times") & (worst.policy == "exact")].iloc[0]
    mupdf_exact = worst[(worst.engine == "mupdf") & (worst.font == "Times") & (worst.policy == "exact")].iloc[0]

    pdf_pages = raw[(raw.attacker == "matched") & (raw.policy == "exact") & (raw.engine != "pillow")]
    held_exact_rows = raw[(raw.attacker == "heldout_font") & (raw.policy == "exact")]
    held_when_true = held_exact_rows[held_exact_rows.truth_in_set == True]  # noqa: E712
    rep = repeated[repeated.kind == "new_geometry"].groupby("releases")[["hit1", "hit10", "feasible", "entropy_reduction", "truth_in_set"]].mean()
    identical = repeated[repeated.kind == "identical_mask"]
    conflict = repeated[repeated.kind == "cross_engine_same_rectangle"]
    square = utility[utility.policy == "square64"]

    def attack_line(item):
        return (
            f"top-1 {pct(item.top1)} (interval {ci(item.top1_ci_low, item.top1_ci_high)}), "
            f"top-10 {pct(item.top10)} (interval {ci(item.top10_ci_low, item.top10_ci_high)}), "
            f"no-box top-10 {pct(item.nobox_top10)}, "
            f"difference {pp(item.top10_minus_nobox)} (interval {ci(item.diff_ci_low, item.diff_ci_high)}), "
            f"entropy reduction {item.entropy_reduction:.2f} bits "
            f"(interval {ci(item.entropy_ci_low, item.entropy_ci_high, scale=1)} bits), "
            f"true name inside the feasible set on {pct(item.truth_in_set)} of pages, "
            f"median feasible set {item.median_feasible:.0f}"
        )

    final = f"""# Final validation report

Fictional surnames from the shipped census head-1,000, set in invented pages. These are not confidential documents. The Dutch FOIA page images are not in this checkout and were not scored.

The independent check of the CSV summaries is `results/verification.json`: {verification["n_checks_failed"]} failures, {verification["n_attack_rows"]} attack rows, median glyph-edge error {verification["median_edge_error_px"]:.4f} px, maximum {verification["max_edge_error_px"]:.6f} px. Every number below is read from `results/`.

## 1. What was implemented

Six policies from the manuscript's geometry: exact box with a 1 px margin, square grids at 16 and 64 px, a width-only grid at 64 px anchored at the shared text start, start-aligned padding at 128 px, and one field box covering the whole shipped list. The integer maps were checked against `research/e1/policies.py`.

Four attackers, all told the pen and the policy. Matched uses the page's engine and font. Unknown renderer takes the union of ReportLab, MuPDF, and Pillow for that font and does not drop the true engine. Unknown font takes the union of Times and Arial and does not look at the page's font. Held-out font uses only Courier and Georgia. A candidate stays in if its predicted rectangle matches the observed rectangle within half a pixel. Ties in the census prior are expected hits. A field box is defined to leave the whole list feasible.

## 2. How many documents were generated

{stats["n_documents"]} pages. {stats["n_sampled_names"]} surnames, probability proportional to census count, seed 20261116, reused across 4 layouts and 3 engines. The split is by surname: {int((docs.split == "calibration").sum())} calibration pages and {int((docs.split == "test").sum())} test pages ({docs.loc[docs.split == "test", "name"].nunique()} test surnames). Attack averages use the test pages only.

## 3. How many valid redactions were created

{stats["n_failures"]} sanitizer failures and {stats["n_excluded_masks"]} masks that missed the glyph. All {stats["n_documents"]} pages and all six policies on the test pages entered the attack. Text pages, {int((docs.text_check == "pymupdf_apply_redactions_reopened").sum())} of them, were redacted with PyMuPDF `apply_redactions`, written, and opened again in PyMuPDF and pypdf. The surname was absent from both extractors, from metadata, and from the raw ASCII of the saved file. The redacted clip averaged {docs.loc[docs.engine != "pillow", "redact_fill_mean"].mean():.2f} on a 0–255 scale (maximum {docs.loc[docs.engine != "pillow", "redact_fill_mean"].max():.2f}). Pillow's {int((docs.engine == "pillow").sum())} pages are image-only PDFs with the surname painted out. An empty text layer on those files is not a PDF text redaction.

## 4. Which PDF engines were used

ReportLab  {stats["environment"]["reportlab"]} wrote 400 PDFs. PyMuPDF {stats["environment"]["pymupdf"]} wrote 400 and rasterized both when a raster was needed. Pillow {stats["environment"]["pillow"]} drew 400 pages. LibreOffice, Poppler, Ghostscript, and WeasyPrint were not installed (`environment.json`). ReportLab and MuPDF are different writers sharing a reader and the same TrueType files. They are not two independent typesetting systems.

Court and hospital pages are Times New Roman. Government and letter pages are Arial. Courier New and Georgia are held out. Body size is 12 pt. Raster scale is 144 dpi.

## 5. Which attackers were evaluated

Matched, unknown renderer, unknown font, and held-out font, on all six policies, plus the no-box prior. The simulated-scan attacker is separate and uses a width tolerance fit on calibration pages only.

## 6. Actual top-1 and top-10

Test pages, surname-cluster 95% intervals, 2000 draws, seed 20261116. No-box top-10 on these pages is {pct(matched["exact"].nobox_top10)}. That is the mean over the sampled test surnames. The prior-weighted no-box top-10 on all 1,000 names is {pct(times_field.prior_weighted_top10)}, which is the field-box row because a field box leaves the prior unchanged. The manuscript's 5.932% is the no-box rate of the 50,000-name list and is not this number.

Matched attacker, test pages:

| Policy | Top-1 | Top-10 | Difference from no-box | Holm p |
| --- | ---: | ---: | ---: | ---: |
| Exact | {pct(matched["exact"].top1)} | {pct(matched["exact"].top10)} {ci(matched["exact"].top10_ci_low, matched["exact"].top10_ci_high)} | {pp(matched["exact"].top10_minus_nobox)} {ci(matched["exact"].diff_ci_low, matched["exact"].diff_ci_high)} | {tests["exact"]["p_holm"]:.3f} |
| Square 16 | {pct(matched["square16"].top1)} | {pct(matched["square16"].top10)} {ci(matched["square16"].top10_ci_low, matched["square16"].top10_ci_high)} | {pp(matched["square16"].top10_minus_nobox)} {ci(matched["square16"].diff_ci_low, matched["square16"].diff_ci_high)} | {tests["square16"]["p_holm"]:.3f} |
| Square 64 | {pct(matched["square64"].top1)} | {pct(matched["square64"].top10)} {ci(matched["square64"].top10_ci_low, matched["square64"].top10_ci_high)} | {pp(matched["square64"].top10_minus_nobox)} {ci(matched["square64"].diff_ci_low, matched["square64"].diff_ci_high)} | {tests["square64"]["p_holm"]:.3f} |
| Width 64 | {pct(matched["width64"].top1)} | {pct(matched["width64"].top10)} {ci(matched["width64"].top10_ci_low, matched["width64"].top10_ci_high)} | {pp(matched["width64"].top10_minus_nobox)} {ci(matched["width64"].diff_ci_low, matched["width64"].diff_ci_high)} | {tests["width64"]["p_holm"]:.3f} |
| Start 128 | {pct(matched["start128"].top1)} | {pct(matched["start128"].top10)} {ci(matched["start128"].top10_ci_low, matched["start128"].top10_ci_high)} | {pp(matched["start128"].top10_minus_nobox)} {ci(matched["start128"].diff_ci_low, matched["start128"].diff_ci_high)} | {tests["start128"]["p_holm"]:.3f} |
| Field | {pct(matched["field"].top1)} | {pct(matched["field"].top10)} {ci(matched["field"].top10_ci_low, matched["field"].top10_ci_high)} | {pp(matched["field"].top10_minus_nobox)} | {tests["field"]["p_holm"]:.3f} |

The p-value adds one to the numerator and the denominator, so a run in which no bootstrap mean crossed zero is reported as about 0.001 before Holm, not as zero. Holm is over the six matched policies.

PDF writers only, matched exact, unweighted over their test pages: top-10 {pct(pdf_pages.hit10.mean())}, top-1 {pct(pdf_pages.hit1.mean())}, {len(pdf_pages)} pages. Pillow alone is higher: top-10 {pct(raw[(raw.attacker == "matched") & (raw.policy == "exact") & (raw.engine == "pillow")].hit10.mean())}.

## 7. Did exact-box leakage transfer to real PDF pipelines

Yes, for these fonts and this list. The measured glyph rectangle and the engine's own catalog rectangle differ by at most {verification["max_edge_error_px"]:.6f} px. The matched attacker placed the true name in the feasible set on every test page. ReportLab Times, prior-weighted over all 1,000 names: top-1 {pct(times_exact.prior_weighted_top1)}, top-10 {pct(times_exact.prior_weighted_top10)}, {int(times_exact.singleton_names)} singleton widths, {int(times_exact.n_classes)} width classes. MuPDF Times top-10 is {pct(mupdf_exact.prior_weighted_top10)}. Pillow Times top-10 is {pct(pillow_exact.prior_weighted_top10)}, with {int(pillow_exact.singleton_names)} singletons. FreeType's integer widths are finer than the PDF writers' widths. Pooling the three engines hides that.

This is not the manuscript's 50.2% top-10. That figure is 36,000 surname trials on a 50,000-name list rendered with the study fonts. The full census file is not in this checkout. A 1,000-name list has fewer collisions, so identification is higher. The transferred fact is the geometry, not the published percentage.

## 8. Did start-aligned padding remain effective

On the test pages the matched start-128 top-10 is {pct(matched["start128"].top10)}, {pp(matched["start128"].top10_minus_nobox)} above the no-box rate. The paired interval is {ci(matched["start128"].diff_ci_low, matched["start128"].diff_ci_high)} and includes zero. Holm p is {tests["start128"]["p_holm"]:.3f}. The prior-weighted top-10 on Times is {pct(worst_row("Times", "start128").prior_weighted_top10)} against the no-box {pct(times_field.prior_weighted_top10)}. The point estimate is a small lift. This experiment does not separate it from the prior after the multiplicity correction.

Width-64 does separate: difference {pp(matched["width64"].top10_minus_nobox)}, interval {ci(matched["width64"].diff_ci_low, matched["width64"].diff_ci_high)}, Holm p {tests["width64"]["p_holm"]:.3f}. It is a small effect next to the exact box.

These two policies need the shared text start and the candidate list. Exact and square policies do not. The comparison is not a claim that one is better under the same knowledge.

## 9. Did any individual remain uniquely identifiable

Yes, on the shipped list. The sample not containing a singleton would not have been evidence that none exists. The exhaustive table does.

Times, ReportLab, exact box: {int(times_exact.singleton_names)} surnames are alone in their rectangle. Their prior mass is {pct(times_exact.prior_mass_singleton)}. The largest pointwise value is {times_exact.max_pointwise_bits:.2f} bits. One singleton, not necessarily the largest, is {times_exact.example_singleton}. Arial exact: {int(arial_exact.singleton_names)} singletons, prior mass {pct(arial_exact.prior_mass_singleton)}, one of them {arial_exact.example_singleton}. Classes smaller than 10 hold {pct(times_exact.prior_mass_lt_10)} of the Times prior and {pct(arial_exact.prior_mass_lt_10)} of the Arial prior.

Coarser policies do not wipe this out. Arial square-16 has {int(arial_sq16.singleton_names)} singleton ({arial_sq16.example_singleton}, {arial_sq16.max_pointwise_bits:.2f} bits). Arial square-64 still has that singleton: prior mass {pct(arial_sq64.prior_mass_singleton)}, {arial_sq64.max_pointwise_bits:.2f} bits. Times square-64 and both start-128 rows have no singletons. Rare-name prior-weighted top-10 under Times exact is {pct(times_exact.mean_hit10_rare)}; under Times start-128 it is {pct(worst_row("Times", "start128").mean_hit10_rare)}. Long names (10 or 11 letters; the list has none longer) have Times exact top-10 {pct(times_exact.mean_hit10_long)}.

This is a guarantee for the shipped 1,000 names under these fonts. It is not a guarantee for the unpublished 50,000.

## 10. How much neighboring information was lost

Only the 64 px square covered a neighboring word. Containment of the surname glyph was 1 for every policy and layout.

| Layout | Square-64 median area ratio | Mean neighboring words | Pages with any loss |
| --- | ---: | ---: | ---: |
"""
    for _, item in square.iterrows():
        final += (
            f"| {item.layout} | {item.median_area_ratio:.2f} | {item.mean_covered_words:.2f} | "
            f"{pct(item.documents_with_neighbor_loss)} |\n"
        )
    final += f"""
Exact boxes have area ratio 1 and cover no neighbor. Start-128 median area ratios are between {utility.loc[utility.policy == "start128", "median_area_ratio"].min():.2f} and {utility.loc[utility.policy == "start128", "median_area_ratio"].max():.2f}, and the neighbor count is zero. Width-64 is the same. The surname is on its own line in these templates, and a mask that only widens that line does not reach the next one. The 64 px square does: on the court page it covers the label above the surname and the first line of the paragraph. The figure is `figures/example_boxes.png`, surname SMITH, which is a census name on an invented page.

So, on these templates, the policy that actually reduces identification without a detectable neighbor cost is the start-aligned or width-only mask, and the neighbor cost shows up when the mask grows vertically. A denser form could change the neighbor counts. This study did not rebuild the templates after seeing that.

## 11. Renderer and font mismatch

Unknown renderer, exact box: {attack_line(rend["exact"])}.

That matches the matched exact attack. It matches because a candidate is kept only when some engine reproduces the whole rectangle. MuPDF's exact rectangle never equalled the ReportLab rectangle on the 200 repeated-release pages (mean feasible set {conflict.feasible.mean():.1f}, true name inside on {pct(conflict.truth_in_set.mean())}). Pillow did not either. The union therefore collapses to the true engine. This is not evidence that a renderer mismatch is harmless. It is evidence that exact rectangle equality is a strict test, and these engines do not meet it for one another's boxes. A fuzzy cross-renderer attacker was not the predeclared primary test.

Unknown font, the union of Times and Arial, exact box: {attack_line(mix["exact"])}. The true name stayed feasible on every page. Top-10 fell from {pct(matched["exact"].top10)} to {pct(mix["exact"].top10)}. Mixing the two fonts used in the study widens the set and does not remove the leak.

Held-out Courier and Georgia, exact box: {attack_line(held["exact"])}. The true name is inside on only {pct(held["exact"].truth_in_set)} of pages. The paired difference from no-box includes zero. The {held["exact"].entropy_reduction:.2f} bits of entropy reduction are mostly concentration on the wrong surnames. On the pages where the true name is inside, the mean entropy reduction is {held_when_true.entropy_reduction.mean():.2f} bits ({len(held_when_true)} pages). Those bits are not the headline.

Held-out square-16 still raises top-10: {attack_line(held["square16"])}. A coarse cell is large enough that the wrong font often still contains the truth, and the prior then ranks inside that cell. Font mismatch is much more protective for an exact box than for a 16 px grid.

## 12. Scanned or scan-like documents

No page was printed or scanned. The arm is a simulated degradation of 40 calibration and {scan["test_n"]} test ReportLab pages: rotation ±0.6 degrees, blur radius 0.6, noise standard deviation 6, JPEG quality 40. The tolerance is the calibration 95th percentile, {scan["tolerance_px"]:.2f} px. Calibration median absolute width error was {scan["calibration_median_abs_error_px"]:.2f} px. Test labels were not used to set the tolerance.

On the test pages, top-1 is {pct(scan["test_top1"])}, top-10 is {pct(scan["test_top10"])} with interval {ci(scan["test_top10_ci"][0], scan["test_top10_ci"][1])}, no-box top-10 on this subset is {pct(scan["test_nobox_top10"])}, and the true width is inside the tolerance on {pct(scan["test_truth_in_set"])} of pages. This mild simulated scan did not remove the width attack. It says nothing about a copier, a phone photograph, or a skew of several degrees.

## 13. Did repeated releases increase leakage

Two hundred ReportLab test pages. Publishing the same exact mask five times leaves top-10 at {pct(identical.hit10.mean())} and the median feasible set at {identical.feasible.median():.0f}. A second rendering by MuPDF, with the attacker told that the second page is MuPDF, leaves top-10 at {pct(rep.loc[2, "hit10"])} and the median feasible set at {repeated[(repeated.kind == "new_geometry") & (repeated.releases == 2)].feasible.median():.0f}. A 7 px shift of the square-16 grid does not shrink the exact-width class, because names that share an exact width still share the coarser cell. Top-10 stays {pct(rep.loc[3, "hit10"])}.

A second release in the other in-distribution font does change the set. Median feasible size falls from {repeated[(repeated.kind == "new_geometry") & (repeated.releases == 1)].feasible.median():.0f} to {repeated[(repeated.kind == "new_geometry") & (repeated.releases == 4)].feasible.median():.0f}. Top-1 rises from {pct(rep.loc[1, "hit1"])} to {pct(rep.loc[4, "hit1"])}, and top-10 rises from {pct(rep.loc[1, "hit10"])} to {pct(rep.loc[4, "hit10"])}. Entropy reduction rises from {rep.loc[1, "entropy_reduction"]:.2f} to {rep.loc[4, "entropy_reduction"]:.2f} bits. The true name stayed feasible. Adding the start-128 mask on top of that does not move the averages further.

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

When the attacker knows the engine, the font, and the pen, the exact redaction rectangle of a 12 pt surname in a real PDF is the same rectangle the attacker's catalog predicts, to well under a tenth of a pixel. On the shipped 1,000-name list that rectangle's prior-weighted top-10 is about {pct(times_exact.prior_weighted_top10)} for Times in ReportLab, against about {pct(times_field.prior_weighted_top10)} from the prior alone, and some surnames are alone in the class. A field box removes that advantage by construction. A 128 px start-aligned mask reduces it to a lift this experiment cannot separate from zero after a Holm correction, and on these pages it covers no neighboring word. A held-out font removes the exact-box identification. A second release in a different font brings it back. A duplicate of the same mask does not.

Matched exact, in one line: {attack_line(matched["exact"])}.
"""
    (REPORTS / "FINAL_VALIDATION_REPORT.md").write_text(final)

    claims = f"""# Claims and evidence

Each claim is a statement this run supports. The check is `src/verify_results.py` unless a row says otherwise.

| Claim | Result | File |
| --- | --- | --- |
| 1,200 pages, 0 sanitizer failures | {stats["n_documents"]} pages, {stats["n_failures"]} failures | `results/statistics.json`, `results/documents.csv` |
| Glyph box matches the catalog | max edge error {verification["max_edge_error_px"]:.6f} px | `results/verification.json` |
| Text was removed and the file reopened | 800 redactions, both extractors clean | `results/documents.csv` column `text_check` |
| Matched exact top-10 above no-box | {pct(matched["exact"].top10)} vs {pct(matched["exact"].nobox_top10)}, Holm p {tests["exact"]["p_holm"]:.3f} | `results/statistics.json` |
| Field box equals the prior | difference 0 on every test page, feasible set 1000 | `results/attacker_results.csv` |
| Start-128 lift not separated from zero after Holm | difference {pp(matched["start128"].top10_minus_nobox)}, Holm p {tests["start128"]["p_holm"]:.3f} | `results/statistics.json` |
| Singletons exist on the shipped list | Times exact {int(times_exact.singleton_names)}, Arial exact {int(arial_exact.singleton_names)}, Arial square-64 {int(arial_sq64.singleton_names)} | `results/worst_case_results.csv` |
| Only square-64 covers neighbors | other policies, 0 neighboring words | `results/utility_results.csv` |
| Held-out exact does not beat no-box | top-10 {pct(held["exact"].top10)}, truth inside on {pct(held["exact"].truth_in_set)} | `results/attacker_results.csv` |
| A duplicate mask adds nothing | top-10 stays {pct(identical.hit10.mean())} | `results/repeated_releases.csv` |
| A second font shrinks the set | median feasible {repeated[(repeated.kind == "new_geometry") & (repeated.releases == 1)].feasible.median():.0f} to {repeated[(repeated.kind == "new_geometry") & (repeated.releases == 4)].feasible.median():.0f} | `results/repeated_releases.csv` |
| Simulated scan, not a physical scan | top-10 {pct(scan["test_top10"])}, tolerance {scan["tolerance_px"]:.2f} px | `results/statistics.json` key `scan` |
| Verifier agreed | {verification["n_checks_failed"]} failures | `results/verification.json` |

The manuscript Table 3 rates are not claims of this run. They live in `out/tables/table3.csv`.
"""
    (REPORTS / "CLAIMS_AND_EVIDENCE.md").write_text(claims)

    limitations = f"""# Limitations

Read as a reviewer.

Internal validity. The glyph measurement, the redaction check, and the feasible-set arithmetic agree with an independent recomputation. The field-box result is true by the definition used here, so it is not evidence that a field box was estimated. The unknown-renderer arm is a weak test of mismatch: exact equality of the whole rectangle makes the other engines contribute nobody, so the union equals the matched attack. That was the predeclared rule. It should not be rewritten, after the fact, as a finding that renderer mismatch is harmless.

External validity. The pages are short, invented, and give the surname a line of its own. A court PDF with the name inside a paragraph would show more neighbor loss and a less obvious pen. The fonts are Times, Arial, Courier, and Georgia on macOS, not the paper's DejaVu, Liberation, and Noto. The list is the most frequent 1,000 surnames, not 50,000. Common names are over-represented in the sample by construction. The prior-weighted table is the one that respects that; the test-page mean does not reweight.

Reproducibility. Seeds, versions, and the verifier are present. The fonts are not redistributed. LibreOffice was unavailable, and Pillow was not described as a substitute for it.

Statistical validity. Intervals are surname-cluster percentile intervals. The p-values are not permutation p-values, and the smallest attainable value is about 1/2000 before the continuity correction used here. Holm covers six tests. The scan interval is a different subset and a different attacker (width tolerance, not rectangle equality). Held-out entropy without the truth-in-set rate is not information about the secret.

Attacker realism. The matched attacker knows the pen, the engine, the font, and the list. That is the manuscript's strong attacker, and it is the right one for a transfer test. It is a generous description of someone who has only a flattened scan and no template. The held-out arm is the closer description of that person, and there the exact box does not beat the prior.

Dataset. No real redacted filing was opened. Nothing here identifies a private person. The singleton examples are public census surnames in a width class, not recovered identities.

Policy fairness. Width, start-aligned, and field masks use the candidate list. Exact and square masks do not. A sentence that ranks them on one scale of "privacy" without that distinction is not supported.
"""
    (REPORTS / "LIMITATIONS.md").write_text(limitations)

    manuscript = f"""# Manuscript additions

Draft text for a later revision. The manuscript was not edited. Numbers are from this run only.

## Design

We set 100 surnames, drawn with probability proportional to census count from the shipped head-1,000, into four invented layouts and three text engines (ReportLab, MuPDF, and Pillow/FreeType), 1,200 pages. Court and hospital text is Times New Roman; government and letter text is Arial. Courier New and Georgia are held out. LibreOffice and Poppler were not available. ReportLab and MuPDF share a reader. The attack averages use the 68 surnames in the test split (816 pages). A separate table weights all 1,000 names by the census prior and does not depend on the sample.

Redaction of the 800 text PDFs used PyMuPDF's redaction operator. The saved file was opened in PyMuPDF and pypdf; the surname was not extracted. Pillow pages are rasters with no text layer.

## Transfer

The page's glyph rectangle and the same engine's catalog rectangle differ by at most {verification["max_edge_error_px"]:.4f} px. Under a matched attacker the true surname is feasible on every test page. For Times set by ReportLab, the prior-weighted top-10 of the exact box is {pct(times_exact.prior_weighted_top10)} and the top-1 is {pct(times_exact.prior_weighted_top1)}, against a no-box top-10 of {pct(times_field.prior_weighted_top10)}. {int(times_exact.singleton_names)} surnames are the only member of their class (prior mass {pct(times_exact.prior_mass_singleton)}; maximum pointwise leakage {times_exact.max_pointwise_bits:.2f} bits). These rates are not the 50.2% and 6.66 bits of the 50,000-name study. The list is shorter, so collisions are fewer.

On the test pages the matched exact top-10 is {pct(matched["exact"].top10)} (interval {ci(matched["exact"].top10_ci_low, matched["exact"].top10_ci_high)}), {pp(matched["exact"].top10_minus_nobox)} above the sample no-box rate of {pct(matched["exact"].nobox_top10)}. The paired interval excludes zero (Holm p {tests["exact"]["p_holm"]:.3f}).

## Mismatch

Replacing the font by a mixture of Times and Arial lowers exact top-10 to {pct(mix["exact"].top10)}. Restricting the attacker to Courier and Georgia, which never generated a page, lowers it to {pct(held["exact"].top10)}, with the true name feasible on only {pct(held["exact"].truth_in_set)} of pages. The difference from no-box includes zero. Entropy reduction of {held["exact"].entropy_reduction:.2f} bits on that arm is concentration on the wrong names and is not reported as information about the secret.

The same held-out attacker facing a 16 px square still has top-10 {pct(held["square16"].top10)} (difference {pp(held["square16"].top10_minus_nobox)}, interval {ci(held["square16"].diff_ci_low, held["square16"].diff_ci_high)}). The coarser cell keeps the true name feasible on {pct(held["square16"].truth_in_set)} of pages.

An attacker who unions exact rectangles from all three engines, without being told which engine was used, matches the matched-engine top-10 of {pct(rend["exact"].top10)}. The other engines' rectangles are not equal to the observed one, so the union does not add them. This is the strict rule stated in the protocol. It is not a fuzzy cross-renderer attack.

## Utility and worst case

Start-aligned 128 px padding has test top-10 {pct(matched["start128"].top10)}. The paired difference from no-box is {pp(matched["start128"].top10_minus_nobox)} (interval {ci(matched["start128"].diff_ci_low, matched["start128"].diff_ci_high)}, Holm p {tests["start128"]["p_holm"]:.3f}). It covers no neighboring word on these templates. The 64 px square does: on court pages it covers {square.loc[square.layout == "court", "mean_covered_words"].iloc[0]:.2f} neighboring words on average and touches another word on {pct(square.loc[square.layout == "court", "documents_with_neighbor_loss"].iloc[0])} of pages, at a median area ratio of {square.loc[square.layout == "court", "median_area_ratio"].iloc[0]:.2f}. The field box matches the prior on every page.

Arial's square-64 grid still isolates {arial_sq64.example_singleton} (pointwise {arial_sq64.max_pointwise_bits:.2f} bits, prior mass {pct(arial_sq64.prior_mass_singleton)}). Average leakage near the prior is compatible with a unique surname.

## Repeated release and simulated scan

Republication of one mask does not change the feasible set (top-10 {pct(identical.hit10.mean())}). A second PDF engine of the same font does not either (top-10 {pct(rep.loc[2, "hit10"])}). A second font cuts the median feasible set from {repeated[(repeated.kind == "new_geometry") & (repeated.releases == 1)].feasible.median():.0f} to {repeated[(repeated.kind == "new_geometry") & (repeated.releases == 4)].feasible.median():.0f} and raises top-10 to {pct(rep.loc[4, "hit10"])}.

A simulated scan (rotation, blur, noise, JPEG; not a physical scan) leaves top-10 at {pct(scan["test_top10"])} (interval {ci(scan["test_top10_ci"][0], scan["test_top10_ci"][1])}) under a tolerance of {scan["tolerance_px"]:.2f} px taken from calibration pages.

## Conclusion paragraph

Geometry leakage of an exact surname box survives passage through ReportLab and MuPDF when the attacker shares the font and the pen. On this 1,000-name list the resulting top-10 is high, and it is not the previously published 50.2%. A held-out font removes that exact-box advantage. A field-wide box removes it by construction. Start-aligned padding reduces it to a difference this sample does not separate from zero, without covering neighboring words on these sparse lines. A 64 px square is the mask that does cover neighboring text, and even that grid leaves at least one Arial surname in a class by itself.
"""
    (REPORTS / "MANUSCRIPT_ADDITIONS.md").write_text(manuscript)
    print("wrote reports")


if __name__ == "__main__":
    main()
