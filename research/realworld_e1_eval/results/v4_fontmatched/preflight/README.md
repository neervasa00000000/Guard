# Font-matched v4 prerequisite audit

This is a preflight, not an attacker evaluation. No candidate rendering, font estimation, tolerance calibration, policy scoring or bootstrap inference was run. The audit reads released no-text tables only; it does not redistribute or upload document text.

The target cohort is exactly the saved DocLayNet v2 targets. Eligibility uses known line-neighbour size and font metadata, separately from whether the target itself has a size or matches its neighbours. Local fonts are indexed by their actual full/PostScript names, with no substitutions. Font availability is a prerequisite, not a claim of source-binary/build equivalence.

Outputs: config.json, per_target.csv.gz (hashes/lengths only), summary.csv, font_availability.csv, pinned_font_availability.csv, local_font_files.json. Missing fonts are explicit; no attacker-performance table is fabricated.

The supplied instruction requires stopping if a run cannot execute because prerequisites are missing. Provide the missing neighbour fonts with suitable local-use rights and the pinned study binaries (see availability tables), then rerun the preflight with additional --font-dir paths. Later experiment prompts have not started.
