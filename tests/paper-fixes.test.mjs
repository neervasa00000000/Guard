// SPDX-License-Identifier: MIT
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile, mkdtemp,writeFile,rm} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {verifyGRD2,encodeGRD2,exportPlainImage,isCanonicalBase64Shape,redactGRD2,sealRgba} from '../src/redactable.js';
import {decodeRgbPng,encodeRgbPng,PngFormatError} from '../src/png.js';
import {signer} from './fixtures.mjs';
import {sign} from 'node:crypto';
const vectors=JSON.parse(await readFile(new URL('vectors/grd2-vectors.json',import.meta.url),'utf8'));
const anchors=[{public_key_hex:vectors.public_key_hex}];
const bytes=Buffer.from(vectors.vectors[4].container,'base64');
const document=JSON.parse(bytes.subarray(5));
test('shared legacy and 2.1 vectors: verdict, root and signed identity binding',async()=>{
 for(const v of vectors.vectors){
  const r=await verifyGRD2(Buffer.from(v.container,'base64'),anchors);
  assert.equal(r.verdict,v.expected_verdict,v.id);
  if(r.regionVerified)assert.equal(r.root,v.expected_root);
 }
});
test('base64 validation stays linear at 20 MB and rejects invalid shapes',()=>{
 for(const s of ['', 'QQ==','QUI=','QUJD'])assert.equal(isCanonicalBase64Shape(s),true);
 for(const s of ['Q','QQ=','Q=Q=','QQ==QQ==','QU I=','éééé'])assert.equal(isCanonicalBase64Shape(s),false,s);
 const large='QUJD'.repeat(5_000_000),start=performance.now();
 assert.equal(isCanonicalBase64Shape(large),true);
 console.log('20 MB base64 shape scan ms:',(performance.now()-start).toFixed(2));
});
test('malformed proof shapes, UTF-8, truncation and 200 body flips are TAMPERED',async()=>{
 for(const body of [null,[],1,'text',{manifest:null},{...document,tiles:null},{...document,redactions:[null]}])
  assert.equal((await verifyGRD2(Buffer.from('GRD2\n'+JSON.stringify(body)),anchors)).verdict,'TAMPERED');
 for(const length of [Math.floor(bytes.length/2),Math.floor(bytes.length*.99),bytes.length-1])
  assert.equal((await verifyGRD2(bytes.subarray(0,length),anchors)).verdict,'TAMPERED');
 const bad=Buffer.from(bytes);bad[7]=255;
 assert.equal((await verifyGRD2(bad,anchors)).verdict,'TAMPERED');
 let seed=42;
 for(let i=0;i<200;i++){
  seed=(Math.imul(seed,1664525)+1013904223)>>>0;
  const flipped=Buffer.from(bytes);flipped[5+seed%(bytes.length-5)]^=1<<(seed>>>24)%8;
  assert.equal((await verifyGRD2(flipped,anchors)).verdict,'TAMPERED','flip '+i);
 }
});
test('PNG corruption is a proof error while an injected decoder runtime fault cannot accuse the file',async()=>{
 const original=globalThis.DecompressionStream;
 try{
  globalThis.DecompressionStream=class {constructor(){throw new RangeError('Injected decoder fault')}};
  const r=await verifyGRD2(bytes,anchors);assert.equal(r.verdict,'CANNOT VERIFY');assert.equal(r.verifierFault,true);
 }finally{globalThis.DecompressionStream=original;}
 const d=structuredClone(document);const png=Buffer.from(d.image,'base64');png[40]^=1;d.image=png.toString('base64');
 assert.equal((await verifyGRD2(encodeGRD2(d),anchors)).verdict,'TAMPERED');
});
test('limits and invalid local trust policy have distinct verdicts',async()=>{
 for(const edit of [m=>m.width=4097,m=>m.height=4097,m=>{m.width=4096;m.height=2048},m=>{m.width=4096;m.height=1025}]){
  const d=structuredClone(document);edit(d.manifest);
  assert.equal((await verifyGRD2(encodeGRD2(d),anchors)).verdict,'LIMIT EXCEEDED');
 }
 const r=await verifyGRD2(bytes,anchors,{revoked:'invalid'});
 assert.equal(r.verdict,'CANNOT VERIFY');assert.equal(r.verifierFault,true);
 assert.equal((await verifyGRD2(new Uint8Array(33*1024*1024))).verdict,'LIMIT EXCEEDED');
});
test('plain PNG preserves visible pixels, clears hidden tiles and refuses damaged proofs; CLI supports PNG and JPEG',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'guard-plain-'));
 try{
  for(const v of vectors.vectors.filter(v=>['GENUINE','VERIFIED WITH REDACTIONS'].includes(v.expected_verdict))){
   const data=Buffer.from(v.container,'base64');
   const plain=await exportPlainImage(data),decoded=await decodeRgbPng(plain);
   assert.deepEqual(decoded.rgb,(await decodeRgbPng(Buffer.from(JSON.parse(data.subarray(5)).image,'base64'))).rgb);
   const types=[];for(let at=8;at<plain.length;){const n=new DataView(plain.buffer,plain.byteOffset+at,4).getUint32(0);types.push(new TextDecoder().decode(plain.subarray(at+4,at+8)));at+=n+12;}
   assert.deepEqual([...new Set(types)],['IHDR','IDAT','IEND']);
   assert.equal(Buffer.from(plain).includes(Buffer.from('GRD')),false);
  }
  await assert.rejects(exportPlainImage(Buffer.from(vectors.vectors[6].container,'base64')),/invalid source/);
  const input=join(dir,'input.GRD');await writeFile(input,bytes);
  for(const format of ['png','jpeg']){
   const output=join(dir,'plain.'+format);
   const proc=spawnSync('python3',['grd.py','export',input,'--plain','--format',format,'-o',output],{encoding:'utf8'});
   assert.equal(proc.status,0,proc.stderr);assert.match(proc.stderr,/no longer verifiable/);
   const image=await readFile(output);assert.equal(image[0],format==='png'?137:255);
   if(format==='jpeg')assert.equal(spawnSync('python3',['grd.py','verify',output]).status,3);
  }
  assert.notEqual(spawnSync('python3',['grd.py','export',input,'-o',join(dir,'refused.png')]).status,0);
 }finally{await rm(dir,{recursive:true,force:true});}
});
test('two honest 2.1 seals have distinct asset IDs, roots and every tile commitment',async()=>{
 const key=signer(),args={rgba:new Uint8Array(128*64*4).fill(255),width:128,height:64,publicKey:key.raw,sign:b=>sign(null,b,key.privateKey)};
 const a=await sealRgba(args),b=await sealRgba(args);
 assert.notEqual(a.manifest.assetId,b.manifest.assetId);assert.notEqual(a.manifest.root,b.manifest.root);
 a.manifest.commitments.forEach((c,i)=>assert.notEqual(c,b.manifest.commitments[i]));
});
