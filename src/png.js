// SPDX-License-Identifier: MIT
// GRD2 canonical image codec: 8-bit RGB, non-interlaced PNG with no ancillary chunks.
// Uses native DEFLATE streams in current browsers and Node 22; no remote decoder.
const PNG_SIGNATURE = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]);
function pngCrc(bytes) {
  let c = 0xffffffff;
  for (const b of bytes) {
    c ^= b;
    for (let i = 0; i < 8; i++) c = (c >>> 1) ^ (c & 1 ? 0xedb88320 : 0);
  }
  return (c ^ 0xffffffff) >>> 0;
}
function pngJoin(arrays) {
  const out = new Uint8Array(arrays.reduce((n, a) => n + a.length, 0));
  let offset = 0;
  for (const a of arrays) {
    out.set(a, offset);
    offset += a.length;
  }
  return out;
}
function pngChunk(type, data) {
  const name = new TextEncoder().encode(type),
    out = new Uint8Array(12 + data.length),
    view = new DataView(out.buffer);
  view.setUint32(0, data.length);
  out.set(name, 4);
  out.set(data, 8);
  view.setUint32(8 + data.length, pngCrc(out.subarray(4, 8 + data.length)));
  return out;
}
async function pngStream(bytes, compress, limit) {
  const stream = new Blob([bytes])
      .stream()
      .pipeThrough(
        compress
          ? new CompressionStream("deflate")
          : new DecompressionStream("deflate"),
      ),
    reader = stream.getReader(),
    parts = [];
  let length = 0;
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      length += value.length;
      if (length > limit) throw new Error("PNG decompression limit exceeded.");
      parts.push(value);
    }
  } finally {
    await reader.cancel().catch(() => {});
  }
  return pngJoin(parts);
}
export async function encodeRgbPng(rgb, width, height) {
  if (rgb.length !== width * height * 3)
    throw new Error("Invalid RGB image length.");
  const rows = new Uint8Array(height * (width * 3 + 1));
  for (let y = 0; y < height; y++)
    rows.set(
      rgb.subarray(y * width * 3, (y + 1) * width * 3),
      y * (width * 3 + 1) + 1,
    );
  const hdr = new Uint8Array(13),
    view = new DataView(hdr.buffer);
  view.setUint32(0, width);
  view.setUint32(4, height);
  hdr[8] = 8;
  hdr[9] = 2;
  return pngJoin([
    PNG_SIGNATURE,
    pngChunk("IHDR", hdr),
    pngChunk("IDAT", await pngStream(rows, true, 32 * 1024 * 1024)),
    pngChunk("IEND", new Uint8Array()),
  ]);
}
export async function decodeRgbPng(bytes) {
  if (
    !(bytes instanceof Uint8Array) ||
    bytes.length < 45 ||
    PNG_SIGNATURE.some((b, i) => bytes[i] !== b)
  )
    throw new Error("Not a GRD2 RGB PNG.");
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength),
    idats = [];
  let offset = 8,
    width,
    height,
    ended = false,
    seenData = false;
  while (offset + 12 <= bytes.length) {
    const size = view.getUint32(offset),
      end = offset + 12 + size;
    if (end > bytes.length) throw new Error("Truncated PNG chunk.");
    const type = String.fromCharCode(...bytes.subarray(offset + 4, offset + 8)),
      data = bytes.subarray(offset + 8, end - 4);
    if (pngCrc(bytes.subarray(offset + 4, end - 4)) !== view.getUint32(end - 4))
      throw new Error("PNG checksum failed.");
    if (type === "IHDR") {
      if (offset !== 8 || size !== 13)
        throw new Error("Invalid PNG header order.");
      width = view.getUint32(offset + 8);
      height = view.getUint32(offset + 12);
      if (
        width < 1 ||
        height < 1 ||
        width > 4096 ||
        height > 4096 ||
        width * height > 4_194_304 ||
        data[8] !== 8 ||
        data[9] !== 2 ||
        data[10] ||
        data[11] ||
        data[12]
      )
        throw new Error("GRD2 needs bounded 8-bit RGB, non-interlaced PNG.");
    } else if (type === "IDAT") {
      if (!width || ended) throw new Error("Invalid PNG data order.");
      idats.push(data);
      seenData = true;
    } else if (type === "IEND") {
      if (size || !seenData || end !== bytes.length)
        throw new Error("Invalid PNG end.");
      ended = true;
      offset = end;
      break;
    } else
      throw new Error(
        "GRD2 PNG contains unsupported ancillary or critical chunks: " + type,
      );
    offset = end;
  }
  if (!ended || !idats.length) throw new Error("Incomplete PNG.");
  const stride = width * 3,
    raw = await pngStream(pngJoin(idats), false, height * (stride + 1));
  if (raw.length !== height * (stride + 1))
    throw new Error("Wrong PNG pixel length.");
  const rgb = new Uint8Array(width * height * 3);
  const paeth = (a, b, c) => {
    const p = a + b - c,
      pa = Math.abs(p - a),
      pb = Math.abs(p - b),
      pc = Math.abs(p - c);
    return pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
  };
  for (let y = 0; y < height; y++) {
    const filter = raw[y * (stride + 1)];
    if (filter > 4) throw new Error("Unknown PNG filter.");
    for (let x = 0; x < stride; x++) {
      const at = y * stride + x,
        a = x >= 3 ? rgb[at - 3] : 0,
        b = y ? rgb[at - stride] : 0,
        c = y && x >= 3 ? rgb[at - stride - 3] : 0;
      const predict =
        filter === 0
          ? 0
          : filter === 1
            ? a
            : filter === 2
              ? b
              : filter === 3
                ? Math.floor((a + b) / 2)
                : paeth(a, b, c);
      rgb[at] = (raw[y * (stride + 1) + 1 + x] + predict) & 255;
    }
  }
  return { rgb, width, height };
}
