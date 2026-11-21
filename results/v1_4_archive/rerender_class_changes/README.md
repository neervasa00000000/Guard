# Original 24px font-rerender check

Recovered a3_start/run.py from commit 733d48a identifies the original target seed and five-release font scenario. Its rerender function executes unchanged using freshly rendered, receipt-consistent six-font geometry. The 128px and 192px counts reproduce 188 and 2 of 2000 targets, respectively; original top-10 and bits also match within 1e-9.

The historical count means any class change among five releases, not only first versus last. Each target has one row per width with first/last classes plus the complete five-class sequence and font order. No surname text or font binaries are archived. New target-bootstrap CIs use 10000 resamples, seed 20261121.
