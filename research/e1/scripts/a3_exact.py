"""Exact-likelihood rescoring of the PUBLISHED A3 (k shifted copies, start unknown, baseline and relative shifts known)
cells, clean, grids 8/16/32/64, k=1,2,3,5, four units. The RNG stream of e1_run.py:unit() is replayed up to `offs`
(targets, pens, calibration draws, the 18 boot_ci draws of the clean block and the D1 jitter draws consume the stream;
clean ink boxes and J=0 tight boxes do not). Replay is checked against the published targets file and against the
published per-case A3 copy-0 box and residual entropy (old flat scoring must be reproduced exactly).
Exact likelihood: P(b_1..b_k | w) = #{px in [64,1023] : every copy j snaps to its observed box}/960 (y known)."""
import argparse
import sys
from pathlib import Path
from multiprocessing import Pool

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import e1lib as E
from phase_exact import scores

N=2000;NCAL=400;SEED=20261029;PX0,PX1=64,1023
def unit(a):
    C,dn,fn,sz=a;D=E.get_dict(dn);p=D['p'];G=E.geometry(dn,fn,sz).astype(np.int64)
    rng=np.random.default_rng([SEED,list(E.DICTS).index(dn),list(E.FONTS).index(fn),sz])
    idx,strs=E.sample_targets(D,N,rng);pens=np.stack([rng.integers(*E.PEN_X,N),rng.integers(*E.PEN_Y,N)],1)
    E.sample_targets(D,NCAL,rng);rng.integers(*E.PEN_X,NCAL);rng.integers(*E.PEN_Y,NCAL)
    for _ in range(10):rng.integers(0,N,(2000,N))          # 5 grids x (A1,A2) boot_ci, clean
    for _ in range(N):rng.integers(0,17,4)                 # D1 jitter tight boxes
    for _ in range(4):rng.integers(0,N,(2000,N))           # D1 cells
    for _ in range(4):rng.integers(0,N,(2000,N))           # D2 cells (no draws in the boxes)
    offs=rng.integers(0,64,(N,5,2));offs[:,0,:]=0
    T=pd.read_csv(f'{C}/{dn}_{fn}_{sz}_targets.csv.gz')
    assert (T.entry.values==idx).all() and (T.pen_x.values==pens[:,0]).all() and (T.baseline_y.values==pens[:,1]).all()
    X=pd.read_csv(f'{C}/{dn}_{fn}_{sz}.csv.gz');X=X[X.variant=='A3_crosscopy'].set_index(['grid_px','k','case'])
    l,t,r,b=G.T;L=l-E.PAD;R=r+E.PAD;Tt=t-E.PAD;B=b+E.PAD;out=[];nchk=0
    for g in (8,16,32,64):
        for k in (1,2,3,5):
            for i in range(N):
                ink=tuple(int(v) for v in G[idx[i]]);px,py=int(pens[i,0]),int(pens[i,1])
                lo=np.full(len(p),-10**9);hi=np.full(len(p),10**9);fy=np.ones(len(p),bool)
                for j in range(k):
                    sx,sy=int(offs[i,j,0]),int(offs[i,j,1])
                    X0,X1,Y0,Y1=E.snapped(E.tight_box(ink,px+sx,py+sy,0,None),g)
                    if j==0:first=(X0,X1,Y0,Y1)
                    yy=py+sy;fy&=(yy+Tt>=Y0)&(yy+Tt<=Y0+g-1)&(yy+B>=Y1-g+1)&(yy+B<=Y1)
                    lo=np.maximum(lo,np.maximum(X0-L,X1-g+1-R)-sx);hi=np.minimum(hi,np.minimum(X0+g-1-L,X1-R)-sx)
                pub=X.loc[(g,k,i)];assert first==(pub.X0,pub.X1,pub.Y0,pub.Y1)
                flat=fy&(lo<=hi);cnt=np.where(fy,np.clip(np.minimum(hi,PX1)-np.maximum(lo,PX0)+1,0,None),0).astype(float)
                Ls=len(strs[i]);sf=scores(D,np.where(flat,p,0.0),idx[i],Ls);sl=scores(D,p*cnt,idx[i],Ls)
                assert abs(sf[3]-pub.resid_bits)<2e-4 and abs(sf[1]-pub.hit10)<1e-9,(g,k,i,sf,pub.resid_bits);nchk+=1
                out.append(dict(dict=dn,font=fn,size=sz,grid_px=g,k=k,case=i,resid_pub=pub.resid_bits,hit10_pub=pub.hit10,hit1_pub=pub.hit1,
                    hit1_lik=sl[0],hit10_lik=sl[1],len_lik=sl[2],resid_lik=sl[3],truth_in_lik=sl[4]))
    print(dn,fn,sz,'replay verified on',nchk,'cases',flush=True);return out
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=HERE/"cases/main-subset")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    E.check_render_inputs()
    E.get_dict("surnames")
    E.get_dict("words")
    out = E.RUN_ROOT/"csv"
    out.mkdir(parents=True, exist_ok=True)
    units = [(args.cases, name, font, 16) for name in ("surnames", "words")
             for font in ("DejaVuSans", "LiberationSerif")]
    with Pool(args.workers) as pool:
        rows = [row for block in pool.map(unit, units) for row in block]
    pd.DataFrame(rows).to_csv(out/"a3_cases.csv.gz", index=False)
