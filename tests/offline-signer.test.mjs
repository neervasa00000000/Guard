import test from 'node:test';
import assert from 'node:assert/strict';
import {createOfflineSigner,unlockOfflineSigner,readSignerContact} from '../src/offline-signer.js';
import {sealRgba,encodeGRD2,verifyGRD2} from '../src/redactable.js';
const password='TEST ONLY long password 123!';
let backup,signer;
test('encrypted backup round-trips without exposing name or private material; unlocked key cannot export',async()=>{
  backup=await createOfflineSigner('TEST ONLY Offline Signer',password);
  assert(!backup.includes('TEST ONLY Offline Signer'));assert(!backup.includes('pkcs8'));
  signer=await unlockOfflineSigner(backup,password);
  assert.equal(signer.contact.name,'TEST ONLY Offline Signer');assert.equal(signer.privateKey.extractable,false);
  await assert.rejects(crypto.subtle.exportKey('pkcs8',signer.privateKey));
  const again=await unlockOfflineSigner(backup,password);assert.equal(again.contact.fingerprint,signer.contact.fingerprint);
  assert.deepEqual(await readSignerContact(JSON.stringify(signer.contact)),signer.contact);
});
test('wrong password and encrypted-body, nonce or salt edits fail closed',async()=>{
  await assert.rejects(unlockOfflineSigner(backup,'Wrong password 12345!'),/Could not unlock/);
  for(const field of ['data','iv','salt']){const e=JSON.parse(backup),raw=Buffer.from(e[field],'base64');raw[0]^=1;e[field]=raw.toString('base64');await assert.rejects(unlockOfflineSigner(JSON.stringify(e),password));}
});
test('malicious KDF cost, schema, oversized input, and unsupported version rejected',async()=>{
  for(const change of [{iterations:1},{iterations:999999999},{version:2},{cipher:'AES-CBC'},{extra:true},{data:'!'}])await assert.rejects(unlockOfflineSigner(JSON.stringify({...JSON.parse(backup),...change}),password));
  await assert.rejects(unlockOfflineSigner(' '.repeat(16385),password));
  await assert.rejects(createOfflineSigner('Neer','short'),/12/);
  await assert.rejects(createOfflineSigner('\u202eFake',password),/control/);
});
test('public contact rejects private envelopes, fingerprint substitutions, private fields and control characters',async()=>{
  await assert.rejects(readSignerContact(backup));
  for(const change of [{fingerprint:'0'.repeat(64)},{privateKey:'secret'},{name:'\u0000bad'},{version:2}])await assert.rejects(readSignerContact(JSON.stringify({...signer.contact,...change})));
});
test('offline-issued asset is unknown until explicitly trusted; revocation wins, personal remains self-signed',async()=>{
  const options={rgba:new Uint8Array(64*64*4).fill(255),width:64,height:64,publicKey:signer.publicKey,sign:b=>crypto.subtle.sign('Ed25519',signer.privateKey,b),label:signer.contact.name};
  const bytes=encodeGRD2(await sealRgba(options));
  const unknown=await verifyGRD2(bytes,[]);assert.equal(unknown.signerStatus,'unknown');assert(!unknown.genuine);assert(!unknown.viewable);
  const anchors=[{public_key_hex:signer.contact.publicKey,name:signer.contact.name}];
  const trusted=await verifyGRD2(bytes,anchors);assert.equal(trusted.verdict,'GENUINE');assert.equal(trusted.signerDisplayName,signer.contact.name);
  const policy={version:1,asOf:'2026-10-29T00:00:00Z',revoked:[{fingerprint:signer.contact.fingerprint,revokedAt:'2026-10-29T00:00:00Z',reason:'TEST ONLY'}]};
  const revoked=await verifyGRD2(bytes,anchors,policy);assert.equal(revoked.signerStatus,'revoked');assert(!revoked.viewable);
  const personal=await verifyGRD2(encodeGRD2(await sealRgba({...options,purpose:'personal'})),anchors);assert.equal(personal.verdict,'UNVERIFIED: SELF-SIGNED');
});
test('each saved signer has a fresh identity and envelope randomness',async()=>{
  const other=await createOfflineSigner('TEST ONLY Offline Signer',password);
  const otherSigner=await unlockOfflineSigner(other,password);assert.notEqual(otherSigner.contact.fingerprint,signer.contact.fingerprint);
  assert.notEqual(JSON.parse(other).salt,JSON.parse(backup).salt);assert.notEqual(JSON.parse(other).iv,JSON.parse(backup).iv);
});
test('an authenticated envelope still rejects mismatched private and public keys',async()=>{
  const e=JSON.parse(backup),salt=Buffer.from(e.salt,'base64'),iv=Buffer.from(e.iv,'base64');
  const material=await crypto.subtle.importKey('raw',new TextEncoder().encode(password),'PBKDF2',false,['deriveKey']);
  const key=await crypto.subtle.deriveKey({name:'PBKDF2',hash:'SHA-256',iterations:600000,salt},material,{name:'AES-GCM',length:256},false,['encrypt','decrypt']);
  const params={name:'AES-GCM',iv,additionalData:new TextEncoder().encode('Guard encrypted signer v1'),tagLength:128};
  const plain=JSON.parse(new TextDecoder().decode(await crypto.subtle.decrypt(params,key,Buffer.from(e.data,'base64'))));
  // TEST ONLY: construct a validly encrypted but inconsistent envelope.
  plain.publicKey='0'.repeat(64);
  e.data=Buffer.from(await crypto.subtle.encrypt(params,key,new TextEncoder().encode(JSON.stringify(plain)))).toString('base64');
  await assert.rejects(unlockOfflineSigner(JSON.stringify(e),password));
});
