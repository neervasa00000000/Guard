// SPDX-License-Identifier: MIT
import test from 'node:test';
import assert from 'node:assert/strict';
import {sign} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {signer} from './fixtures.mjs';
import {sealRgba,encodeGRD2,decodeGRD3,isGRD3,verifyGRD2,redactRects,redactGRD2,exportPlainImage,exportProof,base64,GRD3_LIMITS} from '../src/redactable.js';
import {decodeRgbPng,encodeRgbPng} from '../src/png.js';
const key=signer(),width=131,height=79,rgba=new Uint8Array(width*height*4);
for(let i=0;i<rgba.length;i+=4)rgba.set([(i*3)%251,90,(i>>>3)%247,255],i);
const parse=b=>isGRD3(b)?decodeGRD3(b):JSON.parse(new TextDecoder().decode(b.subarray(5)));
const image=doc=>doc.image instanceof Uint8Array?doc.image:Buffer.from(doc.image,'base64');
const runPython=(data,redact=false)=>{
 const out=spawnSync('python3',['-c',`import json,sys,base64,grd
p=json.load(sys.stdin);data=base64.b64decode(p['container'])
if p['redact']:data=grd.redact(data,[(1,1,10,10)],granularity=16)
r=grd.verify(data,[p['key']]);print(json.dumps(dict(verdict=r['verdict'],map=r.get('redactionMap'),container=grd.b64(data))))`],{input:JSON.stringify({key:key.raw.toString('hex'),container:base64(data),redact}),encoding:'utf8'});
 assert.equal(out.status,0,out.stderr);return JSON.parse(out.stdout);
};
for(const version of [2,3])for(const subTile of [8,16,32])test(`GRD${version} ${subTile}px sub-tiles round-trip, redact precisely and interoperate`,async()=>{
 const doc=await sealRgba({rgba,width,height,version,subTile,publicKey:key.raw,sign:b=>sign(null,b,key.privateKey)}),original=encodeGRD2(doc);
 assert.equal((await verifyGRD2(original,[key.anchor])).verdict,'GENUINE');assert.equal(runPython(original).verdict,'GENUINE');
 const redacted=await redactRects(doc,[{x:1,y:1,width:10,height:10}],{granularity:subTile}),red=parse(redacted),r=await verifyGRD2(redacted,[key.anchor]);
 assert.equal(r.verdict,'VERIFIED WITH REDACTIONS',JSON.stringify(r.problems));assert.deepEqual(Object.keys(red.tiles[0]).sort(),['index','sub']);
 assert.ok(!JSON.stringify(red.tiles).includes(doc.tiles[0].seed));assert.equal(red.manifest.root,doc.manifest.root);assert.equal(red.signature,doc.signature);
 assert.equal(r.redactionMap.reduce((sum,b)=>sum+b.width*b.height,0),Math.ceil(11/subTile)**2*subTile**2);
 const py=runPython(redacted);assert.equal(py.verdict,r.verdict);assert.deepEqual(py.map,r.redactionMap);
 const plain=await decodeRgbPng(await exportPlainImage(redacted),GRD3_LIMITS);assert.equal(plain.rgb[0],0);assert.equal(plain.rgb[(50*width+50)*3],rgba[(50*width+50)*4]);
 await assert.rejects(exportProof(redacted),/partial|whole 64px/i);
 const again=await redactRects(red,[{x:1,y:1,width:10,height:10}],{granularity:subTile});assert.equal((await verifyGRD2(again,[key.anchor])).verdict,'VERIFIED WITH REDACTIONS');
 if(subTile<=16){const fromPython=runPython(original,true);assert.equal((await verifyGRD2(Buffer.from(fromPython.container,'base64'),[key.anchor])).verdict,'VERIFIED WITH REDACTIONS');}
 await assert.rejects(redactRects(doc,[{x:0,y:0,width:1,height:1}],{granularity:subTile/2}),/finer/);
});
test('partial tile cannot retain its seed, omit sub-records, alter retained pixels or leave hidden pixels',async()=>{
 const doc=await sealRgba({rgba,width,height,subTile:16,visual:false,publicKey:key.raw,sign:b=>sign(null,b,key.privateKey)});
 const red=parse(await redactRects(doc,[[1,1,10,10]],{granularity:16}));
 const cases=[];let copy=structuredClone(red);copy.tiles[0].seed=doc.tiles[0].seed;cases.push(encodeGRD2(copy));copy=structuredClone(red);copy.tiles[0].sub.pop();cases.push(encodeGRD2(copy));
 for(const [x,y] of [[1,1],[40,40]]){copy=structuredClone(red);const p=await decodeRgbPng(image(copy));p.rgb[(y*width+x)*3]^=128;copy.image=base64(await encodeRgbPng(p.rgb,width,height));cases.push(encodeGRD2(copy));}
 for(const bytes of cases){assert.equal((await verifyGRD2(bytes,[key.anchor])).verdict,'TAMPERED');assert.equal(runPython(bytes).verdict,'TAMPERED');}
 const all=await redactGRD2(doc,[0,1,2,3,4,5]);assert.equal((await verifyGRD2(all,[key.anchor])).verdict,'FULLY REDACTED');
 const repeat=await redactRects(parse(all),[[1,1,10,10]],{granularity:16});assert.equal((await verifyGRD2(repeat,[key.anchor])).verdict,'FULLY REDACTED');assert.equal(runPython(repeat,true).verdict,'FULLY REDACTED');
 await assert.rejects(redactGRD2(doc,[.5]),/Invalid redaction index/);
});
test('partial redaction of a single parent tile retains a regional verdict',async()=>{
 const doc=await sealRgba({rgba:new Uint8Array(64*64*4).fill(255),width:64,height:64,subTile:16,publicKey:key.raw,sign:b=>sign(null,b,key.privateKey)}),red=await redactRects(doc,[[1,1,5,5]],{granularity:16});
 assert.equal((await verifyGRD2(red,[key.anchor])).verdict,'VERIFIED WITH REDACTIONS');assert.equal(runPython(red).verdict,'VERIFIED WITH REDACTIONS');
});
