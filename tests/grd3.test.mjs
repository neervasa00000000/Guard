// SPDX-License-Identifier: MIT
import test from 'node:test';
import assert from 'node:assert/strict';
import {sign} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {signer} from './fixtures.mjs';
import {sealRgba,encodeGRD3,decodeGRD3,verifyGRD2,redactGRD2,exportPlainImage,GRD3_LIMITS} from '../src/redactable.js';
import {decodeRgbPngBands} from '../src/png.js';
const key=signer(),rgba=new Uint8Array(131*67*4).fill(255);
for(let i=0;i<rgba.length;i+=4){rgba[i]=i%251;rgba[i+1]=(i>>>2)%255;rgba[i+2]=37;}
const doc=await sealRgba({rgba,width:131,height:67,version:3,publicKey:key.raw,sign:b=>sign(null,b,key.privateKey)});
const bytes=encodeGRD3(doc);
function python(cases){
 const proc=spawnSync('python3',['-c',`import sys,json,base64,grd
p=json.load(sys.stdin)
print(json.dumps([grd.verify(base64.b64decode(b),[p['key']])['verdict'] for b in p['cases']]))`],{input:JSON.stringify({key:key.raw.toString('hex'),cases:cases.map(b=>Buffer.from(b).toString('base64'))}),encoding:'utf8'});
 assert.equal(proc.status,0,proc.stderr);return JSON.parse(proc.stdout);
}
test('GRD3 binary round trip and honest redaction agree in JS and Python',async()=>{
 const decoded=decodeGRD3(bytes);assert.deepEqual(decoded.manifest,doc.manifest);assert.deepEqual(encodeGRD3(decoded),bytes);
 const redacted=await redactGRD2(decoded,[0,5]);
 for(const [b,expected] of [[bytes,'GENUINE'],[redacted,'VERIFIED WITH REDACTIONS']]){
  const r=await verifyGRD2(b,[key.anchor]);assert.equal(r.verdict,expected,JSON.stringify(r.problems));assert.equal(r.maxDecodedRows,64);
  assert.equal(python([b])[0],expected);
 }
 assert.ok((await exportPlainImage(redacted)).length>0);
});
test('GRD3 rejects framing and disclosure mutations with matching proof verdicts',async()=>{
 const length=new DataView(bytes.buffer).getUint32(5),signatureAt=9+length,nAt=signatureAt+64,recordAt=nAt+4;
 const change=(at,value)=>{const b=bytes.slice();b[at]=value??(b[at]^1);return b};
 const cases=[Uint8Array.from([...bytes,0]),bytes.subarray(0,-1),bytes.subarray(0,9),change(8),change(nAt+3),change(recordAt,3),change(recordAt+1),change(signatureAt)];
 for(const b of cases)assert.equal((await verifyGRD2(b,[key.anchor])).verdict,'TAMPERED');
 assert.deepEqual(python(cases),cases.map(()=> 'TAMPERED'));
});
test('GRD3 dimensions are checked before decoding pixels',async()=>{
 const malformed=bytes.slice(),raw=new TextDecoder().decode(malformed);
 // Same canonical manifest byte count, but dimension above the supported edge.
 const index=raw.indexOf('"width":131');const prefix=new TextEncoder().encode(raw.slice(0,index));
 const m={...doc.manifest,width:9000};
 await assert.rejects(sealRgba({rgba:new Uint8Array(1),width:36_000_001,height:1,version:3,publicKey:key.raw,sign:b=>sign(null,b,key.privateKey)}));
 const text=JSON.stringify(m,Object.keys(m).sort());
 const b=new Uint8Array(9+new TextEncoder().encode(text).length);b.set([71,82,68,51,10]);new DataView(b.buffer).setUint32(5,b.length-9);b.set(new TextEncoder().encode(text),9);
 assert.equal((await verifyGRD2(b,[key.anchor])).verdict,'LIMIT EXCEEDED');
 assert.equal(python([b])[0],'LIMIT EXCEEDED');
});
test('PNG band decoder emits no more than 64 rows and exactly reconstructs pixels',async()=>{
 const bands=[];for await(const band of decodeRgbPngBands(doc.image,GRD3_LIMITS)){assert.ok(band.rows<=64);bands.push(band);}
 assert.equal(bands.length,2);assert.equal(bands[0].rows,64);assert.equal(bands[1].rows,3);
 const rgb=Buffer.concat(bands.map(b=>Buffer.from(b.rgb)));for(let i=0;i<131*67;i++)for(let c=0;c<3;c++)assert.equal(rgb[i*3+c],rgba[i*4+c]);
});

test('shared GRD3 vectors agree across both implementations',async()=>{
 const {readFile}=await import('node:fs/promises');
 const shared=JSON.parse(await readFile(new URL('vectors/grd3-vectors.json',import.meta.url)));
 for(const v of shared.vectors){const b=Buffer.from(v.container,'base64');const r=await verifyGRD2(b,[{public_key_hex:shared.public_key_hex}]);assert.equal(r.verdict,v.expected_verdict,v.id);if(r.regionVerified)assert.equal(r.root,v.expected_root);}
});

test('all five PNG scanline filters agree across streaming JS and Python decoders',async()=>{
 const {PNG}=await import('pngjs');
 const cases=[];
 for(let filterType=0;filterType<5;filterType++){
  const image=PNG.sync.write({width:131,height:67,data:Buffer.from(rgba)},{colorType:2,inputColorType:6,filterType});
  const copy={...doc,image:new Uint8Array(image)},bytes=encodeGRD3(copy);cases.push(bytes);
  const r=await verifyGRD2(bytes,[key.anchor]);assert.equal(r.verdict,'GENUINE',`filter ${filterType}: ${JSON.stringify(r.problems)}`);
 }
 assert.deepEqual(python(cases),cases.map(()=> 'GENUINE'));
});

test('native Python filter path spans multiple compressed input slices',async()=>{
 const {PNG}=await import('pngjs');const width=257,height=129,pixels=new Uint8Array(width*height*4);let seed=42;
 for(let i=0;i<pixels.length;i+=4){seed=(Math.imul(seed,1664525)+1013904223)>>>0;pixels.set([seed&255,seed>>>8&255,seed>>>16&255,255],i);}
 const sealed=await sealRgba({rgba:pixels,width,height,version:3,visual:false,publicKey:key.raw,sign:b=>sign(null,b,key.privateKey)}),cases=[];
 for(const filterType of [1,2,3,4]){
  const png=PNG.sync.write({width,height,data:Buffer.from(pixels)},{colorType:2,inputColorType:6,filterType});assert.ok(png.length>16384);
  const bytes=encodeGRD3({...sealed,image:new Uint8Array(png)});assert.equal((await verifyGRD2(bytes,[key.anchor])).verdict,'GENUINE');cases.push(bytes);
 }
 assert.deepEqual(python(cases),cases.map(()=> 'GENUINE'));
});

test('Python alpha compositing matches the canonical JS integer formula without a second RGB working image',()=>{
 const width=17,height=9,rgba=Array.from({length:width*height*4},(_,i)=>(i*79+13)%256);
 const out=spawnSync('python3',['-c',`import sys,json,grd
p=json.load(sys.stdin);im=grd.Image.frombytes('RGBA',(p['width'],p['height']),bytes(p['rgba']));key=grd.Ed25519PrivateKey.from_private_bytes(bytes([42])*32);doc=grd.seal(im,key,version=3,visual=False);r=grd.verify_v2(grd.encode3(doc),[doc['manifest']['publicKey']],include_pixels=True);print(json.dumps(dict(verdict=r['verdict'],rgb=list(r['_rgb']))))`],{input:JSON.stringify({width,height,rgba}),encoding:'utf8'});
 assert.equal(out.status,0,out.stderr);const result=JSON.parse(out.stdout);assert.equal(result.verdict,'GENUINE');
 const expected=[];for(let i=0;i<rgba.length;i+=4)for(let c=0;c<3;c++)expected.push(Math.floor((rgba[i+c]*rgba[i+3]+255*(255-rgba[i+3])+127)/255));assert.deepEqual(result.rgb,expected);
});
