// SPDX-License-Identifier: MIT
import test from "node:test";
import assert from "node:assert/strict";
import { readFile, writeFile, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { createHash, sign as nodeSign } from "node:crypto";
import { signer } from "./fixtures.mjs";
import { createVerifier, validateTrustedKeys } from "../src/verifier.js";
import { sealRgba, encodeGRD2, verifyGRD2 } from "../src/redactable.js";

const keyA = signer();
const keyB = signer();

function makeSignerInfo(key, name, extra = {}) {
  const pkHex = key.raw.toString("hex");
  const fp = createHash("sha256").update(key.raw).digest("hex");
  const kid = fp.slice(0, 16);
  return {
    key_id: kid,
    public_key_hex: pkHex,
    fingerprint_sha256: fp,
    name,
    alg: "Ed25519",
    revoked: false,
    revokedAt: null,
    reason: null,
    ...extra,
  };
}

const trustedDoc = {
  version: 1,
  asOf: "2026-10-27T00:00:00Z",
  signers: [
    makeSignerInfo(keyA, "Signer Alice"),
    makeSignerInfo(keyB, "Signer Bob"),
  ],
};

test("two-signer file: fixtures from both signers are GENUINE in JS and Python, each showing its own name", async () => {
  assert.equal(validateTrustedKeys(trustedDoc), true);
  const anchors = trustedDoc.signers.map((s) => ({
    key_id: s.key_id,
    public_key_hex: s.public_key_hex,
    fingerprint_sha256: s.fingerprint_sha256,
    name: s.name,
    owner: s.name,
    alg: s.alg,
  }));
  assert.equal(anchors.length, 2);

  const rgba = new Uint8Array(64 * 64 * 4).fill(128);
  const docA = await sealRgba({
    rgba,
    width: 64,
    height: 64,
    publicKey: keyA.raw,
    sign: (b) => nodeSign(null, Buffer.from(b), keyA.privateKey),
  });
  const docB = await sealRgba({
    rgba,
    width: 64,
    height: 64,
    publicKey: keyB.raw,
    sign: (b) => nodeSign(null, Buffer.from(b), keyB.privateKey),
  });

  const encodedA = encodeGRD2(docA);
  const encodedB = encodeGRD2(docB);

  // JS checks
  const repA = await verifyGRD2(encodedA, anchors);
  assert.equal(repA.verdict, "GENUINE");
  assert.equal(repA.genuine, true);
  assert.equal(repA.signerName, "Signer Alice");

  const repB = await verifyGRD2(encodedB, anchors);
  assert.equal(repB.verdict, "GENUINE");
  assert.equal(repB.genuine, true);
  assert.equal(repB.signerName, "Signer Bob");

  // Python CLI checks
  const dir = await mkdtemp(join(tmpdir(), "grd-multi-signer-"));
  try {
    const keysPath = join(dir, "trusted-keys.json");
    await writeFile(keysPath, JSON.stringify(trustedDoc, null, 2));
    const pathA = join(dir, "a.GRD");
    const pathB = join(dir, "b.GRD");
    await writeFile(pathA, encodedA);
    await writeFile(pathB, encodedB);

    const procA = spawnSync(
      "python3",
      ["grd.py", "verify", pathA, "--trusted-keys", keysPath],
      { cwd: new URL("../", import.meta.url), encoding: "utf8" },
    );
    assert.equal(procA.status, 0);
    const jsonA = JSON.parse(procA.stdout);
    assert.equal(jsonA.verdict, "GENUINE");
    assert.equal(jsonA.signerName, "Signer Alice");

    const procB = spawnSync(
      "python3",
      ["grd.py", "verify", pathB, "--trusted-keys", keysPath],
      { cwd: new URL("../", import.meta.url), encoding: "utf8" },
    );
    assert.equal(procB.status, 0);
    const jsonB = JSON.parse(procB.stdout);
    assert.equal(jsonB.verdict, "GENUINE");
    assert.equal(jsonB.signerName, "Signer Bob");
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("setting signer B to revoked: true gives REVOKED KEY for B while A stays GENUINE", async () => {
  const fpB = createHash("sha256").update(keyB.raw).digest("hex");
  const revokedDoc = {
    version: 1,
    asOf: "2026-10-27T00:00:00Z",
    signers: [
      makeSignerInfo(keyA, "Signer Alice"),
      makeSignerInfo(keyB, "Signer Bob", {
        revoked: true,
        revokedAt: "2026-10-26T00:00:00Z",
        reason: "Key compromised",
      }),
    ],
  };

  assert.equal(validateTrustedKeys(revokedDoc), true);
  const anchors = revokedDoc.signers
    .filter((s) => !s.revoked)
    .map((s) => ({
      key_id: s.key_id,
      public_key_hex: s.public_key_hex,
      fingerprint_sha256: s.fingerprint_sha256,
      name: s.name,
      owner: s.name,
      alg: s.alg,
    }));
  const rgba = new Uint8Array(64 * 64 * 4).fill(128);
  const docA = await sealRgba({
    rgba,
    width: 64,
    height: 64,
    publicKey: keyA.raw,
    sign: (b) => nodeSign(null, Buffer.from(b), keyA.privateKey),
  });
  const docB = await sealRgba({
    rgba,
    width: 64,
    height: 64,
    publicKey: keyB.raw,
    sign: (b) => nodeSign(null, Buffer.from(b), keyB.privateKey),
  });

  const encodedA = encodeGRD2(docA);
  const encodedB = encodeGRD2(docB);

  // JS checks with trust policy including revoked signers
  const trustPolicy = {
    version: 1,
    asOf: "2026-10-27T00:00:00Z",
    revoked: [
      {
        fingerprint: fpB,
        reason: "Key compromised",
        revokedAt: "2026-10-26T00:00:00Z",
      },
    ],
  };

  const repA = await verifyGRD2(encodedA, anchors, trustPolicy);
  assert.equal(repA.verdict, "GENUINE");

  const repB = await verifyGRD2(encodedB, anchors, trustPolicy);
  assert.equal(repB.verdict, "REVOKED KEY");

  // Python CLI checks
  const dir = await mkdtemp(join(tmpdir(), "grd-revoked-b-"));
  try {
    const keysPath = join(dir, "trusted-keys.json");
    await writeFile(keysPath, JSON.stringify(revokedDoc, null, 2));
    const pathA = join(dir, "a.GRD");
    const pathB = join(dir, "b.GRD");
    await writeFile(pathA, encodedA);
    await writeFile(pathB, encodedB);

    const procA = spawnSync(
      "python3",
      ["grd.py", "verify", pathA, "--trusted-keys", keysPath],
      { cwd: new URL("../", import.meta.url), encoding: "utf8" },
    );
    assert.equal(procA.status, 0);
    assert.equal(JSON.parse(procA.stdout).verdict, "GENUINE");

    const procB = spawnSync(
      "python3",
      ["grd.py", "verify", pathB, "--trusted-keys", keysPath],
      { cwd: new URL("../", import.meta.url), encoding: "utf8" },
    );
    assert.equal(procB.status, 6);
    assert.equal(JSON.parse(procB.stdout).verdict, "REVOKED KEY");
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("malformed entry (wrong key_id, bad date) gives CANNOT VERIFY in both checkers", async () => {
  const badKeyIdDoc = {
    version: 1,
    asOf: "2026-10-27T00:00:00Z",
    signers: [
      makeSignerInfo(keyA, "Signer Alice", { key_id: "wrong_key_id" }),
    ],
  };

  assert.throws(() => validateTrustedKeys(badKeyIdDoc), /invalid/);

  const badDateDoc = {
    version: 1,
    asOf: "invalid-date",
    signers: [
      makeSignerInfo(keyA, "Signer Alice"),
    ],
  };

  assert.throws(() => validateTrustedKeys(badDateDoc), /invalid/);

  const rgba = new Uint8Array(64 * 64 * 4).fill(128);
  const docA = await sealRgba({
    rgba,
    width: 64,
    height: 64,
    publicKey: keyA.raw,
    sign: (b) => nodeSign(null, Buffer.from(b), keyA.privateKey),
  });
  const encodedA = encodeGRD2(docA);

  const dir = await mkdtemp(join(tmpdir(), "grd-bad-keys-"));
  try {
    const keysPath = join(dir, "trusted-keys.json");
    await writeFile(keysPath, JSON.stringify(badDateDoc, null, 2));
    const pathA = join(dir, "a.GRD");
    await writeFile(pathA, encodedA);

    const proc = spawnSync(
      "python3",
      ["grd.py", "verify", pathA, "--trusted-keys", keysPath],
      { cwd: new URL("../", import.meta.url), encoding: "utf8" },
    );
    assert.equal(proc.status, 4);
    const res = JSON.parse(proc.stdout);
    assert.equal(res.verdict, "CANNOT VERIFY");
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("grep test: literal 97bb1a09 appears only in trusted-keys.json and built HTML files", async () => {
  const verifierJs = await readFile(
    new URL("../src/verifier.js", import.meta.url),
    "utf8",
  );
  assert.ok(!verifierJs.includes("97bb1a09"));

  const grdPy = await readFile(
    new URL("../grd.py", import.meta.url),
    "utf8",
  );
  assert.ok(!grdPy.includes("97bb1a09"));

  const trustedKeys = await readFile(
    new URL("../src/trusted-keys.json", import.meta.url),
    "utf8",
  );
  assert.ok(trustedKeys.includes("97bb1a09"));
});
