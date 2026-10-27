# SPDX-License-Identifier: MIT
"""Run the shared real-SDK demo as a regression test."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().parents[1]/'examples/c2pa/run_demo.py'),run_name='__main__')
