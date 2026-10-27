// SPDX-License-Identifier: MIT
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,mkdtemp,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {sign} from 'node:crypto';
import {mappedVisualTile,visualFeatures,visualDecision} from '../src/visual.js';
import {sealRgba,encodeGRD2,exportProof,verifyVisual} from '../src/redactable.js';
import {encodeRgbPng} from '../src/png.js';
import {signer} from './fixtures.mjs';

test('shared native RAW RGB at .5/.75/1/1.25/1.5x has identical JS/Python feature bytes',async()=>{
 const shared=JSON.parse(await readFile(new URL('vectors/area-vectors.json',import.meta.url)));
 for(const c of shared.cases)for(let i=0;i<c.features.length;i++)assert.equal(Buffer.from(mappedVisualTile(Buffer.from(c.rgb,'base64'),c.width,c.height,shared.sealed,i)).toString('hex'),c.features[i],c.id+' tile '+i);
 const py=spawnSync('python3',['-c',`import json,base64,grd,grd_visual
s=json.load(open('tests/vectors/area-vectors.json'))
for c in s['cases']:
 for i,f in enumerate(c['features']):assert grd_visual.mapped_tile_features(base64.b64decode(c['rgb']),c['width'],c['height'],s['sealed'],i,grd).hex()==f
print('PASS')`],{encoding:'utf8'});assert.equal(py.status,0,py.stderr);
});
test('same-size mapping preserves the signed y8c16-v1 feature bytes, including edge tiles',()=>{
 for(const [width,height] of [[1,1],[13,17],[64,64]]){const rgb=Uint8Array.from({length:width*height*3},(_,i)=>(137*i+51)%256);assert.deepEqual(mappedVisualTile(rgb,width,height,{width,height,tileSize:64},0),visualFeatures(rgb,width,height));}
});
test('rational overlaps and half-up ties are correct on a hand-computable fractional grid',()=>{
 // Sealed 17x1; candidate 2x1 black/white. First 8px cell is black;
 // next maps 1/17 black + 15/17 white, rounded to 239; last is white.
 const f=mappedVisualTile(Uint8Array.from([0,0,0,255,255,255]),2,1,{width:17,height:1,tileSize:64},0);
 assert.equal(f[0],0);assert.equal(f[1],239);assert.equal(f[2],255);
 const tie=mappedVisualTile(Uint8Array.from([0,0,0,1,1,1]),2,1,{width:1,height:1,tileSize:64},0);assert.equal(tie[0],1);
});
test('tau±2 is BORDERLINE with no positive consistency flag; CLI warns and exits 5',async()=>{
 const k=signer(),rgb=new Uint8Array(64*64*3).fill(100),rgba=new Uint8Array(64*64*4);for(let i=0;i<4096;i++)rgba.set([100,100,100,255],i*4);
 const source=await sealRgba({rgba,width:64,height:64,publicKey:k.raw,sign:b=>sign(null,b,k.privateKey)}),proof=await exportProof(encodeGRD2(source));
 const dir=await mkdtemp(join(tmpdir(),'guard-borderline-'));
 try{
  const p=join(dir,'proof.grdp'),image=join(dir,'copy.png');await writeFile(p,proof);
  for(const delta of [6,7,8,9,10,11,12]){const bytes=await encodeRgbPng(rgb.map(v=>v+delta),64,64),r=await verifyVisual(proof,bytes,[k.anchor]);assert.equal(r.visualVerdict,visualDecision(delta));assert.equal(r.worstError,delta);assert.equal(r.genuine,false);assert.equal(r.visualConsistent,delta===6);await writeFile(image,bytes);
   const cli=spawnSync('python3',['grd.py','verify-visual',p,image],{encoding:'utf8'}),py=JSON.parse(cli.stdout);assert.equal(py.visualVerdict,r.visualVerdict);assert.equal(cli.status,delta===12?2:5);if(delta>=7&&delta<=11)assert.match(cli.stderr,/Close to the threshold; result may differ between apps/);
  }
 }finally{await rm(dir,{recursive:true,force:true});}
});
