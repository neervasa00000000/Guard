// SPDX-License-Identifier: MIT
let unlockedSigner=null,offlineSignerVersion=0,signerBusy=false,personTrustEpoch=0;
const personTrust=new Map();
function lockOfflineSigner(message='Signer locked. Unlock your saved key to sign again.') {
  offlineSignerVersion++;unlockedSigner=null;
  $('signer-active').hidden=true;$('signer-identity').textContent='';
  $('seal-signer-summary').textContent='Signed with a one-time key, so people will see “Unknown signer”.';
  $('signer-status').textContent=message;refreshSealSummary();
}
function activateOfflineSigner(signer) {
  unlockedSigner=signer;$('signer-active').hidden=false;
  $('signer-identity').textContent=signer.contact.name+' · SHA-256 '+signer.contact.fingerprint;
  $('seal-signer-summary').textContent='Signed with '+signer.contact.name+'’s key. People must trust it before it shows as Genuine.';
  $('signer-status').textContent='Signer unlocked for this page. Save your public signer file to share with recipients.';refreshSealSummary();
}
async function signerAction(event,kind) {
  event.preventDefault();if(signerBusy)return;
  const form=$(kind==='create'?'signer-create':'signer-unlock');
  if(!form.reportValidity())return;
  if(kind==='create'&&$('signer-password').value!==$('signer-confirm').value){$('signer-status').textContent='Passwords do not match. Repeat the same password.';$('signer-confirm').focus();return;}
  signerBusy=true;lockOfflineSigner('Working locally…');const epoch=offlineSignerVersion;
  $('signer-create-submit').disabled=true;$('signer-unlock-submit').disabled=true;form.setAttribute('aria-busy','true');
  try {
    let text,password;
    if(kind==='create'){
      password=$('signer-password').value;text=await createOfflineSigner($('signer-name').value,password);
    }else{
      const file=$('signer-file').files[0];if(!file||file.size>16384)throw Error('Choose a .guardkey file up to 16 KiB.');
      text=await file.text();password=$('signer-unlock-password').value;
    }
    const signer=await unlockOfflineSigner(text,password);
    if(epoch!==offlineSignerVersion)return;
    const trust=await sessionTrust();
    if((await checkRevocation(signer.publicKey,trust.policy)).revoked)throw Error('This key is revoked. Create a new signer.');
    if(epoch!==offlineSignerVersion)return;
    if(kind==='create')download(new TextEncoder().encode(text),'signer.guardkey','application/json');
    activateOfflineSigner(signer);
    if(kind==='create')$('signer-status').textContent='Encrypted key download requested. Keep the saved file and a backup; your password cannot be recovered. Signer unlocked for this page.';
  }catch(error){if(epoch===offlineSignerVersion)$('signer-status').textContent=error.message;}
  finally{
    for(const id of ['signer-password','signer-confirm','signer-unlock-password'])$(id).value='';
    signerBusy=false;$('signer-create-submit').disabled=false;$('signer-unlock-submit').disabled=false;form.removeAttribute('aria-busy');
  }
}
$('signer-create').onsubmit=e=>signerAction(e,'create');
$('signer-unlock').onsubmit=e=>signerAction(e,'unlock');
$('signer-lock').onclick=()=>lockOfflineSigner();
window.addEventListener('pagehide',()=>lockOfflineSigner());
$('signer-public').onclick=()=>{if(unlockedSigner)download(new TextEncoder().encode(JSON.stringify(unlockedSigner.contact,null,2)),'public.guardsigner','application/json');};
$('person-file').onchange=async()=>{
  personTrustEpoch++;
  $('person-fingerprint').value='';$('person-preview').textContent='';
  const file=$('person-file').files[0];
  try{if(!file||file.size>16384)throw Error('Choose a public signer file up to 16 KiB.');const c=await readSignerContact(await file.text());if($('person-file').files[0]!==file)return;$('person-preview').textContent='Claimed name: '+c.name+' · SHA-256 '+c.fingerprint;}
  catch(error){$('person-preview').textContent=error.message;}
};
$('person-form').onsubmit=async event=>{
  event.preventDefault();if($('person-submit').disabled||!$('person-form').reportValidity())return;
  $('person-submit').disabled=true;
  const epoch=++personTrustEpoch,trustEpoch=trustImportVersion;
  try{
    const file=$('person-file').files[0],confirmed=$('person-fingerprint').value.toLowerCase();
    if(!file||file.size>16384)throw Error('Choose a public signer file up to 16 KiB.');
    const c=await readSignerContact(await file.text());
    if(c.fingerprint!==confirmed)throw Error('Fingerprint does not match. Check it independently with this person.');
    const trust=await sessionTrust();
    if((await checkRevocation(signerUnhex(c.publicKey),trust.policy)).revoked)throw Error('This key is revoked and cannot be trusted.');
    if(epoch!==personTrustEpoch||trustEpoch!==trustImportVersion)throw Error('Trust changed during import. Check the file again.');
    if(trust.anchors.some(k=>k.public_key_hex===c.publicKey))throw Error('This key is already trusted. Its existing identity stays unchanged.');
    if(personTrust.size>=32)throw Error('This tab already trusts 32 people. Clear the list to start again.');
    personTrust.set(c.publicKey,{public_key_hex:c.publicKey,name:c.name,owner:c.name,alg:'Ed25519',key_id:c.fingerprint.slice(0,16),fingerprint_sha256:c.fingerprint});trustImportVersion++;reset();
    $('person-clear').hidden=false;$('person-trust-note').hidden=false;
    $('person-status').textContent='Trusted '+c.name+' for this tab. Choose their .GRD file again. Reloading clears this trust.';
  }catch(error){$('person-status').textContent=error.message;}
  finally{$('person-submit').disabled=false;}
};
$('person-clear').onclick=()=>{personTrustEpoch++;personTrust.clear();trustImportVersion++;reset();$('person-clear').hidden=true;$('person-trust-note').hidden=true;$('person-status').textContent='People cleared. Bundled signers and any signed trust bundle still apply.';};
