#!/bin/sh
# Full experiment rerun. CPU only.
# Expected time: the published main sweep was an overnight run. A fresh
# surname-and-word sweep is on the order of several hours to more than a day
# on one CPU, and the language-model pass is separate.
# Census SHA-256 is NOT FOUND, so this script does not start a render.
echo "DOES NOT REPRODUCE: this checkout has the census and Qwen SHA-256 checks, not the full render harness."
echo "Gutenberg, census, and Qwen2.5-0.5B hashes are in scripts/fetch_data.py."
echo "Study environment recorded torch 2.15.0 and transformers 5.22.2. They are not installed by the fast path."
exit 1
