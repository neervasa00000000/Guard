import test from "node:test";
import assert from "node:assert/strict";
import { sign } from "node:crypto";
import { mkdtemp, writeFile, rm, readFile, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { inflateSync, deflateSync } from "node:zlib";
import { signer, makeGRD } from "./fixtures.mjs";
import { createVerifier } from "../src/verifier.js";
import {
  sealRgba,
  encodeGRD2,
  verifyGRD2,
  redactGRD2,
  base64,
} from "../src/redactable.js";
import { decodeRgbPng, encodeRgbPng } from "../src/png.js";

const key = signer(),
  rgba = new Uint8Array(128 * 64 * 4).fill(255);
const seal = (purpose = "asset", pixels = rgba) =>
  sealRgba({
    rgba: pixels,
    width: 128,
    height: 64,
    publicKey: key.raw,
    purpose,
    sign: (b) => sign(null, b, key.privateKey),
  });
const original = await seal();
test("issuer setup creates private keys with restricted permissions and refuses replacement", () =>
  withPython(async (run, dir) => {
    const privatePath = join(dir, "issuer.pem"),
      publicPath = join(dir, "issuer-public.pem");
    const args = [
      "scripts/create-signer.mjs",
      "--private",
      privatePath,
      "--public",
      publicPath,
      "--owner",
      "TEST ONLY issuer",
    ];
    const first = spawnSync("node", args, {
      cwd: new URL("../", import.meta.url),
      encoding: "utf8",
    });
    assert.equal(first.status, 0, first.stderr);
    assert.ok(!first.stdout.includes("BEGIN PRIVATE KEY"));
    assert.ok(first.stdout.includes("public_key_hex"));
    assert.equal((await stat(privatePath)).mode & 0o777, 0o600);
    const before = await readFile(privatePath);
    const again = spawnSync("node", args, {
      cwd: new URL("../", import.meta.url),
      encoding: "utf8",
    });
    assert.notEqual(again.status, 0);
    assert.deepEqual(await readFile(privatePath), before);
  }));
async function withPython(fn) {
  const dir = await mkdtemp(join(tmpdir(), "guard-security-"));
  const input = join(dir, "input.GRD"),
    pem = join(dir, "public.pem");
  await writeFile(pem, key.publicKey.export({ type: "spki", format: "pem" }));
  const run = async (bytes, policy) => {
    await writeFile(input, bytes);
    const args = ["grd.py", "verify", input, "--trusted-key", pem];
    if (policy) {
      const path = join(dir, "policy.json");
      await writeFile(path, JSON.stringify(policy));
      args.push("--policy", path);
    }
    const out = spawnSync("python3", args, {
      cwd: new URL("../", import.meta.url),
      encoding: "utf8",
    });
    assert.ok(out.stdout, out.stderr);
    return { status: out.status, report: JSON.parse(out.stdout) };
  };
  try {
    await fn(run, dir, input);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}
test("CLI passes only GENUINE; edited and re-signed personal files stay unverified", () =>
  withPython(async (run) => {
    const changed = rgba.slice();
    changed[0] = 0;
    const cases = [
      [encodeGRD2(original), "GENUINE", 0],
      [await redactGRD2(original, [0]), "VERIFIED WITH REDACTIONS", 2],
      [await redactGRD2(original, [0, 1]), "FULLY REDACTED", 2],
      [encodeGRD2(await seal("personal")), "UNVERIFIED: SELF-SIGNED", 2],
      [
        encodeGRD2(await seal("personal", changed)),
        "UNVERIFIED: SELF-SIGNED",
        2,
      ],
      [encodeGRD2(await seal("demo")), "DEMO", 2],
    ];
    for (const [bytes, verdict, status] of cases) {
      const js = await verifyGRD2(bytes, [key.anchor]),
        py = await run(bytes);
      assert.equal(js.verdict, verdict);
      assert.equal(py.report.verdict, verdict);
      assert.equal(py.status, status);
      assert.equal(js.genuine, verdict === "GENUINE");
    }
  }));
test("blackout clears all hidden pixels, rejects blur exports and treats method as an unsigned claim", () =>
  withPython(async (run, dir, input) => {
    await assert.rejects(redactGRD2(original, [0], "blur"), /Only blackout/);
    const legacy = JSON.parse(
      new TextDecoder().decode((await redactGRD2(original, [0])).subarray(5)),
    );
    const pixels = (await decodeRgbPng(Buffer.from(legacy.image, "base64")))
      .rgb;
    for (let y = 0; y < 64; y++)
      pixels.fill(123, y * 128 * 3, y * 128 * 3 + 64 * 3);
    legacy.image = base64(await encodeRgbPng(pixels, 128, 64));
    legacy.redactions[0].method = "blur";
    const bytes = encodeGRD2(legacy),
      report = await verifyGRD2(bytes, [key.anchor]);
    assert.equal(report.redactionMap[0].claimedMethod, "blur");
    assert.equal(report.redactionMap[0].methodAttested, false);
    assert.deepEqual(
      (await run(bytes)).report.redactionMap,
      report.redactionMap,
    );
    const sanitized = JSON.parse(
      new TextDecoder().decode((await redactGRD2(legacy, [0])).subarray(5)),
    );
    const rgb = (await decodeRgbPng(Buffer.from(sanitized.image, "base64")))
      .rgb;
    for (let y = 0; y < 64; y++)
      assert.ok(
        rgb.subarray(y * 128 * 3, y * 128 * 3 + 64 * 3).every((n) => n === 0),
      );
    assert.deepEqual(sanitized.manifest, original.manifest);
    assert.equal(sanitized.signature, original.signature);
    const output = join(dir, "black.GRD");
    const cli = spawnSync(
      "python3",
      ["grd.py", "redact", input, "--rect", "0,0,1,1", "-o", output],
      { cwd: new URL("../", import.meta.url), encoding: "utf8" },
    );
    assert.equal(cli.status, 0, cli.stderr);
    const { readFile } = await import("node:fs/promises");
    const pyDoc = JSON.parse((await readFile(output, "utf8")).slice(5));
    const pyRgb = (await decodeRgbPng(Buffer.from(pyDoc.image, "base64"))).rgb;
    assert.deepEqual(pyRgb, rgb);
  }));
test("legacy canonical JSON agrees for Unicode keys and rejects fractional or unsafe numbers", () =>
  withPython(async (run) => {
    const verify = createVerifier([key.anchor]);
    for (const meta of [
      { notes: { "\ue000": "one", "😀": "two" } },
      { score: 0.5 },
      { score: 9007199254740992 },
      { width: true },
      { notes: "\ud800" },
    ]) {
      const bytes = makeGRD(key, { meta }),
        js = await verify(bytes),
        py = await run(bytes);
      assert.equal(py.report.genuine, js.genuine, JSON.stringify(meta));
      assert.equal(py.status, js.genuine ? 0 : 2);
    }
  }));
test("invalid or impossible offline-policy dates fail closed in both checkers", () =>
  withPython(async (run) => {
    for (const asOf of [
      "2026-02-30T00:00:00Z",
      "2026-10-27",
      "0000-01-01T00:00:00Z",
    ]) {
      const policy = { version: 1, asOf, revoked: [] },
        bytes = encodeGRD2(original);
      assert.equal(
        (await verifyGRD2(bytes, [key.anchor], policy)).genuine,
        false,
      );
      assert.equal((await run(bytes, policy)).status, 2);
    }
  }));
test("extra decompressed PNG bytes are rejected by both checkers", () =>
  withPython(async (run) => {
    const png = Buffer.from(original.image, "base64");
    let at = 8,
      packed;
    while (at < png.length) {
      const size = png.readUInt32BE(at);
      if (png.toString("ascii", at + 4, at + 8) === "IDAT") {
        packed = png.subarray(at + 8, at + 8 + size);
        break;
      }
      at += size + 12;
    }
    const compressed = deflateSync(
        Buffer.concat([inflateSync(packed), Buffer.from([0])]),
      ),
      chunk = Buffer.alloc(compressed.length + 12);
    chunk.writeUInt32BE(compressed.length);
    chunk.write("IDAT", 4);
    compressed.copy(chunk, 8);
    let crc = 0xffffffff;
    for (const b of chunk.subarray(4, -4)) {
      crc ^= b;
      for (let k = 0; k < 8; k++)
        crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
    chunk.writeUInt32BE((crc ^ 0xffffffff) >>> 0, chunk.length - 4);
    const image = Buffer.concat([
        png.subarray(0, at),
        chunk,
        png.subarray(at + 12 + packed.length),
      ]),
      doc = structuredClone(original);
    doc.image = base64(image);
    const bytes = encodeGRD2(doc);
    assert.equal((await verifyGRD2(bytes, [key.anchor])).viewable, false);
    assert.equal((await run(bytes)).status, 2);
  }));
