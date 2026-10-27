// SPDX-License-Identifier: MIT
// Sequential synthetic 4MP interoperability check; timing is diagnostic only.
import {generateKeyPairSync,sign} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {writeFile,mkdir} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {sealRgba,encodeGRD2,verifyGRD2,redactGRD2} from '../src/redactable.js';
const key=generateKeyPairSync('ed25519'),publicKey=key.publicKey.export({format:'der',type:'spki'}).subarray(-32),anchor={public_key_hex:publicKey.toString('hex')};
const width=2048,height=2048,rgba=new Uint8Array(width*height*4);let seed=42;
for(let i=0;i<rgba.length;i+=4){seed=(Math.imul(seed,1664525)+1013904223)>>>0;rgba[i]=seed&255;rgba[i+1]=seed>>>8&255;rgba[i+2]=seed>>>16&255;rgba[i+3]=255;}
const start=performance.now(),doc=await sealRgba({rgba,width,height,publicKey,sign:b=>sign(null,b,key.privateKey)}),bytes=encodeGRD2(doc),original=await verifyGRD2(bytes,[anchor]);
assert.equal(original.verdict,'GENUINE');
const redacted=await redactGRD2(doc,Array.from({length:103},(_,i)=>i));const redReport=await verifyGRD2(redacted,[anchor]);assert.equal(redReport.verdict,'VERIFIED WITH REDACTIONS');
const jsMs=performance.now()-start;
const python=spawnSync('python3',['-c',`import sys,json,base64,time,grd
p=json.load(sys.stdin);start=time.perf_counter();reports=[grd.verify(base64.b64decode(p[k]),[p['key']]) for k in ('sealed','redacted')]
print(json.dumps(dict(verdicts=[r['verdict'] for r in reports],elapsedMs=(time.perf_counter()-start)*1000)))`],{cwd:new URL('../',import.meta.url),input:JSON.stringify({sealed:Buffer.from(bytes).toString('base64'),redacted:Buffer.from(redacted).toString('base64'),key:anchor.public_key_hex}),encoding:'utf8',maxBuffer:1024*1024});
assert.equal(python.status,0,python.stderr);const py=JSON.parse(python.stdout);assert.deepEqual(py.verdicts,['GENUINE','VERIFIED WITH REDACTIONS']);
const result={image:'2048x2048 seeded noise',containerBytes:bytes.length,tiles:1024,hiddenTiles:103,jsVerdicts:[original.verdict,redReport.verdict],jsElapsedMs:jsMs,python:py,scope:'Single sequential interoperability run; not publication performance evidence'};
await mkdir(new URL('../results/',import.meta.url),{recursive:true});await writeFile(new URL('../results/large-roundtrip.json',import.meta.url),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));
