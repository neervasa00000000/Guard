// SPDX-License-Identifier: MIT
import test from 'node:test';import assert from 'node:assert/strict';
import {mkdtemp,mkdir,cp,writeFile,readFile,rm} from 'node:fs/promises';import {tmpdir} from 'node:os';import {join} from 'node:path';import {spawnSync} from 'node:child_process';import {createPrivateKey,createPublicKey} from 'node:crypto';
import {updateSignerRegistry} from '../scripts/pin-signer.mjs';
test('CLI requires explicit --rename, permits idempotent pinning, and cannot reactivate revoked keys',async()=>{
 const root=await mkdtemp(join(tmpdir(),'guard-rename-'));
 try{
  await mkdir(join(root,'scripts'));await cp(new URL('../src/',import.meta.url),join(root,'src'),{recursive:true});await cp(new URL('../scripts/pin-signer.mjs',import.meta.url),join(root,'scripts/pin-signer.mjs'));await writeFile(join(root,'package.json'),'{"type":"module"}');
  // TEST ONLY public deterministic seed. The private material is never written.
  const privateKey=createPrivateKey({key:Buffer.concat([Buffer.from('302e020100300506032b657004220420','hex'),Buffer.alloc(32,50)]),format:'der',type:'pkcs8'}),pem=createPublicKey(privateKey).export({type:'spki',format:'pem'}),path=join(root,'public.pem');await writeFile(path,pem);
  const run=(name,...flags)=>spawnSync(process.execPath,[join(root,'scripts/pin-signer.mjs'),'--public',path,'--name',name,...flags],{encoding:'utf8'});
  let proc=run('TEST ONLY Alpha');assert.equal(proc.status,0,proc.stderr);const entry=JSON.parse(proc.stdout),before=await readFile(join(root,'src/trusted-keys.json'),'utf8');
  proc=run('TEST ONLY Beta');assert.equal(proc.status,1);assert.match(proc.stderr,/without --rename/);assert.equal(await readFile(join(root,'src/trusted-keys.json'),'utf8'),before);
  proc=run('TEST ONLY Beta','--rename');assert.equal(proc.status,0,proc.stderr);assert.equal(JSON.parse(proc.stdout).name,'TEST ONLY Beta');assert.equal(await readFile(join(root,'src/trusted-keys.json'),'utf8'),await readFile(join(root,'.well-known/guard-signers.json'),'utf8'));
  assert.equal(run('TEST ONLY Beta').status,0);
  await updateSignerRegistry({root,revoke:entry.fingerprint,reason:'TEST ONLY retired',at:'2026-10-29T00:00:00Z'});
  proc=run('TEST ONLY Beta','--rename');assert.equal(proc.status,1);assert.match(proc.stderr,/reactivate a revoked key/);
 }finally{await rm(root,{recursive:true,force:true});}
});
