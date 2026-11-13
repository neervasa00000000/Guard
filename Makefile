# One-command path: archived CSVs to tables, figures, and the manuscript check.
PY ?= python3

.PHONY: all data tables figures check

all: data tables figures check

data:
	$(PY) scripts/verify_inputs.py
	$(PY) scripts/rebuild_clean_summary.py --check

tables:
	$(PY) scripts/regenerate_tables.py

figures:
	$(PY) scripts/make_figures.py

check:
	$(PY) scripts/check_numbers.py
