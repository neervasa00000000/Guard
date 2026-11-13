#!/bin/sh
set -eu
kit=/private/tmp/tileseal-review4.EKJJXk
base="$PWD/research/e1"
docker run --rm --network none --read-only \
  --mount "type=bind,src=$kit,dst=/kit,readonly" \
  --mount "type=bind,src=$base/review4,dst=/review,readonly" \
  --mount "type=bind,src=$base/mdpi_checks/posterior_toy,dst=/out" \
  --mount "type=bind,src=$PWD/Rerun/e1_fonts/e1_fonts,dst=/fonts,readonly" \
  -w /out -e PYTHONDONTWRITEBYTECODE=1 guard-e1-review4-forms \
  python -u /out/check.py /kit /review /out
