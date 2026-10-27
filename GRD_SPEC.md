# Experimental GRD2 selective-redaction profile

Status: research prototype, version 2 / `tile-redaction-v1`. Not independently audited. GRD1 remains supported by the original parser; it is not silently upgraded. The original external specification and server were not supplied.

## Wire format and scope

This implementation deliberately uses **`GRD2\n` followed by canonical UTF-8 JSON**, not the proposed binary section-table extension. Existing GRD1 consumers will not understand GRD2. It also carries the signed commitment vector alongside its Merkle root, enabling precise tile diagnostics at the cost of space. These are implementation choices, not claims of compatibility with an existing GRD2 standard.

Exactly five top-level fields are allowed: `manifest`, `signature`, `image`, `tiles`, `redactions`. Canonical JSON sorts object keys, emits compact separators, preserves Unicode, and uses no insignificant whitespace. Schema keys are ASCII and numeric fields are bounded integers. Input must byte-match its canonical re-encoding; duplicates, extra fields and trailing bytes are rejected. Strings must be valid Unicode. Implementations should run the cross-language conformance tests before accepting another producer.

Limits: 32 MiB container; 4,194,304 pixels; 4,096 pixels per edge; 1,024 tiles. The canonical image is lossless, non-interlaced RGB8 PNG, with only IHDR, IDAT and IEND chunks and valid CRCs. It has no alpha or colour-profile metadata. Input alpha is composited onto white using `(colour*alpha + 255*(255-alpha) + 127) // 255`. This profile uses PNG only, not WebP. Decoded RGB pixels, not compressed PNG bytes, define image identity.

## Immutable signed manifest

Required fields:

| Field                  | Value                                         |
| ---------------------- | --------------------------------------------- |
| format / version       | `GRD2` / `2`                                  |
| width / height         | Positive integer dimensions                   |
| tileSize / pixelFormat | `64` / `RGB8`                                 |
| commitments            | Ordered array of 32-byte lowercase hex hashes |
| root                   | Merkle root, 32-byte lowercase hex            |
| publicKey              | Raw Ed25519 public key, 32-byte lowercase hex |
| keyId                  | Full SHA-256 of raw public key, lowercase hex |
| policy                 | `tile-redaction-v1`                           |
| purpose                | `asset` or `demo`                             |
| label                  | Public string, at most 120 UTF-16 code units  |

Tiles are indexed from zero, left-to-right then top-to-bottom. Right and bottom edges are cropped to actual image dimensions. Tile RGB bytes are row-major, with no padding or separators.

For each tile `i`, generate an independent cryptographically random 16-byte salt:

```
C[i] = SHA256(UTF8("GRD-TILE") || uint32_big_endian(i) || salt[i] || RGB[i])
leaf[i] = SHA256(0x00 || C[i])
parent = SHA256(0x01 || left || right)
```

Duplicate the final node at an odd level. Repeat until one root remains. Sign the following digest using Ed25519:

```
SHA256(UTF8("GUARD-GRD2-MANIFEST-V1\0") || canonical_json(manifest))
```

`signature` is standard padded base64 of the 64-byte signature. Dimensions, grid, commitment vector, purpose and label are therefore bound to the signer. A trusted public key must be pinned out of band; an embedded key is not an identity credential.

## Mutable redaction representation

`image` is padded base64 of the current RGB PNG. `tiles` contains exactly one ordered record per original tile:

- Retained: `{ "index": i, "salt": "32 lowercase hex characters" }`.
- Hidden: `{ "index": i, "commitment": "original C[i]" }`; the original salt is absent.

`redactions` is a sorted array of `{ "index": i, "method": "black" | "blur" }`. Its indices must exactly equal the hidden records. Rectangles round outward to intersecting whole tiles. No timestamp or identity of the redactor is attested.

A holder may replace tiles without the signing key. Keep the original manifest and signature byte-equivalent, discard selected salts, retain their original commitments, replace selected RGB pixels, and append the matching mask entries. Further redactions take the union of hidden tiles. Blackout is the default. Blur can leak private details; it is not guaranteed anonymisation. Labels and signer fingerprints remain public.

The verifier checks the signature, pinned identity, offline revocation policy, full commitment vector/root, exact hidden-mask agreement, and every retained pixel commitment. It reports the index of a mismatching retained tile. Hidden pixel contents are **not verified**; the viewer reconstructs them as fixed labelled placeholders, rather than presenting attacker-chosen hidden pixels as genuine. Restoring a hidden tile requires the original pixels and salt. Someone with the original can reconstruct it; this is not DRM or revocable access control.

## Verdict semantics

| Verdict                        | Meaning                                                                                        |
| ------------------------------ | ---------------------------------------------------------------------------------------------- |
| GENUINE                        | All original pixels match, signature valid, signer pinned, key not revoked in bundled snapshot |
| VERIFIED WITH REDACTIONS       | Retained pixels match; hidden regions explicitly excluded; `genuine:false`                     |
| DEMO                           | Cryptographic demonstration only; signer identity not trusted; never evidence                  |
| FULLY REDACTED                 | No visible original pixels remain; no positive image-authenticity claim                        |
| UNTRUSTED SIGNER / REVOKED KEY | No trusted positive verdict or image rendering                                                 |
| TAMPERED / INVALID             | Proof or format failed; do not render as verified                                              |

These claims do not establish truth of the scene, legal admissibility, authorship, ownership, historical creation time or signer approval of the redaction. Reports exclude image data and salts. The container itself is public and intentionally includes salts for retained tiles.

## Offline revocation

`src/trust-policy.json` is part of the trusted viewer distribution. Each revoked entry has `fingerprint` (full SHA-256 of raw public key), ISO `revokedAt`, and `reason`. Raise `version` and update `asOf` when releasing a reviewed change. Rebuild and distribute a trusted new viewer. GRD1 and GRD2 both reject listed keys. The current snapshot contains no real revocations because none were supplied.

This is a bundled denylist, not an independently signed CRL, live status service, or C2PA certificate-revocation mechanism. An offline old viewer cannot learn newer revocations. Files claiming a date before revocation are still rejected: there is no verified TSA chain to justify an exception. The file cannot override the viewer's trust policy. Replacing the viewer itself can replace its security policy.

## C2PA bridge

`c2pa_bridge.py` creates an ordinary PNG containing a real C2PA manifest using the official Content Authenticity Initiative SDK. The exporter needs its own private key and suitable certificate chain. Exporter identity and original GRD signer identity are separate.

Custom assertion `io.github.neervasa00000000.guard.grd2` contains `profile: "grd2-redaction-v1"`, `source_container_sha256`, `proof` (manifest, signature, tiles, redactions), `scope`, and `demo`. The exported PNG supplies the pixels. Standard `c2pa.actions.v2` records opening the rendered PNG as a parent ingredient and editing when redacted; it does not invent full prior history or classify an unknown image as synthetic.

Mainstream C2PA tools can recognise the exported PNG's Content Credentials. They need the custom Guard profile to interpret its regional proof. Native `.GRD` is not automatically recognised. Bridge acceptance requires **both** C2PA `Trusted` status under the inspecting tool's certificate policy and a trusted GRD regional verdict. A self-signed demo or an unknown exporter certificate is not globally trusted. No production certificate, TSA or online revocation service is bundled.

The official [C2PA specification](https://spec.c2pa.org/specifications/specifications/2.4/specs/C2PA_Specification.html) already describes assertion redaction, regions and Merkle structures. No claim is made that this is the first open format, that C2PA lacks all redaction, or that this prototype is ready for court or insurance evidence.
