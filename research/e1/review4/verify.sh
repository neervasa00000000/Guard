#!/bin/sh
set -eu
cd "$(dirname "$0")"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export MKL_NUM_THREADS=1
python_bin=${REVIEW4_PYTHON:-python3}
font=${1:?Supply a font path or --study-fonts}
started=$(date +%s)
"$python_bin" -c 'import os, platform, PIL, numpy; from PIL import features
print("Platform:", platform.platform(), "architecture:", platform.machine(), "logical CPUs:", os.cpu_count())
print("Python:", platform.python_version(), "Pillow:", PIL.__version__, "FreeType:", features.version_module("freetype2"), "NumPy:", numpy.__version__)
print("Thread settings:", {k: os.environ[k] for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "MKL_NUM_THREADS")})'
if [ "$(uname -s)" = Darwin ]; then
    /usr/sbin/system_profiler SPHardwareDataType 2>/dev/null | awk '/Chip:|Processor Name:|Total Number of Cores:/'
fi
"$python_bin" verify_geometry.py "$font"
"$python_bin" - <<'PY'
import numpy as np
from font_stats import estimates, font_draws, summary

rng = np.random.default_rng(20261031)
by_font = [rng.normal(size=(size, 4)) for size in range(1, 7)]
weights = font_draws(range(len(by_font)), 20261031)
for weight, observed in zip(weights, estimates(by_font, weights)):
    expanded = np.concatenate([rows for rows, n in zip(by_font, weight) for _ in range(n)])
    expected = np.r_[expanded[:, :3].mean(axis=0), np.median(expanded[:, 3])]
    np.testing.assert_allclose(expected, observed)
summary(by_font, weights)
print(f"Passed {len(weights)} cluster bootstrap checks against direct target expansion")
PY
printf "Verification wall_s=%s\n" "$(( $(date +%s) - started ))"
