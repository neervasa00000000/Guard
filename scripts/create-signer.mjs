// SPDX-License-Identifier: MIT
import { generateKeyPairSync, createHash } from "node:crypto";
import { writeFile, stat } from "node:fs/promises";
const options = Object.fromEntries(
  Array.from({ length: Math.ceil((process.argv.length - 2) / 2) }, (_, i) => [
    process.argv[2 + i * 2],
    process.argv[3 + i * 2],
  ]),
);
if (
  !options["--private"] ||
  !options["--public"] ||
  !options["--owner"] ||
  options["--private"] === options["--public"]
)
  throw new Error(
    'Usage: node scripts/create-signer.mjs --private /secure/signer.pem --public /secure/signer-public.pem --owner "Your verified issuer name"',
  );
for (const path of [options["--private"], options["--public"]]) {
  try {
    await stat(path);
    throw new Error("Refusing to overwrite " + path);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
}
const key = generateKeyPairSync("ed25519");
await writeFile(
  options["--private"],
  key.privateKey.export({ type: "pkcs8", format: "pem" }),
  { flag: "wx", mode: 0o600 },
);
await writeFile(
  options["--public"],
  key.publicKey.export({ type: "spki", format: "pem" }),
  { flag: "wx", mode: 0o644 },
);
const raw = key.publicKey.export({ type: "spki", format: "der" }).subarray(-32),
  fingerprint = createHash("sha256").update(raw).digest("hex");
console.log(
  "Private key written with owner-only permissions. Keep it outside the repository.\nReview this signers[] entry before configuring your viewer:\n" +
    JSON.stringify(
      {
        key_id: fingerprint.slice(0, 16),
        public_key_hex: raw.toString("hex"),
        fingerprint_sha256: fingerprint,
        name: options["--owner"],
        alg: "Ed25519",
        revoked: false,
        revokedAt: null,
        reason: null,
      },
      null,
      2,
    ) +
    "\nFull fingerprint: " +
    fingerprint +
    "\nThis does not approve or install the signer automatically.",
);
