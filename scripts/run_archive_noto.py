#!/usr/bin/env python3
"""Freshly render pinned Noto knowledge-matched cells and compare every archived target."""
import argparse,json,pickle,time
import numpy as np
from rerun_common import ROOT,E,P,renderer,read,write,digest,text_hash,mean_intervals,area_intervals,SEED,DRAWS
import run_knowledge_matched as R
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=__import__('pathlib').Path,default=ROOT/'results/reruns/noto_rerender');args=parser.parse_args()
    out=args.out;out.mkdir(parents=True,exist_ok=True);versions=renderer();full=E.dict_surnames();names,counts=E.census(1000)
    short=E._finish(names,counts,np.ones(1000),{'source':'Census head'});rows=[];summary=[];geometry=[]
    receipts={(r['font'],int(r['size_px'])):r['geometry_sha256'] for r in read(ROOT/'research/e1/data/per_person/geometry_receipts.csv')}
    start=time.monotonic()
    for size in E.SIZES:
        face=E.font('NotoSans',size)
        bounds=np.array([face.getbbox(s,anchor='ls') for s in full['strings']],dtype=np.int32)
        sha=__import__('hashlib').sha256(pickle.dumps(np.ascontiguousarray(bounds),protocol=4)).hexdigest()
        old=np.load(ROOT/f'out/retained-geom/geom_surnames_NotoSans_{size}.pkl',allow_pickle=True)
        differences=int(np.any(bounds!=old,axis=1).sum())
        geometry.append(dict(font='NotoSans',size_px=size,n=50000,differing_names=differences,fresh_receipt=sha,archived_receipt=receipts['NotoSans',size],matches=sha==receipts['NotoSans',size]))
        assert differences==0 and geometry[-1]['matches'],'Fresh Noto geometry differs; report rather than substitute'
        asc,desc=face.getmetrics();prep=P.prepare(bounds[:1000],asc,desc)
        chosen,x,y=R.targets(short,'NotoSans',size)
        archive=[r for r in read(ROOT/f'research/e1/cases/knowledge_matched/cases_{size}px.csv.gz') if r['font']=='NotoSans']
        index={(r['policy'],int(r['width_px']),int(r['case'])):r for r in archive}
        for policy,width in R.SETTINGS:
            if policy=='square':
                box=P.square_grid({**prep,**{k:prep[k][chosen] for k in ['left','top','right','bottom']}},width,x,y)
                bits,hits=R.square_scores(prep,short['p'],chosen,x,y,width)
            else:
                if policy=='field':candidate=P.field_box(prep)[:4]
                elif policy=='start-aligned':candidate=P.start_aligned_padding(prep,width)
                else:candidate=P.start_anchored_grid(prep,width)
                b,h=P.class_attack(short['p'],candidate[2]);bits,hits=b[chosen],h[chosen];box=[a[chosen] for a in candidate]
            area=R.obs_area(box,prep['tight_area'][chosen]);block=[]
            for i,target in enumerate(chosen):
                oldrow=index[policy,width,i]
                row=dict(font='NotoSans',size_px=size,policy=policy,param=width,case=i,target_sha256=text_hash(short['strings'][target]),target_char_length=len(short['strings'][target]),
                    bits=float(bits[i]),top10=float(hits[i]),area_ratio=float(area[i]),
                    archived_bits=float(oldrow['bits']),archived_top10=float(oldrow['hit10']),archived_area_ratio=float(oldrow['area_ratio']))
                row.update(bits_difference=row['bits']-row['archived_bits'],top10_difference=row['top10']-row['archived_top10'],area_difference=row['area_ratio']-row['archived_area_ratio'])
                assert all(abs(row[k])<1e-9 for k in ['bits_difference','top10_difference','area_difference'])
                block.append(row);rows.append(row)
            point,lo,hi=mean_intervals(np.column_stack([bits,hits]))
            summary.append(dict(font='NotoSans',size_px=size,policy=policy,param=width,n=2000,bits=float(point[0]),bits_lo=float(lo[0]),bits_hi=float(hi[0]),top10=float(point[1]),top10_lo=float(lo[1]),top10_hi=float(hi[1]),
                **area_intervals(area),max_abs_bits_difference=max(abs(r['bits_difference']) for r in block),max_abs_top10_difference=max(abs(r['top10_difference']) for r in block),max_abs_area_difference=max(abs(r['area_difference']) for r in block)))
        print('Fresh Noto geometry and knowledge-matched target scores match:',size,flush=True)
    write(out/'raw.csv.gz',rows);write(out/'summary.csv',summary);write(out/'geometry_checks.csv',geometry)
    config=dict(status='complete',command='research/realworld_e1_eval/.venv/bin/python -B scripts/run_archive_noto.py',versions=versions,target_seed=R.SEED,bootstrap_seed=SEED,bootstrap_resamples=DRAWS,
        bootstrap='exact target-bootstrap means via multinomial sufficient counts; marginal quantile CIs via exact adjacent uniform order statistics',
        original_code_sha256=digest(ROOT/'scripts/run_knowledge_matched.py'),script_sha256=digest(__file__),elapsed_seconds=time.monotonic()-start,
        n_target_policy_rows=len(rows),n_summary_rows=len(summary),geometry_mismatches=sum(r['differing_names'] for r in geometry),all_target_scores_match=True,
        comparison='Noto-specific archived per-target knowledge-matched rows; old summary.csv pools fonts so is not compared to a single-font mean',font_source_config_sha256=digest(ROOT/'results/reruns/noto_source/config.json'))
    (out/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    (out/'README.md').write_text('# Fresh pinned Noto replay\n\nThe exact manifest font was recovered and all 150,000 freshly rendered surname bounds match retained geometry. All 126,000 Noto target-policy scores (bits, top-10 and area) reproduce the archived knowledge-matched per-target rows within 1e-9. Old tables were read only. The old summary pools fonts; Noto-specific comparisons use its original per-target rows.\n\nRun with the pinned study interpreter as recorded in config.json. Obtain the checked font with scripts/fetch_pinned_noto.py. No font binaries, names, images or original document text are distributed. New intervals use 10,000 target-bootstrap draws, seed 20261121.\n')
    print('Completed fresh Noto replay',len(rows),'rows',flush=True)
if __name__=='__main__':main()
