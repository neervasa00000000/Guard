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

test("fitConversionDimensions handles standard photo aspect ratios and extremes", () => {
  const p3840 = fitConversionDimensions(3840, 2556);
  assert.ok(p3840.width * p3840.height <= 4_194_304);
  assert.ok(Math.ceil(p3840.width / 64) * Math.ceil(p3840.height / 64) <= 1024);
  const ratioOrig = 3840 / 2556;
  const ratioFitted = p3840.width / p3840.height;
  assert.ok(Math.abs(ratioFitted - ratioOrig) / ratioOrig < 0.01);

  const p8000 = fitConversionDimensions(8000, 6000);
  assert.ok(p8000.width * p8000.height <= 4_194_304);
  assert.ok(Math.ceil(p8000.width / 64) * Math.ceil(p8000.height / 64) <= 1024);

  const pNarrow = fitConversionDimensions(16384, 1);
  assert.ok(pNarrow.width <= 4096);
  assert.ok(pNarrow.height >= 1);
  assert.ok(pNarrow.width * pNarrow.height <= 4_194_304);
  assert.ok(Math.ceil(pNarrow.width / 64) * Math.ceil(pNarrow.height / 64) <= 1024);

  assert.deepEqual(fitConversionDimensions(1500, 1500), {
    width: 1500,
    height: 1500,
  });
});

test("end-to-end 12 MP photo downscale, seal and verify passes", async () => {
  const { generateKeyPairSync, sign: nodeSign } = await import("node:crypto");
  const { sealRgba, encodeGRD2, verifyGRD2 } = await import(
    "../src/redactable.js"
  );
  const origW = 4000,
    origH = 3000;
  const fitted = fitConversionDimensions(origW, origH);
  assert.ok(fitted.width * fitted.height <= 4_194_304);
  assert.ok(
    Math.ceil(fitted.width / 64) * Math.ceil(fitted.height / 64) <= 1024,
  );

  const fittedRgba = new Uint8Array(fitted.width * fitted.height * 4);
  let seed = 42;
  for (let i = 0; i < fittedRgba.length; i += 4) {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    fittedRgba[i] = seed & 0xff;
    fittedRgba[i + 1] = (seed >>> 8) & 0xff;
    fittedRgba[i + 2] = (seed >>> 16) & 0xff;
    fittedRgba[i + 3] = 255;
  }
  const { publicKey, privateKey } = generateKeyPairSync("ed25519");
  const rawPub = publicKey
    .export({ type: "spki", format: "der" })
    .subarray(-32);
  const sealed = await sealRgba({
    rgba: fittedRgba,
    width: fitted.width,
    height: fitted.height,
    publicKey: rawPub,
    purpose: "personal",
    sign: (b) => nodeSign(null, Buffer.from(b), privateKey),
  });
  const res = await verifyGRD2(encodeGRD2(sealed), []);
  assert.equal(res.verdict, "UNVERIFIED: SELF-SIGNED");
  assert.equal(res.viewable, true);
});

test("actual conversion submit handler downloads and opens the signed file with a valid size summary", async () => {
  const { readFile } = await import("node:fs/promises");
  const { sealRgba, encodeGRD2, verifyGRD2 } = await import("../src/redactable.js");
  const app = await readFile(new URL("../src/app.js", import.meta.url), "utf8");
  const start = app.indexOf('$("convert-form").onsubmit =');
  assert.ok(start >= 0, "conversion submit handler exists");
  const nodes = new Map();
  const $ = id => {
    if (!nodes.has(id)) nodes.set(id, { disabled: false, setAttribute() {}, removeAttribute() {}, focus() {} });
    return nodes.get(id);
  };
  $("convert-privacy").checked=true;
  const messages = [], downloads = [], opened = [];
  const execute = new Function("$", "conversionImage", "conversionVersion", "operation", "crypto", "sealRgba", "encodeGRD2", "verifyGRD2", "conversionStatus", "download", "openFile", "File", "bytesLabel", "offlineSignerVersion", "unlockedSigner", "TRUSTED", "sessionTrust",
    app.slice(start,app.indexOf('$("copy-form").onsubmit',start)) + '\nreturn $("convert-form").onsubmit({preventDefault() {}});');
  await execute($, { rgba: new Uint8Array(64 * 64 * 4).fill(255), width: 64, height: 64, name: "TEST ONLY.png", sourceBytes: 4096 }, 1, 1, crypto, sealRgba, encodeGRD2, verifyGRD2,
    message => messages.push(message), (...args) => downloads.push(args), async file => opened.push(file), File, n => `${n} bytes`, 0, null, [], async()=>({policy:(await import('../src/trust.js')).TRUST_POLICY}));
  assert.equal(downloads.length, 1, messages.join("\n"));
  assert.equal(downloads[0][1], "image.GRD");
  assert.equal(opened.length, 1);
  assert.match(messages.at(-1), /Downloaded image.GRD/);
  assert.doesNotMatch(messages.at(-1), /NaN|Infinity|failed/);
  assert.equal((await verifyGRD2(downloads[0][0], [])).verdict, "UNVERIFIED: SELF-SIGNED");
  assert.equal($("convert-submit").disabled, false);
  assert.equal($("convert-input").disabled, false);
});

test('ID/document shape heuristic covers both orientations and leaves squares unflagged',async()=>{
 const {looksLikeDocument}=await import('../src/converter.js');for(const [w,h] of [[1012,638],[638,1012],[1414,1000],[1000,1414]])assert.equal(looksLikeDocument(w,h),true);
 for(const [w,h] of [[1000,1000],[1,0],[Infinity,10],[2000,500]])assert.equal(looksLikeDocument(w,h),false);
});
