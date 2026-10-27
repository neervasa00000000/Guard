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
  .replace(/^export /gm, "");
const app = (await readFile(new URL("src/app.js", root), "utf8")).replace(
  /^\/\/ SPDX[^\n]*\n/gm,
  "",
);
const converter = (await readFile(new URL("src/converter.js", root), "utf8"))
  .replace(/^import[^\n]*\n/gm, "")
  .replace(/^export /gm, "");
const frameGuard =
  "if(self!==top){document.documentElement.classList.add('framed');const w=document.createElement('p');w.className='frame-warning';w.textContent='Guard does not run inside embedded pages. Open the inspector directly to check a file.';const l=document.createElement('a');l.className='frame-warning';l.textContent='Open Guard';l.href=location.href;l.target='_blank';l.rel='noopener noreferrer';document.body.replaceChildren(w,l);return;}";
html = html
  .replace("/*__STYLE__*/", () => css)
  .replace(
    "/*__SCRIPT__*/",
    () =>
      `(()=>{\n'use strict';\n${frameGuard}\n${trust}\n${core}\n${png}\n${redactable}\n${converter}\n${app}\n})();`,
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
