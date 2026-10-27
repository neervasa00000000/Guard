import test from "node:test";
import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { verifyGRD2 } from "../src/redactable.js";

test("every shipped example is a valid demo in both checkers, with a failing authenticity exit code", async () => {
  const directory = new URL("../examples/", import.meta.url);
  const files = (await readdir(directory)).filter((n) =>
    n.toLowerCase().endsWith(".grd"),
  );
  assert.ok(files.length >= 2);
  for (const name of files) {
    const path = new URL(name, directory),
      report = await verifyGRD2(await readFile(path));
    assert.equal(report.verdict, "DEMO", name);
    assert.equal(report.genuine, false, name);
    assert.equal(report.viewable, true, name);
    assert.equal(
      report.redactedTiles.length,
      name.includes(".redacted.") ? 1 : 0,
      name,
    );
    const python = spawnSync(
      "python3",
      ["grd.py", "verify", decodeURIComponent(path.pathname)],
      { cwd: new URL("../", import.meta.url), encoding: "utf8" },
    );
    assert.equal(python.status, 2, name);
    const other = JSON.parse(python.stdout);
    assert.equal(other.verdict, report.verdict, name);
    assert.deepEqual(other.redactionMap, report.redactionMap, name);
  }
});
