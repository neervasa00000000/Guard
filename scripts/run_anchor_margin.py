#!/usr/bin/env python3
"""Exact prior-weighted anchor-margin channels, using retained E1 geometry."""
from __future__ import annotations
import argparse,csv,gzip,hashlib,io,json,math,os,pickle,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
os.environ['E1_CENSUS']=str(ROOT/'data/census/Names_2010Census.csv')
sys.path.insert(0,str(ROOT/'research/e1'))
import e1lib as E
import policies as P
import run_tail as T
import run_perturb as R

MARGINS=(0,2,4,8,16)
WIDTHS=(64,96,128,192,256)
ERRORS={'clean':(0,), 'start_uniform_-2_2':tuple(range(-2,3)),
        'start_uniform_-4_4':tuple(range(-4,5)), 'class_width_pm8':(-8,8)}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    with Path(p).open(newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    with Path(p).open('w',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def quantile(x,w,q):
    order=np.argsort(x,kind='stable');x=np.asarray(x)[order];w=np.asarray(w)[order]
    return float(x[min(int(np.searchsorted(np.cumsum(w),q*w.sum(),side='left')),len(x)-1)])

def channel(spans,counts,margin,width,error,font,size,heights,tight):
    """Start errors are visible in the anchor; width errors share an output channel."""
    p=counts/counts.sum();n=len(p);states=ERRORS[error];allrows=[];areas=[];areap=[];extras=[]
    policies='start-aligned' if width else 'fixed-field'
    contexts=[states] if error=='class_width_pm8' else [(e,) for e in states]
    for ctx in contexts:
        context_weight=1/len(contexts)
        emissions=[]
        for delta in ctx:
            shift=delta if error.startswith('start_') else 0
            actual_width=width+delta if error=='class_width_pm8' and width else width
            painted=P.ceil_multiple(spans+margin-shift,actual_width) if width else np.full(n,int(spans.max())+margin-shift)
            base=P.ceil_multiple(spans-shift,actual_width) if width else np.full(n,int(spans.max())-shift)
            # Field start errors move a shared rectangle; they never split the list.
            assert (painted>0).all()
            emissions.append(painted.astype(np.int64))
            prob=context_weight/len(ctx)
            areas.append(painted*heights/tight);areap.append(p*prob)
            extras.append((painted-base)/base)
        emitted=np.stack(emissions)
        for observed in np.unique(emitted):
            likelihood=np.mean(emitted==observed,axis=0)
            eligible=likelihood>0
            joint=p*likelihood;mass=float(joint.sum())
            point=np.log2(likelihood[eligible]/mass)
            # Clamp numerical zero only, consistently with run_perturb.py.
            point[np.abs(point)<1e-12]=0.
            contrib=float(np.dot(joint[eligible],point))*context_weight
            allrows.append(dict(font=font,size_px=size,margin_px=margin,C_px=width,policy=policies,
                template_error=error,visible_start_error=ctx[0] if error!='class_width_pm8' else '',
                released_width_px=int(observed),context_probability=context_weight,
                prior_mass=float(p[eligible].sum()),output_probability=mass,joint_mass=context_weight*mass,names=int(eligible.sum()),
                min_likelihood=float(likelihood[eligible].min()),max_likelihood=float(likelihood[eligible].max()),
                pointwise_bits=float(point.max()),information_contribution=contrib))
    worst=max(allrows,key=lambda r:r['pointwise_bits'])
    row=dict(font=font,size_px=size,margin_px=margin,C_px=width,policy=policies,template_error=error,
        avg_bits=math.fsum(r['information_contribution'] for r in allrows),
        max_pointwise_bits=worst['pointwise_bits'],max_class_names=worst['names'],max_class_mass=worst['prior_mass'],
        n_singletons=math.fsum(r['context_probability'] for r in allrows if r['names']==1),
        singleton_mass=math.fsum(r['joint_mass'] for r in allrows if r['names']==1),
        mass_lt10=math.fsum(r['joint_mass'] for r in allrows if r['names']<10),
        mass_lt100=math.fsum(r['joint_mass'] for r in allrows if r['names']<100),
        area_median=quantile(np.concatenate(areas),np.concatenate(areap),.5),
        area_p90=quantile(np.concatenate(areas),np.concatenate(areap),.9),
        extra_area_vs_m0=float(np.dot(np.concatenate(extras),np.concatenate(areap))))
    assert math.isclose(sum(r['joint_mass'] for r in allrows),1.,abs_tol=1e-12)
    assert row['avg_bits']>=-1e-12 and row['singleton_mass']<=row['mass_lt10']+1e-12
    return row,allrows

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--geometry',type=Path,default=ROOT/'out/retained-geom')
    parser.add_argument('--out',type=Path,default=ROOT/'data/v1_5_anchor_margin')
    args=parser.parse_args();out=args.out;out.mkdir(parents=True,exist_ok=True)
    assert sha(E.CENSUS)==E.FULL_CENSUS_SHA
    names,counts=E.census(50000);counts=np.array(counts,dtype=np.int64)
    assert len(names)==len(set(names))==50000
    receipts={(r['font'],int(r['size_px'])):r for r in read(ROOT/'research/e1/data/v1_3/geometry_receipts.csv')}
    tail={(r['font'],int(r['size_px']),r['policy'],int(r['width_px'])):r for r in read(ROOT/'research/e1/data/v1_3/tail_summary.csv') if r['font']!='pooled'}
    oldclasses=read(ROOT/'research/e1/data/v1_3/tail_per_class.csv')
    archived=json.loads((ROOT/'research/e1/data/v1_2/run.json').read_text())['sources']
    checks=[];error_checks=[];inputs=[];summary=[];classes=[]
    for font in E.FONTS:
        for size in E.SIZES:
            path=args.geometry/f'geom_surnames_{font}_{size}.pkl'
            a=np.load(path,allow_pickle=True)
            assert a.shape==(50000,4) and a.dtype.kind in 'iu'
            receipt=hashlib.sha256(pickle.dumps(np.ascontiguousarray(a),protocol=4)).hexdigest()
            assert receipt==receipts[font,size]['geometry_sha256']
            params=archived[f'{font}/{size}']
            if 'metrics' in params:
                asc,desc=params['metrics'];height=max(desc,int(a[:,3].max()))-min(-asc,int(a[:,1].min()))+2
            else:height=params['recovered_line_height']
            assert height>=int(a[:,3].max()-a[:,1].min())+2
            left=int(a[:,0].min())-E.PAD;spans=a[:,2].astype(np.int64)+E.PAD-left
            tight=(a[:,2]-a[:,0]+2*E.PAD)*(a[:,3]-a[:,1]+2*E.PAD)
            assert (tight>0).all()
            inputs.append(dict(font=font,size_px=size,path=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                sha256=sha(path),geometry_receipt=receipt,anchor_m0=left,line_height_px=height))
            for margin in MARGINS:
                for width in (*WIDTHS,0):
                    for error in ERRORS:
                        row,rs=channel(spans,counts,margin,width,error,font,size,height,tight)
                        summary.append(row);classes.extend(rs)
                        if width:
                            group=R.compress(spans+margin,counts);total=int(counts.sum());peak=int(counts.max())
                            if error=='clean':reference=R.partition(group,0,width,total,peak)
                            elif error.startswith('start_'):reference=R.average_shifts(group,ERRORS[error],width,total,peak)
                            else:reference=R.class_width_channel(group,width,total,peak)
                            for key,col in [('avg_bits','mean_bits'),('max_pointwise_bits','max_pointwise_bits'),('mass_lt100','prior_pct_lt100')]:
                                actual=row[key]*(100 if key=='mass_lt100' else 1);expected=reference[col]
                                assert math.isclose(actual,expected,abs_tol=1e-11),(font,size,margin,width,error,key,actual,expected)
                                error_checks.append(dict(font=font,size_px=size,margin_px=margin,C_px=width,template_error=error,metric=key,
                                    computed=actual,existing_error_model=expected,absolute_difference=abs(actual-expected),matches=True))
                        if margin==0 and error=='clean':
                            old=tail[font,size,row['policy'],width]
                            for key,col in [('avg_bits','mean_bits'),('max_pointwise_bits','max_pointwise_bits'),
                                            ('max_class_names','max_class_names'),('max_class_mass','max_class_prior_mass')]:
                                got=float(row[key]);expected=float(old[col]);assert math.isclose(got,expected,abs_tol=1e-12),(font,size,width,key,got,expected)
                                checks.append(dict(font=font,size_px=size,C_px=width,metric=key,computed=got,archived=expected,absolute_difference=abs(got-expected),matches=True))
                            for key,col in [('mass_lt10','prior_pct_lt10'),('mass_lt100','prior_pct_lt100')]:
                                assert math.isclose(100*row[key],float(old[col]),abs_tol=1e-12)
                            keys=P.class_index(spans+left,left,width) if width else np.ones(len(spans),dtype=np.int64)
                            legacy=T.classes(counts,keys,font,size,row['policy'],width)
                            saved=[r for r in oldclasses if r['font']==font and int(r['size_px'])==size and r['policy']==row['policy'] and int(r['width_px'])==width]
                            assert len(legacy)==len(saved)
                            for r,s in zip(legacy,saved):
                                assert r['k']==int(s['k']) and r['names']==int(s['names'])
                                assert r['prior_mass']==float(s['prior_mass']) and r['pointwise_bits']==float(s['pointwise_bits'])
            print('Verified and evaluated',font,size,flush=True)
    write(out/'summary.csv',summary);write(out/'m0_checks.csv',checks);write(out/'error_model_checks.csv',error_checks)
    with (out/'per_class.csv.gz').open('wb') as f,gzip.GzipFile(fileobj=f,mode='wb',filename='',mtime=0) as z,io.TextIOWrapper(z,newline='') as text:
        w=csv.DictWriter(text,list(classes[0]),lineterminator='\n');w.writeheader();w.writerows(classes)
    config=dict(status='complete',n_surnames=50000,margins_px=MARGINS,C_px=WIDTHS,field_C_px=0,template_errors=ERRORS,
        enumeration='Exact full-list prior-weighted channel enumeration; no sampling uncertainty or bootstrap intervals',
        seed=20261121,bootstrap_resamples=10000,bootstrap_executed=False,
        start_anchor='same global list anchor x_L as run_tail.py, minus margin m; m=0 is exactly the archived policy',
        start_error='anchor shifts by uniform e; visible anchor reveals e; report conditional channel averaged over e',
        width_error='C is replaced by C-8 or C+8 with equal probability; only released width observed; marginalize latent delta as run_perturb.py',
        singleton_count='expected number of singleton output classes across visible start-error states; may be fractional',
        max_class_mass='sum of original priors of names compatible with the worst pointwise output; output_probability separately records likelihood-weighted output mass; stochastic-width pointwise bits=log2(likelihood/output_probability)',
        areas='prior-weighted left-continuous quantiles over all names and error draws; requested box is layout bounds plus PAD on all sides; full-line height from archived v1_2 metrics',
        extra_area_vs_m0='prior/error-weighted mean of (painted_area_m - painted_area_0)/painted_area_0, paired on name and error state',
        field='one full-50000-name field per font-size, anchor x_L-m+e, common right edge max padded right; width errors do not change the field',
        numpy=np.__version__,python=sys.version,census_sha256=sha(E.CENSUS),geometry=inputs,
        source_sha256={s:sha(ROOT/s) for s in ['scripts/run_anchor_margin.py','scripts/run_tail.py','scripts/run_perturb.py','research/e1/policies.py','research/e1/data/v1_2/run.json','research/e1/data/v1_3/tail_summary.csv','research/e1/data/v1_3/tail_per_class.csv']},
        command='.venv/bin/python -B scripts/run_anchor_margin.py',n_summary_rows=len(summary),n_class_rows=len(classes),m0_summary_checks=len(checks),m0_class_checks_pass=True,
        existing_error_model_checks=len(error_checks))
    (out/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    lines=['# Anchor-margin sweep','',f'Exact enumeration of all 50,000 prior-weighted Census surnames, 18 font-size cells, five margins, five class widths plus the field, and four error conditions. {len(summary)} summary rows; {len(classes)} class rows. All zero-margin clean class masses/counts/pointwise bits match tail_per_class.csv exactly; {len(checks)} summary checks agree within 1e-12. All {len(error_checks)} checks against the existing run_perturb.py error-channel functions pass within 1e-11.','',
        'This analysis reuses receipt-matched retained geometry, including Noto Sans; it does not claim a fresh Noto render. No names, fonts or raw geometry are redistributed. Full-line heights come from archived renderer metrics. Exact population quantities have no target-sampling confidence interval; seed and bootstrap defaults are recorded, but no bootstrap is performed.','',
        'The anchor is x_L - m, so m=0 is the paper policy. Start errors are visible in the released anchor and are conditioned on, as in run_perturb.py. Width errors are latent, so the two width channels are marginalized. A field always has one candidate class. Safety margins do not establish target containment under positive start errors.','',
        'Area quantiles are prior-weighted, unlike the earlier sampled area summaries. extra_area_vs_m0 is the expected fractional area increase paired by name and error draw. n_singletons is the conditional expected number of singleton classes for start-error rows. mass_lt10/mass_lt100/singleton_mass are fractions, not percent.','',
        'Run from repository root: `.venv/bin/python -B scripts/run_anchor_margin.py`. Provide the hash-verified Census CSV and retained geometry at the paths in config.json. No previous outputs are overwritten.','',
        '| Margin px | C px | Mean bits, equal-weight 18 cells | Worst pointwise bits | Mean extra area % |','|---:|---:|---:|---:|---:|']
    for m in MARGINS:
        for c in (*WIDTHS,0):
            rs=[r for r in summary if r['margin_px']==m and r['C_px']==c and r['template_error']=='clean']
            lines.append(f'| {m} | {c} | {np.mean([r["avg_bits"] for r in rs]):.6f} | {max(r["max_pointwise_bits"] for r in rs):.6f} | {100*np.mean([r["extra_area_vs_m0"] for r in rs]):.4f} |')
    (out/'README.md').write_text('\n'.join(lines)+'\n')
    print('Wrote',len(summary),'summary rows;',len(checks),'zero-margin checks passed; summary sha256',sha(out/'summary.csv'))

if __name__=='__main__':main()
