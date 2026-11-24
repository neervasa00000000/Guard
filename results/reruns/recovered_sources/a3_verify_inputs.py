"""Verify regenerated stress inputs and reproduce the archived font-change count."""
import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

p = argparse.ArgumentParser()
p.add_argument("kit", type=Path)
args = p.parse_args()
k = args.kit
sys.path.insert(0, str(k/"results/e1-full/scripts"))
import e1lib as E

v = k/"v5.7-ieee"
fonts = list(E.FONTS)
for path in sorted((v/"new_tests_padding/csv/cases_stress").glob("*.csv.gz")):
    name, font, size = path.name.split(".")[0].split("_")
    size = int(size)
    d = E.get_dict(name)
    rng = np.random.default_rng([20261029, list(E.DICTS).index(name), fonts.index(font), size])
    ids, _ = E.sample_targets(d, 2000, rng)
    x, y = rng.integers(*E.PEN_X, 2000), rng.integers(*E.PEN_Y, 2000)
    geom = np.load(k/"results/e1-full/data/cache"/f"geom_{name}_{font}_{size}.pkl",
                   allow_pickle=True)[ids]
    rows = pd.read_csv(path)
    rows = rows[(rows.variant=="D2_bucket128")&(rows.k==1)].sort_values("case")
    assert len(rows)==2000
    left = x + geom[:,0] - E.PAD
    width = -(-(geom[:,2]-geom[:,0]+2*E.PAD)//128)*128
    np.testing.assert_array_equal(rows.X0,left)
    np.testing.assert_array_equal(rows.X1,left+width)
    print("Stress inputs match archived edge boxes",name,font,size,len(rows))

d = E.get_dict("surnames")
rng = np.random.default_rng([20261029, list(E.DICTS).index("surnames"), 0, 24])
ids,_ = E.sample_targets(d,2000,rng)
geom = [np.load(k/"results/e1-full/data/cache"/f"geom_surnames_{f}_24.pkl", allow_pickle=True)[ids]
        for f in fonts]
g = np.stack(geom,axis=1)
classes=-(-(g[:,:,2]-g[:,:,0]+2*E.PAD)//128)
rng=np.random.default_rng([20261120,2,list(E.DICTS).index("surnames"),24,1])
choice=np.array([rng.permutation(6)[:5] for _ in ids])
obs=np.take_along_axis(classes,choice,axis=1)
changed=int((obs.min(axis=1)!=obs.max(axis=1)).sum())
source=pd.read_csv(v/"new_tests_review2/csv/s2_rerender.csv")
expected=source[(source["dict"]=="surnames")&(source["size"]==24)&(source.scenario=="font")&
                (source.attacker=="A2")&(source.k==5)&(source.split=="class_changed")].n.iloc[0]
assert changed==expected
print("Archived 24 px edge-aligned font-change count",changed,"of",len(ids))
