// SPDX-License-Identifier: MIT
import {subTileCount,validateSubRecord,verifySubTile,subRedactionMap} from "./subtiles.js";
import { canon, sha, TRUSTED, IntegrityError } from './verifier.js';
import { checkRevocation, TRUST_POLICY } from './trust.js';
import { rgbPngParts, decodeRgbPngBands, PngFormatError } from './png.js';
import { createTileHasher } from './hash-worker.js';
import { base64, decodeBase64, validateManifest, merkleRoot, manifestDigest, tileBounds } from './redactable.js';
export const GRD3_LIMITS = Object.freeze({ bytes: 256*1024*1024, dimension: 8192, pixels: 36_000_000, tiles: 9000 });
export function isGRD3(input) {
  const b = input instanceof Uint8Array ? input : new Uint8Array(input);
  return b[0] === 71 && b[1] === 82 && b[2] === 68 && b[3] === 51 && b[4] === 10;
}
export function encodeGRD3(doc) {
  validateManifest(doc.manifest);
  if (doc.manifest.version !== 3) throw new IntegrityError('GRD3 requires a version 3 manifest.');
  const manifest = new TextEncoder().encode(canon(doc.manifest)), signature = decodeBase64(doc.signature,64);
  const png = doc.image instanceof Uint8Array ? doc.image : decodeBase64(doc.image);
  if (!Array.isArray(doc.tiles) || doc.tiles.length !== doc.manifest.commitments.length) throw new IntegrityError('Invalid GRD3 tile count.');
  let recordBytes = 0;
  for (const t of doc.tiles) {
    if (doc.manifest.subTile) validateSubRecord(doc.manifest,t,t.index);
    recordBytes += t.sub ? 3+t.sub.reduce((n,s)=>n+(s.salt?17:33),0) : (Object.hasOwn(t,'salt')||t.seed) ? 17 : 33;
  }
  const total = 5+4+manifest.length+64+4+recordBytes+8+png.length;
  if (total > GRD3_LIMITS.bytes) throw new IntegrityError('GRD3 exceeds 256 MiB.');
  const out = new Uint8Array(total), view = new DataView(out.buffer); let at=0;
  out.set([71,82,68,51,10],at); at+=5; view.setUint32(at,manifest.length);at+=4;out.set(manifest,at);at+=manifest.length;out.set(signature,at);at+=64;
  view.setUint32(at,doc.tiles.length);at+=4;
  const putHex = value => { for(let j=0;j<value.length;j+=2)out[at++]=parseInt(value.slice(j,j+2),16); };
  for (let i=0;i<doc.tiles.length;i++) {
    const t=doc.tiles[i], retained=Object.hasOwn(t,'salt') || Object.hasOwn(t,'seed');
    if (doc.manifest.subTile) validateSubRecord(doc.manifest,t,i);
    if (t.sub) {
      out[at++]=3;view.setUint16(at,t.sub.length);at+=2;
      for(const s of t.sub){out[at++]=s.salt?0:1;putHex(s.salt??s.commitment);}
      continue;
    }
    if (t.index!==i || Object.keys(t).length!==2) throw new IntegrityError('Invalid tile record.');
    const value=retained?(t.salt??t.seed):t.commitment;
    if (typeof value!=='string' || !(retained?/^[0-9a-f]{32}$/:/^[0-9a-f]{64}$/).test(value)) throw new IntegrityError('Invalid GRD3 record bytes.');
    const method=doc.redactions.find(r=>r.index===i)?.method;
    if (!retained && !['black','blur'].includes(method)) throw new IntegrityError('Missing GRD3 redaction method.');
    out[at++]=retained?0:method==='black'?1:2;putHex(value);
  }

  view.setBigUint64(at,BigInt(png.length));at+=8;out.set(png,at);return out;
}
export function decodeGRD3(input) {
  const b=input instanceof Uint8Array?input:new Uint8Array(input);
  if(b.length>GRD3_LIMITS.bytes)throw new IntegrityError('GRD3 exceeds 256 MiB.');
  if(!isGRD3(b))throw new IntegrityError('Missing GRD3 header.');
  const view=new DataView(b.buffer,b.byteOffset,b.byteLength);let at=5;
  const need=n=>{if(!Number.isSafeInteger(n)||n<0||at+n>b.length)throw new IntegrityError('Truncated GRD3 section.');};
  need(4);const length=view.getUint32(at);at+=4;if(length>2*1024*1024)throw new IntegrityError('Manifest length exceeds bound.');need(length);
  let raw,m;
  try{raw=new TextDecoder('utf-8',{fatal:true}).decode(b.subarray(at,at+length));m=JSON.parse(raw);}catch(error){if(error instanceof TypeError||error instanceof SyntaxError)throw new IntegrityError('Invalid GRD3 manifest encoding.');throw error;}
  at+=length;const count=validateManifest(m);
  if(m.version!==3||canon(m)!==raw)throw new IntegrityError('Noncanonical GRD3 manifest.');
  need(68);const signature=base64(b.subarray(at,at+64));at+=64;const n=view.getUint32(at);at+=4;
  if(n!==count)throw new IntegrityError('GRD3 tile count mismatch.');
  const tiles=[],redactions=[];
  const toHex=a=>Array.from(a,x=>x.toString(16).padStart(2,'0')).join('');
  for(let index=0;index<n;index++){
    need(1);const kind=b[at++];
    if(kind===3 && m.subTile){
      need(2);const count=view.getUint16(at);at+=2;if(count!==subTileCount(m,index))throw new IntegrityError('Wrong sub-record count.');
      const sub=[];
      for(let j=0;j<count;j++){
        need(1);const k=b[at++];if(k>1)throw new IntegrityError('Invalid sub-record kind.');
        const size=k?32:16;need(size);const value=toHex(b.subarray(at,at+size));at+=size;sub.push(k?{j,commitment:value}:{j,salt:value});
      }
      const t={index,sub};validateSubRecord(m,t,index);tiles.push(t);redactions.push({index,method:'black'});continue;
    }
    if(kind>2 || (m.subTile&&kind===2))throw new IntegrityError('Unknown GRD3 tile kind.');
    const size=kind?32:16;need(size);const value=toHex(b.subarray(at,at+size));at+=size;
    const t=kind?{index,commitment:value}:m.subTile?{index,seed:value}:{index,salt:value};
    if(m.subTile)validateSubRecord(m,t,index);tiles.push(t);if(kind)redactions.push({index,method:kind===1?'black':'blur'});
  }

  need(8);const pngLength=view.getBigUint64(at);at+=8;
  if(pngLength>BigInt(GRD3_LIMITS.bytes)||pngLength!==BigInt(b.length-at))throw new IntegrityError('Invalid GRD3 PNG length or trailing bytes.');
  return {manifest:m,signature,tiles,redactions,image:b.subarray(at)};
}
export async function verifyGRD3(input, anchors=TRUSTED, policy=TRUST_POLICY) {
  const bytes=input instanceof Uint8Array?input:new Uint8Array(input);
  const r={version:3,verdict:'TAMPERED',genuine:false,viewable:false,checks:[],sections:[],problems:[],failed:[],changed:[],hiddenPixelsCleared:true,signature_valid:false};
  const ok=(name,detail)=>r.checks.push({name,status:'pass',detail});let hasher;
  try {
    if(bytes.length>GRD3_LIMITS.bytes){r.verdict='LIMIT EXCEEDED';throw new IntegrityError('GRD3 exceeds 256 MiB.');}
    if(anchors?._invalid||TRUSTED?._invalid||!Array.isArray(anchors))throw new Error('Invalid local trust anchors.');
    const doc=decodeGRD3(bytes),m=doc.manifest;
    ok("Container structure",doc.tiles.length+" ordered parent records · binary lengths agree");
    r.assetId=m.assetId;r.created=m.created;r.root=m.root;r.keyId=m.keyId;
    const pk=Uint8Array.from(m.publicKey.match(/../g),x=>parseInt(x,16));
    if(await sha(pk)!==m.keyId)throw new IntegrityError('Wrong signer fingerprint.');
    r.revocation=await checkRevocation(pk,policy);
    if(r.revocation.revoked){r.verdict='REVOKED KEY';throw new IntegrityError('Signing key is revoked.');}
    ok('Offline revocation','Not listed in bundled snapshot · '+r.revocation.asOf);
    const key=await crypto.subtle.importKey('raw',pk,'Ed25519',false,['verify']);
    r.signature_valid=await crypto.subtle.verify('Ed25519',key,decodeBase64(doc.signature,64),await manifestDigest(m));
    if(!r.signature_valid)throw new IntegrityError('Manifest signature is invalid.');
    if(await merkleRoot(m.commitments)!==m.root)throw new IntegrityError('Signed root mismatch.');
    ok('Signed manifest','Ed25519 · GRD3 domain · complete commitment vector');
    const parts=rgbPngParts(doc.image,GRD3_LIMITS);
    if(parts.width!==m.width||parts.height!==m.height)throw new IntegrityError('PNG dimensions differ from signed manifest.');
    hasher=createTileHasher(m.subTile?0:doc.tiles.length);r.hashWorkers=hasher.workerCount;r.maxDecodedRows=64;
    const prefix=new TextEncoder().encode('GRD-TILE');
    for await(const band of decodeRgbPngBands(doc.image,GRD3_LIMITS)) {
      const buffers=[],indices=[];
      const first=Math.floor(band.y/64)*Math.ceil(m.width/64),end=first+Math.ceil(m.width/64);
      for(let i=first;i<end;i++){
        const t=doc.tiles[i],bounds=tileBounds(m,i),rgb=new Uint8Array(bounds.width*bounds.height*3);
        for(let y=0;y<bounds.height;y++)rgb.set(band.rgb.subarray((y*m.width+bounds.x)*3,(y*m.width+bounds.x+bounds.width)*3),y*bounds.width*3);
        if(m.subTile){await verifySubTile(m,t,i,rgb);continue;}
        if(Object.hasOwn(t,'commitment')){
          if(t.commitment!==m.commitments[i])throw new IntegrityError('Wrong commitment at tile '+i);
          if(doc.redactions.find(e=>e.index===i).method==='black'){
            if(rgb.some(x=>x!==0)){r.hiddenPixelsCleared=false;throw new IntegrityError('blackout incomplete (tile '+i+')');}
          }else{r.hiddenPixelsCleared=false;r.problems.push('Legacy blur redaction (tile '+i+'): pixels not verified.');}
        }else{
          const message=new Uint8Array(prefix.length+4+16+rgb.length);message.set(prefix);new DataView(message.buffer).setUint32(prefix.length,i);
          message.set(Uint8Array.from(t.salt.match(/../g),x=>parseInt(x,16)),prefix.length+4);message.set(rgb,prefix.length+20);buffers.push(message);indices.push(i);
        }
      }
      const hashes=await hasher.hash(buffers);
      hashes.forEach((hash,j)=>{if(hash!==m.commitments[indices[j]])throw new IntegrityError('Non-redacted tile '+indices[j]+' was changed.');});
    }
    ok('Streaming tile commitments',doc.tiles.length+' tiles checked in 64-row bands');
    r.fileHash=await sha(bytes);r.tilesTotal=doc.tiles.length;r.redactedTiles=doc.redactions.map(e=>e.index);r.tilesVisible=r.tilesTotal-r.redactedTiles.length;r.tileSize=64;
    r.redactionMap=m.subTile?subRedactionMap(doc):doc.redactions.map(e=>({index:e.index,...tileBounds(m,e.index),claimedMethod:e.method,methodAttested:false}));
    if(m.subTile){r.subTile=m.subTile;r.subTilesTotal=doc.tiles.reduce((n,t)=>n+subTileCount(m,t.index),0);r.subTilesVisible=doc.tiles.reduce((n,t)=>n+(t.seed?subTileCount(m,t.index):t.sub?t.sub.filter(s=>s.salt).length:0),0);}
    r.regionVerified=true;r.redactionApproval='not_attested';r.container=doc;
    r.meta={asset_id:m.assetId,created_utc:m.created,width:m.width,height:m.height,mime:'image/png',original_filename:m.label||undefined};
    const anchor=anchors.find(k=>k.public_key_hex===m.publicKey);
    r.demo=m.purpose==='demo';r.personal=m.purpose==='personal';r.trusted=!!anchor&&!r.demo&&!r.personal;r.signer=anchor?.name??anchor?.owner??'Untrusted signer';r.signerName=anchor?.name??anchor?.owner;r.fingerprint=m.keyId;
    r.checks.push({name:'Signer trust',status:r.trusted?'pass':r.demo||r.personal?'info':'fail',detail:r.demo?'DEMO ONLY':r.personal?'SELF-SIGNED':r.signer});
    if(!r.trusted&&!r.demo&&!r.personal)r.verdict='UNTRUSTED SIGNER';
    else if(!doc.tiles.some(t=>t.salt||t.seed||t.sub?.some(s=>s.salt)))r.verdict='FULLY REDACTED';
    else {r.verdict=r.demo?'DEMO':r.personal?'UNVERIFIED: SELF-SIGNED':r.redactedTiles.length?'VERIFIED WITH REDACTIONS':'GENUINE';r.genuine=r.verdict==='GENUINE';r.viewable=true;}
    return r;
  }catch(error){
    if(error.message?.startsWith("blackout incomplete"))r.hiddenPixelsCleared=false;
    if(error.name==='ResourceLimitError')r.verdict='LIMIT EXCEEDED';
    else if(!['LIMIT EXCEEDED','REVOKED KEY'].includes(r.verdict)){
      if(error instanceof IntegrityError||error instanceof PngFormatError)r.verdict='TAMPERED';
      else if(error.name==='NotSupportedError')r.verdict='UNSUPPORTED';
      else{r.verdict='CANNOT VERIFY';r.verifierFault=true;}
    }
    r.problems.push(error.message);r.failed.push('GRD3 proof');r.changed=[...r.failed];return r;
  }finally{hasher?.close();}
}
