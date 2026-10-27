// SPDX-License-Identifier: MIT
// Sequential local scale measurements. Synthetic noise; no publication comparison implied.
import {generateKeyPairSync,sign} from 'node:crypto';
import {writeFile,mkdir} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {sealRgba,encodeGRD2,verifyGRD2} from '../src/redactable.js';
const keys=generateKeyPairSync('ed25519'),publicKey=keys.publicKey.export({type:'spki',format:'der'}).subarray(-32);
const sizes=[[2048,2048],[4000,2000],[4000,3000],[6000,4000],[7680,4320]];
await mkdir(new URL('../results/',import.meta.url),{recursive:true});
const rows=[];
for(const [width,height] of sizes){
 if(process.env.SCALE_FILTER&&!`${width}x${height}`.includes(process.env.SCALE_FILTER))continue;
 const rgba=new Uint8Array(width*height*4);let seed=42;
 for(let i=0;i<rgba.length;i+=4){seed=(Math.imul(seed,1664525)+1013904223)>>>0;rgba[i]=seed&255;rgba[i+1]=seed>>>8&255;rgba[i+2]=seed>>>16&255;rgba[i+3]=255;}
 for(const visual of [false,true]){
 const start=performance.now();const doc=await sealRgba({rgba,width,height,visual,publicKey,sign:b=>sign(null,b,keys.privateKey)});const sealedAt=performance.now();const bytes=encodeGRD2(doc),encodedAt=performance.now();
 const r=await verifyGRD2(bytes,[{public_key_hex:publicKey.toString('hex')}]);const end=performance.now();assert.equal(r.verdict,'GENUINE',JSON.stringify(r.problems));
 const path=new URL('../results/scale.GRD',import.meta.url);await writeFile(path,bytes);
 const python=spawnSync('python3',['-c',`import sys,time,json,resource;from pathlib import Path;import grd
start=time.perf_counter();data=Path(sys.argv[1]).read_bytes();r=grd.verify(data,[sys.argv[2]])
print(json.dumps(dict(verdict=r['verdict'],verify_ms=(time.perf_counter()-start)*1000,maxrss_raw=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,problems=r['problems'])))`,fileURLToPath(path),publicKey.toString('hex')],{cwd:new URL('../',import.meta.url),encoding:'utf8',timeout:180000,maxBuffer:1024*1024});
 assert.equal(python.status,0,python.stderr);const py=JSON.parse(python.stdout);assert.equal(py.verdict,'GENUINE',JSON.stringify(py));
 const row={visual_layer:visual?'on':'off',width,height,pixels:width*height,version:doc.manifest.version,container_bytes:bytes.length,seal_ms:sealedAt-start,encode_ms:encodedAt-sealedAt,verify_ms:end-encodedAt,peak_rss_bytes:process.resourceUsage().maxRSS*1024,python:py};rows.push(row);console.log(JSON.stringify(row));
 await writeFile(new URL('../results/v2-scale.json',import.meta.url),JSON.stringify({note:'One sequential synthetic run on an active laptop; both visual modes, fine sub-tiles disabled. Node peak RSS is process high-water, not per-image. Python maxrss_raw units are bytes on macOS, KiB on Linux.',rows},null,2)+'\n');
}
}
