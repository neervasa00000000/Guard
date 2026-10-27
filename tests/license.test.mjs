// SPDX-License-Identifier: MIT
import test from "node:test";
import assert from "node:assert/strict";
import { readFile, readdir, stat } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

test("all source and script files have SPDX MIT header and NOTICE exists", async () => {
  const root = fileURLToPath(new URL("../", import.meta.url));

  const checkDir = async (dir, prefix, ext) => {
    const entries = await readdir(join(root, dir));
    for (const entry of entries) {
      if (entry.endsWith(ext)) {
        const content = await readFile(join(root, dir, entry), "utf8");
        assert.ok(
          content.startsWith(prefix),
          `${dir}/${entry} must start with ${prefix}`,
        );
      }
    }
  };

  await checkDir("src", "// SPDX-License-Identifier: MIT", ".js");
  await checkDir("scripts", "// SPDX-License-Identifier: MIT", ".mjs");

  const grdPy = await readFile(join(root, "grd.py"), "utf8");
  assert.ok(
    grdPy.includes("# SPDX-License-Identifier: MIT"),
    "grd.py must include SPDX MIT comment",
  );

  const notice = await stat(join(root, "NOTICE"));
  assert.ok(notice.isFile(), "NOTICE file must exist");
});
