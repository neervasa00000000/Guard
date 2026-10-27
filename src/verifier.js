// GRD1 compatibility: Ed25519 signs SHA-256(header + table + non-signature sections).
// The embedded public key is never sufficient: it must match a pinned trust anchor.
export const LIMITS = Object.freeze({
  fileBytes: 64 * 1024 * 1024,
  metadataBytes: 256 * 1024,
  imagePixels: 40_000_000,
  dimension: 16384,
});
export const TRUSTED = Object.freeze([
  Object.freeze({
    key_id: "008c06e446c0e983",
    public_key_hex:
      "97bb1a09fb958f21841c21dc2a400d87e333bcf1d1f7390525693319d1fce691",
    owner: "Thuy Tran (Image Guard GRD signer)",
    alg: "Ed25519",
  }),
]);
export const NAMES = Object.freeze({
  1: "Metadata",
  2: "Image",
  3: "Thumbnail",
  4: "Recovery",
  5: "Timestamp",
  6: "Signing key",
  7: "Signature",
});
export const hex = (bytes) =>
  Array.from(new Uint8Array(bytes))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
export const sha = async (bytes) =>
  hex(await crypto.subtle.digest("SHA-256", bytes));
export function canon(value) {
  if (Array.isArray(value)) return "[" + value.map(canon).join(",") + "]";
  if (value && typeof value === "object")
    return (
      "{" +
      Object.keys(value)
        .sort()
        .map((k) => JSON.stringify(k) + ":" + canon(value[k]))
        .join(",") +
      "}"
    );
  return JSON.stringify(value);
}
function validTree(value, depth = 0) {
  if (depth > 32) return false;
  if (
    typeof value === "number" &&
    (!Number.isFinite(value) || Math.abs(value) > Number.MAX_SAFE_INTEGER)
  )
    return false;
  if (value && typeof value === "object")
    return Object.values(value).every((v) => validTree(v, depth + 1));
  return true;
}
export function createVerifier(anchors) {
  const trusted = anchors.map((k) => ({ ...k }));
  return async function verifyGRD(input) {
    const r = {
      verdict: "TAMPERED",
      genuine: false,
      failed: [],
      changed: [],
      problems: [],
      checks: [],
      sections: [],
      meta: null,
      signature_valid: false,
    };
    const issue = (message, part) => {
      r.problems.push(message);
      if (part && !r.failed.includes(part)) r.failed.push(part);
    };
    const check = (name, status, detail) =>
      r.checks.push({ name, status, detail });
    const finish = () => {
      r.changed = [...r.failed];
      return r;
    };
    try {
      const d = input instanceof Uint8Array ? input : new Uint8Array(input);
      r.byteLength = d.byteLength;
      if (d.byteLength > LIMITS.fileBytes) {
        r.verdict = "LIMIT EXCEEDED";
        issue("This viewer accepts files up to 64 MiB.", "file size");
        return finish();
      }
      if (
        d.length < 10 ||
        d[0] !== 71 ||
        d[1] !== 82 ||
        d[2] !== 68 ||
        d[3] !== 49
      ) {
        r.verdict = "NOT A GRD";
        issue("The file has no readable GRD1 header.", "file header");
        return finish();
      }
      const dv = new DataView(d.buffer, d.byteOffset, d.byteLength),
        version = dv.getUint16(4, true),
        flags = dv.getUint16(6, true),
        count = dv.getUint16(8, true);
      r.version = version;
      if (version !== 1) {
        r.verdict = "UNSUPPORTED";
        issue(
          "This viewer supports GRD version 1. The file declares version " +
            version +
            ".",
          "file version",
        );
        return finish();
      }
      if (count < 4 || count > 7) {
        issue("Invalid number of sections.", "file structure");
        return finish();
      }
      const tableEnd = 10 + 50 * count;
      if (tableEnd > d.length) {
        issue("The file ends inside its section table.", "file length");
        return finish();
      }
      const entries = [];
      for (let i = 0; i < count; i++) {
        const at = 10 + 50 * i,
          type = dv.getUint16(at, true),
          offset = dv.getBigUint64(at + 2, true),
          length = dv.getBigUint64(at + 10, true);
        if (!NAMES[type]) {
          issue("Unknown section type " + type + ".", "file structure");
          return finish();
        }
        if (
          offset > BigInt(d.length) ||
          length > BigInt(d.length) ||
          offset + length > BigInt(d.length)
        ) {
          issue(
            NAMES[type] + " exceeds the available file bytes.",
            "file length",
          );
          return finish();
        }
        entries.push({
          type,
          offset: Number(offset),
          length: Number(length),
          hash: hex(d.subarray(at + 18, at + 50)),
        });
      }
      const types = entries.map((e) => e.type);
      if (
        new Set(types).size !== types.length ||
        ![1, 2, 6, 7].every((t) => types.includes(t)) ||
        types.at(-1) !== 7
      ) {
        issue(
          "Sections are duplicated, missing, or the signature is not last.",
          "file structure",
        );
        return finish();
      }
      if (
        Boolean(flags & 1) !== types.includes(5) ||
        Boolean(flags & 2) !== types.includes(4) ||
        flags & ~3
      ) {
        issue("Header flags do not match the section table.", "file structure");
        return finish();
      }
      let expected = tableEnd;
      for (const e of entries) {
        if (e.offset !== expected) {
          issue(
            NAMES[e.type] + " has an overlapping or non-contiguous offset.",
            "file structure",
          );
          return finish();
        }
        expected += e.length;
      }
      if (expected !== d.length) {
        issue(
          "There are " +
            (d.length - expected) +
            " extra bytes after the final section.",
          "file length",
        );
        return finish();
      }
      const signature = entries.at(-1);
      if (signature.length !== 64 || signature.hash !== "0".repeat(64)) {
        issue(
          "The signature entry must contain 64 bytes and a zero hash.",
          "file structure",
        );
        return finish();
      }
      const byType = Object.fromEntries(
        entries.map((e) => [e.type, d.subarray(e.offset, e.offset + e.length)]),
      );
      if (!byType[1].length || byType[1].length > LIMITS.metadataBytes) {
        issue(
          "Metadata must be non-empty and no larger than 256 KiB.",
          "metadata",
        );
        return finish();
      }
      if (!byType[2].length || byType[6].length !== 40) {
        issue(
          "The image is empty or signing key is not 40 bytes.",
          "file structure",
        );
        return finish();
      }
      check(
        "File structure",
        "pass",
        count + " contiguous sections · no trailing bytes",
      );
      if (!globalThis.crypto?.subtle) {
        r.verdict = "UNSUPPORTED";
        issue(
          "Cryptographic verification is unavailable. Open this file in a current browser in a secure context.",
        );
        return finish();
      }
      r.fileHash = await sha(d);
      for (const e of entries) {
        if (e.type === 7) continue;
        const valid = (await sha(byType[e.type])) === e.hash;
        r.sections.push({ ...e, name: NAMES[e.type], valid });
        if (!valid)
          issue(
            NAMES[e.type] + " bytes do not match their signed hash.",
            NAMES[e.type].toLowerCase(),
          );
      }
      check(
        "Section hashes",
        r.sections.every((e) => e.valid) ? "pass" : "fail",
        r.sections.filter((e) => e.valid).length +
          " / " +
          r.sections.length +
          " matched",
      );
      const keyBytes = byType[6],
        keyId = hex(keyBytes.subarray(0, 8)),
        publicKey = keyBytes.subarray(8);
      r.keyId = keyId;
      const keyIdentity = (await sha(publicKey)).slice(0, 16) === keyId;
      const anchor = trusted.find(
        (k) => k.key_id === keyId && k.public_key_hex === hex(publicKey),
      );
      if (!keyIdentity)
        issue("Signing key ID does not match its public key.", "signing key");
      if (!anchor)
        issue(
          "This signing key is not in the viewer’s pinned trusted list.",
          "untrusted signer",
        );
      r.signer = anchor?.owner ?? "Untrusted signing key";
      check(
        "Trusted signer",
        anchor && keyIdentity ? "pass" : "fail",
        anchor?.owner ?? "Unknown key · " + keyId,
      );
      try {
        const key = await crypto.subtle.importKey(
          "raw",
          publicKey,
          { name: "Ed25519" },
          false,
          ["verify"],
        );
        r.signature_valid = await crypto.subtle.verify(
          { name: "Ed25519" },
          key,
          byType[7],
          await crypto.subtle.digest(
            "SHA-256",
            d.subarray(0, signature.offset),
          ),
        );
      } catch (error) {
        if (error.name === "NotSupportedError") {
          r.verdict = "UNSUPPORTED";
          issue(
            "This browser cannot verify Ed25519 signatures. Try a current browser.",
          );
          return finish();
        }
        issue("The Ed25519 signature could not be read.", "signature");
      }
      if (!r.signature_valid)
        issue(
          "The signature does not verify against the signed file bytes.",
          "signature",
        );
      check(
        "Ed25519 signature",
        r.signature_valid ? "pass" : "fail",
        "Signature over the SHA-256 digest of the signed file prefix",
      );
      try {
        const raw = new TextDecoder("utf-8", { fatal: true }).decode(byType[1]),
          meta = JSON.parse(raw);
        if (
          !meta ||
          Array.isArray(meta) ||
          typeof meta !== "object" ||
          !validTree(meta)
        )
          throw new Error(
            "Metadata must be an object with bounded depth and finite, safely represented numbers.",
          );
        r.meta = meta;
        if (canon(meta) !== raw)
          issue(
            "Metadata is not in the expected canonical JSON form.",
            "metadata",
          );
        if (meta.asset_id !== (await sha(byType[2])).slice(0, 15))
          issue("The asset ID does not match the image bytes.", "image");
        if (meta.key_id !== keyId)
          issue("Metadata names a different signer key.", "metadata");
        const imageType = ["image/png", "image/jpeg", "image/webp"].includes(
          meta.mime,
        );
        const dimensions =
          Number.isInteger(meta.width) &&
          Number.isInteger(meta.height) &&
          meta.width > 0 &&
          meta.height > 0 &&
          meta.width <= LIMITS.dimension &&
          meta.height <= LIMITS.dimension &&
          meta.width * meta.height <= LIMITS.imagePixels;
        if (!imageType || !dimensions) {
          r.verdict = "UNSUPPORTED";
          issue(
            "The signed image must be PNG, JPEG or WebP, within 16,384 pixels per edge and 40 megapixels.",
            "image format",
          );
        }
      } catch (error) {
        issue("Metadata is unreadable or unsafe: " + error.message, "metadata");
      }
      check(
        "Metadata binding",
        !r.failed.some((x) => ["metadata", "image"].includes(x)) && r.meta
          ? "pass"
          : "fail",
        "Canonical JSON, matching asset ID and signer key",
      );
      if (byType[5]) r.timestampPresent = true;
      if (!r.problems.length) {
        try {
          const [width, height] = encodedDimensions(byType[2], r.meta.mime);
          if (width !== r.meta.width || height !== r.meta.height) {
            issue(
              "Encoded image dimensions differ from the signed metadata.",
              "image",
            );
            check(
              "Encoded image dimensions",
              "fail",
              "Image header and signed dimensions differ",
            );
          } else
            check(
              "Encoded image dimensions",
              "pass",
              width + " × " + height + " · matches signed metadata",
            );
        } catch (error) {
          r.verdict = "UNREADABLE";
          issue(error.message, "image format");
          check("Encoded image header", "fail", error.message);
        }
      }
      if (!r.problems.length) {
        r.verdict = "GENUINE";
        r.genuine = true;
        r.payload = byType[2].slice();
      }
      return finish();
    } catch (error) {
      issue("Verification stopped safely: " + error.message, "file structure");
      return finish();
    }
  };
}
export const verifyGRD = createVerifier(TRUSTED);

export function encodedDimensions(bytes, mime) {
  const v = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength),
    ascii = (at, n) => String.fromCharCode(...bytes.subarray(at, at + n));
  if (
    mime === "image/png" &&
    bytes.length >= 24 &&
    hex(bytes.subarray(0, 8)) === "89504e470d0a1a0a" &&
    ascii(12, 4) === "IHDR"
  )
    return [v.getUint32(16), v.getUint32(20)];
  if (mime === "image/jpeg" && bytes[0] === 255 && bytes[1] === 216) {
    let i = 2;
    while (i + 3 < bytes.length) {
      if (bytes[i++] !== 255) break;
      while (bytes[i] === 255) i++;
      const marker = bytes[i++];
      if (marker === 0xd9 || marker === 0xda) break;
      if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) continue;
      const len = v.getUint16(i);
      if (len < 2 || i + len > bytes.length) break;
      if (
        [
          0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd,
          0xce, 0xcf,
        ].includes(marker) &&
        len >= 7
      )
        return [v.getUint16(i + 5), v.getUint16(i + 3)];
      i += len;
    }
  }
  if (
    mime === "image/webp" &&
    bytes.length >= 30 &&
    ascii(0, 4) === "RIFF" &&
    ascii(8, 4) === "WEBP"
  ) {
    const kind = ascii(12, 4);
    if (kind === "VP8X")
      return [
        1 + bytes[24] + bytes[25] * 256 + bytes[26] * 65536,
        1 + bytes[27] + bytes[28] * 256 + bytes[29] * 65536,
      ];
    if (kind === "VP8 " && hex(bytes.subarray(23, 26)) === "9d012a")
      return [v.getUint16(26, true) & 0x3fff, v.getUint16(28, true) & 0x3fff];
    if (kind === "VP8L" && bytes[20] === 0x2f) {
      const bits = v.getUint32(21, true);
      return [(bits & 0x3fff) + 1, ((bits >>> 14) & 0x3fff) + 1];
    }
  }
  throw new Error("Unsupported or invalid encoded image header.");
}
