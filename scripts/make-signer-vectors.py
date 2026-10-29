#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Public deterministic TEST ONLY signer/exit vectors. Never use this seed for real identity."""
import sys,json,hashlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import grd
key=grd.Ed25519PrivateKey.from_private_bytes(bytes([48])*32);pk=key.public_key().public_bytes(grd.serialization.Encoding.Raw,grd.serialization.PublicFormat.Raw);fp=grd.sha(pk)
entry=dict(key_id=fp[:16],public_key_hex=pk.hex(),fingerprint_sha256=fp,name='Test Org (Tester)',alg='Ed25519',revoked=False,revokedAt=None,reason=None)
keys=dict(version=1,asOf='2026-10-29T00:00:00Z',signers=[entry]);cases=[];visual=[]
for version in (2,3):
 for purpose in ('asset','personal','demo'):
  counter=iter(range(1000))
  with patch('grd.os.urandom',side_effect=lambda n:hashlib.shake_256(f'TEST-ONLY-{next(counter)}'.encode()).digest(n)),patch('grd.datetime') as clock:
   clock.now.return_value.isoformat.return_value='2026-10-29T00:00:00+00:00';clock.now.return_value.strftime.return_value='2026-10-29T00:00:00Z';doc=grd.seal(grd.Image.new('RGB',(128,64),(100,100,100)),key,version=version,purpose=purpose)
  data=grd.encode(doc);cases.append(dict(id=f'grd{version}-{purpose}',container=grd.b64(data),status={'asset':'trusted','personal':'self','demo':'demo'}[purpose],expected_verdict={'asset':'GENUINE','personal':'UNVERIFIED: SELF-SIGNED','demo':'DEMO'}[purpose]))
  if purpose=='asset':
   cases.append(dict(id=f'grd{version}-redacted',container=grd.b64(grd.redact(data,[(0,0,64,64)])),status='trusted',expected_verdict='VERIFIED WITH REDACTIONS'))
   if version==3:
    proof=grd.export_proof(data)
    for name,delta,code in [('consistent',0,5),('borderline',9,7),('inconsistent',30,2)]:
     image=grd.io.BytesIO();grd.Image.new('RGB',(128,64),(100+delta,)*3).save(image,format='PNG');visual.append(dict(id=name,proof=grd.b64(proof),image=grd.b64(image.getvalue()),exit_code=code))
out=dict(notice='TEST ONLY deterministic public seed 48 repeated, not a production signer',keys=keys,cases=cases,visual=visual)
(grd.ROOT/'tests/vectors/signer-status-vectors.json').write_text(json.dumps(out,indent=2)+'\n');print('Wrote eight signer and three visual-exit cases')
