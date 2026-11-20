# FUNSD real-document validation

Controlled black rectangles on the official FUNSD split. This directory does not replace the synthetic GUARD results and does not edit the manuscript.

Primary held-out result, length–width model, exact box: top-1 0.17% (equal to the no-box baseline on every test field), top-10 4.67%, dictionary entropy reduction 1.17 bits, truth information gain 1.30 bits on the 92 recurring strings. Eligible fields scored in the test split: 585 from 199 documents (2642 eligible overall).

Reports are in `docs/`. The protocol is `PROTOCOL.md`. Verification: 25 passed, 0 failed.

```sh
.venv/bin/python research/funsd_validation/run_funsd_validation.py
.venv/bin/python research/funsd_validation/verify_funsd_independent.py
.venv/bin/python research/funsd_validation/make_funsd_figures.py
.venv/bin/python research/funsd_validation/write_funsd_reports.py
.venv/bin/python -m pytest -q tests/test_funsd_validation.py
```
