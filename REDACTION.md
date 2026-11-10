# Redaction and interoperability guide

## Browser

Open TileSeal and choose **Seal a picture**. Select a PNG, JPG, WebP, GIF or BMP, draw blackout boxes or enter their coordinates, review the preview and download a .GRD. New browser seals use 16 px sub-tiles and a one-time key with self-signed identity. GRD2 or GRD3 is selected by the existing format limits.

Choose **Check a file** to inspect a .GRD and **Black out more areas** on a viewable GRD2 or GRD3. Existing hidden regions display as solid black, including regions from old blur files. The original signature is carried forward. The plain PNG export drops the proof. The editor and browser test plan are documented in [TILESEAL.md](TILESEAL.md).

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

Repeat `--rect` for multiple regions. Add `--pad-boxes --line-height 32` to use the TileSeal padding rule. Use `--granularity 16` on a compatible seal to match the browser default. Redaction requires no signing key. Existing output files are never overwritten. `--trusted-key` is an explicit local trust decision. To support a new real issuer in the web viewer, review its identity and update the source anchors, then rebuild. Never commit private keys. A Node PNG issuer is also available in `scripts/issue-grd2.mjs`; install its dependency with `npm ci`.

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

`grd.py verify` returns exit 0 only for GENUINE. Other verdicts use [grouped non-zero exit codes](#cli-exit-codes), including exit 5 for VERIFIED WITH REDACTIONS, DEMO and UNVERIFIED: SELF-SIGNED. Read the JSON for regional-proof details; never treat these as whole-image acceptance. See [issuer setup](SIGNERS.md) and [privacy notes](PRIVACY.md).

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

## CLI exit codes

Read the JSON verdict for the precise result.

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
