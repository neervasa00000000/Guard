import { readFile, writeFile } from "node:fs/promises";
const root = new URL("../", import.meta.url);
let html = await readFile(new URL("src/index.template.html", root), "utf8");
const css = await readFile(new URL("src/style.css", root), "utf8");
const policy = await readFile(new URL("src/trust-policy.json", root), "utf8");
const trust =
  "const policy=" +
  policy +
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
const app = await readFile(new URL("src/app.js", root), "utf8");
html = html
  .replace("/*__STYLE__*/", () => css)
  .replace(
    "/*__SCRIPT__*/",
    () =>
      `(()=>{\n'use strict';\n${trust}\n${core}\n${png}\n${redactable}\n${app}\n})();`,
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
