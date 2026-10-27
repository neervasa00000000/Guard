// Public, fictional demonstration data. The ephemeral signing key is never saved.
import { generateKeyPairSync, sign } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { sealRgba, encodeGRD2, redactGRD2 } from "../src/redactable.js";
const key = generateKeyPairSync("ed25519");
const publicKey = key.publicKey
  .export({ format: "der", type: "spki" })
  .subarray(-32);
const width = 192,
  height = 128,
  rgba = new Uint8Array(width * height * 4);
for (let y = 0; y < height; y++)
  for (let x = 0; x < width; x++)
    rgba.set([x, y, (x + y) % 256, 255], (y * width + x) * 4);
const document = await sealRgba({
  rgba,
  width,
  height,
  publicKey,
  purpose: "demo",
  label: "Fictional colour-grid demonstration",
  sign: (b) => sign(null, b, key.privateKey),
});
await mkdir(new URL("../examples/", import.meta.url), { recursive: true });
await writeFile(
  new URL("../examples/colour-grid.GRD", import.meta.url),
  encodeGRD2(document),
);
await writeFile(
  new URL("../examples/colour-grid.redacted.GRD", import.meta.url),
  await redactGRD2(document, [0]),
);
console.log("Wrote two DEMO files. No private key was saved.");
