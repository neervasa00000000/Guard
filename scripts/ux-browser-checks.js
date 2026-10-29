// SPDX-License-Identifier: MIT
// TEST ONLY. Appended inside the isolated QA viewer, never the production build.
const uxButton=el('button','Run redesign acceptance checks');uxButton.id='qa-redesign';qaPanel.insertBefore(uxButton,$('qa-results'));
const uxLayoutButton=el('button','Measure current view');uxLayoutButton.id='qa-layout';qaPanel.insertBefore(uxLayoutButton,$('qa-results'));
function uxVisible(node){const r=node.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(node).visibility!=='hidden';}
function uxMetrics(){
 const saved=qaPanel.hidden;qaPanel.hidden=true;
 const text=document.body.innerText.trim(),controls=Array.from(document.querySelectorAll('button,a,input,summary')).filter(uxVisible),wordCount=text.split(/\s+/).filter(Boolean).length;
 const title=$('verdict-title'),download=$('download-plain'),image=$('image-panel');
 const visibleText=(root)=>{const walk=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let n,words=[];while(n=walk.nextNode()){const p=n.parentElement;if(p&&!p.closest('.sr-only,.skip,script,style')&&uxVisible(p))words.push(n.textContent);}return words.join(' ').trim().split(/\s+/).filter(Boolean).length;};
 let aboveImageWords=0;for(const node of [document.querySelector('header'),document.querySelector('.workspace-tabs'),$('verdict-banner')])aboveImageWords+=visibleText(node);
 const result={width:innerWidth,height:innerHeight,words:wordCount,visibleControls:controls.length,scrollHeight:document.documentElement.scrollHeight,noVerticalScroll:document.documentElement.scrollHeight<=innerHeight+1,noHorizontalScroll:document.documentElement.scrollWidth<=innerWidth,aboveImageWords:!$('result').hidden?aboveImageWords:null,resultButtons:Array.from($('result').querySelectorAll('button')).filter(uxVisible).length,titleTop:!$('result').hidden?title.getBoundingClientRect().top:null,plainVisible:uxVisible(download)&&download.getBoundingClientRect().bottom<=innerHeight,detailsClosed:!$('verification-technical').open,overflow:document.documentElement.scrollWidth>innerWidth?Array.from(document.querySelectorAll('body *')).filter(uxVisible).map(n=>({id:n.id,tag:n.tagName,cls:n.className,width:n.getBoundingClientRect().width,right:n.getBoundingClientRect().right,font:getComputedStyle(n).fontSize})).filter(r=>r.right>innerWidth+1).slice(0,15):[],httpResources:performance.getEntriesByType('resource').filter(r=>/^https?:/.test(r.name)).length};qaPanel.hidden=saved;return result;
}
$('qa-layout').onclick=()=>{const text=JSON.stringify(uxMetrics(),null,2);$('qa-results').textContent=text;return text;};
async function uxPrepare(state){
 qaPanel.hidden=false;workspaceMode('verify');
 if(state==='landing'){reset();$('drop').blur();}
 else if(state==='seal'){workspaceMode('seal');$('convert-input').files=new DataTransfer().files;await $('convert-input').onchange();}
 else if(state==='advanced'){showGuardView('#advanced',false);}
 else if(state==='about')showGuardView('#about',false);
 else if(state==='seal-edit'){
  workspaceMode('seal');const dt=new DataTransfer();dt.items.add(new File([Uint8Array.from(atob(QA_IMAGES.id),c=>c.charCodeAt(0))],'TEST ONLY ID shape.png',{type:'image/png'}));$('convert-input').files=dt.files;await $('convert-input').onchange();
  $('rect-x').value='128';$('rect-y').value='240';$('rect-width').value='192';$('rect-height').value='176';$('select-rectangle').onclick();
 }else if(state==='example')await $('try-redaction').onclick();
 else if(state==='notgrd')await openFile(new File([Uint8Array.from(atob(QA_IMAGES.square),c=>c.charCodeAt(0))],'picture.png'));
 else if(state==='fault')await openFile({name:'TEST ONLY oversized.GRD',size:GRD3_LIMITS.bytes+1,arrayBuffer(){throw Error('Limit must be checked before reading');}});
 else await qaLoad(({genuine:'photo',redacted:'photoRedacted',revoked:'photo'})[state]||state);
 if(!$('image-panel').hidden&&bitmap){if(!$('shield').hidden)showImage();if(currentReport.signerStatus!=='unknown')setMode(false);draw();}
 $('verification-technical').open=false;
 qaPanel.hidden=true;
 window.scrollTo(0,0);
 await new Promise(resolve=>requestAnimationFrame(resolve));
 document.documentElement.dataset.uxReady=state;
 return uxMetrics();
}
$('qa-redesign').onclick=async()=>{
 const rows=[],check=(name,ok)=>{rows.push({name,pass:!!ok});if(!ok)throw Error(name);},originalDownload=download,downloads=[];
 download=(bytes,name,type)=>downloads.push({bytes:typeof bytes==='string'?new TextEncoder().encode(bytes):new Uint8Array(bytes),name,type});
 const fileInput=(id,file)=>{const dt=new DataTransfer();dt.items.add(file);$(id).files=dt.files;};
 try{
  reset();workspaceMode('seal');lockOfflineSigner();
  fileInput('convert-input',new File([Uint8Array.from(atob(QA_IMAGES.id),c=>c.charCodeAt(0))],'TEST ONLY ID.png',{type:'image/png'}));await $('convert-input').onchange();
  check('ID warning and consent gate',!$('document-warning').hidden&&$('convert-submit').disabled&&!$('convert-privacy').checked);
  $('rect-x').value='128';$('rect-y').value='240';$('rect-width').value='192';$('rect-height').value='176';$('select-rectangle').onclick();
  check('numbered area preview rounds correctly',sealAreas.length===1&&sealAreas[0].x===128&&sealAreas[0].y===240&&sealAreas[0].width===192&&sealAreas[0].height===176);
  check('no original download before consent',downloads.length===0&&!$('save-original').checked);
  $('convert-privacy').checked=true;syncSealConsent();await $('convert-form').onsubmit(new Event('submit',{cancelable:true}));
  check('exactly one default download',downloads.length===1&&downloads[0].name==='image.GRD');
  let r=await verifyGRD2(downloads[0].bytes,TRUSTED,TRUST_POLICY);check('redacted self-signed output keeps identity semantics',r.verdict==='UNVERIFIED: SELF-SIGNED'&&r.regionVerified&&r.hiddenPixelsCleared&&r.redactionMap.length>0);
  const pixels=await decodeRgbPng(containerImage(r.container));let zero=true;for(let y=240;y<416;y++)for(let x=128;x<320;x++){const i=(y*pixels.width+x)*3;if(pixels.rgb[i]||pixels.rgb[i+1]||pixels.rgb[i+2])zero=false;}
  check('all selected output pixels are black',zero);check('Check this file offered without opening unblacked input',!$('check-sealed').hidden&&lastSealedFile?.name==='image.GRD');
  $('save-original').checked=true;$('save-original').dispatchEvent(new Event('change'));check('enabled full-original copy stays signposted',$('seal-extras-label').textContent.includes('original copy enabled'));await $('convert-form').onsubmit(new Event('submit',{cancelable:true}));check('full original only after explicit opt-in',downloads.length===3&&downloads[2].name==='private-original.GRD'&&(await verifyGRD2(downloads[2].bytes,TRUSTED,TRUST_POLICY)).redactionMap.length===0);
  downloads.length=0;workspaceMode('seal');
  fileInput('convert-input',new File([Uint8Array.from(atob(QA_CASES.photoRedacted),c=>c.charCodeAt(0))],'received.GRD'));await $('convert-input').onchange();
  const originalKey=sealSourceDoc.manifest.publicKey,originalSignature=sealSourceDoc.signature;
  check('received signed file opens without a key',!!sealSourceDoc&&!unlockedSigner&&!$('convert-preview').hidden);
  $('rect-x').value='160';$('rect-y').value='32';$('rect-width').value='32';$('rect-height').value='32';$('select-rectangle').onclick();$('convert-privacy').checked=true;syncSealConsent();await $('convert-form').onsubmit(new Event('submit',{cancelable:true}));
  r=await verifyGRD2(downloads[0].bytes,TRUSTED,TRUST_POLICY);check('key-free received GRD stays under original signer',downloads.length===1&&r.verdict==='VERIFIED WITH REDACTIONS'&&r.container.manifest.publicKey===originalKey&&r.container.signature===originalSignature);
  await openFile(lastSealedFile);check('hidden areas have plain labels',$('hidden-areas').textContent.includes('Hidden 1:')&&$('hidden-areas').children.length===mergedHiddenAreas(r).length);
  const png=await exportPlainImage(currentContainer);check('plain export is PNG without GRD carrier',png[0]===137&&png[1]===80&&png[2]===78&&png[3]===71&&!new TextDecoder().decode(png).includes('GRD2\n'));
  await qaLoad('tampered');await $('show-unknown').onclick();check('changed file cannot reveal or download',$('image-panel').hidden&&$('download-plain').hidden);
  await qaLoad('unknown');const before=currentReport.verdict;await $('show-unknown').onclick();check('explicit unknown preview keeps verdict and hold-to-reveal',currentReport.verdict===before&&unknownApproved&&reveal&&!$('image-panel').hidden);
  await openFile({name:'TEST ONLY large.GRD',size:GRD3_LIMITS.bytes+1});check('operational limit is grey and not called tampering',$('verdict-banner').classList.contains('fault')&&$('verdict-description').textContent.includes('not a sign of tampering')&&$('image-panel').hidden&&$('download-plain').hidden);
  showGuardView('#advanced',false);check('all expert forms reachable',[$('signer-setup'),$('person-form'),$('trust-form'),$('copy-form'),$('download-report'),$('viewing-options'),$('download-viewer')].every(n=>$('advanced').contains(n)));
  showGuardView('#about',false);check('privacy text and example remain reachable',$('about').contains($('privacy-details'))&&$('about').contains($('try-redaction'))&&$('privacy-details').textContent.includes('Effective 29 October 2026'));
  check('runtime has no HTTP resource loads after initial document',performance.getEntriesByType('resource').filter(r=>/^https?:/.test(r.name)).length===0);
  qaPanel.hidden=false;$('qa-results').textContent=JSON.stringify({result:'ALL PASS',rows},null,2);
 }catch(error){qaPanel.hidden=false;$('qa-results').textContent=JSON.stringify({result:'FAIL',message:error.message,rows},null,2);}
 finally{download=originalDownload;lockOfflineSigner();}
};
const uxRevokedButton=el('button','Run revoked guard check');uxRevokedButton.id='qa-revoked';qaPanel.insertBefore(uxRevokedButton,$('qa-results'));
$('qa-revoked').onclick=async()=>{await qaLoad('photo');await $('show-unknown').onclick();await $('redact-checked').onclick();const editBlocked=$('redact-checked').disabled&&!conversionImage;qaPanel.hidden=true;const audit=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']}});qaPanel.hidden=false;const result={pass:currentReport.signerStatus==='revoked'&&$('image-panel').hidden&&$('download-plain').hidden&&editBlocked,editBlocked,verdict:currentReport.verdict,violations:audit.violations.map(v=>({id:v.id,impact:v.impact}))};$('qa-results').textContent=JSON.stringify(result,null,2);return result;};
const snapshot=new URLSearchParams(location.search).get('ux-state');
if(snapshot&&['landing','genuine','redacted','tampered','unknown','self','fully','revoked','example','fault','notgrd','seal','seal-edit','advanced','about'].includes(snapshot))void uxPrepare(snapshot);
const uxSelect=document.createElement('select');uxSelect.id='qa-state';uxSelect.setAttribute('aria-label','QA view');for(const state of ['landing','genuine','redacted','tampered','unknown','self','fully','example','fault','notgrd','seal','seal-edit','advanced','about']){const option=el('option',state);option.value=state;uxSelect.append(option);}qaPanel.insertBefore(uxSelect,$('qa-results'));
const uxPrepareButton=el('button','Prepare QA view');uxPrepareButton.id='qa-prepare';uxPrepareButton.onclick=()=>uxPrepare(uxSelect.value);qaPanel.insertBefore(uxPrepareButton,$('qa-results'));
const uxTextButton=el('button','Probe 200% text');uxTextButton.id='qa-text';qaPanel.insertBefore(uxTextButton,$('qa-results'));
uxTextButton.onclick=async()=>{const sizes=Array.from(document.querySelectorAll('body,body *')).filter(n=>!['SCRIPT','STYLE'].includes(n.tagName)).map(n=>[n,parseFloat(getComputedStyle(n).fontSize)]);for(const [n,size] of sizes)if(Number.isFinite(size))n.style.fontSize=(size*2)+'px';await new Promise(resolve=>requestAnimationFrame(resolve));return uxMetrics();};
// Explicit completion markers let UI automation wait for the real async handler.
for(const id of ['qa-signers','qa-advanced','qa-offline','qa-axe','qa-ux','qa-redesign','qa-revoked']){const run=$(id).onclick;$(id).onclick=async(...args)=>{$('qa-results').removeAttribute('data-complete');try{return await run(...args);}finally{$('qa-results').dataset.complete='1';}};}
const blackoutFixButton=el('button','Run blackout discovery checks');blackoutFixButton.id='qa-blackout-fix';qaPanel.insertBefore(blackoutFixButton,$('qa-results'));
blackoutFixButton.onclick=async()=>{
 const rows=[],check=(name,ok)=>{rows.push({name,pass:!!ok});if(!ok)throw Error(name);},oldDownload=download,files=[];
 download=(bytes,name)=>files.push({bytes:new Uint8Array(bytes),name});
 const waitEditor=async name=>{for(let i=0;i<300;i++){if(conversionImage?.name===name&&!$('convert-preview').hidden)return;await new Promise(resolve=>requestAnimationFrame(resolve));}throw Error('Dropped image did not reach editor');};
 try{
  workspaceMode('seal');const picture=new File([Uint8Array.from(atob(QA_IMAGES.square),c=>c.charCodeAt(0))],'TEST ONLY drop.png',{type:'image/png'}),dt=new DataTransfer();dt.items.add(picture);const version=conversionVersion;
  $('convert').dispatchEvent(new DragEvent('drop',{dataTransfer:dt,bubbles:true,cancelable:true}));await waitEditor(picture.name);
  check('dropping picture in editor opens editor once',!$('convert').hidden&&conversionVersion===version+1&&files.length===0);
  await qaLoad('photo');check('blackout button beside picture',!$('redact-checked').disabled&&$('image-panel').contains($('redact-checked')));
  $('hide-image').onclick();check('Hide preview immediately shields picture',!$('shield').hidden);$('show-image').onclick();
  const originalKey=currentContainer.manifest.publicKey;await $('redact-checked').onclick();check('checked file goes straight to editor',!$('convert').hidden&&sealSourceDoc?.manifest.publicKey===originalKey&&$('convert-input').files.length===1);
  $('rect-x').value='16';$('rect-y').value='16';$('rect-width').value='32';$('rect-height').value='32';$('select-rectangle').onclick();$('convert-privacy').checked=true;syncSealConsent();await $('convert-form').onsubmit(new Event('submit',{cancelable:true}));
  let r=await verifyGRD2(files.at(-1).bytes,TRUSTED,TRUST_POLICY);check('direct edit exports original-signer blackouts',r.verdict==='VERIFIED WITH REDACTIONS'&&r.container.manifest.publicKey===originalKey);
  await qaLoad('unknown');check('unknown file not editable before opt-in',$('redact-checked').disabled);await $('redact-checked').onclick();check('forced edit cannot bypass unknown withholding',$('convert').hidden&&$('image-panel').hidden);
  await $('show-unknown').onclick();check('explicit preview enables blackout action',!$('redact-checked').disabled&&reveal&&currentReport.signerStatus==='unknown');await $('redact-checked').onclick();
  check('approved unknown edit stays clearly unknown',!$('convert').hidden&&sealUnknownApproved&&$('seal-signer-summary').textContent.includes('unknown'));
  $('rect-x').value='0';$('rect-y').value='0';$('rect-width').value='32';$('rect-height').value='32';$('select-rectangle').onclick();$('convert-privacy').checked=true;syncSealConsent();await $('convert-form').onsubmit(new Event('submit',{cancelable:true}));
  r=await verifyGRD2(files.at(-1).bytes,[],TRUST_POLICY);check('unknown blackout output never becomes verified',r.verdict==='UNTRUSTED SIGNER'&&!r.genuine&&!r.viewable&&r.redactionMap.length>0);
  await qaLoad('tampered');await $('redact-checked').onclick();check('changed file cannot enter blackout editor',$('convert').hidden&&$('image-panel').hidden&&$('download-plain').hidden);
  const next=new File([Uint8Array.from(atob(QA_IMAGES.square),c=>c.charCodeAt(0))],'TEST ONLY check drop.png',{type:'image/png'}),data=new DataTransfer();data.items.add(next);document.body.dispatchEvent(new DragEvent('drop',{dataTransfer:data,bubbles:true,cancelable:true}));await waitEditor(next.name);
  check('dropping ordinary picture on Check routes to editor',!$('convert').hidden&&sealSourceDoc===null);
  $('qa-results').textContent=JSON.stringify({result:'ALL PASS',rows},null,2);
 }catch(error){$('qa-results').textContent=JSON.stringify({result:'FAIL',message:error.message,rows},null,2);}
 finally{download=oldDownload;$('qa-results').dataset.complete='1';}
};
