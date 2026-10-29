// SPDX-License-Identifier: MIT
// Generates isolated, visibly labelled QA viewers. NEVER deploy these copies.
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createPrivateKey,createPublicKey,sign} from 'node:crypto';
import {sealRgba,encodeGRD2,redactRects} from '../src/redactable.js';
const dir='/tmp/guard-v4-qa';
let bundleVectors;
try {bundleVectors=JSON.parse(await readFile(new URL('../results/trust-bundle-vectors.json',import.meta.url)));}
catch(error){if(error.code==='ENOENT'){console.error('Run python3 scripts/make-trust-bundle-vectors.py first');process.exit(1);}throw error;}
const vectors=JSON.parse(await readFile(new URL('../tests/vectors/signer-status-vectors.json',import.meta.url)));
await mkdir(dir,{recursive:true});
const seed=n=>createPrivateKey({key:Buffer.concat([Buffer.from('302e020100300506032b657004220420','hex'),Buffer.alloc(32,n)]),format:'der',type:'pkcs8'});
const keyB=seed(49),bundleIssuer=seed(44),rootKey=createPublicKey(seed(43)).export({type:'spki',format:'pem'});
const make=async key=>Buffer.from(encodeGRD2(await sealRgba({width:128,height:64,rgba:new Uint8Array(128*64*4).fill(255),publicKey:createPublicKey(key).export({type:'spki',format:'der'}).subarray(-32),sign:b=>sign(null,b,key)}))).toString('base64');
const genuine=vectors.cases.find(c=>c.id==='grd2-asset').container,parsed=JSON.parse(Buffer.from(genuine,'base64').subarray(5));parsed.manifest.label='TEST ONLY tamper';
const {canon}=await import('../src/verifier.js');
const photoKey=seed(48),photoDoc=await sealRgba({width:384,height:256,subTile:16,rgba:Uint8Array.from({length:384*256*4},(_,i)=>i%4===3?255:(Math.floor(i/4)%251)+1),publicKey:createPublicKey(photoKey).export({type:'spki',format:'der'}).subarray(-32),sign:b=>sign(null,b,photoKey)});
const photo=Buffer.from(encodeGRD2(photoDoc)).toString('base64'),photoRedacted=Buffer.from(await redactRects(photoDoc,[{x:32,y:32,width:96,height:80},{x:256,y:128,width:64,height:64}],{granularity:16})).toString('base64');
const fully=Buffer.from(await redactRects(photoDoc,[{x:0,y:0,width:384,height:256}],{granularity:16})).toString('base64');
const cases={photo,photoRedacted,fully,genuine,tampered:Buffer.from('GRD2\n'+canon(parsed)).toString('base64'),self:vectors.cases.find(c=>c.id==='grd2-personal').container,redact:vectors.cases.find(c=>c.id==='grd2-redacted').container,unknown:await make(keyB),bundle:await make(bundleIssuer)};
let html=await readFile(new URL('../index.html',import.meta.url),'utf8');const productionTrust=await readFile(new URL('../src/trusted-keys.json',import.meta.url),'utf8'),policy=await readFile(new URL('../src/trust-policy.json',import.meta.url),'utf8');
html=html.replace('const trustedData='+productionTrust+';','const trustedData='+JSON.stringify(vectors.keys)+';').replace('<title>Guard /','<title>TEST ONLY QA — Guard /');
const axe=(await readFile(new URL('../node_modules/axe-core/axe.min.js',import.meta.url),'utf8')).replaceAll('</script','<\\/script');html=html.replace('<script>','<script>'+axe+'</script><script>');
const {default:qaSharp}=await import('sharp');
const qaImages={id:(await qaSharp({create:{width:1012,height:638,channels:3,background:'#eee'}}).png().toBuffer()).toString('base64'),square:(await qaSharp({create:{width:1000,height:1000,channels:3,background:'#eee'}}).png().toBuffer()).toString('base64')};
const qaCode=`
const QA_REVOKED_KEY=${JSON.stringify(JSON.parse(productionTrust).signers.find(s=>s.revoked).public_key_hex)};
const QA_CASES=${JSON.stringify(cases)},QA_BUNDLES=${JSON.stringify(bundleVectors)},QA_ROOT=${JSON.stringify(rootKey)},QA_IMAGES=${JSON.stringify(qaImages)},QA_VISUAL=${JSON.stringify(vectors.visual)};
const qaPanel=document.createElement('section');qaPanel.setAttribute('aria-label','TEST ONLY QA controls');qaPanel.innerHTML='<h2>TEST ONLY QA controls</h2><button id="qa-signers">Run signer flow checks</button><button id="qa-advanced">Run advanced tools checks</button><button id="qa-offline">Run offline signer checks</button><button id="qa-axe">Run accessibility audit</button><button id="qa-ux">Run privacy and drop checks</button><button id="qa-redacted">Load redacted signer</button><button id="qa-self">Load self-signed file</button><button id="qa-unknown">Load unknown signer</button><button id="qa-genuine">Load trusted signer</button><pre id="qa-results" role="status" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre>';document.querySelector('main').append(qaPanel);
const qaLoad=kind=>openFile(new File([Uint8Array.from(atob(QA_CASES[kind]),c=>c.charCodeAt(0))],kind+'.GRD'));
$('qa-redacted').onclick=()=>qaLoad('redact');$('qa-self').onclick=()=>qaLoad('self');$('qa-unknown').onclick=()=>qaLoad('unknown');$('qa-genuine').onclick=()=>qaLoad('genuine');
function qaInputs(bundle){revealAdvancedTool('trust');for(const [id,file] of [['trust-bundle',new File([Uint8Array.from(atob(bundle),c=>c.charCodeAt(0))],'bundle.json')],['trust-root',new File([QA_ROOT],'root.pem')]]){const dt=new DataTransfer();dt.items.add(file);$(id).files=dt.files;}}
$('qa-signers').onclick=async()=>{const rows=[];const check=(name,ok)=>{rows.push({name,pass:!!ok});if(!ok)throw Error(name);};try{
 check('Advanced view hidden on load',$('advanced').hidden);
 await qaLoad('genuine');check('trusted title', $('verdict-title').textContent==='Genuine'&&$('verdict-signer').textContent.includes('Test Org (Tester)'));
 await qaLoad('self');check('personal remains self-signed', currentReport.signerStatus==='self'&&!currentReport.genuine);check('plain self title',$('verdict-title').textContent==='Unknown signer');
 await qaLoad('tampered');check('plain tampered title',$('verdict-title').textContent==='Changed');
 await qaLoad('redact');check('plain redaction title',$('verdict-title').textContent==='Genuine, with parts blacked out');check('redaction retains signer identity',$('verdict-signer').textContent.includes('Test Org (Tester)'));check('technical verdict retained',$('technical-verdict').textContent.includes('VERIFIED WITH REDACTIONS'));
 await qaLoad('unknown');check('unknown withheld by default',$('image-panel').hidden&&!$('show-unknown').hidden);await $('show-unknown').onclick();check('explicit unknown display preserves verdict',!$('image-panel').hidden&&currentReport.verdict==='UNTRUSTED SIGNER'&&!currentReport.genuine&&unknownApproved&&reveal);check('plain export enabled',!$('download-plain').hidden);
 showGuardView('#advanced',false);
 qaInputs(QA_BUNDLES.cases.find(c=>c.id==='valid').bundle);await $('trust-form').onsubmit(new Event('submit',{cancelable:true}));check('bundle accepted',!!activeBundle);check('active trust stays visible',!$('active-trust-note').hidden);await qaLoad('bundle');check('bundle issuer recognized',currentReport.signerStatus==='trusted');
 qaInputs(QA_BUNDLES.cases.find(c=>c.id==='rollback').bundle);await $('trust-form').onsubmit(new Event('submit',{cancelable:true}));check('bundle rollback rejected',$('trust-status').textContent.startsWith('Trust bundle rejected:'));
 $('trust-clear').onclick();await qaLoad('bundle');check('clear removes imported identity',currentReport.signerStatus==='unknown');check('clear hides active trust note',$('active-trust-note').hidden);
 $('qa-results').textContent=JSON.stringify({result:'ALL PASS',rows},null,2);
 }catch(error){$('qa-results').textContent=JSON.stringify({result:'FAIL',message:error.message,rows},null,2);}};
$('qa-ux').onclick=async()=>{const rows=[],check=(name,ok)=>{rows.push({name,pass:!!ok});if(!ok)throw Error(name);};try{
 workspaceMode('seal');check('privacy gate starts closed',$('convert-submit').disabled&&!$('convert-privacy').checked);
 for(const [kind,expected] of [['id',true],['square',false]]){const dt=new DataTransfer();dt.items.add(new File([Uint8Array.from(atob(QA_IMAGES[kind]),c=>c.charCodeAt(0))],kind+'.png',{type:'image/png'}));$('convert-input').files=dt.files;await $('convert-input').onchange();check(kind+' heuristic',!$('document-warning').hidden===expected);check(kind+' requires fresh acknowledgement',$('convert-submit').disabled&&!$('convert-privacy').checked);$('convert-privacy').checked=true;$('convert-privacy').onchange();check(kind+' acknowledgement enables seal',!$('convert-submit').disabled);}
 await $('convert-form').onsubmit(new Event('submit',{cancelable:true}));await openFile(lastSealedFile);check('real browser conversion stays self-signed',currentReport?.signerStatus==='self'&&!currentReport.genuine);
 const dt=new DataTransfer();dt.items.add(new File([Uint8Array.from(atob(QA_CASES.genuine),c=>c.charCodeAt(0))],'window-drop.GRD'));document.body.dispatchEvent(new DragEvent('drop',{dataTransfer:dt,bubbles:true,cancelable:true}));for(let i=0;i<120&&currentReport?.fileName!=='window-drop.GRD';i++)await new Promise(resolve=>requestAnimationFrame(resolve));check('drop anywhere opens file',currentReport?.fileName==='window-drop.GRD'&&currentReport.genuine);check('drop switches to recipient tab',!$('inspection-panel').hidden&&$('convert').hidden);$('qa-results').textContent=JSON.stringify({result:'ALL PASS',rows},null,2);
 }catch(error){$('qa-results').textContent=JSON.stringify({result:'FAIL',message:error.message,rows},null,2);}};
$('qa-advanced').onclick=async()=>{const rows=[],check=(name,ok)=>{rows.push({name,pass:!!ok});if(!ok)throw Error(name);};try{
 await qaLoad('genuine');showGuardView('#advanced',false);
 check('Advanced view contains specialist tools',!$('advanced').hidden&&$('main-view').hidden&&$('advanced-tools').contains($('trust-form')));
 revealAdvancedTool('trust');check('trust form visible',$('trust-form').getBoundingClientRect().height>0);revealAdvancedTool('copy');check('copy form visible',$('copy-form').getBoundingClientRect().height>0);check('only the selected tool stays expanded',!$('trust-form').closest('details').open);check('visual proof export available',!$('download-proof').hidden&&$('download-proof').getBoundingClientRect().height>0);
 for(const item of QA_VISUAL){for(const [id,encoded,name] of [['copy-proof',item.proof,'proof.grdp'],['copy-image',item.image,'copy.png']]){const dt=new DataTransfer();dt.items.add(new File([Uint8Array.from(atob(encoded),c=>c.charCodeAt(0))],name));$(id).files=dt.files;}await $('copy-form').onsubmit(new Event('submit',{cancelable:true}));check(item.id+' copy result',$('copy-status').textContent.startsWith(item.id==='consistent'?'VISUALLY CONSISTENT':item.id==='borderline'?'BORDERLINE (decoder-dependent)':'VISUALLY INCONSISTENT'));}
 check('copy form unlocked after check',!$('copy-submit').disabled&&!$('copy-image').disabled&&!$('copy-proof').disabled);$('qa-results').textContent=JSON.stringify({result:'ALL PASS',rows},null,2);
 }catch(error){$('qa-results').textContent=JSON.stringify({result:'FAIL',message:error.message,rows},null,2);}};
$('qa-offline').onclick=async()=>{
 const qaPassword='TEST ONLY '+hex(crypto.getRandomValues(new Uint8Array(16)));
 const rows=[],check=(name,ok)=>{rows.push({name,pass:!!ok});if(!ok)throw Error(name);},savedDownload=download,downloads=[];
 const input=(id,file)=>{const dt=new DataTransfer();dt.items.add(file);$(id).files=dt.files;};
 download=(bytes,name,type)=>downloads.push({bytes:typeof bytes==='string'?new TextEncoder().encode(bytes):new Uint8Array(bytes),name,type});
 try{
  showGuardView('#signer',false);revealAdvancedTool('signer');
  $('signer-name').value='TEST ONLY Offline Person';$('signer-password').value=qaPassword;$('signer-confirm').value='Different password 123!';
  await $('signer-create').onsubmit(new Event('submit',{cancelable:true}));check('mismatch does not create signer',!unlockedSigner&&downloads.length===0);
  $('signer-confirm').value=$('signer-password').value;await $('signer-create').onsubmit(new Event('submit',{cancelable:true}));
  check('encrypted key created and unlocked',!!unlockedSigner&&downloads.some(d=>d.name==='signer.guardkey'));
  const contact={...unlockedSigner.contact},backup=downloads.find(d=>d.name==='signer.guardkey').bytes;
  check('unlocked private key nonextractable',!unlockedSigner.privateKey.extractable);check('password fields cleared',!$('signer-password').value&&!$('signer-confirm').value);
  $('download-viewer').onclick();const viewer=new TextDecoder().decode(downloads.find(d=>d.name==='grd_viewer.html').bytes);check('offline viewer includes signer UI',viewer.includes('id="signer-create"')&&viewer.includes('createOfflineSigner'));check('offline viewer excludes runtime keys and passwords',!viewer.includes(contact.publicKey)&&!viewer.includes(qaPassword));
  $('signer-public').onclick();const publicFile=downloads.find(d=>d.name==='public.guardsigner');
  check('public export contains only public contact',JSON.stringify(await readSignerContact(new TextDecoder().decode(publicFile.bytes)))===JSON.stringify(contact));
  $('signer-lock').onclick();check('lock clears signer',!unlockedSigner&&$('signer-active').hidden);
  input('signer-file',new File([backup],'signer.guardkey'));$('signer-unlock-password').value='Wrong password 123!';await $('signer-unlock').onsubmit(new Event('submit',{cancelable:true}));
  check('wrong password remains locked',!unlockedSigner&&$('signer-status').textContent.includes('Could not unlock'));
  $('signer-unlock-password').value=qaPassword;await $('signer-unlock').onsubmit(new Event('submit',{cancelable:true}));check('saved key unlocks same identity',unlockedSigner?.contact.fingerprint===contact.fingerprint);
  workspaceMode('seal');input('convert-input',new File([Uint8Array.from(atob(QA_IMAGES.square),c=>c.charCodeAt(0))],'square.png',{type:'image/png'}));await $('convert-input').onchange();$('convert-privacy').checked=true;$('convert-privacy').onchange();await $('convert-form').onsubmit(new Event('submit',{cancelable:true}));
  const asset=downloads.find(d=>d.name==='image.GRD');check('named asset downloaded',!!asset);await openFile(lastSealedFile);check('no automatic signer trust',currentReport?.signerStatus==='unknown'&&!currentReport.genuine&&$('image-panel').hidden);
  const parsed=JSON.parse(new TextDecoder().decode(asset.bytes.subarray(5)));check('asset purpose and label signed',parsed.manifest.purpose==='asset'&&parsed.manifest.label===contact.name);
  workspaceMode('verify');showGuardView('#advanced',false);revealAdvancedTool('advanced-person');
  input('person-file',new File([publicFile.bytes],'public.guardsigner'));await $('person-file').onchange();$('person-fingerprint').value='0'.repeat(64);await $('person-form').onsubmit(new Event('submit',{cancelable:true}));check('mismatched fingerprint rejected',!personTrust.has(contact.publicKey));
  $('person-fingerprint').value=contact.fingerprint;await $('person-form').onsubmit(new Event('submit',{cancelable:true}));check('explicit public trust added',personTrust.has(contact.publicKey)&&!$('person-trust-note').hidden);
  await openFile(new File([asset.bytes],'offline-person.GRD'));check('recipient verifies named asset',currentReport?.genuine&&$('verdict-title').textContent==='Genuine'&&$('verdict-signer').textContent.includes(contact.name));
  $('person-clear').onclick();await openFile(new File([asset.bytes],'offline-person.GRD'));check('clearing trust withholds image again',currentReport?.signerStatus==='unknown'&&$('image-panel').hidden&&$('person-trust-note').hidden);
  const revokedContact=await signerContact(QA_REVOKED_KEY,'TEST ONLY Revoked Contact');input('person-file',new File([JSON.stringify(revokedContact)],'revoked.guardsigner'));$('person-fingerprint').value=revokedContact.fingerprint;await $('person-form').onsubmit(new Event('submit',{cancelable:true}));check('revoked key cannot be trusted',$('person-status').textContent.includes('revoked')&&!personTrust.has(revokedContact.publicKey));
  input('person-file',new File([publicFile.bytes],'public.guardsigner'));$('person-fingerprint').value=contact.fingerprint;const pendingTrust=$('person-form').onsubmit(new Event('submit',{cancelable:true}));$('person-clear').onclick();await pendingTrust;check('clear cancels pending person import',!personTrust.has(contact.publicKey));
  workspaceMode('seal');$('convert-privacy').checked=true;syncSealConsent();const count=downloads.filter(d=>d.name==='image.GRD').length;const pendingSign=$('convert-form').onsubmit(new Event('submit',{cancelable:true}));$('signer-lock').onclick();await pendingSign;check('locking prevents pending signed export',downloads.filter(d=>d.name==='image.GRD').length===count&&$('convert-status').textContent.startsWith('Sealing failed:'));
  $('signer-lock').onclick();workspaceMode('seal');$('signer-unlock-password').value=qaPassword;const pending=$('signer-unlock').onsubmit(new Event('submit',{cancelable:true}));lockOfflineSigner();await pending;check('locking cancels pending unlock',!unlockedSigner);
  check('local cryptography available',!!crypto.subtle);check('no online resources required',!Array.from(document.querySelectorAll('script[src],link[rel="stylesheet"]')).length);
  $('qa-results').textContent=JSON.stringify({result:'ALL PASS',origin:location.protocol,rows},null,2);
 }catch(error){$('qa-results').textContent=JSON.stringify({result:'FAIL',message:error.message,rows},null,2);}
 finally{download=savedDownload;lockOfflineSigner();}
};

$('qa-axe').onclick=async()=>{const rows=[];for(const state of ['empty','genuine','tampered','self','redact','unknown','fully','fault','notgrd','example','seal','seal-edit','trust','signer','person','copy-tools','report-tools','viewing-tools','offline-tools','about']){qaPanel.hidden=true;workspaceMode('verify');if(['fault','notgrd','example','seal-edit'].includes(state))await uxPrepare(state);else if(state==='empty')reset();else if(state==='seal')workspaceMode('seal');else if(state==='signer'){showGuardView('#signer',false);revealAdvancedTool('signer');}else if(state==='about'){showGuardView('#about',false);}else if(state==='person'){workspaceMode('verify');showGuardView('#advanced',false);revealAdvancedTool('advanced-person');}else if(state==='trust'){showGuardView('#advanced',false);revealAdvancedTool('trust');}else if(state.endsWith('-tools')){showGuardView('#advanced',false);revealAdvancedTool(state.replace('-tools',''));}else await qaLoad(state);if(state==='redact')$('verification-technical').open=true;if(state==='seal-edit'){document.querySelector('.seal-extras').open=true;document.querySelector('.editor-settings').open=true;$('rect-numbers').open=true;}await new Promise(resolve=>requestAnimationFrame(resolve));const audit=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']}});rows.push({state,seriousCritical:audit.violations.filter(v=>['serious','critical'].includes(v.impact)).map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),allViolations:audit.violations.map(v=>({id:v.id,impact:v.impact}))});$('qa-results').textContent=JSON.stringify({result:rows.some(r=>r.seriousCritical.length)?'FAIL':'ALL PASS',rows},null,2);}qaPanel.hidden=false;};
`;
const uxCode=await readFile(new URL('./ux-browser-checks.js',import.meta.url),'utf8');
const tail='\n})();';const where=html.lastIndexOf(tail);if(where<0)throw Error('Viewer wrapper not found');html=html.slice(0,where)+qaCode+uxCode+html.slice(where);
await writeFile(dir+'/index.html',html);
const revoked=JSON.parse(policy);revoked.revoked.push({fingerprint:vectors.keys.signers[0].fingerprint_sha256,reason:'TEST ONLY revoked signer',revokedAt:'2026-10-28T00:00:00Z'});await writeFile(dir+'/revoked.html',html.replace('const policy='+policy+';','const policy='+JSON.stringify(revoked)+';'));
await writeFile(dir+'/revoked-viewport.html',(await readFile(dir+'/revoked.html','utf8')).replaceAll('if(self!==top){','if(false){').replaceAll('if (self !== top) {','if (false) {'));
for(const [name,encoded] of Object.entries(cases))await writeFile(dir+'/'+name+'.GRD',Buffer.from(encoded,'base64'));
const {default:sharp}=await import('sharp');await sharp({create:{width:1012,height:638,channels:3,background:'#eee'}}).png().toFile(dir+'/fake-id-shape.png');await sharp({create:{width:1000,height:1000,channels:3,background:'#eee'}}).png().toFile(dir+'/square.png');
console.log('TEST ONLY fixtures and axe QA viewer written to '+dir+'; production viewer contains no axe');

// CSS reflow QA only: these fixture copies disable their own frame guard so a
// real Chromium iframe can supply a narrow CSS viewport. Production guard stays intact.
await writeFile(dir+'/viewport.html',html.replaceAll('if(self!==top){','if(false){').replaceAll('if (self !== top) {','if (false) {'));
const mobile=`<!doctype html><html lang="en"><meta charset="utf-8"><title>TEST ONLY narrow viewport QA</title><style>body{font:16px system-ui;margin:16px}iframe{border:2px solid #333;display:block}pre{white-space:pre-wrap}</style><h1>CSS viewport reflow checks</h1><p>Isolated TEST ONLY viewer. Chromium iframe CSS widths; not a real phone or screen-reader trial.</p><button id="run">Run narrow viewport checks</button><p id="summary" role="status">Ready</p><details><summary>Reflow measurements</summary><pre id="results">Ready</pre></details><iframe id="frame" title="TEST ONLY viewer viewport" width="390" height="844" src="viewport.html"></iframe><script>
const frame=document.querySelector('#frame'),output=document.querySelector('#results');document.querySelector('#run').onclick=async()=>{const rows=[];for(const [width,height] of [[1440,900],[1920,1080],[2560,1440],[320,740],[360,740],[390,844]]){frame.width=width;frame.height=height;await new Promise(resolve=>{frame.onload=resolve;frame.src='viewport.html?width='+width+'&run='+Date.now();});for(const state of ['empty','genuine','unknown','signer','person']){const d=frame.contentDocument;if(state==='signer'){d.querySelector('a[href="#advanced"]').click();d.getElementById('signer-setup').open=true;}else if(state==='about'){showGuardView('#about',false);}else if(state==='person'){d.querySelector('a[href="#advanced"]').click();d.querySelector('.person-trust').open=true;}else if(state!=='empty')await d.getElementById('qa-'+state).onclick();await new Promise(resolve=>requestAnimationFrame(resolve));const scrollWidth=d.documentElement.scrollWidth;rows.push({width,height,state,scrollWidth,pass:scrollWidth<=width,overflow:scrollWidth>width?Array.from(d.querySelectorAll('*')).map(el=>({selector:el.id?'#'+el.id:el.tagName+'.'+el.className,right:el.getBoundingClientRect().right,width:el.getBoundingClientRect().width})).filter(r=>r.width>0&&r.right>width+1).slice(0,12):[]});}}output.textContent=JSON.stringify({result:rows.every(r=>r.pass)?'ALL PASS':'FAIL',rows},null,2);document.querySelector('#summary').textContent=rows.filter(r=>r.pass).length+'/'+rows.length+' CSS viewport checks passed';};</script></html>`;
await writeFile(dir+'/mobile.html',mobile);

await writeFile(dir+'/ux-review.html',await readFile(new URL('./ux-review-page.html',import.meta.url),'utf8'));
