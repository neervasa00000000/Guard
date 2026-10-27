import test from "node:test";
import assert from "node:assert/strict";
import { inspectConversionImage } from "../src/converter.js";
import { png } from "./fixtures.mjs";

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
  assert.throws(() => inspectConversionImage(png(4096, 1025)), /4 megapixels/);
  assert.throws(() => inspectConversionImage(new Uint8Array(0)), /32 MiB/);
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
  assert.throws(() => inspectConversionImage(gif), /4 megapixels/);
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
  assert.throws(() => inspectConversionImage(bmp), /4 megapixels/);
});
