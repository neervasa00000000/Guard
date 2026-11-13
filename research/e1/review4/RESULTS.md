# TileSeal v5.8 review rerun

The published 16 px surname check passed in 12 font–attacker cells. The largest absolute differences were 0 in top-10 and 6.75e-14 bits. A1 uses the original summary reference. A2 uses the exact-likelihood audit reference, which includes the pen support.

## Task 1. Left-edge rerun

The table shows clean surnames at 16 px pooled over the six fonts. [Per-font results](per_font.csv), [pooled results and intervals](pooled.csv), and [paired padding-minus-64 differences](padding_minus_64.csv) cover all five lists and all sizes.

| Box model | Attacker | Policy | Top-1 | Top-10 (95% CI) | Bits (95% CI) | Median area ratio | n | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LAYOUT-BOX | A1 | exact | 19.02% | 48.27% [39.71%, 55.88%] | 6.476 [5.581, 7.217] | 1.00× | 12000 | Published condition rerun |
| LAYOUT-BOX | A1 | square-8 | 5.18% | 20.02% [18.95%, 21.10%] | 3.189 [3.042, 3.332] | 1.67× | 12000 | Published condition rerun |
| LAYOUT-BOX | A1 | square-16 | 3.09% | 13.85% [13.15%, 14.52%] | 2.089 [1.966, 2.195] | 2.67× | 12000 | Published condition rerun |
| LAYOUT-BOX | A1 | square-32 | 1.93% | 9.90% [9.50%, 10.42%] | 1.195 [1.098, 1.281] | 4.38× | 12000 | Published condition rerun |
| LAYOUT-BOX | A1 | square-64 | 1.41% | 7.62% [7.38%, 7.88%] | 0.612 [0.554, 0.664] | 10.25× | 12000 | Published condition rerun |
| LAYOUT-BOX | A1 | ink-anchored-128 | 1.39% | 6.73% [5.91%, 7.57%] | 0.190 [0.033, 0.374] | 3.45× | 12000 | Published condition rerun |
| LAYOUT-BOX | A1 | pen-anchored-128 | 0.92% | 5.68% [5.53%, 5.85%] | 0.003 [0.000, 0.007] | 3.45× | 12000 | New |
| LAYOUT-BOX | A2 | exact | 17.71% | 47.02% [39.02%, 53.63%] | 6.349 [5.523, 7.005] | 1.00× | 12000 | Published condition rerun |
| LAYOUT-BOX | A2 | square-8 | 3.98% | 16.43% [15.55%, 17.32%] | 2.512 [2.357, 2.646] | 1.67× | 12000 | Published condition rerun |
| LAYOUT-BOX | A2 | square-16 | 2.50% | 11.38% [10.98%, 11.84%] | 1.453 [1.338, 1.559] | 2.67× | 12000 | Published condition rerun |
| LAYOUT-BOX | A2 | square-32 | 1.65% | 8.15% [7.80%, 8.49%] | 0.666 [0.588, 0.737] | 4.38× | 12000 | Published condition rerun |
| LAYOUT-BOX | A2 | square-64 | 1.13% | 6.60% [6.38%, 6.85%] | 0.283 [0.236, 0.328] | 10.25× | 12000 | Published condition rerun |
| LAYOUT-BOX | A2 | ink-anchored-128 | 0.92% | 5.69% [5.53%, 5.86%] | 0.003 [0.000, 0.007] | 3.45× | 12000 | Published condition rerun |
| LAYOUT-BOX | A2 | pen-anchored-128 | 0.92% | 5.68% [5.53%, 5.85%] | 0.003 [0.000, 0.007] | 3.45× | 12000 | New |
| PIXEL-INK | A1 | exact | 23.76% | 56.39% [49.98%, 62.12%] | 7.275 [6.631, 7.836] | 1.00× | 12000 | New |
| PIXEL-INK | A1 | square-8 | 5.55% | 21.01% [19.99%, 22.04%] | 3.301 [3.142, 3.432] | 1.67× | 12000 | New |
| PIXEL-INK | A1 | square-16 | 3.16% | 14.15% [13.53%, 14.78%] | 2.141 [2.011, 2.246] | 2.69× | 12000 | New |
| PIXEL-INK | A1 | square-32 | 1.94% | 10.03% [9.63%, 10.56%] | 1.219 [1.120, 1.303] | 4.39× | 12000 | New |
| PIXEL-INK | A1 | square-64 | 1.40% | 7.69% [7.44%, 7.96%] | 0.622 [0.563, 0.674] | 10.33× | 12000 | New |
| PIXEL-INK | A1 | ink-anchored-128 | 2.01% | 9.31% [8.37%, 10.25%] | 0.952 [0.732, 1.111] | 3.50× | 12000 | New |
| PIXEL-INK | A1 | pen-anchored-128 | 0.92% | 5.68% [5.53%, 5.85%] | 0.002 [0.000, 0.005] | 3.50× | 12000 | New |
| PIXEL-INK | A2 | exact | 17.81% | 48.56% [43.83%, 53.46%] | 6.534 [6.104, 6.989] | 1.00× | 12000 | New |
| PIXEL-INK | A2 | square-8 | 3.99% | 16.45% [15.57%, 17.28%] | 2.523 [2.367, 2.671] | 1.67× | 12000 | New |
| PIXEL-INK | A2 | square-16 | 2.47% | 11.36% [10.97%, 11.80%] | 1.453 [1.339, 1.558] | 2.69× | 12000 | New |
| PIXEL-INK | A2 | square-32 | 1.67% | 8.14% [7.80%, 8.49%] | 0.669 [0.594, 0.739] | 4.39× | 12000 | New |
| PIXEL-INK | A2 | square-64 | 1.11% | 6.59% [6.34%, 6.85%] | 0.281 [0.233, 0.325] | 10.33× | 12000 | New |
| PIXEL-INK | A2 | ink-anchored-128 | 0.92% | 5.70% [5.53%, 5.88%] | 0.004 [0.001, 0.008] | 3.50× | 12000 | New |
| PIXEL-INK | A2 | pen-anchored-128 | 0.92% | 5.68% [5.53%, 5.85%] | 0.002 [0.000, 0.005] | 3.50× | 12000 | New |

For PIXEL-INK A1 at 16 px, ink-anchored padding leaked 0.952 bits, the square 64 px grid leaked 0.622 bits, and pen-anchored padding leaked 0.002 bits. Ink-anchored padding leaked more than the grid in 5 of 6 fonts.

The published-condition reruns are the LAYOUT-BOX exact and square-grid rows and 128 px ink-anchored padding. Their A2 values supersede prior-only feasible-set scoring where the earlier table used it. The PIXEL-INK and pen-anchored results are new.

## Task 2. Area and leakage

Each comparison uses the ratio of the redacted area to that model’s padded tight area. Matched policies have a larger median area ratio at most 1.10 times the smaller. The [matched-area CSV](matched_overredaction.csv) gives the comparisons for each list, size, model and attacker. All policies are in the pooled CSV.

| Policy | LAYOUT-BOX area | LAYOUT-BOX A1 bits | LAYOUT-BOX A2 bits | PIXEL-INK area | PIXEL-INK A1 bits | PIXEL-INK A2 bits |
| --- | --- | --- | --- | --- | --- | --- |
| exact | 1.00× | 6.476 | 6.349 | 1.00× | 7.275 | 6.534 |
| square-8 | 1.67× | 3.189 | 2.512 | 1.67× | 3.301 | 2.523 |
| square-16 | 2.67× | 2.089 | 1.453 | 2.69× | 2.141 | 1.453 |
| square-32 | 4.38× | 1.195 | 0.666 | 4.39× | 1.219 | 0.669 |
| square-64 | 10.25× | 0.612 | 0.283 | 10.33× | 0.622 | 0.281 |
| square-128 | 29.63× | 0.316 | 0.069 | 30.01× | 0.321 | 0.068 |
| width-grid-16 | 1.88× | 1.905 | 1.268 | 1.89× | 1.957 | 1.268 |
| width-grid-64 | 3.15× | 0.568 | 0.239 | 3.16× | 0.578 | 0.237 |
| width-grid-128 | 4.70× | 0.293 | 0.046 | 4.78× | 0.298 | 0.045 |
| ink-anchored-32 | 1.88× | 1.235 | 1.046 | 1.89× | 1.983 | 1.038 |
| ink-anchored-64 | 2.07× | 0.983 | 0.794 | 2.09× | 1.728 | 0.781 |
| ink-anchored-96 | 2.58× | 0.263 | 0.076 | 2.63× | 1.010 | 0.063 |
| ink-anchored-128 | 3.45× | 0.190 | 0.003 | 3.50× | 0.952 | 0.004 |
| ink-anchored-192 | 5.17× | 0.188 | 0.001 | 5.25× | 0.950 | 0.002 |
| ink-anchored-256 | 6.89× | 0.188 | 0.001 | 7.00× | 0.950 | 0.002 |
| pen-anchored-32 | 1.91× | 1.051 | 1.051 | 1.92× | 1.046 | 1.046 |
| pen-anchored-64 | 2.09× | 0.806 | 0.806 | 2.12× | 0.800 | 0.800 |
| pen-anchored-96 | 2.58× | 0.083 | 0.083 | 2.63× | 0.079 | 0.079 |
| pen-anchored-128 | 3.45× | 0.003 | 0.003 | 3.50× | 0.002 | 0.002 |
| pen-anchored-192 | 5.17× | -0.000 | -0.000 | 5.25× | -0.000 | -0.000 |
| pen-anchored-256 | 6.89× | -0.000 | -0.000 | 7.00× | -0.000 | -0.000 |

Matched comparisons involving padding for PIXEL-INK A1 on 16 px surnames.

| Policy A | Policy B | Area ratio A | Area ratio B | Bits B − A |
| --- | --- | --- | --- | --- |
| square-16 | ink-anchored-96 | 2.69× | 2.63× | -1.131 |
| square-16 | pen-anchored-96 | 2.69× | 2.63× | -2.063 |
| width-grid-16 | ink-anchored-32 | 1.89× | 1.89× | +0.026 |
| width-grid-16 | pen-anchored-32 | 1.89× | 1.92× | -0.911 |
| width-grid-128 | ink-anchored-192 | 4.78× | 5.25× | +0.651 |
| width-grid-128 | pen-anchored-192 | 4.78× | 5.25× | -0.298 |
| ink-anchored-32 | pen-anchored-32 | 1.89× | 1.92× | -0.937 |
| ink-anchored-64 | pen-anchored-32 | 2.09× | 1.92× | -0.682 |
| ink-anchored-64 | pen-anchored-64 | 2.09× | 2.12× | -0.929 |
| ink-anchored-96 | pen-anchored-96 | 2.63× | 2.63× | -0.932 |
| ink-anchored-128 | pen-anchored-128 | 3.50× | 3.50× | -0.950 |
| ink-anchored-192 | pen-anchored-192 | 5.25× | 5.25× | -0.950 |
| ink-anchored-256 | pen-anchored-256 | 7.00× | 7.00× | -0.950 |

The matched-area CSV contains 1922 comparisons, including the rows pooled across sizes.

## Task 3. Fig. 3 known-font and known-size baseline

This reruns variant K from the original Fig. 3 script at the requested sample size with its original scoring and seed scheme. The final two columns use the original clean 16 px pooled-size CSV for the Table VII comparison.

| List | Attacker | Grid | n | Top-1 (95% CI) | Top-10 (95% CI) | Bits (95% CI) | Clean 16 px top-10 | Clean 16 px bits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| surnames | A1 | Exact | 12000 | 18.83% [14.02%, 23.09%] | 48.84% [40.87%, 55.11%] | 6.502 [5.606, 7.229] | 13.85% | 2.089 |
| surnames | A2 | Exact | 12000 | 17.73% [13.50%, 21.17%] | 47.67% [40.28%, 52.88%] | 6.367 [5.544, 7.012] | 9.89% | 1.230 |
| surnames | A1 | 16 px | 12000 | 3.40% [3.05%, 3.62%] | 14.79% [14.19%, 15.19%] | 2.101 [1.983, 2.200] | 13.85% | 2.089 |
| surnames | A2 | 16 px | 12000 | 2.02% [1.71%, 2.35%] | 10.53% [9.83%, 11.03%] | 1.235 [1.137, 1.330] | 9.89% | 1.230 |
| words | A1 | Exact | 12000 | 47.83% [38.77%, 53.18%] | 79.21% [71.79%, 84.32%] | 6.887 [6.079, 7.376] | 38.23% | 2.539 |
| words | A2 | Exact | 12000 | 46.84% [38.16%, 52.13%] | 78.65% [71.49%, 83.40%] | 6.816 [6.036, 7.289] | 31.45% | 1.652 |
| words | A1 | 16 px | 12000 | 11.57% [10.95%, 12.46%] | 38.25% [37.53%, 39.07%] | 2.497 [2.384, 2.598] | 38.23% | 2.539 |
| words | A2 | 16 px | 12000 | 7.82% [7.38%, 8.31%] | 31.07% [30.60%, 31.49%] | 1.610 [1.497, 1.728] | 31.45% | 1.652 |

[Fig. 3 baseline CSV](fig3_baseline.csv) · [Fig. 3 target CSV](fig3_cases.csv.gz)

The expanded K rows are new estimates of the Fig. 3 baseline. They use the original feasible-set scorer, including for A2.

## Task 4. Single-thread A4

The optional A4 run was skipped. The local feasibility archive is truncated.

## Reproduction

The clean sweep and Fig. 3 ran after the published surname sanity check passed. The verification log records the rerun with the six supplied fonts. The first direct-scoring sweep was stopped after its completed units had been saved. The final sweep uses grouped geometry and was checked against the direct scorer. It completed before its outer shell emitted a post-run error caused by an edit to the wrapper during execution. Report validation confirmed all output cells.

The Fig. 3 baseline and target CSVs were reproduced with the finalized wrapper. The report validation checks target coverage in both lists.

The clean seed is `[20261029, dictionary_index, font_index, size]` and the Fig. 3 seed is `[20261110, dictionary_index, font_index]`. Percentile intervals resample six font clusters 10,000 times with seed `20261110`. Pooled means and medians weight each target equally. Leave-one-font-out bounds recompute the statistic after each omission. The area statistic is the median of per-target area ratios.

Per-font padding differences pair the same target draws and subtract the 64 px grid metric from the padding metric. For area the difference is between the two medians.

For digits the published dictionary compresses each length/first/last class to one representative string with multiplicity. The sweep renders the sampled target’s actual middle digits. Exact pen-position counts therefore apply to representative candidate geometry. When a representative misses the target, the truth earns zero hits. When the whole candidate set is empty, the entropy calculation falls back to the prior. The CSVs report `truth_in` so these model-based digit results can be identified. An exact posterior over individual digit strings is blocked by the grouped candidate representation in the supplied kit.

Pen-anchored widths round the span from the fixed anchor through the padded right edge so the box covers the target. Width-only grids snap the horizontal edges to the page grid and use the same full line vertically as padding. The line starts from the font ascent and descent, expands to cover any candidate extrema, and includes the one-pixel margin.

The container used Linux aarch64 on an Apple M4 host. Fonts were installed at the original paths after checking both the archive manifest and the study receipts.

Linux runtime versions, thread settings, font verification and wall times are in [sanity.log](sanity.log), [verification.log](verification.log), [sweep.log](sweep.log) and [fig3.log](fig3.log). FriBidi was 1.0.8. The other requested rendering versions matched.

The [published A1 controls](published_a1_controls.csv) compare each reproduced non-digit LAYOUT-BOX cell with the original CSV, including the area statistic. The [A2 controls](published_a2_controls.csv) use the exact-likelihood audit cases.

```sh
docker build -t guard-e1-review4 research/e1/review4
kit=/private/tmp/tileseal-review4.EKJJXk
mkdir -p Rerun/e1_fonts
tar -xzf Rerun/e1_fonts.tar.gz -C Rerun/e1_fonts
set -e
for mode in sanity sweep fig3 report; do
  sh research/e1/review4/run_sanity.sh "$kit" "$PWD/Rerun/e1_fonts.tar.gz" \
    "$PWD/Rerun/e1_fonts" "$mode"
done
```
