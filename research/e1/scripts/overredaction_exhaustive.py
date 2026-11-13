#!/usr/bin/env python3
"""Exhaustive over-redaction: every placement of an s x s box (s=40,80 px) on a 1024x768 canvas, snapped to
Guard's tile grid g in {64,32,16,8}. Ratio = snapped area / box area. Also reports the 200-random-box estimate
(seed 42) used by Guard's bench/overredaction.py for comparison. Pure arithmetic; ~3 s."""
import random,statistics,csv,os,json
W,H=1024,768
def r(x,y,s,g):return ((x+s+g-1)//g*g-x//g*g)*((y+s+g-1)//g*g-y//g*g)/(s*s)
import e1lib as E
E.RUN_ROOT.joinpath('csv').mkdir(parents=True,exist_ok=True)
out=E.RUN_ROOT/'csv'/'overredaction_exhaustive.csv';rows=[]
rng=random.Random(42)
for s in (40,80):
    boxes=[(rng.randrange(W-s+1),rng.randrange(H-s+1)) for _ in range(200)]
    for g in (64,32,16,8):
        ex=[r(x,y,s,g) for x in range(W-s+1) for y in range(H-s+1)];sm=[r(x,y,s,g) for x,y in boxes]
        rows.append(dict(box_px=s,grid_px=g,placements=len(ex),exh_median=statistics.median(ex),exh_mean=statistics.mean(ex),exh_min=min(ex),exh_max=max(ex),
                         sample200_seed42_median=statistics.median(sm),sample200_seed42_mean=statistics.mean(sm)))
        print(rows[-1])
with open(out,'w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
