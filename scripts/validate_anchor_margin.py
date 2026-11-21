#!/usr/bin/env python3
"""Recompute anchor summary metrics from released class-channel rows."""
import argparse,csv,gzip,hashlib,json,math
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'data/v1_5_anchor_margin')
    p=parser.parse_args().out
    with (p/'summary.csv').open() as f:rows=list(csv.DictReader(f))
    config=json.loads((p/'config.json').read_text())
    with gzip.open(p/'per_class.csv.gz','rt') as f:raw=list(csv.DictReader(f))
    groups=defaultdict(list);keys=['font','size_px','margin_px','C_px','policy','template_error']
    for r in raw:groups[tuple(r[k] for k in keys)].append(r)
    assert len(rows)==config['n_summary_rows']==2160
    assert len(raw)==config['n_class_rows'] and len(groups)==len(rows)
    for s in rows:
        rs=groups[tuple(s[k] for k in keys)]
        assert math.isclose(sum(float(r['joint_mass']) for r in rs),1,abs_tol=1e-12)
        assert math.isclose(math.fsum(float(r['information_contribution']) for r in rs),float(s['avg_bits']),abs_tol=1e-12)
        worst=max(rs,key=lambda r:float(r['pointwise_bits']))
        assert math.isclose(float(worst['pointwise_bits']),float(s['max_pointwise_bits']),abs_tol=1e-12)
        assert worst['names']==s['max_class_names']
        assert math.isclose(float(worst['prior_mass']),float(s['max_class_mass']),abs_tol=1e-12)
        assert all(float(r['output_probability'])<=float(r['prior_mass'])+1e-12 for r in rs)
        for key,n in [('mass_lt10',10),('mass_lt100',100)]:
            assert math.isclose(math.fsum(float(r['joint_mass']) for r in rs if int(r['names'])<n),float(s[key]),abs_tol=1e-12)
        assert math.isclose(math.fsum(float(r['joint_mass']) for r in rs if int(r['names'])==1),float(s['singleton_mass']),abs_tol=1e-12)
        assert math.isclose(math.fsum(float(r['context_probability']) for r in rs if int(r['names'])==1),float(s['n_singletons']),abs_tol=1e-12)
        assert float(s['area_p90'])>=float(s['area_median'])
        assert float(s['extra_area_vs_m0'])>=0
        if s['margin_px']=='0':assert float(s['extra_area_vs_m0'])==0
        if s['policy']=='fixed-field':assert float(s['avg_bits'])==float(s['max_pointwise_bits'])==0
    for name,expected in config['source_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
    proof=dict(passed=True,n_summary_rows=len(rows),n_class_rows=len(raw),m0_checks=config['m0_summary_checks'],
        error_model_checks=config['existing_error_model_checks'],
        summary_sha256=hashlib.sha256((p/'summary.csv').read_bytes()).hexdigest(),
        raw_class_aggregates_match=True,source_hashes_match=True,validator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        command='.venv/bin/python -B scripts/validate_anchor_margin.py')
    (p/'validation.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps(proof,indent=2))
if __name__=='__main__':main()
