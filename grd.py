#!/usr/bin/env python3
"""Independent GRD1 verifier and GRD2 issuer/redactor. No private key is needed to redact."""
import argparse, base64, hashlib, io, json, os, re, struct, sys, zlib
from pathlib import Path
from datetime import datetime
from PIL import Image
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey, Ed25519PrivateKey
ROOT=Path(__file__).resolve().parent
PINNED=['97bb1a09fb958f21841c21dc2a400d87e333bcf1d1f7390525693319d1fce691']
MF={'format','version','width','height','tileSize','pixelFormat','root','commitments','publicKey','keyId','policy','purpose','label'}
def canon(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def sha(v):return hashlib.sha256(v).hexdigest()
def un64(v):
 if not isinstance(v,str):raise ValueError('Invalid base64 field')
 b=base64.b64decode(v,validate=True)
 if base64.b64encode(b).decode()!=v:raise ValueError('Noncanonical base64')
 return b
def b64(v):return base64.b64encode(v).decode()
def hx(v):return isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v) is not None
def bounds(m,i):
 cols=(m['width']+63)//64;x=i%cols*64;y=i//cols*64
 return dict(x=x,y=y,width=min(64,m['width']-x),height=min(64,m['height']-y))
def pixels(rgb,m,i):
 b=bounds(m,i);return b''.join(rgb[((b['y']+r)*m['width']+b['x'])*3:((b['y']+r)*m['width']+b['x']+b['width'])*3] for r in range(b['height']))
def commit(m,i,salt,rgb):return sha(b'GRD-TILE'+struct.pack('>I',i)+bytes.fromhex(salt)+rgb)
def merkle(cs):
 if not cs:raise ValueError('Empty tree')
 level=[hashlib.sha256(b'\0'+bytes.fromhex(c)).digest() for c in cs]
 while len(level)>1:level=[hashlib.sha256(b'\1'+level[i]+level[min(i+1,len(level)-1)]).digest() for i in range(0,len(level),2)]
 return level[0].hex()
def digest(m):return hashlib.sha256(b'GUARD-GRD2-MANIFEST-V1\0'+canon(m).encode()).digest()
def encode(doc):
 data=b'GRD2\n'+canon(doc).encode()
 if len(data)>32*1024*1024:raise ValueError('GRD2 exceeds 32 MiB')
 return data
def policy_check(pk,policy=None):
 p=policy if policy is not None else json.loads((ROOT/'src/trust-policy.json').read_text())
 if not isinstance(p,dict) or type(p.get('version')) is not int or p['version']<1 or not isinstance(p.get('asOf'),str) or not isinstance(p.get('revoked'),list):raise ValueError('Invalid offline trust policy')
 datetime.fromisoformat(p['asOf'].replace('Z','+00:00'))
 for entry in p['revoked']:
  if not isinstance(entry,dict) or not hx(entry.get('fingerprint')) or not isinstance(entry.get('reason'),str) or not isinstance(entry.get('revokedAt'),str):raise ValueError('Invalid revocation entry')
  datetime.fromisoformat(entry['revokedAt'].replace('Z','+00:00'))
 entry=next((e for e in p['revoked'] if e['fingerprint']==sha(pk)),None)
 return dict(revoked=bool(entry),fingerprint=sha(pk),reason=entry['reason'] if entry else None,policyVersion=p['version'],asOf=p['asOf'],scope='Bundled snapshot only; newer revocations may be unknown.')
def png_read(data):
 if len(data)<45 or data[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('Invalid PNG')
 at=8;size=None;found=False;ended=False
 while at+12<=len(data):
  n=struct.unpack_from('>I',data,at)[0];end=at+12+n
  if end>len(data):raise ValueError('Truncated PNG')
  kind=data[at+4:at+8];body=data[at+8:end-4]
  if zlib.crc32(data[at+4:end-4])&0xffffffff!=struct.unpack_from('>I',data,end-4)[0]:raise ValueError('PNG checksum failed')
  if kind==b'IHDR':
   if at!=8 or n!=13:raise ValueError('Invalid PNG header')
   w,h,depth,colour,comp,filt,interlace=struct.unpack('>IIBBBBB',body)
   if min(w,h)<1 or max(w,h)>4096 or w*h>4194304 or (depth,colour,comp,filt,interlace)!=(8,2,0,0,0):raise ValueError('GRD2 requires bounded RGB8 PNG')
   size=(w,h)
  elif kind==b'IDAT':
   if size is None:raise ValueError('PNG data before header')
   found=True
  elif kind==b'IEND':
   if n or not found or end!=len(data):raise ValueError('Invalid PNG end')
   ended=True;break
  else:raise ValueError('Unsupported PNG chunk')
  at=end
 if not ended:raise ValueError('Incomplete PNG')
 with Image.open(io.BytesIO(data)) as im:
  im.load()
  if im.mode!='RGB' or im.size!=size:raise ValueError('Wrong PNG dimensions or mode')
  return im.tobytes(),size[0],size[1]
def png_write(rgb,w,h):
 im=Image.frombytes('RGB',(w,h),bytes(rgb));out=io.BytesIO();im.save(out,format='PNG');return out.getvalue()
def validate_manifest(m):
 if not isinstance(m,dict) or set(m)!=MF or m['format']!='GRD2' or type(m['version']) is not int or m['version']!=2 or m['pixelFormat']!='RGB8' or type(m['tileSize']) is not int or m['tileSize']!=64 or m['policy']!='tile-redaction-v1' or m['purpose'] not in ('asset','demo'):raise ValueError('Unsupported manifest')
 if any(type(m[k]) is not int or m[k]<1 or m[k]>4096 for k in ('width','height')) or m['width']*m['height']>4194304:raise ValueError('Image limit exceeded')
 count=((m['width']+63)//64)*((m['height']+63)//64)
 if count>1024 or not isinstance(m['commitments'],list) or len(m['commitments'])!=count or not all(hx(c) for c in m['commitments']):raise ValueError('Invalid commitment grid')
 if not all(hx(m[k]) for k in ('root','keyId','publicKey')) or not isinstance(m['label'],str) or len(m['label'].encode('utf-16-le'))//2>120:raise ValueError('Invalid manifest fields')
 return count
def seal(image,key,purpose='asset',label=''):
 w,h=image.size
 if max(w,h)>4096 or w*h>4194304:raise ValueError('Image limit exceeded')
 rgba=image.convert('RGBA')
 raw=rgba.tobytes();rgb=bytes((raw[i+c]*raw[i+3]+255*(255-raw[i+3])+127)//255 for i in range(0,len(raw),4) for c in range(3))
 pk=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
 m=dict(format='GRD2',version=2,width=w,height=h,tileSize=64,pixelFormat='RGB8',root='0'*64,commitments=['0'*64]*(((w+63)//64)*((h+63)//64)),publicKey=pk.hex(),keyId=sha(pk),policy='tile-redaction-v1',purpose=purpose,label=label);count=validate_manifest(m);tiles=[]
 for i in range(count):
  salt=os.urandom(16).hex();m['commitments'][i]=commit(m,i,salt,pixels(rgb,m,i));tiles.append(dict(index=i,salt=salt))
 m['root']=merkle(m['commitments'])
 return dict(manifest=m,signature=b64(key.sign(digest(m))),image=b64(png_write(rgb,w,h)),tiles=tiles,redactions=[])
def verify_v2(data,trusted=None,policy=None):
 r=dict(version=2,verdict='TAMPERED',genuine=False,viewable=False,problems=[])
 try:
  if len(data)>32*1024*1024:raise ValueError('GRD2 exceeds 32 MiB')
  raw=data[5:].decode('utf-8');doc=json.loads(raw)
  if set(doc)!={'manifest','signature','image','tiles','redactions'}:raise ValueError('Unexpected container fields')
  m=doc['manifest'];count=validate_manifest(m)
  if len(doc['tiles'])!=count:raise ValueError('Incomplete tile grid')
  hidden=[]
  for i,t in enumerate(doc['tiles']):
   if not isinstance(t,dict) or type(t.get('index')) is not int or t.get('index')!=i or set(t) not in ({'index','salt'},{'index','commitment'}):raise ValueError('Invalid tile entry')
   if 'commitment' in t:hidden.append(i)
  if len(doc['redactions'])!=len(hidden):raise ValueError('REDACTIONS does not match TILES')
  for i,entry in enumerate(doc['redactions']):
   if set(entry)!={'index','method'} or type(entry['index']) is not int or entry['index']!=hidden[i] or entry['method'] not in ('black','blur'):raise ValueError('REDACTIONS does not match hidden tiles')
  if canon(doc)!=raw:raise ValueError('Noncanonical JSON')
  pk=bytes.fromhex(m['publicKey'])
  if sha(pk)!=m['keyId']:raise ValueError('Wrong signer fingerprint')
  r['revocation']=policy_check(pk,policy)
  if r['revocation']['revoked']:r['verdict']='REVOKED KEY';raise ValueError('Revoked signer')
  Ed25519PublicKey.from_public_bytes(pk).verify(un64(doc['signature']),digest(m));r['signature_valid']=True
  if merkle(m['commitments'])!=m['root']:raise ValueError('Signed root mismatch')
  rgb,w,h=png_read(un64(doc['image']))
  if (w,h)!=(m['width'],m['height']):raise ValueError('Wrong image dimensions')
  for i,t in enumerate(doc['tiles']):
   if 'commitment' in t:
    if t['commitment']!=m['commitments'][i]:raise ValueError('Wrong commitment at tile '+str(i))
   else:
    if not isinstance(t['salt'],str) or not re.fullmatch('[0-9a-f]{32}',t['salt']) or commit(m,i,t['salt'],pixels(rgb,m,i))!=m['commitments'][i]:raise ValueError('Non-redacted tile '+str(i)+' changed')
  r.update(root=m['root'],tilesTotal=count,tilesVisible=count-len(hidden),redactedTiles=hidden,redactionMap=[dict(index=i,**bounds(m,i),method=doc['redactions'][n]['method']) for n,i in enumerate(hidden)],regionVerified=True,redactionApproval='not_attested',_document=doc,_rgb=rgb)
  is_demo=m['purpose']=='demo';is_trusted=m['publicKey'] in (PINNED if trusted is None else trusted)
  if not is_trusted and not is_demo:r['verdict']='UNTRUSTED SIGNER'
  elif not r['tilesVisible']:r['verdict']='FULLY REDACTED'
  else:r.update(verdict='DEMO' if is_demo else 'VERIFIED WITH REDACTIONS' if hidden else 'GENUINE',genuine=is_trusted and not is_demo and not hidden,viewable=True)
 except Exception as exc:r['problems'].append(str(exc) or type(exc).__name__)
 return r
def verify_v1(data,trusted=None,policy=None):
 r=dict(version=1,verdict='TAMPERED',genuine=False,problems=[])
 try:
  if len(data)>64*1024*1024:raise ValueError('Size limit')
  if len(data)<10 or data[:4]!=b'GRD1':r['verdict']='NOT A GRD';raise ValueError('Bad header')
  version,flags,n=struct.unpack_from('<HHH',data,4)
  if version!=1:r['verdict']='UNSUPPORTED';raise ValueError('Unsupported version')
  if not 4<=n<=7 or len(data)<10+50*n:raise ValueError('Bad table')
  expected=10+50*n;sections={};entries=[]
  for i in range(n):
   typ,offset,length,digest_bytes=struct.unpack_from('<HQQ32s',data,10+50*i)
   if typ not in range(1,8) or typ in sections or offset!=expected or offset+length>len(data):raise ValueError('Bad section structure')
   sections[typ]=data[offset:offset+length];entries.append((typ,offset,length,digest_bytes));expected+=length
  if expected!=len(data) or not {1,2,6,7}<=sections.keys() or entries[-1][0]!=7 or len(sections[7])!=64 or entries[-1][3]!=bytes(32):raise ValueError('Bad signature entry or length')
  if bool(flags&1)!=(5 in sections) or bool(flags&2)!=(4 in sections) or flags&~3:raise ValueError('Bad flags')
  for typ,off,length,dg in entries[:-1]:
   if hashlib.sha256(sections[typ]).digest()!=dg:raise ValueError('Section hash mismatch: '+str(typ))
  if len(sections[6])!=40:raise ValueError('Bad public key')
  kid=sections[6][:8].hex();pk=sections[6][8:]
  r['revocation']=policy_check(pk,policy)
  if r['revocation']['revoked']:r['verdict']='REVOKED KEY';raise ValueError('Revoked signer')
  if sha(pk)[:16]!=kid or pk.hex() not in (PINNED if trusted is None else trusted):raise ValueError('Unknown signer')
  Ed25519PublicKey.from_public_bytes(pk).verify(sections[7],hashlib.sha256(data[:entries[-1][1]]).digest())
  if not sections[1] or len(sections[1])>256*1024:raise ValueError('Metadata size limit')
  raw=sections[1].decode();m=json.loads(raw)
  if not isinstance(m,dict) or canon(m)!=raw or m.get('asset_id')!=sha(sections[2])[:15] or m.get('key_id')!=kid:raise ValueError('Metadata mismatch')
  with Image.open(io.BytesIO(sections[2])) as image:
   if image.format not in ('PNG','JPEG','WEBP') or min(image.size)<1 or max(image.size)>16384 or image.width*image.height>40000000:raise ValueError('Unsupported or oversized image')
   if image.size!=(m.get('width'),m.get('height')):raise ValueError('Image dimension mismatch')
   image.load()
  r.update(verdict='GENUINE',genuine=True)
 except Exception as exc:r['problems'].append(str(exc) or type(exc).__name__)
 return r
def verify(data,trusted=None,policy=None):return verify_v2(data,trusted,policy) if data.startswith(b'GRD2\n') else verify_v1(data,trusted,policy)
def redact(data,rects,mode='black'):
 r=verify_v2(data)
 if not r.get('regionVerified'):raise ValueError('Source proof does not verify: '+str(r['problems']))
 doc=r['_document'];m=doc['manifest'];rgb=bytearray(r['_rgb']);selected=set()
 for x,y,w,h in rects:
  if w<=0 or h<=0:raise ValueError('Invalid rectangle')
  for i in range(len(doc['tiles'])):
   b=bounds(m,i)
   if b['x']<x+w and b['x']+b['width']>x and b['y']<y+h and b['y']+b['height']>y:selected.add(i)
 if not selected:raise ValueError('No tiles selected')
 methods={x['index']:x['method'] for x in doc['redactions']}
 for i in selected:
  t=doc['tiles'][i]
  if 'salt' not in t:continue
  b=bounds(m,i);original=pixels(rgb,m,i);doc['tiles'][i]=dict(index=i,commitment=m['commitments'][i]);methods[i]=mode
  for y in range(b['height']):
   for x in range(b['width']):
    dst=((b['y']+y)*m['width']+b['x']+x)*3
    if mode=='black':rgb[dst:dst+3]=b'\0\0\0'
    else:
     samples=[original[(yy*b['width']+xx)*3:(yy*b['width']+xx)*3+3] for yy in range(max(0,y-12),min(b['height']-1,y+12)+1,3) for xx in range(max(0,x-12),min(b['width']-1,x+12)+1,3)]
     rgb[dst:dst+3]=bytes(int(sum(s[c] for s in samples)/len(samples)+.5) for c in range(3))
 doc['image']=b64(png_write(rgb,m['width'],m['height']));doc['redactions']=[dict(index=i,method=methods[i]) for i in sorted(methods)];return encode(doc)
def main():
 parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
 s=sub.add_parser('seal');s.add_argument('input');s.add_argument('--key',required=True);s.add_argument('-o','--output',required=True);s.add_argument('--label',default='')
 v=sub.add_parser('verify');v.add_argument('input');v.add_argument('--trusted-key',action='append',default=[]);v.add_argument('--policy')
 rd=sub.add_parser('redact');rd.add_argument('input');rd.add_argument('--rect',action='append',required=True);rd.add_argument('--mode',choices=['black','blur'],default='black');rd.add_argument('-o','--output',required=True)
 args=parser.parse_args()
 try:
  if Path(args.input).stat().st_size>64*1024*1024:raise ValueError('Input size limit')
  data=Path(args.input).read_bytes()
  if args.command=='seal':
   key=serialization.load_pem_private_key(Path(args.key).read_bytes(),password=None)
   if not isinstance(key,Ed25519PrivateKey):raise ValueError('Ed25519 key required')
   with Image.open(io.BytesIO(data)) as im:output=encode(seal(im,key,label=args.label))
  elif args.command=='redact':output=redact(data,[tuple(map(int,r.split(','))) for r in args.rect],args.mode)
  else:
   trusted=PINNED+[serialization.load_pem_public_key(Path(p).read_bytes()).public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex() for p in args.trusted_key];r=verify(data,trusted,json.loads(Path(args.policy).read_text()) if args.policy else None);print(json.dumps({k:v for k,v in r.items() if not k.startswith('_')},indent=2));return 0 if r['verdict'] in ('GENUINE','VERIFIED WITH REDACTIONS','DEMO','FULLY REDACTED') else 2
  with open(args.output,'xb') as handle:handle.write(output)
  print('Wrote '+args.output);return 0
 except Exception as exc:print('GRD error: '+str(exc),file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
