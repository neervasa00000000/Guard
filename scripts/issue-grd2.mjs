import { readFile, writeFile, stat } from "node:fs/promises";
import { createPrivateKey, createPublicKey, sign } from "node:crypto";
import { PNG } from "pngjs";
import { encodedDimensions, TRUSTED } from "../src/verifier.js";
import { sealRgba, encodeGRD2, TILE_LIMITS } from "../src/redactable.js";
const options = {};
for (let i = 2; i < process.argv.length; i += 2)
  options[process.argv[i]] = process.argv[i + 1];
if (!options["--input"] || !options["--key"] || !options["--output"]) {
  console.error(
    "Usage: node scripts/issue-grd2.mjs --input image.png --key private-ed25519.pem --output image.GRD [--tile-size 64] [--label public-label]",
  );
  process.exitCode = 1;
} else
  try {
    const info = await stat(options["--input"]);
    if (info.size > TILE_LIMITS.bytes)
      throw new Error("Input PNG exceeds 32 MiB.");
    const bytes = await readFile(options["--input"]),
      [width, height] = encodedDimensions(bytes, "image/png");
    if (
      width > TILE_LIMITS.dimension ||
      height > TILE_LIMITS.dimension ||
      width * height > TILE_LIMITS.pixels
    )
      throw new Error("PNG exceeds GRD2’s 4096px / 4-megapixel limits.");
    const key = createPrivateKey(await readFile(options["--key"]));
    if (key.asymmetricKeyType !== "ed25519")
      throw new Error("An Ed25519 private key is required.");
    const publicKey = createPublicKey(key)
        .export({ format: "der", type: "spki" })
        .subarray(-32),
      image = PNG.sync.read(bytes, { checkCRC: true });
    const document = await sealRgba({
      rgba: image.data,
      width,
      height,
      tileSize: Number(options["--tile-size"] ?? 64),
      publicKey,
      label: options["--label"] ?? "",
      sign: (bytes) => sign(null, Buffer.from(bytes), key),
    });
    await writeFile(options["--output"], encodeGRD2(document), {
      flag: "wx",
      mode: 0o600,
    });
    console.log(
      "Created GRD2: " +
        width +
        " × " +
        height +
        " / " +
        document.tiles.length +
        " tiles.\nSigner fingerprint: " +
        document.manifest.keyId +
        "\nMerkle root: " +
        document.manifest.root,
    );
    if (!TRUSTED.some((k) => k.public_key_hex === document.manifest.publicKey))
      console.log(
        "This key is not pinned in the shipped viewer. It will report UNTRUSTED SIGNER until its public identity is independently reviewed and added.",
      );
  } catch (error) {
    console.error("GRD2 issuance failed: " + error.message);
    process.exitCode = 1;
  }
