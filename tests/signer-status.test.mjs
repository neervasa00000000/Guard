// SPDX-License-Identifier: MIT
import test from 'node:test';import assert from 'node:assert/strict';import {readFile,writeFile,mkdtemp,rm,mkdir} from 'node:fs/promises';import {join} from 'node:path';import {tmpdir} from 'node:os';import {spawnSync} from 'node:child_process';import {createPrivateKey} from 'node:crypto';import {verifyGRD2} from '../src/redactable.js';import {createVerifier} from '../src/verifier.js';import {updateSignerRegistry} from '../scripts/pin-signer.mjs';
const shared=JSON.parse(await readFile(new URL('vectors/signer-status-vectors.json',import.meta.url))),key=shared.keys.signers[0];
function python(bytes,keys=shared.keys,policy=null){const py=spawnSync('python3',['-c',`import sys,json,tempfile,base64;from pathlib import Path;import grd
x=json.load(sys.stdin)
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'keys.json';p.write_text(json.dumps(x['keys']));r=grd.verify(base64.b64decode(x['data']),keys_path=p,policy=x['policy']);print(json.dumps({k:r.get(k) for k in ('verdict','signerStatus','signerDisplayName','fingerprint')}))`],{input:JSON.stringify({data:bytes.toString('base64'),keys,policy}),encoding:'utf8'});assert.equal(py.status,0,py.stderr);return JSON.parse(py.stdout);}
const fields=r=>Object.fromEntries(['verdict','signerStatus','signerDisplayName','fingerprint'].map(k=>[k,r[k]]));
test('shared GRD2/3 signer identity, personal/demo and redaction reports agree in JS/Python',async()=>{
 for(const v of shared.cases){const bytes=Buffer.from(v.container,'base64'),js=await verifyGRD2(bytes,[key]);assert.equal(js.signerStatus,v.status,v.id);assert.equal(js.verdict,v.expected_verdict);assert.equal(js.fingerprint,key.fingerprint_sha256);assert.deepEqual(fields(js),python(bytes));}
});
test('unknown, revoked and invalid files never gain trusted signer status or automatic display',async()=>{
 const bytes=Buffer.from(shared.cases[0].container,'base64'),empty={...shared.keys,signers:[]};let js=await verifyGRD2(bytes,[]);assert.equal(js.signerStatus,'unknown');assert.equal(js.viewable,false);assert.equal(js.genuine,false);assert.equal(js.canRevealUnknown,true);assert.deepEqual(fields(js),python(bytes,empty));
 const policy={version:1,asOf:'2026-10-29T00:00:00Z',revoked:[{fingerprint:key.fingerprint_sha256,reason:'TEST ONLY revocation',revokedAt:'2026-10-28T00:00:00Z'}]};js=await verifyGRD2(bytes,[key],policy);assert.equal(js.signerStatus,'revoked');assert.equal(js.viewable,false);assert.deepEqual(fields(js),python(bytes,shared.keys,policy));
 js=await verifyGRD2(bytes.subarray(0,20),[key]);assert.equal(js.signerStatus,'none');assert.equal(js.signerDisplayName,null);
});
test('pin helper refuses private keys and keeps public registries/revocation in agreement',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'guard-pin-test-'));
 try{await mkdir(join(dir,'src'));await writeFile(join(dir,'src/trusted-keys.json'),JSON.stringify({...shared.keys,signers:[]}));await writeFile(join(dir,'src/trust-policy.json'),JSON.stringify({version:1,asOf:shared.keys.asOf,revoked:[]}));
  const privateKey=createPrivateKey({key:Buffer.concat([Buffer.from('302e020100300506032b657004220420','hex'),Buffer.alloc(32,48)]),format:'der',type:'pkcs8'});
  await assert.rejects(updateSignerRegistry({root:dir,publicPem:privateKey.export({type:'pkcs8',format:'pem'}),name:'Test'}),/Refusing: this is a private key/);
  const {createPublicKey}=await import('node:crypto');const pub=createPublicKey(privateKey).export({type:'spki',format:'pem'});await updateSignerRegistry({root:dir,publicPem:pub,name:key.name});
  assert.equal(await readFile(join(dir,'src/trusted-keys.json'),'utf8'),await readFile(join(dir,'.well-known/guard-signers.json'),'utf8'));
  await updateSignerRegistry({root:dir,revoke:key.fingerprint_sha256,reason:'TEST ONLY revoked',at:'2026-10-29T00:00:00Z'});assert.equal(JSON.parse(await readFile(join(dir,'src/trust-policy.json'))).revoked[0].fingerprint,key.fingerprint_sha256);
  await assert.rejects(updateSignerRegistry({root:dir,publicPem:pub,name:key.name}),/reactivate/);
 }finally{await rm(dir,{recursive:true,force:true});}
});

test('all conformance GRD1/2/3 files have matching signer metadata in JS/Python',async()=>{
 const keys=JSON.parse(await readFile(new URL('../conformance/trusted-keys.test.json',import.meta.url))),vectors=JSON.parse(await readFile(new URL('../conformance/vectors.json',import.meta.url))),policy={version:1,asOf:keys.asOf,revoked:keys.signers.filter(s=>s.revoked).map(s=>({fingerprint:s.fingerprint_sha256,reason:s.reason,revokedAt:s.revokedAt}))};
 for(const v of vectors){const bytes=await readFile(new URL('../'+v.file,import.meta.url)),js=v.format===1?await createVerifier(keys.signers,policy)(bytes):await verifyGRD2(bytes,keys.signers,policy);assert.deepEqual(fields(js),python(bytes,keys,policy),v.id);}
});

test('build refuses a published registry that differs from the embedded registry',async()=>{
 const {cp}=await import('node:fs/promises'),dir=await mkdtemp(join(tmpdir(),'guard-build-registry-'));
 try{await mkdir(join(dir,'scripts'));await mkdir(join(dir,'.well-known'));await cp(new URL('../src/',import.meta.url),join(dir,'src'),{recursive:true});await cp(new URL('../scripts/build.mjs',import.meta.url),join(dir,'scripts/build.mjs'));await writeFile(join(dir,'.well-known/guard-signers.json'),JSON.stringify({...shared.keys,signers:[]}));const proc=spawnSync(process.execPath,[join(dir,'scripts/build.mjs')],{encoding:'utf8'});assert.notEqual(proc.status,0);assert.match(proc.stderr,/Published signer registry differs/);}finally{await rm(dir,{recursive:true,force:true});}
});

test('existing shared GRD2/GRD3 exact vectors retain signer parity as well as their verdicts',async()=>{
 const {createHash}=await import('node:crypto');
 for(const file of ['grd2-vectors.json','grd3-vectors.json','upgrade-vectors.json']){const s=JSON.parse(await readFile(new URL('vectors/'+file,import.meta.url))),fp=createHash('sha256').update(Buffer.from(s.public_key_hex,'hex')).digest('hex'),keys={version:1,asOf:shared.keys.asOf,signers:[{...key,public_key_hex:s.public_key_hex,fingerprint_sha256:fp,key_id:fp.slice(0,16)}]};for(const v of s.vectors){const bytes=Buffer.from(v.container,'base64'),js=await verifyGRD2(bytes,keys.signers);assert.equal(js.verdict,v.expected_verdict,v.id);assert.deepEqual(fields(js),python(bytes,keys),file+':'+v.id);}}
});
