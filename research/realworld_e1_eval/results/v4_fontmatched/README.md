# Available-font attacker comparison

All numbers below come from this run’s summary.csv. This is the user-authorized available-font subset, with additional explicit exclusions where no independent context geometry exists or the pinned renderer fails. It is not a full-cohort replication.

The font-known arm uses neighbour font metadata and a locally available matching font name. Matching a font name does not establish equality of source font binaries/builds. Point sizes are converted to horizontal page pixels using page metadata. The renderer-mismatch arm uses Pillow BASIC instead of RAQM.

The font-estimated arm is one explicitly specified **anonymous-geometry baseline**, not an optimal font-recognition attack: it uses no visible word identities, character counts, pixels or font names. It compares width/height quantiles with 512 fixed prior-weighted Census probes per candidate font/size. Source context cells can contain several words, so the probe width distribution can be misspecified. Accuracy is strict equality to the neighbour modal font identity; true identities outside the regular six-font bank count incorrect.

All six study fonts, including the recovered hash-matched Noto Sans binary, are rendered at the fixed sizes and the observed context size. Native context fonts are matched by embedded identity, including Type 1 fonts where available; this does not verify equality to the document’s original font build. The generic arm is unchanged v2 per-token scoring on the same paired tokens, with its original pooled calibration tolerance.

Each other arm uses the original held-out page split, restricted to common usable DocLayNet calibration targets. FUNSD supplies no font metadata. Tolerances are the smallest integer symmetric edge slack reaching 95% exact-box truth-in, then frozen across policies. Padding and empty-set fallback retain the v2 feasibility/scoring convention. CIs are 10,000 page-cluster percentile draws, seed 20261121.

The first-1000 field row includes only targets in that bounded list and uses its renormalized prior, as v2 does; its n and prior differ from the full-list rows.

| Attacker | Policy | n | Tolerance px | Calib truth-in % | Truth-in % [95% CI] | Top-1 % [95% CI] | Top-10 % [95% CI] | Attacker performance (bits) [95% CI] |
|---|---|---:|---:|---:|---|---|---|---|
| font-known | nobox | 1936 | 22 | 95.67 | 100.000 [100.000, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| font-known | exact | 1936 | 22 | 95.67 | 96.074 [94.603, 97.322] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.416 [0.345, 0.507] |
| font-known | grid-16 | 1936 | 22 | 95.67 | 97.779 [96.667, 98.683] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.179 [0.124, 0.257] |
| font-known | grid-64 | 1936 | 22 | 95.67 | 99.432 [98.756, 99.896] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.044 [0.012, 0.102] |
| font-known | start-aligned-128 | 1936 | 22 | 95.67 | 99.587 [98.926, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.027 [0.003, 0.075] |
| font-known | field-1000 | 159 | 22 | 95.67 | 100.000 [100.000, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| font-estimated | nobox | 1936 | 23 | 95.60 | 100.000 [100.000, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| font-estimated | exact | 1936 | 23 | 95.60 | 96.384 [95.176, 97.431] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.654 [0.579, 0.731] |
| font-estimated | grid-16 | 1936 | 23 | 95.60 | 98.295 [97.570, 98.907] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.336 [0.293, 0.382] |
| font-estimated | grid-64 | 1936 | 23 | 95.60 | 99.742 [99.430, 99.951] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.060 [0.050, 0.070] |
| font-estimated | start-aligned-128 | 1936 | 23 | 95.60 | 99.845 [99.573, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.067 [0.059, 0.076] |
| font-estimated | field-1000 | 159 | 23 | 95.60 | 100.000 [100.000, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| renderer-mismatch | nobox | 1936 | 22 | 95.26 | 100.000 [100.000, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| renderer-mismatch | exact | 1936 | 22 | 95.26 | 95.661 [94.136, 96.943] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.415 [0.344, 0.506] |
| renderer-mismatch | grid-16 | 1936 | 22 | 95.26 | 97.727 [96.613, 98.633] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.180 [0.125, 0.260] |
| renderer-mismatch | grid-64 | 1936 | 22 | 95.26 | 99.432 [98.756, 99.896] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.043 [0.012, 0.101] |
| renderer-mismatch | start-aligned-128 | 1936 | 22 | 95.26 | 99.587 [98.926, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.027 [0.003, 0.076] |
| renderer-mismatch | field-1000 | 159 | 22 | 95.26 | 100.000 [100.000, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| generic | nobox | 1936 | 31 | 95.15 | 100.000 [100.000, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| generic | exact | 1936 | 31 | 95.15 | 98.244 [97.406, 98.959] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.020 [0.010, 0.031] |
| generic | grid-16 | 1936 | 31 | 95.15 | 98.864 [98.259, 99.390] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.011 [0.003, 0.022] |
| generic | grid-64 | 1936 | 31 | 95.15 | 99.742 [99.430, 99.951] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.005 [0.000, 0.011] |
| generic | start-aligned-128 | 1936 | 31 | 95.15 | 99.897 [99.670, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| generic | field-1000 | 159 | 31 | 95.15 | 100.000 [100.000, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |

Strict neighbour-font estimate accuracy: 0.000%; target-font accuracy: 0.000%. Only 63 evaluated neighbour font identities are in the regular six-font bank.

The expanded cohort includes 63 of the preliminary test's 66 tokens. It uses a new calibrated tolerance and cohort, so its bits are not a direct replacement for the old 66-token estimate.

Evaluation targets: 1936; calibration targets: 15490. Full exclusion counts and native font provenance are in config.json; failed font-size cells are in render_failures.csv; omitted targets are in excluded.csv.gz and render_excluded.csv.gz.

No old result files, source fonts, page images or document text were changed or redistributed. Validation recomputes all point estimates, verifies exact generic replay, common cohorts, source hashes, split separation and minimal calibration tolerances.
