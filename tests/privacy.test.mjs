// SPDX-License-Identifier: MIT
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

test("privacy section copy and links in index.html and PRIVACY.md", async () => {
  const indexHtml = await readFile(
    new URL("../index.html", import.meta.url),
    "utf8",
  );
  assert.ok(
    indexHtml.includes("Effective 27 October 2026"),
    "index.html must include effective date",
  );
  assert.ok(
    indexHtml.includes("github-general-privacy-statement"),
    "index.html must link to GitHub privacy statement",
  );
  assert.ok(
    indexHtml.includes("GitHub Pages"),
    "index.html must mention GitHub Pages hosting",
  );
  assert.ok(
    indexHtml.includes('href="#privacy-details"'),
    "index.html footer must link to privacy details",
  );
  assert.ok(
    !indexHtml.includes("[contact"),
    "index.html must not contain placeholder contact string",
  );

  const privacyMd = await readFile(
    new URL("../PRIVACY.md", import.meta.url),
    "utf8",
  );
  assert.ok(
    privacyMd.includes("Effective 27 October 2026"),
    "PRIVACY.md must include effective date",
  );
  assert.ok(
    !privacyMd.includes("[contact"),
    "PRIVACY.md must not contain placeholder contact string",
  );
});
