// SPDX-License-Identifier: MIT
import {canon,sha,TRUSTED,IntegrityError,encodedDimensions} from './verifier.js';
import {checkRevocation,TRUST_POLICY} from './trust.js';
import {base64,decodeBase64,verifyGRD2,encodeGRD2,validateManifest,manifestDigest,merkleRoot,tileBounds,containerImage,GRD3_LIMITS} from './redactable.js';
import {decodeRgbPng} from './png.js';
export const VISUAL_GUARANTEE = 'A VISUALLY CONSISTENT result means every disclosed 8×8 brightness block and 16×16 colour block is within 9 levels of the signed reference. Finer detail is NOT verified. Mean-preserving edits and some smooth blurs can pass.';
export function visualFeatures(rgb,width,height) {
  if (!(rgb instanceof Uint8Array)||!Number.isInteger(width)||!Number.isInteger(height)||width<1||height<1||width>64||height>64||rgb.length!==width*height*3)throw new IntegrityError('Invalid visual tile dimensions.');
  const sums=new Uint32Array(96),counts=new Uint16Array(96);
  const clamp=x=>Math.max(0,Math.min(255,x));
  for(let y=0;y<height;y++)for(let x=0;x<width;x++){
    const at=(y*width+x)*3,r=rgb[at],g=rgb[at+1],b=rgb[at+2];
    const l=(y>>>3)*8+(x>>>3),c=(y>>>4)*4+(x>>>4);
    sums[l]+=Math.floor((299*r+587*g+114*b+500)/1000);counts[l]++;
    sums[64+c]+=clamp(Math.floor((128000000-168736*r-331264*g+500000*b+500000)/1000000));counts[64+c]++;
    sums[80+c]+=clamp(Math.floor((128000000+500000*r-418688*g-81312*b+500000)/1000000));counts[80+c]++;
  }
  return Uint8Array.from(sums,(sum,i)=>counts[i]?Math.floor((sum+Math.floor(counts[i]/2))/counts[i]):i<64?0:128);
}
// Exact rational overlap in integer coordinate units. Cell sums are <=255*256*cw*ch,
// hence <=2,350,080,000,000 under the 36M-pixel limit: exact in Number (<2^42).
export function mappedVisualTile(rgb,cw,ch,m,index) {
  if (!(rgb instanceof Uint8Array)||!Number.isInteger(cw)||!Number.isInteger(ch)||cw<1||ch<1||cw>8192||ch>8192||cw*ch>36_000_000||rgb.length!==cw*ch*3)throw new IntegrityError('Invalid native visual pixels.');
  if(!m||m.tileSize!==64||!Number.isInteger(m.width)||!Number.isInteger(m.height)||m.width<1||m.height<1||m.width>8192||m.height>8192||m.width*m.height>36_000_000||!Number.isInteger(index)||index<0||index>=Math.ceil(m.width/64)*Math.ceil(m.height/64))throw new IntegrityError('Invalid signed visual grid.');
  const b=tileBounds(m,index),out=new Uint8Array(96);out.fill(128,64);
  for(const size of [8,16])for(let yy=0;yy<64;yy+=size)for(let xx=0;xx<64;xx+=size){
    if(xx>=b.width||yy>=b.height)continue;
    const left=(b.x+xx)*cw,right=(b.x+Math.min(xx+size,b.width))*cw,top=(b.y+yy)*ch,bottom=(b.y+Math.min(yy+size,b.height))*ch;
    let sy=0,scb=0,scr=0;const area=(right-left)*(bottom-top);
    for(let y=Math.floor(top/m.height);y<Math.ceil(bottom/m.height);y++){
      const wy=Math.min(bottom,(y+1)*m.height)-Math.max(top,y*m.height);
      for(let x=Math.floor(left/m.width);x<Math.ceil(right/m.width);x++){
        const weight=wy*(Math.min(right,(x+1)*m.width)-Math.max(left,x*m.width)),at=(y*cw+x)*3,r=rgb[at],g=rgb[at+1],v=rgb[at+2];
        if(size===8)sy+=weight*Math.floor((299*r+587*g+114*v+500)/1000);
        else {scb+=weight*Math.max(0,Math.min(255,Math.floor((128000000-168736*r-331264*g+500000*v+500000)/1000000)));scr+=weight*Math.max(0,Math.min(255,Math.floor((128000000+500000*r-418688*g-81312*v+500000)/1000000)));}
      }
    }
    const cell=(yy/size)*(64/size)+xx/size,round=n=>Math.floor((n+Math.floor(area/2))/area);
    if(size===8)out[cell]=round(sy);else {out[64+cell]=round(scb);out[80+cell]=round(scr);}
  }
  return out;
}
export function visualDecision(error,tau=9) {return error>=tau-2&&error<=tau+2?'BORDERLINE (decoder-dependent)':error<tau-2?'VISUALLY CONSISTENT':'VISUALLY INCONSISTENT';}
export async function visualSalt(salt) {
  const bytes=Uint8Array.from(salt.match(/../g),x=>parseInt(x,16));
  const key=await crypto.subtle.importKey('raw',bytes,{name:'HMAC',hash:'SHA-256'},false,['sign']);
  return new Uint8Array(await crypto.subtle.sign('HMAC',key,new TextEncoder().encode('GRD-VIS'))).subarray(0,16);
}
export async function visualCommitment(index,salt,feature) {
  const prefix=new TextEncoder().encode('GRD-VIS'),message=new Uint8Array(prefix.length+4+16+96);
  message.set(prefix);new DataView(message.buffer).setUint32(prefix.length,index);message.set(salt,prefix.length+4);message.set(feature,prefix.length+20);return sha(message);
}
export function visualTile(rgb,m,index) {
  const b=tileBounds(m,index),out=new Uint8Array(b.width*b.height*3);
  for(let y=0;y<b.height;y++)out.set(rgb.subarray(((b.y+y)*m.width+b.x)*3,((b.y+y)*m.width+b.x+b.width)*3),y*b.width*3);
  return visualFeatures(out,b.width,b.height);
}
export async function exportProof(container) {
  const bytes=container instanceof Uint8Array?container:encodeGRD2(container),report=await verifyGRD2(bytes,[]);
  if(!report.regionVerified||report.verdict==='REVOKED KEY')throw new IntegrityError('Cannot export proof from invalid source.');
  const doc=report.container??JSON.parse(new TextDecoder().decode(bytes.subarray(5))),m=doc.manifest;
  if(doc.tiles.some(t=>t.sub))throw new Error("Visual proof export requires whole 64px tile redactions; partially hidden tiles cannot disclose their original block means safely.");
  if(!m.visual)throw new Error('No visual layer in this legacy file.');
  const decoded=await decodeRgbPng(containerImage(doc),m.version===3?GRD3_LIMITS:undefined),vis=[];
  for(let i=0;i<doc.tiles.length;i++){
    const t=doc.tiles[i];
    if(Object.hasOwn(t,'commitment'))vis.push({index:i,commitment:m.visual.commitments[i]});
    else{
      const salt=await visualSalt(t.salt??t.seed),feature=mappedVisualTile(decoded.rgb,decoded.width,decoded.height,m,i);
      if(await visualCommitment(i,salt,feature)!==m.visual.commitments[i])throw new IntegrityError('Visual reference no longer opens (tile '+i+').');
      vis.push({index:i,salt:base64(salt),feature:base64(feature)});
    }
  }
  return new TextEncoder().encode('GRDP\n'+canon({manifest:m,signature:doc.signature,vis}));
}
async function visualDecodeImage(bytes,m) {
  if(bytes.length>GRD3_LIMITS.bytes)throw new IntegrityError('Candidate image exceeds size limit.');
  if(typeof createImageBitmap==='function'){
    const ascii=(start,length)=>String.fromCharCode(...bytes.subarray(start,start+length));
    const mime=bytes[0]===137&&ascii(1,3)==='PNG'?'image/png':bytes[0]===255&&bytes[1]===216?'image/jpeg':ascii(0,4)==='RIFF'&&ascii(8,4)==='WEBP'?'image/webp':null;
    if(!mime)throw new IntegrityError('Use a PNG, JPEG or WebP copy.');
    const [encodedWidth,encodedHeight]=encodedDimensions(bytes,mime);
    if(!encodedWidth||!encodedHeight||encodedWidth>8192||encodedHeight>8192||encodedWidth*encodedHeight>36_000_000)throw new IntegrityError('Candidate image dimensions exceed limits.');
    if(Math.abs((encodedWidth/encodedHeight)/(m.width/m.height)-1)>.01)return {aspectMismatch:true};
    let bitmap;
    try {
      bitmap=await createImageBitmap(new Blob([bytes]),{imageOrientation:'none'});
      const w=bitmap.width,h=bitmap.height;
      if(!w||!h||w>8192||h>8192||w*h>36_000_000)throw new IntegrityError('Candidate image dimensions exceed limits.');
      if(Math.abs((w/h)/(m.width/m.height)-1)>.01)return {aspectMismatch:true};
      const canvas=typeof OffscreenCanvas==='function'?new OffscreenCanvas(w,h):document.createElement('canvas');canvas.width=w;canvas.height=h;
      const context=canvas.getContext('2d',{willReadFrequently:true});context.fillStyle='#fff';context.fillRect(0,0,w,h);context.drawImage(bitmap,0,0);
      const rgba=context.getImageData(0,0,w,h).data,rgb=new Uint8Array(w*h*3);
      for(let i=0;i<w*h;i++)rgb.set(rgba.subarray(i*4,i*4+3),i*3);return {rgb,width:w,height:h};
    }finally{bitmap?.close();}
  }
  // Node uses a local image codec. The browser never loads this dependency.
  if(!globalThis.process?.versions?.node)throw new DOMException('Image-copy decoding is unavailable in this browser.','NotSupportedError');
  const {default:sharp}=await import('sharp');
  const image=sharp(bytes,{limitInputPixels:36_000_000,failOn:'warning'}),info=await image.metadata();
  if(!['png','jpeg','webp'].includes(info.format)||!info.width||!info.height||info.width>8192||info.height>8192)throw new IntegrityError('Unsupported candidate image.');
  if(Math.abs((info.width/info.height)/(m.width/m.height)-1)>.01)return {aspectMismatch:true};
  const rgb=await image.flatten({background:'#fff'}).removeAlpha().toColourspace('srgb').raw().toBuffer();return {rgb,width:info.width,height:info.height};
}
export async function verifyVisual(proof,imageBytes,anchors=TRUSTED,policy=TRUST_POLICY) {
  const r={verdict:'TAMPERED',genuine:false,viewable:false,problems:[],visualConsistent:false,guarantee:VISUAL_GUARANTEE};
  try{
    const bytes=proof instanceof Uint8Array?proof:new Uint8Array(proof);
    if(bytes.length>16*1024*1024)throw new IntegrityError('Visual proof exceeds 16 MiB.');
    let raw,p;
    try{raw=new TextDecoder('utf-8',{fatal:true}).decode(bytes.subarray(5));p=JSON.parse(raw);}catch(error){throw new IntegrityError('Invalid visual proof encoding.');}
    if(new TextDecoder().decode(bytes.subarray(0,5))!=='GRDP\n'||!p||Object.keys(p).sort().join(',')!=='manifest,signature,vis'||canon(p)!==raw)throw new IntegrityError('Noncanonical visual proof.');
    const m=p.manifest,count=validateManifest(m);
    if(!m.visual){r.verdict='UNSUPPORTED';r.problems.push('No visual layer.');return r;}
    const pk=Uint8Array.from(m.publicKey.match(/../g),x=>parseInt(x,16));
    if(await sha(pk)!==m.keyId)throw new IntegrityError('Wrong signer fingerprint.');
    r.revocation=await checkRevocation(pk,policy);if(r.revocation.revoked){r.verdict='REVOKED KEY';r.problems.push('Signing key is revoked.');return r;}
    const key=await crypto.subtle.importKey('raw',pk,'Ed25519',false,['verify']);
    if(!await crypto.subtle.verify('Ed25519',key,decodeBase64(p.signature,64),await manifestDigest(m)))throw new IntegrityError('Invalid visual manifest signature.');
    if(await merkleRoot(m.commitments)!==m.root)throw new IntegrityError('Invalid exact commitment root.');
    if(!Array.isArray(p.vis)||p.vis.length!==count)throw new IntegrityError('Invalid visual disclosures.');
    const features=[];
    for(let i=0;i<count;i++){
      const t=p.vis[i];if(!t||t.index!==i)throw new IntegrityError('Unordered visual tile.');
      if(Object.keys(t).sort().join(',')==='commitment,index'){
        if(t.commitment!==m.visual.commitments[i])throw new IntegrityError('Wrong hidden visual commitment.');features.push(null);
      }else{
        if(Object.keys(t).sort().join(',')!=='feature,index,salt')throw new IntegrityError('Invalid visual disclosure fields.');
        const salt=decodeBase64(t.salt,16),feature=decodeBase64(t.feature,96);
        if(await visualCommitment(i,salt,feature)!==m.visual.commitments[i])throw new IntegrityError('Visual feature proof mismatch (tile '+i+').');features.push(feature);
      }
    }
    const anchor=Array.isArray(anchors)?anchors.find(k=>k.public_key_hex===m.publicKey):null;
    if(!Array.isArray(anchors)||anchors._invalid)throw new Error('Invalid local trust anchors.');
    r.trusted=!!anchor&&m.purpose==='asset';r.signer=anchor?.name??anchor?.owner??'Identity not verified';r.trustVerdict=m.purpose==='demo'?'DEMO':m.purpose==='personal'?'UNVERIFIED: SELF-SIGNED':anchor?'TRUSTED':'UNTRUSTED SIGNER';
    const decoded=await visualDecodeImage(imageBytes instanceof Uint8Array?imageBytes:new Uint8Array(imageBytes),m);
    r.worstError=0;r.worstTile=null;r.worstCell=null;
    if(decoded.aspectMismatch){r.verdict='VISUALLY INCONSISTENT';r.visualVerdict=r.verdict;r.problems.push('Aspect ratio differs by more than 1%.');return r;}
    for(let i=0;i<count;i++){
      const actual=mappedVisualTile(decoded.rgb,decoded.width,decoded.height,m,i),expected=features[i];
      for(let cell=0;cell<(expected?96:64);cell++){
        const b=tileBounds(m,i),cx=(cell%8)*8,cy=Math.floor(cell/8)*8;
        if(!expected&&(cx>=b.width||cy>=b.height))continue;
        const error=expected?Math.abs(actual[cell]-expected[cell]):actual[cell];
        if(error>r.worstError){r.worstError=error;r.worstTile=i;r.worstCell=cell;}
      }
    }
    r.visualVerdict=visualDecision(r.worstError,m.visual.tau);
    r.visualConsistent=r.visualVerdict==='VISUALLY CONSISTENT';
    if(!features.some(feature=>feature!==null)&&r.visualVerdict!=='VISUALLY INCONSISTENT'){r.verdict='FULLY REDACTED';r.visualVerdict='FULLY REDACTED';r.visualConsistent=false;r.problems.push('No visible original block means are disclosed.');return r;}
    r.verdict=r.visualVerdict==='BORDERLINE (decoder-dependent)'?r.visualVerdict:!r.visualConsistent?'VISUALLY INCONSISTENT':r.trusted?'VISUALLY CONSISTENT':r.trustVerdict;
    if(r.visualVerdict==='BORDERLINE (decoder-dependent)'){r.warning='Close to the threshold; result may differ between apps';r.problems.push(r.warning);}
    r.assetId=m.assetId;r.width=m.width;r.height=m.height;r.tau=m.visual.tau;
    if(!r.trusted)r.problems.push('Visual matching does not establish signer identity. '+r.trustVerdict+'.');
    return r;
  }catch(error){if(error instanceof IntegrityError)r.verdict='TAMPERED';else if(error.name==='NotSupportedError')r.verdict='UNSUPPORTED';else{r.verdict='CANNOT VERIFY';r.verifierFault=true;}r.problems.push(error.message);return r;}
}
