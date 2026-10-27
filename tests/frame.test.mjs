// SPDX-License-Identifier: MIT
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

test("frame guard triggers when self !== top and replaces body", async () => {
  const indexHtml = await readFile(
    new URL("../index.html", import.meta.url),
    "utf8",
  );
  assert.ok(indexHtml.includes("if(self!==top)"));
  assert.ok(
    indexHtml.includes("html.framed body > *:not(.frame-warning)"),
    "css contains anti-frame hiding rule",
  );

  const addedClasses = [];
  let replacedWith = [];
  const fakeDoc = {
    documentElement: {
      classList: {
        add: (cls) => addedClasses.push(cls),
      },
    },
    createElement: (tag) => ({
      tag,
      className: "",
      textContent: "",
      href: "",
      target: "",
      rel: "",
    }),
    body: {
      replaceChildren: (...children) => {
        replacedWith = children;
      },
    },
  };
  const sandbox = {
    self: { id: "iframe-self" },
    top: { id: "top-window" },
    document: fakeDoc,
    location: { href: "https://example.com/guard" },
    console,
  };

  const scriptMatch = indexHtml.match(/<script>([\s\S]*?)<\/script>/);
  assert.ok(scriptMatch, "inline script found");
  vm.runInNewContext(scriptMatch[1], sandbox);

  assert.ok(addedClasses.includes("framed"), "documentElement got class framed");
  assert.equal(replacedWith.length, 2);
  assert.equal(
    replacedWith[0].textContent,
    "Guard does not run inside embedded pages. Open the inspector directly to check a file.",
  );
  assert.equal(replacedWith[1].textContent, "Open Guard");
  assert.equal(replacedWith[1].href, "https://example.com/guard");
});
