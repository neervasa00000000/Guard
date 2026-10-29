// SPDX-License-Identifier: MIT
// TEST ONLY: independent Python decryption / signature / GRD verification.
// Creates random test keys in memory; emits only public results.
import {execFileSync} from 'node:child_process';
import {createOfflineSigner,unlockOfflineSigner} from '../src/offline-signer.js';
import {sealRgba,encodeGRD2} from '../src/redactable.js';
const password='TEST ONLY interoperability password 123!';
const envelope=await createOfflineSigner('TEST ONLY interop signer',password);
const signer=await unlockOfflineSigner(envelope,password);
const asset=encodeGRD2(await sealRgba({rgba:new Uint8Array(64*64*4).fill(255),width:64,height:64,publicKey:signer.publicKey,label:signer.contact.name,sign:b=>crypto.subtle.sign('Ed25519',signer.privateKey,b)}));
const python=String.raw`
import sys,json,base64
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import grd
i=json.load(sys.stdin); e=json.loads(i['envelope']); b64=base64.b64decode
k=PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=b64(e['salt']),iterations=e['iterations']).derive(i['password'].encode())
p=json.loads(AESGCM(k).decrypt(b64(e['iv']),b64(e['data']),b'Guard encrypted signer v1'))
private=serialization.load_der_private_key(b64(p['pkcs8']),None)
public=private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex()
assert public==p['publicKey']==i['contact']['publicKey']
asset=b64(i['asset']); unknown=grd.verify(asset,[]); trusted=grd.verify(asset,[public])
assert unknown['verdict']=='UNTRUSTED SIGNER',unknown
assert trusted['verdict']=='GENUINE',trusted
print(json.dumps({'pythonDecryption':True,'publicKeyMatches':True,'unknownVerdict':unknown['verdict'],'trustedVerdict':trusted['verdict'],'signature':base64.b64encode(private.sign(b'Guard TEST ONLY interop')).decode()}))
`;
const result=JSON.parse(execFileSync(process.env.GUARD_TEST_PYTHON||'python3',['-c',python],{cwd:new URL('../',import.meta.url),input:JSON.stringify({envelope,password,contact:signer.contact,asset:Buffer.from(asset).toString('base64')}),encoding:'utf8'}));
const publicKey=await crypto.subtle.importKey('raw',signer.publicKey,'Ed25519',false,['verify']);
if(!await crypto.subtle.verify('Ed25519',publicKey,Buffer.from(result.signature,'base64'),new TextEncoder().encode('Guard TEST ONLY interop')))throw Error('Python signature failed WebCrypto verification');
delete result.signature;console.log(JSON.stringify({...result,webCryptoVerifiesPython:true},null,2));
