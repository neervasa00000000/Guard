// SPDX-License-Identifier: MIT
import test from 'node:test';
import assert from 'node:assert/strict';
import {generateKeyPairSync,createHash,sign} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {verifyTrustBundle} from '../src/trust-bundle.js';
import {sealRgba,encodeGRD2} from '../src/redactable.js';
const root=generateKeyPairSync('ed25519'), signer=generateKeyPairSync('ed25519');
const raw=k=>k.publicKey.export({type:'spki',format:'der'}).subarray(-32);
const fp=createHash('sha256').update(raw(signer)).digest('hex'),rootHex=raw(root).toString('hex');
const canon=v=>Array.isArray(v)?'['+v.map(canon).join(',')+']':v&&typeof v==='object'?'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canon(v[k])).join(',')+'}':JSON.stringify(v);
const now=Date.parse('2026-10-27T12:00:00Z');
function payload(sequence=1,revoked=false){return {format:'GUARD-TRUST-1',sequence,issued:'2026-10-27T00:00:00Z',expires:'2026-11-27T00:00:00Z',keys:{version:1,asOf:'2026-10-27T00:00:00Z',signers:[{key_id:fp.slice(0,16),public_key_hex:raw(signer).toString('hex'),fingerprint_sha256:fp,name:'TEST ONLY issuer',alg:'Ed25519',revoked,revokedAt:revoked?'2026-10-26T00:00:00Z':null,reason:revoked?'Test compromise':null}]}};}
function encode(p){return Buffer.from(canon({payload:p,signature:sign(null,Buffer.concat([Buffer.from('GUARD-TRUST-BUNDLE-V1\0'),Buffer.from(canon(p))]),root.privateKey).toString('base64')}));}
function python(data,options={}){const proc=spawnSync('python3',['-c',`import sys,json,base64;import trust_bundle
x=json.load(sys.stdin)
try:
 r=trust_bundle.verify_bundle(base64.b64decode(x['data']),x['root'],now=x['now'],min_sequence=x.get('minSequence',1),previous=x.get('previous'));print(json.dumps(dict(ok=True,result=r)))
except Exception as e:print(json.dumps(dict(ok=False,error=str(e))))`],{input:JSON.stringify({data:Buffer.from(data).toString('base64'),root:rootHex,now,...options}),encoding:'utf8',cwd:new URL('../',import.meta.url)});assert.equal(proc.status,0,proc.stderr);return JSON.parse(proc.stdout);}
test('signed bundles give identical JS/Python anchors, policy, digest and root-pinned state',async()=>{
 for(const revoked of [false,true]){const data=encode(payload(2,revoked));const r=await verifyTrustBundle(data,rootHex,{now});assert.deepEqual(r,python(data).result);assert.equal(r.anchors.length,revoked?0:1);assert.equal(r.policy.revoked.length,revoked?1:0);assert.deepEqual(await verifyTrustBundle(data,rootHex,{now,previous:r.state}),r);}
});
test('signed malformed, stale, rollback, equivocation and forgery cases fail in both languages',async()=>{
 const good=encode(payload(2)),state=(await verifyTrustBundle(good,rootHex,{now})).state;
 const cases=[];const bad=(edit,options={})=>{const p=payload(2);edit(p);cases.push([encode(p),options]);};
 cases.push([Buffer.concat([good,Buffer.from('\n')]),{}]);const forged=Buffer.from(good);forged[forged.length-8]^=1;cases.push([forged,{}]);
 bad(p=>p.expires='2026-10-27T12:00:00Z');bad(p=>p.issued=p.keys.asOf='2026-10-28T00:00:00Z');bad(p=>p.expires='2027-11-27T00:00:00Z');bad(p=>p.issued='2026-02-30T00:00:00Z');bad(p=>p.keys.signers.push({...p.keys.signers[0]}));bad(p=>p.keys.signers[0].fingerprint_sha256='0'.repeat(64));bad(p=>p.keys.signers[0].key_id='0'.repeat(16));bad(p=>p.keys.signers[0].unknown=1);bad(p=>p.keys.extra=1);bad(p=>p.keys.signers[0].name='\ud800');bad(p=>p.keys.signers[0].reason='unexpected');bad(p=>p.sequence=1,{previous:state});bad(p=>p.keys.signers[0].name='Changed',{previous:state});bad(p=>{}, {minSequence:3});bad(p=>{}, {previous:{...state,rootFingerprint:'0'.repeat(64)}});bad(p=>{}, {previous:false});bad(p=>{p.keys.signers[0].revoked=true;p.keys.signers[0].revokedAt='2026-10-28T00:00:00Z';p.keys.signers[0].reason='test';});
 for(const [data,options] of cases){await assert.rejects(verifyTrustBundle(data,rootHex,{now,...options}));assert.equal(python(data,options).ok,false);}
 await assert.rejects(verifyTrustBundle(good,'0'.repeat(64),{now}));assert.equal(python(good,{root:'0'.repeat(64)}).ok,false);
});
test('CLI recognizes the signed issuer, persists state, rejects rollback and enforces revocation',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'guard-bundle-'));
 try{
  const image=join(dir,'image.GRD'),bundle=join(dir,'bundle.json'),pub=join(dir,'root.pem'),state=join(dir,'state.json'),privatePath=join(dir,'root-private.pem'),keys=join(dir,'keys.json');
  await writeFile(pub,root.publicKey.export({type:'spki',format:'pem'}));await writeFile(privatePath,root.privateKey.export({type:'pkcs8',format:'pem'}));
  // CLI uses real wall clock; issue today and expire tomorrow rather than depending on a test clock.
  const issued=new Date().toISOString().slice(0,10)+'T00:00:00Z',expires=new Date(Date.parse(issued)+86400000).toISOString().replace('.000Z','Z');
  const p=payload(2);p.issued=p.keys.asOf=issued;p.expires=expires;
  await writeFile(keys,JSON.stringify(p.keys));
  const signCLI=spawnSync('python3',['trust_bundle.py','sign','--keys',keys,'--root-key',privatePath,'--sequence','2','--issued',issued,'--expires',expires,'-o',bundle],{encoding:'utf8'});assert.equal(signCLI.status,0,signCLI.stdout+signCLI.stderr);
  const rgba=new Uint8Array(64*64*4).fill(255);await writeFile(image,encodeGRD2(await sealRgba({rgba,width:64,height:64,version:3,publicKey:raw(signer),sign:b=>sign(null,b,signer.privateKey)})));
  const run=()=>spawnSync('python3',['trust_bundle.py','verify',image,'--bundle',bundle,'--root',pub,'--state',state],{encoding:'utf8'});
  let proc=run();assert.equal(proc.status,0,proc.stdout);assert.equal(JSON.parse(proc.stdout).verdict,'GENUINE');const remembered=await readFile(state,'utf8');
  p.sequence=1;await writeFile(bundle,encode(p));proc=run();assert.equal(proc.status,4);assert.equal(await readFile(state,'utf8'),remembered);
  p.sequence=3;Object.assign(p.keys.signers[0],{revoked:true,revokedAt:issued,reason:'Test compromise'});await writeFile(bundle,encode(p));proc=run();assert.equal(proc.status,6,proc.stdout);assert.equal(JSON.parse(proc.stdout).verdict,'REVOKED KEY');assert.equal(JSON.parse(await readFile(state,'utf8')).sequence,3);
 }finally{await rm(dir,{recursive:true,force:true});}
});
