#!/usr/bin/env python3
"""Documented 36-cell alternative-build sensitivity, without claiming lost provenance."""
import json,time
from pathlib import Path
import numpy as np
from PIL import ImageFont
from v14_runtime import ROOT,E,renderer,digest,text_hash,write,mean_intervals,SEED,DRAWS
from run_email_digits import Scores
def main():
    out=ROOT/'results/v1_4_archive/font_builds';spec=json.loads((out/'protocol.json').read_text());versions=renderer()
    assert spec['cells'].startswith('6 fonts x 3 sizes x A1/A2')
    paths={r['font']:ROOT/r['path'] for r in spec['fonts']}
    for r in spec['fonts']:
        assert digest(paths[r['font']])==r['sha256']
        assert digest(E.checked_font_path(r['font']))!=r['sha256'],'Alternative build is the baseline binary'
    d=E.get_dict('surnames');raw=[];summary=[];start=time.monotonic()
    for font in E.FONTS:
        for size in E.SIZES:
            rng=np.random.default_rng([20261029,list(E.DICTS).index('surnames'),list(E.FONTS).index(font),size])
            chosen,strings=E.sample_targets(d,2000,rng);pens=rng.integers(*E.PEN_X,2000);baseline=rng.integers(*E.PEN_Y,2000)
            a=E.font(font,size);b=ImageFont.truetype(str(paths[font]),size,layout_engine=ImageFont.Layout.RAQM)
            if font=='NotoSans':b.set_variation_by_name(b'Regular')
            norm=lambda s:''.join(c for c in s.lower() if c.isalnum())
            assert norm(a.getname()[0])==norm(b.getname()[0]),('Different family',a.getname(),b.getname())
            bounds=[np.array([f.getbbox(s,anchor='ls') for s in d['strings']],dtype=np.int32) for f in [a,b]]
            scorers=[Scores(d,g) for g in bounds]
            for attacker in ['A1','A2']:
                values=[]
                for i,target in enumerate(chosen):
                    scored=[]
                    for G,scorer in zip(bounds,scorers):
                        g=scorer.geometry;t=G[target]
                        mask=(g[:,1]==t[1])&(g[:,3]==t[3])
                        if attacker=='A1':mask&=(g[:,0]==t[0])&(g[:,2]==t[2])
                        else:
                            implied=pens[i]+t[0]-g[:,0]
                            mask&=((g[:,2]-g[:,0])==(t[2]-t[0]))&(implied>=E.PEN_X[0])&(implied<E.PEN_X[1])
                        bits,h1,h10,truth=scorer.score(mask,int(target));assert truth;scored.append((h1,h10,bits))
                    old,new=scored;delta=100*(new[1]-old[1])
                    values.append([*old,*new,delta,new[2]-old[2]])
                    raw.append(dict(font=font,size_px=size,attacker=attacker,case=i,target_sha256=text_hash(strings[i]),target_char_length=len(strings[i]),
                        baseline_top1=old[0],baseline_top10=old[1],baseline_bits=old[2],alternative_top1=new[0],alternative_top10=new[1],alternative_bits=new[2],delta_top10_pp=delta,delta_bits=new[2]-old[2]))
                point,lo,hi=mean_intervals(values);row=dict(font=font,size_px=size,attacker=attacker,n=2000,baseline_font_sha256=digest(E.checked_font_path(font)),alternative_font_sha256=digest(paths[font]))
                for j,key in enumerate(['baseline_top1','baseline_top10','baseline_bits','alternative_top1','alternative_top10','alternative_bits','delta_top10_pp','delta_bits']):row.update({key:float(point[j]),key+'_lo':float(lo[j]),key+'_hi':float(hi[j])})
                row['absolute_delta_top10_pp']=abs(row['delta_top10_pp']);row['shift_at_least_4pp']=row['absolute_delta_top10_pp']>=4
                summary.append(row)
            print('Completed alternative build',font,size,flush=True)
    write(out/'raw.csv.gz',raw);write(out/'summary.csv',summary)
    changed=[r for r in summary if r['shift_at_least_4pp']]
    config=dict(status='complete_new_sensitivity_run',command='research/realworld_e1_eval/.venv/bin/python -B scripts/run_archive_font_builds.py',
        versions=versions,target_seed=20261029,bootstrap_seed=SEED,bootstrap_resamples=DRAWS,
        original_manifest_available=False,historical_claim_status='unverified: original alternative-build identities and exact cell definition were not archived; this explicitly defined rerun is not presented as the original experiment',
        cell_definition=spec['cells'],protocol_sha256=digest(out/'protocol.json'),script_sha256=digest(__file__),n_cells=len(summary),n_cells_shift_at_least_4pp=len(changed),
        shifted_pp=[r['absolute_delta_top10_pp'] for r in changed],elapsed_seconds=time.monotonic()-start)
    (out/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    (out/'README.md').write_text('# Alternative font-build sensitivity\n\nThis new run defines the previously unspecified 36 cells as six fonts × three sizes × A1/A2, on exact clean surname layout boxes and the original seeded 2000 targets per font-size. Both sides use their own matched renderer; A2 respects the finite uniform pen support. Builds and thresholds were frozen in protocol.json before scoring.\n\n'+str(len(changed))+' of 36 cells shift by at least 4 percentage points. This does not verify the historical “2 of 36, 4–9 points” claim because the original alternative binaries and cell definition were not archived. No builds were chosen after observing scores. The explicit modern sensitivity experiment and its paired target-bootstrap CIs are fully recorded; the historical claim remains marked unverified. Font binaries and target strings are not redistributed.\n')
    print('Alternative builds:',len(changed),'of 36 cells shift >=4pp',flush=True)
if __name__=='__main__':main()
