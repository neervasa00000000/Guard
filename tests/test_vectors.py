#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent Python conformance, malformed-input, fault and CLI regressions."""
import sys,json,copy,tempfile,subprocess,random
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import grd
root=grd.ROOT
vectors=json.loads((root/'tests/vectors/grd2-vectors.json').read_text())
pk=vectors['public_key_hex'];trusted=[pk]
for v in vectors['vectors']:
 r=grd.verify(grd.un64(v['container']),trusted)
 assert r['verdict']==v['expected_verdict'],(v['id'],r)
 if r.get('regionVerified'):assert r['root']==v['expected_root']
print('Shared deterministic vectors:',len(vectors['vectors']),'passed')
for v in json.loads((root/'conformance/vectors.json').read_text()):
 r=grd.verify((root/v['file']).read_bytes(),keys_path=root/'conformance/trusted-keys.test.json')
 assert r['verdict']==v['expected_verdict'],(v['id'],r)
 assert grd.EXIT[r['verdict']]==v['expected_exit']
print('Existing conformance vectors: all passed')
data=grd.un64(vectors['vectors'][4]['container'])
for body in [None,[],1,'text',{'manifest':None},dict(json.loads(data[5:]),tiles=None),dict(json.loads(data[5:]),redactions=[None])]:
 raw=b'GRD2\n'+json.dumps(body,separators=(',',':')).encode()
 assert grd.verify(raw,trusted)['verdict']=='TAMPERED',(body,grd.verify(raw,trusted))
assert grd.verify(data,trusted,dict(revoked='invalid'))['verdict']=='CANNOT VERIFY'
for fault in ('sha','png_read'):
 with patch.object(grd,fault,side_effect=RuntimeError('Injected verifier fault')):
  r=grd.verify(data,trusted);assert r['verdict']=='CANNOT VERIFY' and r['verifierFault'],r
for frac in (.5,.99):assert grd.verify(data[:int(len(data)*frac)],trusted)['verdict']=='TAMPERED'
assert grd.verify(data[:-1],trusted)['verdict']=='TAMPERED'
rng=random.Random(42)
for _ in range(200):
 flipped=bytearray(data);at=rng.randrange(5,len(data));flipped[at]^=1<<rng.randrange(8)
 r=grd.verify(bytes(flipped),trusted);assert r['verdict']=='TAMPERED',r
print('200 seeded body bit flips, malformed shapes, truncation and injected faults: passed')
doc=json.loads(data[5:]);rows=[]
for purpose,expected in [('asset',0),('demo',5),('personal',5)]:
 d=copy.deepcopy(doc);d['manifest']['purpose']=purpose
 key=grd.Ed25519PrivateKey.from_private_bytes(grd.hashlib.sha256(b'GUARD TEST VECTOR KEY - DO NOT USE').digest())
 d['signature']=grd.b64(key.sign(grd.digest(d['manifest'])));rows.append((grd.encode(d),expected,None))
rows.extend([(b'not a grd',3,None),(data[:-1],2,None),(data,4,{'revoked':'invalid'}),(data,6,dict(version=1,asOf='2026-10-27T00:00:00Z',revoked=[dict(fingerprint=grd.sha(bytes.fromhex(pk)),reason='TEST ONLY',revokedAt='2026-10-26T00:00:00Z')]))])
with tempfile.TemporaryDirectory() as temp:
 p=Path(temp);public=p/'public.pem';public.write_bytes(key.public_key().public_bytes(grd.serialization.Encoding.PEM,grd.serialization.PublicFormat.SubjectPublicKeyInfo))
 for raw,expected,policy in rows:
  source=p/'input.GRD';source.write_bytes(raw);args=[sys.executable,str(root/'grd.py'),'verify',str(source),'--trusted-key',str(public)]
  if policy is not None:
   policy_file=p/'policy.json';policy_file.write_text(json.dumps(policy));args+=['--policy',str(policy_file)]
  proc=subprocess.run(args,capture_output=True,text=True);assert proc.returncode==expected,(expected,proc.stdout,proc.stderr)
print('CLI verdict exit-code groups 0, 2, 3, 4, 5, 6: passed')

for edit in [lambda m:m.update(width=4097),lambda m:m.update(width=4096,height=2048),lambda m:m.update(width=4096,height=1025)]:
 d=copy.deepcopy(doc);edit(d['manifest']);assert grd.verify(grd.encode(d),trusted)['verdict']=='LIMIT EXCEEDED'
for v in vectors['vectors']:
 if v['expected_verdict']=='TAMPERED':
  try:grd.export_plain(grd.un64(v['container']))
  except ValueError:pass
  else:raise AssertionError('Export accepted tampered source '+v['id'])
print('Python dimension/tile limits and rejection of all tampered plain exports: passed')
