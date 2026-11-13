#!/bin/sh
# Rebuild every locked table and figure from the archived CSVs.
# Exits non-zero if any locked number does not match the manuscript.
set -eu
cd "$(dirname "$0")"
exec make all
