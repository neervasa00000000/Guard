"""Check retained target alignment against the archived A2 per-target scores."""
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from control import POLICY

kit,out=map(Path,sys.argv[1:])
root=kit/"v5.7-ieee"
phase=pd.read_csv(root/"new_tests_posterior/csv/phase_cases.csv.gz")
phase=phase[phase["dict"].isin(["surnames","words"]) &
            ((phase.variant=="main")|((phase.variant=="D2_bucket128")&(phase.grid_px==1)))]
units=pd.read_csv(kit/"results/e1-full/csv/e1_summary.csv")
h0=units.groupby("dict").prior_bits.first()
groups=[]
for (name,font,size,variant,grid),rows in phase.groupby(["dict","font","size","variant","grid_px"]):
    label=POLICY[0 if variant=="D2_bucket128" else grid]
    r=rows.sort_values("case")
    np.testing.assert_array_equal(r.case,np.arange(len(r)))
    assert r.exact_model.all()
    with np.load(kit/"review4_grouped"/f"{name}_{font}_{size}.npz") as a:
        h=a[f"LAYOUT-BOX|{label}|A2"]
        hit=np.max(np.abs(h[:,1]-r.hit10_lik))
        bits=np.max(np.abs(h[:,2]-(h0[name]-r.resid_lik)))
        assert hit<=1e-12 and bits<=1e-10,(name,font,size,label,hit,bits)
    groups.append((name,font,size,label,len(r),hit,bits))
summary=pd.DataFrame(groups,columns="list font size policy n max_hit_error max_bits_error".split())
assert len(summary)==216 and summary.n.sum()==432000
summary.to_csv(out/"a2_alignment.csv",index=False)
print(len(summary),"A2 cells;",summary.n.sum(),"per-target records;",
      summary.max_hit_error.max(),"max top-10 error;",summary.max_bits_error.max(),"max bits error")
