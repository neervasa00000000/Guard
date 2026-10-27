// SPDX-License-Identifier: MIT
import { checkRevocation, TRUST_POLICY } from "./trust.js";
import { canon, sha, hex, TRUSTED, validateTrustedKeys, IntegrityError } from "./verifier.js";
import { encodeRgbPng, decodeRgbPng } from "./png.js";

export { IntegrityError };

export const TILE_LIMITS = Object.freeze({
  bytes: 32 * 1024 * 1024,
  pixels: 4_194_304,
  dimension: 4096,
  tiles: 1024,
});
const textEncoder = new TextEncoder();
const MANIFEST_FIELDS = [
  "format",
  "version",
  "width",
  "height",
  "tileSize",
  "pixelFormat",
  "root",
  "commitments",
  "publicKey",
  "keyId",
  "policy",
  "purpose",
  "label",
];
const unhex = (value) =>
  Uint8Array.from(value.match(/../g), (v) => parseInt(v, 16));
const joinBytes = (...arrays) => {
  const out = new Uint8Array(arrays.reduce((n, a) => n + a.length, 0));
  let at = 0;
  for (const a of arrays) {
    out.set(a, at);
    at += a.length;
  }
  return out;
};
export function base64(bytes) {
  let raw = "";
  for (let i = 0; i < bytes.length; i += 32768)
    raw += String.fromCharCode(...bytes.subarray(i, i + 32768));
  return btoa(raw);
}

export function isCanonicalBase64Shape(s) {
  if (s.length % 4) return false;
  const pad = s.endsWith("==") ? 2 : s.endsWith("=") ? 1 : 0;
  for (let i = 0; i < s.length - pad; i++) {
    const c = s.charCodeAt(i);
    const ok =
      (c >= 65 && c <= 90) ||
      (c >= 97 && c <= 122) ||
      (c >= 48 && c <= 57) ||
      c === 43 ||
      c === 47;
    if (!ok) return false;
  }
  return true;
}

export function decodeBase64(value, length) {
  if (
    typeof value !== "string" ||
    value.length > Math.ceil(TILE_LIMITS.bytes / 3) * 4 ||
    value.length % 4 ||
    !isCanonicalBase64Shape(value)
  )
    throw new IntegrityError("Invalid base64 payload length or encoding.");
  const raw = atob(value);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  if (
    (length !== undefined && bytes.length !== length) ||
    base64(bytes) !== value
  )
    throw new IntegrityError("Noncanonical base64 payload.");
  return bytes;
}
const exactKeys = (value, keys) =>
  value &&
  typeof value === "object" &&
  !Array.isArray(value) &&
  Object.keys(value).length === keys.length &&
  keys.every((k) => Object.hasOwn(value, k));
const hashHex = (value) =>
  typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
export function isGRD2(input) {
  const d = input instanceof Uint8Array ? input : new Uint8Array(input);
  return (
    d[0] === 71 && d[1] === 82 && d[2] === 68 && d[3] === 50 && d[4] === 10
  );
}
export function tileBounds(m, index) {
  const columns = Math.ceil(m.width / m.tileSize),
    x = (index % columns) * m.tileSize,
    y = Math.floor(index / columns) * m.tileSize;
  return {
    x,
    y,
    width: Math.min(m.tileSize, m.width - x),
    height: Math.min(m.tileSize, m.height - y),
  };
}
function validateManifest(m) {
  if (
    !exactKeys(m, MANIFEST_FIELDS) ||
    m.format !== "GRD2" ||
    m.version !== 2 ||
    m.pixelFormat !== "RGB8" ||
    m.policy !== "tile-redaction-v1" ||
    !["asset", "demo", "personal"].includes(m.purpose)
  )
    throw new IntegrityError("Unsupported GRD2 manifest or policy.");
  if (
    !Number.isInteger(m.width) ||
    !Number.isInteger(m.height) ||
    m.width < 1 ||
    m.height < 1 ||
    m.width > TILE_LIMITS.dimension ||
    m.height > TILE_LIMITS.dimension ||
    m.width * m.height > TILE_LIMITS.pixels ||
    m.tileSize !== 64
  )
    throw new IntegrityError("GRD2 needs a bounded RGB image and 64px tiles.");
  if (
    !hashHex(m.root) ||
    !hashHex(m.publicKey) ||
    !hashHex(m.keyId) ||
    typeof m.label !== "string" ||
    m.label.length > 120 ||
    !m.label.isWellFormed()
  )
    throw new IntegrityError("Invalid GRD2 root, key or label.");
  const count = Math.ceil(m.width / 64) * Math.ceil(m.height / 64);
  if (
    count > TILE_LIMITS.tiles ||
    !Array.isArray(m.commitments) ||
    m.commitments.length !== count ||
    !m.commitments.every(hashHex)
  )
    throw new IntegrityError("Invalid signed tile commitments.");
  return count;
}
export async function tileCommitment(m, index, salt, rgb) {
  void m;
  const idx = new Uint8Array(4);
  new DataView(idx.buffer).setUint32(0, index);
  return sha(joinBytes(textEncoder.encode("GRD-TILE"), idx, unhex(salt), rgb));
}
export async function merkleRoot(commitments) {
  if (!commitments.length) throw new IntegrityError("Empty Merkle tree.");
  let layer = await Promise.all(
    commitments.map((c) => sha(joinBytes(new Uint8Array([0]), unhex(c)))),
  );
  while (layer.length > 1) {
    const next = [];
    for (let i = 0; i < layer.length; i += 2)
      next.push(
        await sha(
          joinBytes(
            new Uint8Array([1]),
            unhex(layer[i]),
            unhex(layer[i + 1] ?? layer[i]),
          ),
        ),
      );
    layer = next;
  }
  return layer[0];
}
export async function manifestDigest(manifest) {
  return crypto.subtle.digest(
    "SHA-256",
    joinBytes(
      textEncoder.encode("GUARD-GRD2-MANIFEST-V1\0"),
      textEncoder.encode(canon(manifest)),
    ),
  );
}
export function encodeGRD2(document) {
  const encoded = textEncoder.encode("GRD2\n" + canon(document));
  if (encoded.length > TILE_LIMITS.bytes)
    throw new Error("GRD2 exceeds 32 MiB.");
  return encoded;
}
function tilePixels(rgb, m, index) {
  const b = tileBounds(m, index),
    out = new Uint8Array(b.width * b.height * 3);
  for (let row = 0; row < b.height; row++)
    out.set(
      rgb.subarray(
        ((b.y + row) * m.width + b.x) * 3,
        ((b.y + row) * m.width + b.x + b.width) * 3,
      ),
      row * b.width * 3,
    );
  return out;
}
export async function sealRgba({
  rgba,
  width,
  height,
  tileSize = 64,
  publicKey,
  sign,
  purpose = "asset",
  label = "",
}) {
  if (
    !(rgba instanceof Uint8Array) ||
    rgba.length !== width * height * 4 ||
    tileSize !== 64
  )
    throw new Error("Expected exact RGBA8 bytes and 64px tiles.");
  const count = Math.ceil(width / 64) * Math.ceil(height / 64),
    manifest = {
      format: "GRD2",
      version: 2,
      width,
      height,
      tileSize,
      pixelFormat: "RGB8",
      root: "0".repeat(64),
      commitments: Array(count).fill("0".repeat(64)),
      publicKey: hex(publicKey),
      keyId: await sha(publicKey),
      policy: "tile-redaction-v1",
      purpose,
      label,
    };
  validateManifest(manifest);
  const rgb = new Uint8Array(width * height * 3);
  for (let i = 0; i < width * height; i++)
    for (let c = 0; c < 3; c++)
      rgb[i * 3 + c] = Math.floor(
        (rgba[i * 4 + c] * rgba[i * 4 + 3] +
          255 * (255 - rgba[i * 4 + 3]) +
          127) /
          255,
      );
  const tiles = [];
  for (let index = 0; index < count; index++) {
    const salt = hex(crypto.getRandomValues(new Uint8Array(16)));
    manifest.commitments[index] = await tileCommitment(
      manifest,
      index,
      salt,
      tilePixels(rgb, manifest, index),
    );
    tiles.push({ index, salt });
  }
  manifest.root = await merkleRoot(manifest.commitments);
  const signature = new Uint8Array(await sign(await manifestDigest(manifest)));
  if (signature.length !== 64)
    throw new Error("Expected an Ed25519 signature.");
  return {
    manifest,
    signature: base64(signature),
    image: base64(await encodeRgbPng(rgb, width, height)),
    tiles,
    redactions: [],
  };
}
export async function verifyGRD2(
  input,
  anchors = TRUSTED,
  revocationPolicy = TRUST_POLICY,
) {
  const r = {
    version: 2,
    verdict: "TAMPERED",
    genuine: false,
    viewable: false,
    checks: [],
    sections: [],
    problems: [],
    failed: [],
    changed: [],
    meta: null,
    signature_valid: false,
    hiddenPixelsCleared: true,
  };
  const check = (name, status, detail) =>
    r.checks.push({ name, status: status ? "pass" : "fail", detail });
  try {
    if (anchors?._invalid || TRUSTED?._invalid) {
      r.verdict = "CANNOT VERIFY";
      r.problems.push("Trusted-keys file is invalid.");
      check("GRD2 verification", false, "Trusted-keys file is invalid.");
      return r;
    }
    const bytes = input instanceof Uint8Array ? input : new Uint8Array(input);
    r.byteLength = bytes.length;
    if (bytes.length > TILE_LIMITS.bytes) {
      r.verdict = "LIMIT EXCEEDED";
      throw new IntegrityError("GRD2 is limited to 32 MiB.");
    }
    if (!isGRD2(bytes)) {
      r.verdict = "NOT A GRD";
      throw new IntegrityError("Missing GRD2 header.");
    }
    let raw;
    try {
      raw = new TextDecoder("utf-8", { fatal: true }).decode(bytes.subarray(5));
    } catch (e) {
      throw new IntegrityError("Invalid UTF-8 in GRD2 container: " + e.message);
    }
    let doc;
    try {
      doc = JSON.parse(raw);
    } catch (e) {
      throw new IntegrityError("Invalid JSON in GRD2 container: " + e.message);
    }
    if (
      !exactKeys(doc, ["manifest", "signature", "image", "tiles", "redactions"])
    )
      throw new IntegrityError("Unexpected container fields.");
    const m = doc.manifest,
      count = validateManifest(m);
    if (
      !Array.isArray(doc.tiles) ||
      doc.tiles.length !== count ||
      !Array.isArray(doc.redactions) ||
      doc.redactions.length > count
    )
      throw new IntegrityError("Tile grid or redaction list is incomplete.");
    const redacted = [];
    for (let index = 0; index < count; index++) {
      const t = doc.tiles[index];
      if (
        !t ||
        t.index !== index ||
        !(
          exactKeys(t, ["index", "salt"]) ||
          exactKeys(t, ["index", "commitment"])
        )
      )
        throw new IntegrityError(
          "Tiles must be ordered, unique and have only permitted disclosure fields.",
        );
      if (Object.hasOwn(t, "commitment")) redacted.push(index);
    }
    for (let i = 0; i < doc.redactions.length; i++) {
      const item = doc.redactions[i];
      if (
        !exactKeys(item, ["index", "method"]) ||
        item.index !== redacted[i] ||
        !["black", "blur"].includes(item.method)
      )
        throw new IntegrityError("REDACTIONS does not match the hidden tile set.");
    }
    if (doc.redactions.length !== redacted.length)
      throw new IntegrityError("REDACTIONS does not match TILES.");
    if (canon(doc) !== raw)
      throw new IntegrityError(
        "GRD2 must use canonical JSON without duplicate keys or extra bytes.",
      );
    check(
      "Container structure",
      true,
      count + " ordered tiles · redaction records agree",
    );
    r.fileHash = await sha(bytes);
    r.keyId = m.keyId;
    r.root = m.root;
    if ((await sha(unhex(m.publicKey))) !== m.keyId)
      throw new IntegrityError("Signer fingerprint does not match public key.");
    r.revocation = await checkRevocation(unhex(m.publicKey), revocationPolicy);
    if (r.revocation.revoked) {
      r.verdict = "REVOKED KEY";
      throw new IntegrityError("Signing key is revoked: " + r.revocation.reason);
    }
    check(
      "Offline revocation",
      true,
      "Not listed in bundled snapshot · " + r.revocation.asOf,
    );
    const pk = await crypto.subtle.importKey(
      "raw",
      unhex(m.publicKey),
      { name: "Ed25519" },
      false,
      ["verify"],
    );
    r.signature_valid = await crypto.subtle.verify(
      { name: "Ed25519" },
      pk,
      decodeBase64(doc.signature, 64),
      await manifestDigest(m),
    );
    check(
      "Signed Merkle root",
      r.signature_valid,
      "Ed25519 · immutable manifest and tile commitments",
    );
    if (!r.signature_valid) throw new IntegrityError("Manifest signature is invalid.");
    if ((await merkleRoot(m.commitments)) !== m.root)
      throw new IntegrityError("Signed commitment vector and Merkle root disagree.");
    const anchor = anchors.find((k) => k.public_key_hex === m.publicKey);
    r.demo = m.purpose === "demo";
    r.personal = m.purpose === "personal";
    r.trusted = !!anchor && !r.demo && !r.personal;
    r.signer = r.demo
      ? "Demonstration signer (not an identity claim)"
      : r.personal
        ? "Self-signed personal file (identity not verified)"
        : (anchor?.name ?? anchor?.owner ?? "Untrusted signer");
    if (anchor) {
      r.signerName = anchor.name ?? anchor.owner;
      r.fingerprint = anchor.fingerprint_sha256 || m.keyId;
    } else {
      r.fingerprint = m.keyId;
    }
    check(
      "Signer trust",
      r.trusted,
      r.demo ? "DEMO ONLY · identity not verified" : r.signer,
    );
    if (r.demo || r.personal) r.checks.at(-1).status = "info";
    let decoded;
    try {
      decoded = await decodeRgbPng(decodeBase64(doc.image));
    } catch (e) {
      if (e instanceof IntegrityError) throw e;
      throw new IntegrityError("Invalid PNG image data: " + e.message);
    }
    if (decoded.width !== m.width || decoded.height !== m.height)
      throw new IntegrityError("PNG dimensions differ from the signed tile grid.");

    // Task 4: verify hidden tiles are solid black
    let hiddenCleared = true;
    for (const index of redacted) {
      const b = tileBounds(m, index);
      for (let row = 0; row < b.height; row++) {
        const start = ((b.y + row) * m.width + b.x) * 3;
        for (let col = 0; col < b.width * 3; col++) {
          if (decoded.rgb[start + col] !== 0) {
            hiddenCleared = false;
            break;
          }
        }
        if (!hiddenCleared) break;
      }
      if (!hiddenCleared) break;
    }
    r.hiddenPixelsCleared = hiddenCleared;
    if (!hiddenCleared) {
      r.problems.push(
        "Hidden tiles still contain pixel data in this file. The viewer covers them, but anyone who extracts the image can see it. Re-export with Guard to clear them before sharing.",
      );
      check(
        "Hidden pixels cleared",
        false,
        "Hidden tiles still contain pixel data in this file.",
      );
    } else if (redacted.length > 0) {
      check(
        "Hidden pixels cleared",
        true,
        "Solid black pixels in hidden regions",
      );
    }

    const leaves = [];
    for (let index = 0; index < count; index++) {
      const t = doc.tiles[index];
      if (Object.hasOwn(t, "commitment")) {
        if (!hashHex(t.commitment) || t.commitment !== m.commitments[index])
          throw new IntegrityError(
            "Redacted tile " + index + " has the wrong commitment.",
          );
        leaves.push(t.commitment);
      } else {
        if (typeof t.salt !== "string" || !/^[0-9a-f]{32}$/.test(t.salt))
          throw new IntegrityError("Invalid salt at tile " + index + ".");
        const actual = await tileCommitment(
          m,
          index,
          t.salt,
          tilePixels(decoded.rgb, m, index),
        );
        if (actual !== m.commitments[index])
          throw new IntegrityError("Non-redacted tile " + index + " was changed.");
        leaves.push(actual);
      }
    }
    if ((await merkleRoot(leaves)) !== m.root)
      throw new IntegrityError("Current tile disclosures do not match the signed root.");
    check(
      "Tile commitments",
      true,
      count -
        redacted.length +
        " retained tiles match · " +
        redacted.length +
        " redacted tiles excluded",
    );
    r.tilesTotal = count;
    r.tilesVisible = count - redacted.length;
    r.redactedTiles = redacted;
    r.redactionMap = redacted.map((index) => ({
      index,
      ...tileBounds(m, index),
      claimedMethod: doc.redactions.find((x) => x.index === index).method,
      methodAttested: false,
    }));
    r.redactionApproval = "not_attested";
    r.tileSize = 64;
    r.regionVerified = true;
    r.meta = {
      asset_id: m.root,
      key_id: m.keyId,
      width: m.width,
      height: m.height,
      mime: "image/raw-rgba",
      original_filename: m.label || undefined,
    };
    if (!r.trusted && !r.demo && !r.personal) {
      r.verdict = "UNTRUSTED SIGNER";
      r.problems.push(
        "The pixels match this key’s root, but the key is not pinned as trusted. Image withheld.",
      );
      return r;
    }
    if (!r.tilesVisible) {
      r.verdict = "FULLY REDACTED";
      r.problems.push(
        "No original pixels remain to inspect. No visible content is being called genuine.",
      );
      return r;
    }
    r.verdict = r.demo
      ? "DEMO"
      : r.personal
        ? "UNVERIFIED: SELF-SIGNED"
        : redacted.length
          ? "VERIFIED WITH REDACTIONS"
          : "GENUINE";
    r.genuine = r.trusted && !redacted.length;
    r.viewable = true;
    const rgba = new Uint8Array(m.width * m.height * 4);
    const rgb = decoded.rgb;
    for (let i = 0; i < m.width * m.height; i++) {
      const src = i * 3;
      const dst = i * 4;
      rgba[dst] = rgb[src];
      rgba[dst + 1] = rgb[src + 1];
      rgba[dst + 2] = rgb[src + 2];
      rgba[dst + 3] = 255;
    }
    for (const index of redacted) {
      const b = tileBounds(m, index);
      for (let row = 0; row < b.height; row++)
        for (let col = 0; col < b.width; col++)
          rgba.set(
            (row + col) % 20 < 3 ? [71, 82, 119, 255] : [27, 33, 49, 255],
            ((b.y + row) * m.width + b.x + col) * 4,
          );
    }
    r.imageRgba = rgba;
    r.container = doc;
    return r;
  } catch (error) {
    if (error.name === "NotSupportedError" || !globalThis.crypto?.subtle) {
      r.verdict = "UNSUPPORTED";
    } else if (
      r.verdict === "LIMIT EXCEEDED" ||
      r.verdict === "NOT A GRD" ||
      r.verdict === "REVOKED KEY"
    ) {
      // Keep verdict
    } else if (error instanceof IntegrityError) {
      r.verdict = "TAMPERED";
    } else {
      r.verdict = "CANNOT VERIFY";
    }
    r.problems.push(error.message);
    r.failed.push("GRD2 proof");
    r.changed = [...r.failed];
    check("GRD2 verification", false, error.message);
    return r;
  }
}
export async function redactGRD2(document, indices, method = "black") {
  const m = document.manifest,
    count = validateManifest(m),
    selected = new Set(indices);
  if (!selected.size || method !== "black")
    throw new Error("Select tiles. Only blackout exports are supported.");
  for (const index of selected)
    if (!Number.isInteger(index) || index < 0 || index >= count)
      throw new Error("Invalid redaction index.");
  const result = await verifyGRD2(encodeGRD2(document), []);
  if (!result.regionVerified)
    throw new Error("Cannot redact an invalid source proof.");
  const decoded = await decodeRgbPng(decodeBase64(document.image)),
    rgb = decoded.rgb,
    tiles = [],
    methods = new Map();
  for (const item of document.redactions) methods.set(item.index, item.method);
  const hidden = new Set([
    ...document.redactions.map((item) => item.index),
    ...selected,
  ]);
  for (let index = 0; index < count; index++)
    if (hidden.has(index)) {
      const b = tileBounds(m, index);
      for (let row = 0; row < b.height; row++)
        rgb.fill(
          0,
          ((b.y + row) * m.width + b.x) * 3,
          ((b.y + row) * m.width + b.x + b.width) * 3,
        );
      tiles.push({ index, commitment: m.commitments[index] });
    } else tiles.push(document.tiles[index]);
  const redactions = Array.from(hidden)
    .sort((a, b) => a - b)
    .map((index) => ({
      index,
      method: methods.get(index) ?? "black",
    }));
  return encodeGRD2({
    manifest: m,
    signature: document.signature,
    image: base64(await encodeRgbPng(rgb, m.width, m.height)),
    tiles,
    redactions,
  });
}
export function tilesForRect(manifest, rect) {
  const count = validateManifest(manifest),
    out = [];
  for (let index = 0; index < count; index++) {
    const b = tileBounds(manifest, index);
    if (
      b.x < rect.x + rect.width &&
      b.x + b.width > rect.x &&
      b.y < rect.y + rect.height &&
      b.y + b.height > rect.y
    )
      out.push(index);
  }
  return out;
}
export function verificationReport(result) {
  const { payload, imageRgba, container, ...evidence } = result;
  void payload;
  void imageRgba;
  void container;
  return evidence;
}
