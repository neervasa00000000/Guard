#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate Python expectations for a real-browser corpus, or validate its downloaded report."""
import argparse,base64,hashlib,json,random,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import grd
ROOT=grd.ROOT

def generate(count):
 if not 1<=count<=10000:raise ValueError('Use 1..10000 mutations')
 keys=[];cases=[];seeds=[]
 for filename in ('grd2-vectors.json','grd3-vectors.json','upgrade-vectors.json'):
  doc=json.loads((ROOT/'tests/vectors'/filename).read_text());keys.append(doc['public_key_hex'])
  for v in doc['vectors']:
   cases.append(dict(id=filename+':'+v['id'],container=v['container']))
   if v['expected_verdict'] in ('GENUINE','VERIFIED WITH REDACTIONS'):seeds.append(grd.un64(v['container']))
 rng=random.Random(20261028)
 for i in range(count):
  b=bytearray(rng.choice(seeds));kind=i%4
  if kind==0:b[rng.randrange(len(b))]^=1<<rng.randrange(8)
  elif kind==1:b.insert(rng.randrange(len(b)+1),rng.randrange(256))
  elif kind==2:del b[rng.randrange(len(b))]
  else:b=b[:rng.randrange(len(b))]
  cases.append(dict(id='mutation-'+str(i),container=grd.b64(b)))
 for c in cases:
  r=grd.verify(grd.un64(c['container']),keys)
  c['expected']=dict(verdict=r['verdict'],genuine=bool(r.get('genuine')),regionVerified=bool(r.get('regionVerified')))
 payload=dict(format='GUARD-BROWSER-DIFF-1',seed=20261028,keys=keys,cases=cases)
 data=grd.canon(payload).encode();folder=ROOT/'results';folder.mkdir(exist_ok=True)
 (folder/'browser-corpus.json').write_bytes(data)
 print(json.dumps(dict(cases=len(cases),corpusSha256=hashlib.sha256(data).hexdigest(),output=str(folder/'browser-corpus.json'))))

def check(report_path):
 data=(ROOT/'results/browser-corpus.json').read_bytes();corpus=json.loads(data);report=json.loads(Path(report_path).read_text())
 assert report['corpusSha256']==hashlib.sha256(data).hexdigest(),'Corpus digest differs'
 assert isinstance(report.get('runtime'),str) and report['runtime'],'Missing browser runtime'
 assert len(report['results'])==len(corpus['cases']),'Missing or extra cases'
 mismatches=[]
 for c,r in zip(corpus['cases'],report['results']):
  if r.get('id')!=c['id'] or r.get('actual')!=c['expected']:mismatches.append(dict(id=c['id'],expected=c['expected'],actual=r))
 result=dict(scope='Native-browser vs Python on local exact-container vectors and seeded byte mutations; not the external structural harness or visual codec equivalence.',cases=len(corpus['cases']),disagreements=len(mismatches),runtime=report['runtime'],corpusSha256=report['corpusSha256'],elapsedMs=report['elapsedMs'],mismatches=mismatches)
 (ROOT/'results/browser-differential.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));assert not mismatches,'Browser/Python disagreement'
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--count',type=int,default=1000);p.add_argument('--check');a=p.parse_args()
 check(a.check) if a.check else generate(a.count)
