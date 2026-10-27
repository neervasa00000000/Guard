// Ephemeral QA trust anchor only. Never copy the generated QA viewer to production.
import { mkdir, writeFile, readFile } from "node:fs/promises";
import { signer, makeGRD, png } from "../tests/fixtures.mjs";
import { TRUSTED } from "../src/verifier.js";
const dir = "/tmp/guard-qa";
await mkdir(dir, { recursive: true });
const key = signer(),
  valid = makeGRD(key, {
    image: png(960, 640),
    width: 960,
    height: 640,
    meta: {
      author: "Generated QA fixture",
      original_filename: "fixture-landscape.png",
    },
  });
let html = await readFile(
  new URL("../grd_viewer.html", import.meta.url),
  "utf8",
);
for (const field of ["key_id", "public_key_hex", "owner"])
  html = html.replace(TRUSTED[0][field], key.anchor[field]);
html = html.replace("<title>Guard /", "<title>QA FIXTURE ONLY — Guard /");
const bad = Buffer.from(valid);
const imageTable = 10 + 50;
const imageOffset = Number(bad.readBigUInt64LE(imageTable + 2));
bad[imageOffset + 40] ^= 1;
await Promise.all([
  writeFile(dir + "/index.html", html),
  writeFile(dir + "/genuine-test.GRD", valid),
  writeFile(dir + "/tampered-test.GRD", bad),
  writeFile(dir + "/not-a-grd.GRD", "not a signed image"),
  writeFile(
    dir + "/wrong-dimensions.GRD",
    makeGRD(key, { image: png(100, 80), width: 120, height: 80 }),
  ),
  writeFile(dir + "/unknown-key.GRD", makeGRD(signer())),
]);
console.log(
  "Temporary QA files written to " +
    dir +
    ". The production trust list is unchanged.",
);
