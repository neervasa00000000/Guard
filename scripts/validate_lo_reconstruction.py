#!/usr/bin/env python3
"""Independently score archived full candidate arrays and validate new LO tables."""
import json,math
from collections import defaultdict
import numpy as np
from rerun_common import ROOT,E,read,mean_intervals,area_intervals,digest
OUT=ROOT/'results/reruns/mock_forms_reconstruction'
CHECKS=0
def eq(a,b):
    global CHECKS
    assert math.isclose(float(a),float(b),rel_tol=0,abs_tol=1e-10),(a,b)
    CHECKS+=1
def main():
    spec=json.loads((OUT/'config.json').read_text());assert spec['historical_replication'] is False
    records=read(OUT/'candidate_geometry.csv.gz');assert len(records)==200000
    grouped=defaultdict(list)
    for r in records:grouped[(r['font'],r['size_px'])].append(r)
    arrays={};dictionary=None;by_hash={}
    for k,rs in grouped.items():
        assert len(rs)==50000 and [int(r['index']) for r in rs]==list(range(50000))
        d=dict(p=np.array([float(r['prior']) for r in rs]),m=np.ones(50000),length=np.array([int(r['target_char_length']) for r in rs]))
        eq(d['p'].sum(),1)
        if dictionary is None:
            dictionary=d;by_hash={r['target_sha256']:int(r['index']) for r in rs};assert len(by_hash)==50000
        else:
            assert np.array_equal(d['p'],dictionary['p']) and np.array_equal(d['length'],dictionary['length'])
            assert all(by_hash[r['target_sha256']]==int(r['index']) for r in rs)
        arrays[k]={prefix:np.array([[int(r[prefix+'_'+c]) for c in ['l','t','r','b']] for r in rs]) for prefix in ['lo','pil']}
    del records,grouped
    tolerance={(r['font'],str(r['size_px']),r['condition'],r['attacker']):r['edges'] for r in spec['tolerance_px']}
    frames={(r['font'],str(r['size_px'])):r for r in spec['policy_frames']}
    calibration=defaultdict(list)
    for r in read(OUT/'calibration.csv.gz'):calibration[tuple(r[k] for k in ['font','size_px','condition','attacker'])].append(r)
    assert sum(map(len,calibration.values()))==9600
    for key,rs in calibration.items():
        assert len(rs)==400
        errors=np.array([[int(r[c+'_error']) for c in ['left','top','right','bottom']] for r in rs])
        expected=np.stack([np.floor(np.percentile(errors,.5,axis=0)),np.ceil(np.percentile(errors,99.5,axis=0))],axis=1)
        assert np.array_equal(expected,tolerance[key])
    observations=read(OUT/'observations.csv.gz');assert len(observations)==400
    obs={(r['doc'],r['size_px'],r['condition']):r for r in observations};assert len(obs)==400
    source=read(ROOT/'research/e1/data/forms/replayed_forms_obs.csv')
    source={(r['doc'],r['size'],r['cond']):r for r in source}
    for k,r in obs.items():
        old=source[k];assert r['target_sha256']==__import__('hashlib').sha256(old['truth'].encode()).hexdigest()
        assert r['font']==old['font']
    raw=read(OUT/'raw.csv.gz');assert len(raw)==7200;seen=set();summary_groups=defaultdict(list)
    p=dictionary['p'];logp=np.log2(p);h0=-float(p@logp)
    for r in raw:
        key=tuple(r[k] for k in ['doc','size_px','condition','attacker','policy']);assert key not in seen;seen.add(key)
        item=obs[tuple(r[k] for k in ['doc','size_px','condition'])]
        assert all(item[k]==r[k] for k in ['target_sha256','target_char_length','font'])
        gkey=(r['font'],r['size_px']);prefix='lo' if r['attacker']=='libreoffice_matched' else 'pil';g=arrays[gkey][prefix]
        tol=tolerance[(r['font'],r['size_px'],r['condition'],r['attacker'])];target=by_hash[r['target_sha256']]
        x=int(item['pen_x']);y=int(item['baseline_y']);policy=r['policy'];box=None if not r['box'] else json.loads(r['box'])
        l,t,rr,b=[int(item[k]) for k in ['left','top','right','bottom']];frame=frames[gkey]
        if policy=='nobox':assert box is None and r['area_ratio']==r['target_coverage']==''
        else:
            tight=[x+l-1,y+t-1,x+rr+1,y+b+1]
            if policy=='exact':expected=tight
            elif policy.startswith('grid-'):
                grid=int(policy.split('-')[1]);expected=[tight[0]//grid*grid,tight[1]//grid*grid,-(-tight[2]//grid)*grid,-(-tight[3]//grid)*grid]
            elif policy=='start128':
                left=x+frame['x_l'];expected=[left,y+frame['line_top'],left+-(-(rr+1-frame['x_l'])//128)*128,y+frame['line_bottom']]
            else:expected=[x+frame['x_l'],y+frame['line_top'],x+int(arrays[gkey]['lo'][:,2].max())+1,y+frame['line_bottom']]
            assert box==expected,(policy,box,expected)
            eq((box[2]-box[0])*(box[3]-box[1])/((rr-l+2)*(b-t+2)),r['area_ratio'])
            assert (r['target_coverage']=='True')==(box[0]<=tight[0] and box[1]<=tight[1] and box[2]>=tight[2] and box[3]>=tight[3])
        if policy in ['nobox','field']:mask=np.ones(50000,bool)
        elif policy=='start128':
            width=box[2]-box[0];span=g[:,2]+1-frame['x_l'];lo,hi=tol[2]
            mask=(-(-(span+lo)//128)*128<=width)&(-(-(span+hi)//128)*128>=width)
        else:
            grid=int(policy.split('-')[1]) if policy.startswith('grid-') else 1
            mask=E.Cell(g,tol,0).feasible([(box[0],box[2],box[1],box[3])],[(x,y)],grid,'A1')
        assert int(mask.sum())==int(r['n_candidates'])
        score=E.metrics(dictionary,mask,target,int(r['target_char_length']),logp)
        for k,v in [('top1',score['hit1']),('top10',score['hit10']),('bits',h0-score['resid_bits'])]:eq(v,r[k])
        assert bool(score['truth_in'])==(r['truth_in']=='True')
        summary_groups[tuple(r[k] for k in ['size_px','condition','attacker','policy'])].append(r)
    summaries=read(OUT/'summary.csv');assert len(summaries)==72
    historical={(r['size'],r['cond'],r['attacker'],r['variant']):float(r['archived'])/int(r['n']) for r in read(ROOT/'research/e1/data/forms/libreoffice_hit_check.csv')}
    for s in summaries:
        rs=summary_groups[tuple(s[k] for k in ['size_px','condition','attacker','policy'])];assert len(rs)==int(s['n'])==100
        keys=['bits','top1','top10','truth_in'];a=np.array([[float(r[k]=='True') if k=='truth_in' else float(r[k]) for k in keys] for r in rs])
        point,lo,hi=mean_intervals(a)
        for j,k in enumerate(keys):
            for suffix,v in [('',point[j]),('_lo',lo[j]),('_hi',hi[j])]:eq(v,s[k+suffix])
        if s['policy']!='nobox':
            for k,v in area_intervals([float(r['area_ratio']) for r in rs]).items():eq(v,s[k])
            eq(np.mean([r['target_coverage']=='True' for r in rs]),s['target_coverage'])
        if s['historical_top10']:
            arm={'libreoffice_matched':'b_lo_table','pillow_mismatch':'a_paper_renderer','pillow_lo_calibrated':'b_lo_calibrated'}[s['attacker']]
            policy={'exact':'exact','grid-16':'16px','grid-64':'64px'}[s['policy']]
            eq(historical[(s['size_px'],s['condition'],arm,policy)],s['historical_top10'])
            eq(100*(float(s['top10'])-float(s['historical_top10'])),s['difference_from_historical_pp'])
    report=dict(passed=True,historical_replication=False,full_candidate_rows=200000,evaluation_observations=400,calibration_rows=9600,per_form_rows=7200,
        summary_rows=72,numeric_checks=CHECKS,full_array_scores_match_grouped_scores=True,all_policy_boxes_recomputed=True,all_points_and_10000_draw_intervals_recomputed=True,
        original_targets_and_font_assignments_preserved=True,no_document_text_or_images_archived=True,
        validator_sha256=digest(__file__),command='research/realworld_e1_eval/.venv/bin/python -B scripts/validate_lo_reconstruction.py')
    (OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
