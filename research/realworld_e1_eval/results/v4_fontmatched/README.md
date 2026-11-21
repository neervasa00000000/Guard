# Available-font attacker comparison

All numbers below come from this run’s summary.csv. This is the user-authorized available-font subset, with additional explicit exclusions where no independent context geometry exists or the pinned renderer fails. It is not a full-cohort replication.

The font-known arm uses neighbour font metadata and a locally available matching font name. Matching a font name does not establish equality of source font binaries/builds. Point sizes are converted to horizontal page pixels using page metadata. The renderer-mismatch arm uses Pillow BASIC instead of RAQM.

The font-estimated arm is one explicitly specified **anonymous-geometry baseline**, not an optimal font-recognition attack: it uses no visible word identities, character counts, pixels or font names. It compares width/height quantiles with 512 fixed prior-weighted Census probes per candidate font/size. Source context cells can contain several words, so the probe width distribution can be misspecified. Accuracy is strict equality to the neighbour modal font identity; true identities outside the regular six-font bank count incorrect.

Noto Sans uses receipt-matched retained geometry only at 12/16/24 px. Its unavailable pinned binary is not replaced. The additional stored-size option is rendered only for the other five study fonts. The generic arm is unchanged v2 per-token scoring on the same paired tokens, with its original pooled calibration tolerance.

Each other arm uses the original held-out page split, restricted to common usable DocLayNet calibration targets. FUNSD supplies no font metadata. Tolerances are the smallest integer symmetric edge slack reaching 95% exact-box truth-in, then frozen across policies. Padding and empty-set fallback retain the v2 feasibility/scoring convention. CIs are 10,000 page-cluster percentile draws, seed 20261121.

The first-1000 field row includes only targets in that bounded list and uses its renormalized prior, as v2 does; its n and prior differ from the full-list rows.

| Attacker | Policy | n | Tolerance px | Calib truth-in % | Truth-in % [95% CI] | Top-1 % [95% CI] | Top-10 % [95% CI] | Attacker performance (bits) [95% CI] |
|---|---|---:|---:|---:|---|---|---|---|
| font-known | nobox | 969 | 20 | 95.37 | 100.000 [100.000, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| font-known | exact | 969 | 20 | 95.37 | 96.285 [94.221, 97.921] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.635 [0.489, 0.821] |
| font-known | grid-16 | 969 | 20 | 95.37 | 97.523 [95.896, 98.780] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.305 [0.197, 0.464] |
| font-known | grid-64 | 969 | 20 | 95.37 | 98.762 [97.399, 99.690] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.075 [0.017, 0.189] |
| font-known | start-aligned-128 | 969 | 20 | 95.37 | 99.278 [97.983, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.053 [0.006, 0.149] |
| font-known | field-1000 | 52 | 20 | 95.37 | 100.000 [100.000, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| font-estimated | nobox | 969 | 20 | 95.11 | 100.000 [100.000, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| font-estimated | exact | 969 | 20 | 95.11 | 96.078 [94.173, 97.607] | 0.000 [0.000, 0.000] | 0.103 [0.000, 0.330] | 1.026 [0.902, 1.156] |
| font-estimated | grid-16 | 969 | 20 | 95.11 | 98.039 [96.891, 98.984] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.496 [0.421, 0.577] |
| font-estimated | grid-64 | 969 | 20 | 95.11 | 99.794 [99.318, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.077 [0.062, 0.094] |
| font-estimated | start-aligned-128 | 969 | 20 | 95.11 | 99.794 [99.318, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.078 [0.066, 0.092] |
| font-estimated | field-1000 | 52 | 20 | 95.11 | 100.000 [100.000, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| renderer-mismatch | nobox | 969 | 20 | 95.50 | 100.000 [100.000, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| renderer-mismatch | exact | 969 | 20 | 95.50 | 96.285 [94.221, 97.921] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.639 [0.493, 0.824] |
| renderer-mismatch | grid-16 | 969 | 20 | 95.50 | 97.420 [95.780, 98.690] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.305 [0.198, 0.464] |
| renderer-mismatch | grid-64 | 969 | 20 | 95.50 | 98.762 [97.399, 99.690] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.075 [0.017, 0.189] |
| renderer-mismatch | start-aligned-128 | 969 | 20 | 95.50 | 99.278 [97.983, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.054 [0.006, 0.153] |
| renderer-mismatch | field-1000 | 52 | 20 | 95.50 | 100.000 [100.000, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| generic | nobox | 969 | 31 | 95.15 | 100.000 [100.000, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| generic | exact | 969 | 31 | 95.15 | 98.762 [97.931, 99.433] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.011 [0.005, 0.019] |
| generic | grid-16 | 969 | 31 | 95.15 | 98.968 [98.180, 99.585] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.003 [0.001, 0.006] |
| generic | grid-64 | 969 | 31 | 95.15 | 99.794 [99.318, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| generic | start-aligned-128 | 969 | 31 | 95.15 | 99.794 [99.318, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| generic | field-1000 | 52 | 31 | 95.15 | 100.000 [100.000, 100.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |

Strict neighbour-font estimate accuracy: 0.000%; target-font accuracy: 0.000%. Only 63 evaluated neighbour font identities are in the regular six-font bank.

The expanded cohort includes 63 of the preliminary test's 66 tokens. It uses a new calibrated tolerance and cohort, so its bits are not a direct replacement for the old 66-token estimate.

Evaluation targets: 969; calibration targets: 8569. Full exclusion counts and native font provenance are in config.json; failed font-size cells are in render_failures.csv; omitted targets are in excluded.csv.gz and render_excluded.csv.gz.

No old result files, source fonts, page images or document text were changed or redistributed. Validation recomputes all point estimates, verifies exact generic replay, common cohorts, source hashes, split separation and minimal calibration tolerances.
