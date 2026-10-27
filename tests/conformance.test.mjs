// SPDX-License-Identifier: MIT
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { createVerifier, validateTrustedKeys } from "../src/verifier.js";
import { verifyGRD2 } from "../src/redactable.js";

const root = fileURLToPath(new URL("../", import.meta.url));
const conformanceDir = join(root, "conformance");

const vectors = JSON.parse(
  await readFile(join(conformanceDir, "vectors.json"), "utf8"),
);

const trustedKeysDoc = JSON.parse(
  await readFile(join(conformanceDir, "trusted-keys.test.json"), "utf8"),
);

validateTrustedKeys(trustedKeysDoc);

const anchors = trustedKeysDoc.signers
  .filter((s) => !s.revoked)
  .map((s) => ({
    key_id: s.key_id,
    public_key_hex: s.public_key_hex,
    fingerprint_sha256: s.fingerprint_sha256,
    name: s.name,
    owner: s.name,
    alg: s.alg,
  }));

const revokedEntries = trustedKeysDoc.signers
  .filter((s) => s.revoked)
  .map((s) => ({
    fingerprint: s.fingerprint_sha256,
    reason: s.reason || "Revoked key",
    revokedAt: s.revokedAt,
  }));

const trustPolicy = {
  version: 1,
  asOf: "2026-10-27T00:00:00Z",
  revoked: revokedEntries,
};

const verifyGRD1 = createVerifier(anchors, trustPolicy);

test("conformance vectors agree across JS and Python checkers", async () => {
  for (const v of vectors) {
    const bytes = await readFile(join(root, v.file));

    // JS checker
    let js;
    if (v.format === 1) {
      js = await verifyGRD1(bytes);
    } else {
      js = await verifyGRD2(bytes, anchors, trustPolicy);
    }

    assert.equal(
      js.verdict,
      v.expected_verdict,
      `[${v.id}] JS verdict mismatch (got ${js.verdict}, expected ${v.expected_verdict})`,
    );

    if (v.expected_hidden_pixels_cleared !== undefined) {
      assert.equal(
        js.hiddenPixelsCleared,
        v.expected_hidden_pixels_cleared,
        `[${v.id}] JS hiddenPixelsCleared mismatch`,
      );
    }

    // Python checker
    const proc = spawnSync(
      "python3",
      [
        "grd.py",
        "verify",
        join(root, v.file),
        "--trusted-keys",
        join(conformanceDir, "trusted-keys.test.json"),
      ],
      { cwd: root, encoding: "utf8" },
    );

    assert.equal(
      proc.status,
      v.expected_exit,
      `[${v.id}] Python exit code mismatch (got ${proc.status}, expected ${v.expected_exit}, output: ${proc.stdout} ${proc.stderr})`,
    );

    const py = JSON.parse(proc.stdout);
    assert.equal(
      py.verdict,
      v.expected_verdict,
      `[${v.id}] Python verdict mismatch (got ${py.verdict}, expected ${v.expected_verdict})`,
    );

    if (v.expected_hidden_pixels_cleared !== undefined) {
      assert.equal(
        py.hiddenPixelsCleared,
        v.expected_hidden_pixels_cleared,
        `[${v.id}] Python hiddenPixelsCleared mismatch`,
      );
    }
  }
});
