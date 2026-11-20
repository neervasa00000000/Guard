# Coordinate-error sensitivity

This is the paper cohort: the first 50,000 alphabetic 2010 Census surnames in file order, with the Census-count prior normalized within the list, six fonts, and 12, 16 and 24 px. `scripts/run_perturb.py` does not render. It reads retained layout bounds, `geom_surnames_<font>_<size>.pkl`, one Pillow `getbbox` row per surname at anchor `ls`. The padded span is the layout right edge plus one pixel, minus the shared text start `x_L`.

Before writing `summary.csv`, the script recomputes the zero-error start-aligned classes at C = 64, 96, 128, 160, 192 and 256 and the fixed field. Those rows must match `research/e1/data/v1_3/tail_summary.csv` to `1e-9`. The run that produced this directory did.

## What is perturbed

Start-aligned padding at C = 128, 192 and 256 places the left edge at the redactor's start estimate `x_L + e` and rounds the remaining span up to a multiple of C. `e` is uniform on `{-4..+4}`, and, separately, on `{-2..+2}`. The attacker knows the true template `x_L`, so the released left edge reveals `e`, and knows that distribution. Mean bits are the expected class entropy. The maximum pointwise value is the largest `-log2(class mass)` over those shifts. Min-entropy is the log of the attacker's expected guessing success divided by the prior peak, after averaging success over `e`. The candidate share is the expected prior mass of classes with fewer than 100 surnames.

The published box uses one full-line height for every surname. A baseline error of ±2 px shifts both line edges together. A line-bound error of ±2 px changes that shared height. Neither error depends on the hidden surname, so `baseline_pm2` and `line_bounds_pm2` copy the zero-error row.

Class width is mis-set to `C-8` or `C+8` with equal probability. The attacker knows the true C and that distribution and sees the released width, not the chosen width. Where both choices emit the same width for every surname, the result is the ordinary class entropy of that width.

The fixed field is one rectangle for the whole list. A per-instance start error moves the shared anchor and shortens the shared width by the same amount, so every surname still produces the same box. Its rows are zero under every condition here. It has no class width.

Pooled rows weight font–size cells equally. `n_cells` is 1, 6 or 18. Each perturbed row repeats the zero-error metrics in the `*_e0` columns.

## Pooled result

At 12 px, and at C = 256 for every size, every condition stays at 0. The fixed field stays at 0. Vertical errors match the zero-error row in every cell. The non-zero pooled cells are below. Mean bits can move down while the worst class or the guessing advantage moves up; both columns are in `summary.csv`.

| Size | C | Condition | Mean bits | Max pointwise | Min-entropy | Prior % with < 100 names |
|---|---:|---|---:|---:|---:|---:|
| 16 | 128 | e = 0 | 0.001522 | 18.602 | 0.001632 | 0.011061 |
| 16 | 128 | start −4..+4 | 0.001868 | 18.602 | 0.002237 | 0.010212 |
| 16 | 128 | start −2..+2 | 0.001726 | 18.602 | 0.001989 | 0.010511 |
| 16 | 128 | class width ±8 | 0.002329 | 15.221 | 0.002516 | 0.007636 |
| 24 | 128 | e = 0 | 0.227115 | 8.763 | 0.320984 | 0 |
| 24 | 128 | start −4..+4 | 0.222478 | 9.311 | 0.341664 | 0 |
| 24 | 128 | start −2..+2 | 0.226320 | 9.141 | 0.346109 | 0 |
| 24 | 128 | class width ±8 | 0.216708 | 9.877 | 0.293880 | 0 |
| 24 | 192 | e = 0 | 0.001475 | 18.602 | 0.001632 | 0.010669 |
| 24 | 192 | start −4..+4 | 0.001590 | 18.602 | 0.001747 | 0.010398 |
| 24 | 192 | start −2..+2 | 0.001468 | 18.602 | 0.001533 | 0.010630 |
| 24 | 192 | class width ±8 | 0.002105 | 15.768 | 0.002536 | 0.010345 |
| all | 128 | e = 0 | 0.076213 | 18.602 | 0.115617 | 0.003687 |
| all | 128 | start −4..+4 | 0.074782 | 18.602 | 0.123785 | 0.003404 |
| all | 128 | class width ±8 | 0.073012 | 15.221 | 0.105534 | 0.002545 |
| all | 192 | e = 0 | 0.000492 | 18.602 | 0.000544 | 0.003556 |
| all | 192 | start −4..+4 | 0.000530 | 18.602 | 0.000583 | 0.003466 |
| all | 192 | class width ±8 | 0.000702 | 15.768 | 0.000846 | 0.003448 |

The 18.602-bit pointwise values are the single-surname class already in the v1.3 tail. Per-font rows are in `summary.csv`.

## Reproduce

```sh
E1_CENSUS=/path/to/Names_2010Census.csv python scripts/run_perturb.py \
  --geometry /path/to/retained/geom
(cd research/e1/data/v1_4 && shasum -a 256 -c SHA256SUMS)
```

The geometry directory is the retained `geom_surnames_<font>_<size>.pkl` cache used by `scripts/run_tail.py`. The script exits if a zero-error cell disagrees with the v1.3 tail.
