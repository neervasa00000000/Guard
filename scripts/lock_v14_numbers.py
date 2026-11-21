#!/usr/bin/env python3
"""Explicitly refresh expected values from completed summaries; never run from make."""
import json,subprocess
from pathlib import Path
from v14_numbers import snapshot
ROOT=Path(__file__).resolve().parents[1]
def main():
    changed=subprocess.check_output(['git','diff','--name-only','v1.3-artifact','--','*.csv'],cwd=ROOT,text=True).splitlines()
    new=[str(p.relative_to(ROOT)) for folder in ['results/v1_4_archive','data/v1_6_email_digits'] for p in (ROOT/folder).rglob('summary.csv') if '.cache' not in p.parts]
    sources=sorted({p for p in changed+new if p.endswith('summary.csv')}|{'results/v1_4_archive/v931_figures/summary.csv','data/v1_6_email_digits/table_pooled.csv','results/v1_4_archive/noto_rerender/geometry_checks.csv'})
    records=[snapshot(ROOT,p) for p in sources]
    path=ROOT/'manuscript/expected_numbers.json';spec=json.loads(path.read_text())
    spec['v1_4']=dict(status='complete with user-approved documented reconstructions; historical provenance limits retained',
        absolute_tolerance=1e-12,unknown_values='Blank/non-numeric cells preserved exactly; no unknown value replaced by a number.',
        pending_reproductions=[],scope_approval='2026-11-21: Use the documented new experiments',
        historical_unverified=['Exact original LibreOffice template/full-page scan replication','Original alternative font-build identities and cell definition'],
        aggregates=[
          dict(id='rerender_C128_changed_targets',path='results/v1_4_archive/rerender_class_changes/summary.csv',where={'C_px':128},operation='sum',column='n_class_changes',expected=188),
          dict(id='rerender_C192_changed_targets',path='results/v1_4_archive/rerender_class_changes/summary.csv',where={'C_px':192},operation='sum',column='n_class_changes',expected=2),
          dict(id='tileseal_matching_redactions',path='results/v1_4_archive/tileseal/summary.csv',operation='sum',column='matching',expected=392),
          dict(id='new_sensitivity_cell_count',path='results/v1_4_archive/font_builds/summary.csv',operation='count',expected=36),
          dict(id='new_sensitivity_cells_shift_at_least_4pp',path='results/v1_4_archive/font_builds/summary.csv',where={'shift_at_least_4pp':'True'},operation='count',expected=2)],
        sources=records)
    path.write_text(json.dumps(spec,indent=2,ensure_ascii=False)+'\n')
    print('Locked',sum(r['n_numeric_values'] for r in records),'numeric values across',len(records),'completed/preflight summary tables; approved scope and historical limits remain explicit.')
if __name__=='__main__':main()
