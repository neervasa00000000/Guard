// SPDX-License-Identifier: MIT
// Fixed-cost, versioned password envelope. No private material enters storage.
const SIGNER_AAD = new TextEncoder().encode('Guard encrypted signer v1');
const SIGNER_ROUNDS = 600000;
function signerHex(bytes) { return Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join(''); }
function signerUnhex(s) { if(typeof s!=='string'||!/^[a-f0-9]{64}$/.test(s))throw Error('Invalid public key.');return Uint8Array.from(s.match(/../g),b=>parseInt(b,16)); }
function signerB64(bytes) { return btoa(String.fromCharCode(...new Uint8Array(bytes))); }
function signerDecode(s, max=2048) { if(typeof s!=='string'||s.length>max||!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(s))throw Error('Invalid key file.');return Uint8Array.from(atob(s),c=>c.charCodeAt(0)); }
function signerObject(s, keys) { if(!s||typeof s!=='object'||Array.isArray(s)||Object.keys(s).sort().join()!==keys.sort().join())throw Error('Invalid key file.'); }
function signerJson(text) { if(typeof text!=='string'||text.length>16384)throw Error('Choose a Guard key file up to 16 KiB.');return JSON.parse(text); }
function signerName(name) { if(typeof name!=='string'||!name.trim()||name.trim().length>80||/[\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/u.test(name))throw Error('Enter a name of 1–80 characters, without control characters.');return name.trim(); }
function signerPassword(password) { if(typeof password!=='string'||password.length<12||password.length>1024)throw Error('Use a password of 12–1024 characters.'); }
async function signerWrappingKey(password,salt) {
  signerPassword(password);
  const material=await crypto.subtle.importKey('raw',new TextEncoder().encode(password),'PBKDF2',false,['deriveKey']);
  return crypto.subtle.deriveKey({name:'PBKDF2',hash:'SHA-256',iterations:SIGNER_ROUNDS,salt},material,{name:'AES-GCM',length:256},false,['encrypt','decrypt']);
}
export async function signerContact(publicKey,name) {
  const raw=typeof publicKey==='string'?signerUnhex(publicKey):new Uint8Array(publicKey);
  if(raw.length!==32)throw Error('Invalid public key.');
  return {format:'Guard public signer',version:1,name:signerName(name),publicKey:signerHex(raw),fingerprint:signerHex(new Uint8Array(await crypto.subtle.digest('SHA-256',raw)))};
}
export async function readSignerContact(text) {
  const c=signerJson(text);signerObject(c,['format','version','name','publicKey','fingerprint']);
  if(c.format!=='Guard public signer'||c.version!==1)throw Error('Choose a Guard public signer file, never a private key.');
  const expected=await signerContact(c.publicKey,c.name);
  if(c.fingerprint!==expected.fingerprint)throw Error('Public fingerprint does not match the key.');
  return expected;
}
export async function createOfflineSigner(name,password) {
  name=signerName(name);signerPassword(password);
  const pair=await crypto.subtle.generateKey('Ed25519',true,['sign','verify']);
  const raw=new Uint8Array(await crypto.subtle.exportKey('raw',pair.publicKey));
  const secret=new Uint8Array(await crypto.subtle.exportKey('pkcs8',pair.privateKey));
  const salt=crypto.getRandomValues(new Uint8Array(16)),iv=crypto.getRandomValues(new Uint8Array(12));
  const payload=new TextEncoder().encode(JSON.stringify({name,publicKey:signerHex(raw),pkcs8:signerB64(secret)}));
  try {
    const key=await signerWrappingKey(password,salt);
    const encrypted=await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:SIGNER_AAD,tagLength:128},key,payload);
    const envelope={format:'Guard encrypted signer',version:1,kdf:'PBKDF2-SHA256',iterations:SIGNER_ROUNDS,cipher:'AES-256-GCM',salt:signerB64(salt),iv:signerB64(iv),data:signerB64(encrypted)};
    // Return only the encrypted backup. The UI unlocks this exact file before use.
    return JSON.stringify(envelope);
  } finally { secret.fill(0);payload.fill(0); }
}
export async function unlockOfflineSigner(text,password) {
  const e=signerJson(text);signerObject(e,['format','version','kdf','iterations','cipher','salt','iv','data']);
  if(e.format!=='Guard encrypted signer'||e.version!==1||e.kdf!=='PBKDF2-SHA256'||e.iterations!==SIGNER_ROUNDS||e.cipher!=='AES-256-GCM')throw Error('Unsupported signer key file.');
  const salt=signerDecode(e.salt),iv=signerDecode(e.iv),data=signerDecode(e.data);
  if(salt.length!==16||iv.length!==12||data.length<16)throw Error('Invalid key file.');
  let plain;
  try {
    const key=await signerWrappingKey(password,salt);
    plain=new Uint8Array(await crypto.subtle.decrypt({name:'AES-GCM',iv,additionalData:SIGNER_AAD,tagLength:128},key,data));
  } catch { throw Error('Could not unlock. Check your password and key file.'); }
  let secret;
  try {
    const p=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(plain));signerObject(p,['name','publicKey','pkcs8']);
    const contact=await signerContact(p.publicKey,p.name);secret=signerDecode(p.pkcs8);
    const privateKey=await crypto.subtle.importKey('pkcs8',secret,'Ed25519',false,['sign']);
    const publicKey=await crypto.subtle.importKey('raw',signerUnhex(contact.publicKey),'Ed25519',false,['verify']);
    const challenge=crypto.getRandomValues(new Uint8Array(32));
    if(!await crypto.subtle.verify('Ed25519',publicKey,await crypto.subtle.sign('Ed25519',privateKey,challenge),challenge))throw Error('Key pair does not match.');
    return {contact,privateKey,publicKey:signerUnhex(contact.publicKey)};
  } finally { plain.fill(0);secret?.fill(0); }
}
