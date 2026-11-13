#!/usr/bin/env python3
"""Validate the E1 snap model against Guard's own grd.redact() at f8f2558 (read-only clone).
Throwaway in-memory Ed25519 key (purpose=demo); nothing written into the clone."""
import sys,os,json,subprocess,random,csv,time
sys.dont_write_bytecode=True
from pathlib import Path
GUARD=os.environ.get('E1_GUARD', str(Path(__file__).resolve().parents[3]));sys.path.insert(0,GUARD)
import grd,numpy as np
from PIL import Image,ImageDraw
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
sys.path.insert(0,os.path.dirname(__file__));import e1lib as E
if len(sys.argv)>1 and sys.argv[1] in ('-h','--help'):
    print('Usage: e1_validate_guard.py [image count]; E1_GUARD selects the Guard checkout')
    raise SystemExit(0)
E.check_render_inputs()
sha=subprocess.check_output(['git','-C',GUARD,'rev-parse','HEAD']).decode().strip()
rng=np.random.default_rng(20261030);key=Ed25519PrivateKey.generate()
W,H=1216,1024;rows=[];t0=time.time()
NIMG=int(sys.argv[1]) if len(sys.argv)>1 else 84
for k in range(NIMG):
    dn=list(E.DICTS)[k%5];fn=list(E.FONTS)[(k//5)%6];sz=E.SIZES[k%3]
    variant=['clean','clean','jpeg75','scan','D1_jitter16','D2_bucket128'][k%6]
    D=E.get_dict(dn);idx,strs=E.sample_targets(D,1,rng);s=strs[0]
    px=int(rng.integers(*E.PEN_X));py=int(rng.integers(*E.PEN_Y))
    cond=variant if variant in('jpeg75','scan') else 'clean'
    box=E.ink_box(fn,sz,s,cond,rng)
    if variant=='D2_bucket128':box=E.bucket_box(box,fn,sz)
    tb=E.tight_box(box,px,py,16 if variant=='D1_jitter16' else 0,rng)
    tb=tuple(int(v) for v in tb)
    if tb[2]>W or tb[3]>H or tb[0]<0 or tb[1]<0:continue
    im=Image.new('RGB',(W,H),'white');ImageDraw.Draw(im).text((px,py),s,font=E.font(fn,sz),fill='black',anchor='ls')
    doc=grd.seal(im,key,purpose='demo',label='e1-validate',version=3,visual=False,sub_tile=8);data=grd.encode(doc)
    for g in (8,16,32,64):
        red=grd.redact(data,[(tb[0],tb[1],tb[2]-tb[0],tb[3]-tb[1])],'black',g)
        rep=grd.verify_v2(red,trusted=[doc['manifest']['publicKey']])
        rm=rep['redactionMap'];gb=(min(e['x'] for e in rm),max(e['x']+e['width'] for e in rm),min(e['y'] for e in rm),max(e['y']+e['height'] for e in rm))
        # also check the union is a full rectangle (area equals bbox area)
        area=sum(e['width']*e['height'] for e in rm);full=area==(gb[1]-gb[0])*(gb[3]-gb[2])
        mb=E.snapped(tb,g)
        rows.append(dict(case_id=f'{k}-{g}',dict=dn,font=fn,size_px=sz,variant=variant,target=s,grid_px=g,tight_box=tb,model_box=mb,guard_box=gb,guard_union_is_rectangle=full,match=(tuple(mb)==tuple(gb) and full),verdict=rep['verdict']))
    print(k,dn,fn,sz,variant,s,round(time.time()-t0),flush=True)
E.RUN_ROOT.joinpath('csv').mkdir(parents=True,exist_ok=True)
out=os.path.join(E.RUN_ROOT,'csv','e1_validation.csv')
with open(out,'w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
res=dict(guard_sha=sha,checked=len(rows),matching=sum(r['match'] for r in rows),verdicts=sorted({r['verdict'] for r in rows}),seconds=round(time.time()-t0),key='fresh in-memory Ed25519, purpose=demo, discarded')
json.dump(res,open(os.path.join(E.RUN_ROOT,'csv','e1_validation_summary.json'),'w'),indent=1);print(res)
