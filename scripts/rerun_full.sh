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
    echo 'This entry point takes no arguments. It is not part of make all.' >&2
    exit 2
fi
export E1_N=2000
echo 'Full re-render needs Pillow 12.3.0 with RAQM, the six fonts, and the full Census CSV (E1_CENSUS).' >&2
"$PY" research/e1/e1_run.py
