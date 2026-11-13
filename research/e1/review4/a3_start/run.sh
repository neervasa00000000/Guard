#!/bin/sh
set -eu
kit=/private/tmp/tileseal-review4.EKJJXk
review="$PWD/research/e1/review4"
docker run --rm --network none --read-only \
  --mount "type=bind,src=$kit,dst=/kit,readonly" \
  --mount "type=bind,src=$review,dst=/review,readonly" \
  --mount "type=bind,src=$review/a3_start,dst=/out" \
  --mount "type=bind,src=$PWD/Rerun/e1_fonts/e1_fonts,dst=/fonts,readonly" \
  -e PYTHONDONTWRITEBYTECODE=1 guard-e1-review4-forms sh -eu -c '
  python -c "
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, \"/kit/results/e1-full/scripts\")
import e1lib as E
for name, row in json.loads(Path(\"/kit/results/e1-full/data/fonts.json\").read_text()).items():
    source = Path(\"/fonts\") / Path(row[\"path\"]).name
    assert hashlib.sha256(source.read_bytes()).hexdigest() == row[\"sha256\"]
"
  exec python -u /out/run.py /kit /review /out "$@"
' sh "$@"
