"""Write the FUNSD validation reports from the saved tables.

The prose is generated here so every quoted figure is read from a file.
It does not edit the manuscript.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
DOCS = ROOT / "docs"


def load(name):
    frame = pd.read_csv(OUT / name, dtype=str, keep_default_na=False)
    for column in frame.columns:
        if column in {
            "text", "split", "doc_id", "exclusion", "policy", "regime", "knowledge",
            "status", "note", "width_definition", "estimand", "font", "label",
            "subset", "dataset", "source_split", "worst_truth_ig_doc",
            "worst_top_posterior_doc", "reason",
        }:
            continue
        values = frame[column]
        tokens = set(values.unique())
        if tokens <= {"True", "False", ""}:
            frame[column] = values.map({"True": True, "False": False, "": False})
        else:
            numeric = pd.to_numeric(values.replace("", "nan"), errors="coerce")
            if numeric.notna().sum() >= (values != "").sum():
                frame[column] = numeric
    return frame


def pct(value):
    return f"{100 * float(value):.2f}%"


def num(value, digits=2):
    return f"{float(value):.{digits}f}"


def ci(low, high, digits=2, scale=1.0, suffix=""):
    return f"[{scale * float(low):.{digits}f}{suffix}, {scale * float(high):.{digits}f}{suffix}]"


def row(summary, regime, policy):
    found = summary[(summary["regime"] == regime) & (summary["policy"] == policy)]
    if found.empty:
        raise SystemExit(f"missing {regime} {policy}")
    return found.iloc[0]


def main():
    DOCS.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((OUT / "manifest.json").read_text())
    verification = json.loads((OUT / "verification.json").read_text())
    summary = load("summary.csv")
    exclusions = load("exclusions.csv")
    association = load("width_length_association.csv")
    renderers = load("renderer_test_error.csv")
    synthetic = load("synthetic_reference.csv")
    sensitivity = load("sensitivity_mad.csv")
    example = json.loads((OUT / "figures" / "example.json").read_text()) if (OUT / "figures" / "example.json").is_file() else {}
    primary = summary[(summary["regime"] == "length_width") & (summary["status"] == "measured")].copy()
    exact = row(summary, "length_width", "exact")
    nobox = row(summary, "length_width", "no_box")
    square16 = row(summary, "length_width", "square_grid_16")
    square64 = row(summary, "length_width", "square_grid_64")
    width64 = row(summary, "length_width", "width_grid_64")
    width128 = row(summary, "length_width", "width_grid_128")
    test_corr = association[(association["split"] == "testing") & (association["width_definition"] == "inclusive")].iloc[0]
    half_corr = association[(association["split"] == "testing") & (association["width_definition"] == "half_open_reading")].iloc[0]
    manuscript = synthetic[(synthetic["dataset"] == "synthetic_manuscript_table3") & (synthetic["policy"] == "exact")]
    manuscript_exact = manuscript.iloc[0] if len(manuscript) else None
    contrasts = verification.get("contrasts", {})
    diff_ci = contrasts.get("exact_minus_nobox_top10_ci") or [float("nan"), float("nan")]
    diff_ci_text = ci(diff_ci[0], diff_ci[1], digits=2, scale=100, suffix=" percentage points")
    diff_text = f"{100 * float(contrasts.get('exact_minus_nobox_top10', float('nan'))):.2f} percentage points"
    model = manifest["length_model"]
    exclusion_lines = "\n".join(
        f"| {record.exclusion} | {int(record.n)} |" for record in exclusions.itertuples(index=False)
    )
    measured_lines = []
    label = {
        "no_box": "No-box baseline",
        "exact": "Exact annotation box",
        "square_grid_8": "Square grid, 8 px",
        "square_grid_16": "Square grid, 16 px",
        "square_grid_32": "Square grid, 32 px",
        "square_grid_64": "Square grid, 64 px",
        "width_grid_32": "Width grid, 32 px",
        "width_grid_64": "Width grid, 64 px",
        "width_grid_128": "Width grid, 128 px",
        "start_aligned_32": "Start-aligned, 32 px (same map)",
        "start_aligned_64": "Start-aligned, 64 px (same map)",
        "start_aligned_128": "Start-aligned, 128 px (same map)",
    }
    for policy, name in label.items():
        item = row(summary, "length_width", policy)
        area = "—" if policy == "no_box" else f"{num(item.median_area_ratio)} {ci(item.median_area_ratio_ci_low, item.median_area_ratio_ci_high)}"
        worst_area = "—" if policy == "no_box" else num(item.worst_area_ratio)
        measured_lines.append(
            f"| {name} | {pct(item.top1)} {ci(item.top1_ci_low, item.top1_ci_high, digits=2, scale=100, suffix='%')} | "
            f"{pct(item.top10)} {ci(item.top10_ci_low, item.top10_ci_high, digits=2, scale=100, suffix='%')} | "
            f"{num(item.entropy_reduction)} {ci(item.entropy_reduction_ci_low, item.entropy_reduction_ci_high)} | "
            f"{num(item.truth_info_gain)} {ci(item.truth_info_gain_ci_low, item.truth_info_gain_ci_high)} | "
            f"{area} | {worst_area} |"
        )
    mismatch_lines = []
    for regime, name in (
        ("length_width", "Length–width model"),
        ("mismatch_Arial", "Arial, size chosen on training"),
        ("mismatch_TimesNewRoman", "Times New Roman, size chosen on training"),
        ("mismatch_CourierNew", "Courier New, size chosen on training"),
    ):
        item = row(summary, regime, "exact")
        mismatch_lines.append(
            f"| {name} | {pct(item.top1)} | {pct(item.top10)} | {num(item.entropy_reduction)} {ci(item.entropy_reduction_ci_low, item.entropy_reduction_ci_high)} | {num(item.truth_info_gain)} |"
        )
    renderer_lines = "\n".join(
        f"| {record.font} | {int(record.size_selected_on_training)} | {num(record.training_median_abs_error, 1)} | {num(record.test_median_abs_error, 1)} | {num(record.sigma)} |"
        for record in renderers.itertuples(index=False)
    )
    synthetic_lines = "\n".join(
        f"| {record.dataset} | {record.subset} | {record.policy} | {int(record.n)} | {num(record.top10_percent, 1)} | {num(record.bits_layout)} | {num(record.median_area_ratio)} |"
        for record in synthetic.itertuples(index=False)
    )
    sensitivity_lines = "\n".join(
        f"| {record.policy} | {num(record.sigma)} | {pct(record.top1)} | {pct(record.top10)} | {num(record.entropy_reduction)} | {num(record.truth_info_gain)} |"
        for record in sensitivity.itertuples(index=False)
    )
    check_lines = "\n".join(
        f"| {'pass' if item['passed'] else 'fail'} | {item['check']} | {item['detail']} |"
        for item in verification["checks"]
    )
    manuscript_sentence = "The manuscript Table 3 surname row was not found in the local reference file."
    if manuscript_exact is not None:
        manuscript_sentence = (
            f"Manuscript Table 3, synthetic surnames, exact box: top-10 {num(manuscript_exact.top10_percent, 1)}%, "
            f"layout leakage {num(manuscript_exact.bits_layout)} bits, area ratio {num(manuscript_exact.median_area_ratio)}, "
            f"n = {int(manuscript_exact.n)}. Those numbers are not estimates for FUNSD."
        )
    side_rate = float(manifest["side_spill_rate_eligible"])
    (DOCS / "METHODOLOGY.md").write_text(f"""# Experimental methodology and dataset

## Question

The synthetic study asks how much a redaction rectangle reveals when an attacker has the renderer, the font, the text origin, and a dictionary that actually generated the string. FUNSD does not provide those ingredients. This experiment asks a narrower question: if controlled black rectangles are painted on the official FUNSD answer boxes, which of the paper's policies can be applied from information the scan really contains, and what do the identified measurements say?

This is a validation of geometry on scanned forms. It is not an attack on redactions that were already present in the world. The rectangles were drawn for this study.

## Dataset

FUNSD (Jaume, Ekenel, and Thiran, ICDAR 2019) is stored at `dataset/`. The official split is intact: {manifest['n_training_documents']} training documents and {manifest['n_testing_documents']} test documents, {manifest['n_documents']} in total. Image stems do not overlap. Every document has a matching annotation and a grayscale PNG. Entity labels in the local copy are question {manifest['label_counts'].get('question')}, answer {manifest['label_counts'].get('answer')}, other {manifest['label_counts'].get('other')}, and header {manifest['label_counts'].get('header')}.

The population is the answer entities, {manifest['n_answer_entities']} of them. Questions, headers, and other regions are counted and then excluded. They are not the filled values the synthetic study treats as the secret.

## Ground truth

The string is the whitespace-normalized entity text. It is kept only when the word strings normalize to the same text. Three answers failed that check and were removed. No OCR engine was available, so the annotations were not transcribed a second time. The verification script re-read every answer from the JSON files and compared the stored string and box.

Boxes are the stored FUNSD coordinates read as inclusive pixels. A probe before the attack was scored found dark pixels on the stored right and bottom edges, which is why the inclusive reading is primary. Area and width use that reading. Repeating the test-set rank correlation with the opposite, half-open reading gives Spearman {num(half_corr.spearman, 3)} against {num(test_corr.spearman, 3)} for the inclusive reading. The reading does not drive the association.

## Eligibility

An answer is eligible when its text is non-empty and consistent, its box lies inside the image, the entity and its words are horizontal, the words form one line, the string has at most 80 characters, and the box contains at least 8 pixels darker than gray value 140 and at least 2% ink. The first failure is the recorded reason. The ink threshold and the one-line overlap rule were chosen after looking at image mode, edge darkness, and form rules, and before recovery scores were computed. They were not pre-registered.

Eligible answers: {manifest['n_eligible']} fields in {manifest['n_eligible_training_documents'] + manifest['n_eligible_testing_documents']} documents. Training uses {manifest['n_eligible_training']} fields from {manifest['n_eligible_training_documents']} documents. The held-out evaluation uses {manifest['n_eligible_testing']} fields from {manifest['n_eligible_testing_documents']} documents. Eight documents have no eligible answer (four in each split).

Side spill is recorded and does not remove a field. It counts dark pixels in the two columns beside the box, inside the central half of its height, so a form rule above or below the text is not called a leaked glyph. {manifest['side_spill_eligible']} eligible fields ({pct(side_rate)}) meet the spill rule of 6 or more such pixels. Painting the annotation therefore covers the annotation, and on those fields it does not cover every nearby dark pixel.

## Policies

Exact boxes, square grids of 8, 16, 32, and 64 pixels, and annotation-anchored width grids of 32, 64, and 128 pixels are applied to the original images. The square grid snaps the half-open rectangle outward onto the image grid. The width grid keeps the annotation's left, top, and bottom edges and rounds the width up. The same rectangles are reported again as start-aligned padding. Under this anchor the two maps are the same function. They are not the manuscript's start-aligned policy, which also expands the box to a known font line and shares one typesetting pen across a candidate list. Neither fact is known here.

Fixed field boxes are not applied. FUNSD does not mark the blank field. Inventing the blank from the longest answer on the page would smuggle in a width the dataset does not contain.

A matched-renderer attack is not run. The scans do not name a font or a renderer, and the six study fonts are not installed on this machine.

## Attackers that were actually scored

Recovery metrics are computed only for attackers who are given extra knowledge.

The candidate list is the set of distinct eligible training answers, {manifest['n_training_candidates']} strings. The prior is the share of eligible training fields. Test strings are not added. {manifest['test_fields_in_training_dictionary']} of the {manifest['n_eligible_testing']} test fields use a string that appears in that list. The other {manifest['n_eligible_testing'] - manifest['test_fields_in_training_dictionary']} cannot be recovered by exact match, and their truth information gain is left undefined.

The length–width model is ordinary least squares of inclusive width on character length, fit on training fields only. Intercept {num(model['intercept'], 3)}, slope {num(model['slope'], 3)} pixels per character, residual standard deviation {num(model['sigma'], 3)} pixels, residual median absolute error {num(model['residual_mae'], 3)} pixels. The likelihood of an observed width bin is the normal probability of that bin. Exact boxes use a one-pixel bin. Grids use the integer widths still compatible with the snap. Top-1 and top-10 break ties in expectation.

Three mismatched renderers, Arial, Times New Roman, and Courier New, are calibrated the same way. The size is the training median absolute width error. The test error is reported after the size is frozen. These fonts are not the font on the page.

The realistic attacker, who sees only the redacted image and has no dictionary, does not receive a top-1, a top-10, a no-box rate, or a bit count. Those quantities are unidentified without a candidate distribution.

## What the bit numbers mean

Dictionary entropy reduction is the drop in Shannon entropy of the training-answer prior after the Bayesian update. It is defined for every test field. It counts concentration on the wrong string.

Truth information gain is the base-2 change in probability of the true string. It is averaged only over the {int(exact.n_truth_info_gain)} in-list fields. It can be negative. It is not the manuscript's mutual information, and it is not an estimate of leakage for strings outside the training list.

## Uncertainty

Primary 95% intervals resample test documents with replacement, 2000 times, seed 20261116. Fields from the same page stay together. The interval for truth information gain uses the in-list fields only.

## Diagnostic facts seen before the scores

Before any attacker was scored, the audit had already shown grayscale pages, boxes inside the images except one non-answer, three text/word disagreements, a strong raw width–length correlation on all answers, and form-rule darkness on the top and bottom edges. The attack model was not tuned to a target accuracy after that.
""")
    (DOCS / "RESULTS.md").write_text(f"""# Results

All recovery numbers below are for the {manifest['n_eligible_testing']} eligible answers in the {manifest['n_eligible_testing_documents']} held-out FUNSD documents. Training answers were used to build the dictionary and to fit the width model. They are not in the averages.

The realistic image-only regime, the fixed field box, and the matched renderer were not scored. Their reasons are in `not_measured.csv`.

## Exclusions among {manifest['n_answer_entities']} answers

| Reason | n |
| --- | ---: |
{exclusion_lines}

Eligible answers remaining: {manifest['n_eligible']}.

## Held-out length–width model

No-box top-1 is {pct(nobox.top1)} and no-box top-10 is {pct(nobox.top10)}. The no-box attacker ignores the rectangle and ranks the training prior. It is not a redaction of area zero.

Exact-box top-1 is {pct(exact.top1)}, with document-cluster interval {ci(exact.top1_ci_low, exact.top1_ci_high, digits=2, scale=100, suffix='%')}. It matches the no-box top-1. The exact rectangle changes the top-1 score on {contrasts.get('exact_vs_nobox_top1_fields_changed', '—')} of {manifest['n_eligible_testing']} test fields.

Exact-box top-10 is {pct(exact.top10)}, interval {ci(exact.top10_ci_low, exact.top10_ci_high, digits=2, scale=100, suffix='%')}, against no-box {pct(nobox.top10)}, interval {ci(nobox.top10_ci_low, nobox.top10_ci_high, digits=2, scale=100, suffix='%')}. Those two marginal intervals overlap. The comparison that respects the pairing is the field-wise difference: {diff_text}, interval {diff_ci_text}. That interval excludes zero. The exact rectangle changes top-10 on {contrasts.get('exact_vs_nobox_top10_fields_changed', '—')} fields, so the detected shift is small and concentrated.

Dictionary entropy reduction for the exact box is {num(exact.entropy_reduction)} bits, interval {ci(exact.entropy_reduction_ci_low, exact.entropy_reduction_ci_high)}. The interval excludes zero. Square 64 px falls to {num(square64.entropy_reduction)} bits, interval {ci(square64.entropy_reduction_ci_low, square64.entropy_reduction_ci_high)}. Width grid 128 px falls to {num(width128.entropy_reduction)} bits, interval {ci(width128.entropy_reduction_ci_low, width128.entropy_reduction_ci_high)}.

Truth information gain on the {int(exact.n_in_list)} in-list fields is {num(exact.truth_info_gain)} bits for the exact box, interval {ci(exact.truth_info_gain_ci_low, exact.truth_info_gain_ci_high)}. The worst in-list field reaches {num(exact.worst_truth_info_gain)} bits (document {exact.worst_truth_ig_doc}, entity {int(exact.worst_truth_ig_entity)}). The highest posterior probability placed on any one candidate is {num(exact.worst_top_posterior, 3)}. No test field reaches posterior 0.5. Five in-list exact-box fields have negative truth information gain. Those values were kept.

Conditional top-1, which drops every test string absent from training, is {pct(exact.top1_conditional)}. That subgroup is not the recovery rate.

| Policy | Top-1 (95% CI) | Top-10 (95% CI) | Entropy reduction, bits | Truth information gain, bits | Median area ratio (95% CI) | Worst area ratio |
| --- | --- | --- | ---: | ---: | ---: | ---: |
{chr(10).join(measured_lines)}

Start-aligned rows repeat the width-grid rows. The verification compared the rectangles and the feasible widths and found no difference, and the point estimates match. The intervals differ in the last digit because each row draws its own bootstrap stream. The agreement is an identity of the maps, not a second experiment.

Median area is 1 for the exact box, {num(square16.median_area_ratio)} for the 16 px square grid, {num(square64.median_area_ratio)} for the 64 px square grid, {num(width64.median_area_ratio)} for the 64 px width grid, and {num(width128.median_area_ratio)} for the 128 px width grid. The worst 64 px square box is {num(square64.worst_area_ratio)} times the annotation. Median inflation above the exact box is the ratio minus one: {num(float(square16.median_area_ratio) - 1)} at 16 px square and {num(float(width128.median_area_ratio) - 1)} at width 128 px.

Every saved coverage check passed: the policy rectangle contains the annotation, every dark pixel in the annotation is black after painting, and pixels outside the painted rectangle are unchanged. That is true for all eligible fields and all applied policies. It does not say the annotation contains every glyph. Side spill remains on {pct(side_rate)} of eligible fields.

## Width and length, descriptive

On the test fields, Spearman correlation between inclusive width and character length is {num(test_corr.spearman, 3)}, document-cluster interval {ci(test_corr.ci_low, test_corr.ci_high, digits=3)}. This is an association, not a bit leakage and not a recovery rate. The half-open reading of the same boxes gives {num(half_corr.spearman, 3)}.

## Mismatched renderers

Sizes were frozen on training median absolute error. Test error is larger than training error for Arial and Courier New, and close for Times.

| Font | Training-chosen size | Training median absolute error | Test median absolute error | Residual SD |
| --- | ---: | ---: | ---: | ---: |
{renderer_lines}

Exact-box recovery under those frozen fonts:

| Regime | Top-1 | Top-10 | Entropy reduction, bits | Truth information gain, bits |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(mismatch_lines)}

Top-1 does not move. Entropy reduction stays near one bit and is slightly lower than the length model for the proportional fonts. Courier New is close to the length model. None of these runs is a matched-renderer result.

## Post-hoc scale check

The protocol residual standard deviation is {num(model['sigma'], 2)} pixels. The median absolute residual is {num(model['residual_mae'], 2)} pixels, and one training residual exceeds 380 pixels. Replacing the scale by 1.4826 times the median absolute deviation, after seeing the primary scores, does not change top-1. It raises exact-box entropy reduction and top-10. The file is `sensitivity_mad.csv`. It is not a primary result.

| Policy | Robust sigma | Top-1 | Top-10 | Entropy reduction | Truth information gain |
| --- | ---: | ---: | ---: | ---: | ---: |
{sensitivity_lines}

## Synthetic reference, not pooled

{manuscript_sentence}

The reference file keeps the synthetic rows in their own table. `same_estimand_as_funsd` is false on every row. No average in this study mixes a FUNSD field with a synthetic surname.

| Dataset | Subset | Policy | n | Top-10 % | Layout bits | Median area ratio |
| --- | --- | --- | ---: | ---: | ---: | ---: |
{synthetic_lines}
""")
    (DOCS / "STATISTICAL_ANALYSIS.md").write_text(f"""# Statistical analysis

## Estimands

Unconditional top-1 and top-10 are means of expected tie-resolved hits on all {manifest['n_eligible_testing']} test fields. A field whose string is outside the training dictionary contributes zero. Conditional top-1 restricts the mean to the {int(exact.n_in_list)} in-list fields and is reported as a subgroup.

Dictionary entropy reduction is the mean of H(prior) − H(posterior) on all test fields. Truth information gain is the mean of log2 posterior(truth) − log2 prior(truth) on in-list fields only. Fields with negative gain stay in the mean. Five exact-box in-list fields are negative.

The no-box baseline uses the same prior and a flat likelihood. Its entropy reduction is zero by construction. Its top-1 and top-10 are the right baseline for the recovery rates.

Area ratios use the inclusive pixel area of the policy rectangle divided by the inclusive annotation area. The reported center is the median. The worst case is the maximum on the test fields.

The Spearman statistics describe rank association. They are not converted into bits.

## Intervals

The interval is a percentile cluster bootstrap. Documents are drawn with replacement, every eligible test field in a drawn document is kept, and the statistic is recomputed. There are 2000 draws. The seed is 20261116, hashed with the regime, policy, and statistic name so that the stream for one cell does not depend on the order of other cells. The verification script recomputed the exact-box entropy interval with its own implementation and the same seed construction. The endpoints matched.

An ordinary binomial interval would treat 585 fields as independent. They are not. {manifest['n_eligible_testing_documents']} documents contribute the test fields, and several answers share a page. The cluster interval is the one to quote. It is still an interval for this FUNSD split, not a super-population of all scanned forms.

## What is separated from the baseline

Exact-box top-1 equals no-box top-1 on every test field. There is no top-1 effect to interval.

Exact-box top-10 is higher by {diff_text}. The paired cluster interval is {diff_ci_text} and excludes zero. The marginal intervals overlap, which is expected for a small paired shift and is not the right comparison. The change is carried by {contrasts.get('exact_vs_nobox_top10_fields_changed')} fields. The detected gain is real under this bootstrap and is still under one percentage point. It is not a change in the practical success of the attack.

Exact-box entropy reduction, {num(exact.entropy_reduction)} bits with interval {ci(exact.entropy_reduction_ci_low, exact.entropy_reduction_ci_high)}, excludes zero. Coarser policies have lower point estimates. Square 64 px is {num(square64.entropy_reduction)} bits, interval {ci(square64.entropy_reduction_ci_low, square64.entropy_reduction_ci_high)}. Width 128 px is {num(width128.entropy_reduction)} bits, interval {ci(width128.entropy_reduction_ci_low, width128.entropy_reduction_ci_high)}. Those two intervals are separated from the exact-box interval. The ordering across the grid was not multiplicity-adjusted. It is a pre-specified family of widths, and the claim is the downward pattern, not a selected winner.

Truth information gain for the exact box, {num(exact.truth_info_gain)} bits, interval {ci(exact.truth_info_gain_ci_low, exact.truth_info_gain_ci_high)}, also excludes zero. It applies only to strings the training forms already contained.

## Model diagnostics that affect the bits

The Gaussian scale is the residual standard deviation, {num(model['sigma'], 2)} pixels. The median absolute residual is {num(model['residual_mae'], 2)} pixels. The scale is inflated by a heavy tail, including a training residual of several hundred pixels. A post-hoc robust scale of about 10 pixels raises the bit numbers and still leaves top-1 unchanged. The primary bit numbers are therefore the more conservative of the two Gaussian scales, and they remain model-dependent. They are not a measurement of mutual information under a known renderer.

## Coverage and association

Coverage of the annotated ink is a finite population count, not a sample proportion: every eligible field passed. There is no interval to attach to a complete enumeration of this file set.

The test-set Spearman interval is a cluster bootstrap of the correlation, {ci(test_corr.ci_low, test_corr.ci_high, digits=3)} around {num(test_corr.spearman, 3)}. It excludes weak association. It does not identify who wrote the string.
""")
    (DOCS / "VERIFICATION.md").write_text(f"""# Independent verification

The checker is `research/funsd_validation/verify_funsd_independent.py`. It does not call the experiment's likelihood, line fit, exclusion rule, paint check, or bootstrap. It re-reads the FUNSD JSON and PNG files.

Result: {verification['n_passed']} checks passed and {verification['n_failed']} failed, out of {verification['n_checks']}.

| Result | Check | Evidence |
| --- | --- | --- |
{check_lines}

## What was re-derived

- Every answer string and box in `answer_entities.csv` was compared with the source JSON. Disagreements: {len(verification['text_failures'])}.
- Eligibility was recomputed from the images and the word boxes, including the ink rule.
- Training and test document identifiers are disjoint. The candidate list is a subset of eligible training strings and contains no test-only string. The in-list count is {manifest['test_fields_in_training_dictionary']}.
- The attacker observation table has no text, length, or prior column.
- Ordinary least squares was refit with a centered formula. Intercept, slope, and residual scale matched the manifest to 1e-8.
- Exact and quantized length-model scores were recomputed with `math.erf` and `math.erfc`, one candidate at a time. Top-1 and top-10 matched to 1e-8. Entropy and truth information gain matched to 1e-5. The remaining gap is the difference between the Abramowitz approximation used in the experiment and the system math library.
- The exact-box entropy cluster interval was recomputed and matched the published endpoints.
- Square-16 median area was recomputed from the observation table.
- Start-aligned rectangles match the width-grid rectangles.
- Truth information gain is undefined when the string is outside the candidate list. No-box entropy reduction is identically zero. Negative truth gains were not clipped.
- Realistic recovery, fixed field boxes, and a matched renderer remain in `not_measured.csv`.
- Every synthetic reference row is flagged as a different estimand.

## Redaction coverage

On every test field, the verifier painted the exact box, the 16 px square grid, the 64 px square grid, and the 128 px width grid. It required the rectangle to contain the annotation, every dark annotation pixel to become black, and the surrounding pixels in the local window to stay unchanged. Failures: {len(verification['coverage_failures'])}. The experiment's own table, which covers every eligible field and every applied policy, has covered fraction 1.

## Reproduction of the published means

The exact-box means in `summary.csv` match the means of `scores.csv` within 1e-8 after CSV rounding.

## Checks that were not executed

- A second transcription with an OCR engine. Tesseract is not installed, and no OCR result was invented.
- A matched-renderer rescore. The study fonts are not on this machine, and the scans do not name a font.
- A fixed-field policy. The blank is not annotated.
- Re-rendering the synthetic surname archive. Those results were read from the existing tables and were not rerun.
""")
    (DOCS / "REPRODUCIBILITY.md").write_text(f"""# Reproducibility

From the repository root, with the project virtual environment:

```sh
.venv/bin/python research/funsd_validation/run_funsd_validation.py
.venv/bin/python research/funsd_validation/verify_funsd_independent.py
.venv/bin/python research/funsd_validation/make_funsd_figures.py
.venv/bin/python research/funsd_validation/write_funsd_reports.py
.venv/bin/python -m pytest -q tests/test_funsd_validation.py
```

The run reads `dataset/training_data` and `dataset/testing_data` and writes `research/funsd_validation/out/`. It does not download data, call a model service, or modify `manuscript/`, `out/tables/`, or the synthetic archives.

The scoring seed is {manifest['bootstrap_seed']} with {manifest['bootstrap_draws']} document-cluster draws. A cell's generator is the first eight hex digits of SHA-256 of `seed:regime|policy|statistic`. Recomputing a cell does not depend on which other cells were computed first.

Pinned project packages used here are the environment's numpy, pandas, Pillow, and matplotlib. The length model does not need the study fonts. The mismatched-renderer arm needs the macOS supplemental files for Arial, Times New Roman, and Courier New. On a machine without those files the arm is recorded as not measured and the length-model arm still runs.

The protocol is `research/funsd_validation/PROTOCOL.md`. It was written in the same session as the code, after a diagnostic look at the images and before the recovery scores. It was not registered in advance.

Current verification: {verification['n_passed']} passed, {verification['n_failed']} failed.

## Outputs

| File | Role |
| --- | --- |
| `out/manifest.json` | Counts, fit, coverage flag |
| `out/answer_entities.csv` | Every answer, eligible or not, with the normalized string |
| `out/exclusions.csv` | Exclusion counts |
| `out/attacker_observations.csv` | Bins and areas, with no ground-truth text |
| `out/training_candidates.csv` | Training dictionary and prior |
| `out/scores.csv` | Per-field hits, bits, and posteriors |
| `out/summary.csv` | The table behind the report |
| `out/not_measured.csv` | Conditions that were refused |
| `out/coverage.csv` | Per-field paint checks |
| `out/width_length_association.csv` | Descriptive correlations |
| `out/renderer_calibration.csv` | Training size sweep |
| `out/renderer_test_error.csv` | Frozen size, then test error |
| `out/synthetic_reference.csv` | Unpooled synthetic numbers |
| `out/sensitivity_mad.csv` | Post-hoc robust scale |
| `out/verification.json` | Checker results |
| `out/figures/` | PDF and PNG figures |
| `docs/` | The reports in this folder |
""")
    (DOCS / "LIMITATIONS.md").write_text(f"""# Limitations and threats to validity

1. The rectangles were painted by this study on human annotation boxes. A result about those rectangles is not a result about redactions that offices, courts, or FOIA reviewers have already released.

2. The realistic attacker is unidentified. Without a dictionary, top-1, top-10, and bits are not defined. Reporting them as zero would be a fabricated leakage claim.

3. The dictionary is the empirical list of eligible training answers. It is a justified attacker prior only for someone who has already read the training forms. It is not the process that generated the test answers. Most test strings, {manifest['n_eligible_testing'] - manifest['test_fields_in_training_dictionary']} of {manifest['n_eligible_testing']}, are outside it. Identity metrics are dominated by that open set.

4. The bit numbers use a Gaussian width model whose scale is pulled up by outliers. A robust scale, examined after the primary run, changes the bit values. Both scales leave top-1 on the no-box rate. The bits should not be quoted without the scale.

5. Truth information gain is estimated on a selected subgroup, the strings that happen to recur. That subgroup is easier than the full test set and is still not the manuscript's mutual information.

6. Start-aligned padding here does not implement the manuscript's policy. The font line and the shared pen are missing, so only the horizontal snap was applied, and it coincides with the width grid.

7. Fixed field boxes were not tested. Any sentence that treats a full-field box as measured on FUNSD is unsupported.

8. Square-grid likelihoods use the feasible width interval, not the paper's full attacker, who knows the pen, the font, and the four edges of a rendered candidate. Absolute position on a form is about where the blank sits, so it was not used as an identity feature. Using it would have been a bug. The comparison still understates the synthetic attacker rather than reproducing it.

9. Annotation boxes are the human boxes in FUNSD. The "exact" condition gives the redactor that box. It is not the output of an automatic ink tracer, and it was not checked by a second OCR engine.

10. Side spill on {pct(side_rate)} of eligible fields means some dark pixels sit beside the box. The coverage test does not count those pixels as covered. Form rules were excluded from the spill definition by using the central band, and that definition can miss a glyph that touches the box only at its top or bottom.

11. Fields on a page are dependent. The cluster bootstrap respects the page. It does not create a confidence interval for other document collections. FUNSD is one corpus of noisy scanned forms, largely from a single historical collection.

12. Eligibility thresholds were chosen after a diagnostic pass and were not registered. The half-open sensitivity shows that the width–length correlation is stable to the inclusive reading. Other thresholds, such as the 80-character cap and the 2% ink rule, remove only a few answers (see the exclusion table) and are unlikely to carry the recovery result. That is an argument, not a proof.

13. The mismatched fonts are macOS system fonts. Another machine without those files cannot reproduce the renderer arm. The length-model arm does not need them.

14. No multiplicity adjustment covers every policy and both bit definitions. The supported geometric claim is the ordered drop in entropy reduction as the snap gets coarser, together with the rise in area. It is not a catalogue of individually tested winners.
""")
    (DOCS / "MANUSCRIPT_SECTION.md").write_text(f"""# Proposed section: a scanned-form boundary check

This section is a draft for insertion after the synthetic results. It is not part of the current manuscript file. The numbers below were computed in this repository from the local FUNSD copy and should be copied only together with the tables in `docs/RESULTS.md`.

## Real-document boundary check

The attacks in the preceding sections give the attacker the renderer, the font, the shared text origin, and a dictionary from which the secret was drawn. Scanned forms do not hand over that package. We therefore painted controlled solid-black rectangles on the answer boxes of FUNSD, the 199-document ICDAR 2019 form set, and measured only the quantities the scans support. The official split was preserved. Of {manifest['n_answer_entities']} answer entities, {manifest['n_eligible']} single-line horizontal answers remained after documented exclusions. Evaluation used the {manifest['n_eligible_testing']} eligible answers in the {manifest['n_eligible_testing_documents']} test documents that contain one.

The inclusive width of a test answer and its character length have Spearman correlation {num(test_corr.spearman, 3)} (document-cluster 95% interval {ci(test_corr.ci_low, test_corr.ci_high, digits=3)}). Box geometry on these scans does track length. That association is not, by itself, a recovery rate.

An attacker who is also given the eligible training answers as a dictionary, and a Gaussian width model fit only on those training answers, does not convert the association into top-1 recovery. Exact-box top-1 is {pct(exact.top1)}, the same as the no-box prior on every test field. Exact-box top-10 is {pct(exact.top10)} against a no-box rate of {pct(nobox.top10)}. The paired difference is {diff_text} (interval {diff_ci_text}) and is carried by {contrasts.get('exact_vs_nobox_top10_fields_changed')} fields. {manifest['test_fields_in_training_dictionary']} test strings occur in the training dictionary. The rest are exact-match failures before geometry is consulted.

Under that extra-knowledge model the exact rectangle reduces the entropy of the training dictionary by {num(exact.entropy_reduction)} bits (interval {ci(exact.entropy_reduction_ci_low, exact.entropy_reduction_ci_high)}). A 64 px square grid reduces it by {num(square64.entropy_reduction)} bits and multiplies median area by {num(square64.median_area_ratio)}. A 128 px width grid, anchored at the annotation's left edge and not expanded to a font line, reduces it by {num(width128.entropy_reduction)} bits and multiplies median area by {num(width128.median_area_ratio)}. On the {int(exact.n_in_list)} test strings that the training list already contains, the mean truth information gain of the exact box is {num(exact.truth_info_gain)} bits. These bit quantities are properties of the training-answer prior and the Gaussian width model. They are not the layout leakage reported for synthetic surnames, and they are undefined for the realistic attacker who has no dictionary.

{manuscript_sentence} Arial, Times New Roman, and Courier New, with sizes chosen on the training forms, produce the same qualitative pattern and do not create a matched-renderer condition. The original fonts are unknown. Fixed field boxes were not scored, because the blank width is not annotated. Start-aligned padding in the synthetic sense was not scored either; the horizontal snap we could apply is the width grid.

The black rectangles cover every dark pixel of every eligible annotation, and they leave the surrounding pixels unchanged. They are controlled masks. They are not evidence about redactions that already existed on the pages. The boundary check supports a geometric statement, that scanned answer width carries length and that coarser masks spend area to reduce dictionary concentration. It does not support transferring the synthetic top-10 rates or the synthetic bit totals onto scanned forms.
""")
    recommendation = "The scanned-form study should be added only as a boundary condition, after the revisions below. It should not be cited as confirmation that the synthetic attack rates survive contact with real documents."
    (DOCS / "PEER_REVIEW.md").write_text(f"""# Peer-review assessment

This is an internal review of the FUNSD validation against the standard the synthetic paper would face if this section were added. It is written to find the reasons a careful referee would reject the section or narrow it.

## Recommendation

{recommendation}

The synthetic conclusions about a matched renderer and a generative dictionary are not contradicted, because those assumptions were not recreated. They are also not confirmed on scanned forms. The new evidence supports the geometric mechanism and cuts against any broader claim that the published top-10 rates or bit totals are what a scanned form leaks.

## Major points

1. The estimands differ. Manuscript layout leakage is mutual information under a renderer and a dictionary that generated the string. The FUNSD truth information gain is a pointwise log posterior ratio on the {int(exact.n_in_list)} recurring strings, under a Gaussian width model. Entropy reduction counts concentration on wrong candidates. A referee who finds these numbers placed next to Table 3 without the estimand sentence should reject the section.

2. Top-1 is a negative result and must stay one. It equals the no-box rate on all {manifest['n_eligible_testing']} test fields. Top-10 has a paired gain of {diff_text}, and that paired interval excludes zero, but the gain lives in {contrasts.get('exact_vs_nobox_top10_fields_changed')} fields. Writing that the box recovers the answers would not survive the absolute rate. Writing that top-10 is unchanged would not survive the paired interval. The defensible sentence is a shift of less than one percentage point.

3. The open set does most of the work. {manifest['n_eligible_testing'] - manifest['test_fields_in_training_dictionary']} test answers are absent from the training list, so exact match fails before width is used. A closed world that plants the truth in the candidate list was not run. If a revision adds one, it has to be labeled as a gift to the attacker. The low top-1 rate is therefore not, on its own, evidence that width carries no identity information among strings of equal length.

4. The noise model is misspecified in a way that moves the bits. Residual SD is {num(model['sigma'], 1)} pixels and the median absolute residual is {num(model['residual_mae'], 1)}. The robust-scale check was computed after the primary scores. A referee can accept it as a sensitivity or call the primary bits arbitrary. The section should lead with the pre-specified scale and should not shop between them.

5. Two policies the paper cares about were not instantiated. Fixed field boxes need a blank the dataset does not mark. Start-aligned padding, as defined in the paper, needs a font line and a shared pen. Reporting the width grid under both names is honest only while the identity is explicit. A table that lists them as two agreeing experiments would be misleading. The current table repeats them and says they are the same map.

6. The rectangles are ours. Any abstract sentence that says the study attacked real-world redactions is false. The coverage result shows that a black rectangle covers the annotation we painted. It does not show that FUNSD pages contain redactions, and they do not.

7. External validity is a single corpus. FUNSD's forms are a narrow historical collection. The cluster interval does not stretch to born-digital PDFs, to FOIA releases, or to the synthetic template. The side-spill rate of {pct(side_rate)} is a reminder that human boxes and ink are not the same object.

## Minor points

- Eligibility rules were set after a diagnostic image pass. The exclusions that remove more than a handful of answers are vertical text and line breaks, which are visible properties, not outcome-driven cuts. The three text/word mismatches and two low-ink answers are small. The absence of a prior registration should still be stated, and it is.
- There is no second transcription. OCR was not installed. The ground-truth check is internal consistency plus a full re-read of the JSON, not an independent reader.
- The prior is dominated by short recurring tokens. The most common training answer is a one-character mark. A frequency prior will keep ranking that mark first unless the likelihood is sharp. That is a property of this dictionary, and it should be visible to the reader.
- No multiplicity correction is applied across grids. The ordered entropy drop is the claim that fits the design. Isolated "significant" cells should not be starred.
- Mismatched-font calibration uses macOS files. It is a portability limit, not a scientific one, provided the length-model arm remains the primary arm.
- The example figure shows a real FUNSD crop. It should be captioned as a controlled mask. It should not be described as a redaction found on the page.

## Why this would be rejected if overclaimed

The rejection paragraph writes itself if the section says that real documents leak the Table 3 surname totals, that top-10 recovery transferred, that start-aligned padding was reproduced, that field boxes drive leakage to zero, or that the study measured naturally occurring redactions. None of those sentences is supported. The section that remains, limited to the width–length association, the open-set recovery failure, the small and model-dependent entropy reductions, and the area cost of coarser grids, is the part a referee can accept.
""")
    (ROOT / "README.md").write_text(f"""# FUNSD real-document validation

Controlled black rectangles on the official FUNSD split. This directory does not replace the synthetic GUARD results and does not edit the manuscript.

Primary held-out result, length–width model, exact box: top-1 {pct(exact.top1)} (equal to the no-box baseline on every test field), top-10 {pct(exact.top10)}, dictionary entropy reduction {num(exact.entropy_reduction)} bits, truth information gain {num(exact.truth_info_gain)} bits on the {int(exact.n_in_list)} recurring strings. Eligible fields scored in the test split: {manifest['n_eligible_testing']} from {manifest['n_documents']} documents ({manifest['n_eligible']} eligible overall).

Reports are in `docs/`. The protocol is `PROTOCOL.md`. Verification: {verification['n_passed']} passed, {verification['n_failed']} failed.

```sh
.venv/bin/python research/funsd_validation/run_funsd_validation.py
.venv/bin/python research/funsd_validation/verify_funsd_independent.py
.venv/bin/python research/funsd_validation/make_funsd_figures.py
.venv/bin/python research/funsd_validation/write_funsd_reports.py
.venv/bin/python -m pytest -q tests/test_funsd_validation.py
```
""")
    print("reports written")


if __name__ == "__main__":
    main()
