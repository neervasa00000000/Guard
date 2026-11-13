# All runs summary

## A — number audit

Done from the printed PDF. The v6.1 `.tex` file was NOT FOUND.

Output: `research/e1/mdpi_checks/number_audit/NUMBER_AUDIT.md`

- 48 checked rows: 34 MATCH, 4 ROUNDING, 7 MISMATCH, 3 NO SOURCE FOUND.
- The 4.25 and 4.50 point padding gaps match the rerun’s own 64 px cells, 198/400 in both fonts, not Table V’s 199/400 and 200/400.
- Jitter at 24 px is 0.275 to 0.567 bits in `d2jit_pooled.csv`. Table X has no jitter row, and that file has no 16 px surname row.
- Abstract 3.8 million is 3,762,000. Surname 128 px median area is 3.358×, from a box of height ascent + descent + 2.
- Printed 38.0%, 9.4%, and 0.71 bits in Sec. IV-E do not match the font-cluster file (38.167%, 8.333% pooled, 0.571 bits).

## B — start-aligned padding

Done. The Table IV and Table X controls passed.

Output: `research/e1/review4/a3_start/RESULTS.md`

- Shifted copies changed top-10 by +0.000 to +0.000 points and leakage by +0.00000 to +0.00000 bits.
- Harder sets changed top-10 by +0.000 to +0.000 points and leakage by +0.00000 to +0.00000 bits.
- Jitter changed top-10 by +0.000 to +1.000 points and leakage by +0.00000 to +0.28121 bits.
- A new font or size changed top-10 by +0.000 to +2.750 points and leakage by +0.00099 to +0.47108 bits.
- A mixed renderer changed top-10 by +0.000 to +0.150 points and leakage by +0.00003 to +0.01401 bits.

## C — posterior check

Done. The toy replay reproduced prior entropy 2.831 bits and A2 exact mutual information 2.423 bits.

Output: `research/e1/mdpi_checks/posterior_toy/POSTERIOR_CHECK.md`

- 39 toy configurations passed at a maximum per-box difference of 5.11e-15 bits.
- Equation 2 moved toward exact mutual information: mean absolute gaps 0.023535, 0.007987, and 0.001867 bits at 100, 1,000, and 10,000 samples.
- The hand-checked T1 box has posterior entropy 2.312942195 bits.
- 800 real-target comparisons had 0 mismatches. The largest A1 difference was 4.995e-5 bits.
- The largest A2 difference was 1.954e-14 bits.

## D — paired tests

Done. The archived Holm table reproduced: 25 families of 18 cells.

Output: `research/e1/mdpi_checks/paired_stats/PAIRED_STATS.md`

- Surnames, layout, A1, top-10 Holm: exact>8, 8>16, and 16>32 stay 18 of 18.
- The same family: 32>64 moves from 10 to 18 of 18, and padding<64 px moves from 2 to 9 of 18.
- Words, layout, A1, top-10 Holm: 32>64 moves from 9 to 18 of 18, and padding<64 px moves from 3 to 12 of 18.
- A published per-target tie-break seed was NOT FOUND, so McNemar was not run.
- Stored A2 scores matched 432,000 layout records, with hit error 0 and maximum bits error 7.46e-13.
