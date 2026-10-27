// SPDX-License-Identifier: MIT
// Local attack catalogue; independent of the unavailable guard-paper harness.
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import assert from 'node:assert/strict';
import {encodeGRD2,verifyGRD2,base64,decodeBase64,redactGRD2} from '../src/redactable.js';
import {decodeRgbPng,encodeRgbPng} from '../src/png.js';
const shared=JSON.parse(await readFile(new URL('../tests/vectors/grd2-vectors.json',import.meta.url)));
const sealed=Buffer.from(shared.vectors[4].container,'base64'),doc=JSON.parse(sealed.subarray(5)),red=JSON.parse(Buffer.from(shared.vectors[5].container,'base64').subarray(5));
const cases=[];
const add=(id,bytes,expected='TAMPERED',policy)=>cases.push({id,container:base64(bytes),expected,policy});
const edit=(id,fn,d=doc,expected='TAMPERED')=>{const copy=structuredClone(d);fn(copy);add(id,encodeGRD2(copy),expected)};
const pixel=async(d,x,y)=>{const copy=structuredClone(d),p=await decodeRgbPng(decodeBase64(d.image));p.rgb[(y*p.width+x)*3]^=1;copy.image=base64(await encodeRgbPng(p.rgb,p.width,p.height));return encodeGRD2(copy)};
add('retained-pixel',await pixel(doc,100,10));
add('hidden-pixel',await pixel(red,1,1));
edit('fake-blackout',d=>d.image=doc.image,red);
edit('wrong-salt',d=>d.tiles[0].salt='f'.repeat(32));
edit('wrong-commitment',d=>d.manifest.commitments[0]='0'.repeat(64));
edit('wrong-root',d=>d.manifest.root='0'.repeat(64));
edit('wrong-asset-id',d=>d.manifest.assetId=base64(new Uint8Array(16)));
edit('wrong-created',d=>d.manifest.created='2026-10-26T00:00:00Z');
edit('wrong-dimensions',d=>d.manifest.width--);
edit('wrong-tile-size',d=>d.manifest.tileSize=32);
edit('short-signature',d=>d.signature=base64(new Uint8Array(63)));
edit('key-substitution',d=>d.manifest.publicKey='0'.repeat(64));
edit('missing-tile',d=>d.tiles.pop());
edit('duplicate-index',d=>d.tiles[1].index=0);
edit('reordered-tiles',d=>[d.tiles[0],d.tiles[1]]=[d.tiles[1],d.tiles[0]]);
edit('missing-mask',d=>d.redactions=[],red);
edit('duplicate-mask',d=>d.redactions.push(d.redactions[0]),red);
edit('wrong-hidden-commitment',d=>d.tiles[0].commitment='0'.repeat(64),red);
add('noncanonical-json',Buffer.from('GRD2\n'+JSON.stringify(doc,null,2)));
edit('noncanonical-base64',d=>d.image+='\n');
const utf=Buffer.from(sealed);utf[7]=255;add('invalid-utf8',utf);
for(const ratio of [.5,.99])add('truncation-'+ratio,sealed.subarray(0,Math.floor(sealed.length*ratio)));
add('last-byte-truncation',sealed.subarray(0,-1));
add('invalid-policy',sealed,'CANNOT VERIFY',{revoked:'invalid'});
cases.push({id:'oversized',size:33*1024*1024,expected:'LIMIT EXCEEDED'});
add('honest-redaction',encodeGRD2(red),'VERIFIED WITH REDACTIONS');
const flips=Number(process.env.FLIPS??200);let seed=42;
for(let i=0;i<flips;i++){seed=(Math.imul(seed,1664525)+1013904223)>>>0;const b=Buffer.from(sealed);b[5+seed%(b.length-5)]^=1<<(seed>>>24)%8;add('flip-'+i,b)}
const py=spawnSync('python3',['-c',`import sys,json,base64;import grd
payload=json.load(sys.stdin)
print(json.dumps([grd.verify(bytes(c['size']) if 'size' in c else base64.b64decode(c['container']),[payload['publicKey']],c.get('policy'))['verdict'] for c in payload['cases']]))`],{cwd:new URL('../',import.meta.url),input:JSON.stringify({publicKey:shared.public_key_hex,cases}),encoding:'utf8',timeout:30000,maxBuffer:8*1024*1024});
assert.equal(py.status,0,py.stderr);const python=JSON.parse(py.stdout),rows=[];
for(let i=0;i<cases.length;i++){const c=cases[i],r=await verifyGRD2(c.size ? new Uint8Array(c.size) : Buffer.from(c.container,'base64'),[{public_key_hex:shared.public_key_hex}],c.policy);rows.push({id:c.id,expected:c.expected,js:r.verdict,python:python[i],passed:r.verdict===c.expected&&python[i]===c.expected})}
await mkdir(new URL('../results/',import.meta.url),{recursive:true});
await writeFile(new URL('../results/local-attacks.json',import.meta.url),JSON.stringify({scope:'Local synthetic catalogue; not the external 107-image paper protocol. Body flips exclude magic bytes, which identify file format.',namedCases:27,flips,rows},null,2)+'\n');
for(const row of rows.filter(r=>!r.passed))console.error(row);
console.log(`Named attacks: ${rows.slice(0,27).filter(r=>r.passed).length}/27; body bit flips: ${rows.slice(27).filter(r=>r.passed).length}/${flips}; both JS and Python`);
assert.ok(rows.every(r=>r.passed));
