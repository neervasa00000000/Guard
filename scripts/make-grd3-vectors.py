#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Public TEST ONLY key 0x2a repeated; never use this seed for real signing."""
import sys,json,hashlib,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import grd
root=grd.ROOT;key=grd.Ed25519PrivateKey.from_private_bytes(bytes([42])*32);pk=key.public_key().public_bytes(grd.serialization.Encoding.Raw,grd.serialization.PublicFormat.Raw)
w,h=131,67;rgb=bytes(c for y in range(h) for x in range(w) for c in (x%256,y%256,(x+y)%256))
m=dict(format='GRD3',version=3,profile='3.0',assetId=grd.b64(bytes(range(16))),created='2026-10-27T00:00:00Z',width=w,height=h,tileSize=64,pixelFormat='RGB8',root='0'*64,commitments=[],publicKey=pk.hex(),keyId=grd.sha(pk),policy='tile-redaction-v1',purpose='asset',label='TEST ONLY GRD3 vector')
tiles=[]
for i in range(6):
 salt=hashlib.sha256(('TEST ONLY GRD3 salt '+str(i)).encode()).digest()[:16].hex();tiles.append(dict(index=i,salt=salt));m['commitments'].append(grd.commit(m,i,salt,grd.pixels(rgb,m,i)))
m['root']=grd.merkle(m['commitments']);doc=dict(manifest=m,signature=grd.b64(key.sign(grd.digest(m))),image=grd.png_write(rgb,w,h),tiles=tiles,redactions=[])
red=copy.deepcopy(doc);pixels=bytearray(rgb)
for y in range(64):pixels[y*w*3:y*w*3+64*3]=bytes(64*3)
red['image']=grd.png_write(pixels,w,h);red['tiles'][0]=dict(index=0,commitment=m['commitments'][0]);red['redactions']=[dict(index=0,method='black')]
sealed=grd.encode3(doc);redacted=grd.encode3(red);damaged=bytearray(sealed);damaged[-1]^=1
cases=[];conformance=json.loads((root/'conformance/vectors.json').read_text());conformance=[v for v in conformance if not v['id'].startswith('grd3-')]
for name,data,verdict in [('sealed',sealed,'GENUINE'),('redacted',redacted,'VERIFIED WITH REDACTIONS'),('tampered',bytes(damaged),'TAMPERED')]:
 id='grd3-'+name;file='conformance/files/'+id+'.GRD';(root/file).write_bytes(data)
 cases.append(dict(id=id,container=grd.b64(data),expected_verdict=verdict,expected_root=m['root']))
 conformance.append(dict(id=id,file=file,description='GRD3 TEST ONLY '+name,format=3,expected_verdict=verdict,expected_exit=grd.EXIT[verdict]))
(root/'tests/vectors/grd3-vectors.json').write_text(json.dumps(dict(notice='TEST ONLY public deterministic signing seed',public_key_hex=pk.hex(),vectors=cases),indent=2)+'\n')
(root/'conformance/vectors.json').write_text(json.dumps(conformance,indent=2)+'\n')
print('Generated 3 deterministic GRD3 conformance vectors')
