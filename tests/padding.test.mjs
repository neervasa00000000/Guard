// SPDX-License-Identifier: MIT
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { padBox, boxUnionArea } from "../src/pad-box.js";

const vectors = JSON.parse(await readFile(new URL("./vectors/padding-vectors.json", import.meta.url)));
for (const { name, box, image: [imgW, imgH], grid, widthClass, lineHeight, expected } of vectors) {
  test(name, () => assert.deepEqual(padBox(box, { imgW, imgH, grid, widthClass, lineHeight }), expected));
}

test("padding always contains the original selection and covers whole grid cells", () => {
  let seed = 4109;
  const next = max => (seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) % max;
  for (let i = 0; i < 3000; i++) {
    const imgW = next(512) + 1, imgH = next(333) + 1;
    const grid = [8, 16, 32, 64][i % 4];
    const x = next(imgW), y = next(imgH), w = next(imgW - x) + 1, h = next(imgH - y) + 1;
    const lineHeight = next(400) + 1;
    const padded = padBox({ x, y, w, h }, { grid, imgW, imgH, lineHeight });
    const right = padded.x + padded.w, bottom = padded.y + padded.h;
    assert(padded.x >= 0 && padded.x <= x && right >= x + w && right <= imgW);
    assert(padded.y >= 0 && padded.y <= y && bottom >= y + h && bottom <= imgH);
    assert.equal(padded.x % grid, 0);
    assert.equal(padded.y % grid, 0);
    assert(right === imgW || right % grid === 0);
    assert(bottom === imgH || bottom % grid === 0);
    assert(padded.h >= Math.min(lineHeight, imgH));
    if (right !== imgW || imgW % grid === 0)
      assert(padded.w === imgW || padded.w % 128 === 0);
  }
});

test("overlapping boxes count only once in the live area metric", () => {
  assert.equal(boxUnionArea([{ x: 0, y: 0, w: 32, h: 32 }, { x: 16, y: 16, w: 32, h: 32 }]), 1792);
  assert.equal(boxUnionArea([]), 0);
});

test("invalid coordinates or padding settings are rejected", () => {
  const box = { x: 0, y: 0, w: 20, h: 20 }, options = { grid: 16, imgW: 64, imgH: 64 };
  for (const invalid of [{ x: -1 }, { x: 64 }, { w: 0 }, { y: NaN }, { h: Infinity }])
    assert.throws(() => padBox({ ...box, ...invalid }, options), RangeError);
  for (const invalid of [{ grid: 0 }, { widthClass: 127 }, { lineHeight: -1 }])
    assert.throws(() => padBox(box, { ...options, ...invalid }), RangeError);
});
