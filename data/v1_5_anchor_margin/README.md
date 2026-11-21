# Anchor-margin sweep

Exact enumeration of all 50,000 prior-weighted Census surnames, 18 font-size cells, five margins, five class widths plus the field, and four error conditions. 2160 summary rows; 15216 class rows. All zero-margin clean class masses/counts/pointwise bits match tail_per_class.csv exactly; 432 summary checks agree within 1e-12. All 5400 checks against the existing run_perturb.py error-channel functions pass within 1e-11.

This analysis reuses receipt-matched retained geometry, including Noto Sans; it does not claim a fresh Noto render. No names, fonts or raw geometry are redistributed. Full-line heights come from archived renderer metrics. Exact population quantities have no target-sampling confidence interval; seed and bootstrap defaults are recorded, but no bootstrap is performed.

The anchor is x_L - m, so m=0 is the paper policy. Start errors are visible in the released anchor and are conditioned on, as in run_perturb.py. Width errors are latent, so the two width channels are marginalized. A field always has one candidate class. Safety margins do not establish target containment under positive start errors.

Area quantiles are prior-weighted, unlike the earlier sampled area summaries. extra_area_vs_m0 is the expected fractional area increase paired by name and error draw. n_singletons is the conditional expected number of singleton classes for start-error rows. mass_lt10/mass_lt100/singleton_mass are fractions, not percent.

Run from repository root: `.venv/bin/python -B scripts/run_anchor_margin.py`. Provide the hash-verified Census CSV and retained geometry at the paths in config.json. No previous outputs are overwritten.

| Margin px | C px | Mean bits, equal-weight 18 cells | Worst pointwise bits | Mean extra area % |
|---:|---:|---:|---:|---:|
| 0 | 64 | 0.645002 | 18.601528 | 0.0000 |
| 0 | 96 | 0.296121 | 18.601528 | 0.0000 |
| 0 | 128 | 0.076213 | 18.601528 | 0.0000 |
| 0 | 192 | 0.000492 | 18.601528 | 0.0000 |
| 0 | 256 | 0.000000 | 0.000000 | 0.0000 |
| 0 | 0 | 0.000000 | 0.000000 | 0.0000 |
| 2 | 64 | 0.666401 | 17.772483 | 2.4019 |
| 2 | 96 | 0.311039 | 17.772483 | 0.8354 |
| 2 | 128 | 0.082998 | 15.479999 | 0.1417 |
| 2 | 192 | 0.000559 | 17.772483 | 0.0005 |
| 2 | 256 | 0.000000 | 0.000000 | 0.0000 |
| 2 | 0 | 0.000000 | 0.000000 | 1.4793 |
| 4 | 64 | 0.686480 | 15.479999 | 5.1133 |
| 4 | 96 | 0.330034 | 15.479999 | 1.8446 |
| 4 | 128 | 0.090774 | 15.479999 | 0.3161 |
| 4 | 192 | 0.000911 | 15.479999 | 0.0036 |
| 4 | 256 | 0.000000 | 0.000000 | 0.0000 |
| 4 | 0 | 0.000000 | 0.000000 | 2.9586 |
| 8 | 64 | 0.717324 | 15.234194 | 13.3167 |
| 8 | 96 | 0.361413 | 15.234194 | 3.8629 |
| 8 | 128 | 0.105654 | 14.512267 | 0.6927 |
| 8 | 192 | 0.001058 | 15.234194 | 0.0048 |
| 8 | 256 | 0.000000 | 0.000000 | 0.0000 |
| 8 | 0 | 0.000000 | 0.000000 | 5.9172 |
| 16 | 64 | 0.779842 | 15.479999 | 29.1765 |
| 16 | 96 | 0.430993 | 14.237162 | 10.4706 |
| 16 | 128 | 0.167593 | 15.479999 | 2.6552 |
| 16 | 192 | 0.001687 | 13.750462 | 0.0104 |
| 16 | 256 | 0.000000 | 0.000000 | 0.0000 |
| 16 | 0 | 0.000000 | 0.000000 | 11.8345 |
