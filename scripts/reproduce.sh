#!/bin/sh
# Fast path: fetch what can be checked, then rebuild tables from results/.
set -eu
cd "$(dirname "$0")/.."
if [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
else
  PY=python3
fi
"$PY" scripts/fetch_data.py || echo "FETCH DID NOT MATCH EVERY RECEIPT"
"$PY" scripts/regenerate_tables.py
"$PY" scripts/check_numbers.py
