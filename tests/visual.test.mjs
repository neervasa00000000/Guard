// SPDX-License-Identifier: MIT
import test from 'node:test';
import assert from 'node:assert/strict';
import {sign} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import sharp from 'sharp';
import {signer} from './fixtures.mjs';
import {canon} from '../src/verifier.js';
import {sealRgba,encodeGRD2,verifyGRD2,exportProof,verifyVisual,redactGRD2,visualFeatures,decodeBase64,base64} from '../src/redactable.js';
import {encodeRgbPng} from '../src/png.js';
const key=signer(),width=192,height=128,rgb=new Uint8Array(width*height*3),rgba=new Uint8Array(width*height*4);
for(let y=0;y<height;y++)for(let x=0;x<width;x++){
 const c=[Math.floor(x*200/width)+20,Math.floor(y*180/height)+30,Math.floor((x+y)*150/(width+height))+40];rgb.set(c,(y*width+x)*3);rgba.set([...c,255],(y*width+x)*4);
}
const doc=await sealRgba({rgba,width,height,publicKey:key.raw,sign:b=>sign(null,b,key.privateKey)}),sealed=encodeGRD2(doc),proof=await exportProof(sealed);
const python=(p,image)=>{
 const out=spawnSync('python3',['-c',`import sys,json,base64,grd
p=json.load(sys.stdin);r=grd.verify_visual(base64.b64decode(p['proof']),base64.b64decode(p['image']),[p['key']]);print(json.dumps(r))`],{input:JSON.stringify({proof:base64(p),image:base64(image),key:key.raw.toString('hex')}),encoding:'utf8'});
 assert.equal(out.status,0,out.stderr);return JSON.parse(out.stdout);
};
test('visual features use bit-identical integer arithmetic and edge cells in JS/Python',()=>{
 const cases=[[1,1],[13,17],[64,64]].map(([w,h])=>({w,h,rgb:Array.from({length:w*h*3},(_,i)=>(i*137+51)%256)}));
 const py=spawnSync('python3',['-c',`import sys,json,grd
print(json.dumps([list(grd.visual_features(bytes(p['rgb']),p['w'],p['h'])) for p in json.load(sys.stdin)]))`],{input:JSON.stringify(cases),encoding:'utf8'});
 assert.equal(py.status,0,py.stderr);const values=JSON.parse(py.stdout);
 cases.forEach((p,i)=>assert.deepEqual(Array.from(visualFeatures(Uint8Array.from(p.rgb),p.w,p.h)),values[i]));
});
test('JPEG q30/50/75/95 and 0.5x/1.5x copies stay visually consistent without an exact authenticity verdict',async()=>{
 const images=[];
 for(const quality of [30,50,75,95])images.push(await sharp(rgb,{raw:{width,height,channels:3}}).jpeg({quality}).toBuffer());
 for(const scale of [.5,1.5])images.push(await sharp(rgb,{raw:{width,height,channels:3}}).resize(width*scale,height*scale,{kernel:'cubic'}).png().toBuffer());
 for(const image of images){const js=await verifyVisual(proof,image,[key.anchor]),py=python(proof,image);assert.equal(js.verdict,'VISUALLY CONSISTENT',JSON.stringify(js));assert.equal(py.verdict,js.verdict,JSON.stringify(py));assert.equal(js.genuine,false);assert.equal(py.genuine,false);}
});
test('splices and added text fail; mean-preserving changes document the visual limitation',async()=>{
 const spliced=rgb.slice();for(let y=32;y<64;y++)for(let x=40;x<72;x++)spliced.set([255,255,255],(y*width+x)*3);
 const text=rgb.slice();for(let y=20;y<44;y++)for(let x=20;x<60;x++)if((x%12)<4||y<24)text.set([0,0,0],(y*width+x)*3);
 for(const bytes of [spliced,text]){const image=await encodeRgbPng(bytes,width,height);assert.equal((await verifyVisual(proof,image,[key.anchor])).verdict,'VISUALLY INCONSISTENT');assert.equal(python(proof,image).verdict,'VISUALLY INCONSISTENT');}
 const shuffled=rgb.slice();const pixel=shuffled.slice(0,3);shuffled.copyWithin(0,3,6);shuffled.set(pixel,3);
 const image=await encodeRgbPng(shuffled,width,height);assert.equal((await verifyVisual(proof,image,[key.anchor])).verdict,'VISUALLY CONSISTENT');
 const edited=structuredClone(doc);edited.image=base64(image);assert.equal((await verifyGRD2(encodeGRD2(edited),[key.anchor])).verdict,'TAMPERED');
});
test('redacted proof discloses no hidden features/salts, checks black, and rejects a changed reference',async()=>{
 const bytes=await redactGRD2(doc,[0]),p=await exportProof(bytes),parsed=JSON.parse(new TextDecoder().decode(p.subarray(5)));
 assert.deepEqual(Object.keys(parsed.vis[0]).sort(),['commitment','index']);
 assert.equal((await verifyVisual(p,decodeBase64(doc.image),[key.anchor])).verdict,'VISUALLY INCONSISTENT');
 const red=JSON.parse(new TextDecoder().decode(bytes.subarray(5))),image=decodeBase64(red.image);
 assert.equal((await verifyVisual(p,image,[key.anchor])).verdict,'VISUALLY CONSISTENT');assert.equal(python(p,image).verdict,'VISUALLY CONSISTENT');
 parsed.vis[1].feature=base64(new Uint8Array(96));const forged=new TextEncoder().encode('GRDP\n'+canon(parsed));
 assert.equal((await verifyVisual(forged,image,[key.anchor])).verdict,'TAMPERED');assert.equal(python(forged,image).verdict,'TAMPERED');
});

test('shared fine and visual profile vectors agree with Python',async()=>{
 const {readFile}=await import('node:fs/promises');const shared=JSON.parse(await readFile(new URL('vectors/upgrade-vectors.json',import.meta.url)));
 for(const v of shared.vectors){const r=await verifyGRD2(Buffer.from(v.container,'base64'),[{public_key_hex:shared.public_key_hex}]);assert.equal(r.verdict,v.expected_verdict,v.id+': '+JSON.stringify(r.problems));}
 for(const v of shared.visual){const r=await verifyVisual(Buffer.from(v.proof,'base64'),Buffer.from(v.image,'base64'),[{public_key_hex:shared.public_key_hex}]);assert.equal(r.verdict,v.expected_verdict,v.id);}
});

test('a wholly hidden visual proof makes no positive visible-content claim',async()=>{
 const bytes=await redactGRD2(doc,[0,1,2,3,4,5]),p=await exportProof(bytes),d=JSON.parse(new TextDecoder().decode(bytes.subarray(5))),image=decodeBase64(d.image);
 const js=await verifyVisual(p,image,[key.anchor]),py=python(p,image);assert.equal(js.verdict,'FULLY REDACTED');assert.equal(py.verdict,js.verdict);assert.equal(js.genuine,false);assert.equal(js.visualConsistent,false);
});
