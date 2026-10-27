#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproducible geometry experiment, not a claim about a particular photo dataset."""
import random,json,statistics
from pathlib import Path
rng=random.Random(42);rows=[]
for side in (40,80):
 boxes=[(rng.randrange(1024-side+1),rng.randrange(768-side+1)) for _ in range(200)]
 for g in (64,32,16,8):
  ratios=[((x+side+g-1)//g*g-x//g*g)*((y+side+g-1)//g*g-y//g*g)/(side*side) for x,y in boxes]
  rows.append(dict(box_side=side,grid=g,boxes=len(boxes),mean_ratio=statistics.mean(ratios),median_ratio=statistics.median(ratios)))
out=dict(seed=42,canvas=[1024,768],note='Area rounded out divided by box area; hidden positions remain visible.',rows=rows)
p=Path(__file__).resolve().parents[1]/'results/overredaction.json';p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
