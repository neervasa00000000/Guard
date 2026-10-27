# SPDX-License-Identifier: MIT
"""Always run both real-SDK formats, independently of the caller environment."""
import json,os,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
failed=False
for version in (2,3):
 try:
  proc=subprocess.run([sys.executable,str(root/'examples/c2pa/run_demo.py')],env={**os.environ,'GUARD_C2PA_VERSION':str(version)},capture_output=True,text=True,timeout=120)
  if proc.returncode:raise RuntimeError(proc.stderr or proc.stdout)
  r=json.loads(proc.stdout)
  assert r['format_version']==version and r['validation_state']=='Trusted' and r['grd']=='VERIFIED WITH REDACTIONS'
  assert r['without_anchor']=='Valid' and r['without_anchor_accepted'] is False
  assert r['edited_c2pa']=='Invalid' and r['edited_grd']=='TAMPERED'
  print(f'GRD{version}: PASS (Trusted; unanchored not accepted; edited Invalid + TAMPERED)')
 except Exception as exc:failed=True;print(f'GRD{version}: FAIL: {exc}',file=sys.stderr)
if failed:sys.exit(1)
