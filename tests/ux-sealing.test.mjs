// SPDX-License-Identifier: MIT
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { sealRgba, encodeGRD2, verifyGRD2, redactRects, redactGRD2, tilesForRect, containerImage } from "../src/redactable.js";
import { decodeRgbPng } from "../src/png.js";
import { padBox } from "../src/pad-box.js";

const app = await readFile(new URL("../src/app.js", import.meta.url), "utf8");
const sealCode = app.slice(app.indexOf("async function buildSeal("), app.indexOf('$("redact-checked").onclick'));
function harness({ doc = null, width = 384, height = 128, grid = 16, boxes = [], anchors = [], fail = false } = {}) {
  const nodes = new Map(), downloads = [];
  const $ = id => {
    if (!nodes.has(id)) nodes.set(id, { focus() {}, setAttribute() {}, removeAttribute() {} });
    return nodes.get(id);
  };
  $("convert-privacy").checked = true;
  $("check-sealed").hidden = true;
  $("rounding").value = String(grid);
  const actualCrypto = doc ? { subtle: { generateKey() { throw Error("A received file must never be re-signed"); } } } : crypto;
  const document = {
    createElement: () => ({
      getContext: () => ({
        drawImage() {},
        getImageData: () => ({ data: new Uint8ClampedArray(width * height * 4).fill(255) }),
      }),
    }),
  };
  const setup = new Function("deps", `
    const { $, crypto, document, sealRgba, encodeGRD2, verifyGRD2, redactRects, redactGRD2, tilesForRect, download, File } = deps;
    const editor = deps.editor, activeMode = "seal", selections = [];
    let busy = false, savedFile = null, dragStart = null;
    const drawEditor = () => {};
    const syncConsent = () => { $("convert-submit").disabled = busy || !$("convert-privacy").checked; };
    const setEditorStatus = message => { $("convert-status").textContent = message; };
    ${sealCode}
    return { run: () => $("convert-form").onsubmit({ preventDefault() {} }), saved: () => savedFile };
  `);
  const subject = setup({
    $, document, crypto: actualCrypto, sealRgba, encodeGRD2, redactRects, redactGRD2, tilesForRect, File,
    verifyGRD2: fail ? async () => ({ verdict: "TAMPERED", regionVerified: false }) : bytes => verifyGRD2(bytes, anchors),
    download: (bytes, name) => downloads.push({ bytes, name }),
    editor: { doc, width, height, image: {}, boxes },
  });
  return { $, downloads, ...subject };
}

test("one self-signed GRD2 download applies padded boxes and omits visual data", async () => {
  const box = padBox({ x: 73, y: 51, w: 19, h: 8 }, { grid: 16, imgW: 384, imgH: 128, lineHeight: 48 });
  const h = harness({ boxes: [box] });
  await h.run();
  assert.deepEqual(h.downloads.map(d => d.name), ["image.GRD"]);
  const report = await verifyGRD2(h.downloads[0].bytes, []);
  assert.equal(report.verdict, "UNVERIFIED: SELF-SIGNED");
  assert.equal(report.version, 2);
  assert.equal(report.subTile, 16);
  assert.equal(report.container.manifest.visual, undefined);
  assert.equal(report.regionVerified, true);
  assert.equal(report.hiddenPixelsCleared, true);
  assert.equal(report.redactionMap.reduce((area, b) => area + b.width * b.height, 0), 128 * 48);
  const { rgb, width, height } = await decodeRgbPng(containerImage(report.container));
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const hidden = x >= box.x && x < box.x + box.w && y >= box.y && y < box.y + box.h;
    assert.equal(rgb[(y * width + x) * 3], hidden ? 0 : 255);
  }
  assert.equal(h.$("check-sealed").hidden, false);
  assert(h.saved() instanceof File);
});

test("new pictures above GRD2 dimension limits seal as GRD3 on a 16 px grid", async () => {
  const h = harness({ width: 4097, height: 32, grid: 64 });
  await h.run();
  assert.equal(h.downloads.length, 1, h.$("convert-status").textContent);
  const report = await verifyGRD2(h.downloads[0].bytes, []);
  assert.equal(report.version, 3);
  assert.equal(report.subTile, 16);
  assert.equal(report.regionVerified, true);
});

for (const [version, subTile] of [[2, 16], [3, 16], [2, 64], [3, 64]]) {
  test(`received GRD${version} ${subTile}px files keep their original signature when blacked out`, async () => {
    const key = await crypto.subtle.generateKey("Ed25519", false, ["sign", "verify"]);
    const publicKey = new Uint8Array(await crypto.subtle.exportKey("raw", key.publicKey));
    const anchors = [{ public_key_hex: Buffer.from(publicKey).toString("hex"), name: "Test signer" }];
    const doc = await sealRgba({
      rgba: new Uint8Array(384 * 128 * 4).fill(255), width: 384, height: 128,
      version, subTile, publicKey, sign: bytes => crypto.subtle.sign("Ed25519", key.privateKey, bytes),
    });
    assert.equal((await verifyGRD2(encodeGRD2(doc), anchors)).verdict, "GENUINE");
    const box = padBox({ x: 73, y: 51, w: 19, h: 8 }, { grid: subTile, imgW: 384, imgH: 128 });
    const h = harness({ doc, anchors, grid: subTile, boxes: [box] });
    await h.run();
    assert.equal(h.downloads.length, 1, h.$("convert-status").textContent);
    const report = await verifyGRD2(h.downloads[0].bytes, anchors);
    assert.equal(report.verdict, "VERIFIED WITH REDACTIONS");
    assert.equal(report.hiddenPixelsCleared, true);
    assert.deepEqual(report.container.manifest, doc.manifest);
    assert.equal(report.container.signature, doc.signature);
    assert.equal((await verifyGRD2(h.downloads[0].bytes, [])).verdict, "UNTRUSTED SIGNER");
  });
}

test("failed self-check produces no file or follow-up link", async () => {
  const h = harness({ fail: true });
  await h.run();
  assert.equal(h.downloads.length, 0);
  assert.equal(h.$("check-sealed").hidden, true);
  assert.match(h.$("convert-status").textContent, /Nothing was downloaded/);
});

test("the viewer remains self-contained and omits retired tools", async () => {
  const html = await readFile(new URL("../index.html", import.meta.url), "utf8");
  assert.equal(html.match(/http-equiv="Content-Security-Policy"\s+content="([^"]+)"/)[1],
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src blob: data:; connect-src 'none'; worker-src blob:; object-src 'none'; base-uri 'none'; form-action 'none'");
  assert.doesNotMatch(html, /<script[^>]+src=|<link[^>]+rel="stylesheet"|\b(?:localStorage|indexedDB|navigator\.serviceWorker)\s*[.(]/);
  assert.doesNotMatch(html, /Hold to reveal|Full view|Fit large photos|Also save the full original|Check a recompressed copy|function (?:exportProof|verifyVisual|createOfflineSigner|verifyTrustBundle)\b/);
});
