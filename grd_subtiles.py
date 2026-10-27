# SPDX-License-Identifier: MIT
"""Independent two-level tile commitments with PRF-derived disclosure salts."""
import hmac,hashlib

def count(m,i,c):
 b=c.bounds(m,i);g=m['subTile'];return ((b['width']+g-1)//g)*((b['height']+g-1)//g)
def bounds(m,i,j,c):
 b=c.bounds(m,i);g=m['subTile'];cols=(b['width']+g-1)//g;x=(j%cols)*g;y=(j//cols)*g
 return dict(x=b['x']+x,y=b['y']+y,width=min(g,b['width']-x),height=min(g,b['height']-y))
def salts(seed,n):return [hmac.new(bytes.fromhex(seed),b'GRD-SUB'+j.to_bytes(2,'big'),hashlib.sha256).digest()[:16].hex() for j in range(n)]
def commitment(i,j,salt,rgb,c):return c.sha(b'GRD-SUBTILE'+i.to_bytes(4,'big')+j.to_bytes(2,'big')+bytes.fromhex(salt)+rgb)
def parent(i,cs,c):return c.sha(b'GRD-TILE2'+i.to_bytes(4,'big')+b''.join(bytes.fromhex(x) for x in cs))
def sub_pixels(tile,m,i,j,c):
 b=c.bounds(m,i);s=bounds(m,i,j,c);x=s['x']-b['x'];y=s['y']-b['y']
 return b''.join(tile[((y+r)*b['width']+x)*3:((y+r)*b['width']+x+s['width'])*3] for r in range(s['height']))
def seal(m,i,seed,tile,c):
 ss=salts(seed,count(m,i,c));cs=[commitment(i,j,s,sub_pixels(tile,m,i,j,c),c) for j,s in enumerate(ss)]
 return parent(i,cs,c),ss,cs

def validate(m,t,i,c):
 if not isinstance(t,dict) or type(t.get('index')) is not int or t['index']!=i:raise c.IntegrityError('Invalid tile index')
 if set(t)=={'index','seed'}:
  if not isinstance(t['seed'],str) or not c.re.fullmatch('[0-9a-f]{32}',t['seed']):raise c.IntegrityError('Invalid tile seed')
 elif set(t)=={'index','commitment'}:
  if not c.hx(t['commitment']):raise c.IntegrityError('Invalid hidden tile commitment')
 elif set(t)=={'index','sub'}:
  if not isinstance(t['sub'],list) or len(t['sub'])!=count(m,i,c):raise c.IntegrityError('Wrong sub-record count')
  hidden=0
  for j,s in enumerate(t['sub']):
   if not isinstance(s,dict) or type(s.get('j')) is not int or s['j']!=j:raise c.IntegrityError('Unordered sub-record')
   if set(s)=={'j','salt'}:
    if not isinstance(s['salt'],str) or not c.re.fullmatch('[0-9a-f]{32}',s['salt']):raise c.IntegrityError('Invalid sub-tile salt')
   elif set(s)=={'j','commitment'}:
    if not c.hx(s['commitment']):raise c.IntegrityError('Invalid sub-tile commitment')
    hidden+=1
   else:raise c.IntegrityError('Invalid sub-record fields')
  if hidden in (0,len(t['sub'])):raise c.IntegrityError('Partial tile must have retained and hidden sub-tiles')
 else:raise c.IntegrityError('Seed must be absent on a partially hidden tile')

def verify(m,t,i,tile,c):
 validate(m,t,i,c)
 if 'commitment' in t:
  if t['commitment']!=m['commitments'][i] or any(tile):raise c.IntegrityError('blackout incomplete or wrong commitment (tile '+str(i)+')')
 elif 'seed' in t:
  if seal(m,i,t['seed'],tile,c)[0]!=m['commitments'][i]:raise c.IntegrityError('Non-redacted tile '+str(i)+' changed')
 else:
  cs=[]
  for s in t['sub']:
   p=sub_pixels(tile,m,i,s['j'],c)
   if 'commitment' in s:
    if any(p):raise c.IntegrityError('blackout incomplete (tile '+str(i)+' sub '+str(s['j'])+')')
    cs.append(s['commitment'])
   else:cs.append(commitment(i,s['j'],s['salt'],p,c))
  if parent(i,cs,c)!=m['commitments'][i]:raise c.IntegrityError('Retained disclosure changed (tile '+str(i)+' sub proof)')

def redaction_map(doc,c):
 m=doc['manifest'];out=[]
 for t in doc['tiles']:
  if 'commitment' in t:out.append(dict(index=t['index'],**c.bounds(m,t['index']),claimedMethod='black',methodAttested=False))
  elif 'sub' in t:
   for s in t['sub']:
    if 'commitment' in s:out.append(dict(index=t['index'],subIndex=s['j'],**bounds(m,t['index'],s['j'],c),claimedMethod='black',methodAttested=False))
 return out

def redact(data,rects,granularity,c):
 r=c.verify_v2(data,include_pixels=True)
 if not r.get('regionVerified'):raise ValueError('Source proof does not verify')
 doc=r['_document'];m=doc['manifest'];g=m['subTile']
 if granularity not in (8,16,32,64) or granularity<g:raise ValueError('granularity finer than sealed sub-tile')
 rounded=[]
 for x,y,w,h in rects:
  if not all(isinstance(v,(int,float)) and c.math.isfinite(v) for v in (x,y,w,h)) or w<=0 or h<=0:raise ValueError('Invalid rectangle')
  rounded.append((c.math.floor(x/granularity)*granularity,c.math.floor(y/granularity)*granularity,c.math.ceil((x+w)/granularity)*granularity,c.math.ceil((y+h)/granularity)*granularity))
 rgb=bytearray(r['_rgb']);tiles=[];selected=False
 for i,t in enumerate(doc['tiles']):
  if 'commitment' in t:
   b=c.bounds(m,i)
   if any(b['x']<right and b['x']+b['width']>x and b['y']<bottom and b['y']+b['height']>y for x,y,right,bottom in rounded):selected=True
   tiles.append(dict(t));continue
  tile=c.pixels(rgb,m,i);material=seal(m,i,t['seed'],tile,c) if 'seed' in t else None
  sub=[dict(j=j,salt=s) for j,s in enumerate(material[1])] if material else [dict(s) for s in t['sub']]
  for j,s in enumerate(sub):
   b=bounds(m,i,j,c);hit=any(b['x']<right and b['x']+b['width']>x and b['y']<bottom and b['y']+b['height']>y for x,y,right,bottom in rounded)
   if hit:
    selected=True
    if 'commitment' not in s:sub[j]=dict(j=j,commitment=material[2][j] if material else commitment(i,j,s['salt'],sub_pixels(tile,m,i,j,c),c))
   if 'commitment' in sub[j]:
    for row in range(b['height']):
     at=((b['y']+row)*m['width']+b['x'])*3;rgb[at:at+b['width']*3]=bytes(b['width']*3)
  hidden=sum('commitment' in s for s in sub)
  tiles.append(dict(index=i,commitment=m['commitments'][i]) if hidden==len(sub) else dict(index=i,sub=sub) if hidden else t)
 if not selected:raise ValueError('No image sub-tiles intersect the rectangles')
 doc['tiles']=tiles;doc['redactions']=[dict(index=t['index'],method='black') for t in tiles if 'commitment' in t or 'sub' in t]
 png=c.png_write(rgb,m['width'],m['height']);doc['image']=png if m['version']==3 else c.b64(png);return c.encode(doc)
