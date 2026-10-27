# Guard / GRD Inspector — selective redaction

## Convert, redact and verify

Use **Make a .GRD** on the live site to convert PNG, JPG, WebP, GIF or BMP locally. Preview, convert and download; the result opens below for redaction. Converted files are explicitly **UNVERIFIED: SELF-SIGNED**, not identity-trusted. Inputs up to 32 MiB / 50 megapixels; “Fit large photos” previews a smaller copy within GRD’s 4-megapixel output limit. GRD2 files are lossless and typically 3–8× larger than the source JPEG. Unsupported formats need a PNG/JPG export first. See [conversion details](REDACTION.md#convert-an-image-in-the-browser).

[Experimental GRD2 specification](GRD_SPEC.md) · [Commands and trust boundaries](REDACTION.md)

Mark private regions and export a copy whose **retained pixels** still match the signed original. No private key is needed to redact. Hidden regions are clearly marked and excluded from the authenticity claim. The built-in example and `examples/` assets are fictional **DEMO / NOT TRUSTED EVIDENCE**.

GRD2 is a new experimental canonical-JSON wire format, not a binary extension understood by existing GRD1 tools. GRD1 support is retained. Both versions check a bundled offline revoked-key snapshot; an old viewer cannot know newer revocations. An optional bridge exports a standard C2PA PNG with a custom GRD proof assertion, using the official CAI SDK and your exporter certificate. Standard tools recognise the PNG credentials; regional verification requires the Guard profile.

No claim is made that this is the first open format or ready for legal evidence. The [C2PA specification](https://spec.c2pa.org/specifications/specifications/2.4/specs/C2PA_Specification.html) already covers assertion redaction, regions and Merkle structures. This prototype needs independent cryptographic review before sensitive use.

A single-file, dependency-free browser viewer for the `.GRD` format in the supplied `grd_viewer.html`. It verifies signed bytes against a pinned Ed25519 public key, then provides intentional image viewing and a downloadable verification report.

**The original repository was empty.** This implementation starts from the supplied offline viewer, preserved in `reference/grd_viewer.original.html`. The original server, Convert, Check/copy-tracing service, Android app, private signing keys and Goose Bumps sample were not supplied. Their behaviour and the previously reported 9,118 mutation tests cannot be independently confirmed here.

**Live viewer:** https://neervasa00000000.github.io/Guard/

## Use

Open `grd_viewer.html` in a current browser and choose or drop a `.GRD` file. It works offline with browser WebCrypto support for Ed25519. No file is uploaded. A browser without the required crypto support reports **UNSUPPORTED**, rather than asserting tampering.

Or run locally:

```sh
npm run dev
```

Open http://127.0.0.1:4195/. The standalone viewer needs no installation. Use `npm ci` before builds/tests. Node.js 22+ is used for builds/tests; Python 3 serves the local preview.

## What changed

- A responsive verification workspace: file intake, verdict, named checks and signed details.
- Clear states for genuine, failed integrity/trust, invalid format, unsupported capabilities, oversized input and unreadable images.
- Bounds-checked BigInt section offsets, exact contiguity, no duplicates, required sections, no trailing data, fixed signature entry and bounded metadata parsing.
- Pinned signer identity remains mandatory. An embedded public key and a mathematically valid signature alone are insufficient.
- File size is checked **before** reading (64 MiB). Images are limited to PNG/JPEG/WebP, 40 megapixels and 16,384 pixels per edge. Encoded dimensions are checked before decoding, then compared with decoded dimensions and signed metadata.
- Replacing/cancelling a file invalidates stale async results. Old bitmaps and redraw timers are disposed.
- Keyboard file selection, focus feedback, reduced motion, browser zoom and 44px controls. Reveal can be operated with Space/Enter and arrow keys.
- Hide on window blur, tab switching and printing. Resuming restores hold-to-reveal, not full view.
- Local JSON reports contain checks, metadata, hashes and the verification scope; no image/recovery bytes. Reports include signed metadata, so treat them as potentially personal documents.
- The offline download is captured from the initial clean page, so it does not contain a previously opened file's metadata or image.
- No clipboard overwrites, global copy shortcuts, zoom blocking, analytics, external fonts, runtime dependencies or service-worker cache.
- The page CSP disallows network connections. Only explicit outbound navigation (such as opening the source link) leaves the viewer.

## Verification scope

**GENUINE** means that this viewer's cryptographic and image checks passed against its pinned signer list. It is not independent proof of authorship, ownership, legal rights, historical creation time or the safety of the depicted content. The viewer itself must come from a trusted source: changing the HTML can change its trust policy.

Signed metadata is a signer claim. A timestamp section is integrity-checked as file bytes, but this viewer does **not** validate the timestamp authority signature, certificate chain or claimed time. The original viewer extracted a date-like string and labelled it trusted; that misleading claim was removed.

Browser blur, session stamps, print styles and focus hiding are deterrents, not DRM. They cannot reliably block screenshots, extraction with developer tools or camera capture. This viewer does not assert that a watermark survives screenshots or edits. Copy tracing and edit localisation require the separate Check implementation, which is not included. No Hugging Face token is needed to host this offline viewer; that does not implement the original Convert or Check services.

The added size/schema/image limits are stricter than the supplied viewer. Files outside those limits may be refused even if a different implementation accepts them. Exact server parity needs the original server and real compatibility fixtures.

## Licence, privacy and issuer setup

This implementation is released under the [MIT licence](LICENSE). Third-party dependencies retain their own licences. See [privacy and hosting details](PRIVACY.md) and [configuring your own issuer](SIGNERS.md). Browser conversions use an empty public label and generic download name. Redaction exports are blackout-only; method labels are unsigned claims.

Exit 0 means GENUINE only. Other verdicts use the non-zero groups below; inspect the JSON verdict for the precise result. Treat any non-zero code as 'not proven genuine'.

### CLI exit codes

| Exit | Verdict |
|------|---------|
| 0 | GENUINE |
| 1 | Operational error (I/O, bad key file, write refused) |
| 2 | TAMPERED (also argparse usage errors; inspect JSON) |
| 3 | NOT A GRD |
| 4 | CANNOT VERIFY, UNSUPPORTED, LIMIT EXCEEDED, UNREADABLE |
| 5 | VERIFIED WITH REDACTIONS, FULLY REDACTED, DEMO, UNVERIFIED: SELF-SIGNED, UNTRUSTED SIGNER |
| 6 | REVOKED KEY |

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

This creates a temporary QA viewer with an **ephemeral test trust anchor**, plus valid/tampered/unknown-key fixtures. Never publish that generated QA viewer. Production output retains only the original supplied public trust anchor. No private signing key is stored or shipped.

## Source map

- `src/verifier.js`: GRD1 parser, pinned trust and WebCrypto verification.
- `src/app.js`: local file lifecycle, reports, safe image decoding and viewer controls.
- `src/style.css` and `src/index.template.html`: visual system and accessible interface.
- `scripts/build.mjs`: dependency-free standalone build.
- `tests/`: generated fixtures and regression suite.
- `reference/`: unchanged supplied viewer for compatibility investigation.

Updating the trusted signer list requires a reviewed source change and rebuild. The UI cannot import keys or make an untrusted file genuine. Keep private signing keys outside this repository.

## Plain image export and reproducibility

The viewer offers **Download plain image** for verified, displayed GRD2 files, including demos and personal files. Untrusted signer images remain withheld in the viewer. The CLI can export intact GRD2 files from untrusted signers:

```sh
python3 grd.py export image.GRD --plain -o image.png
python3 grd.py export image.GRD --plain --format jpeg --quality 95 -o image.jpg
```

Plain images have no Guard proof or overlay; hidden tiles remain black. Invalid sources are refused. Keep the `.GRD` to retain verification. New seals use the backward-compatible GRD2 profile 2.1, with a signed random asset ID and a creation time claimed by the signer. Older manifests still verify.

See [REPRODUCE.md](REPRODUCE.md) for local tests and the distinction between local evidence and the external publication protocol. The [C2PA demo](examples/c2pa/run_demo.py) exercises the real SDK with ephemeral test certificates:

```sh
.venv-c2pa/bin/python examples/c2pa/run_demo.py
```

The bridge's `export` and `verify` commands are described in [REDACTION.md](REDACTION.md). A supplied test anchor establishes trust only under that test policy; mainstream C2PA trust requires an appropriately trusted certificate authority.
