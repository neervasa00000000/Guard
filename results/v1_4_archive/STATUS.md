# v1.4 run status

Completed runs and checks are archived below. A fresh end-to-end LibreOffice reconstruction is complete; exact replication of the historical template is still blocked by its missing kit; the historical alternative-font-build provenance remains unverified. The new explicit 36-cell sensitivity experiment is complete. On 2026-11-21 the user accepted these documented new experiments for v1.4-artifact, retaining the historical provenance limits. Branch `exp-v1.4` and tag `v1.4-artifact` (commit 162567c) were pushed to origin; `v1.3-artifact` and TileSeal `f8f2558` were not moved.

| Work | Result |
|---|---|
| Expanded font-context attackers | 1,936 paired evaluation targets; 15,490 calibration targets; 24 summaries. |
| Area/OCR | Completed approved FUNSD-only fallback; DocLayNet insertion reconstruction remains outside that fallback. |
| Anchor margin | Full 50,000-name prior, six fonts, three sizes; 2,160 summaries. |
| E-mail/digits | 864,000 target-policy rows, 432 summaries, 24 pooled summaries; digit bits unknown except fixed-field zero. |
| Pinned Noto | All 150,000 fresh bounds match retained receipts; 126,000 target-policy scores reproduce v1.2. |
| Five-font rerender | 188/2,000 class changes at C=128; 2/2,000 at C=192. |
| TileSeal | 392/392 predicted tile sets match actual sealed tile sets and original archived cases. |
| Font-build sensitivity | 2/36 cells shift at least 4 pp; both +7.8 pp. Historical build identities unknown. |
| Figures | Five v9.31 figures: zero layout problems and zero missing plotted values. |
| LibreOffice reconstruction | Fresh LibreOffice 25.2.3.2: 200 form pages, 200000 candidate geometries, 7200 per-form rows, 72 summaries. Historical differences are explicit; original template still unavailable. |

## New font-build sensitivity

Cells are six fonts × 12/16/24 px × A1/A2 exact clean layout boxes. Alternative builds were frozen before scoring. Rates below are percentages; intervals are paired target-bootstrap 95% CIs (10,000 draws, seed 20261121).

| Font | Size | Attacker | Baseline top-10 % | Alternative top-10 % | Change pp [95% CI] |
|---|---:|---|---:|---:|---|
| LiberationSans | 16 | A1 | 46.95 | 54.75 | 7.80 [6.65, 9.00] |
| LiberationSans | 16 | A2 | 46.95 | 54.75 | 7.80 [6.65, 9.00] |

All 36 cells and font hashes: font_builds/summary.csv and protocol.json. The historical claim is not verified merely because this separately defined experiment reproduces its count and range.

Expanded attacker results: ../../research/realworld_e1_eval/results/v4_fontmatched/README.md. Its exclusions explicitly include 3,259 targets with unknown neighbour size/font, 40 missing local font identities, and 76 lacking independent context geometry. Eight calibration targets also failed rendering. Font-name identity does not establish equality of source font builds.

The independent new-run validator recomputed all reported new-run means and bootstrap intervals from raw no-text rows (532,620 numeric comparisons). See new_runs_validation.json. The v4 validator independently checked points, pairing, source hashes, original generic scores and minimal 95% calibration tolerances.

Detailed tables: ../../data/v1_6_email_digits/table_pooled.csv; ../../data/v1_5_anchor_margin/summary.csv; ../../research/area_eval/results/summary.csv. All rates in CSVs are fractions unless a column explicitly says pp or percent; bits and area ratios retain their own units.

Fresh LibreOffice reconstruction and historical comparisons: mock_forms_reconstruction/README.md and summary.csv. The full-array validator recomputes every score, policy box, summary and 10000-draw interval from archived no-text candidate geometry. The original archived manuscript numbers are unchanged.

Release verification: libreoffice_clean_clone/ records a clean-clone make all (46410 new checks and 369 baseline checks, zero mismatches), plus both independent raw-data validators (28960 and 532620 numeric checks). The final release scope acceptance is in scope_approval.json.
