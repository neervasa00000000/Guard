#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Public TEST ONLY roots; never use these deterministic seeds for real identity."""
import sys,json,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import grd,trust_bundle
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
root=Ed25519PrivateKey.from_private_bytes(bytes([43])*32);issuer=Ed25519PrivateKey.from_private_bytes(bytes([44])*32)
raw=lambda k:k.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
root_hex=raw(root).hex();fp=grd.sha(raw(issuer));now=trust_bundle.date('2026-10-27T12:00:00Z')
payload=dict(format='GUARD-TRUST-1',sequence=2,issued='2026-10-27T00:00:00Z',expires='2026-11-27T00:00:00Z',keys=dict(version=1,asOf='2026-10-27T00:00:00Z',signers=[dict(key_id=fp[:16],public_key_hex=raw(issuer).hex(),fingerprint_sha256=fp,name='TEST ONLY issuer',alg='Ed25519',revoked=False,revokedAt=None,reason=None)]))
def encode(p):return grd.canon(dict(payload=p,signature=grd.b64(root.sign(trust_bundle.DOMAIN+grd.canon(p).encode())))).encode()
good=encode(payload);state=trust_bundle.verify_bundle(good,root_hex,now)['state'];cases=[]
def add(name,p=None,options=None,data=None):
 data=encode(p or payload) if data is None else data;options=options or {}
 try:expected=dict(ok=True,result=trust_bundle.verify_bundle(data,root_hex,now,min_sequence=options.get('minSequence',1),previous=options.get('previous')))
 except Exception:expected=dict(ok=False)
 cases.append(dict(id=name,bundle=grd.b64(data),options=options,expected=expected))
add('valid');add('idempotent',options=dict(previous=state))
p=copy.deepcopy(payload);p['expires']='2026-10-27T12:00:00Z';add('expiry-boundary',p)
p=copy.deepcopy(payload);p['sequence']=1;add('rollback',p,dict(previous=state))
p=copy.deepcopy(payload);p['keys']['signers'][0]['name']='Different';add('equivocation',p,dict(previous=state))
p=copy.deepcopy(payload);p['sequence']=3;p['keys']['signers'][0].update(revoked=True,revokedAt=p['issued'],reason='Test compromise');add('revoked',p,dict(previous=state))
p=copy.deepcopy(payload);p['keys']['signers'].append(copy.deepcopy(p['keys']['signers'][0]));add('duplicate',p)
p=copy.deepcopy(payload);p['issued']=p['keys']['asOf']='2026-10-28T00:00:00Z';add('future',p)
p=copy.deepcopy(payload);p['expires']='2027-11-27T00:00:00Z';add('excess-validity',p)
p=copy.deepcopy(payload);p['keys']['signers'][0]['fingerprint_sha256']='0'*64;add('bad-fingerprint',p)
p=copy.deepcopy(payload);p['keys']['signers'][0]['reason']='unexpected';add('bad-reason',p)
add('noncanonical',data=good+b'\n');changed=bytearray(good);changed[-8]^=1;add('forged-signature',data=bytes(changed));add('sequence-floor',options=dict(minSequence=3))
result=dict(notice='TEST ONLY deterministic public root and issuer; no production identity.',root=root_hex,now=now,cases=cases)
path=grd.ROOT/'results/trust-bundle-vectors.json';path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(result,indent=2)+'\n');print(f'Wrote {len(cases)} native-browser trust-bundle cases')
