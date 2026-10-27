#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent GRD1 verifier and GRD2 issuer/redactor. No private key is needed to redact."""
import grd3_codec, grd_visual, grd_subtiles
import argparse, base64, hashlib, io, json, os, re, struct, sys, zlib, math
from pathlib import Path
ROOT=Path(__file__).resolve().parent
for _p in ROOT.glob('.venv/lib/python*/site-packages'):
 if str(_p) not in sys.path:
  sys.path.insert(0, str(_p))
from datetime import datetime, timezone
from PIL import Image
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey, Ed25519PrivateKey
from cryptography.exceptions import InvalidSignature

class IntegrityError(Exception): pass
class PolicyError(Exception): pass
class ResourceLimitError(IntegrityError): pass
PROOF_ERRORS=(IntegrityError, UnicodeError, json.JSONDecodeError, zlib.error, InvalidSignature)

EXIT = {
 'GENUINE':0, 'TAMPERED':2, 'VISUALLY CONSISTENT':5, 'BORDERLINE (decoder-dependent)':5, 'VISUALLY INCONSISTENT':2, 'NOT A GRD':3,
 'CANNOT VERIFY':4, 'UNSUPPORTED':4, 'LIMIT EXCEEDED':4, 'UNREADABLE':4,
 'VERIFIED WITH REDACTIONS':5, 'FULLY REDACTED':5, 'DEMO':5,
 'UNVERIFIED: SELF-SIGNED':5, 'UNTRUSTED SIGNER':5, 'REVOKED KEY':6,
}

MF={'format','version','width','height','tileSize','pixelFormat','root','commitments','publicKey','keyId','policy','purpose','label'}

def load_trusted_keys(path=ROOT/'src/trusted-keys.json'):
 path=Path(path)
 try:
  data=json.loads(path.read_text())
  if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('asOf'),str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',data['asOf']):
   raise ValueError('Trusted-keys file is invalid.')
  datetime.strptime(data['asOf'],'%Y-%m-%dT%H:%M:%SZ')
  if not isinstance(data.get('signers'),list):raise ValueError('Trusted-keys file is invalid.')
  for s in data['signers']:
   if not isinstance(s,dict):raise ValueError('Trusted-keys file is invalid.')
   name=s.get('name')
   if not isinstance(name,str) or not (1<=len(name)<=120):raise ValueError('Trusted-keys file is invalid.')
   pk=s.get('public_key_hex')
   if not isinstance(pk,str) or not re.fullmatch(r'[0-9a-f]{64}',pk):raise ValueError('Trusted-keys file is invalid.')
   fp=s.get('fingerprint_sha256')
   if not isinstance(fp,str) or fp!=hashlib.sha256(bytes.fromhex(pk)).hexdigest():raise ValueError('Trusted-keys file is invalid.')
   kid=s.get('key_id')
   if not isinstance(kid,str) or kid!=fp[:16]:raise ValueError('Trusted-keys file is invalid.')
   if s.get('alg')!='Ed25519':raise ValueError('Trusted-keys file is invalid.')
   if not isinstance(s.get('revoked'),bool):raise ValueError('Trusted-keys file is invalid.')
   revoked_at=s.get('revokedAt')
   if s['revoked']:
    if not isinstance(revoked_at,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',revoked_at):
     raise ValueError('Trusted-keys file is invalid.')
    datetime.strptime(revoked_at,'%Y-%m-%dT%H:%M:%SZ')
   else:
    if revoked_at is not None:raise ValueError('Trusted-keys file is invalid.')
  return data
 except Exception:
  raise ValueError('Trusted-keys file is invalid.')

def get_pinned_signers(path=ROOT/'src/trusted-keys.json'):
 path=Path(path)
 tk=load_trusted_keys(path)
 return [s['public_key_hex'] for s in tk['signers'] if not s.get('revoked')]

def canon(v):
 if isinstance(v,dict):return '{'+','.join(json.dumps(k,ensure_ascii=False)+':'+canon(v[k]) for k in sorted(v,key=lambda x:x.encode('utf-16-be')))+'}'
 if isinstance(v,list):return '['+','.join(canon(x) for x in v)+']'
 if type(v) is float and math.isfinite(v) and v.is_integer():v=int(v)
 return json.dumps(v,ensure_ascii=False,separators=(',',':'),allow_nan=False)

def valid_tree(v,depth=0):
 if depth>32:return False
 if type(v) in (int,float):return math.isfinite(v) and v==int(v) and abs(v)<=9007199254740991
 if isinstance(v,str):
  try:v.encode('utf-8');return True
  except UnicodeError:return False
 if isinstance(v,list):return all(valid_tree(x,depth+1) for x in v)
 if isinstance(v,dict):return all(valid_tree(k,depth+1) and valid_tree(x,depth+1) for k,x in v.items())
 return v is None or type(v) is bool

def policy_date(v):
 if not isinstance(v,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',v):raise PolicyError('Invalid policy date')
 try:datetime.strptime(v,'%Y-%m-%dT%H:%M:%SZ')
 except ValueError as exc:raise PolicyError('Invalid policy date') from exc

def sha(v):return hashlib.sha256(v).hexdigest()

def un64(v):
 if not isinstance(v,str):raise IntegrityError('Invalid base64 field')
 try:b=base64.b64decode(v,validate=True)
 except Exception as e:raise IntegrityError(str(e))
 if base64.b64encode(b).decode()!=v:raise IntegrityError('Noncanonical base64')
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
 if not cs:raise IntegrityError('Empty tree')
 level=[hashlib.sha256(b'\0'+bytes.fromhex(c)).digest() for c in cs]
 while len(level)>1:level=[hashlib.sha256(b'\1'+level[i]+level[min(i+1,len(level)-1)]).digest() for i in range(0,len(level),2)]
 return level[0].hex()

def digest(m):return hashlib.sha256((b'GUARD-GRD3-MANIFEST-V1\0' if m['version']==3 else b'GUARD-GRD2-MANIFEST-V1\0')+canon(m).encode()).digest()

def encode3(doc):return grd3_codec.encode3(doc,sys.modules[__name__])
def decode3(data):return grd3_codec.decode3(data,sys.modules[__name__])
def image_bytes(doc):return doc['image'] if isinstance(doc['image'],(bytes,bytearray,memoryview)) else un64(doc['image'])

def encode(doc):
 if doc['manifest'].get('version')==3:return encode3(doc)
 data=b'GRD2\n'+canon(doc).encode()
 if len(data)>32*1024*1024:raise IntegrityError('GRD2 exceeds 32 MiB')
 return data

def policy_check(pk,policy=None,keys_path=ROOT/'src/trusted-keys.json'):
 keys_path=Path(keys_path)
 try:p=policy if policy is not None else json.loads((ROOT/'src/trust-policy.json').read_text())
 except (OSError,ValueError,UnicodeError) as exc:raise PolicyError('Invalid local trust policy') from exc
 if not isinstance(p,dict) or type(p.get('version')) is not int or not 1<=p['version']<=9007199254740991 or not isinstance(p.get('asOf'),str) or not isinstance(p.get('revoked'),list):raise PolicyError('Invalid offline trust policy')
 policy_date(p['asOf'])
 for entry in p['revoked']:
  if not isinstance(entry,dict) or not hx(entry.get('fingerprint')) or not isinstance(entry.get('reason'),str) or not isinstance(entry.get('revokedAt'),str):raise PolicyError('Invalid revocation entry')
  policy_date(entry['revokedAt'])
 rev_list=list(p['revoked'])
 try:
  tk=load_trusted_keys(keys_path)
  for s in tk['signers']:
   if s.get('revoked'):
    rev_list.append(dict(fingerprint=s['fingerprint_sha256'],reason=s.get('reason') or 'Revoked key',revokedAt=s.get('revokedAt')))
 except Exception:
  pass
 entry=next((e for e in rev_list if e['fingerprint']==sha(pk)),None)
 return dict(revoked=bool(entry),fingerprint=sha(pk),reason=entry['reason'] if entry else None,policyVersion=p['version'],asOf=p['asOf'],scope='Bundled snapshot only; newer revocations may be unknown.')

def png_read(data):
 if len(data)<45 or data[:8]!=b'\x89PNG\r\n\x1a\n':raise IntegrityError('Invalid PNG')
 at=8;size=None;found=False;ended=False;idats=[]
 while at+12<=len(data):
  n=struct.unpack_from('>I',data,at)[0];end=at+12+n
  if end>len(data):raise IntegrityError('Truncated PNG')
  kind=data[at+4:at+8];body=data[at+8:end-4]
  if zlib.crc32(data[at+4:end-4])&0xffffffff!=struct.unpack_from('>I',data,end-4)[0]:raise IntegrityError('PNG checksum failed')
  if kind==b'IHDR':
   if at!=8 or n!=13:raise IntegrityError('Invalid PNG header')
   w,h,depth,colour,comp,filt,interlace=struct.unpack('>IIBBBBB',body)
   if min(w,h)<1 or max(w,h)>4096 or w*h>4194304 or (depth,colour,comp,filt,interlace)!=(8,2,0,0,0):raise IntegrityError('GRD2 requires bounded RGB8 PNG')
   size=(w,h)
  elif kind==b'IDAT':
   if size is None:raise IntegrityError('PNG data before header')
   found=True;idats.append(body)
  elif kind==b'IEND':
   if n or not found or end!=len(data):raise IntegrityError('Invalid PNG end')
   ended=True;break
  else:raise IntegrityError('Unsupported PNG chunk')
  at=end
 if not ended:raise IntegrityError('Incomplete PNG')
 expected=size[1]*(size[0]*3+1);inflater=zlib.decompressobj();raw=inflater.decompress(b''.join(idats),expected+1)
 if len(raw)!=expected or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:raise IntegrityError('Invalid PNG pixel stream')
 if any(raw[row*(size[0]*3+1)]>4 for row in range(size[1])):raise IntegrityError('Unknown PNG filter')
 with Image.open(io.BytesIO(data)) as im:
  im.load()
  if im.mode!='RGB' or im.size!=size:raise IntegrityError('Wrong PNG dimensions or mode')
  return im.tobytes(),size[0],size[1]

def png_write(rgb,w,h):
 im=Image.frombytes('RGB',(w,h),bytes(rgb));out=io.BytesIO();im.save(out,format='PNG');return out.getvalue()

def validate_manifest(m):
 v3=isinstance(m,dict) and m.get("version")==3
 limits=grd3_codec.LIMITS if v3 else dict(dimension=4096,pixels=4194304,tiles=1024)
 if not isinstance(m,dict) or set(m)!=(MF|{'profile','assetId','created'}|({'visual'} if 'visual' in m else set())|({'subTile'} if 'subTile' in m else set()) if 'profile' in m else MF) or m['format']!=('GRD3' if v3 else 'GRD2') or type(m['version']) is not int or m['version'] not in (2,3) or m['pixelFormat']!='RGB8' or type(m['tileSize']) is not int or m['tileSize']!=64 or m['policy']!='tile-redaction-v1' or m['purpose'] not in ('asset','demo','personal'):raise IntegrityError('Unsupported manifest')
 if 'subTile' in m and (type(m['subTile']) is not int or m['subTile'] not in (8,16,32)):raise IntegrityError('Invalid sealed sub-tile size')
 if 'profile' in m:
  if m['profile']!=((('3.3' if 'visual' in m else '3.1') if 'subTile' in m else ('3.2' if 'visual' in m else '3.0')) if v3 else (('2.4' if 'visual' in m else '2.2') if 'subTile' in m else ('2.3' if 'visual' in m else '2.1'))) or len(un64(m['assetId']))!=16:raise IntegrityError('Invalid manifest profile or asset ID')
  try:policy_date(m['created'])
  except PolicyError as exc:raise IntegrityError('Invalid signer-claimed creation time') from exc
 if any(type(m[k]) is not int or m[k]<1 for k in ('width','height')):raise IntegrityError('Invalid image dimensions')
 if max(m['width'],m['height'])>limits['dimension'] or m['width']*m['height']>limits['pixels']:raise ResourceLimitError('Image limit exceeded')
 count=((m['width']+63)//64)*((m['height']+63)//64)
 if 'visual' in m:
  visual=m['visual']
  if not isinstance(visual,dict) or set(visual)!={'version','tau','commitments'} or visual['version']!='y8c16-v1' or type(visual['tau']) is not int or visual['tau']!=9 or not isinstance(visual['commitments'],list) or len(visual['commitments'])!=count or not all(hx(v) for v in visual['commitments']):raise IntegrityError('Invalid signed visual layer')
 if count>limits['tiles']:raise ResourceLimitError('Tile limit exceeded')
 if not isinstance(m['commitments'],list) or len(m['commitments'])!=count or not all(hx(c) for c in m['commitments']):raise IntegrityError('Invalid commitment grid')
 if not all(hx(m[k]) for k in ('root','keyId','publicKey')) or not isinstance(m['label'],str) or len(m['label'].encode('utf-16-le'))//2>120:raise IntegrityError('Invalid manifest fields')
 return count

def seal(image,key,purpose='asset',label='',version=None,visual=True,sub_tile=64):
 w,h=image.size
 if version is None:version=3 if max(w,h)>4096 or w*h>4194304 or ((w+63)//64)*((h+63)//64)>1024 else 2
 limits=grd3_codec.LIMITS if version==3 else dict(dimension=4096,pixels=4194304)
 if max(w,h)>limits['dimension'] or w*h>limits['pixels']:raise ValueError('Image limit exceeded')
 if image.mode=='RGB':rgb=image.tobytes()
 else:
  rgba=image.convert('RGBA');flattened=Image.new('RGBA',(w,h),'white');flattened.alpha_composite(rgba);rgb=flattened.tobytes('raw','RGB');del rgba,flattened
 pk=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
 m=dict(format='GRD3' if version==3 else 'GRD2',version=version,profile=(('3.3' if visual else '3.1') if sub_tile!=64 else ('3.2' if visual else '3.0')) if version==3 else (('2.4' if visual else '2.2') if sub_tile!=64 else ('2.3' if visual else '2.1')),assetId=b64(os.urandom(16)),created=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),width=w,height=h,tileSize=64,pixelFormat='RGB8',root='0'*64,commitments=['0'*64]*(((w+63)//64)*((h+63)//64)),publicKey=pk.hex(),keyId=sha(pk),policy='tile-redaction-v1',purpose=purpose,label=label)
 if sub_tile!=64:m['subTile']=sub_tile
 if visual:m['visual']=dict(version='y8c16-v1',tau=9,commitments=['0'*64]*len(m['commitments']))
 count=validate_manifest(m);tiles=[]
 for i in range(count):
  salt=os.urandom(16).hex();m['commitments'][i]=grd_subtiles.seal(m,i,salt,pixels(rgb,m,i),sys.modules[__name__])[0] if 'subTile' in m else commit(m,i,salt,pixels(rgb,m,i));tiles.append(dict(index=i,seed=salt) if 'subTile' in m else dict(index=i,salt=salt))
  if visual:m['visual']['commitments'][i]=grd_visual.commitment(i,grd_visual.salt(salt),grd_visual.tile_features(rgb,m,i,sys.modules[__name__]),sys.modules[__name__])
 m['root']=merkle(m['commitments'])
 return dict(manifest=m,signature=b64(key.sign(digest(m))),image=grd3_codec.png_write_stream(rgb,w,h) if version==3 else b64(png_write(rgb,w,h)),tiles=tiles,redactions=[])

def verify_v2(data,trusted=None,policy=None,keys_path=ROOT/'src/trusted-keys.json',include_pixels=False):
 if data.startswith(b'GRD3\n'):return grd3_codec.verify3(data,trusted,policy,Path(keys_path),sys.modules[__name__],include_pixels)
 keys_path=Path(keys_path)
 r=dict(version=2,verdict='TAMPERED',genuine=False,viewable=False,problems=[],hiddenPixelsCleared=True)
 try:
  if len(data)>32*1024*1024:
   r['verdict']='LIMIT EXCEEDED'
   raise IntegrityError('GRD2 exceeds 32 MiB')
  if not data.startswith(b'GRD2\n'):
   r['verdict']='NOT A GRD'
   raise IntegrityError('Missing GRD2 header')
  try:raw=data[5:].decode('utf-8')
  except UnicodeError as e:raise IntegrityError('Invalid UTF-8: '+str(e))
  try:doc=json.loads(raw)
  except (json.JSONDecodeError,RecursionError) as e:raise IntegrityError('Invalid JSON: '+str(e))
  if not isinstance(doc,dict) or set(doc)!={'manifest','signature','image','tiles','redactions'}:raise IntegrityError('Unexpected container fields')
  m=doc['manifest'];count=validate_manifest(m)
  if not isinstance(doc['tiles'],list) or not isinstance(doc['redactions'],list) or len(doc['tiles'])!=count:raise IntegrityError('Incomplete tile grid')
  hidden=[]
  for i,t in enumerate(doc['tiles']):
   if 'subTile' in m:
    grd_subtiles.validate(m,t,i,sys.modules[__name__])
    if 'commitment' in t or 'sub' in t:hidden.append(i)
   else:
    if not isinstance(t,dict) or type(t.get('index')) is not int or t.get('index')!=i or set(t) not in ({'index','salt'},{'index','commitment'}):raise IntegrityError('Invalid tile entry')
    if 'commitment' in t:hidden.append(i)
  if len(doc['redactions'])!=len(hidden):raise IntegrityError('REDACTIONS does not match TILES')
  for i,entry in enumerate(doc['redactions']):
   if not isinstance(entry,dict) or set(entry)!={'index','method'} or type(entry['index']) is not int or entry['index']!=hidden[i] or entry['method'] not in ('black','blur'):raise IntegrityError('REDACTIONS does not match hidden tiles')
  if not valid_tree(doc) or canon(doc)!=raw:raise IntegrityError('Noncanonical JSON')
  pk=bytes.fromhex(m['publicKey'])
  if sha(pk)!=m['keyId']:raise IntegrityError('Wrong signer fingerprint')
  r['revocation']=policy_check(pk,policy,keys_path)
  if r['revocation']['revoked']:
   r['verdict']='REVOKED KEY'
   raise IntegrityError('Revoked signer')
  try:
   Ed25519PublicKey.from_public_bytes(pk).verify(un64(doc['signature']),digest(m))
   r['signature_valid']=True
  except InvalidSignature as e:
   raise IntegrityError('Invalid signature: '+str(e))
  if merkle(m['commitments'])!=m['root']:raise IntegrityError('Signed root mismatch')
  rgb,w,h=png_read(un64(doc['image']))
  if (w,h)!=(m['width'],m['height']):raise IntegrityError('Wrong image dimensions')

  for entry in doc['redactions']:
   i=entry['index']
   if 'subTile' in m and entry['method']!='black':raise IntegrityError('Sub-tile files support blackout only')
   if 'subTile' in m and 'sub' in doc['tiles'][i]:continue
   if entry['method']=='blur':
    r['hiddenPixelsCleared']=False
    r['problems'].append('Legacy blur redaction (tile '+str(i)+'): replacement pixels are not verified.')
   elif any(pixels(rgb,m,i)):
    r['hiddenPixelsCleared']=False
    raise IntegrityError('blackout incomplete (tile '+str(i)+')')

  for i,t in enumerate(doc['tiles']):
   if 'subTile' in m:
    grd_subtiles.verify(m,t,i,pixels(rgb,m,i),sys.modules[__name__]);continue
   if 'commitment' in t:
    if t['commitment']!=m['commitments'][i]:raise IntegrityError('Wrong commitment at tile '+str(i))
   else:
    if not isinstance(t['salt'],str) or not re.fullmatch('[0-9a-f]{32}',t['salt']) or commit(m,i,t['salt'],pixels(rgb,m,i))!=m['commitments'][i]:raise IntegrityError('Non-redacted tile '+str(i)+' changed')
  if 'assetId' not in m:r['problems'].append('legacy manifest: no asset ID')
  r.update(assetId=m.get('assetId'),created=m.get('created'),root=m['root'],tilesTotal=count,tilesVisible=count-len(hidden),redactedTiles=hidden,redactionMap=[dict(index=i,**bounds(m,i),claimedMethod=doc['redactions'][n]['method'],methodAttested=False) for n,i in enumerate(hidden)],regionVerified=True,redactionApproval='not_attested',_document=doc,_rgb=rgb)
  if 'subTile' in m:
   r['redactionMap']=grd_subtiles.redaction_map(doc,sys.modules[__name__]);r['subTile']=m['subTile'];r['subTilesTotal']=sum(grd_subtiles.count(m,i,sys.modules[__name__]) for i in range(count));r['subTilesVisible']=sum(grd_subtiles.count(m,t['index'],sys.modules[__name__]) if 'seed' in t else sum('salt' in s for s in t.get('sub',[])) for t in doc['tiles'])
  is_demo=m['purpose']=='demo';is_personal=m['purpose']=='personal';is_trusted=not is_personal and m['publicKey'] in (get_pinned_signers(keys_path) if trusted is None else trusted)
  name=None
  try:
   tk=load_trusted_keys(keys_path)
   for s in tk['signers']:
    if s.get('public_key_hex')==m['publicKey']:
     name=s.get('name');break
  except Exception:
   pass
  if is_demo:r['signer']='Demonstration signer (not an identity claim)'
  elif is_personal:r['signer']='Untrusted signer'
  elif name:r['signer']=name;r['signerName']=name
  else:r['signer']='Untrusted signer'
  if not is_trusted and not is_demo and not is_personal:r['verdict']='UNTRUSTED SIGNER'
  elif not any('salt' in t or 'seed' in t or any('salt' in s for s in t.get('sub',[])) for t in doc['tiles']):r['verdict']='FULLY REDACTED'
  else:r.update(verdict='DEMO' if is_demo else 'UNVERIFIED: SELF-SIGNED' if is_personal else 'VERIFIED WITH REDACTIONS' if hidden else 'GENUINE',genuine=is_trusted and not is_demo and not hidden,viewable=True)
 except Exception as exc:
  if str(exc).startswith('blackout incomplete'):r['hiddenPixelsCleared']=False
  if r['verdict'] not in ('LIMIT EXCEEDED','NOT A GRD','REVOKED KEY','UNSUPPORTED'):
   if isinstance(exc,ResourceLimitError):r['verdict']='LIMIT EXCEEDED'
   elif not isinstance(exc,PROOF_ERRORS):
    r['verdict']='CANNOT VERIFY';r['verifierFault']=True
  r['problems'].append(str(exc) or type(exc).__name__)
 return r

def verify_v1(data,trusted=None,policy=None,keys_path=ROOT/'src/trusted-keys.json'):
 keys_path=Path(keys_path)
 r=dict(version=1,verdict='TAMPERED',genuine=False,problems=[])
 try:
  if len(data)>64*1024*1024:
   r['verdict']='LIMIT EXCEEDED'
   raise IntegrityError('Size limit')
  if len(data)<10 or data[:4]!=b'GRD1':
   r['verdict']='NOT A GRD'
   raise IntegrityError('Bad header')
  version,flags,n=struct.unpack_from('<HHH',data,4)
  if version!=1:
   r['verdict']='UNSUPPORTED'
   raise IntegrityError('Unsupported version')
  if not 4<=n<=7 or len(data)<10+50*n:raise IntegrityError('Bad table')
  expected=10+50*n;sections={};entries=[]
  for i in range(n):
   typ,offset,length,digest_bytes=struct.unpack_from('<HQQ32s',data,10+50*i)
   if typ not in range(1,8) or typ in sections or offset!=expected or offset+length>len(data):raise IntegrityError('Bad section structure')
   sections[typ]=data[offset:offset+length];entries.append((typ,offset,length,digest_bytes));expected+=length
  if expected!=len(data) or not {1,2,6,7}<=sections.keys() or entries[-1][0]!=7 or len(sections[7])!=64 or entries[-1][3]!=bytes(32):raise IntegrityError('Bad signature entry or length')
  if bool(flags&1)!=(5 in sections) or bool(flags&2)!=(4 in sections) or flags&~3:raise IntegrityError('Bad flags')
  for typ,off,length,dg in entries[:-1]:
   if hashlib.sha256(sections[typ]).digest()!=dg:raise IntegrityError('Section hash mismatch: '+str(typ))
  if len(sections[6])!=40:raise IntegrityError('Bad public key')
  kid=sections[6][:8].hex();pk=sections[6][8:]
  r['revocation']=policy_check(pk,policy,keys_path)
  if r['revocation']['revoked']:
   r['verdict']='REVOKED KEY'
   raise IntegrityError('Revoked signer')
  if sha(pk)[:16]!=kid:raise IntegrityError('Key ID mismatch')
  try:
   Ed25519PublicKey.from_public_bytes(pk).verify(sections[7],hashlib.sha256(data[:entries[-1][1]]).digest())
  except Exception as e:
   raise IntegrityError('Signature verification failed: '+str(e))
  if pk.hex() not in (get_pinned_signers(keys_path) if trusted is None else trusted):
   r['verdict']='UNTRUSTED SIGNER'
   raise IntegrityError('Unknown signer')
  name=None
  try:
   tk=load_trusted_keys(keys_path)
   for s in tk['signers']:
    if s.get('public_key_hex')==pk.hex():
     name=s.get('name');break
  except Exception:
   pass
  if name:r['signer']=name;r['signerName']=name
  else:r['signer']='Untrusted signer'
  if not sections[1] or len(sections[1])>256*1024:raise IntegrityError('Metadata size limit')
  raw=sections[1].decode();m=json.loads(raw)
  if not isinstance(m,dict) or not valid_tree(m) or canon(m)!=raw or m.get('asset_id')!=sha(sections[2])[:15] or m.get('key_id')!=kid:raise IntegrityError('Metadata mismatch')
  if m.get('mime') not in ('image/png','image/jpeg','image/webp') or any(type(m.get(k)) is not int or m[k]<1 or m[k]>16384 for k in ('width','height')) or m['width']*m['height']>40000000:raise IntegrityError('Unsupported image metadata')
  try:
   with Image.open(io.BytesIO(sections[2])) as image:
    if image.format not in ('PNG','JPEG','WEBP') or min(image.size)<1 or max(image.size)>16384 or image.width*image.height>40000000:raise IntegrityError('Unsupported or oversized image')
    if image.size!=(m.get('width'),m.get('height')):raise IntegrityError('Image dimension mismatch')
    image.load()
  except IntegrityError:
   raise
  except Exception as e:
   r['verdict']='UNREADABLE'
   raise IntegrityError(str(e))
  r.update(verdict='GENUINE',genuine=True)
 except Exception as exc:
  if str(exc).startswith('blackout incomplete'):r['hiddenPixelsCleared']=False
  if r['verdict'] not in ('LIMIT EXCEEDED','NOT A GRD','REVOKED KEY','UNSUPPORTED','UNTRUSTED SIGNER','UNREADABLE'):
   if isinstance(exc,ResourceLimitError):r['verdict']='LIMIT EXCEEDED'
   elif not isinstance(exc,PROOF_ERRORS):
    r['verdict']='CANNOT VERIFY';r['verifierFault']=True
  r['problems'].append(str(exc) or type(exc).__name__)
 return r

def verify(data,trusted=None,policy=None,keys_path=ROOT/'src/trusted-keys.json'):
 if data.startswith(b'GRD3\n'):return verify_v2(data,trusted,policy,keys_path)
 if len(data)>32*1024*1024 and not data.startswith(b'GRD1'):return dict(verdict='LIMIT EXCEEDED',genuine=False,problems=['Input exceeds GRD2 32 MiB limit'])
 return verify_v2(data,trusted,policy,keys_path) if data.startswith(b'GRD2\n') else verify_v1(data,trusted,policy,keys_path)

def redact(data,rects,mode='black',granularity=64):
 if mode!='black':raise ValueError('Only blackout exports are supported')
 r=verify_v2(data,include_pixels=True)
 if not r.get('regionVerified'):raise ValueError('Source proof does not verify: '+str(r['problems']))
 doc=r['_document'];m=doc['manifest']
 if 'subTile' in m:return grd_subtiles.redact(data,rects,granularity,sys.modules[__name__])
 if granularity!=64:raise ValueError('granularity finer than sealed sub-tile')
 rgb=bytearray(r['_rgb']);selected=set()
 for x,y,w,h in rects:
  if w<=0 or h<=0:raise ValueError('Invalid rectangle')
  for i in range(len(doc['tiles'])):
   b=bounds(m,i)
   if b['x']<x+w and b['x']+b['width']>x and b['y']<y+h and b['y']+b['height']>y:selected.add(i)
 if not selected:raise ValueError('No tiles selected')
 hidden=set(r['redactedTiles'])|selected
 for i in sorted(hidden):
  b=bounds(m,i);doc['tiles'][i]=dict(index=i,commitment=m['commitments'][i])
  for row in range(b['height']):
   start=((b['y']+row)*m['width']+b['x'])*3;rgb[start:start+b['width']*3]=bytes(b['width']*3)
 doc['image']=png_write(rgb,m['width'],m['height']) if m['version']==3 else b64(png_write(rgb,m['width'],m['height']));doc['redactions']=[dict(index=i,method='black') for i in sorted(hidden)];return encode(doc)

def export_plain(data,format='png',quality=95):
 r=verify_v2(data, trusted=[],include_pixels=True)
 if not r.get('regionVerified'):raise ValueError('Cannot export an invalid source proof: '+r['verdict'])
 doc=r['_document'];m=doc['manifest'];rgb=bytearray(r['_rgb'])
 regions=grd_subtiles.redaction_map(doc,sys.modules[__name__]) if 'subTile' in m else [bounds(m,entry['index']) for entry in doc['redactions']]
 for b in regions:
  for row in range(b['height']):
   start=((b['y']+row)*m['width']+b['x'])*3;rgb[start:start+b['width']*3]=bytes(b['width']*3)
 if format=='png':return png_write(rgb,m['width'],m['height'])
 if format!='jpeg' or not 1<=quality<=100:raise ValueError('Invalid export format or quality')
 out=io.BytesIO();Image.frombytes('RGB',(m['width'],m['height']),bytes(rgb)).save(out,format='JPEG',quality=quality);return out.getvalue()

def visual_features(rgb,width,height):return grd_visual.features(rgb,width,height,sys.modules[__name__])
def export_proof(data):return grd_visual.export_proof(data,sys.modules[__name__])
def verify_visual(proof,image_bytes,trusted=None,policy=None,keys_path=ROOT/'src/trusted-keys.json'):return grd_visual.verify_visual(proof,image_bytes,trusted,policy,Path(keys_path),sys.modules[__name__])

def main():
 parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
 s=sub.add_parser('seal');s.add_argument('input');s.add_argument('--key',required=True);s.add_argument('-o','--output',required=True);s.add_argument('--label',default='');s.add_argument('--sub-tile',type=int,choices=[8,16,32,64],default=64);s.add_argument('--format-version',type=int,choices=[2,3]);s.add_argument('--no-visual',action='store_true')
 v=sub.add_parser('verify');v.add_argument('input');v.add_argument('--trusted-key',action='append',default=[]);v.add_argument('--policy');v.add_argument('--trusted-keys')
 rd=sub.add_parser('redact');rd.add_argument('input');rd.add_argument('--rect',action='append',required=True);rd.add_argument('--mode',choices=['black'],default='black');rd.add_argument('--granularity',type=int,choices=[8,16,32,64],default=64);rd.add_argument('-o','--output',required=True)
 ex=sub.add_parser('export');ex.add_argument('input');ex.add_argument('--plain',action='store_true',required=True);ex.add_argument('--format',choices=['png','jpeg'],default='png');ex.add_argument('--quality',type=int,default=95);ex.add_argument('-o','--output',required=True)
 ep=sub.add_parser('export-proof');ep.add_argument('input');ep.add_argument('-o','--output',required=True)
 vv=sub.add_parser('verify-visual');vv.add_argument('input');vv.add_argument('image');vv.add_argument('--trusted-key',action='append',default=[]);vv.add_argument('--trusted-keys');vv.add_argument('--policy')
 args=parser.parse_args()
 try:
  if Path(args.input).stat().st_size>256*1024*1024:
   r=dict(verdict='LIMIT EXCEEDED',genuine=False,problems=['Input size limit'])
   r['exit_code']=EXIT.get(r['verdict'],4)
   print(json.dumps(r,indent=2));return r['exit_code']
  data=Path(args.input).read_bytes()
  if args.command=='seal':
   key=serialization.load_pem_private_key(Path(args.key).read_bytes(),password=None)
   if not isinstance(key,Ed25519PrivateKey):raise ValueError('Ed25519 key required')
   with Image.open(io.BytesIO(data)) as im:output=encode(seal(im,key,label=args.label,version=args.format_version,visual=not args.no_visual,sub_tile=args.sub_tile))
  elif args.command=='export-proof':output=export_proof(data)
  elif args.command=='export':
   output=export_plain(data,args.format,args.quality)
   print('Plain image is no longer verifiable; keep the .GRD if you need proof.',file=sys.stderr)
  elif args.command=='redact':output=redact(data,[tuple(map(int,r.split(','))) for r in args.rect],args.mode,args.granularity)
  else:
   keys_path=Path(args.trusted_keys) if args.trusted_keys else (ROOT/'src/trusted-keys.json')
   try:
    pinned=get_pinned_signers(keys_path)
   except Exception:
    r=dict(verdict='CANNOT VERIFY',genuine=False,verifierFault=True,problems=['Trusted-keys file is invalid.'])
    r['exit_code']=EXIT.get(r['verdict'],4)
    print(json.dumps(r,indent=2));return r['exit_code']
   trusted=pinned+[serialization.load_pem_public_key(Path(p).read_bytes()).public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex() for p in args.trusted_key]
   try:local_policy=json.loads(Path(args.policy).read_text()) if args.policy else None
   except (OSError,ValueError) as exc:
    r=dict(verdict='CANNOT VERIFY',genuine=False,verifierFault=True,problems=['Invalid local policy: '+str(exc)],exit_code=4)
    print(json.dumps(r,indent=2));return 4
   if args.command=='verify-visual':
    if Path(args.image).stat().st_size>256*1024*1024:raise ValueError('Candidate image exceeds 256 MiB')
    r=verify_visual(data,Path(args.image).read_bytes(),trusted,local_policy,keys_path=keys_path)
    if r.get('warning'):print('Warning: '+r['warning'],file=sys.stderr)
   else:r=verify(data,trusted,local_policy,keys_path=keys_path)
   r['exit_code']=EXIT.get(r['verdict'],4)
   print(json.dumps({k:v for k,v in r.items() if not k.startswith('_')},indent=2))
   return r['exit_code']
  with open(args.output,'xb') as handle:handle.write(output)
  print('Wrote '+args.output);return 0
 except Exception as exc:print('GRD error: '+str(exc),file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
