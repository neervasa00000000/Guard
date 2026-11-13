# Start-aligned 128 px padding on mock forms

Surname top-10 hits per 100 forms, with Wilson 95% intervals. Each paired difference is the 16 px grid minus start-aligned padding, in percentage points. The interval resamples the same forms in both policies.

| Renderer | Size | Condition | Attacker | Exact | 16 px grid | 64 px grid | Edge-aligned 128 px | Start-aligned 128 px | Paired difference (95% CI) |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| LibreOffice | 16 | clean | Mismatched (Pillow) | 0 [0.0, 3.7] | 12 [7.0, 19.8] | 6 [2.8, 12.5] | 7 [3.4, 13.7] | 6 [2.8, 12.5] | +6.0 [+2.0, +11.0] |
| LibreOffice | 16 | clean | Matched | 63 [53.2, 71.8] | 13 [7.8, 21.0] | 6 [2.8, 12.5] | 9 [4.8, 16.2] | 6 [2.8, 12.5] | +7.0 [+2.0, +12.0] |
| LibreOffice | 16 | scan | Mismatched (Pillow) | 23 [15.8, 32.2] | 10 [5.5, 17.4] | 6 [2.8, 12.5] | 6 [2.8, 12.5] | 6 [2.8, 12.5] | +4.0 [+1.0, +8.0] |
| LibreOffice | 16 | scan | Matched | 22 [15.0, 31.1] | 10 [5.5, 17.4] | 6 [2.8, 12.5] | 5 [2.2, 11.2] | 6 [2.8, 12.5] | +4.0 [+1.0, +8.0] |
| LibreOffice | 24 | clean | Mismatched (Pillow) | 3 [1.0, 8.5] | 21 [14.2, 30.0] | 7 [3.4, 13.7] | 8 [4.1, 15.0] | 8 [4.1, 15.0] | +13.0 [+7.0, +20.0] |
| LibreOffice | 24 | clean | Matched | 73 [63.6, 80.7] | 21 [14.2, 30.0] | 7 [3.4, 13.7] | 14 [8.5, 22.1] | 8 [4.1, 15.0] | +13.0 [+7.0, +20.0] |
| LibreOffice | 24 | scan | Mismatched (Pillow) | 35 [26.4, 44.7] | 19 [12.5, 27.8] | 9 [4.8, 16.2] | 7 [3.4, 13.7] | 7 [3.4, 13.7] | +12.0 [+6.0, +19.0] |
| LibreOffice | 24 | scan | Matched | 34 [25.5, 43.7] | 19 [12.5, 27.8] | 9 [4.8, 16.2] | 7 [3.4, 13.7] | 7 [3.4, 13.7] | +12.0 [+6.0, +19.0] |
| Pillow | 16 | clean | A1 (known start) | 52 [42.3, 61.5] | 12 [7.0, 19.8] | 8 [4.1, 15.0] | 10 [5.5, 17.4] | 7 [3.4, 13.7] | +5.0 [+1.0, +10.0] |
| Pillow | 16 | clean | A2 (unknown start) | 51 [41.3, 60.6] | 10 [5.5, 17.4] | 7 [3.4, 13.7] | 7 [3.4, 13.7] | 7 [3.4, 13.7] | +3.0 [+0.0, +7.0] |

Median redacted area divided by the padded tight-box area.

| Renderer | Size | Condition | Exact | 16 px grid | 64 px grid | Edge-aligned 128 px | Start-aligned 128 px |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| LibreOffice | 16 | clean | 1.00× | 2.62× | 17.64× | 3.36× | 3.36× |
| LibreOffice | 16 | scan | 1.00× | 2.55× | 15.66× | 4.15× | 4.15× |
| LibreOffice | 24 | clean | 1.00× | 1.90× | 10.78× | 2.47× | 2.47× |
| LibreOffice | 24 | scan | 1.00× | 1.98× | 11.49× | 2.67× | 2.67× |
| Pillow | 16 | clean | 1.00× | 2.95× | 20.42× | 3.66× | 3.66× |

The template-derived start differs from the rounded PDF-origin start in 28 of 400 LibreOffice observations. Start-aligned padding contains the full padded tight box in 400 observations and the measured ink bounds in 400. The scores use the specified fixed policy on every form.

The LibreOffice controls are the archived policies, checked against the regenerated forms. The new policy uses the margin plus the template tab stop as the pen column and maps it through the known page rotation for scan-like forms. The anchor offset is the minimum left offset of the matched surname dictionary minus one pixel. The width rounds the span to the padded right edge up to a multiple of 128 px. The full line uses the font metrics expanded to candidate extrema plus one pixel on each side, as in review4. Both attackers receive the same policy geometry. Each attacker's candidate right edge uses its original renderer and calibrated tolerance. Candidate filtering retains the original prior ranking and tie handling.

**Start recovery from a standalone scan is untested.**

The Pillow clean replay uses the available LAYOUT-BOX scorer for A1 and A2. Its original exact and grid controls and A1 edge-padding control match the archive. The A2 edge-padding count is a replay because the corresponding archived count was absent.

The paired bootstrap uses 4,000 resamples with seed 20261117. The form, scan and calibration seeds are documented with the replay setup. [Replay setup](FORMS_RESULTS.md) · [Run log](start_replay.log)

```sh
sh research/e1/review4/forms/run_replay.sh \
  /private/tmp/tileseal-review4.EKJJXk "$PWD/Rerun/e1_fonts" \
  "$HOME/tileseal-t3-lm/csv/test3_docs.json" start \
  > research/e1/review4/forms/start_replay.log 2>&1
python3 research/e1/review4/forms/report_start.py research/e1/review4/forms
```

[Policy summary CSV](start_policy_summary.csv) · [Paired differences CSV](start_vs_grid16_paired.csv) · [LibreOffice cases](libreoffice_start_cases.csv) · [Pillow cases](pillow_start_cases.csv)
