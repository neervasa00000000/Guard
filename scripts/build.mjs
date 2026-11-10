// SPDX-License-Identifier: MIT
import { readFile, writeFile } from "node:fs/promises";
const root = new URL("../", import.meta.url);
let html = await readFile(new URL("src/index.template.html", root), "utf8");
const css = await readFile(new URL("src/style.css", root), "utf8");
const policy = await readFile(new URL("src/trust-policy.json", root), "utf8");
const trustedKeys = await readFile(
  new URL("src/trusted-keys.json", root),
  "utf8",
);
const publishedKeys = await readFile(new URL('.well-known/guard-signers.json',root),'utf8');
if (JSON.stringify(JSON.parse(trustedKeys)) !== JSON.stringify(JSON.parse(publishedKeys))) throw new Error('Published signer registry differs from src/trusted-keys.json');
const trust =
  "const policy=" +
  policy +
  ";\nconst trustedData=" +
  trustedKeys +
  ";\n" +
  (await readFile(new URL("src/trust.js", root), "utf8"))
    .replace(/^import[\s\S]*?;\n/gm, "")
    .replace(/^export /gm, "");
const core = (await readFile(new URL("src/verifier.js", root), "utf8"))
  .replace(/^export /gm, "")
  .replace(/^import[\s\S]*?;\n/gm, "");
const png = (await readFile(new URL("src/png.js", root), "utf8")).replace(
  /^export /gm,
  "",
);
const redactable = (await readFile(new URL("src/redactable.js", root), "utf8"))
  .replace(/^import[\s\S]*?;\n/gm, "")
  .replace(/^export \{[^}]+\};\n/gm, "")
  .replace(/^export /gm, "");
const hashWorker = (await readFile(new URL("src/hash-worker.js", root), "utf8")).replace(/^export /gm, "");
const grd3 = (await readFile(new URL("src/grd3.js", root), "utf8")).replace(/^import[\s\S]*?;\n/gm, "").replace(/^export /gm, "");
// The shared sealing module still supports legacy visual commitments for other
// callers. Keep those primitives without bundling the visual proof tools.
const visualSource = await readFile(new URL("src/visual.js", root), "utf8");
const visual = ["visualFeatures", "visualSalt", "visualCommitment"].map(name => {
  const pattern = new RegExp("^export ((?:async )?function " + name + "\\([^]*?^})", "m");
  const match = visualSource.match(pattern);
  if (!match) throw new Error("Missing shared visual primitive: " + name);
  return match[1];
}).join("\n");
const subtiles = (await readFile(new URL("src/subtiles.js", root), "utf8")).replace(/^import[\s\S]*?;\n/gm, "").replace(/^export /gm, "");
const geometry = (await readFile(new URL("src/pad-box.js", root), "utf8")).replace(/^export /gm, "");
const app = (await readFile(new URL("src/app.js", root), "utf8")).replace(
  /^\/\/ SPDX[^\n]*\n/gm,
  "",
);
const converter = (await readFile(new URL("src/converter.js", root), "utf8"))
  .replace(/^import[^\n]*\n/gm, "")
  .replace(/^export /gm, "");
const frameGuard =
  "if(self!==top){document.documentElement.classList.add('framed');const w=document.createElement('p');w.className='frame-warning';w.textContent='TileSeal does not run inside embedded pages. Open it directly to check a file.';const l=document.createElement('a');l.className='frame-warning';l.textContent='Open TileSeal';l.href=location.href;l.target='_blank';l.rel='noopener noreferrer';document.body.replaceChildren(w,l);return;}";
html = html
  .replace("/*__STYLE__*/", () => css)
  .replace(
    "/*__SCRIPT__*/",
    () =>
      `(()=>{\n'use strict';\n${frameGuard}\n${trust}\n${core}\n${png}\n${hashWorker}\n${grd3}\n${visual}\n${subtiles}\n${redactable}\n${converter}\n${geometry}\n${app}\n})();`,
  );
await Promise.all(
  ["index.html", "grd_viewer.html"].map((name) =>
    writeFile(new URL(name, root), html),
  ),
);
console.log(
  "Built index.html and standalone grd_viewer.html (" +
    Buffer.byteLength(html) +
    " bytes each). No runtime dependencies.",
);
