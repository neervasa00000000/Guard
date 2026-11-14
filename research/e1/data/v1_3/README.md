# Tail leakage from the paper's layout boxes

This is the paper control's 50,000 alphabetic 2010 Census surnames in file order, with the Census-count prior normalized within the list. The analysis uses the retained Pillow 12.3.0 layout bounds for the six fonts and three sizes. It runs no new renders. The source geometry and reference-score hashes are in `geometry_receipts.csv`.

For each font and size, the left anchor is one pixel left of the minimum layout left offset. The padded right edge is the layout right offset plus one pixel. Class `k` is the ceiling of their difference divided by `C`. The fixed field has one class that covers every value. The known font, size, pen and baseline make the class the only name-dependent information in the published box.

`tail_per_class.csv` stores the conditional class mass, number of names, pointwise loss `-log2(mass)`, and largest name prior within each class. `tail_summary.csv` reports the class entropy, maximum pointwise loss with the associated class, min-entropy leakage and prior-mass shares with strictly fewer than 100 or 10 candidates. The pooled rows condition on the known font and size, weighting the 18 cells equally. Min-entropy leakage takes the log of the pooled success ratio after averaging the attacker's posterior guessing success over cells. The pooled maximum searches all classes and reports the winning class's mass conditional on its own font and size. Tied maxima show the first cell in harness order.

The exact analytic mean and the paper's Monte Carlo estimate use different averaging. At C=128, the analytic result is 0.076213 bits and the replayed target mean is 0.078577 bits. Both round to 0.08 bits. `control_128.csv` records the per-cell replay against archived per-target A1 scores. The no-box prior gives 14,462,534 / 243,825,142, or **5.932%** expected top-10.

## Archived exact and square-grid cases

`results_cases.csv.gz` contains multiple-release scores and lacks candidate counts. The requested full-cohort exact, 16-px and 64-px target percentages cannot be computed from that file. `archive_candidate_tails.csv` also reports the original clean A1 archive subset for DejaVu Sans and Liberation Serif at 16 px. Its three-decimal `log10_cands` distinguishes counts immediately below 10 or 100 from those thresholds. The two-font pooled rows describe only that subset.

## Reproduce

Point to the verified full Census input and the trusted retained kit cache and review arrays:

```sh
E1_CENSUS=/path/to/Names_2010Census.csv python scripts/run_tail.py \
  --geometry /path/to/kit/results/e1-full/data/cache \
  --scores /path/to/kit/review4_grouped
(cd research/e1/data/v1_3 && shasum -a 256 -c SHA256SUMS)
```

The A3 likelihood scorer and the A2 phase scorer are under `research/e1/scripts/` with the Guard validation script. The original A3 case archive remains at `research/e1/cases/posterior/a3_cases.csv.gz`. The scorers write to the configured `E1_OUTPUT` run directory. The optional third-party input downloader is `scripts/fetch_data.py`. `make all` uses the offline input verifier.
