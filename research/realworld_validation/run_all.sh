#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
PY=".venv/bin/python"
"$PY" -m pytest -q research/realworld_validation/tests/test_geometry.py
"$PY" research/realworld_validation/src/run_validation.py --out research/realworld_validation/results
"$PY" research/realworld_validation/src/verify_results.py
"$PY" research/realworld_validation/src/make_figures.py
"$PY" research/realworld_validation/src/write_report.py
