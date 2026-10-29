// SPDX-License-Identifier: MIT
import test from 'node:test';import assert from 'node:assert/strict';import {readFile} from 'node:fs/promises';
import {sealRgba,encodeGRD2,verifyGRD2,redactRects,containerImage} from '../src/redactable.js';
import {decodeRgbPng} from '../src/png.js';import {TRUST_POLICY} from '../src/trust.js';
const app=await readFile(new URL('../src/app.js',import.meta.url),'utf8');
const handler=app.slice(app.indexOf('$("convert-form").onsubmit ='),app.indexOf('$("copy-form").onsubmit'));
function harness({doc=null,anchors=[],areas=[{x:16,y:16,width:32,height:16}],saveOriginal=false,fail=false}={}){
 const nodes=new Map(),downloads=[];const $=id=>{if(!nodes.has(id))nodes.set(id,{disabled:false,checked:false,hidden:true,focus(){},setAttribute(){},removeAttribute(){}});return nodes.get(id);};$('convert-privacy').checked=true;$('save-original').checked=saveOriginal;
 const create=new Function('deps',`const {$,crypto,sealRgba,encodeGRD2,verifyGRD2,redactRects,TRUSTED,sessionTrust,download,File,bytesLabel,conversionStatus}=deps;
 let conversionImage={rgba:new Uint8Array(64*64*4).fill(255),width:64,height:64,sourceBytes:100},conversionVersion=1,operation=1,offlineSignerVersion=0,unlockedSigner=null,sealSourceDoc=deps.doc,sealAreas=deps.areas,lastSealedFile=null;
 const sealGrid=()=>16;${handler}
 return {run:()=>$('convert-form').onsubmit({preventDefault(){}}),file:()=>lastSealedFile};`);
 const subject=create({$,crypto:doc?{subtle:{generateKey(){throw Error('Must not re-sign a received GRD');}}}:crypto,sealRgba,encodeGRD2,verifyGRD2:fail?async()=>({regionVerified:false,signature_valid:false,verdict:'TAMPERED'}):verifyGRD2,redactRects,TRUSTED:[],sessionTrust:async()=>({anchors,policy:TRUST_POLICY}),download:(bytes,name)=>downloads.push({bytes,name}),File,bytesLabel:n=>n+' bytes',conversionStatus:text=>{$('convert-status').textContent=text;},doc,areas});return {subject,downloads,$};
}
test('first and only default download has zeroed blackout pixels and no disclosed salts for that area',async()=>{
 const h=harness();await h.subject.run();assert.equal(h.downloads.length,1);const r=await verifyGRD2(h.downloads[0].bytes,[]);assert.equal(r.verdict,'UNVERIFIED: SELF-SIGNED');assert.equal(r.regionVerified,true);assert.equal(r.hiddenPixelsCleared,true);assert(r.redactionMap.length>0);
 const rgb=await decodeRgbPng(containerImage(r.container));for(let y=16;y<32;y++)for(let x=16;x<48;x++)assert.deepEqual([...rgb.rgb.subarray((y*64+x)*3,(y*64+x)*3+3)],[0,0,0]);assert.equal(h.$('check-sealed').hidden,false);assert(h.subject.file() instanceof File);
});
test('saving the unblackened original requires explicit opt-in',async()=>{
 const h=harness({saveOriginal:true});await h.subject.run();assert.deepEqual(h.downloads.map(d=>d.name),['image.GRD','private-original.GRD']);const r=await verifyGRD2(h.downloads[1].bytes,[]);assert.equal(r.redactionMap.length,0);assert.equal(r.verdict,'UNVERIFIED: SELF-SIGNED');
});
test('received GRD blackouts retain its original signer, signature and root without any signing key',async()=>{
 const pair=await crypto.subtle.generateKey('Ed25519',false,['sign','verify']),publicKey=new Uint8Array(await crypto.subtle.exportKey('raw',pair.publicKey));
 const doc=await sealRgba({rgba:new Uint8Array(64*64*4).fill(255),width:64,height:64,publicKey,subTile:16,sign:b=>crypto.subtle.sign('Ed25519',pair.privateKey,b)}),anchors=[{public_key_hex:Buffer.from(publicKey).toString('hex'),name:'TEST ONLY original issuer'}];
 const h=harness({doc,anchors});await h.subject.run();assert.equal(h.downloads.length,1);const r=await verifyGRD2(h.downloads[0].bytes,anchors);assert.equal(r.verdict,'VERIFIED WITH REDACTIONS');assert.equal(r.container.signature,doc.signature);assert.equal(r.container.manifest.root,doc.manifest.root);assert.equal(r.container.manifest.publicKey,doc.manifest.publicKey);
});
test('failed self-check produces no file and no Check this file link',async()=>{
 const h=harness({fail:true});await h.subject.run();assert.equal(h.downloads.length,0);assert.equal(h.$('check-sealed').hidden,true);assert.match(h.$('convert-status').textContent,/Nothing was downloaded/);
});
test('rectangle editor rounds outward, stays inside the image, and rejects invalid coordinates',()=>{
 const body=app.slice(app.indexOf('function roundSealArea('),app.indexOf('function drawSealEditor('));const round=new Function('conversionImage','sealGrid',body+'return roundSealArea;')({width:70,height:68},()=>16);
 assert.deepEqual(round({x:17,y:18,width:1,height:1}),{x:16,y:16,width:16,height:16});assert.deepEqual(round({x:65,y:65,width:40,height:40}),{x:64,y:64,width:6,height:4});for(const rect of [{x:-1,y:0,width:10,height:10},{x:70,y:0,width:1,height:1},{x:0,y:0,width:0,height:4},{x:NaN,y:0,width:2,height:2}])assert.throws(()=>round(rect));
});
test('CSP and offline/no-storage constraints survive the redesign',async()=>{
 const html=await readFile(new URL('../index.html',import.meta.url),'utf8');assert.equal(html.match(/http-equiv="Content-Security-Policy"\s+content="([^"]+)"/)[1],"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src blob: data:; connect-src 'none'; worker-src blob:; object-src 'none'; base-uri 'none'; form-action 'none'");assert.doesNotMatch(html,/<script[^>]+src=|<link[^>]+rel="stylesheet"/);assert.doesNotMatch(html,/\b(?:localStorage|indexedDB|navigator\.serviceWorker)\s*[.(]/);
});
