#!/usr/bin/env python3
"""Explicitly refresh expected values from completed summaries; never run from make."""
import json,subprocess
from pathlib import Path
from v14_numbers import snapshot
ROOT=Path(__file__).resolve().parents[1]
def main():
    changed=subprocess.check_output(['git','diff','--name-only','v1.3-artifact','--','*.csv'],cwd=ROOT,text=True).splitlines()
    sources=sorted({p for p in changed if p.endswith('summary.csv')}|{'results/v1_4_archive/v931_figures/summary.csv'})
    records=[snapshot(ROOT,p) for p in sources]
    path=ROOT/'manuscript/expected_numbers.json';spec=json.loads(path.read_text())
    spec['v1_4']=dict(status='completed summaries locked; remaining experiments incomplete',
        absolute_tolerance=1e-12,unknown_values='Blank/non-numeric cells preserved exactly; no unknown value replaced by a number.',
        pending_reproductions=['fresh six-font email/digit sweep','pinned Noto rerender','original mock-form rerun','same-target 188/2 rerender','392 TileSeal cases','original 36-cell alternative font builds'],
        sources=records)
    path.write_text(json.dumps(spec,indent=2,ensure_ascii=False)+'\n')
    print('Locked',sum(r['n_numeric_values'] for r in records),'numeric values across',len(records),'completed/preflight summary tables; pending reproductions remain explicit.')
if __name__=='__main__':main()
