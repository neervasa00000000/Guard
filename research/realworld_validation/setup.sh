#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
python3 -m venv .venv
.venv/bin/python -m pip install -r research/realworld_validation/requirements.txt
echo "Installed into .venv. No system packages were changed."
