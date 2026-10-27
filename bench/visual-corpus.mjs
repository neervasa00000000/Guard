// SPDX-License-Identifier: MIT
import {readFile,writeFile} from 'node:fs/promises';
import {verifyVisual} from '../src/visual.js';
const folder=new URL('../results/visual-corpus/',import.meta.url),manifest=JSON.parse(await readFile(new URL('manifest.json',folder))),rows=[],start=performance.now();
for(const c of manifest.cases){const r=await verifyVisual(await readFile(new URL(c.proof,folder)),await readFile(new URL(c.image,folder)),[{public_key_hex:manifest.key}]);rows.push({id:c.id,actual:{visualVerdict:r.visualVerdict,genuine:r.genuine,visualConsistent:r.visualConsistent},worstError:r.worstError,problems:r.problems});}
await writeFile(new URL('node-report.json',folder),JSON.stringify({runtime:process.version,elapsedMs:performance.now()-start,rows},null,2)+'\n');console.log(`Wrote ${rows.length} Node visual results`);
