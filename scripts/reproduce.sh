#!/bin/sh
# Rebuild the clean table from the released posterior rows without downloads.
set -eu
cd "$(dirname "$0")/.."
PY=${PYTHON:-}
if [ -z "$PY" ]; then
    if [ -n "${VIRTUAL_ENV:-}" ] || [ ! -x .venv/bin/python ]; then
        PY=python3
    else
        PY=.venv/bin/python
    fi
fi
"$PY" scripts/rebuild_clean_summary.py --check
"$PY" scripts/regenerate_tables.py
"$PY" scripts/check_numbers.py
