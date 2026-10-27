import { encodedDimensions } from "./verifier.js";
import { TILE_LIMITS } from "./redactable.js";

// Inspect encoded dimensions before giving compressed bytes to an image decoder.
export function inspectConversionImage(bytes) {
  if (
    !(bytes instanceof Uint8Array) ||
    !bytes.length ||
    bytes.length > TILE_LIMITS.bytes
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
    width > TILE_LIMITS.dimension ||
    height > TILE_LIMITS.dimension ||
    width * height > TILE_LIMITS.pixels
  )
    throw new Error(
      "Choose an image up to 4 megapixels and 4,096 pixels per edge. Resize it first; conversion never silently reduces quality.",
    );
  return { mime, width, height };
}
