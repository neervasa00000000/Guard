// SPDX-License-Identifier: MIT
// Public registry administration only; never accepts or writes a private key.
import {readFile,writeFile,mkdir,rename as renameFile} from 'node:fs/promises';
import {realpathSync} from 'node:fs';
import {createPublicKey,createHash} from 'node:crypto';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {join} from 'node:path';
import {validateTrustedKeys} from '../src/verifier.js';
export async function updateSignerRegistry({root=fileURLToPath(new URL('../',import.meta.url)),publicPem,name,revoke,reason,at,rename=false,now=new Date().toISOString().replace(/\.\d{3}Z$/,'Z')}) {
 const source=join(root,'src/trusted-keys.json'),published=join(root,'.well-known/guard-signers.json'),policyPath=join(root,'src/trust-policy.json');
 const keys=JSON.parse(await readFile(source,'utf8')),policy=JSON.parse(await readFile(policyPath,'utf8'));validateTrustedKeys(keys);
 if(publicPem && revoke || !publicPem && !revoke)throw Error('Choose --public or --revoke');
 if(typeof rename!=='boolean'||rename&&!publicPem)throw Error('--rename is only valid with --public');
 let entry;
 if(publicPem){
  if(publicPem.includes('PRIVATE KEY'))throw Error('Refusing: this is a private key. Pass the public key only.');
  if(typeof name!=='string'||!name.trim()||name.length>120)throw Error('Supply a signer name (1..120 characters)');
  const key=createPublicKey(publicPem);if(key.asymmetricKeyType!=='ed25519')throw Error('An Ed25519 PUBLIC key is required');
  const raw=key.export({type:'spki',format:'der'}).subarray(-32),fp=createHash('sha256').update(raw).digest('hex');entry=keys.signers.find(s=>s.fingerprint_sha256===fp);
  if(entry?.revoked || policy.revoked.some(r=>r.fingerprint===fp))throw Error('Refusing to reactivate a revoked key; rotate to a new key');
  if(entry&&entry.name!==name&&!rename)throw Error('Refusing to rename an existing signer without --rename');
  if(entry)entry.name=name;else {entry={key_id:fp.slice(0,16),public_key_hex:raw.toString('hex'),fingerprint_sha256:fp,name,alg:'Ed25519',revoked:false,revokedAt:null,reason:null};keys.signers.push(entry);}
 }else{
  if(!/^[0-9a-f]{64}$/.test(revoke)||typeof reason!=='string'||!reason.trim()||reason.length>512||typeof at!=='string'||!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(at)||at.startsWith('0000')||!Number.isFinite(Date.parse(at))||new Date(at).toISOString()!==at.replace('Z','.000Z'))throw Error('Supply a fingerprint, reason and exact UTC --at timestamp');
  entry=keys.signers.find(s=>s.fingerprint_sha256===revoke);if(!entry)throw Error('Signer not found');
  if(entry.revoked && (entry.revokedAt!==at||entry.reason!==reason))throw Error('Existing revocation is immutable; keep its original date and reason');
  Object.assign(entry,{revoked:true,revokedAt:at,reason});const row={fingerprint:revoke,reason,revokedAt:at};const old=policy.revoked.find(r=>r.fingerprint===revoke);if(old&&(old.revokedAt!==at||old.reason!==reason))throw Error('Revocation policy conflicts with registry');if(!old)policy.revoked.push(row);policy.version++;policy.asOf=now;
 }
 keys.asOf=now;validateTrustedKeys(keys);
 await mkdir(join(root,'.well-known'),{recursive:true});
 // Each replace is atomic. An interruption between files fails the build agreement check.
 for(const [path,doc] of [[source,keys],[published,keys],[policyPath,policy]]){const temp=path+'.tmp';await writeFile(temp,JSON.stringify(doc,null,2)+'\n',{flag:'wx',mode:0o644});await renameFile(temp,path);}
 return entry;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(realpathSync(process.argv[1])).href){
 try{const opts={};for(let i=2;i<process.argv.length;){const flag=process.argv[i++];if(flag==='--rename'){if(opts[flag])throw Error('Duplicate --rename');opts[flag]=true;continue;}const value=process.argv[i++];if(!['--public','--name','--revoke','--reason','--at'].includes(flag)||!value||value.startsWith('--')||opts[flag])throw Error('Usage: --public PUBLIC.pem --name NAME [--rename] | --revoke FINGERPRINT --reason REASON --at UTC');opts[flag]=value;}
  const entry=await updateSignerRegistry({publicPem:opts['--public']?await readFile(opts['--public'],'utf8'):undefined,name:opts['--name'],rename:opts['--rename']??false,revoke:opts['--revoke'],reason:opts['--reason'],at:opts['--at']});console.log(JSON.stringify({fingerprint:entry.fingerprint_sha256,name:entry.name,revoked:entry.revoked},null,2));
 }catch(error){console.error(error.message);process.exitCode=1;}
}
