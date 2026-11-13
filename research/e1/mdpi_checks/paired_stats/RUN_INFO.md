# Run information

Inputs were read from `/private/tmp/tileseal-review4.EKJJXk`. The archived Holm script is `v5.7-ieee/new_tests_review4/scripts/w9_holm.py` and its outputs are `csv/w9_holm_cells.csv` and `csv/w9_holm_summary.csv` in the same study folder. The paper's main clean A1 cell means are in `results/e1-full/csv/e1_summary.csv`. The full original main per-target directory was excluded from the kit. The retained `review4_grouped/<list>_<font>_<size>.npz` arrays cover the same main targets and the later Table III policies. Their keys encode observation model, policy and attacker. Columns are top-1, expected top-10, bits leaked, area ratio and truth-in-set, in target order. The archived A2 exact-likelihood per-target controls are in `v5.7-ieee/new_tests_posterior/csv/phase_cases.csv.gz`. Review4 records targeted the original seed components [20261029, list index, font index, size].

The sign-flip seed is 20261119 and the bootstrap seed is 20261120. Cell streams append the comparison family index, the index of the sorted unit file and the metric index. The pooled bootstrap appends the number of cell files as its unit index. Grouped equal absolute differences use binomial sign counts, which has the distribution of independent signs on those individual targets. Low-cardinality bootstrap samples use multinomial counts at the empirical frequencies. Floating equality in the permutation tail uses a tolerance of 1e-13 times the sum of absolute differences. The log records versions, wall time and worker count.

```sh
d=research/e1/mdpi_checks/paired_stats
kit=/private/tmp/tileseal-review4.EKJJXk
p="$HOME/tileseal-t3-lm/venv/bin/python"
PYTHONDONTWRITEBYTECODE=1 "$p" "$d/control.py" "$kit" "$d" > "$d/control.log" 2>&1
VECLIB_MAXIMUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 "$p" "$d/paired.py" "$kit" "$d" --workers 4 > "$d/run.log" 2>&1
PYTHONDONTWRITEBYTECODE=1 "$p" "$d/check_pairs.py" "$kit" "$d" > "$d/alignment.log" 2>&1
PYTHONDONTWRITEBYTECODE=1 "$p" "$d/report.py" "$d"
```

[Control log](control.log) · [Run log](run.log) · [A2 alignment log](alignment.log) · [Git before](git_before.txt) · [Git after](git_after.txt)
