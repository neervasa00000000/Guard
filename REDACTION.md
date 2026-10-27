# Redaction and interoperability guide

## Browser

Open the [inspector](https://neervasa00000000.github.io/Guard/), then choose **Try redaction with an example**. Drag a rectangle, select tiles, or enter rectangle coordinates. Export a redacted `.GRD`; it reopens automatically. Rectangles round outward to 64px tile boundaries. Blackout is recommended; blur can leave private information visible. Further redactions work on exported copies.

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

Blackout removes selected original pixels and salts from the exported container. Blur can leak private details. Labels, dimensions, fingerprints and commitments remain public. Someone retaining the original can still see it: this is not DRM. Reports omit image data and salts, but include public metadata.

The supplied original server and Goose Bumps fixture are absent. Python/JavaScript conformance tests cover the new GRD2 profile and generated legacy fixtures; universal legacy JSON floating-point canonicalisation parity is not claimed. The [format specification](GRD_SPEC.md) documents the deliberate JSON wire-format difference from the requested binary proposal. No novelty or production-security claim replaces an independent review.
