# Fresh LibreOffice reconstruction

This end-to-end experiment generates new LibreOffice documents, PDF pages, raster ink, full-list candidate measurements and attacks. It uses the same 100 archived synthetic surname targets and font assignments, sizes 16/24, and records one hashed row per target/policy/attacker. No saved target geometry is used to score. LibreOffice and all parameters are recorded in config.json. The container has no network access.

The original generator/template is still missing. The FODT template and local-word scan model are newly specified, so these results do not establish reproduction of the historical mock-form numbers. summary.csv reports differences wherever directly corresponding historical hit rates exist; no historical row is overwritten. Raw PDFs, glyph images, font binaries and text requests remain ignored under out/. Only derived geometry, hashes, counts, config and code are archived.

Run the command in config.json with the existing LibreOffice container and checked study dependencies. Confidence intervals use 10000 form bootstrap draws, seed 20261121. No-box area/coverage is unknown (blank), rather than a fabricated zero.
