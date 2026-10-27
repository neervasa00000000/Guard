#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Local deterministic differential mutations; not the external guard-paper harness."""
import sys,os,json,random,base64,subprocess,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import grd
root=grd.ROOT;rng=random.Random(20261027);seeds=[];keys=[]
for filename in ('grd2-vectors.json','grd3-vectors.json','upgrade-vectors.json'):
 doc=json.loads((root/'tests/vectors'/filename).read_text());keys.append(doc['public_key_hex'])
 seeds.extend(grd.un64(v['container']) for v in doc['vectors'] if v['expected_verdict'] in ('GENUINE','VERIFIED WITH REDACTIONS'))
count=int(os.environ.get('FUZZ_N','10000'));batch_size=1000;disagreements=[];accepted=[];exceptions=[];start=time.perf_counter()
for offset in range(0,count,batch_size):
 batch=[]
 for i in range(min(batch_size,count-offset)):
  b=bytearray(rng.choice(seeds));operation=rng.randrange(4)
  if operation==0:b[rng.randrange(len(b))]^=1<<rng.randrange(8)
  elif operation==1:b.insert(rng.randrange(len(b)+1),rng.randrange(256))
  elif operation==2:del b[rng.randrange(len(b))]
  else:b=b[:rng.randrange(len(b))]
  batch.append(bytes(b))
 payload=dict(keys=keys,cases=[grd.b64(b) for b in batch])
 proc=subprocess.run(['node',str(root/'bench/differential-worker.mjs')],input=json.dumps(payload),capture_output=True,text=True,cwd=root,timeout=120)
 if proc.returncode:raise RuntimeError(proc.stderr)
 js=json.loads(proc.stdout)
 for i,(b,j) in enumerate(zip(batch,js)):
  try:p=grd.verify(b,keys)
  except Exception as exc:exceptions.append(dict(case=offset+i,python=repr(exc)));continue
  if 'exception' in j:exceptions.append(dict(case=offset+i,js=j['exception']));continue
  if j['verdict']!=p['verdict']:disagreements.append(dict(case=offset+i,js=j['verdict'],python=p['verdict'],container=grd.b64(b)))
  if j.get('genuine') or p.get('genuine') or j.get('regionVerified') or p.get('regionVerified'):accepted.append(dict(case=offset+i,js=j['verdict'],python=p['verdict'],container=grd.b64(b)))
 result=dict(scope='Local seeded byte flip/insert/delete/truncate mutations of small GRD2, GRD3, fine and visual-profile exact containers. Not the external 50,002-case structural harness, and not a proof of absence of defects.',seed=20261027,cases=offset+len(batch),disagreements=disagreements,accepted_mutants=accepted,exceptions=exceptions,elapsed_seconds=time.perf_counter()-start)
 path=root/'results/local-differential.json';path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v if not isinstance(v,list) else len(v) for k,v in result.items()},indent=2))
assert not disagreements and not accepted and not exceptions
