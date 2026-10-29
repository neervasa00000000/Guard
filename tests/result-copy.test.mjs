// SPDX-License-Identifier: MIT
import test from 'node:test';import assert from 'node:assert/strict';
import {readFile,mkdtemp,mkdir,cp,writeFile,rm} from 'node:fs/promises';import {tmpdir} from 'node:os';import {join} from 'node:path';import {spawnSync} from 'node:child_process';
import {resultTitle,signerSummary} from '../src/result-copy.js';
test('plain-language titles preserve signer distinctions and technical verdicts',()=>{
 const cases={GENUINE:'Genuine','VERIFIED WITH REDACTIONS':'Genuine, with parts blacked out','UNVERIFIED: SELF-SIGNED':'Unknown signer',TAMPERED:'Changed',DEMO:'Example only','FULLY REDACTED':'Genuine, but everything is blacked out','NOT A GRD':'Not a Guard file','REVOKED KEY':'Revoked signer'};
 for(const [verdict,title] of Object.entries(cases)){const r={verdict,signerStatus:'trusted',signerDisplayName:'Test Org'};assert.equal(resultTitle(r),title);assert.equal(r.verdict,verdict);}
 for(const verdict of ['CANNOT VERIFY','UNSUPPORTED','LIMIT EXCEEDED','UNREADABLE'])assert.equal(resultTitle({verdict}),"Couldn't check this file");
 assert.equal(resultTitle({verdict:'UNTRUSTED SIGNER',signerStatus:'unknown'}),'Unknown signer');
});
test('revoked banner never displays its configured signer identity',()=>{
 const r={verdict:'REVOKED KEY',signerStatus:'revoked',signerDisplayName:'Neer',signerName:'Neer',revocation:{reason:'TEST ONLY revoked',revokedAt:'2026-10-28T00:00:00Z'}};
 assert.doesNotMatch(resultTitle(r)+' '+signerSummary(r),/Neer/);assert.match(signerSummary(r),/Do not rely on this file/);
});
test('ownership-unconfirmed legacy key has a neutral label and unchanged revocation',async()=>{
 const keys=JSON.parse(await readFile(new URL('../src/trusted-keys.json',import.meta.url))),published=JSON.parse(await readFile(new URL('../.well-known/guard-signers.json',import.meta.url)));
 assert.deepEqual(keys,published);
 for(const entry of keys.signers.filter(s=>s.revoked))assert.doesNotMatch(entry.name,/\bNeer\b/i);
 const legacy=keys.signers.find(s=>s.key_id==='008c06e446c0e983');assert.equal(legacy.name,'Legacy viewer key (ownership unconfirmed)');assert.equal(legacy.revoked,true);assert.equal(legacy.revokedAt,'2026-10-28T16:07:50Z');
});
test('fresh-clone QA failure explains the missing generated prerequisite',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'guard-qa-prereq-'));
 try{await mkdir(join(dir,'scripts'));await cp(new URL('../src/',import.meta.url),join(dir,'src'),{recursive:true});await cp(new URL('../scripts/v4-browser-qa.mjs',import.meta.url),join(dir,'scripts/v4-browser-qa.mjs'));await writeFile(join(dir,'package.json'),'{"type":"module"}');const r=spawnSync(process.execPath,[join(dir,'scripts/v4-browser-qa.mjs')],{encoding:'utf8'});assert.equal(r.status,1);assert.match(r.stderr,/Run python3 scripts\/make-trust-bundle-vectors.py first/);assert.doesNotMatch(r.stderr,/ENOENT|at async/);}finally{await rm(dir,{recursive:true,force:true});}
});
