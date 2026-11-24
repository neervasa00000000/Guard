#!/usr/bin/env python3
"""Paired six-font secondary-list sweep using the pinned E1 clean renderer."""
from __future__ import annotations
import argparse,json,math,time
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import numpy as np
from rerun_common import ROOT,E,P,SEED,DRAWS,renderer,digest,text_hash,write,mean_intervals,area_intervals
OUT=ROOT/'data/email_digits'
SETTINGS=[('exact',1)]+[('square',g) for g in [8,16,32,64]]+[('width-only',64)]+[('start-aligned',c) for c in [64,128,192,256,384]]+[('field',0)]
N=2000;NCAL=400;TARGET_SEED=20261029

class Scores:
    """Geometry sufficient groups; scores exactly match E.metrics strict ties."""
    def __init__(self,dictionary,geometry):
        self.D=dictionary
        self.geometry,self.representatives,self.group=np.unique(geometry,axis=0,return_index=True,return_inverse=True)
        p=dictionary['p'];m=dictionary['m'];self.mass=np.bincount(self.group,weights=p*m)
        self.plog=np.bincount(self.group,weights=p*m*np.log2(p));self.h0=-float(self.plog.sum())
        self.priors=[];self.cumulative=[];self.lo=[];self.hi=[];self.n=[]
        for g in range(len(self.geometry)):
            ix=np.flatnonzero(self.group==g);ix=ix[np.argsort(p[ix],kind='stable')]
            self.priors.append(p[ix]);self.cumulative.append(np.r_[0,np.cumsum(m[ix])])
            self.lo.append(p[ix[0]]);self.hi.append(p[ix[-1]]);self.n.append(m[ix].sum())
        self.lo=np.array(self.lo);self.hi=np.array(self.hi);self.n=np.array(self.n)
    def score(self,mask,target):
        mask=np.asarray(mask,dtype=bool);truth=bool(mask[self.group[target]])
        if not mask.any():mask=np.ones(len(mask),dtype=bool)
        active=np.flatnonzero(mask);mass=float(self.mass[active].sum())
        bits=self.h0-(math.log2(mass)-float(self.plog[active].sum())/mass)
        if mask.all():bits=0.
        if not truth:return bits,0.,0.,False
        pt=self.D['p'][target];gt=float(self.n[active[self.lo[active]>pt]].sum());eq=0.
        if gt>=10:return bits,0.,0.,True
        for g in active[(self.lo[active]<=pt)&(self.hi[active]>=pt)]:
            values=self.priors[g];a=np.searchsorted(values,pt,side='left');b=np.searchsorted(values,pt,side='right');cum=self.cumulative[g]
            gt+=float(cum[-1]-cum[b]);eq+=float(cum[b]-cum[a])
            if gt>=10:return bits,0.,0.,True
        assert eq>0
        return bits,min(1.,max(0.,(1-gt)/eq)),min(1.,max(0.,(10-gt)/eq)),True

def entropy(prob,keys):
    _,inverse=np.unique(keys,axis=0,return_inverse=True)
    mass=np.bincount(inverse,weights=prob);return -float(np.dot(mass,np.log2(mass)))

def exact_email_bits(scorer,prep,policy,param):
    """Enumerate all names and pen phases, compressed by equivalent partitions."""
    g=scorer.geometry;p=scorer.mass
    if policy=='field':return 0.
    if policy=='exact':return entropy(p,np.arange(len(p)))
    if policy=='start-aligned':return entropy(p,P.class_index(g[:,2]+1,prep['x_l'],param))
    # Every phase is uniform: E1 pen ranges are exact multiples of each grid.
    assert (E.PEN_X[1]-E.PEN_X[0])%param==0 and (E.PEN_Y[1]-E.PEN_Y[0])%param==0
    from collections import Counter
    xs=Counter();ys=Counter()
    for phase in range(param):
        l=(g[:,0]-1+phase)//param;r=P.ceil_multiple(g[:,2]+1+phase,param)//param
        key=np.unique(np.column_stack([l,r]),axis=0,return_inverse=True)[1];xs[key.tobytes()]+=1
        if policy=='square':
            t=(g[:,1]-1+phase)//param;b=P.ceil_multiple(g[:,3]+1+phase,param)//param
            key=np.unique(np.column_stack([t,b]),axis=0,return_inverse=True)[1];ys[key.tobytes()]+=1
    if policy!='square':ys[np.zeros(len(g),dtype=np.int64).tobytes()]=param
    result=0.
    for x,nx in xs.items():
        for y,ny in ys.items():result+=nx*ny/param**2*entropy(p,np.column_stack([np.frombuffer(x,dtype=np.int64),np.frombuffer(y,dtype=np.int64)]))
    return result

def one_cell(unit):
    name,font,size=unit;start=time.monotonic();cache=OUT/'.cache';cache.mkdir(parents=True,exist_ok=True)
    saved=cache/f'{name}_{font}_{size}.npz';table=cache/f'{name}_{font}_{size}.csv.gz'
    signature=text_hash(json.dumps([digest(__file__),digest(ROOT/'scripts/rerun_common.py'),digest(E.checked_font_path(font)),N,NCAL,SETTINGS]))
    if saved.exists() and table.exists():
        with np.load(saved) as old:
            if json.loads(str(old['metadata'])).get('signature')==signature:return str(saved)
    D=E.get_dict(name);G=np.asarray(E.geometry(name,font,size),dtype=np.int64)
    assert len(G)==len(D['p']);face=E.font(font,size);asc,desc=face.getmetrics();prep=P.prepare(G,asc,desc)
    rng=np.random.default_rng([TARGET_SEED,list(E.DICTS).index(name),list(E.FONTS).index(font),size])
    chosen,strings=E.sample_targets(D,N,rng);x=rng.integers(*E.PEN_X,N);y=rng.integers(*E.PEN_Y,N)
    calibration,calstrings=E.sample_targets(D,NCAL,rng);cx=rng.integers(*E.PEN_X,NCAL);cy=rng.integers(*E.PEN_Y,NCAL)
    actual=np.array([face.getbbox(s,anchor='ls') for s in strings],dtype=np.int64)
    cal=np.array([face.getbbox(s,anchor='ls') for s in calstrings],dtype=np.int64)
    errors=cal-G[calibration]
    tolerance=tuple((int(np.floor(np.percentile(errors[:,j],.5))),int(np.ceil(np.percentile(errors[:,j],99.5)))) for j in range(4)) if name=='digits' else ((0,0),)*4
    target=P.prepare(actual,asc,desc);target['x_l']=prep['x_l'];target['line_top']=prep['line_top'];target['line_bottom']=prep['line_bottom']
    scorer=Scores(D,G);cell=E.Cell(scorer.geometry,tolerance,0)
    width_geom=scorer.geometry.copy();width_geom[:,1]=prep['line_top']+1;width_geom[:,3]=prep['line_bottom']-1
    width_cell=E.Cell(width_geom,(tolerance[0],(0,0),tolerance[2],(0,0)),0)
    hashes=[text_hash(s) for s in strings];lengths=[len(s) for s in strings]
    arrays={};raw=[];summ=[]
    for policy,param in SETTINGS:
        if policy=='exact':box=[target[k]+offset for k,offset in [('left',x),('top',y),('right',x),('bottom',y)]]
        elif policy in ['square','width-only']:
            box=list(P.square_grid(target,param,x,y))
            if policy=='width-only':box[1]=np.full(N,prep['line_top']);box[3]=np.full(N,prep['line_bottom'])
            box=[a+offset for a,offset in zip(box,[x,y,x,y])]
        elif policy=='start-aligned':box=[a+offset for a,offset in zip(P.start_aligned_padding(target,param),[x,y,x,y])]
        else:
            constant=P.field_box(prep)[:4];box=[np.full(N,int(a[0]))+offset for a,offset in zip(constant,[x,y,x,y])]
        observed=np.column_stack(box);area=(observed[:,2]-observed[:,0])*(observed[:,3]-observed[:,1])/target['tight_area']
        values=[];score_cache={}
        for i,idx in enumerate(chosen):
            relative=tuple(int(a-b) for a,b in zip(observed[i],[x[i],y[i],x[i],y[i]]))
            key=(int(idx),relative)
            if key not in score_cache:
                if policy=='field':mask=np.ones(len(scorer.geometry),bool)
                elif policy=='start-aligned':
                    lo=prep['x_l']+P.ceil_multiple(scorer.geometry[:,2]+1+tolerance[2][0]-prep['x_l'],param)
                    hi=prep['x_l']+P.ceil_multiple(scorer.geometry[:,2]+1+tolerance[2][1]-prep['x_l'],param)
                    mask=(lo<=relative[2])&(hi>=relative[2])
                else:
                    used=width_cell if policy=='width-only' else cell
                    mask=used.feasible([(int(observed[i,0]),int(observed[i,2]),int(observed[i,1]),int(observed[i,3]))],[(int(x[i]),int(y[i]))],param,'A1')
                score_cache[key]=scorer.score(mask,int(idx))
            bits,top1,top10,truth=score_cache[key]
            publish_bits=name=='emails' or policy=='field'
            if name=='emails':assert truth
            contained=(observed[i,0]<=x[i]+actual[i,0]-1 and observed[i,1]<=y[i]+actual[i,1]-1 and observed[i,2]>=x[i]+actual[i,2]+1 and observed[i,3]>=y[i]+actual[i,3]+1)
            values.append([bits if publish_bits else np.nan,top1,top10,area[i],float(truth),float(contained)])
            raw.append(dict(list=name,policy=policy,param=param,font=font,size_px=size,case=i,target_sha256=hashes[i],target_char_length=lengths[i],
                pen_x=int(x[i]),baseline_y=int(y[i]),box=','.join(map(str,observed[i])),bits=float(bits) if publish_bits else '',top1=float(top1),top10=float(top10),
                truth_in=truth,area_ratio=float(area[i]),target_fully_covered=contained))
        a=np.array(values);arrays[policy+'_'+str(param)]=a
        included=[0,1,2,4,5] if publish_bits else [1,2,4,5]
        point,low,high=mean_intervals(a[:,included]);metrics={}
        for j,k in enumerate(included):
            metric={0:'bits',1:'top1',2:'top10',4:'truth_in',5:'target_coverage'}[k]
            metrics.update({metric:float(point[j]),metric+'_lo':float(low[j]),metric+'_hi':float(high[j])})
        if not publish_bits:metrics.update(bits='',bits_lo='',bits_hi='')
        exact=exact_email_bits(scorer,prep,policy,param) if name=='emails' else (0. if policy=='field' else '')
        summ.append(dict(list=name,policy=policy,param=param,font=font,size_px=size,n=N,
            **metrics,**area_intervals(area),exact_bits=exact,
            bits_method='sampled estimate; exact prior/pen-phase enumeration also provided' if name=='emails' else ('constant field: exact zero' if policy=='field' else 'not computed: calibrated compressed digit model is not exact surname-style entropy inference'),
            n_bits=N if publish_bits else 0,n_bits_unknown=0 if publish_bits else N,
            calibration_n=NCAL,tolerance=json.dumps(tolerance,separators=(',',':'))))
    raw.sort(key=lambda r:(r['case'],SETTINGS.index((r['policy'],r['param']))))
    write(table,raw);write(cache/f'{name}_{font}_{size}_summary.csv',summ)
    arrays['metadata']=np.array(json.dumps(dict(unit=unit,signature=signature,tolerance=tolerance,calibration_n=NCAL,
        calibration_sha256=[text_hash(s) for s in calstrings],calibration_char_length=[len(s) for s in calstrings],
        calibration_pen_x=cx.tolist(),calibration_baseline_y=cy.tolist(),calibration_edge_error=errors.tolist(),
        source_font_sha256=digest(E.checked_font_path(font)),geometry_rows=len(G),prior_entropy=scorer.h0,elapsed_seconds=time.monotonic()-start)))
    with saved.open('wb') as f:np.savez_compressed(f,**arrays)
    print('Completed',name,font,size,'seconds',round(time.monotonic()-start,1),flush=True)
    return str(saved)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=6);args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True);versions=renderer()
    for name in ['emails','digits']:E.get_dict(name)
    units=[(d,f,s) for d in ['emails','digits'] for f in E.FONTS for s in E.SIZES]
    started=time.monotonic();paths=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(one_cell,u) for u in units]
        for f in as_completed(futures):paths.append(Path(f.result()))
    import gzip,csv,io
    summary=[];metadata=[]
    with (OUT/'per_target.csv.gz').open('wb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',mtime=0,filename='') as z,io.TextIOWrapper(z,newline='') as stream:
        writer=None
        for p in sorted(paths):
            with gzip.open(p.with_suffix('.csv.gz'),'rt',newline='') as f:
                r=csv.DictReader(f)
                if writer is None:writer=csv.DictWriter(stream,r.fieldnames,lineterminator='\n');writer.writeheader()
                writer.writerows(r)
            summary.extend(__import__('rerun_common').read(p.with_name(p.stem+'_summary.csv')))
            with np.load(p) as a:metadata.append(json.loads(str(a['metadata'])))
    write(OUT/'summary.csv',summary);pooled=[]
    for name in ['emails','digits']:
        for policy,param in SETTINGS:
            arrays=[]
            for p in sorted(paths):
                if p.name.startswith(name+'_'):
                    with np.load(p) as a:arrays.append(a[policy+'_'+str(param)])
            a=np.concatenate(arrays);known=np.isfinite(a[:,0]).all();included=[0,1,2,4,5] if known else [1,2,4,5]
            point,low,high=mean_intervals(a[:,included]);metrics={}
            for j,k in enumerate(included):
                metric={0:'bits',1:'top1',2:'top10',4:'truth_in',5:'target_coverage'}[k];metrics.update({metric:float(point[j]),metric+'_lo':float(low[j]),metric+'_hi':float(high[j])})
            if not known:metrics.update(bits='',bits_lo='',bits_hi='')
            cells=[r for r in summary if r['list']==name and r['policy']==policy and int(r['param'])==param]
            pooled.append(dict(list=name,policy=policy,param=param,n=len(a),**metrics,**area_intervals(a[:,3]),
                exact_bits=float(np.mean([float(r['exact_bits']) for r in cells])) if known else '',
                n_bits=len(a) if known else 0,n_bits_unknown=0 if known else len(a)))
    write(OUT/'table_pooled.csv',pooled)
    config=dict(status='complete',command='research/realworld_e1_eval/.venv/bin/python -B scripts/run_email_digits.py --workers '+str(args.workers),
        versions=versions,target_seed=TARGET_SEED,bootstrap_seed=SEED,bootstrap_resamples=DRAWS,n_per_cell=N,calibration_per_cell=NCAL,
        target_design='same 2000 independently generated targets and pen/baseline positions reused by all 12 policies; original E1 per-cell seed scheme',
        renderer='clean E1 ink_box equals Pillow getbbox(anchor=ls), RAQM; no scan/jpeg transformation',
        calibration='digits: independent 400 targets after evaluation-target/pen draws; per-edge floor/ceil 0.5/99.5 percentiles as e1_run.py; same tolerance propagated and frozen across policies',
        width_only='both horizontal edges snapped to page 64px grid, full font-line height; not the start-anchored width grid',
        field='one full-line fixed field across the bounded candidate list; digit list uses original 700 multiplicity classes; actual target containment reported',
        bits='Email primary bits are paired-target sample estimates with target-bootstrap CIs; exact_bits additionally enumerates full prior and all uniform pen phases. Digit bits unknown except geometry-constant field zero; no entropy inferred from calibrated prototype classes.',
        uncertainty='10k exact target-bootstrap means via multinomial sufficient counts; quantile marginal bootstrap via adjacent uniform order statistics; no joint/paired quantile CI claimed',
        pooled_design='all 36000 targets per list-policy pooled, not averaging cell medians; pooled exact_bits equally averages identical target-count font-size cells',
        policies=SETTINGS,workers=args.workers,cells=metadata,n_raw_rows=36*N*len(SETTINGS),n_summary_rows=len(summary),elapsed_seconds=time.monotonic()-started,
        source_sha256={p:digest(ROOT/p) for p in ['scripts/run_email_digits.py','scripts/rerun_common.py','research/e1/e1lib.py','research/e1/policies.py','research/e1/e1_run.py']})
    (OUT/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    (OUT/'README.md').write_text('# E-mail and digit sweep\n\nSix hash-verified fonts, sizes 12/16/24, 2000 paired targets per cell and 12 policies. All targets are synthetic; only hashes and character lengths are archived. Exact geometry comes from the pinned clean E1 RAQM renderer. Width-only grid snaps both horizontal edges to the page; start padding uses the shared list anchor.\n\nEmail bits are sampled target estimates with CIs; exact_bits separately enumerates the entire prior and every uniform pen phase, compressed only by identical observation partitions. Digit scoring retains the original multiplicity classes and independently calibrated 400-string edge tolerance; entropy inference is not exact for this approximate geometry model, so digit bits are explicitly unknown except the common field geometry (zero). n_bits_unknown records these omissions. Field target containment is separately reported.\n\nConfidence limits use 10000 target-bootstrap resamples, seed 20261121. Means use exact multinomial sufficient counts. Area quantiles use the mathematically identical marginal bootstrap generated from adjacent uniform order statistics; these are marginal intervals, not a joint paired confidence region. Pooled quantiles use all target-level areas.\n\nRun the command in config.json after obtaining checked font inputs. Per-cell numeric working files are cached under ignored .cache/. No fonts, rendered images, original document text or private keys are redistributed.\n')
    print('Completed sweep',len(summary),'cells/policies;',len(pooled),'pooled rows',flush=True)
if __name__=='__main__':main()
