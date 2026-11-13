#!/bin/sh
set -eu
kit=${1:?Pass the verified, extracted experiment kit directory}
font_archive=${2:?Pass the font archive path}
fonts=${3:?Pass the extracted font directory}
mode=${4:-sanity}
review_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python3 "$review_dir/verify_fonts.py" "$font_archive" "$fonts" "$kit/results/e1-full/data/fonts.json"
docker run --rm \
    --mount "type=bind,src=$kit,dst=/kit" \
    --mount "type=bind,src=$fonts,dst=/fonts,readonly" \
    --mount "type=bind,src=$review_dir,dst=/review" \
    --env "REVIEW_MODE=$mode" --env "REVIEW_KIT_HOST=$kit" guard-e1-review4 sh -ec '
python - <<'"'"'PY'"'"'
import hashlib
import json
import os
import platform
import shutil
from pathlib import Path

import numpy as np
import PIL
from PIL import features

print(f"Python {platform.python_version()}, NumPy {np.__version__}, Pillow {PIL.__version__}")
print(f"{platform.platform()}, {platform.machine()}, {os.cpu_count()} logical CPUs")
print(next((row.strip() for row in Path("/proc/cpuinfo").read_text().splitlines()
            if row.startswith(("model name", "Hardware"))), "CPU model unavailable in guest"))
print({key: os.environ[key] for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")})
for name in ("raqm", "harfbuzz", "fribidi", "freetype2"):
    print(name, features.check(name), features.version(name))
if PIL.__version__ != "12.3.0" or not features.check("raqm"):
    raise SystemExit("Pillow 12.3.0 with RAQM is required")

manifest = json.loads(Path("/kit/results/e1-full/data/fonts.json").read_text())
for name, row in manifest.items():
    dest = Path(row["path"])
    matches = [p for p in Path("/fonts").rglob(dest.name)
               if p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest() == row["sha256"]]
    if len(matches) != 1:
        raise SystemExit(f"Missing unique verified font {name}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(matches[0], dest)
    print(f"Installed {name} at {dest} from {matches[0]}")
PY
export PYTHONPATH=/kit/results/e1-full/scripts
if [ "$REVIEW_MODE" = sweep ]; then
    python /review/verify_scoring.py /kit
    exec python /review/sweep.py /kit /kit/review4_grouped /review/sanity.csv --workers 6
fi
if [ "$REVIEW_MODE" = fig3 ]; then
    exec python /review/fig3.py /kit /review
fi
if [ "$REVIEW_MODE" = report ]; then
    started=$(date +%s)
    python /review/report.py /kit/review4_grouped /review "$REVIEW_KIT_HOST" /kit/results/e1-full/csv/pooled_size.csv
    python /review/validate_results.py /kit /review
    echo "Report wall_s=$(( $(date +%s) - started ))"
    exit
fi
sh /review/verify.sh --study-fonts > /review/verification.log 2>&1
started=$(date +%s)
rc=0
python /review/sanity.py /kit /review/sanity.csv || rc=$?
echo "Sanity wall_s=$(( $(date +%s) - started ))"
exit "$rc"
'
