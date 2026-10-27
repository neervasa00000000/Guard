#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Deterministic TEST ONLY fine/visual upgrade vectors; no real private keys."""
import sys,json,hashlib,copy
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import grd
key=grd.Ed25519PrivateKey.from_private_bytes(bytes([42])*32);pk=key.public_key().public_bytes(grd.serialization.Encoding.Raw,grd.serialization.PublicFormat.Raw)
im=grd.Image.new('RGB',(131,79));im.putdata([(x%256,y%256,(x+y)%256) for y in range(79) for x in range(131)])
cases=[];visual=[];counter=0

def random_test_bytes(n):
 global counter
 counter+=1;return hashlib.sha256(('TEST ONLY upgrade bytes '+str(counter)).encode()).digest()[:n]
for version in (2,3):
 for sub_tile in (16,64):
  with patch.object(grd.os,'urandom',side_effect=random_test_bytes):doc=grd.seal(im,key,version=version,sub_tile=sub_tile)
  doc['manifest']['created']='2026-10-27T00:00:00Z';doc['signature']=grd.b64(key.sign(grd.digest(doc['manifest'])));data=grd.encode(doc)
  id=f'grd{version}-sub{sub_tile}'
  cases.append(dict(id=id+'-sealed',container=grd.b64(data),expected_verdict='GENUINE'))
  red=grd.redact(data,[(1,1,10,10)],granularity=sub_tile);cases.append(dict(id=id+'-redacted',container=grd.b64(red),expected_verdict='VERIFIED WITH REDACTIONS'))
  bad=copy.deepcopy(doc);bad['manifest']['label']='TEST ONLY changed';cases.append(dict(id=id+'-tampered',container=grd.b64(grd.encode(bad)),expected_verdict='TAMPERED'))
  if sub_tile==64:
   for name,source in [('sealed',data),('redacted',red)]:
    proof=grd.export_proof(source);r=grd.verify_v2(source,[pk.hex()],include_pixels=True)
    visual.append(dict(id=id+'-'+name,proof=grd.b64(proof),image=grd.b64(grd.png_write(r['_rgb'],131,79)),expected_verdict='VISUALLY CONSISTENT'))
out=dict(notice='TEST ONLY public deterministic signing seed and salts',public_key_hex=pk.hex(),vectors=cases,visual=visual)
(grd.ROOT/'tests/vectors/upgrade-vectors.json').write_text(json.dumps(out,indent=2)+'\n')
print('Generated',len(cases),'exact and',len(visual),'visual upgrade vectors')
