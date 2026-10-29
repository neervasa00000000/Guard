// SPDX-License-Identifier: MIT
import { encodedDimensions } from "./verifier.js";
import { TILE_LIMITS, GRD3_LIMITS } from "./redactable.js";

// Inspect encoded dimensions before giving compressed bytes to an image decoder.
export function inspectConversionImage(bytes, { allowResize = false, large = false } = {}) {
  if (
    !(bytes instanceof Uint8Array) ||
    !bytes.length ||
    bytes.length > (large ? GRD3_LIMITS.bytes : TILE_LIMITS.bytes)
  )
    throw new Error("Choose an image up to 32 MiB.");
  const ascii = (at, count) =>
    String.fromCharCode(...bytes.subarray(at, at + count));
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let mime, width, height;
  if (bytes[0] === 137 && ascii(1, 3) === "PNG") mime = "image/png";
  else if (bytes[0] === 255 && bytes[1] === 216) mime = "image/jpeg";
  else if (ascii(0, 4) === "RIFF" && ascii(8, 4) === "WEBP")
    mime = "image/webp";
  else if (["GIF87a", "GIF89a"].includes(ascii(0, 6)) && bytes.length >= 13) {
    mime = "image/gif";
    width = view.getUint16(6, true);
    height = view.getUint16(8, true);
  } else if (ascii(0, 2) === "BM" && bytes.length >= 26) {
    mime = "image/bmp";
    const dib = view.getUint32(14, true);
    if (dib === 12) {
      width = view.getUint16(18, true);
      height = view.getUint16(20, true);
    } else if (
      [40, 52, 56, 108, 124].includes(dib) &&
      bytes.length >= 14 + dib
    ) {
      width = view.getInt32(18, true);
      height = Math.abs(view.getInt32(22, true));
    }
  } else
    throw new Error(
      "Use PNG, JPG, WebP, GIF or BMP. Export HEIC, AVIF, PDF and other files to PNG or JPG first.",
    );
  if (width === undefined && !["image/gif", "image/bmp"].includes(mime))
    [width, height] = encodedDimensions(bytes, mime);
  if (
    !Number.isSafeInteger(width) ||
    !Number.isSafeInteger(height) ||
    width < 1 ||
    height < 1 ||
    width > 16384 ||
    height > 16384 ||
    width * height > 50_000_000
  )
    throw new Error(
      "Choose a photo up to 50 megapixels and 16,384 pixels per edge. This image needs resizing before it can be safely opened here.",
    );
  const fitted = fitConversionDimensions(width, height, { large });
  if (!allowResize && (fitted.width !== width || fitted.height !== height))
    throw new Error(
      "This photo exceeds the GRD 4-megapixel output limit. Enable “Fit large photos” to convert it here.",
    );
  return { mime, width, height };
}

export function fitConversionDimensions(width, height, { large = false } = {}) {
  const limits = large ? GRD3_LIMITS : TILE_LIMITS;
  if (
    !Number.isSafeInteger(width) ||
    !Number.isSafeInteger(height) ||
    width < 1 ||
    height < 1
  )
    throw new Error("Invalid image dimensions.");
  const fits = (w, h) =>
    w <= limits.dimension &&
    h <= limits.dimension &&
    w * h <= limits.pixels &&
    Math.ceil(w / 64) * Math.ceil(h / 64) <= limits.tiles;
  if (fits(width, height)) return { width, height };
  let low = 0,
    high = 1;
  for (let i = 0; i < 50; i++) {
    const scale = (low + high) / 2,
      w = Math.max(1, Math.floor(width * scale)),
      h = Math.max(1, Math.floor(height * scale));
    if (fits(w, h)) low = scale;
    else high = scale;
  }
  return {
    width: Math.max(1, Math.floor(width * low)),
    height: Math.max(1, Math.floor(height * low)),
  };
}

export function looksLikeDocument(width,height) {
 if(!Number.isFinite(width)||!Number.isFinite(height)||Math.min(width,height)<=0)return false;
 const ratio=Math.max(width,height)/Math.min(width,height);
 return [85.6/54,Math.SQRT2].some(target=>Math.abs(ratio/target-1)<=.04);
}
