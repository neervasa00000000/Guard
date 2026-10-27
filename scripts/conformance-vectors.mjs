// SPDX-License-Identifier: MIT
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createPrivateKey, createPublicKey, createHash, sign as nodeSign } from "node:crypto";
import { sealRgba, encodeGRD2, redactGRD2, tileBounds, base64, decodeBase64 } from "../src/redactable.js";
import { encodeRgbPng, decodeRgbPng } from "../src/png.js";
import { makeGRD, png, hash } from "../tests/fixtures.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const conformanceDir = join(root, "conformance");
const filesDir = join(conformanceDir, "files");

await mkdir(filesDir, { recursive: true });

function makeDeterministicKey(seedByte) {
  const seed = Buffer.alloc(32, seedByte);
  const priv = createPrivateKey({
    key: Buffer.concat([Buffer.from("302e020100300506032b657004220420", "hex"), seed]),
    format: "der",
    type: "pkcs8",
  });
  const pub = createPublicKey(priv);
  const raw = pub.export({ type: "spki", format: "der" }).subarray(-32);
  const fp = createHash("sha256").update(raw).digest("hex");
  const kid = fp.slice(0, 16);
  return {
    privateKey: priv,
    publicKey: pub,
    raw,
    id: Buffer.from(kid, "hex"),
    hex: raw.toString("hex"),
    fingerprint: fp,
    keyId: kid,
    anchor: {
      key_id: kid,
      public_key_hex: raw.toString("hex"),
      fingerprint_sha256: fp,
      name: `Conformance Signer ${seedByte}`,
      owner: `Conformance Signer ${seedByte}`,
      alg: "Ed25519",
    },
  };
}

const trustedKey = makeDeterministicKey(42);
const revokedKey = makeDeterministicKey(99);
const unknownKey = makeDeterministicKey(77);

const trustedKeysDoc = {
  version: 1,
  asOf: "2026-10-27T00:00:00Z",
  signers: [
    {
      key_id: trustedKey.keyId,
      public_key_hex: trustedKey.hex,
      fingerprint_sha256: trustedKey.fingerprint,
      name: "Conformance Trusted Signer",
      alg: "Ed25519",
      revoked: false,
      revokedAt: null,
      reason: null,
    },
    {
      key_id: revokedKey.keyId,
      public_key_hex: revokedKey.hex,
      fingerprint_sha256: revokedKey.fingerprint,
      name: "Conformance Revoked Signer",
      alg: "Ed25519",
      revoked: true,
      revokedAt: "2026-10-26T00:00:00Z",
      reason: "Revoked for conformance testing",
    },
  ],
};

await writeFile(
  join(conformanceDir, "trusted-keys.test.json"),
  JSON.stringify(trustedKeysDoc, null, 2) + "\n",
);

const vectors = [];

async function addVector({ id, description, format, bytes, expectedVerdict, expectedExit, hiddenPixelsCleared }) {
  const filename = `${id}.GRD`;
  const relPath = `conformance/files/${filename}`;
  await writeFile(join(filesDir, filename), bytes);
  const v = {
    id,
    file: relPath,
    description,
    format,
    expected_verdict: expectedVerdict,
    expected_exit: expectedExit,
  };
  if (hiddenPixelsCleared !== undefined) {
    v.expected_hidden_pixels_cleared = hiddenPixelsCleared;
  }
  vectors.push(v);
}

// -------------------------------------------------------------
// GRD1 Vectors
// -------------------------------------------------------------
const baseGrd1 = makeGRD(trustedKey);
await addVector({
  id: "grd1-genuine",
  description: "Valid GRD1 signed by trusted key",
  format: 1,
  bytes: baseGrd1,
  expectedVerdict: "GENUINE",
  expectedExit: 0,
});

const metadataEditGrd1 = Buffer.from(baseGrd1);
// Modify byte in metadata section
metadataEditGrd1[120] ^= 1;
await addVector({
  id: "grd1-metadata-edit",
  description: "GRD1 with flipped bit in metadata section",
  format: 1,
  bytes: metadataEditGrd1,
  expectedVerdict: "TAMPERED",
  expectedExit: 2,
});

const imageFlipGrd1 = Buffer.from(baseGrd1);
// Flip a bit in the image section (starts around offset 450)
imageFlipGrd1[500] ^= 1;
await addVector({
  id: "grd1-one-bit-image-flip",
  description: "GRD1 with flipped bit in image section",
  format: 1,
  bytes: imageFlipGrd1,
  expectedVerdict: "TAMPERED",
  expectedExit: 2,
});

const trailingGrd1 = Buffer.concat([baseGrd1, Buffer.from([0xaa])]);
await addVector({
  id: "grd1-trailing-byte",
  description: "GRD1 with extra trailing byte appended",
  format: 1,
  bytes: trailingGrd1,
  expectedVerdict: "TAMPERED",
  expectedExit: 2,
});

// Duplicate section in table
const dupSectionGrd1 = Buffer.from(baseGrd1);
dupSectionGrd1.writeUInt16LE(1, 10 + 50); // change second section type to 1 (duplicate metadata)
await addVector({
  id: "grd1-duplicate-section",
  description: "GRD1 section table containing duplicate section types",
  format: 1,
  bytes: dupSectionGrd1,
  expectedVerdict: "TAMPERED",
  expectedExit: 2,
});

const unknownKeyGrd1 = makeGRD(unknownKey);
await addVector({
  id: "grd1-unknown-key",
  description: "GRD1 signed by key absent from trusted-keys.test.json",
  format: 1,
  bytes: unknownKeyGrd1,
  expectedVerdict: "UNTRUSTED SIGNER",
  expectedExit: 5,
});

const revokedKeyGrd1 = makeGRD(revokedKey);
await addVector({
  id: "grd1-revoked-key",
  description: "GRD1 signed by key marked revoked in trusted-keys.test.json",
  format: 1,
  bytes: revokedKeyGrd1,
  expectedVerdict: "REVOKED KEY",
  expectedExit: 6,
});

// -------------------------------------------------------------
// GRD2 Vectors
// -------------------------------------------------------------
const width = 128;
const height = 128;
const baseRgba = new Uint8Array(width * height * 4);
for (let y = 0; y < height; y++) {
  for (let x = 0; x < width; x++) {
    const idx = (y * width + x) * 4;
    baseRgba[idx] = (x * 2) % 256;
    baseRgba[idx + 1] = (y * 2) % 256;
    baseRgba[idx + 2] = 128;
    baseRgba[idx + 3] = 255;
  }
}

const personalDoc = await sealRgba({
  rgba: baseRgba,
  width,
  height,
  publicKey: trustedKey.raw,
  purpose: "personal",
  label: "Personal Photo",
  sign: (b) => nodeSign(null, Buffer.from(b), trustedKey.privateKey),
});
await addVector({
  id: "grd2-personal",
  description: "GRD2 self-signed personal file",
  format: 2,
  bytes: encodeGRD2(personalDoc),
  expectedVerdict: "UNVERIFIED: SELF-SIGNED",
  expectedExit: 5,
});

const demoDoc = await sealRgba({
  rgba: baseRgba,
  width,
  height,
  publicKey: trustedKey.raw,
  purpose: "demo",
  label: "Demo Asset",
  sign: (b) => nodeSign(null, Buffer.from(b), trustedKey.privateKey),
});
await addVector({
  id: "grd2-demo",
  description: "GRD2 demonstration file with purpose: demo",
  format: 2,
  bytes: encodeGRD2(demoDoc),
  expectedVerdict: "DEMO",
  expectedExit: 5,
});

const trustedDoc = await sealRgba({
  rgba: baseRgba,
  width,
  height,
  publicKey: trustedKey.raw,
  purpose: "asset",
  label: "Certified Asset",
  sign: (b) => nodeSign(null, Buffer.from(b), trustedKey.privateKey),
});
const trustedEncoded = encodeGRD2(trustedDoc);
await addVector({
  id: "grd2-trusted-asset",
  description: "GRD2 genuine asset signed by trusted key",
  format: 2,
  bytes: trustedEncoded,
  expectedVerdict: "GENUINE",
  expectedExit: 0,
});

const partialRedacted = await redactGRD2(trustedDoc, [0]);
await addVector({
  id: "grd2-partial-redaction",
  description: "GRD2 with partial blackout redaction of tile 0",
  format: 2,
  bytes: partialRedacted,
  expectedVerdict: "VERIFIED WITH REDACTIONS",
  expectedExit: 5,
  hiddenPixelsCleared: true,
});

const fullRedacted = await redactGRD2(trustedDoc, [0, 1, 2, 3]);
await addVector({
  id: "grd2-full-redaction",
  description: "GRD2 with all tiles blackout redacted",
  format: 2,
  bytes: fullRedacted,
  expectedVerdict: "FULLY REDACTED",
  expectedExit: 5,
  hiddenPixelsCleared: true,
});

// Non-black hidden tile: hidden tile contains non-zero pixels
const dirtyRedactedDoc = JSON.parse(new TextDecoder().decode(partialRedacted).slice(5));
const decodedImage = await decodeRgbPng(decodeBase64(dirtyRedactedDoc.image));
const bounds = tileBounds(dirtyRedactedDoc.manifest, 0);
decodedImage.rgb[((bounds.y) * width + bounds.x) * 3] = 255; // write non-zero pixel in hidden tile 0
dirtyRedactedDoc.image = base64(await encodeRgbPng(decodedImage.rgb, width, height));
await addVector({
  id: "grd2-dirty-hidden-tile",
  description: "GRD2 where blacked-out tile still carries underlying non-zero pixels",
  format: 2,
  bytes: encodeGRD2(dirtyRedactedDoc),
  expectedVerdict: "TAMPERED",
  expectedExit: 2,
  hiddenPixelsCleared: false,
});

// One-bit retained flip
const tamperedTileDoc = JSON.parse(new TextDecoder().decode(trustedEncoded).slice(5));
const decodedTampered = await decodeRgbPng(decodeBase64(tamperedTileDoc.image));
decodedTampered.rgb[100] ^= 1;
tamperedTileDoc.image = base64(await encodeRgbPng(decodedTampered.rgb, width, height));
await addVector({
  id: "grd2-retained-bit-flip",
  description: "GRD2 with single-bit flip inside retained tile",
  format: 2,
  bytes: encodeGRD2(tamperedTileDoc),
  expectedVerdict: "TAMPERED",
  expectedExit: 2,
});

// Label change
const labelChangedDoc = structuredClone(trustedDoc);
labelChangedDoc.manifest.label = "Modified Label";
await addVector({
  id: "grd2-label-change",
  description: "GRD2 with signed label changed in manifest",
  format: 2,
  bytes: encodeGRD2(labelChangedDoc),
  expectedVerdict: "TAMPERED",
  expectedExit: 2,
});

// Non-canonical JSON (extra space)
const nonCanonicalJson = Buffer.concat([
  Buffer.from("GRD2\n"),
  Buffer.from(JSON.stringify(trustedDoc, null, 2)),
]);
await addVector({
  id: "grd2-noncanonical-json",
  description: "GRD2 container formatted with non-canonical whitespace",
  format: 2,
  bytes: nonCanonicalJson,
  expectedVerdict: "TAMPERED",
  expectedExit: 2,
});

// Noncanonical base64
const badBase64Doc = structuredClone(trustedDoc);
badBase64Doc.image = badBase64Doc.image.slice(0, 10) + "_" + badBase64Doc.image.slice(11);
await addVector({
  id: "grd2-noncanonical-base64",
  description: "GRD2 container with invalid base64 character (_) in image payload",
  format: 2,
  bytes: encodeGRD2(badBase64Doc),
  expectedVerdict: "TAMPERED",
  expectedExit: 2,
});

// Oversized
const oversizedBytes = Buffer.concat([
  Buffer.from("GRD2\n"),
  Buffer.alloc(33 * 1024 * 1024, 0x20),
]);
await addVector({
  id: "grd2-oversized",
  description: "GRD2 file exceeding 32 MiB size limit",
  format: 2,
  bytes: oversizedBytes,
  expectedVerdict: "LIMIT EXCEEDED",
  expectedExit: 4,
});

// 4 MP noise personal photo
const wBig = 2496;
const hBig = 1662;
const bigRgba = new Uint8Array(wBig * hBig * 4);
let lcg = 123456789;
for (let i = 0; i < bigRgba.length; i += 4) {
  lcg = (lcg * 1664525 + 1013904223) >>> 0;
  bigRgba[i] = lcg & 0xff;
  bigRgba[i + 1] = (lcg >>> 8) & 0xff;
  bigRgba[i + 2] = (lcg >>> 16) & 0xff;
  bigRgba[i + 3] = 255;
}
const bigDoc = await sealRgba({
  rgba: bigRgba,
  width: wBig,
  height: hBig,
  publicKey: trustedKey.raw,
  purpose: "personal",
  label: "Large 4MP Noise",
  sign: (b) => nodeSign(null, Buffer.from(b), trustedKey.privateKey),
});
await addVector({
  id: "grd2-large-4mp-noise",
  description: "GRD2 4-megapixel photo (1014 tiles) with high-entropy noise",
  format: 2,
  bytes: encodeGRD2(bigDoc),
  expectedVerdict: "UNVERIFIED: SELF-SIGNED",
  expectedExit: 5,
});

// -------------------------------------------------------------
// Canonicalisation Vectors
// -------------------------------------------------------------
const astralDoc = await sealRgba({
  rgba: baseRgba,
  width,
  height,
  publicKey: trustedKey.raw,
  purpose: "asset",
  label: "Astral Emoji 😀",
  sign: (b) => nodeSign(null, Buffer.from(b), trustedKey.privateKey),
});
await addVector({
  id: "grd2-canonical-astral-plane",
  description: "GRD2 manifest label with astral-plane UTF-16 character (😀)",
  format: 2,
  bytes: encodeGRD2(astralDoc),
  expectedVerdict: "GENUINE",
  expectedExit: 0,
});

// Integer-valued float 1.0 in raw JSON
const floatDocRaw = new TextDecoder().decode(trustedEncoded).replace('"version":2', '"version":2.0');
await addVector({
  id: "grd2-integer-valued-float-raw",
  description: "GRD2 JSON formatted with float 2.0 where integer is required",
  format: 2,
  bytes: Buffer.from(floatDocRaw),
  expectedVerdict: "TAMPERED",
  expectedExit: 2,
});

// Lone surrogate in JSON
const loneSurrogateRaw = Buffer.from(new TextDecoder().decode(trustedEncoded).replace('"Certified Asset"', '"Certified \ud800"'), "utf8");
await addVector({
  id: "grd2-lone-surrogate",
  description: "GRD2 with lone surrogate code unit in JSON string",
  format: 2,
  bytes: loneSurrogateRaw,
  expectedVerdict: "TAMPERED",
  expectedExit: 2,
});

await writeFile(
  join(conformanceDir, "vectors.json"),
  JSON.stringify(vectors, null, 2) + "\n",
);

console.log(`Generated ${vectors.length} conformance vectors in conformance/`);
