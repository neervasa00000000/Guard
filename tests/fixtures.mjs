import { generateKeyPairSync, createHash, sign } from "node:crypto";
import { deflateSync } from "node:zlib";
import { canon } from "../src/verifier.js";
export const hash = (bytes) => createHash("sha256").update(bytes).digest();
export function signer() {
  const pair = generateKeyPairSync("ed25519");
  const raw = pair.publicKey
    .export({ type: "spki", format: "der" })
    .subarray(-32);
  const id = hash(raw).subarray(0, 8);
  return {
    ...pair,
    raw,
    id,
    anchor: {
      key_id: id.toString("hex"),
      public_key_hex: raw.toString("hex"),
      owner: "TEST FIXTURE — not a production trust anchor",
      alg: "Ed25519",
    },
  };
}
function crc32(buffer) {
  let c = 0xffffffff;
  for (const b of buffer) {
    c ^= b;
    for (let i = 0; i < 8; i++) c = (c >>> 1) ^ (c & 1 ? 0xedb88320 : 0);
  }
  return (c ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const name = Buffer.from(type);
  const size = Buffer.alloc(4);
  size.writeUInt32BE(data.length);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(Buffer.concat([name, data])));
  return Buffer.concat([size, name, data, crc]);
}
export function png(width = 1, height = 1) {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;
  ihdr[9] = 2;
  const rows = [];
  for (let y = 0; y < height; y++) {
    const row = Buffer.alloc(1 + width * 3);
    for (let x = 0; x < width; x++) {
      const ridge = height * 0.55 + Math.sin((x / width) * 5) * height * 0.12;
      const c =
        y > ridge
          ? [
              38 + Math.round((x / width) * 25),
              75 + Math.round((y / height) * 35),
              62,
            ]
          : [
              210 - Math.round((y / height) * 25),
              220 - Math.round((y / height) * 20),
              192 - Math.round((y / height) * 20),
            ];
      for (let k = 0; k < 3; k++) row[1 + x * 3 + k] = c[k];
    }
    rows.push(row);
  }
  return Buffer.concat([
    Buffer.from("89504e470d0a1a0a", "hex"),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(Buffer.concat(rows))),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}
export function makeGRD(
  key,
  {
    image = png(),
    width = 1,
    height = 1,
    meta = {},
    extras = true,
    metadataRaw,
  } = {},
) {
  const metadata = {
    asset_id: hash(image).toString("hex").slice(0, 15),
    key_id: key.id.toString("hex"),
    mime: "image/png",
    width,
    height,
    author: "Fixture author",
    issued_by: "Test suite",
    original_filename: "sample.png",
    created_utc: "2026-10-27T00:00:00Z",
    watermark_id: "TEST-NO-REAL-WATERMARK",
    ...meta,
  };
  const parts = [
    [1, Buffer.from(metadataRaw ?? canon(metadata))],
    [2, image],
  ];
  if (extras)
    parts.push(
      [3, png()],
      [4, Buffer.from("fixture recovery bytes")],
      [
        5,
        Buffer.from("fixture timestamp token, NOT a validated authority time"),
      ],
    );
  parts.push([6, Buffer.concat([key.id, key.raw])], [7, Buffer.alloc(64)]);
  const header = Buffer.alloc(10);
  header.write("GRD1");
  header.writeUInt16LE(1, 4);
  header.writeUInt16LE(extras ? 3 : 0, 6);
  header.writeUInt16LE(parts.length, 8);
  const table = Buffer.alloc(parts.length * 50);
  let offset = 10 + table.length;
  for (let i = 0; i < parts.length; i++) {
    const [type, data] = parts[i],
      at = i * 50;
    table.writeUInt16LE(type, at);
    table.writeBigUInt64LE(BigInt(offset), at + 2);
    table.writeBigUInt64LE(BigInt(data.length), at + 10);
    if (type !== 7) hash(data).copy(table, at + 18);
    offset += data.length;
  }
  const prefix = Buffer.concat([
    header,
    table,
    ...parts.slice(0, -1).map((p) => p[1]),
  ]);
  return Buffer.concat([prefix, sign(null, hash(prefix), key.privateKey)]);
}
