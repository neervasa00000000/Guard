import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import { createVerifier, verifyGRD, LIMITS } from "../src/verifier.js";
import { signer, makeGRD, png } from "./fixtures.mjs";
const key = signer(),
  verify = createVerifier([key.anchor]),
  valid = makeGRD(key);
test("valid fixture checks all sections, pinned signer and signature", async () => {
  const r = await verify(valid);
  assert.equal(r.verdict, "GENUINE");
  assert.equal(r.genuine, true);
  assert.equal(r.sections.length, 6);
  assert.ok(r.signature_valid);
  assert.deepEqual(Buffer.from(r.payload), png());
  assert.equal(r.timestampPresent, true);
  assert.equal(r.tsa_time, undefined);
});
test("every single-bit mutation fails closed", async (t) => {
  let count = 0;
  for (let i = 0; i < valid.length; i++)
    for (let bit = 0; bit < 8; bit++) {
      const copy = Buffer.from(valid);
      copy[i] ^= 1 << bit;
      const result = await verify(copy);
      assert.notEqual(
        result.genuine,
        true,
        `Accepted mutation byte ${i}, bit ${bit}`,
      );
      assert.equal(result.payload, undefined);
      count++;
    }
  t.diagnostic(
    `${count.toLocaleString()} single-bit mutations rejected across ${valid.length} bytes.`,
  );
});
test("unknown signer cannot become genuine even with a mathematically valid signature", async () => {
  const r = await verifyGRD(valid);
  assert.equal(r.verdict, "TAMPERED");
  assert.equal(r.signature_valid, true);
  assert.ok(r.failed.includes("untrusted signer"));
  assert.equal(r.payload, undefined);
});
test("copying or mutating a trust anchor after creating a verifier cannot change trust", async () => {
  const entry = { ...key.anchor },
    v = createVerifier([entry]);
  entry.public_key_hex = "00".repeat(32);
  assert.equal((await v(valid)).genuine, true);
});
test("truncation, trailing bytes, impossible offsets and duplicate types are rejected", async () => {
  for (const data of [
    valid.subarray(0, 9),
    valid.subarray(0, -1),
    Buffer.concat([valid, Buffer.from([0])]),
  ])
    assert.notEqual((await verify(data)).genuine, true);
  const huge = Buffer.from(valid);
  huge.writeBigUInt64LE(2n ** 63n, 12);
  assert.equal((await verify(huge)).genuine, false);
  const duplicate = Buffer.from(valid);
  duplicate.writeUInt16LE(1, 60);
  assert.equal((await verify(duplicate)).genuine, false);
});
test("valid signed but wrongly bound or noncanonical metadata is rejected", async () => {
  for (const options of [
    { meta: { asset_id: "another-image" } },
    { meta: { key_id: "bad-key" } },
    { metadataRaw: "{} " },
    { metadataRaw: "[]" },
    { meta: { width: 0 } },
    { meta: { height: LIMITS.dimension + 1 } },
    { meta: { mime: "image/svg+xml" } },
  ])
    assert.equal((await verify(makeGRD(key, options))).genuine, false);
});
test("oversized input is rejected before hashing or decoding", async () => {
  const r = await verify(new Uint8Array(LIMITS.fileBytes + 1));
  assert.equal(r.verdict, "LIMIT EXCEEDED");
  assert.equal(r.fileHash, undefined);
});
test("Uint8Array byte offsets are respected", async () => {
  const padded = Buffer.concat([
    Buffer.from("prefix"),
    valid,
    Buffer.from("suffix"),
  ]);
  assert.equal(
    (await verify(padded.subarray(6, 6 + valid.length))).genuine,
    true,
  );
});
test("optional sections may be absent in the existing GRD1 layout", async () => {
  assert.equal((await verify(makeGRD(key, { extras: false }))).genuine, true);
});
test("reference viewer and hardened verifier agree on acceptance for fixture and mutations", async () => {
  let source = await readFile(
    new URL("../reference/grd_viewer.original.html", import.meta.url),
    "utf8",
  );
  source = source.slice(
    source.indexOf("const TRUSTED ="),
    source.indexOf("// ---------------- protected rendering"),
  );
  source = source.replace(
    /const TRUSTED = .*?;\n/,
    `const TRUSTED = ${JSON.stringify([key.anchor])};\n`,
  );
  const context = {
    crypto,
    TextDecoder,
    DataView,
    Uint8Array,
    ArrayBuffer,
    console,
  };
  vm.runInNewContext(
    source + "\nglobalThis.referenceVerify=verifyGRD;",
    context,
  );
  assert.equal(
    (
      await context.referenceVerify(
        valid.buffer.slice(
          valid.byteOffset,
          valid.byteOffset + valid.byteLength,
        ),
      )
    ).genuine,
    true,
  );
  for (let i = 0; i < valid.length; i += 7) {
    const copy = Buffer.from(valid);
    copy[i] ^= 1;
    const a = await verify(copy),
      b = await context.referenceVerify(
        copy.buffer.slice(copy.byteOffset, copy.byteOffset + copy.byteLength),
      );
    assert.equal(
      a.genuine === true,
      b.genuine === true,
      "Acceptance differed at " + i,
    );
  }
});
test("encoded image dimensions must match signed dimensions before returning genuine", async () => {
  const r = await verify(
    makeGRD(key, { image: png(100, 80), width: 120, height: 80 }),
  );
  assert.equal(r.verdict, "TAMPERED");
  assert.equal(r.genuine, false);
  assert.equal(r.payload, undefined);
  assert.ok(r.failed.includes("image"));
});
test("a signed invalid image is not called genuine", async () => {
  const r = await verify(
    makeGRD(key, { image: Buffer.from("not an encoded image") }),
  );
  assert.equal(r.verdict, "UNREADABLE");
  assert.equal(r.signature_valid, true);
  assert.equal(r.payload, undefined);
});
test("GRD1 rejects a revoked pinned key before accepting its signature", async () => {
  const fingerprint = await (
    await import("../src/trust.js")
  ).checkRevocation(key.raw);
  const policy = {
    version: 2,
    asOf: "2026-10-27T00:00:00Z",
    revoked: [
      {
        fingerprint: fingerprint.fingerprint,
        reason: "Fixture revoked",
        revokedAt: "2026-10-26T00:00:00Z",
      },
    ],
  };
  const revoked = await createVerifier([key.anchor], policy)(valid);
  assert.equal(revoked.verdict, "REVOKED KEY");
  assert.equal(revoked.genuine, false);
  assert.equal(revoked.payload, undefined);
});
