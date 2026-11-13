"""Summarize the persisted trial rows, skipping resampling of constant differences."""
from pathlib import Path
import sys

import numpy as np
import pandas as pd

root = Path(sys.argv[1])
frame = pd.read_csv(root/"cases.csv.gz")
keys = list(frame.columns[:8])
rng = np.random.default_rng(20261117)
result = []
for label, group in frame.groupby(keys, sort=True):
    pivot = group.pivot(index="case", columns="k", values=["hit10","bits"])
    base = group[group.k==1]
    for k, cell in group.groupby("k"):
        delta = pivot.xs(k, axis=1, level=1).to_numpy() - pivot.xs(1,axis=1,level=1).to_numpy()
        delta[:,0] *= 100
        point = delta.mean(axis=0)
        draw = rng.integers(0,len(delta),(10000,len(delta)),dtype=np.int32)
        ci = np.stack((point,point))
        for field in range(2):
            if np.any(delta[:,field]!=delta[0,field]):
                ci[:,field] = np.quantile(delta[:,field][draw].mean(axis=1), [.025,.975])
        result.append(dict(zip(keys,label),k=k,n=len(delta),top10_1=100*base.hit10.mean(),
                           top10_k=100*cell.hit10.mean(),bits_1=base.bits.mean(),
                           bits_k=cell.bits.mean(),delta_top10=point[0],top10_lo=ci[0,0],
                           top10_hi=ci[1,0],delta_bits=point[1],bits_lo=ci[0,1],bits_hi=ci[1,1],
                           median_area=cell.area.median(),targets_change_class=int(cell.class_changed.sum())))
pd.DataFrame(result).to_csv(root/"summary_checked.csv",index=False)
