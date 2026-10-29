// SPDX-License-Identifier: MIT
import test from 'node:test';import assert from 'node:assert/strict';import {readFile} from 'node:fs/promises';import {spawnSync} from 'node:child_process';import {EXIT_CODES} from '../src/verifier.js';import {verifyVisual} from '../src/visual.js';
test('JS/Python exit tables cannot drift, and shared visual outcomes map to 5/7/2',async()=>{
 const py=spawnSync('python3',['-c','import json,grd;print(json.dumps(grd.EXIT))'],{encoding:'utf8'});assert.equal(py.status,0,py.stderr);assert.deepEqual(EXIT_CODES,JSON.parse(py.stdout));
 const s=JSON.parse(await readFile(new URL('vectors/signer-status-vectors.json',import.meta.url)));
 for(const v of s.visual){const r=await verifyVisual(Buffer.from(v.proof,'base64'),Buffer.from(v.image,'base64'),s.keys.signers);assert.equal(EXIT_CODES[r.verdict],v.exit_code,v.id);}
});
