#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Deterministic public TEST ONLY vectors. Never use this signing key for real assets."""
import sys,hashlib,json,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import grd
seed=hashlib.sha256(b'GUARD TEST VECTOR KEY - DO NOT USE').digest()
key=grd.Ed25519PrivateKey.from_private_bytes(seed)
pk=key.public_key().public_bytes(grd.serialization.Encoding.Raw,grd.serialization.PublicFormat.Raw)
w,h=192,128
rgb=bytes(c for y in range(h) for x in range(w) for c in (x%256,y%256,(x+y)%256))
cases=[]
for profile in ('legacy','2.1'):
 m=dict(format='GRD2',version=2,width=w,height=h,tileSize=64,pixelFormat='RGB8',root='0'*64,commitments=[],publicKey=pk.hex(),keyId=grd.sha(pk),policy='tile-redaction-v1',purpose='asset',label='TEST ONLY shared vector')
 if profile=='2.1':m.update(profile='2.1',assetId=grd.b64(bytes(range(16))),created='2026-10-27T00:00:00Z')
 tiles=[]
 for i in range(6):
  salt=hashlib.sha256(('TEST ONLY salt '+str(i)).encode()).digest()[:16].hex()
  tiles.append(dict(index=i,salt=salt));m['commitments'].append(grd.commit(m,i,salt,grd.pixels(rgb,m,i)))
 m['root']=grd.merkle(m['commitments'])
 doc=dict(manifest=m,signature=grd.b64(key.sign(grd.digest(m))),image=grd.b64(grd.png_write(rgb,w,h)),tiles=tiles,redactions=[])
 def add(name,d,verdict):
  cases.append(dict(id=profile+'-'+name,container=grd.b64(grd.encode(d)),expected_verdict=verdict,expected_root=m['root']))
 add('sealed',doc,'GENUINE')
 red=copy.deepcopy(doc);pixels=bytearray(rgb)
 for y in range(64):pixels[y*w*3:y*w*3+64*3]=bytes(64*3)
 red['image']=grd.b64(grd.png_write(pixels,w,h));red['tiles'][0]=dict(index=0,commitment=m['commitments'][0]);red['redactions']=[dict(index=0,method='black')]
 add('redacted',red,'VERIFIED WITH REDACTIONS')
 dirty=copy.deepcopy(red);dirty['image']=doc['image'];add('fake-blackout',dirty,'TAMPERED')
 tampered=copy.deepcopy(doc);tampered['manifest']['root']='0'*64;add('tampered',tampered,'TAMPERED')
 if profile=='2.1':
  for field,value in [('assetId',grd.b64(bytes(16))),('created','2026-10-26T00:00:00Z')]:
   changed=copy.deepcopy(doc);changed['manifest'][field]=value;add('edited-'+field,changed,'TAMPERED')
# Valid PNG framing and CRCs around a deliberately damaged DEFLATE stream.
damaged=copy.deepcopy(doc);png=bytearray(grd.un64(doc['image']));at=8
while at<len(png):
 n=int.from_bytes(png[at:at+4],'big')
 if png[at+4:at+8]==b'IDAT':
  png[at+8]=0
  png[at+8+n:at+12+n]=grd.struct.pack('>I',grd.zlib.crc32(png[at+4:at+8+n])&0xffffffff)
  break
 at+=n+12
damaged['image']=grd.b64(png);add('damaged-deflate',damaged,'TAMPERED')
out=dict(notice='TEST ONLY: public deterministic key, never use for real assets',public_key_hex=pk.hex(),vectors=cases)
path=grd.ROOT/'tests/vectors/grd2-vectors.json';path.write_text(json.dumps(out,indent=2)+'\n')
print('Generated '+str(len(cases))+' deterministic TEST ONLY vectors')
