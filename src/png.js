// SPDX-License-Identifier: MIT
// GRD2 canonical image codec: 8-bit RGB, non-interlaced PNG with no ancillary chunks.
// Uses native DEFLATE streams in current browsers and Node 22; no remote decoder.
export class PngFormatError extends Error {}
const PNG_SIGNATURE = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]);
const PNG_CRC_TABLE = Uint32Array.from({length:256}, (_, value) => {
  let c=value;for(let bit=0;bit<8;bit++)c=(c>>>1)^((c&1)?0xedb88320:0);return c>>>0;
});
function pngCrc(bytes) {
  let c=0xffffffff;
  for(let i=0;i<bytes.length;i++)c=(c>>>8)^PNG_CRC_TABLE[(c^bytes[i])&255];
  return (c^0xffffffff)>>>0;
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
      if (length > limit) throw new PngFormatError("PNG decompression limit exceeded.");
      parts.push(value);
    }
  } catch (error) {
    if (error instanceof PngFormatError) throw error;
    if (!compress && (error instanceof TypeError || ["Z_DATA_ERROR","Z_BUF_ERROR"].includes(error?.code) || error?.name === "DataError"))
      throw new PngFormatError("Invalid PNG deflate stream: " + error.message);
    throw error;
  } finally {
    await reader.cancel().catch(() => {});
  }
  return pngJoin(parts);
}
export async function encodeRgbPng(rgb, width, height) {
  if (rgb.length !== width * height * 3 || width < 1 || height < 1 || width > 8192 || height > 8192 || width * height > 36_000_000)
    throw new PngFormatError("Invalid RGB image dimensions or length.");
  let y = 0;
  const rows = new ReadableStream({ pull(controller) {
    if (y === height) { controller.close(); return; }
    const count = Math.min(64, height-y), bytes = new Uint8Array(count * (width*3+1));
    for (let row=0;row<count;row++) bytes.set(rgb.subarray((y+row)*width*3,(y+row+1)*width*3),row*(width*3+1)+1);
    y+=count;controller.enqueue(bytes);
  }});
  const hdr = new Uint8Array(13), view = new DataView(hdr.buffer);
  view.setUint32(0,width);view.setUint32(4,height);hdr[8]=8;hdr[9]=2;
  const parts=[PNG_SIGNATURE,pngChunk("IHDR",hdr)];
  const reader=rows.pipeThrough(new CompressionStream("deflate")).getReader();
  try { for (;;) { const {value,done}=await reader.read(); if(done)break; parts.push(pngChunk("IDAT",value)); } }
  finally { await reader.cancel().catch(()=>{}); }
  parts.push(pngChunk("IEND",new Uint8Array()));return pngJoin(parts);
}
export async function decodeRgbPng(bytes, limits) {
  if (limits) {
    const {width,height}=rgbPngParts(bytes,limits), rgb=new Uint8Array(width*height*3);
    for await (const band of decodeRgbPngBands(bytes,limits)) rgb.set(band.rgb,band.y*width*3);
    return {rgb,width,height};
  }
  if (
    !(bytes instanceof Uint8Array) ||
    bytes.length < 45 ||
    PNG_SIGNATURE.some((b, i) => bytes[i] !== b)
  )
    throw new PngFormatError("Not a GRD2 RGB PNG.");
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
    if (end > bytes.length) throw new PngFormatError("Truncated PNG chunk.");
    const type = String.fromCharCode(...bytes.subarray(offset + 4, offset + 8)),
      data = bytes.subarray(offset + 8, end - 4);
    if (pngCrc(bytes.subarray(offset + 4, end - 4)) !== view.getUint32(end - 4))
      throw new PngFormatError("PNG checksum failed.");
    if (type === "IHDR") {
      if (offset !== 8 || size !== 13)
        throw new PngFormatError("Invalid PNG header order.");
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
        throw new PngFormatError("GRD2 needs bounded 8-bit RGB, non-interlaced PNG.");
    } else if (type === "IDAT") {
      if (!width || ended) throw new PngFormatError("Invalid PNG data order.");
      idats.push(data);
      seenData = true;
    } else if (type === "IEND") {
      if (size || !seenData || end !== bytes.length)
        throw new PngFormatError("Invalid PNG end.");
      ended = true;
      offset = end;
      break;
    } else
      throw new PngFormatError(
        "GRD2 PNG contains unsupported ancillary or critical chunks: " + type,
      );
    offset = end;
  }
  if (!ended || !idats.length) throw new PngFormatError("Incomplete PNG.");
  const stride = width * 3,
    raw = await pngStream(pngJoin(idats), false, height * (stride + 1));
  if (raw.length !== height * (stride + 1))
    throw new PngFormatError("Wrong PNG pixel length.");
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
    if (filter > 4) throw new PngFormatError("Unknown PNG filter.");
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

// Strict PNG framing is shared by the streaming verifier and full-image decoder.
export function rgbPngParts(bytes, { dimension = 4096, pixels = 4_194_304 } = {}) {
  if (!(bytes instanceof Uint8Array) || bytes.length < 45 || PNG_SIGNATURE.some((b, i) => bytes[i] !== b))
    throw new PngFormatError('Invalid RGB PNG signature.');
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength), idats = [];
  let offset = 8, width, height, ended = false, dataSeen = false;
  while (offset + 12 <= bytes.length) {
    const length = view.getUint32(offset), end = offset + length + 12;
    if (end > bytes.length) throw new PngFormatError('Truncated PNG chunk.');
    const type = String.fromCharCode(...bytes.subarray(offset + 4, offset + 8));
    const data = bytes.subarray(offset + 8, end - 4);
    if (pngCrc(bytes.subarray(offset + 4, end - 4)) !== view.getUint32(end - 4)) throw new PngFormatError('PNG checksum failed.');
    if (type === 'IHDR') {
      if (offset !== 8 || length !== 13) throw new PngFormatError('Invalid PNG header order.');
      width = view.getUint32(offset + 8); height = view.getUint32(offset + 12);
      if (!width || !height || width > dimension || height > dimension || width * height > pixels || data[8] !== 8 || data[9] !== 2 || data[10] || data[11] || data[12])
        throw new PngFormatError('Unsupported PNG dimensions or pixel format.');
    } else if (type === 'IDAT') {
      if (!width || ended) throw new PngFormatError('PNG data before header.');
      idats.push(data); dataSeen = true;
    } else if (type === 'IEND') {
      if (length || !dataSeen || end !== bytes.length) throw new PngFormatError('Invalid PNG end.');
      ended = true; break;
    } else throw new PngFormatError('Unexpected PNG chunk: ' + type);
    offset = end;
  }
  if (!ended) throw new PngFormatError('Incomplete PNG.');
  return { width, height, idats };
}
export async function* decodeRgbPngBands(bytes, limits = { dimension: 8192, pixels: 36_000_000 }) {
  const { width, height, idats } = rgbPngParts(bytes, limits), stride = width * 3;
  let part = 0, offset = 0;
  const packed = new ReadableStream({ pull(controller) {
    while (part < idats.length && offset === idats[part].length) { part++; offset = 0; }
    if (part === idats.length) { controller.close(); return; }
    const end = Math.min(offset + 16_384, idats[part].length);
    controller.enqueue(idats[part].subarray(offset, end)); offset = end;
  }});
  const reader = packed.pipeThrough(new DecompressionStream('deflate')).getReader();
  let pending = new Uint8Array(), previous = new Uint8Array(stride), row = 0;
  let band = new Uint8Array(Math.min(64, height) * stride), inBand = 0;
  const paeth = (a, b, c) => { const p = a + b - c, x = Math.abs(p-a), y = Math.abs(p-b), z = Math.abs(p-c); return x <= y && x <= z ? a : y <= z ? b : c; };
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      const raw = pngJoin([pending, value]); let at = 0;
      while (raw.length - at >= stride + 1) {
        if (row >= height) throw new PngFormatError('Extra decompressed PNG bytes.');
        const filter = raw[at++]; if (filter > 4) throw new PngFormatError('Unknown PNG filter.');
        const current = band.subarray(inBand * stride, (inBand + 1) * stride);
        if (filter === 0) { current.set(raw.subarray(at,at+stride)); at += stride; }
        else for (let x = 0; x < stride; x++) {
          const a = x >= 3 ? current[x-3] : 0, b = previous[x], c = x >= 3 ? previous[x-3] : 0;
          const prediction = filter === 0 ? 0 : filter === 1 ? a : filter === 2 ? b : filter === 3 ? Math.floor((a+b)/2) : paeth(a,b,c);
          current[x] = (raw[at++] + prediction) & 255;
        }
        previous.set(current); row++; inBand++;
        if (inBand === 64 || row === height) {
          yield { y: row-inBand, width, height, rows: inBand, rgb: band };
          inBand = 0; band = new Uint8Array(Math.min(64, height-row) * stride);
        }
      }
      pending = raw.slice(at);
    }
    if (row !== height || pending.length) throw new PngFormatError('Wrong PNG pixel length.');
  } catch (error) {
    if (error instanceof PngFormatError) throw error;
    if (error instanceof TypeError || ['Z_DATA_ERROR','Z_BUF_ERROR'].includes(error?.code) || error?.name === 'DataError') throw new PngFormatError('Invalid PNG deflate stream.');
    throw error;
  } finally { await reader.cancel().catch(() => {}); }
}
