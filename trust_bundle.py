#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline explicit-root trust bundles. No root generation, network or implicit trust."""
import argparse, base64, hashlib, json, os, tempfile, sys
from pathlib import Path
from datetime import datetime, timezone
import grd
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey, Ed25519PrivateKey
DOMAIN=b'GUARD-TRUST-BUNDLE-V1\0'
MAX_BYTES=2*1024*1024

def date(value):
 grd.policy_date(value)
 return datetime.strptime(value,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).timestamp()*1000

def exact(value,fields):
 return isinstance(value,dict) and set(value)==set(fields)

def verify_bundle(data,root_hex,now=None,min_sequence=1,previous=None):
 if not isinstance(data,bytes) or len(data)>MAX_BYTES:raise ValueError('Bundle exceeds input limit')
 if not grd.hx(root_hex):raise ValueError('An explicit Ed25519 root is required')
 doc=json.loads(data.decode('utf-8'))
 if not grd.valid_tree(doc) or not exact(doc,('payload','signature')) or grd.canon(doc).encode()!=data:raise ValueError('Noncanonical bundle')
 p=doc['payload']
 if not exact(p,('format','sequence','issued','expires','keys')) or p['format']!='GUARD-TRUST-1' or type(p['sequence']) is not int or not 1<=p['sequence']<=9007199254740991 or type(min_sequence) is not int or min_sequence<1 or p['sequence']<min_sequence:raise ValueError('Invalid bundle or rollback')
 now=datetime.now(timezone.utc).timestamp()*1000 if now is None else now
 issued,expires=date(p['issued']),date(p['expires'])
 if not isinstance(now,(int,float)) or not grd.math.isfinite(now) or issued>now or expires<=now or expires<=issued or expires-issued>90*86400000:raise ValueError('Bundle expired, future-dated or validity exceeds 90 days')
 keys=p['keys']
 if not exact(keys,('version','asOf','signers')) or type(keys['version']) is not int or keys['version']!=1 or keys['asOf']!=p['issued'] or not isinstance(keys['signers'],list) or len(keys['signers'])>4096:raise ValueError('Invalid bundle key snapshot')
 seen=set()
 for s in keys['signers']:
  if not exact(s,('key_id','public_key_hex','fingerprint_sha256','name','alg','revoked','revokedAt','reason')) or not grd.hx(s['public_key_hex']):raise ValueError('Invalid signer')
  fp=grd.sha(bytes.fromhex(s['public_key_hex']))
  if fp!=s['fingerprint_sha256'] or s['key_id']!=fp[:16] or fp in seen or s['alg']!='Ed25519' or not isinstance(s['name'],str) or not s['name'].strip(' \t\r\n') or len(s['name'].encode('utf-16-le'))//2>120 or type(s['revoked']) is not bool:raise ValueError('Invalid or duplicate signer')
  if s['revoked']:
   if not isinstance(s['reason'],str) or not s['reason'].strip(' \t\r\n') or date(s['revokedAt'])>issued:raise ValueError('Invalid revocation')
  elif s['revokedAt'] is not None or s['reason'] is not None:raise ValueError('Invalid revocation')
  seen.add(fp)
 root_fp=grd.sha(bytes.fromhex(root_hex));digest=grd.sha(data)
 if previous is not None:
  if not exact(previous,('rootFingerprint','sequence','digest')) or previous['rootFingerprint']!=root_fp or type(previous['sequence']) is not int or not 1<=previous['sequence']<=9007199254740991 or not grd.hx(previous['digest']) or p['sequence']<previous['sequence'] or (p['sequence']==previous['sequence'] and digest!=previous['digest']):raise ValueError('Bundle rollback, equivocation or cache/root mismatch')
 signature=grd.un64(doc['signature'])
 if len(signature)!=64:raise ValueError('Invalid bundle signature')
 Ed25519PublicKey.from_public_bytes(bytes.fromhex(root_hex)).verify(signature,DOMAIN+grd.canon(p).encode())
 return dict(keys=keys,anchors=[s for s in keys['signers'] if not s['revoked']],policy=dict(version=p['sequence'],asOf=p['issued'],revoked=[dict(fingerprint=s['fingerprint_sha256'],reason=s['reason'],revokedAt=s['revokedAt']) for s in keys['signers'] if s['revoked']]),state=dict(rootFingerprint=root_fp,sequence=p['sequence'],digest=digest),expires=p['expires'])

def read_bounded(path):
 if Path(path).stat().st_size>MAX_BYTES:raise ValueError('Bundle/state exceeds input limit')
 return Path(path).read_bytes()

def accept_cached_bundle(data,root_hex,state_path,min_sequence=1):
 # Advisory lock serializes this CLI's read/check/replace sequence on macOS/Linux.
 # The directory and cache are trusted local state; deleting them resets rollback protection.
 import fcntl
 state_path=Path(state_path)
 lock_fd=os.open(str(state_path)+'.lock',os.O_CREAT|os.O_RDWR,0o600)
 with os.fdopen(lock_fd,'a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  previous=json.loads(read_bounded(state_path)) if state_path.exists() else None
  result=verify_bundle(data,root_hex,min_sequence=min_sequence,previous=previous)
  fd,tmp=tempfile.mkstemp(prefix='.guard-state-',dir=state_path.parent)
  try:
   with os.fdopen(fd,'w') as f:f.write(grd.canon(result['state']));f.flush();os.fsync(f.fileno())
   os.replace(tmp,state_path)
  finally:
   if os.path.exists(tmp):os.unlink(tmp)
  return result

def main():
 parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
 sign=sub.add_parser('sign');sign.add_argument('--keys',required=True);sign.add_argument('--root-key',required=True);sign.add_argument('--sequence',required=True,type=int);sign.add_argument('--issued',required=True);sign.add_argument('--expires',required=True);sign.add_argument('-o','--output',required=True)
 verify=sub.add_parser('verify');verify.add_argument('input');verify.add_argument('--bundle',required=True);verify.add_argument('--root',required=True,help='Separately provisioned Ed25519 PUBLIC PEM');verify.add_argument('--state',required=True,help='Persistent local rollback-state path');verify.add_argument('--min-sequence',type=int,default=1)
 args=parser.parse_args()
 try:
  if args.command=='sign':
   keys=json.loads(read_bounded(args.keys));key=serialization.load_pem_private_key(Path(args.root_key).read_bytes(),password=None)
   if not isinstance(key,Ed25519PrivateKey):raise ValueError('Ed25519 private root required')
   p=dict(format='GUARD-TRUST-1',sequence=args.sequence,issued=args.issued,expires=args.expires,keys=keys)
   data=grd.canon(dict(payload=p,signature=grd.b64(key.sign(DOMAIN+grd.canon(p).encode())))).encode()
   root=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex()
   verify_bundle(data,root,now=date(args.issued));Path(args.output).open('xb').write(data);print('Wrote '+args.output);return 0
  key=serialization.load_pem_public_key(Path(args.root).read_bytes())
  if not isinstance(key,Ed25519PublicKey):raise ValueError('Ed25519 public root required')
  result=accept_cached_bundle(read_bounded(args.bundle),key.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex(),args.state,args.min_sequence)
  if Path(args.input).stat().st_size>256*1024*1024:raise ValueError('Image exceeds input limit')
  with tempfile.TemporaryDirectory(prefix='guard-bundle-') as folder:
   path=Path(folder)/'keys.json';path.write_text(grd.canon(result['keys']))
   report=grd.verify(Path(args.input).read_bytes(),[s['public_key_hex'] for s in result['anchors']],result['policy'],keys_path=path)
  report['trustBundle']=dict(sequence=result['state']['sequence'],expires=result['expires'],rootFingerprint=result['state']['rootFingerprint']);report['exit_code']=grd.EXIT.get(report['verdict'],4)
  print(json.dumps({k:v for k,v in report.items() if not k.startswith('_')},indent=2));return report['exit_code']
 except Exception as exc:
  print(json.dumps(dict(verdict='CANNOT VERIFY',genuine=False,problems=['Trust-bundle verification failed: '+(str(exc) or type(exc).__name__)],exit_code=4)));return 4
if __name__=='__main__':sys.exit(main())
