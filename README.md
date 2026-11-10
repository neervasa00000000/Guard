# TileSeal

TileSeal (repository: Guard) lets you black out parts of a picture, seal it as a `.GRD` file, and check the retained pixels later. Images are processed inside your browser.

Open the standalone [index.html](index.html) in a current browser, or run `npm run dev` and open `http://127.0.0.1:4195/`. Choose a picture, drag or enter blackout areas, review the preview and download. The editor starts at 16 px rounding with width-class padding enabled. Use **Check a file** to inspect an existing GRD1, GRD2 or GRD3. GRD2 and GRD3 can be blacked out again without the signer key.

New browser files use a one-time key and show **UNVERIFIED: SELF-SIGNED**. **GENUINE** and **VERIFIED WITH REDACTIONS** require the verifier's configured signer trust. Unknown signer pictures require an explicit action before display. The result describes the signed file and its retained pixels.

Supported pictures are PNG, JPG, WebP, GIF and BMP, up to 256 MiB and within the GRD3 limits of 36 MP, 8,192 px per edge and 9,000 parent tiles. Larger pictures need resizing before selection. The browser chooses GRD2 or GRD3 based on the existing format limits. **Download plain picture** creates a PNG with the hidden pixels blacked out. Keep the GRD if you need to check the proof again.

See the [manual test plan and removal list](TILESEAL.md), [CLI guide](REDACTION.md), [format specification](GRD_SPEC.md), [privacy notice](PRIVACY.md) and [MIT licence](LICENSE).

Exit 0 means GENUINE only. Other verdicts use the non-zero groups below; inspect the JSON verdict for the precise result. Treat any non-zero code as 'not proven genuine'.

### CLI exit codes

| Exit | Verdict |
|------|---------|
| 0 | GENUINE |
| 1 | Operational error (I/O, bad key file, write refused) |
| 2 | TAMPERED, VISUALLY INCONSISTENT (also argparse usage errors; inspect JSON) |
| 3 | NOT A GRD |
| 4 | CANNOT VERIFY, UNSUPPORTED, LIMIT EXCEEDED, UNREADABLE |
| 5 | VISUALLY CONSISTENT, VERIFIED WITH REDACTIONS, FULLY REDACTED, DEMO, UNVERIFIED: SELF-SIGNED, UNTRUSTED SIGNER |
| 6 | REVOKED KEY |
| 7 | BORDERLINE (decoder-dependent): close to the threshold; treat as not proven |

These groups replace the earlier 10–43 codes. Scripts must read the JSON verdict or migrate their exit-code handling.

## Hosting

For browser-enforced anti-framing, host on a platform that sends Content-Security-Policy: frame-ancestors 'none' (for example Cloudflare Pages using _headers, or Netlify). GitHub Pages cannot send it.

## Build and test

```sh
npm run build
npm test
```

Build produces identical `index.html` and `grd_viewer.html` files with inline CSS and JavaScript. Both are directly usable; GitHub Pages can serve the repository root.

The automated suite additionally covers GRD2 proof/mask/pixel tampering, chained redaction, full redaction, revoked keys, 2,000 deterministic GRD2 bit mutations, and independent Python ↔ JavaScript issue/redact/verify round trips. Optional C2PA integration checks a real SDK-signed PNG with an explicitly trusted temporary test CA and rejects a pixel-modified export. These mutation counts are not a security proof.

The legacy suite includes **7,504 single-bit mutations** across a generated 938-byte GRD1 fixture, all rejected; unknown keys with valid signatures; truncated and extended files; unsafe offsets; duplicate sections; invalid metadata; size limits; typed-array offsets; optional sections; and acceptance comparison with the supplied reference verifier. It does not reproduce the absent Goose Bumps/server test suite.

For UI testing only:

```sh
node scripts/browser-fixtures.mjs
python3 -m http.server 4196 --bind 127.0.0.1 --directory /tmp/guard-qa
```

This creates a temporary QA viewer with an **ephemeral test trust anchor**, plus valid/tampered/unknown-key fixtures. Never publish that generated QA viewer. Production output uses the bundled signer registry and revocation policy. No private signing key is stored or shipped.

## Source map

- `src/app.js` handles file intake, the editor, signing and verification.
- `src/pad-box.js` and `grd_geometry.py` implement matching blackout geometry.
- `src/index.template.html`, `src/style.css` and `scripts/build.mjs` build the standalone page.
- `tests/vectors/padding-vectors.json` is shared by the JavaScript and Python tests.
- `REPRODUCE.md`, `UX_STATUS.md` and `UI_POLISH.md` include historical evidence for earlier Guard builds.
