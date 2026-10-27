// SPDX-License-Identifier: MIT
// Ephemeral QA trust anchor only. Never copy the generated QA viewer to production.
import { mkdir, writeFile, readFile } from "node:fs/promises";
import { signer, makeGRD, png } from "../tests/fixtures.mjs";
import { TRUSTED } from "../src/verifier.js";
import { sign } from "node:crypto";
import { sealRgba, encodeGRD2, redactGRD2 } from "../src/redactable.js";
const dir = "/tmp/guard-qa";
await mkdir(dir, { recursive: true });
const key = signer(),
  valid = makeGRD(key, {
    image: png(960, 640),
    width: 960,
    height: 640,
    meta: {
      author: "Generated QA fixture",
      original_filename: "fixture-landscape.png",
    },
  });
let html = await readFile(
  new URL("../grd_viewer.html", import.meta.url),
  "utf8",
);
for (const field of ["key_id", "public_key_hex", "owner"])
  html = html.replace(TRUSTED[0][field], key.anchor[field]);
html = html.replace("<title>Guard /", "<title>QA FIXTURE ONLY — Guard /");
const bad = Buffer.from(valid);
const rgba = new Uint8Array(192 * 128 * 4).fill(255);
for (let i = 0; i < 192 * 128; i++)
  rgba.set([i % 192, Math.floor(i / 192), 120, 255], i * 4);
const v2 = await sealRgba({
  rgba,
  width: 192,
  height: 128,
  publicKey: key.raw,
  label: "QA FIXTURE ONLY",
  sign: (b) => sign(null, b, key.privateKey),
});
const v2redacted = await redactGRD2(v2, [0, 1]);
const revokedHtml = html.replace(
  /"revoked"\s*:\s*\[\]/,
  JSON.stringify({
    revoked: [
      {
        fingerprint: v2.manifest.keyId,
        reason: "QA ONLY revoked test signer",
        revokedAt: "2026-10-26T00:00:00Z",
      },
    ],
  }).slice(1, -1),
);
const tamperedV2 = structuredClone(v2);
tamperedV2.manifest.label = "Changed label";
const imageTable = 10 + 50;
const imageOffset = Number(bad.readBigUInt64LE(imageTable + 2));
bad[imageOffset + 40] ^= 1;
await Promise.all([
  writeFile(dir + "/index.html", html),
  writeFile(dir + "/revoked.html", revokedHtml),
  writeFile(dir + "/genuine-v2.GRD", encodeGRD2(v2)),
  writeFile(dir + "/redacted-v2.GRD", v2redacted),
  writeFile(dir + "/tampered-v2.GRD", encodeGRD2(tamperedV2)),
  writeFile(dir + "/genuine-test.GRD", valid),
  writeFile(dir + "/tampered-test.GRD", bad),
  writeFile(dir + "/not-a-grd.GRD", "not a signed image"),
  writeFile(
    dir + "/wrong-dimensions.GRD",
    makeGRD(key, { image: png(100, 80), width: 120, height: 80 }),
  ),
  writeFile(dir + "/unknown-key.GRD", makeGRD(signer())),
]);
console.log(
  "Temporary QA files written to " +
    dir +
    ". The production trust list is unchanged.",
);
