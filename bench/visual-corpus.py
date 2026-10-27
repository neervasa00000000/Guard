#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproducible 24 Kodak x 7 visual transformations. External harness equivalence is not asserted."""
import argparse,hashlib,json,sys,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import grd
from PIL import ImageFilter
root=grd.ROOT;data=root/'data/kodak';out=root/'results/visual-corpus'

def fetch():
 data.mkdir(parents=True,exist_ok=True)
 for i in range(1,25):
  name=f'kodim{i:02d}.png';path=data/name
  if path.exists():continue
  url='https://r0k.us/graphics/kodak/kodak/'+name
  download=subprocess.run(['curl','--fail','--location','--silent','--show-error','--max-time','60',url],capture_output=True,check=True);raw=download.stdout
  if len(raw)>4*1024*1024:raise ValueError('Unexpected Kodak file size')
  with grd.Image.open(grd.io.BytesIO(raw)) as im:
   if im.size not in ((768,512),(512,768)):raise ValueError('Unexpected Kodak size')
   im.verify()
  path.write_bytes(raw);print('Fetched '+name,flush=True)

def generate():
 out.mkdir(parents=True,exist_ok=True);cases=[];inputs=[]
 key=grd.Ed25519PrivateKey.from_private_bytes(bytes([45])*32);pk=key.public_key().public_bytes(grd.serialization.Encoding.Raw,grd.serialization.PublicFormat.Raw).hex()
 for i in range(1,25):
  path=data/f'kodim{i:02d}.png';raw=path.read_bytes();inputs.append(dict(file=path.name,sha256=hashlib.sha256(raw).hexdigest()))
  with grd.Image.open(path) as original:im=original.convert('RGB')
  # Deterministic public TEST ONLY key; do not infer real Kodak capture identity.
  from unittest.mock import patch
  counter=iter(range(10000))
  with patch('grd.os.urandom',side_effect=lambda n:hashlib.shake_256(f'TEST-ONLY-{i}-{next(counter)}-{n}'.encode()).digest(n)),patch('grd.datetime') as clock:
   clock.now.return_value.isoformat.return_value='2026-10-28T00:00:00+00:00';clock.now.return_value.strftime.return_value='2026-10-28T00:00:00Z';doc=grd.seal(im,key,version=3)
  proof=grd.export_proof(grd.encode3(doc));proof_path=out/f'{i:02d}.grdp';proof_path.write_bytes(proof)
  w,h=im.size;splice=im.copy()
  with grd.Image.open(data/f'kodim{(i%24)+1:02d}.png') as donor_source:donor=donor_source.convert('RGB')
  splice.paste(donor.crop((0,0,128,128)),(w//2-64,h//2-64))
  transforms=[('jpeg30',im,'JPEG',dict(quality=30)),('jpeg90',im,'JPEG',dict(quality=90)),('webp',im,'WEBP',dict(quality=80)),('half',im.resize((w//2,h//2),grd.Image.Resampling.BICUBIC),'PNG',{}),('onehalf-jpeg',im.resize((w*3//2,h*3//2),grd.Image.Resampling.BICUBIC),'JPEG',dict(quality=75)),('splice',splice,'PNG',{}),('blur',im.filter(ImageFilter.GaussianBlur(2)),'PNG',{})]
  for name,image,fmt,kwargs in transforms:
   image_path=out/f'{i:02d}-{name}.{fmt.lower()}'
   image.save(image_path,format=fmt,**kwargs);image_bytes=image_path.read_bytes();r=grd.verify_visual(proof,image_bytes,[pk]);assert r['verdict'] not in ('CANNOT VERIFY','TAMPERED'),r
   cases.append(dict(id=f'{i:02d}-{name}',proof=proof_path.name,image=image_path.name,imageSha256=hashlib.sha256(image_bytes).hexdigest(),expected=dict(visualVerdict=r['visualVerdict'],genuine=r['genuine'],visualConsistent=r['visualConsistent']),pythonWorstError=r.get('worstError')))
  print(f'Prepared {i}/24 images ({len(cases)} cases)',flush=True)
 manifest=dict(source='https://r0k.us/graphics/kodak/',format='GUARD-VISUAL-CORPUS-1',notice='TEST ONLY public deterministic key. Same Kodak images and transform categories as the request; independent, explicitly specified transform settings, not the missing external harness.',key=pk,inputs=inputs,recipes='Pillow: JPEG q30/q90 defaults; WebP q80; 0.5x BICUBIC PNG; 1.5x BICUBIC JPEG q75; central128px splice from next image top-left; GaussianBlur radius2 PNG.',cases=cases)
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('Wrote 168-case manifest')

def check(report):
 manifest=json.loads((out/'manifest.json').read_text());rows=json.loads(Path(report).read_text());rows=rows['rows'] if isinstance(rows,dict) else rows
 assert len(rows)==168 and len(manifest['cases'])==168
 disagreements=[]
 for case,r in zip(manifest['cases'],rows):
  assert case['id']==r['id'];assert hashlib.sha256((out/case['image']).read_bytes()).hexdigest()==case['imageSha256']
  if r.get('actual')!=case['expected']:disagreements.append(dict(id=case['id'],python=case['expected'],other=r))
 print(json.dumps(dict(cases=len(rows),disagreements=disagreements),indent=2));assert not disagreements,'Visual verdict disagreement'
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--fetch',action='store_true');p.add_argument('--check');a=p.parse_args()
 if a.fetch:fetch()
 elif a.check:check(a.check)
 else:generate()
