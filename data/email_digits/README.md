# E-mail and digit sweep

Six hash-verified fonts, sizes 12/16/24, 2000 paired targets per cell and 12 policies. All targets are synthetic; only hashes and character lengths are archived. Exact geometry comes from the pinned clean E1 RAQM renderer. Width-only grid snaps both horizontal edges to the page; start padding uses the shared list anchor.

Email bits are sampled target estimates with CIs; exact_bits separately enumerates the entire prior and every uniform pen phase, compressed only by identical observation partitions. Digit scoring retains the original multiplicity classes and independently calibrated 400-string edge tolerance; entropy inference is not exact for this approximate geometry model, so digit bits are explicitly unknown except the common field geometry (zero). n_bits_unknown records these omissions. Field target containment is separately reported.

Confidence limits use 10000 target-bootstrap resamples, seed 20261121. Means use exact multinomial sufficient counts. Area quantiles use the mathematically identical marginal bootstrap generated from adjacent uniform order statistics; these are marginal intervals, not a joint paired confidence region. Pooled quantiles use all target-level areas.

Run the command in config.json after obtaining checked font inputs. Per-cell numeric working files are cached under ignored .cache/. No fonts, rendered images, original document text or private keys are redistributed.
