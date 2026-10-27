#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Deterministic RAW RGB feature vectors; no codec or image resizer involved."""
import sys,json,base64
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import grd,grd_visual
m=dict(width=132,height=84,tileSize=64);cases=[]
for n,d in ((1,2),(3,4),(5,4),(3,2),(1,1)):
 w=m['width']*n//d;h=m['height']*n//d
 rgb=bytes((x*37+y*71+c*113+(x*y)%251)%256 for y in range(h) for x in range(w) for c in range(3))
 cases.append(dict(id=f'{n}/{d}',width=w,height=h,rgb=base64.b64encode(rgb).decode(),features=[grd_visual.mapped_tile_features(rgb,w,h,m,i,grd).hex() for i in range(6)]))
(grd.ROOT/'tests/vectors/area-vectors.json').write_text(json.dumps(dict(sealed=m,cases=cases),indent=2)+'\n');print('Wrote five raw-RGB area mapping vectors')
