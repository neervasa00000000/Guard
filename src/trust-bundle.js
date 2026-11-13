// SPDX-License-Identifier: MIT
// Explicit-root, offline trust-bundle verification. No network or persistent storage.
import { validateTrustedKeys } from './verifier.js';
const bundleDomain = new TextEncoder().encode('GUARD-TRUST-BUNDLE-V1\0');
function bundleCanon(v) {
  if (Array.isArray(v)) return '[' + v.map(bundleCanon).join(',') + ']';
  if (v && typeof v === 'object') return '{' + Object.keys(v).sort().map(k => JSON.stringify(k)+':'+bundleCanon(v[k])).join(',') + '}';
  return JSON.stringify(v);
}
function portable(v, depth=0) {
  if (depth>32) return false;
  if (typeof v==='number') return Number.isSafeInteger(v);
  if (typeof v==='string') return !/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/u.test(v);
  if (Array.isArray(v)) return v.every(x=>portable(x,depth+1));
  if (v && typeof v==='object') return Object.entries(v).every(([k,x])=>portable(k,depth+1)&&portable(x,depth+1));
  return v===null||typeof v==='boolean';
}
const bundleHex = b => Array.from(b,x=>x.toString(16).padStart(2,'0')).join('');
const bundleExact = (v, fields) => v && typeof v==='object' && !Array.isArray(v) && Object.keys(v).sort().join(',')===fields.sort().join(',');
function bundleDate(v) {
  if (typeof v!=='string'||!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(v)||v.startsWith('0000')||!Number.isFinite(Date.parse(v))||new Date(v).toISOString()!==v.replace('Z','.000Z')) throw Error('Invalid bundle bundleDate');
  return Date.parse(v);
}
export async function verifyTrustBundle(bytes, rootHex, {now=Date.now(), minSequence=1, previous=null}={}) {
  if (!(bytes instanceof Uint8Array)||bytes.length>2*1024*1024) throw Error('Bundle exceeds input limit');
  if (!/^[0-9a-f]{64}$/.test(rootHex)) throw Error('An explicit Ed25519 root is required');
  const text = new TextDecoder('utf-8',{fatal:true}).decode(bytes), doc=JSON.parse(text);
  if (!portable(doc)||!bundleExact(doc,['payload','signature'])||bundleCanon(doc)!==text) throw Error('Noncanonical bundle');
  const p=doc.payload;
  if (!bundleExact(p,['format','sequence','issued','expires','keys'])||p.format!=='GUARD-TRUST-1'||!Number.isSafeInteger(p.sequence)||p.sequence<1||!Number.isSafeInteger(minSequence)||minSequence<1||p.sequence<minSequence) throw Error('Invalid bundle or rollback');
  const issued=bundleDate(p.issued),expires=bundleDate(p.expires);
  if (!Number.isFinite(now)||issued>now||expires<=now||expires<=issued||expires-issued>90*86400000) throw Error('Bundle expired, future-dated or validity exceeds 90 days');
  validateTrustedKeys(p.keys);
  if (!bundleExact(p.keys,['version','asOf','signers'])||p.keys.asOf!==p.issued||p.keys.signers.length>4096) throw Error('Invalid bundle key snapshot');
  const seen=new Set();
  for (const s of p.keys.signers) {
    if (!bundleExact(s,['key_id','public_key_hex','fingerprint_sha256','name','alg','revoked','revokedAt','reason'])) throw Error('Invalid signer fields');
    const fp=bundleHex(new Uint8Array(await crypto.subtle.digest('SHA-256',Uint8Array.from(s.public_key_hex.match(/../g),x=>parseInt(x,16)))));
    if (fp!==s.fingerprint_sha256||s.key_id!==fp.slice(0,16)||seen.has(fp)||typeof s.name!=='string'||!s.name.replace(/[ \t\r\n]/g,'')||(s.revoked&&(typeof s.reason!=='string'||!s.reason.replace(/[ \t\r\n]/g,'')||bundleDate(s.revokedAt)>issued))) throw Error('Invalid or duplicate signer');
    if (!s.revoked && s.reason!==null) throw Error('Invalid revocation reason');
    seen.add(fp);
  }
  const root=Uint8Array.from(rootHex.match(/../g),x=>parseInt(x,16)),rootFingerprint=bundleHex(new Uint8Array(await crypto.subtle.digest('SHA-256',root)));
  const digest=bundleHex(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)));
  if (previous !== null && (!bundleExact(previous,['rootFingerprint','sequence','digest'])||previous.rootFingerprint!==rootFingerprint||!Number.isSafeInteger(previous.sequence)||previous.sequence<1||!/^[0-9a-f]{64}$/.test(previous.digest)||p.sequence<previous.sequence||(p.sequence===previous.sequence&&digest!==previous.digest))) throw Error('Bundle rollback, equivocation or cache/root mismatch');
  if (typeof doc.signature!=='string'||!/^[A-Za-z0-9+/]{86}==$/.test(doc.signature)) throw Error('Invalid bundle signature');
  const signature=Uint8Array.from(atob(doc.signature),c=>c.charCodeAt(0));
  if (btoa(String.fromCharCode(...signature))!==doc.signature) throw Error('Noncanonical signature');
  const payload=new TextEncoder().encode(bundleCanon(p)),message=new Uint8Array(bundleDomain.length+payload.length);message.set(bundleDomain);message.set(payload,bundleDomain.length);
  const key=await crypto.subtle.importKey('raw',root,{name:'Ed25519'},false,['verify']);
  if (!await crypto.subtle.verify('Ed25519',key,signature,message)) throw Error('Bundle signature failed');
  return {keys:p.keys,anchors:p.keys.signers.filter(s=>!s.revoked),policy:{version:p.sequence,asOf:p.issued,revoked:p.keys.signers.filter(s=>s.revoked).map(s=>({fingerprint:s.fingerprint_sha256,reason:s.reason,revokedAt:s.revokedAt}))},state:{rootFingerprint,sequence:p.sequence,digest},expires:p.expires};
}

export function publicKeyHexFromPem(pem) {
 if(typeof pem!=='string'||pem.length>4096||pem.includes('PRIVATE KEY'))throw Error('Pass an Ed25519 public key PEM only.');
 const match=pem.trim().match(/^-----BEGIN PUBLIC KEY-----\s+([A-Za-z0-9+/=\s]+)-----END PUBLIC KEY-----$/);
 if(!match)throw Error('Invalid public key PEM');
 const bytes=Uint8Array.from(atob(match[1].replace(/\s/g,'')),c=>c.charCodeAt(0));
 if(bytes.length!==44||bundleHex(bytes.subarray(0,12))!=='302a300506032b6570032100')throw Error('An Ed25519 public key is required');
 return bundleHex(bytes.subarray(12));
}
