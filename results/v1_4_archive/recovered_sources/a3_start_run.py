"""Replay the archived A3 checks and score fixed-start padding."""
import argparse
import gzip
from functools import lru_cache
from itertools import product
import math
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

P = argparse.ArgumentParser()
P.add_argument("kit", type=Path)
P.add_argument("review", type=Path)
P.add_argument("output", type=Path)
P.add_argument("--size-replay", action="store_true")
args = P.parse_args()
K = args.kit
V = K / "v5.7-ieee"
sys.path[:0] = [str(K/"results/e1-full/scripts"), str(args.review)]
import e1lib as E
from geometry import text_bounds, Geometry, Policy, ceil_multiple
from grouped_scores import GroupedScores
from PIL import __version__ as pillow_version, features

for name, (path, license_name, variation) in E.FONTS.items():
    E.FONTS[name] = (str(Path("/fonts") / Path(path).name), license_name, variation)

SEED = 20261029
STUDY = 20261120
BOOT = 20261117
FONTS = ("DejaVuSans", "LiberationSerif")
ARCH = V / "new_tests_padding/csv/cases_a3"
N = 2000
COPY_COUNTS = (1, 2, 3, 5)
OUT = args.output
started = time.monotonic()


@lru_cache(None)
def data(d):
    return E.get_dict(d)


def indexes(d, f):
    return [list(E.DICTS).index(d), list(E.FONTS).index(f)]


@lru_cache(None)
def targets(d, f, s):
    rng = np.random.default_rng([SEED, *indexes(d, f), s])
    ids, strings = E.sample_targets(data(d), N, rng)
    x, y = rng.integers(*E.PEN_X, N), rng.integers(*E.PEN_Y, N)
    return ids, strings, x, y, rng


@lru_cache(None)
def bounds(d, f, s, model, renderer="pillow"):
    if renderer == "lo":
        return np.load(K / f"start-work/table_{f}_{s}.npy")
    if model == "layout":
        return np.load(K/"results/e1-full/data/cache"/f"geom_{d}_{f}_{s}.pkl", allow_pickle=True)
    font = E.font(f,s)
    return np.array([text_bounds(font, word, "PIXEL-INK") for word in data(d)["strings"]])


def shifted_rng(d,f,s):
    ids, strings, x, y, _ = targets(d,f,s)
    rng = np.random.default_rng([SEED,*indexes(d,f),s])
    E.sample_targets(data(d),N,rng)
    rng.integers(*E.PEN_X,N)
    rng.integers(*E.PEN_Y,N)
    E.sample_targets(data(d),400,rng)
    rng.integers(*E.PEN_X,400)
    rng.integers(*E.PEN_Y,400)
    for _ in range(10):
        rng.integers(0,N,(2000,N))
    for _ in range(N):
        rng.integers(0,17,4)
    for _ in range(8):
        rng.integers(0,N,(2000,N))
    offsets = rng.integers(0,64,(N,5,2))
    offsets[:,0] = 0
    archive = pd.read_csv(ARCH / f"{d}_{f}_{s}_targets.csv.gz")
    assert np.array_equal(archive.entry,ids) and np.array_equal(archive.target,strings)
    assert np.array_equal(archive.pen_x,x) and np.array_equal(archive.baseline_y,y)
    return offsets


def sanity():
    exact = pd.read_csv(V/"new_tests_posterior/csv/a3_cases.csv.gz")
    assert len(exact)==128000
    pooled = []
    for d,f in product(("surnames","words"),FONTS):
        ids,_,x,y,_ = targets(d,f,16)
        offsets = shifted_rng(d,f,16)
        gb = bounds(d,f,16,"layout")
        reference = pd.read_csv(ARCH/f"{d}_{f}_16.csv.gz")
        rows = reference[(reference.variant=="A3_crosscopy") & (reference.condition=="clean") &
                         (reference.grid_px==16)]
        exact_rows = exact[(exact["dict"]==d)&(exact.font==f)&(exact.grid_px==16)]
        if d == "surnames":
            weights = data(d)["p"]
            h0 = -(weights*np.log2(weights)).sum()
            for k in COPY_COUNTS:
                pub = rows[rows.k==k].sort_values("case")
                check = exact_rows[exact_rows.k==k].sort_values("case")
                assert np.allclose(pub.hit10,check.hit10_pub) and np.allclose(pub.resid_bits,check.resid_pub)
                scorer = GroupedScores(data(d),gb)
                l,t,r,b = gb[scorer.representatives].T
                out = []
                for i in range(N):
                    lo=np.full(len(l), E.PEN_X[0])
                    hi=np.full(len(l), E.PEN_X[1]-1)
                    allowed=np.ones(len(l),bool)
                    for sx,sy in offsets[i,:k]:
                        box=E.snapped(E.tight_box(gb[ids[i]],x[i]+sx,y[i]+sy,0,None),16)
                        if sx==sy==0 and np.array_equal(offsets[i,0],(sx,sy)):
                            first=E.snapped(E.tight_box(gb[ids[i]],x[i],y[i],0,None),16)
                        xl,xr,yt,yb=box
                        lo=np.maximum(lo,np.maximum(xl-l+1,xr-15-r-1)-sx)
                        hi=np.minimum(hi,np.minimum(xl+15-l+1,xr-r-1)-sx)
                        allowed &= (E.snap(y[i]+sy+t-1,y[i]+sy+b+1,16)[0]==yt)
                        allowed &= (E.snap(y[i]+sy+t-1,y[i]+sy+b+1,16)[1]==yb)
                    assert tuple(pub.iloc[i][["X0","X1","Y0","Y1"]])==first
                    _,hit,bits,_=scorer.score(np.maximum(hi-lo+1,0)*allowed,ids[i])
                    out.append((hit,bits))
                values=np.array(out)
                np.testing.assert_allclose(values[:,0],check.hit10_lik,atol=1e-9,rtol=0)
                np.testing.assert_allclose(values[:,1],h0-check.resid_lik,atol=1e-9,rtol=0)
                pooled.append(pd.DataFrame(dict(k=k,hit=values[:,0],bits=values[:,1])))
        # Edge pad, unchanged under integer translation after alignment.
        edge = E.bucket_transform(gb,f,16)
        for attacker in ("A3","A1") if d=="surnames" and f=="DejaVuSans" else ("A3",):
            keys = edge if attacker=="A1" else np.column_stack((edge[:,2]-edge[:,0],edge[:,1],edge[:,3]))
            scorer=GroupedScores(data(d),keys)
            vals=np.array([scorer.score((np.arange(scorer.size)==scorer.group[i]).astype(int),i)[1:3] for i in ids])
            for k in COPY_COUNTS:
                if attacker=="A3":
                    pub = reference[(reference.variant=="D2pad_A3")&(reference.k==k)].sort_values("case")
                    np.testing.assert_allclose(vals[:,0],pub.hit10,atol=1e-9,rtol=0)
                if attacker=="A1" and k in (1,5):
                    assert f"{vals[:,0].mean()*100:.1f}"=="8.0"
                    assert f"{vals[:,1].mean():.2f}"=="0.39"
                    print("Table X edge padding known start",k,*vals.mean(axis=0))
    result=pd.concat(pooled).groupby("k").mean()
    assert [f"{x*100:.1f}" for x in result.hit]==["11.5","15.1","17.3","22.0"]
    assert [f"{x:.2f}" for x in result.bits.iloc[[0,-1]]]==["1.36","3.30"]
    result.to_csv(OUT/"sanity_grid.csv")
    pad=pd.read_csv(V/"new_tests_padding/csv/a3_padding_pooled.csv")
    pad=pad[pad.variant=="D2pad_A3"]
    for d,expected in (("surnames","5.9"),("words","24.6")):
        rows=pad[pad["dict"]==d]
        assert len(rows)==4 and all(f"{v:.1f}"==expected for v in rows.top10_pct)
    pad.to_csv(OUT/"sanity_edge_pad.csv",index=False)
    print("A3 replay and mandatory controls passed",flush=True)


@lru_cache(None)
def features_for(d,f,s,model,c,renderer="pillow"):
    g = bounds(d,f,s,model,renderer)
    asc,desc = E.font(f,s).getmetrics()
    geom = Geometry(g,-asc,desc)
    l,r = geom.horizontal(Policy("pen-anchored",c))
    span=geom.right-geom.fixed_left
    tight=(geom.right-geom.left)*(geom.bottom-geom.top)
    return geom, r-l, span, tight


def same_render(d,f,s,model,c,offset,jitter,condition):
    geom,width,span,tight=features_for(d,f,s,model,c)
    ids,_,x,y,_=targets(d,f,s)
    score=GroupedScores(data(d),span[:,None] if jitter is not None else width[:,None])
    reps=score.representatives
    rows=[]
    grids=(1,) if jitter is not None else (1,16)
    for g,att in product(grids,("A1","A3")):
        for i,target in enumerate(ids):
            likelihood=np.ones(score.size,dtype=np.int64)
            if jitter is None:
                # The fixed left edge and common line recover the nuisance
                # pen interval independently of the candidate width.
                origin=x[i]+geom.fixed_left
                lo,hi=E.PEN_X[0],E.PEN_X[1]-1
                if att=="A1": lo=hi=x[i]
                else:
                    for sx,_ in offset[i]:
                        snapped_left=(origin+sx)//g*g
                        lo=max(lo,snapped_left-sx-geom.fixed_left)
                        hi=min(hi,snapped_left+g-1-sx-geom.fixed_left)
                assert lo <= x[i] <= hi
                # Since c is divisible by g and width is a multiple of c,
                # all starts in a left bucket predict the same right bucket.
                likelihood *= width[reps]==width[target]
            for j in range(5):
                w=int(width[target])
                if jitter is not None:
                    # Keep the fixed anchor. Only extension at the right
                    # changes the class. Left jitter is absorbed by the fixed
                    # anchor if the requested left edge remains inside it.
                    w=int(ceil_multiple(span[target]+jitter[i,j,1],c))
                    likelihood *= np.maximum(0,np.minimum(16,w-span[reps])-
                                             np.maximum(0,w-c+1-span[reps])+1)
                k=j+1
                if k not in ((1,5) if jitter is not None else COPY_COUNTS):
                    continue
                _,hit,bits,truth=score.score(likelihood,target)
                assert truth
                w0=int(width[target]) if jitter is None else int(ceil_multiple(span[target]+jitter[i,0,1],c))
                xx=x[i]+geom.fixed_left
                a,b=E.snap(xx,xx+w0,g)
                u,v=E.snap(y[i]+geom.line_top,y[i]+geom.line_bottom,g)
                rows.append((condition,d,f,s,model,c,g,att,k,i,hit,bits,(b-a)*(v-u)/tight[target],False))
    return rows


def rerender(d,s,scenario,model,c):
    ids,_,_,_,_=targets(d,"DejaVuSans",s)
    rng=np.random.default_rng([STUDY,2,list(E.DICTS).index(d),s,["translate","font","size","fontsize","renderer"].index(scenario)])
    if scenario=="font":
        rel=[[(list(E.FONTS)[j],s,"pillow") for j in rng.permutation(6)[:5]] for _ in ids]
    elif scenario=="size":
        fs=[list(E.FONTS)[rng.integers(6)] for _ in ids]
        rel=[[(f,int(z),"pillow") for z in np.array([12,16,24])[rng.permutation(3)]] for f in fs]
    else:
        rel=[]
        for _ in ids:
            f=FONTS[rng.integers(2)]
            pair=[(f,s,"pillow"),(f,s,"lo")]
            rel.append(pair if rng.integers(2) else pair[::-1])
    options=sorted({r for rr in rel for r in rr})
    all_widths=np.column_stack([features_for(d,f,z,model,c,r)[1] for f,z,r in options])
    scorer=GroupedScores(data(d),all_widths)
    widths=all_widths[scorer.representatives]
    positions={key:i for i,key in enumerate(options)}
    rows=[]
    for i,target in enumerate(ids):
        releases=rel[i]
        cols=[positions[r] for r in releases]
        first=features_for(d,*releases[0][:2],model,c,releases[0][2])
        geom,w,_,tight=first
        area=w[target]*(geom.line_bottom-geom.line_top)/tight[target]
        for k in (1,len(releases)):
            chosen=cols[:k]
            count=np.all(widths[:,chosen]==all_widths[target,chosen],axis=1).astype(int)
            _,hit,bits,truth=scorer.score(count,target)
            assert truth
            changed=len(set(all_widths[target,chosen]))>1
            for att in (("A1","A2") if scenario=="font" else ("A2",)):
                rows.append((scenario,d,"mixed",s,model,c,1,att,k,i,hit,bits,area,changed))
    return rows


def summarize(frame):
    keys=list(frame.columns[:8])
    rng=np.random.default_rng(BOOT)
    results=[]
    for label,group in frame.groupby(keys,sort=True):
        pivot=group.pivot(index="case",columns="k",values=["hit10","bits"])
        base=group[group.k==1]
        for k,cell in group.groupby("k"):
            a=pivot["hit10"][k].to_numpy()*100-pivot["hit10"][1].to_numpy()*100
            b=pivot["bits"][k].to_numpy()-pivot["bits"][1].to_numpy()
            draw=rng.integers(0,len(a),(10000,len(a)),dtype=np.int32)
            a0,a1=np.quantile(a[draw].mean(axis=1),[.025,.975])
            b0,b1=np.quantile(b[draw].mean(axis=1),[.025,.975])
            results.append(dict(zip(keys,label),k=k,n=len(a),top10_1=100*base.hit10.mean(),top10_k=100*cell.hit10.mean(),
                                bits_1=base.bits.mean(),bits_k=cell.bits.mean(),delta_top10=a.mean(),top10_lo=a0,top10_hi=a1,
                                delta_bits=b.mean(),bits_lo=b0,bits_hi=b1,median_area=cell.area.median(),
                                targets_change_class=int(cell.class_changed.sum())))
    return pd.DataFrame(results)


if __name__=="__main__":
    print(sys.version, "numpy",np.__version__,"pandas",pd.__version__,"Pillow",pillow_version,
          "raqm",features.version("raqm"),flush=True)
    columns="condition list font size model class_px grid attacker k case hit10 bits area class_changed".split()
    if args.size_replay:
        rows=[]
        for model,c in product(("layout","ink"),(128,192)):
            rows.extend(rerender("surnames",24,"size",model,c))
        cases=pd.DataFrame(rows,columns=columns)
        cases.to_csv(OUT/"size_cases.csv.gz",index=False)
        summarize(cases).to_csv(OUT/"size_summary.csv",index=False)
        print("Size replay wall seconds",time.monotonic()-started)
        sys.exit(0)
    sanity()
    if "--sanity-only" in sys.argv:
        sys.exit(0)
    print("Sanity wall seconds",time.monotonic()-started,flush=True)
    rows=[]
    for d,f,s in ([(d,f,16) for d,f in product(("surnames","words"),FONTS)] +
                  [("emails",f,16) for f in FONTS] +
                  [(d,f,24) for d,f in product(("surnames","words"),FONTS)]):
        original=s==16 and d!="emails"
        off=shifted_rng(d,f,s) if original else np.random.default_rng(
            [SEED,*indexes(d,f),s,128,3]).integers(0,64,(N,5,2))
        off[:,0]=0
        jit_seed=[SEED,*indexes(d,f),s,128]+([] if original else [4])
        jit=np.random.default_rng(jit_seed).integers(0,17,(N,5,2))
        for model,c in product(("layout","ink"), (128,192) if s==24 else (128,)):
            rows.extend(same_render(d,f,s,model,c,off,None,"shifted" if original else "harder"))
            if d=="surnames" or (d=="words" and s==16):
                rows.extend(same_render(d,f,s,model,c,off,jit,"jitter"))
        print("Completed",d,f,s,flush=True)
    for d,s,scenario in ([("surnames",s,"font") for s in (16,24)]+
                         [("surnames",24,"size"),("surnames",24,"renderer")]):
        for model,c in product(("layout","ink"),(128,192) if s==24 else (128,)):
            if scenario=="renderer" and model=="layout":
                continue  # LibreOffice table is true ink only.
            rows.extend(rerender(d,s,scenario,model,c))
    cases=pd.DataFrame(rows,columns=columns)
    cases.to_csv(OUT/"cases.csv.gz",index=False)
    summarize(cases).to_csv(OUT/"summary.csv",index=False)
    print("Wall seconds",time.monotonic()-started)
