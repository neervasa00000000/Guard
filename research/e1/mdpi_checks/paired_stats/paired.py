"""Paired sign flips and bootstrap from retained trial arrays. No rendering."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from itertools import product
from pathlib import Path
import platform
import sys
import time

import numpy as np
import pandas as pd

from control import holm, OLD, POLICY, replay

MODELS=("LAYOUT-BOX","PIXEL-INK")
ATTACKERS=("A1","A2")
LISTS=("surnames","words")
TESTS=tuple((label,POLICY[a],POLICY[b]) for label,a,b in OLD)+(
    ("64>start","square-64","pen-anchored-128"),
    ("16>start","square-16","pen-anchored-128"),
)
TABLE=("exact","square-16","square-64","ink-anchored-128","pen-anchored-128","width-grid-64")
FIELDS=("top10","bits")
PERMUTATIONS=100000
RESAMPLES=10000
SIGN_SEED=20261119
BOOT_SEED=20261120
ALPHA=.05


def sign_null(delta,rng):
    """Random sums of signed magnitudes, grouping tied magnitudes exactly."""
    magnitude,counts=np.unique(np.abs(delta[delta!=0]),return_counts=True)
    grouped=counts>=8
    out=np.zeros(PERMUTATIONS)
    for v,n in zip(magnitude[grouped],counts[grouped]):
        out+=v*(2*rng.binomial(n,.5,size=PERMUTATIONS)-n)
    singles=np.repeat(magnitude[~grouped],counts[~grouped])
    if singles.size:
        byte_width=(singles.size+7)//8
        for i in range(0,PERMUTATIONS,2048):
            size=min(2048,PERMUTATIONS-i)
            draws=rng.integers(0,256,(size,byte_width),dtype=np.uint8)
            bits=np.unpackbits(draws,axis=1,count=singles.size)
            out[i:i+size]+=2*(bits@singles)-singles.sum()
    return out


def pvalue(delta,null):
    observed=delta.sum()
    tol=1e-13*np.abs(delta).sum()
    return (1+np.count_nonzero(null>=observed-tol))/(PERMUTATIONS+1)


def bootstrap(delta,rng):
    values,counts=np.unique(delta,return_counts=True)
    n=len(delta)
    if len(values)==1:
        return values[0],values[0]
    if len(values)<=128:
        means=rng.multinomial(n,counts/n,size=RESAMPLES)@values/n
    else:
        means=np.empty(RESAMPLES)
        for i in range(0,RESAMPLES,256):
            draws=rng.integers(0,n,(min(256,RESAMPLES-i),n),dtype=np.int32)
            means[i:i+len(draws)]=delta[draws].mean(axis=1)
    return np.quantile(means,[.025,.975])


def study(family):
    index,name,model,att,comparison,a,b,files=family
    rows=[]
    deltas=[]
    nulls=np.zeros((2,PERMUTATIONS))
    for unit,path in enumerate(files):
        _,font,size=path.stem.split("_")
        with np.load(path) as data:
            left=data[f"{model}|{a}|{att}"]
            right=data[f"{model}|{b}|{att}"]
            assert left.shape==right.shape==(2000,5)
            assert np.all(left[:,4]==1) and np.all(right[:,4]==1)
        diff=(left-right)[:,1:3]
        deltas.append(diff)
        for metric,delta in enumerate(diff.T):
            rng=np.random.default_rng([SIGN_SEED,index,unit,metric])
            null=sign_null(delta,rng)
            nulls[metric]+=null
            brng=np.random.default_rng([BOOT_SEED,index,unit,metric])
            lo,hi=bootstrap(delta,brng)
            rows.append((name,model,att,comparison,FIELDS[metric],font,int(size),len(delta),
                         delta.mean(),lo,hi,pvalue(delta,null)))
    diff=np.concatenate(deltas)
    for metric,delta in enumerate(diff.T):
        rng=np.random.default_rng([BOOT_SEED,index,len(files),metric])
        lo,hi=bootstrap(delta,rng)
        rows.append((name,model,att,comparison,FIELDS[metric],"pooled",0,len(delta),
                     delta.mean(),lo,hi,pvalue(delta,nulls[metric])))
    return rows


def font_table(kit):
    rows=[]
    for name,model,att,policy in product(LISTS,MODELS,ATTACKERS,TABLE):
        by_font={}
        for path in sorted((kit/"review4_grouped").glob(f"{name}_*.npz")):
            _,font,size=path.stem.split("_")
            with np.load(path) as data:
                by_font.setdefault(font,[]).append(data[f"{model}|{policy}|{att}"][:,1:4])
        assert len(by_font)==6 and all(len(a)==3 for a in by_font.values())
        values={f:np.concatenate(a) for f,a in by_font.items()}
        values["pooled"]=np.concatenate(list(values.values()))
        def stats(array):
            return np.r_[100*array[:,0].mean(),array[:,1].mean(),np.median(array[:,2])]
        points={f:stats(a) for f,a in values.items()}
        for font,a in points.items():
            rows.append((name,model,att,policy,font,len(values[font]),*a))
        six=np.stack([a for f,a in points.items() if f!="pooled"])
        for key,v in (("min",six.min(axis=0)),("max",six.max(axis=0))):
            rows.append((name,model,att,policy,key,0,*v))
    return pd.DataFrame(rows,columns="list model attacker policy font n top10_pct bits median_area".split())


def count_cells(frame,old):
    group=frame[frame.font!="pooled"].groupby(["list","model","attacker","comparison","metric"])
    totals=group.agg(cells=("n","size"),positive=("difference",lambda x:(x>0).sum()),
                     paired_raw=("p_value",lambda x:(x<ALPHA).sum()),
                     paired_holm=("p_holm",lambda x:(x<ALPHA).sum())).reset_index()
    totals["old_raw"]=pd.Series(pd.NA,dtype="Int64",index=totals.index)
    totals["old_holm"]=pd.Series(pd.NA,dtype="Int64",index=totals.index)
    control=old.set_index(["dict","comparison"])
    sel=totals[(totals.model=="LAYOUT-BOX")&(totals.attacker=="A1")&(totals.metric=="top10")]
    for i,row in sel.iterrows():
        key=(row["list"],row.comparison)
        if key in control.index:
            totals.loc[i,["old_raw","old_holm"]]=control.loc[key,["sig_raw_2prop","sig_holm_2prop"]].to_numpy()
    return totals


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("kit",type=Path)
    parser.add_argument("out",type=Path)
    parser.add_argument("--workers",type=int,default=4)
    args=parser.parse_args()
    started=time.monotonic()
    print(sys.version,platform.platform(),"numpy",np.__version__,"pandas",pd.__version__,flush=True)
    print("workers",args.workers,"permutations",PERMUTATIONS,"bootstrap",RESAMPLES,
          "sign seed",SIGN_SEED,"bootstrap seed",BOOT_SEED,flush=True)
    old=replay(args.kit,args.out)
    files={name:sorted((args.kit/"review4_grouped").glob(f"{name}_*.npz")) for name in LISTS}
    assert all(len(f)==18 for f in files.values())
    jobs=[(i,name,model,att,*test,files[name])
          for i,(name,model,att,test) in enumerate(product(LISTS,MODELS,ATTACKERS,TESTS))]
    rows=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i,result in enumerate(pool.map(study,jobs)):
            rows.extend(result)
            print(f"Completed family {i+1}/{len(jobs)} at {time.monotonic()-started:.1f} seconds",
                  *jobs[i][1:5],flush=True)
    frame=pd.DataFrame(rows,columns="list model attacker comparison metric font size n difference ci_lo ci_hi p_value".split())
    cells=(frame.font!="pooled")
    keys=["list","model","attacker","comparison","metric"]
    frame.loc[cells,"p_holm"]=frame[cells].groupby(keys).p_value.transform(holm)
    frame.to_csv(args.out/"paired_tests.csv",index=False)
    count_cells(frame,old).to_csv(args.out/"ordering_counts.csv",index=False)
    font_table(args.kit).to_csv(args.out/"per_font.csv",index=False)
    print(f"Completed {len(frame)} estimates in {time.monotonic()-started:.1f} seconds",flush=True)


if __name__=="__main__":
    main()
