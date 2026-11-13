#!/bin/sh
# Re-render the main sweep and the 42 px supplement using the original seeds.
set -eu
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
case "${1:-}" in
    -h|--help)
        echo 'Usage: scripts/rerun_full.sh (see research/e1/README.md for renderer inputs)'
        exit 0
        ;;
esac
if [ "$#" -ne 0 ]; then
    echo 'This entry point takes no arguments. See research/e1/README.md for smaller runs.' >&2
    exit 2
fi
export E1_N=2000
"$PY" research/e1/scripts/e1_run.py
"$PY" research/e1/scripts/e1_run_300dpi.py
"$PY" research/e1/scripts/e1_analyze.py
