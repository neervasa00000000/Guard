# Independent posterior check

The archived toy replay reproduced prior entropy **2.831 bits** and A2 exact mutual information **2.423 bits** at printed precision. [Sanity replay](published_replay.log)

## Toy universes

The independent code enumerates starts and jitter draws. Exact integer counts and rational priors give posterior weights and observation masses before evaluating logarithms. A1 includes the known start in each observation. A3 enumerates every copy at the same start. T2 has identical vertical offsets for every candidate, so the vertical jitter factor has no effect on any posterior. Its vertical outcomes are marginalized using their full multiplicity.

The adapter calls the unchanged `Cell.feasible`, `metrics` and `bucket_transform` in `results/e1-full/scripts/e1lib.py`, the unchanged `scores` in `new_tests_posterior/scripts/phase_exact.py`, and the unchanged jitter count `cnt` in `new_tests_review3/scripts/d1_exact.py`. It supplies inclusive start counts using the interval formula in `phase_exact.py` and `a3_exact.py`. It uses `Geometry.horizontal` in `research/e1/review4/geometry.py` for the full-line start-padding policy.

T1 uses prior weights 6 through 1. T2 uses NumPy seed 1 and Zipf exponent 1. T3 uses descending prior weights 8 through 1. T4 uses descending weights 10 through 1, a fixed anchor at the minimum tight left edge, and line offsets −15 and 6 for full-line cells. The [toy CSV](toy_comparison.csv) records every configuration, its exact mutual information and the paired Equation 2 checks at the three sample sizes.

| Test | Configurations | Max per-box entropy difference | Max Eq. 2 difference | Max mutual information difference | Pass |
|---|---:|---:|---:|---:|---|
| T1 | 6 | 8.88e-16 | 8.88e-16 | 2.22e-16 | PASS |
| T2 | 15 | 5.11e-15 | 1.78e-15 | 1.55e-15 | PASS |
| T3 | 2 | 4.44e-16 | 4.44e-16 | 0 | PASS |
| T4 | 16 | 6.66e-16 | 8.88e-16 | 4.44e-16 | PASS |

Equation 2 uses seeded samples of observation boxes from the exact marginal distribution. The difference from exact mutual information can fluctuate as the sample grows.

| Samples | Mean absolute Equation 2 minus exact mutual information |
|---:|---:|
| 100 | 0.023535 bits |
| 1,000 | 0.007987 bits |
| 10,000 | 0.001867 bits |

## Hand check

T1, A2, 16-px grid. The common padded vertical interval [51,63) snaps to [48,64). For horizontal observation [0,32), floor((x − 1)/16) × 16 = 0 gives starts 1 through 16. The right edge requires 17 ≤ x + width + 1 ≤ 32. Intersect those two integer intervals and divide the count by 64. Multiply by the prior and divide by the total joint mass.

| Entry | Width | Prior | Starts | Likelihood | Joint probability | Posterior |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 10 | 2/7 | 11 | 11/64 | 11/224 | 33/127 |
| 2 | 11 | 5/21 | 12 | 3/16 | 5/112 | 30/127 |
| 3 | 13 | 4/21 | 14 | 7/32 | 1/24 | 28/127 |
| 4 | 17 | 1/7 | 14 | 7/32 | 1/32 | 21/127 |
| 5 | 17 | 2/21 | 14 | 7/32 | 1/48 | 14/127 |
| 6 | 29 | 1/21 | 2 | 1/32 | 1/672 | 1/127 |

The sum of the joint column is 127/672. Substituting the posterior column in −Σ p log₂ p gives **2.312942195 bits**.

## Published surname targets

The first 200 archived targets use DejaVu Sans at 16 px. The independent scorer recomputes all candidate bounds with `font.getbbox(word, anchor='ls')` using Pillow 12.3.0 and RAQM, then enumerates the pen range for A2. Every target box was checked against the archive. A1 uses archived residuals rounded to four decimal places. A2 uses archived exact-likelihood residuals at full precision. [Case results](real_comparison.csv)

| Attacker | Grid | Targets | Max absolute difference (bits) | Mismatches |
|---|---:|---:|---:|---:|
| A1 | 1 | 200 | 4.99520806e-05 | 0 |
| A1 | 16 | 200 | 4.99087641e-05 | 0 |
| A2 | 1 | 200 | 5.32907052e-15 | 0 |
| A2 | 16 | 200 | 1.95399252e-14 | 0 |

## Three-line summary

- 39 toy configurations passed the 1e-9-bit comparison.
- Maximum toy per-box difference was 5.11e-15 bits.
- 0 mismatches in 800 real-target comparisons at stored precision.

[Independent code](posterior.py) · [Adapter](adapter.py) · [Versions and command](run.log) · [Git before](git_before.txt) · [Git after](git_after.txt)

```sh
sh research/e1/mdpi_checks/posterior_toy/run.sh > research/e1/mdpi_checks/posterior_toy/run.log 2>&1
```
