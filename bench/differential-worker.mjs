// SPDX-License-Identifier: MIT
import {readFileSync} from 'node:fs';
import {createVerifier} from '../src/verifier.js';
import {isGRD2,verifyGRD2} from '../src/redactable.js';
const input=JSON.parse(readFileSync(0,'utf8')),anchors=input.keys.map(public_key_hex=>({public_key_hex})),legacy=createVerifier(anchors),out=[];
for(const encoded of input.cases){const bytes=Buffer.from(encoded,'base64');try{const r=await(isGRD2(bytes)?verifyGRD2(bytes,anchors):legacy(bytes));out.push({verdict:r.verdict,genuine:r.genuine,regionVerified:!!r.regionVerified});}catch(error){out.push({exception:error.name+': '+error.message});}}
process.stdout.write(JSON.stringify(out));
