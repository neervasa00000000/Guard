# SPDX-License-Identifier: MIT
"""Integer visual commitments and a deliberately non-exact copy checker."""
import hashlib,hmac,json,io
GUARANTEE='A VISUALLY CONSISTENT result means every disclosed 8x8 brightness block and 16x16 colour block is within 9 levels of the signed reference. Finer detail is NOT verified. Mean-preserving edits and some smooth blurs can pass.'

def features(rgb,width,height,c):
 if not isinstance(rgb,(bytes,bytearray,memoryview)) or not (1<=width<=64 and 1<=height<=64) or len(rgb)!=width*height*3:raise c.IntegrityError('Invalid visual tile dimensions')
 sums=[0]*96;counts=[0]*96
 for y in range(height):
  for x in range(width):
   at=(y*width+x)*3;r,g,b=rgb[at:at+3];l=(y//8)*8+x//8;ch=(y//16)*4+x//16
   sums[l]+=(299*r+587*g+114*b+500)//1000;counts[l]+=1
   sums[64+ch]+=max(0,min(255,(128000000-168736*r-331264*g+500000*b+500000)//1000000));counts[64+ch]+=1
   sums[80+ch]+=max(0,min(255,(128000000+500000*r-418688*g-81312*b+500000)//1000000));counts[80+ch]+=1
 return bytes((sums[i]+counts[i]//2)//counts[i] if counts[i] else 0 if i<64 else 128 for i in range(96))

def mapped_tile_features(rgb,cw,ch,m,index,c):
 if not isinstance(rgb,(bytes,bytearray,memoryview)) or type(cw) is not int or type(ch) is not int or not (1<=cw<=8192 and 1<=ch<=8192) or cw*ch>36_000_000 or len(rgb)!=cw*ch*3:raise c.IntegrityError('Invalid native visual pixels')
 if not isinstance(m,dict) or m.get('tileSize')!=64 or type(m.get('width')) is not int or type(m.get('height')) is not int or not (1<=m['width']<=8192 and 1<=m['height']<=8192) or m['width']*m['height']>36_000_000 or type(index) is not int or not 0<=index<((m['width']+63)//64)*((m['height']+63)//64):raise c.IntegrityError('Invalid signed visual grid')
 b=c.bounds(m,index);out=[0]*64+[128]*32;W,H=m['width'],m['height']
 for size in (8,16):
  for yy in range(0,64,size):
   for xx in range(0,64,size):
    if xx>=b['width'] or yy>=b['height']:continue
    left=(b['x']+xx)*cw;right=(b['x']+min(xx+size,b['width']))*cw;top=(b['y']+yy)*ch;bottom=(b['y']+min(yy+size,b['height']))*ch
    sy=scb=scr=0;area=(right-left)*(bottom-top)
    for y in range(top//H,(bottom+H-1)//H):
     wy=min(bottom,(y+1)*H)-max(top,y*H)
     for x in range(left//W,(right+W-1)//W):
      weight=wy*(min(right,(x+1)*W)-max(left,x*W));at=(y*cw+x)*3;r,g,v=rgb[at:at+3]
      if size==8:sy+=weight*((299*r+587*g+114*v+500)//1000)
      else:
       scb+=weight*max(0,min(255,(128000000-168736*r-331264*g+500000*v+500000)//1000000))
       scr+=weight*max(0,min(255,(128000000+500000*r-418688*g-81312*v+500000)//1000000))
    cell=(yy//size)*(64//size)+xx//size
    if size==8:out[cell]=(sy+area//2)//area
    else:out[64+cell]=(scb+area//2)//area;out[80+cell]=(scr+area//2)//area
 return bytes(out)

def visual_decision(error,tau=9):return 'BORDERLINE (decoder-dependent)' if tau-2<=error<=tau+2 else 'VISUALLY CONSISTENT' if error<tau-2 else 'VISUALLY INCONSISTENT'

def salt(value):return hmac.new(bytes.fromhex(value),b'GRD-VIS',hashlib.sha256).digest()[:16]
def commitment(i,t,f,c):return c.sha(b'GRD-VIS'+i.to_bytes(4,'big')+t+f)
def tile_features(rgb,m,i,c):
 b=c.bounds(m,i);return features(c.pixels(rgb,m,i),b['width'],b['height'],c)

def export_proof(data,c):
 r=c.verify_v2(data,trusted=[],include_pixels=True)
 if not r.get('regionVerified'):raise c.IntegrityError('Cannot export proof from invalid source')
 doc=r['_document'];m=doc['manifest']
 if any('sub' in t for t in doc['tiles']):raise ValueError('Visual proof export requires whole 64px redactions; partial tile means would leak hidden information')
 if 'visual' not in m:raise ValueError('No visual layer in this legacy file')
 rgb=r['_rgb'];vis=[]
 for i,t in enumerate(doc['tiles']):
  if 'commitment' in t:vis.append(dict(index=i,commitment=m['visual']['commitments'][i]))
  else:
   secret=salt(t.get('salt',t.get('seed')));feature=tile_features(rgb,m,i,c)
   if commitment(i,secret,feature,c)!=m['visual']['commitments'][i]:raise c.IntegrityError('Visual reference no longer opens')
   vis.append(dict(index=i,salt=c.b64(secret),feature=c.b64(feature)))
 return b'GRDP\n'+c.canon(dict(manifest=m,signature=doc['signature'],vis=vis)).encode()

def verify_visual(proof,image_bytes,trusted,policy,keys_path,c):
 r=dict(verdict='TAMPERED',genuine=False,viewable=False,problems=[],visualConsistent=False,guarantee=GUARANTEE)
 try:
  if len(proof)>16*1024*1024:raise c.IntegrityError('Visual proof exceeds 16 MiB')
  if not proof.startswith(b'GRDP\n'):raise c.IntegrityError('Missing GRDP header')
  try:raw=proof[5:].decode('utf-8');p=json.loads(raw)
  except (UnicodeError,json.JSONDecodeError,RecursionError) as e:raise c.IntegrityError('Invalid visual proof encoding') from e
  if not isinstance(p,dict) or set(p)!={'manifest','signature','vis'} or not c.valid_tree(p) or c.canon(p)!=raw:raise c.IntegrityError('Noncanonical visual proof')
  m=p['manifest'];count=c.validate_manifest(m)
  if 'visual' not in m:r['verdict']='UNSUPPORTED';r['problems'].append('No visual layer.');return c.signer_report(r,keys_path)
  pk=bytes.fromhex(m['publicKey']);r['fingerprint']=c.sha(pk)
  if c.sha(pk)!=m['keyId']:raise c.IntegrityError('Wrong signer fingerprint')
  r['revocation']=c.policy_check(pk,policy,keys_path)
  if r['revocation']['revoked']:r['verdict']='REVOKED KEY';r['problems'].append('Signing key is revoked.');return c.signer_report(r,keys_path)
  c.Ed25519PublicKey.from_public_bytes(pk).verify(c.un64(p['signature']),c.digest(m))
  r['signature_valid']=True
  if c.merkle(m['commitments'])!=m['root']:raise c.IntegrityError('Invalid exact commitment root')
  if not isinstance(p['vis'],list) or len(p['vis'])!=count:raise c.IntegrityError('Invalid visual disclosures')
  reference=[]
  for i,t in enumerate(p['vis']):
   if not isinstance(t,dict) or type(t.get('index')) is not int or t['index']!=i:raise c.IntegrityError('Unordered visual tile')
   if set(t)=={'index','commitment'}:
    if t['commitment']!=m['visual']['commitments'][i]:raise c.IntegrityError('Wrong hidden visual commitment')
    reference.append(None)
   else:
    if set(t)!={'index','salt','feature'}:raise c.IntegrityError('Invalid visual disclosure fields')
    secret=c.un64(t['salt']);f=c.un64(t['feature'])
    if len(secret)!=16 or len(f)!=96 or commitment(i,secret,f,c)!=m['visual']['commitments'][i]:raise c.IntegrityError('Visual feature proof mismatch (tile '+str(i)+')')
    reference.append(f)
  pinned=c.get_pinned_signers(keys_path) if trusted is None else trusted
  r['trusted']=m['publicKey'] in pinned and m['purpose']=='asset';r['trustVerdict']='DEMO' if m['purpose']=='demo' else 'UNVERIFIED: SELF-SIGNED' if m['purpose']=='personal' else 'TRUSTED' if m['publicKey'] in pinned else 'UNTRUSTED SIGNER'
  if len(image_bytes)>256*1024*1024:raise c.IntegrityError('Candidate exceeds image size limit')
  with c.Image.open(io.BytesIO(image_bytes)) as im:
   if im.format not in ('PNG','JPEG','WEBP') or max(im.size)>8192 or im.width*im.height>36_000_000:raise c.IntegrityError('Unsupported candidate image')
   if abs((im.width/im.height)/(m['width']/m['height'])-1)>.01:r['verdict']='VISUALLY INCONSISTENT';r['visualVerdict']=r['verdict'];r['problems'].append('Aspect ratio differs by more than 1%.');return c.signer_report(r,keys_path)
   rgba=im.convert('RGBA');flattened=c.Image.new('RGB',im.size,'white');flattened.paste(rgba,mask=rgba.getchannel('A'))
   cw,ch=im.size;rgb=flattened.tobytes()
  r.update(worstError=0,worstTile=None,worstCell=None)
  for i,expected in enumerate(reference):
   actual=mapped_tile_features(rgb,cw,ch,m,i,c);b=c.bounds(m,i)
   for cell in range(96 if expected is not None else 64):
    if expected is None and ((cell%8)*8>=b['width'] or (cell//8)*8>=b['height']):continue
    error=abs(actual[cell]-expected[cell]) if expected is not None else actual[cell]
    if error>r['worstError']:r.update(worstError=error,worstTile=i,worstCell=cell)
  r['visualVerdict']=visual_decision(r['worstError'],m['visual']['tau']);r['visualConsistent']=r['visualVerdict']=='VISUALLY CONSISTENT'
  if not any(f is not None for f in reference) and r['visualVerdict']!='VISUALLY INCONSISTENT':r.update(verdict='FULLY REDACTED',visualVerdict='FULLY REDACTED',visualConsistent=False);r['problems'].append('No visible original block means are disclosed.');return c.signer_report(r,keys_path)
  r['verdict']=r['visualVerdict'] if r['visualVerdict']=='BORDERLINE (decoder-dependent)' else 'VISUALLY INCONSISTENT' if not r['visualConsistent'] else 'VISUALLY CONSISTENT' if r['trusted'] else r['trustVerdict']
  if r['visualVerdict']=='BORDERLINE (decoder-dependent)':r['warning']='Close to the threshold; result may differ between apps';r['problems'].append(r['warning'])
  r.update(assetId=m['assetId'],width=m['width'],height=m['height'],tau=m['visual']['tau'])
  if not r['trusted']:r['problems'].append('Visual matching does not establish signer identity. '+r['trustVerdict']+'.')
 except Exception as exc:
  if not isinstance(exc,c.PROOF_ERRORS):r['verdict']='CANNOT VERIFY';r['verifierFault']=True
  r['problems'].append(str(exc) or type(exc).__name__)
 return c.signer_report(r,keys_path)
