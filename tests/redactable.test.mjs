import test from "node:test";
import assert from "node:assert/strict";
import { sign as nodeSign, generateKeyPairSync } from "node:crypto";
import { mkdtemp, writeFile, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync, execFileSync } from "node:child_process";
import { signer, png } from "./fixtures.mjs";
import {
  sealRgba,
  encodeGRD2,
  verifyGRD2,
  redactGRD2,
  tileBounds,
  tilesForRect,
  verificationReport,
  base64,
  decodeBase64,
  IntegrityError,
} from "../src/redactable.js";
import { decodeRgbPng, encodeRgbPng } from "../src/png.js";
import { checkRevocation } from "../src/trust.js";
const key = signer(),
  width = 131,
  height = 67,
  rgba = new Uint8Array(width * height * 4);
for (let y = 0; y < height; y++)
  for (let x = 0; x < width; x++)
    rgba.set(
      [(x * 3) % 256, (y * 7) % 256, (x + y) % 256, 255],
      (y * width + x) * 4,
    );
const doc = await sealRgba({
  rgba,
  width,
  height,
  tileSize: 64,
  publicKey: key.raw,
  sign: (b) => nodeSign(null, Buffer.from(b), key.privateKey),
});
const verify = (bytes) => verifyGRD2(bytes, [key.anchor]);
const mutate = (fn) => {
  const copy = structuredClone(doc);
  fn(copy);
  return encodeGRD2(copy);
};
const parse = (bytes) => JSON.parse(new TextDecoder().decode(bytes).slice(5));
async function editPixel(document, x, y) {
  const copy = structuredClone(document),
    decoded = await decodeRgbPng(
      Uint8Array.from(atob(copy.image), (c) => c.charCodeAt(0)),
    );
  decoded.rgb[(y * width + x) * 3] ^= 128;
  copy.image = base64(await encodeRgbPng(decoded.rgb, width, height));
  return encodeGRD2(copy);
}
test("GRD2 preserves exact canonical pixels, partial-edge tiles and trusted signature", async () => {
  const r = await verify(encodeGRD2(doc));
  assert.equal(r.verdict, "GENUINE");
  assert.equal(r.tilesTotal, 6);
  assert.deepEqual(r.imageRgba, rgba);
});
test("redaction preserves manifest and signature, drops salts and records precise tiles", async () => {
  const output = await redactGRD2(doc, [1, 4]),
    r = await verify(output),
    copy = parse(output);
  assert.equal(r.verdict, "VERIFIED WITH REDACTIONS");
  assert.equal(r.genuine, false);
  assert.equal(r.viewable, true);
  assert.deepEqual(r.redactedTiles, [1, 4]);
  assert.deepEqual(copy.manifest, doc.manifest);
  assert.equal(copy.signature, doc.signature);
  for (const i of [1, 4]) {
    assert.deepEqual(Object.keys(copy.tiles[i]).sort(), [
      "commitment",
      "index",
    ]);
    assert.ok(!new TextDecoder().decode(output).includes(doc.tiles[i].salt));
  }
  for (const i of [0, 2, 3, 5]) {
    const b = tileBounds(doc.manifest, i);
    for (let row = 0; row < b.height; row++) {
      const at = ((b.y + row) * width + b.x) * 4;
      assert.deepEqual(
        r.imageRgba.subarray(at, at + b.width * 4),
        rgba.subarray(at, at + b.width * 4),
      );
    }
  }
});
test("non-redacted pixel edits name the failing tile", async () => {
  const r = await verify(await editPixel(doc, 65, 1));
  assert.equal(r.verdict, "TAMPERED");
  assert.match(r.problems.join(" "), /tile 1/);
  assert.equal(r.imageRgba, undefined);
});
test("redacted pixels are explicitly unverified and cannot become genuine content", async () => {
  const redacted = parse(await redactGRD2(doc, [1]));
  const r = await verify(await editPixel(redacted, 65, 1));
  assert.equal(r.verdict, "TAMPERED");
  assert.equal(r.viewable, false);
  assert.equal(r.genuine, false);
});
test("guessed original pixels and salt cannot un-redact a tile", async () => {
  const redacted = parse(await redactGRD2(doc, [1]));
  redacted.tiles[1] = { index: 1, salt: "0".repeat(32) };
  redacted.redactions = [];
  assert.equal((await verify(encodeGRD2(redacted))).viewable, false);
});
test("swaps, salt changes, commitment changes and signed-metadata edits fail", async () => {
  for (const attack of [
    (d) => (d.tiles[0].salt = "f".repeat(32)),
    (d) => ([d.tiles[0], d.tiles[1]] = [d.tiles[1], d.tiles[0]]),
    (d) => d.manifest.width++,
    (d) => (d.manifest.root = "a".repeat(64)),
    (d) => d.manifest.commitments.reverse(),
    (d) => (d.manifest.tileSize = 128),
  ])
    assert.equal((await verify(mutate(attack))).viewable, false);
});
test("REDACTIONS must exactly agree with TILES; removing, altering or duplicating an entry fails", async () => {
  const original = parse(await redactGRD2(doc, [1, 4]));
  for (const attack of [
    (d) => d.redactions.pop(),
    (d) => (d.redactions[0].index = 0),
    (d) => (d.redactions[0].method = "unknown"),
    (d) => d.redactions.push(d.redactions[0]),
    (d) => (d.tiles[1].commitment = "0".repeat(64)),
  ]) {
    const copy = structuredClone(original);
    attack(copy);
    assert.equal((await verify(encodeGRD2(copy))).viewable, false);
  }
});
test("crop, missing tile, extra payload, duplicate index and appended bytes fail", async () => {
  for (const attack of [
    (d) => d.tiles.pop(),
    (d) => d.tiles.push(d.tiles[0]),
    (d) => (d.tiles[1].index = 0),
    (d) => (d.tiles[0].original = "private"),
    (d) => (d.extra = "data"),
  ])
    assert.equal((await verify(mutate(attack))).viewable, false);
  const b = encodeGRD2(doc),
    extra = new Uint8Array(b.length + 1);
  extra.set(b);
  assert.equal((await verify(extra)).viewable, false);
});
test("unknown and demonstration signers are never called genuine", async () => {
  const u = await verifyGRD2(encodeGRD2(doc), []);
  assert.equal(u.verdict, "UNTRUSTED SIGNER");
  assert.equal(u.imageRgba, undefined);
  const demo = await sealRgba({
    rgba,
    width,
    height,
    publicKey: key.raw,
    purpose: "demo",
    sign: (b) => nodeSign(null, Buffer.from(b), key.privateKey),
  });
  const r = await verify(encodeGRD2(demo));
  assert.equal(r.verdict, "DEMO");
  assert.equal(r.genuine, false);
});
test("fully redacted files make no visible authenticity claim", async () => {
  const r = await verify(
    await redactGRD2(
      doc,
      doc.tiles.map((t) => t.index),
    ),
  );
  assert.equal(r.verdict, "FULLY REDACTED");
  assert.equal(r.viewable, false);
});
test("chained blackout exports preserve the union and original signed root", async () => {
  const first = parse(await redactGRD2(doc, [0]));
  const second = await redactGRD2(first, [2, 5], "black"),
    r = await verify(second);
  assert.equal(r.root, doc.manifest.root);
  assert.deepEqual(r.redactedTiles, [0, 2, 5]);
  assert.deepEqual(parse(second).redactions, [
    { index: 0, method: "black" },
    { index: 2, method: "black" },
    { index: 5, method: "black" },
  ]);
});
test("rectangles round up to intersecting 64px tiles including edge tiles", () => {
  assert.deepEqual(
    tilesForRect(doc.manifest, { x: 63, y: 0, width: 2, height: 1 }),
    [0, 1],
  );
  assert.deepEqual(
    tilesForRect(doc.manifest, { x: 130, y: 66, width: 1, height: 1 }),
    [5],
  );
});
test("report includes redaction map but no image, salts or complete container", async () => {
  const report = verificationReport(await verify(await redactGRD2(doc, [1])));
  assert.equal(report.imageRgba, undefined);
  assert.equal(report.container, undefined);
  assert.equal(report.payload, undefined);
  assert.deepEqual(report.redactionMap, [
    {
      index: 1,
      x: 64,
      y: 0,
      width: 64,
      height: 64,
      claimedMethod: "black",
      methodAttested: false,
    },
  ]);
  assert.ok(!JSON.stringify(report).includes(doc.tiles[0].salt));
});
test("independent salts produce different roots for identical pixels", async () => {
  const other = await sealRgba({
    rgba,
    width,
    height,
    publicKey: key.raw,
    sign: (b) => nodeSign(null, Buffer.from(b), key.privateKey),
  });
  assert.notEqual(other.manifest.root, doc.manifest.root);
});
test("revoked signer is rejected offline despite a valid signature", async () => {
  const fingerprint = (await checkRevocation(key.raw)).fingerprint,
    policy = {
      version: 2,
      asOf: "2026-10-27T00:00:00Z",
      revoked: [
        {
          fingerprint,
          reason: "Test compromise",
          revokedAt: "2026-10-26T00:00:00Z",
        },
      ],
    };
  const r = await verifyGRD2(encodeGRD2(doc), [key.anchor], policy);
  assert.equal(r.verdict, "REVOKED KEY");
  assert.equal(r.viewable, false);
  assert.equal(r.imageRgba, undefined);
});
test("thousands of random single-bit changes to a GRD2 never verify", async (t) => {
  const bytes = encodeGRD2(doc);
  let seed = 731;
  for (let i = 0; i < 2000; i++) {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    const at = seed % bytes.length,
      copy = bytes.slice();
    copy[at] ^= 1 << (seed % 8);
    assert.equal(
      (await verify(copy)).viewable,
      false,
      "Accepted bit edit at " + at,
    );
  }
  t.diagnostic("2,000 deterministic random single-bit mutations rejected.");
});
test("Python and JS verify and redact each other’s output", async () => {
  const { mkdtemp, writeFile, readFile, rm } = await import("node:fs/promises"),
    { tmpdir } = await import("node:os"),
    { join } = await import("node:path"),
    { execFileSync } = await import("node:child_process");
  const dir = await mkdtemp(join(tmpdir(), "guard-parity-"));
  try {
    const input = join(dir, "source.GRD"),
      pem = join(dir, "public.pem"),
      redacted = join(dir, "redacted.GRD"),
      privatePem = join(dir, "private.pem"),
      image = join(dir, "input.png"),
      sealed = join(dir, "python.GRD");
    await writeFile(input, encodeGRD2(doc));
    await writeFile(pem, key.publicKey.export({ type: "spki", format: "pem" }));
    await writeFile(
      privatePem,
      key.privateKey.export({ type: "pkcs8", format: "pem" }),
      { mode: 0o600 },
    );
    const run = (args) =>
      execFileSync("python3", ["grd.py", ...args], {
        cwd: new URL("../", import.meta.url),
        encoding: "utf8",
        stdio: "pipe",
      });
    const report = (args) => {
      try {
        return JSON.parse(run(args));
      } catch (e) {
        if (e.stdout) return JSON.parse(e.stdout);
        throw e;
      }
    };
    assert.equal(
      JSON.parse(run(["verify", input, "--trusted-key", pem])).verdict,
      "GENUINE",
    );
    run(["redact", input, "--rect", "65,1,2,2", "-o", redacted]);
    assert.equal(
      (await verify(await readFile(redacted))).verdict,
      "VERIFIED WITH REDACTIONS",
    );
    const js = await redactGRD2(doc, [1, 4]);
    await writeFile(input, js);
    assert.deepEqual(
      report(["verify", input, "--trusted-key", pem]).redactedTiles,
      [1, 4],
    );
    await writeFile(image, png(70, 68));
    run(["seal", image, "--key", privatePem, "-o", sealed]);
    assert.equal((await verify(await readFile(sealed))).genuine, true);
    const personal = await sealRgba({
      rgba,
      width,
      height,
      publicKey: key.raw,
      purpose: "personal",
      sign: (b) => nodeSign(null, Buffer.from(b), key.privateKey),
    });
    await writeFile(input, encodeGRD2(personal));
    const personalReport = await verify(await readFile(input));
    assert.equal(personalReport.verdict, "UNVERIFIED: SELF-SIGNED");
    assert.equal(personalReport.genuine, false);
    assert.equal(personalReport.trusted, false);
    assert.equal(personalReport.viewable, true);
    assert.equal(
      report(["verify", input, "--trusted-key", pem]).verdict,
      "UNVERIFIED: SELF-SIGNED",
    );
    assert.throws(
      () => run(["verify", input, "--trusted-key", pem]),
      (e) => e.status === 5,
    );
    const hiddenPersonal = await redactGRD2(personal, [0]);
    assert.equal(
      (await verify(hiddenPersonal)).verdict,
      "UNVERIFIED: SELF-SIGNED",
    );
    const revokedPersonal = await verifyGRD2(
      encodeGRD2(personal),
      [key.anchor],
      {
        version: 2,
        asOf: "2026-10-27T00:00:00Z",
        revoked: [
          {
            fingerprint: personal.manifest.keyId,
            reason: "Test only",
            revokedAt: "2026-10-26T00:00:00Z",
          },
        ],
      },
    );
    assert.equal(revokedPersonal.verdict, "REVOKED KEY");
    const unicode = await sealRgba({
      rgba,
      width,
      height,
      publicKey: key.raw,
      label: "Café / 顔 / 🔒",
      sign: (b) => nodeSign(null, Buffer.from(b), key.privateKey),
    });
    await writeFile(input, encodeGRD2(unicode));
    assert.equal(
      JSON.parse(run(["verify", input, "--trusted-key", pem])).verdict,
      "GENUINE",
    );
    unicode.tiles[0].index = false;
    await writeFile(input, encodeGRD2(unicode));
    assert.equal((await verify(await readFile(input))).viewable, false);
    assert.throws(
      () => run(["verify", input, "--trusted-key", pem]),
      (e) => JSON.parse(e.stdout).verdict === "TAMPERED",
    );
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("GRD2 at the 4-megapixel / 1024-tile limit with photo-like noise verifies", async () => {
  const w = 2496,
    h = 1662;
  const bigRgba = new Uint8Array(w * h * 4);
  let seed = 123456789;
  for (let i = 0; i < bigRgba.length; i += 4) {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    bigRgba[i] = seed & 0xff;
    bigRgba[i + 1] = (seed >>> 8) & 0xff;
    bigRgba[i + 2] = (seed >>> 16) & 0xff;
    bigRgba[i + 3] = 255;
  }
  const { publicKey: pubKeyObj, privateKey: privKeyObj } = generateKeyPairSync("ed25519");
  const rawPub = pubKeyObj.export({ type: "spki", format: "der" }).subarray(-32);
  const bigDoc = await sealRgba({
    rgba: bigRgba,
    width: w,
    height: h,
    publicKey: rawPub,
    purpose: "personal",
    sign: (b) => nodeSign(null, Buffer.from(b), privKeyObj),
  });
  const encoded = encodeGRD2(bigDoc);
  const rep = await verifyGRD2(encoded, []);
  assert.equal(rep.verdict, "UNVERIFIED: SELF-SIGNED");
  assert.equal(rep.viewable, true);

  const dir = await mkdtemp(join(tmpdir(), "grd-big-"));
  try {
    const file = join(dir, "big.GRD");
    await writeFile(file, encoded);
    const proc = spawnSync("python3", ["grd.py", "verify", file], {
      cwd: new URL("../", import.meta.url),
      encoding: "utf8",
    });
    assert.equal(proc.status, 5);
    const out = JSON.parse(proc.stdout);
    assert.equal(out.verdict, "UNVERIFIED: SELF-SIGNED");
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("decodeBase64 rejects bad shapes without throwing RangeError", () => {
  assert.throws(() => decodeBase64("abc"), IntegrityError);
  assert.throws(() => decodeBase64("A==="), IntegrityError);
  assert.throws(() => decodeBase64("AB=C"), IntegrityError);

  const valid12M = "QUJD".repeat(3_000_000);
  const decoded = decodeBase64(valid12M);
  assert.equal(decoded.length, 9_000_000);

  const withStar = "QUJD".repeat(1_500_000) + "*" + "QUJD".repeat(1_500_000).slice(1);
  assert.throws(() => decodeBase64(withStar), IntegrityError);
});

test("internal error maps to CANNOT VERIFY, while pixel edit maps to TAMPERED", async () => {
  const origDigest = crypto.subtle.digest;
  try {
    crypto.subtle.digest = async () => {
      throw new RangeError("Simulated internal recursion limit");
    };
    const rep = await verifyGRD2(encodeGRD2(doc), [key.anchor]);
    assert.equal(rep.verdict, "CANNOT VERIFY");
    assert.equal(rep.viewable, false);
    assert.equal(rep.genuine, false);
  } finally {
    crypto.subtle.digest = origDigest;
  }

  const tamperedBytes = await editPixel(doc, 10, 10);
  const tamperedRep = await verify(tamperedBytes);
  assert.equal(tamperedRep.verdict, "TAMPERED");
});

test("hidden tiles non-zero pixel check flags hiddenPixelsCleared: false", async () => {
  const redactedBytes = await redactGRD2(doc, [0]);
  const repClean = await verify(redactedBytes);
  assert.equal(repClean.hiddenPixelsCleared, true);

  const dirtyDoc = parse(redactedBytes);
  const decoded = await decodeRgbPng(decodeBase64(dirtyDoc.image));
  const b = tileBounds(dirtyDoc.manifest, 0);
  const offset = (b.y * dirtyDoc.manifest.width + b.x) * 3;
  decoded.rgb[offset] = 1;
  decoded.rgb[offset + 1] = 2;
  decoded.rgb[offset + 2] = 3;
  dirtyDoc.image = base64(
    await encodeRgbPng(decoded.rgb, dirtyDoc.manifest.width, dirtyDoc.manifest.height),
  );

  const encodedDirty = encodeGRD2(dirtyDoc);
  const repDirty = await verify(encodedDirty);
  assert.equal(repDirty.hiddenPixelsCleared, false);
  assert.equal(repDirty.verdict, "TAMPERED");
  assert.ok(
    repDirty.problems.some((p) =>
      p.includes("blackout incomplete (tile 0)"),
    ),
  );

  const dir = await mkdtemp(join(tmpdir(), "grd-dirty-"));
  try {
    const file = join(dir, "dirty.GRD");
    await writeFile(file, encodedDirty);
    const proc = spawnSync("python3", ["grd.py", "verify", file], {
      cwd: new URL("../", import.meta.url),
      encoding: "utf8",
    });
    const out = JSON.parse(proc.stdout);
    assert.equal(out.hiddenPixelsCleared, false);
    assert.equal(out.verdict, "TAMPERED");
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});
