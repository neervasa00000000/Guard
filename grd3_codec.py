# SPDX-License-Identifier: MIT
"""GRD3 binary framing and band verifier, independent of the browser implementation."""
import hashlib,json,struct,zlib
LIMITS=dict(bytes=256*1024*1024,dimension=8192,pixels=36_000_000,tiles=9000)

def encode3(doc,c):
 m=doc['manifest'];c.validate_manifest(m)
 if m['version']!=3:raise c.IntegrityError('GRD3 requires version 3')
 manifest=c.canon(m).encode();signature=c.un64(doc['signature']);png=doc['image'] if isinstance(doc['image'],(bytes,bytearray,memoryview)) else c.un64(doc['image'])
 if len(signature)!=64 or len(doc['tiles'])!=len(m['commitments']):raise c.IntegrityError('Invalid GRD3 signature or count')
 records=[];methods={e['index']:e['method'] for e in doc['redactions']}
 for i,t in enumerate(doc['tiles']):
  if 'subTile' in m:c.grd_subtiles.validate(m,t,i,c)
  elif t.get('index')!=i or set(t) not in ({'index','salt'},{'index','commitment'}):raise c.IntegrityError('Invalid GRD3 tile record')
  if 'sub' in t:
   records.append(bytes([3])+struct.pack('>H',len(t['sub']))+b''.join(bytes([0 if 'salt' in s else 1])+bytes.fromhex(s.get('salt',s.get('commitment'))) for s in t['sub']));continue
  retained='salt' in t or 'seed' in t;value=t.get('salt',t.get('seed')) if retained else t['commitment']
  if not isinstance(value,str) or not c.re.fullmatch('[0-9a-f]{'+str(32 if retained else 64)+'}',value):raise c.IntegrityError('Invalid GRD3 record bytes')
  if not retained and methods.get(i) not in ('black','blur'):raise c.IntegrityError('Missing redaction method')
  records.append(bytes([0 if retained else 1 if methods[i]=='black' else 2])+bytes.fromhex(value))
 out=b''.join([b'GRD3\n',struct.pack('>I',len(manifest)),manifest,signature,struct.pack('>I',len(records)),b''.join(records),struct.pack('>Q',len(png)),png])
 if len(out)>LIMITS['bytes']:raise c.ResourceLimitError('GRD3 exceeds 256 MiB')
 return out

def decode3(data,c):
 if len(data)>LIMITS['bytes']:raise c.ResourceLimitError('GRD3 exceeds 256 MiB')
 if data[:5]!=b'GRD3\n':raise c.IntegrityError('Missing GRD3 header')
 at=5
 def take(n):
  nonlocal at
  if n<0 or at+n>len(data):raise c.IntegrityError('Truncated GRD3 section')
  result=memoryview(data)[at:at+n];at+=n;return result
 length=struct.unpack('>I',take(4))[0]
 if length>2*1024*1024:raise c.IntegrityError('Manifest length exceeds bound')
 try:
  raw=bytes(take(length)).decode('utf-8');m=json.loads(raw)
 except (UnicodeError,json.JSONDecodeError,RecursionError) as e:raise c.IntegrityError('Invalid GRD3 manifest') from e
 count=c.validate_manifest(m)
 if m['version']!=3 or not c.valid_tree(m) or c.canon(m)!=raw:raise c.IntegrityError('Noncanonical GRD3 manifest')
 signature=c.b64(take(64));n=struct.unpack('>I',take(4))[0]
 if n!=count:raise c.IntegrityError('GRD3 tile count mismatch')
 tiles=[];redactions=[]
 for i in range(n):
  kind=take(1)[0]
  if kind==3 and 'subTile' in m:
   nsub=struct.unpack('>H',take(2))[0]
   if nsub!=c.grd_subtiles.count(m,i,c):raise c.IntegrityError('Wrong sub-record count')
   sub=[]
   for j in range(nsub):
    k=take(1)[0]
    if k not in (0,1):raise c.IntegrityError('Invalid sub-record kind')
    value=take(16 if k==0 else 32).hex();sub.append(dict(j=j,**({'salt':value} if k==0 else {'commitment':value})))
   t=dict(index=i,sub=sub);c.grd_subtiles.validate(m,t,i,c);tiles.append(t);redactions.append(dict(index=i,method='black'));continue
  if kind not in (0,1,2) or ('subTile' in m and kind==2):raise c.IntegrityError('Unknown GRD3 tile kind')
  value=take(16 if kind==0 else 32).hex();t=dict(index=i,**({'seed':value} if 'subTile' in m else {'salt':value}) if kind==0 else {'commitment':value})
  if 'subTile' in m:c.grd_subtiles.validate(m,t,i,c)
  tiles.append(t)
  if kind:redactions.append(dict(index=i,method='black' if kind==1 else 'blur'))
 length=struct.unpack('>Q',take(8))[0]
 if length>LIMITS['bytes'] or length!=len(data)-at:raise c.IntegrityError('Invalid GRD3 PNG length or trailing data')
 return dict(manifest=m,signature=signature,tiles=tiles,redactions=redactions,image=take(length))

def png_parts(data,c):
 if len(data)<45 or bytes(data[:8])!=b'\x89PNG\r\n\x1a\n':raise c.IntegrityError('Invalid PNG')
 at=8;size=None;idats=[];ended=False
 while at+12<=len(data):
  n=struct.unpack_from('>I',data,at)[0];end=at+n+12
  if end>len(data):raise c.IntegrityError('Truncated PNG')
  kind=bytes(data[at+4:at+8]);body=data[at+8:end-4]
  if zlib.crc32(data[at+4:end-4])&0xffffffff!=struct.unpack_from('>I',data,end-4)[0]:raise c.IntegrityError('PNG checksum failed')
  if kind==b'IHDR':
   if at!=8 or n!=13:raise c.IntegrityError('Invalid PNG header')
   w,h,depth,colour,comp,filt,interlace=struct.unpack('>IIBBBBB',body)
   if min(w,h)<1 or max(w,h)>8192 or w*h>36_000_000 or (depth,colour,comp,filt,interlace)!=(8,2,0,0,0):raise c.IntegrityError('Unsupported PNG dimensions or format')
   size=(w,h)
  elif kind==b'IDAT':
   if size is None:raise c.IntegrityError('PNG data before header')
   idats.append(body)
  elif kind==b'IEND':
   if n or not idats or end!=len(data):raise c.IntegrityError('Invalid PNG end')
   ended=True;break
  else:raise c.IntegrityError('Unexpected PNG chunk')
  at=end
 if not ended:raise c.IntegrityError('Incomplete PNG')
 return (*size,idats)

def png_bands(data,c):
 w,h,idats=png_parts(data,c);stride=w*3;inflater=zlib.decompressobj();pending=bytearray();previous=bytearray(stride);row=0;band=bytearray()
 def paeth(a,b,d):
  p=a+b-d;x=abs(p-a);y=abs(p-b);z=abs(p-d)
  return a if x<=y and x<=z else b if y<=z else d
 for chunk in idats:
  for offset in range(0,len(chunk),16384):
   packed=chunk[offset:offset+16384]
   while len(packed):
    raw=inflater.decompress(packed,64*(stride+1));packed=inflater.unconsumed_tail;pending.extend(raw)
    if inflater.unused_data:raise c.IntegrityError('Trailing deflate bytes')
    consumed=0
    while len(pending)-consumed>=stride+1:
     if row>=h:raise c.IntegrityError('Extra PNG pixels')
     filt=pending[consumed];current=bytearray(pending[consumed+1:consumed+stride+1]);consumed+=stride+1
     if filt>4:raise c.IntegrityError('Unknown PNG filter')
     if filt:
      # Decode just two rows with Pillow's native PNG unfilterer: a filter-zero
      # previous row supplies the context for this row. This bounds memory by
      # O(width), handles all five filters, and avoids a full-image allocation.
      def native_chunk(kind,body):return struct.pack('>I',len(body))+kind+body+struct.pack('>I',zlib.crc32(kind+body)&0xffffffff)
      hdr=struct.pack('>IIBBBBB',w,2,8,2,0,0,0)
      packed_rows=zlib.compress(b'\0'+previous+bytes([filt])+current,0)
      tiny=b'\x89PNG\r\n\x1a\n'+native_chunk(b'IHDR',hdr)+native_chunk(b'IDAT',packed_rows)+native_chunk(b'IEND',b'')
      with c.Image.open(c.io.BytesIO(tiny)) as decoded:current=bytearray(decoded.tobytes()[stride:])

     previous=current;band.extend(current);row+=1
     if row%64==0 or row==h:
      yield row-(64 if row%64==0 else row%64),w,h,band
      band.clear()
    del pending[:consumed]
 if not inflater.eof or pending or row!=h:raise c.IntegrityError('Invalid PNG pixel stream')

def verify3(data,trusted,policy,keys_path,c,include_pixels=False):
 r=dict(version=3,verdict='TAMPERED',genuine=False,viewable=False,problems=[],hiddenPixelsCleared=True,signature_valid=False,maxDecodedRows=64)
 try:
  doc=decode3(data,c);m=doc['manifest'];pk=bytes.fromhex(m['publicKey'])
  r['fingerprint']=c.sha(pk);r['_purpose']=m['purpose']
  if c.sha(pk)!=m['keyId']:raise c.IntegrityError('Wrong signer fingerprint')
  r['revocation']=c.policy_check(pk,policy,keys_path)
  if r['revocation']['revoked']:
   r['verdict']='REVOKED KEY';raise c.IntegrityError('Revoked signer')
  c.Ed25519PublicKey.from_public_bytes(pk).verify(c.un64(doc['signature']),c.digest(m));r['signature_valid']=True
  if c.merkle(m['commitments'])!=m['root']:raise c.IntegrityError('Signed root mismatch')
  w,h,_=png_parts(doc['image'],c)
  if (w,h)!=(m['width'],m['height']):raise c.IntegrityError('Wrong PNG dimensions')
  methods={e['index']:e['method'] for e in doc['redactions']};all_rgb=bytearray() if include_pixels else None
  for y,w,h,band in png_bands(doc['image'],c):
   if all_rgb is not None:all_rgb.extend(band)
   first=(y//64)*((w+63)//64)
   for i in range(first,first+(w+63)//64):
    t=doc['tiles'][i];b=c.bounds(m,i);tile=b''.join(band[(row*w+b['x'])*3:(row*w+b['x']+b['width'])*3] for row in range(b['height']))
    if 'subTile' in m:
     c.grd_subtiles.verify(m,t,i,tile,c);continue
    if 'commitment' in t:
     if t['commitment']!=m['commitments'][i]:raise c.IntegrityError('Wrong commitment at tile '+str(i))
     if methods[i]=='black' and any(tile):r['hiddenPixelsCleared']=False;raise c.IntegrityError('blackout incomplete (tile '+str(i)+')')
     if methods[i]=='blur':r['hiddenPixelsCleared']=False;r['problems'].append('Legacy blur redaction (tile '+str(i)+'): pixels not verified.')
    elif c.commit(m,i,t['salt'],tile)!=m['commitments'][i]:raise c.IntegrityError('Non-redacted tile '+str(i)+' changed')
  hidden=[e['index'] for e in doc['redactions']];count=len(doc['tiles']);pinned=c.get_pinned_signers(keys_path) if trusted is None else trusted
  demo=m['purpose']=='demo';personal=m['purpose']=='personal';is_trusted=m['publicKey'] in pinned and not demo and not personal
  r.update(assetId=m['assetId'],created=m['created'],root=m['root'],tilesTotal=count,tilesVisible=count-len(hidden),redactedTiles=hidden,redactionMap=[dict(index=i,**c.bounds(m,i),claimedMethod=methods[i],methodAttested=False) for i in hidden],regionVerified=True,redactionApproval='not_attested',_document=doc)
  if 'subTile' in m:
   r['redactionMap']=c.grd_subtiles.redaction_map(doc,c);r['subTile']=m['subTile'];r['subTilesTotal']=sum(c.grd_subtiles.count(m,i,c) for i in range(count));r['subTilesVisible']=sum(c.grd_subtiles.count(m,t['index'],c) if 'seed' in t else sum('salt' in s for s in t.get('sub',[])) for t in doc['tiles'])
  if all_rgb is not None:r['_rgb']=all_rgb
  if not is_trusted and not demo and not personal:r['verdict']='UNTRUSTED SIGNER'
  elif not any('salt' in t or 'seed' in t or any('salt' in s for s in t.get('sub',[])) for t in doc['tiles']):r['verdict']='FULLY REDACTED'
  else:r.update(verdict='DEMO' if demo else 'UNVERIFIED: SELF-SIGNED' if personal else 'VERIFIED WITH REDACTIONS' if hidden else 'GENUINE',genuine=is_trusted and not hidden,viewable=True)
 except Exception as exc:
  if str(exc).startswith('blackout incomplete'):r['hiddenPixelsCleared']=False
  if isinstance(exc,c.ResourceLimitError):r['verdict']='LIMIT EXCEEDED'
  elif r['verdict']!='REVOKED KEY' and not isinstance(exc,c.PROOF_ERRORS):r['verdict']='CANNOT VERIFY';r['verifierFault']=True
  r['problems'].append(str(exc) or type(exc).__name__)
 return c.signer_report(r,keys_path)

def png_write_stream(rgb,w,h):
 """Encode RGB scanlines in 64-row bands without a second full RGB image."""
 if min(w,h)<1 or max(w,h)>8192 or w*h>36_000_000 or len(rgb)!=w*h*3:raise ValueError("Invalid RGB image dimensions or length")
 def piece(kind,body):return struct.pack('>I',len(body))+kind+body+struct.pack('>I',zlib.crc32(kind+body)&0xffffffff)
 hdr=struct.pack('>IIBBBBB',w,h,8,2,0,0,0);parts=[b'\x89PNG\r\n\x1a\n',piece(b'IHDR',hdr)];compressor=zlib.compressobj();stride=w*3
 for y in range(0,h,64):
  rows=min(64,h-y);band=bytearray(rows*(stride+1))
  for row in range(rows):band[row*(stride+1)+1:(row+1)*(stride+1)]=rgb[(y+row)*stride:(y+row+1)*stride]
  packed=compressor.compress(band)
  if packed:parts.append(piece(b'IDAT',packed))
 packed=compressor.flush()
 if packed:parts.append(piece(b'IDAT',packed))
 parts.append(piece(b'IEND',b''));return b''.join(parts)
