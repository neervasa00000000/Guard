# v9.31 figure checks

The supplied script draws Figures 2–5 and A1 from the existing figs_data.csv. Its content is unchanged. All five figures have zero reported layout problems; 101 plotted values match the source CSV. The contact sheet was visually inspected during initial integration; changed inputs or renderer versions need renewed visual review.

Run `make figures PY=python3` from the repository root, or `python3 scripts/check_v931_figures.py`. The first run downloads Source Sans Pro Regular and Bold from the pinned official Adobe commit, verifies SHA-256, and caches them under ignored out/fonts/. Later runs use that cache. Network access is needed only when those font files are absent. No document text or images are uploaded.

Source Sans Pro is required for these five-inch layouts; the DejaVu fallback produced 24 layout problems in the initial check. The checked font builds and renderer versions are in config.json. Font binaries, generated PNG/PDF files and the contact sheet are excluded from Git. raw.csv records the plotted numerical values; run.log and summary.csv record the supplied checks. These figure checks do not reproduce the remaining blocked experiments.
