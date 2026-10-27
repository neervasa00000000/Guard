import test from "node:test";
import assert from "node:assert/strict";
import {
  inspectConversionImage,
  fitConversionDimensions,
} from "../src/converter.js";
import { png } from "./fixtures.mjs";
function pngHeader(width, height) {
  const bytes = png(1, 1).subarray(0, 24);
  bytes.writeUInt32BE(width, 16);
  bytes.writeUInt32BE(height, 20);
  return bytes;
}

test("conversion inspects PNG pixels rather than trusting filename or MIME", () => {
  assert.deepEqual(inspectConversionImage(png(70, 68)), {
    mime: "image/png",
    width: 70,
    height: 68,
  });
  assert.throws(
    () =>
      inspectConversionImage(
        new TextEncoder().encode("<svg>not an image</svg>"),
      ),
    /Use PNG/,
  );
  assert.throws(
    () => inspectConversionImage(pngHeader(4096, 1025)),
    /Fit large photos/,
  );
  assert.throws(() => inspectConversionImage(new Uint8Array(0)), /32 MiB/);
});
test("camera photos fit output pixel, edge and tile-count bounds without upscaling", () => {
  for (const [width, height] of [
    [6000, 4000],
    [4000, 6000],
    [8000, 6000],
    [16000, 200],
    [3000, 1398],
    [192, 128],
  ]) {
    const out = fitConversionDimensions(width, height);
    assert.ok(out.width <= width && out.height <= height);
    assert.ok(out.width <= 4096 && out.height <= 4096);
    assert.ok(out.width * out.height <= 4194304);
    assert.ok(Math.ceil(out.width / 64) * Math.ceil(out.height / 64) <= 1024);
    assert.ok(Math.abs(out.height - (height * out.width) / width) <= 2);
  }
  assert.deepEqual(fitConversionDimensions(192, 128), {
    width: 192,
    height: 128,
  });
  assert.deepEqual(
    inspectConversionImage(pngHeader(6000, 4000), { allowResize: true }),
    { mime: "image/png", width: 6000, height: 4000 },
  );
  assert.throws(
    () => inspectConversionImage(pngHeader(10000, 6000), { allowResize: true }),
    /50 megapixels/,
  );
});
test("conversion bounds GIF and BMP dimensions before decode", () => {
  const gif = new Uint8Array(13);
  gif.set(new TextEncoder().encode("GIF89a"));
  const g = new DataView(gif.buffer);
  g.setUint16(6, 320, true);
  g.setUint16(8, 240, true);
  assert.deepEqual(inspectConversionImage(gif), {
    mime: "image/gif",
    width: 320,
    height: 240,
  });
  g.setUint16(6, 65535, true);
  assert.throws(() => inspectConversionImage(gif), /50 megapixels/);
  const bmp = new Uint8Array(54);
  bmp.set([66, 77]);
  const b = new DataView(bmp.buffer);
  b.setUint32(14, 40, true);
  b.setInt32(18, 240, true);
  b.setInt32(22, -320, true);
  assert.deepEqual(inspectConversionImage(bmp), {
    mime: "image/bmp",
    width: 240,
    height: 320,
  });
  b.setInt32(18, -240, true);
  assert.throws(() => inspectConversionImage(bmp), /50 megapixels/);
});
