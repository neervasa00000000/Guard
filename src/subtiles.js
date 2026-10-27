// SPDX-License-Identifier: MIT
import {sha,IntegrityError} from './verifier.js';
import {tileBounds,verifyGRD2,encodeGRD2,containerImage,GRD3_LIMITS,base64} from './redactable.js';
import {decodeRgbPng,encodeRgbPng} from './png.js';
export function subTileBounds(m,index,j) {
  const b=tileBounds(m,index),g=m.subTile,cols=Math.ceil(b.width/g),x=(j%cols)*g,y=Math.floor(j/cols)*g;
  return {x:b.x+x,y:b.y+y,width:Math.min(g,b.width-x),height:Math.min(g,b.height-y)};
}
export function subTileCount(m,index){const b=tileBounds(m,index);return Math.ceil(b.width/m.subTile)*Math.ceil(b.height/m.subTile);}
export async function subSalts(seed,count){
 const key=await crypto.subtle.importKey('raw',Uint8Array.from(seed.match(/../g),x=>parseInt(x,16)),{name:'HMAC',hash:'SHA-256'},false,['sign']);
 return Promise.all(Array.from({length:count},async(_,j)=>{const message=new Uint8Array([71,82,68,45,83,85,66,0,0]);new DataView(message.buffer).setUint16(7,j);return Array.from(new Uint8Array(await crypto.subtle.sign('HMAC',key,message)).subarray(0,16),b=>b.toString(16).padStart(2,'0')).join('');}));
}
export async function subCommitment(index,j,salt,rgb){
 const prefix=new TextEncoder().encode('GRD-SUBTILE'),message=new Uint8Array(prefix.length+4+2+16+rgb.length);message.set(prefix);const view=new DataView(message.buffer);view.setUint32(prefix.length,index);view.setUint16(prefix.length+4,j);message.set(Uint8Array.from(salt.match(/../g),x=>parseInt(x,16)),prefix.length+6);message.set(rgb,prefix.length+22);return sha(message);
}
export async function subParentCommitment(index,commitments){
 const prefix=new TextEncoder().encode('GRD-TILE2'),message=new Uint8Array(prefix.length+4+32*commitments.length);message.set(prefix);new DataView(message.buffer).setUint32(prefix.length,index);
 commitments.forEach((c,j)=>message.set(Uint8Array.from(c.match(/../g),x=>parseInt(x,16)),prefix.length+4+j*32));return sha(message);
}
export function subPixels(tile,m,index,j){
 const b=tileBounds(m,index),s=subTileBounds(m,index,j),x=s.x-b.x,y=s.y-b.y,out=new Uint8Array(s.width*s.height*3);
 for(let r=0;r<s.height;r++)out.set(tile.subarray(((y+r)*b.width+x)*3,((y+r)*b.width+x+s.width)*3),r*s.width*3);return out;
}
export async function sealSubTile(m,index,seed,tile){
 const salts=await subSalts(seed,subTileCount(m,index)),commitments=await Promise.all(salts.map((salt,j)=>subCommitment(index,j,salt,subPixels(tile,m,index,j))));
 return {commitment:await subParentCommitment(index,commitments),salts,commitments};
}
export function validateSubRecord(m,t,index){
 const keys=Object.keys(t).sort().join(',');
 if(t.index!==index)throw new IntegrityError('Wrong tile index.');
 if(keys==='index,seed'){
  if(typeof t.seed!=='string'||!/^[0-9a-f]{32}$/.test(t.seed))throw new IntegrityError('Invalid tile seed.');
 }else if(keys==='commitment,index'){
  if(typeof t.commitment!=='string'||!/^[0-9a-f]{64}$/.test(t.commitment))throw new IntegrityError('Invalid hidden tile commitment.');
 }else if(keys==='index,sub'){
  if(!Array.isArray(t.sub)||t.sub.length!==subTileCount(m,index))throw new IntegrityError('Wrong sub-record count.');
  let hidden=0;
  t.sub.forEach((s,j)=>{
   if(!s||s.j!==j)throw new IntegrityError('Unordered sub-record.');
   const k=Object.keys(s).sort().join(',');
   if(k==='j,salt'){if(typeof s.salt!=='string'||!/^[0-9a-f]{32}$/.test(s.salt))throw new IntegrityError('Invalid sub-tile salt.');}
   else if(k==='commitment,j'){if(typeof s.commitment!=='string'||!/^[0-9a-f]{64}$/.test(s.commitment))throw new IntegrityError('Invalid sub-tile commitment.');hidden++;}
   else throw new IntegrityError('Invalid sub-record fields.');
  });
  if(!hidden||hidden===t.sub.length)throw new IntegrityError('Partial tile must contain both retained and hidden sub-tiles.');
 }else throw new IntegrityError('Seed must be absent on a partially hidden tile.');
}
export async function verifySubTile(m,t,index,tile){
 validateSubRecord(m,t,index);
 if(Object.hasOwn(t,'commitment')){
  if(t.commitment!==m.commitments[index]||tile.some(x=>x!==0))throw new IntegrityError('blackout incomplete or wrong commitment (tile '+index+')');return;
 }
 if(t.seed){if((await sealSubTile(m,index,t.seed,tile)).commitment!==m.commitments[index])throw new IntegrityError('Non-redacted tile '+index+' changed.');return;}
 const commitments=[];
 for(const s of t.sub){
  const pixels=subPixels(tile,m,index,s.j);
  if(s.commitment){if(pixels.some(x=>x!==0))throw new IntegrityError('blackout incomplete (tile '+index+' sub '+s.j+')');commitments.push(s.commitment);}
  else commitments.push(await subCommitment(index,s.j,s.salt,pixels));
 }
 if(await subParentCommitment(index,commitments)!==m.commitments[index])throw new IntegrityError('Retained disclosure changed (tile '+index+' sub proof).');
}
export function subRedactionMap(doc){
 const m=doc.manifest,out=[];
 for(const t of doc.tiles){
  if(t.commitment)out.push({index:t.index,...tileBounds(m,t.index),claimedMethod:'black',methodAttested:false});
  else if(t.sub)for(const s of t.sub)if(s.commitment)out.push({index:t.index,subIndex:s.j,...subTileBounds(m,t.index,s.j),claimedMethod:'black',methodAttested:false});
 }
 return out;
}
export async function redactRects(document,rects,{granularity=64}={}){
 const m=document.manifest;
 if(!m.subTile){if(granularity<64)throw new Error('granularity finer than sealed sub-tile');throw new Error('Use whole-tile redaction for this legacy file.');}
 if(![8,16,32,64].includes(granularity)||granularity<m.subTile)throw new Error('granularity finer than sealed sub-tile');
 if(!Array.isArray(rects)||!rects.length)throw new Error('Select at least one rectangle.');
 const rounded=rects.map(rect=>{
  const {x,y,width,height}=Array.isArray(rect)?{x:rect[0],y:rect[1],width:rect[2],height:rect[3]}:rect;
  if(![x,y,width,height].every(Number.isFinite)||width<=0||height<=0)throw new Error('Invalid rectangle.');
  return {x:Math.floor(x/granularity)*granularity,y:Math.floor(y/granularity)*granularity,right:Math.ceil((x+width)/granularity)*granularity,bottom:Math.ceil((y+height)/granularity)*granularity};
 });
 const r=await verifyGRD2(encodeGRD2(document),[]);if(!r.regionVerified)throw new Error('Cannot redact invalid source proof.');
 const decoded=await decodeRgbPng(containerImage(document),m.version===3?GRD3_LIMITS:undefined),rgb=decoded.rgb,tiles=[];
 let selected=false;
 for(let i=0;i<document.tiles.length;i++){
  const t=document.tiles[i];if(t.commitment){const b=tileBounds(m,i);if(rounded.some(rect=>b.x<rect.right&&b.x+b.width>rect.x&&b.y<rect.bottom&&b.y+b.height>rect.y))selected=true;tiles.push({...t});continue;}
  const b=tileBounds(m,i),tile=new Uint8Array(b.width*b.height*3);
  for(let row=0;row<b.height;row++)tile.set(rgb.subarray(((b.y+row)*m.width+b.x)*3,((b.y+row)*m.width+b.x+b.width)*3),row*b.width*3);
  const material=t.seed?await sealSubTile(m,i,t.seed,tile):null;
  const sub=material?material.salts.map((salt,j)=>({j,salt})):t.sub.map(s=>({...s}));
  for(let j=0;j<sub.length;j++){
   const cell=subTileBounds(m,i,j),hit=rounded.some(rect=>cell.x<rect.right&&cell.x+cell.width>rect.x&&cell.y<rect.bottom&&cell.y+cell.height>rect.y);
   if(hit){selected=true;if(!sub[j].commitment)sub[j]={j,commitment:material?material.commitments[j]:await subCommitment(i,j,sub[j].salt,subPixels(tile,m,i,j))};}
   if(sub[j].commitment)for(let row=0;row<cell.height;row++){const at=((cell.y+row)*m.width+cell.x)*3;rgb.fill(0,at,at+cell.width*3);}
  }
  const hidden=sub.filter(s=>s.commitment).length;
  tiles.push(hidden===sub.length?{index:i,commitment:m.commitments[i]}:hidden?{index:i,sub}:t);
 }
 if(!selected)throw new Error('No image sub-tiles intersect the rectangles.');
 const png=await encodeRgbPng(rgb,m.width,m.height),redactions=tiles.filter(t=>t.commitment||t.sub).map(t=>({index:t.index,method:'black'}));
 return encodeGRD2({manifest:m,signature:document.signature,tiles,redactions,image:m.version===3?png:base64(png)});
}
