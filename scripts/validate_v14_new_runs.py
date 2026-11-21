#!/usr/bin/env python3
"""Recompute new-run estimates and confidence limits from archived no-text rows."""
import csv,gzip,hashlib,itertools,json,math
from collections import defaultdict
import numpy as np
from v14_runtime import ROOT,read,mean_intervals,area_intervals,digest

CHECKS=0
def equal(a,b):
    global CHECKS
    assert math.isclose(float(a),float(b),rel_tol=0,abs_tol=1e-10),(a,b)
    CHECKS+=1
def intervals(rows,keys,summary):
    a=np.array([[float(r[k]) for k in keys] for r in rows])
    point,lo,hi=mean_intervals(a)
    for j,k in enumerate(keys):
        for suffix,value in [('',point[j]),('_lo',lo[j]),('_hi',hi[j])]:equal(value,summary[k+suffix])
def groups(rows,keys):
    result=defaultdict(list)
    for r in rows:
        assert len(r['target_sha256'])==64 and int(r['target_char_length'])>0
        assert not ({'text','target','surname','email','string'}&r.keys())
        result[tuple(r[k] for k in keys)].append(r)
    return result
def archive():
    out=ROOT/'results/v1_4_archive'
    raw=read(out/'font_builds/raw.csv.gz');g=groups(raw,['font','size_px','attacker'])
    assert len(raw)==72000 and len(g)==36
    keys=['baseline_top1','baseline_top10','baseline_bits','alternative_top1','alternative_top10','alternative_bits','delta_top10_pp','delta_bits']
    shifted=[]
    for s in read(out/'font_builds/summary.csv'):
        rs=g[tuple(s[k] for k in ['font','size_px','attacker'])];assert len(rs)==2000
        for r in rs:
            equal(100*(float(r['alternative_top10'])-float(r['baseline_top10'])),r['delta_top10_pp'])
            equal(float(r['alternative_bits'])-float(r['baseline_bits']),r['delta_bits'])
        intervals(rs,keys,s)
        if abs(float(s['delta_top10_pp']))>=4:shifted.append(s)
    assert len(shifted)==2
    for s in shifted:equal(s['delta_top10_pp'],7.8)
    for size in ['12','16','24']:
        for font in {r['font'] for r in raw}:
            assert [(r['case'],r['target_sha256']) for r in g[(font,size,'A1')]]==[(r['case'],r['target_sha256']) for r in g[(font,size,'A2')]]
    raw=read(out/'rerender_class_changes/raw.csv.gz');g=groups(raw,['C_px'])
    assert len(raw)==4000
    for s in read(out/'rerender_class_changes/summary.csv'):
        rs=g[(s['C_px'],)];changes=0;end_changes=0
        for r in rs:
            classes=json.loads(r['all_release_classes']);fonts=json.loads(r['release_fonts'])
            assert len(classes)==len(fonts)==len(set(fonts))==5
            changed=len(set(classes))>1;end=classes[0]!=classes[-1]
            assert changed==(r['any_class_change']=='True') and end==(r['first_last_change']=='True')
            assert classes[0]==int(r['old_class']) and classes[-1]==int(r['new_class'])
            changes+=changed;end_changes+=end
            r['bits_gain']=float(r['bits_after'])-float(r['bits_first']);r['change_fraction']=float(changed)
        assert changes==int(s['n_class_changes'])=={'128':188,'192':2}[s['C_px']]
        assert end_changes==int(s['n_first_last_changes'])
        intervals(rs,['top10_first','top10_after','bits_first','bits_after','bits_gain','change_fraction'],s)
    raw=read(out/'tileseal/raw.csv.gz');g=groups(raw,['grid_px']);assert len(raw)==392
    for r in raw:
        a=json.loads(r['predicted_tiles']);b=json.loads(r['sealed_tiles'])
        assert a==b and len(a)==int(r['n_predicted_tiles'])==int(r['n_sealed_tiles'])
        assert len({tuple(t) for t in a})==len(a) and all(t[2:]==[8,8] for t in a)
    for s in read(out/'tileseal/summary.csv'):
        assert len(g[(s['grid_px'],)])==int(s['matching'])==int(s['n_redactions'])==98
        assert int(s['mismatching'])==0
    raw=read(out/'noto_rerender/raw.csv.gz');g=groups(raw,['size_px','policy','param']);assert len(raw)==126000
    for s in read(out/'noto_rerender/summary.csv'):
        rs=g[tuple(s[k] for k in ['size_px','policy','param'])];assert len(rs)==2000
        for r in rs:
            for k in ['bits','top10','area_ratio']:equal(r[k],r['archived_'+k])
        intervals(rs,['bits','top10'],s)
        for k,v in area_intervals([float(r['area_ratio']) for r in rs]).items():equal(v,s[k])
    for r in read(out/'noto_rerender/geometry_checks.csv'):
        assert r['fresh_receipt']==r['archived_receipt'] and int(r['differing_names'])==0 and int(r['n'])==50000
    return dict(font_build_cells=36,new_sensitivity_cells_shifted_4pp=2,historical_build_manifest_verified=False,
        rerender_changes_C128=188,rerender_changes_C192=2,tileseal_matching=392,noto_target_policy_rows=126000)

def secondary():
    out=ROOT/'data/v1_6_email_digits';spec=json.loads((out/'config.json').read_text())
    summaries={tuple(s[k] for k in ['list','font','size_px','policy','param']):s for s in read(out/'summary.csv')}
    pooled=defaultdict(list);nraw=0;ncell=0
    # The raw file is grouped by list/font/size, with 12 consecutive policy rows per case.
    with gzip.open(out/'per_target.csv.gz','rt',newline='') as f:
        reader=csv.DictReader(f)
        for cell,stream in itertools.groupby(reader,key=lambda r:tuple(r[k] for k in ['list','font','size_px'])):
            rows=list(stream);nraw+=len(rows);ncell+=1;assert len(rows)==24000
            for _,case in itertools.groupby(rows,key=lambda r:r['case']):
                case=list(case);assert len(case)==12
                assert len({tuple(r[k] for k in ['target_sha256','target_char_length','pen_x','baseline_y']) for r in case})==1
            g=groups(rows,['policy','param'])
            assert len(g)==12
            for policy,rs in g.items():
                assert len(rs)==2000
                s=summaries[cell+policy];known=cell[0]=='emails' or policy[0]=='field'
                for r in rs:
                    r['truth_in']=float(r['truth_in']=='True');r['target_coverage']=float(r['target_fully_covered']=='True')
                    if not known:assert r['bits']==''
                keys=(['bits'] if known else [])+['top1','top10','truth_in','target_coverage']
                intervals(rs,keys,s)
                assert int(s['n_bits_unknown'])==(0 if known else 2000)
                for k,v in area_intervals([float(r['area_ratio']) for r in rs]).items():equal(v,s[k])
                pooled[(cell[0],*policy)].extend(rs)
            print('Validated secondary',cell,flush=True)
    assert len(summaries)==432 and nraw==864000 and ncell==36
    for s in read(out/'table_pooled.csv'):
        rs=pooled[tuple(s[k] for k in ['list','policy','param'])];assert len(rs)==int(s['n'])==36000
        known=s['list']=='emails' or s['policy']=='field'
        intervals(rs,(['bits'] if known else [])+['top1','top10','truth_in','target_coverage'],s)
        assert int(s['n_bits_unknown'])==(0 if known else 36000)
        for k,v in area_intervals([float(r['area_ratio']) for r in rs]).items():equal(v,s[k])
        cells=[r for r in summaries.values() if all(r[k]==s[k] for k in ['list','policy','param'])]
        if known:equal(np.mean([float(r['exact_bits']) for r in cells]),s['exact_bits'])
        else:assert s['exact_bits']==s['bits']==s['bits_lo']==s['bits_hi']==''
    for c in spec['cells']:
        assert c['calibration_n']==400 and len(c['calibration_sha256'])==400
        assert all(len(h)==64 for h in c['calibration_sha256'])
        if c['unit'][0]=='digits':
            errors=np.array(c['calibration_edge_error'])
            tolerance=np.stack([np.floor(np.percentile(errors,.5,axis=0)),np.ceil(np.percentile(errors,99.5,axis=0))],axis=1)
            assert np.array_equal(tolerance,c['tolerance'])
    return dict(secondary_rows=nraw,secondary_summaries=432,pooled_summaries=24,calibration_per_cell=400,
                points_and_10000_resample_intervals_recomputed=True,policy_targets_and_pens_paired=True)

def main():
    result=archive();result.update(secondary());result.update(passed=True,numeric_checks=CHECKS,
        command='research/realworld_e1_eval/.venv/bin/python -B scripts/validate_v14_new_runs.py',validator_sha256=digest(__file__))
    (ROOT/'results/v1_4_archive/new_runs_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
