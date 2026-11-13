"""Exact-likelihood rescoring of PUBLISHED width-only (A2) observations, clean images, main sweep and D2 padding.
Generator (e1_run.py/e1lib.py): pen x ~ U{64..1023}, baseline y ~ U{64..959}; tight box = ink bbox(w) + 1 px;
snapped outward to grid g (page-aligned); D2: width rounded up to a multiple of 128 px, height = full line.
A2 knows the baseline (so y is deterministic given w) but not pen x. Then
  P(b | w) = #{px in [64,1023] : snap(px+L_w, px+R_w) = (X0,X1)} / 960  (times the 0/1 vertical match),
which differs between candidates when g > 1 (it depends on the width modulo g). Published code ranked and scored
p(w) restricted to {w : count > 0, ignoring the pen range}; here p(w|b) ~ p(w) P(b|w).
Units whose clean tolerance is non-zero (digits in Liberation Sans/Serif) keep the tolerance (model-based), flagged."""
import sys,os,math,json,numpy as np,pandas as pd
from multiprocessing import Pool
import e1lib as E
OUT = E.RUN_ROOT / 'csv'
C = OUT / 'cases'
PX0,PX1=E.PEN_X[0],E.PEN_X[1]-1
def init_tolerance():
    global TOL
    summary = pd.read_csv(OUT / 'e1_summary.csv')
    clean = summary[(summary.variant == 'main') & (summary.condition == 'clean') &
                    (summary.grid_px == 1) & (summary.attacker == 'A2')]
    TOL = {f'{row.dict}_{row.font}_{row.size_px}': json.loads(row.tol)
           for row in clean.itertuples(index=False)}
def scores(D,w8,ti,lens_true):
    """w8: per-entry unnormalised posterior weight per string (p*lik); returns hit1,hit10,len_ok,H,truth_in"""
    p=D['p'];m=D['m'];F=w8>0;truth_in=bool(F[ti])
    if not F.any():F=np.ones_like(F);w8=p.copy()
    q=w8[F];mf=m[F];W=(q*mf);Z=W.sum()
    H=math.log2(Z)-float((W*np.log2(q)).sum())/Z
    qt=w8[ti]
    if truth_in:
        gt=float(mf[q>qt*(1+1e-12)].sum());eq=float(mf[np.abs(q-qt)<=qt*1e-12].sum())
        h=lambda k:min(1.0,max(0.0,(k-gt)/eq))
    else:h=lambda k:0.0
    lm=np.bincount(D['length'][F],weights=W);lc=int(np.argmax(lm))
    return h(1),h(10),float(lc==lens_true),H,float(truth_in)
def unit(a):
    dn,fn,sz=a;D=E.get_dict(dn);p=D['p']
    tol=TOL[f'{dn}_{fn}_{sz}'];(dl0,dl1),(dt0,dt1),(dr0,dr1),(db0,db1)=tol;exact=all(x==0 for e in tol for x in e)
    T=pd.read_csv(f'{C}/{dn}_{fn}_{sz}_targets.csv.gz',dtype={'target':str},keep_default_na=False);X=pd.read_csv(f'{C}/{dn}_{fn}_{sz}.csv.gz')
    X=X[(X.condition=='clean')&(X.attacker=='A2')&X.variant.isin(['main','D2_bucket128'])]
    G0=E.geometry(dn,fn,sz).astype(np.int64);GB=E.bucket_transform(E.geometry(dn,fn,sz),fn,sz).astype(np.int64)
    out=[]
    for (var,g),R in X.groupby(['variant','grid_px']):
        G=GB if var=='D2_bucket128' else G0;l,t,r,b=G.T
        Llo=l-E.PAD+dl0;Lhi=l-E.PAD+dl1;Rlo=r+E.PAD+dr0;Rhi=r+E.PAD+dr1
        Tlo=t-E.PAD+dt0;Thi=t-E.PAD+dt1;Blo=b+E.PAD+db0;Bhi=b+E.PAD+db1
        for row in R.itertuples():
            i=int(row.case);py=int(T.baseline_y[i]);ti=int(T.entry[i]);L=len(str(T.target[i]))
            X0,X1,Y0,Y1=int(row.X0),int(row.X1),int(row.Y0),int(row.Y1)
            fy=(py+Thi>=Y0)&(py+Tlo<=Y0+g-1)&(py+Bhi>=Y1-g+1)&(py+Blo<=Y1)
            lo=np.maximum(X0-Lhi,X1-g+1-Rhi);hi=np.minimum(X0+g-1-Llo,X1-Rlo)
            flat=fy&(lo<=hi)                                        # published feasibility (no pen range)
            cnt=np.where(fy,np.clip(np.minimum(hi,PX1)-np.maximum(lo,PX0)+1,0,None),0).astype(float)
            s_flat=scores(D,np.where(flat,p,0.0),ti,L);s_lik=scores(D,p*cnt,ti,L)
            out.append(dict(dict=dn,font=fn,size=sz,variant=var,grid_px=g,case=i,exact_model=exact,
                resid_pub=row.resid_bits,hit10_pub=row.hit10,hit1_pub=row.hit1,len_pub=row.len_ok,
                resid_flat=s_flat[3],hit10_flat=s_flat[1],
                hit1_lik=s_lik[0],hit10_lik=s_lik[1],len_lik=s_lik[2],resid_lik=s_lik[3],truth_in_lik=s_lik[4]))
    print(dn,fn,sz,'done',flush=True);return out
if __name__=='__main__':
    if not (OUT / 'e1_summary.csv').is_file():
        raise SystemExit('Run scripts/rerun_full.sh first to generate the case rows and tolerances.')
    E.check_render_inputs()
    init_tolerance()
    U=[(d,f,s) for d in E.DICTS for f in E.FONTS for s in E.SIZES]
    if os.environ.get('ONLY'):U=[u for u in U if u[0]==os.environ['ONLY']]
    if os.environ.get('PX42'):U=[(d,f,42) for d in ('surnames','words','emails') for f in ('DejaVuSans','LiberationSans','LiberationSerif')]
    for d in {u[0] for u in U}:E.get_dict(d)
    with Pool(int(os.environ.get('E1_PROCS',6)), initializer=init_tolerance) as P:R=[x for y in P.map(unit,U) for x in y]
    pd.DataFrame(R).to_csv(f'{OUT}/phase_cases'+('_42' if os.environ.get('PX42') else '')+('_'+os.environ['ONLY'] if os.environ.get('ONLY') else '')+'.csv.gz',index=False);print('ALL DONE')
