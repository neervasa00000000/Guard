# Redaction and interoperability guide

## Convert an image in the browser

Use **Make a .GRD** at the top of the inspector. Choose PNG, JPG, WebP, GIF or BMP, review the preview, then choose **Convert & download .GRD**. It downloads a real GRD2 container and opens it below for verification and further redaction. All processing stays on your device.

In this upgrade checkout, input limits are 256 MiB, 50 megapixels and 16,384 pixels per edge. “Fit large photos” is enabled by default and fits the output within 36,000,000 pixels, 8,192 pixels per edge and 9,000 parent tiles, preserving aspect ratio. The preview shows original and output dimensions before conversion; smaller photos are not enlarged. Turn it off to require original-size conversion. Unsupported formats (including HEIC, AVIF, PDF and SVG) need a PNG/JPG export first. Encoded dimensions are inspected before decoding. Animated images use their first frame; transparency becomes white. Original EXIF/other metadata is not copied; new conversions omit the filename from their public label and download as `image.GRD`. The resized pixels become the signed original of the new GRD; the higher-resolution source file is not embedded or changed.

Each conversion creates an ephemeral Ed25519 key; its private half is never exported or retained by the application. The signed purpose is `personal`, and both verifiers return **UNVERIFIED: SELF-SIGNED**, never genuine or identity-trusted, even if the public key were separately pinned. Reopening and redaction preserve that status. This is a consistency proof since conversion, not proof of the scene's truth or the creator's identity. Revocation checks still apply. Earlier experimental GRD2 viewers need updating to recognise this purpose. The C2PA bridge does not promote personal files to trusted evidence.

## Browser

Open the [inspector](https://neervasa00000000.github.io/Guard/), then choose **Try redaction with an example**. Drag a rectangle, select tiles, or enter rectangle coordinates. Export a redacted `.GRD`; it reopens automatically. Rectangles round outward to the selected sealed grid (new browser files default to 16 px; legacy files remain 64 px). Blackout is the only export mode. Older blur containers can still be inspected, but hidden contents are not verified; re-exporting replaces all hidden pixels with black. Further redactions work on exported copies.

Demo keys are ephemeral and never pinned. The example always says **DEMO**, even when its proof is mathematically valid. The shipped viewer cannot import an arbitrary key and promote it to genuine. The original production public anchor is unchanged.

## Python issuer, redactor and verifier

Use Python 3.13 and keep your Ed25519 private key outside the repository:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python grd.py seal image.png --key /secure/signer.pem -o image.GRD --label "Public label"
.venv/bin/python grd.py verify image.GRD --trusted-key /secure/signer-public.pem
.venv/bin/python grd.py redact image.GRD --rect 20,30,80,60 --mode black -o private.GRD
.venv/bin/python grd.py verify private.GRD --trusted-key /secure/signer-public.pem
```

Repeat `--rect` for multiple regions. Redaction requires no signing key. Existing output files are never overwritten. `--trusted-key` is an explicit local trust decision. To support a new real issuer in the web viewer, review its identity and update the source anchors, then rebuild. Never commit private keys. A Node PNG issuer is also available in `scripts/issue-grd2.mjs`; install its dependency with `npm ci`.

## C2PA PNG export

```sh
.venv/bin/python -m pip install -r requirements-c2pa.txt
.venv/bin/python c2pa_bridge.py export private.GRD -o credential.png --key /secure/exporter.key --cert /secure/exporter-chain.pem --trusted-grd-key /secure/signer-public.pem
.venv/bin/python c2pa_bridge.py verify credential.png --trusted-grd-key /secure/signer-public.pem --trust-anchor /secure/ca.pem
.venv/bin/python tests/c2pa_roundtrip.py
```

This uses the official [CAI Python SDK](https://github.com/contentauth/c2pa-python). Provide a suitable ES256 or Ed25519 exporter key and certificate chain. The exporter certificate and original GRD signer are distinct identities. No production credentials are bundled. A test certificate is not automatically trusted by mainstream tools. `--allow-demo` permits a labelled demo export, never trusted evidence.

Bridge acceptance requires **both** C2PA `Trusted` status under the inspector's certificate policy and a trusted GRD regional verdict. The custom assertion carries the original signed manifest and tile disclosures. C2PA binds the entire exported PNG, including hidden-region replacement pixels; GRD binds only the retained original pixels. Standard tools recognise PNG Content Credentials, but need this custom profile to interpret the GRD proof. Native `.GRD` files do not become C2PA-compatible automatically. No verified TSA or online certificate-revocation service is added.

The optional integration test creates a temporary CA and explicitly trusts it, exports through the real SDK, reads the manifest back, checks both proofs, then modifies a redacted-area pixel and confirms C2PA rejects the changed asset. This is not evidence of admission to a global trust list.

## Offline key rejection

Review additions to `src/trust-policy.json` using the full SHA-256 fingerprint of the raw Ed25519 public key, an ISO `revokedAt`, and a reason. Increment `version`, update `asOf`, rebuild, and distribute a trusted viewer. The current list is empty because no actual compromised keys were supplied. Tests use temporary revoked keys.

The policy is a bundled snapshot, not an independently signed update feed or live CRL. An offline older viewer cannot know later revocations. A file cannot override viewer policy. All listed keys are rejected regardless of claimed date; no timestamp exception is justified without verified TSA evidence.

## Scope and limitations

`GENUINE` means all original pixels match a pinned signer's proof. `VERIFIED WITH REDACTIONS` means retained pixels match; `genuine:false` remains explicit. Hidden pixels render as fixed labelled placeholders, and a fully hidden file receives no positive image claim. Neither signature attests approval by the redactor, scene truth, authorship, ownership, historical time or legal admissibility.

Blackout removes selected original pixels and salts from the exported container. Conforming exporters MUST write 0,0,0 into hidden tiles, and verifiers MUST reject non-zero pixels in tiles claimed as black with TAMPERED. Blur can leak private details. Labels, dimensions, fingerprints and commitments remain public. Someone retaining the original can still see it: this is not DRM. Reports omit image data and salts, but include public metadata.

Hiding parts of an image can change what the rest appears to show. VERIFIED WITH REDACTIONS proves only that the visible tiles are unchanged, not that the redacted image is a fair representation.

The supplied original server and Goose Bumps fixture are absent. Python/JavaScript conformance tests cover the new GRD2 profile and generated legacy fixtures; both checkers now reject fractional/unsafe legacy metadata numbers and sort Unicode keys using UTF-16 order. This stricter interoperability profile can reject legacy files accepted before; conformance tests are not a guarantee of universal decoder parity. The [format specification](GRD_SPEC.md) documents the deliberate JSON wire-format difference from the requested binary proposal. No novelty or production-security claim replaces an independent review.

## Strict command-line acceptance

`grd.py verify` returns exit 0 only for GENUINE. Other verdicts use grouped non-zero exit codes (table in README), including exit 5 for VERIFIED WITH REDACTIONS, DEMO and UNVERIFIED: SELF-SIGNED. Read the JSON for regional-proof details; never treat these as whole-image acceptance. See [issuer setup](SIGNERS.md) and [privacy notes](PRIVACY.md).

## Plain download

Sealing never restricts use. **Download plain image** saves an ordinary PNG containing only IHDR, IDAT and IEND chunks, with no Guard metadata or viewing overlay. It preserves retained pixels and blackens every hidden tile defensively. It cannot restore removed content. The plain copy can no longer be verified as genuine; keep the `.GRD` if you need proof.

The viewer withholds images and this button for UNTRUSTED SIGNER. The CLI permits export of intact self-signed and untrusted GRD2 files, but refuses broken proofs, revoked keys and verifier faults. `--plain` is mandatory:

```sh
python3 grd.py export source.GRD --plain -o copy.png
python3 grd.py export source.GRD --plain --format jpeg --quality 95 -o copy.jpg
```

## Fine redaction and visual-copy checks

The signed sub-tile size fixes the smallest permitted grid. You may choose a coarser grid at export. A partly hidden parent drops its seed and discloses salts only for retained children. Further redactions preserve the union. Dense grids use rectangle coordinates and drag selection to avoid creating hundreds of thousands of focusable buttons.

Visual proofs check 8×8 brightness and 16×16 colour averages with tolerance 9. They do not verify finer detail or turn self-signed/untrusted files into trusted identities. JPEG/resize acceptance is empirical, not guaranteed for every image. Mean-preserving edits and some blurs may pass.

A visual sidecar omits features and nonces for wholly hidden parents. A partial parent cannot export its original aggregate feature without potentially leaking hidden information, so this combined export is deliberately refused. Use whole 64 px blackouts when visual-copy checking is needed. Plain exports retain only the actually hidden sub-tiles as black.
