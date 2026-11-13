"""Reproduce the archived 18-cell Holm tables from the original inputs."""
from math import sqrt
from pathlib import Path
from statistics import NormalDist
import sys

import numpy as np
import pandas as pd

OLD = (("exact>8",1,8),("8>16",8,16),("16>32",16,32),("32>64",32,64),("64>pad",64,0))
POLICY = {0:"ink-anchored-128",1:"exact",8:"square-8",16:"square-16",32:"square-32",64:"square-64"}
NORM = NormalDist()


def holm(values):
    values = np.asarray(values)
    order = np.argsort(values,kind="stable")
    adjusted = np.empty(len(values))
    adjusted[order] = np.minimum(1,np.maximum.accumulate(values[order]*np.arange(len(values),0,-1)))
    return adjusted


def replay(kit,out):
    root = kit/"v5.7-ieee/new_tests_review4/csv"
    old = pd.read_csv(root/"w9_holm_cells.csv")
    published = pd.read_csv(kit/"results/e1-full/csv/e1_summary.csv")
    published = published[(published.condition=="clean")&(published.attacker=="A1")&
                          (published.k_copies==1)]
    lookup = published.set_index(["dict","font","size_px","variant","grid_px"])
    labels = {label:(a,b) for label,a,b in OLD}
    rows = []
    files = {}
    for name,font,size,label,p1,p2,z,p,zpair,ppair,*_ in old.itertuples(index=False,name=None):
        a,b = labels[label]
        left = lookup.loc[(name,font,size,"main",a)]
        right = lookup.loc[(name,font,size,"main",b) if b else (name,font,size,"D2_bucket128",1)]
        assert left.n==right.n
        n=int(left.n)
        x,y = float(left.top10),float(right.top10)
        np.testing.assert_allclose([x,y],[p1,p2],rtol=0,atol=5e-15)
        mid=(x+y)/2
        newz=(x-y)/sqrt(max(mid*(1-mid)*2/n,1e-12))
        newp=1-NORM.cdf(newz)
        np.testing.assert_allclose([newz,newp],[z,p],rtol=0,atol=2e-12)
        source="archived paired z"
        if name in {"surnames","words"}:
            key=name,font,size
            if key not in files:
                with np.load(kit/"review4_grouped"/f"{name}_{font}_{size}.npz") as data:
                    files[key]={g:data[f"LAYOUT-BOX|{policy}|A1"][:,1] for g,policy in POLICY.items()}
            delta=files[key][a]-files[key][b]
            assert len(delta)==n
            se=delta.std(ddof=1)/sqrt(n)
            paired=delta.mean()/se if se else np.inf*np.sign(delta.mean() or 1)
            np.testing.assert_allclose(paired,zpair,rtol=0,atol=2e-10)
            zpair=paired
            source="per-target review4 A1"
        newpp=1-NORM.cdf(zpair) if np.isfinite(zpair) else 0.0
        np.testing.assert_allclose(newpp,ppair,rtol=0,atol=2e-12)
        rows.append(dict(dict=name,font=font,size=size,comparison=label,n=n,p1=x,p2=y,
                         z_2prop=newz,p_2prop=newp,z_paired=zpair,p_paired=newpp,paired_source=source))
    cells=pd.DataFrame(rows)
    for col in ("p_2prop","p_paired"):
        cells[col+"_holm"]=cells.groupby(["dict","comparison"])[col].transform(holm)
    summary=cells.groupby(["dict","comparison"]).agg(
        cells=("font","size"),
        sig_raw_2prop=("p_2prop",lambda z:(z<.05).sum()),
        sig_holm_2prop=("p_2prop_holm",lambda z:(z<.05).sum()),
        sig_holm_paired=("p_paired_holm",lambda z:(z<.05).sum())).reset_index()
    expected=pd.read_csv(root/"w9_holm_summary.csv")
    pd.testing.assert_frame_equal(summary,expected,check_dtype=False)
    cells.to_csv(out/"w9_replayed_cells.csv",index=False)
    summary.to_csv(out/"w9_replayed_summary.csv",index=False)
    print(f"Archived Holm reproduction passed: {len(summary)} families, {len(cells)} cells",flush=True)
    return summary


if __name__=="__main__":
    replay(*map(Path,sys.argv[1:]))
