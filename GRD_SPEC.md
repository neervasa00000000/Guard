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
| purpose                | `asset`, `demo` or `personal`                 |
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

A `personal` purpose marks browser-converted self-signed files. Their identity is never trusted and their verdict is UNVERIFIED: SELF-SIGNED, even if their key appears in the anchor list. They may be displayed and redacted with an explicit identity-not-verified label. Revocation still rejects them. The browser generates a non-exportable ephemeral signing key and retains no private key after conversion. Earlier experimental viewers must update to understand this signed purpose.

## Mutable redaction representation

`image` is padded base64 of the current RGB PNG. `tiles` contains exactly one ordered record per original tile:

- Retained: `{ "index": i, "salt": "32 lowercase hex characters" }`.
- Hidden: `{ "index": i, "commitment": "original C[i]" }`; the original salt is absent.

`redactions` is a sorted array of `{ "index": i, "method": "black" | "blur" }`. Its indices must exactly equal the hidden records. The method value is an **unsigned claim**, exposed as `claimedMethod` and `methodAttested:false` in reports; it is not authenticated by the original manifest. New exports permit only black and sanitize every hidden tile, including legacy blur disclosures. Rectangles round outward to intersecting whole tiles. No timestamp or identity of the redactor is attested.

A holder may replace tiles without the signing key. Keep the original manifest and signature byte-equivalent, discard selected salts, retain their original commitments, replace selected RGB pixels, and append the matching mask entries. Further redactions take the union of hidden tiles. Blackout is the only export mode. Legacy blur records remain readable for compatibility, but their replacement pixels and method claims are never verified. A re-export blackens all hidden tiles and removes their original salts. Labels and signer fingerprints remain public.

The verifier checks the signature, pinned identity, offline revocation policy, full commitment vector/root, exact hidden-mask agreement, and every retained pixel commitment. It reports the index of a mismatching retained tile. For a hidden tile claimed as `black`, every RGB byte MUST be zero; otherwise the verdict is TAMPERED with `blackout incomplete (tile i)`. Legacy `blur` replacements remain readable with a per-tile warning; their contents are **not verified**; the viewer reconstructs them as fixed labelled placeholders, rather than presenting attacker-chosen hidden pixels as genuine. Restoring a hidden tile requires the original pixels and salt. Someone with the original can reconstruct it; this is not DRM or revocable access control.

## Verdict semantics

| Verdict                        | Meaning                                                                                        |
| ------------------------------ | ---------------------------------------------------------------------------------------------- |
| GENUINE                        | All original pixels match, signature valid, signer pinned, key not revoked in bundled snapshot |
| VERIFIED WITH REDACTIONS       | Retained pixels match; hidden regions explicitly excluded; `genuine:false`                     |
| UNVERIFIED: SELF-SIGNED        | Personal conversion; pixel consistency only; identity not verified; `genuine:false`            |
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

## Cross-language acceptance profile

GRD1 metadata now permits finite safe integers only (no fractional numbers), valid Unicode strings/keys, and depth at most 32. Canonical object keys use UTF-16 code-unit order in both languages. Python validates bounded PNG inflated scanline lengths and rejects unused/trailing compressed data, matching the JS profile. UTC policy dates use exact second-resolution ISO syntax with valid calendar dates. These restrictions intentionally reject some previously accepted legacy inputs rather than claiming universal number/decoder equivalence. Regression vectors include Unicode key ordering, fractional/unsafe numbers, boolean dimensions, lone surrogates, invalid dates and extra PNG scanlines.

## Conformance vectors

A conforming implementation MUST produce expected_verdict for every vector in conformance/vectors.json.

## GRD2 profile 2.1

New seals keep `version: 2` and add exactly three signed manifest fields: `profile: "2.1"`, `assetId` (canonical base64 of 16 independently random bytes), and `created` (UTC `YYYY-MM-DDTHH:MM:SSZ`). All fields participate in the existing sorted-key canonical JSON and signature digest. `created` is a time claimed by the signer, not a trusted timestamp. Verification reports and the C2PA custom assertion preserve this asset identity. Tile commitments and their index binding are unchanged.

Legacy manifests with none of these fields remain valid and produce `legacy manifest: no asset ID`. Partial sets and malformed IDs/timestamps are rejected. The viewer falls back to the root as a legacy identifier.

The signature covers the full commitment vector, which supplies the security binding. Security arguments MUST NOT depend on the Merkle root as an additional guarantee. The root remains a compact identifier and a consistency check (`root == MT(commitments)`), reserved for a possible future root-only inclusion-proof profile. There is no root-only wire change in profile 2.1.

The CLI verdict groups are 0 (GENUINE), 2 (TAMPERED), 3 (NOT A GRD), 4 (CANNOT VERIFY / UNSUPPORTED / LIMIT EXCEEDED / UNREADABLE), 5 (valid but not whole-image genuine) and 6 (REVOKED KEY). A verifier fault includes `verifierFault: true`; damaged proof encodings are TAMPERED. Legacy GRD1 verification remains supported with its existing 64 MiB limit; GRD2 uses 32 MiB, 4096 pixels per side, 4,194,304 pixels and 1024 tiles.

## New profile registry (upgrade checkout)

Legacy manifests and GRD1 remain readable. New explicit profile/field combinations are strict; partial sets and unknown fields are rejected. Every field below is signed using the existing canonical JSON rules.

| Container | Profile | Additional signed fields |
|---|---|---|
| GRD2 | 2.1 | assetId, created (existing) |
| GRD2 | 2.2 | assetId, created, subTile |
| GRD2 | 2.3 | assetId, created, visual |
| GRD2 | 2.4 | assetId, created, subTile, visual |
| GRD3 | 3.0 | assetId, created |
| GRD3 | 3.1 | assetId, created, subTile |
| GRD3 | 3.2 | assetId, created, visual |
| GRD3 | 3.3 | assetId, created, subTile, visual |

GRD2 retains `format:"GRD2", version:2` and its 32 MiB / 4,194,304-pixel / 4096-edge / 1024-parent bounds. GRD3 has `format:"GRD3", version:3`, a 256 MiB container bound, 36,000,000 pixels, 8192-edge and 9000-parent bounds. Parent tileSize remains 64. A missing `subTile` means the original single-level commitment construction; a present value is exactly 8, 16 or 32.

## GRD3 binary envelope

All integers are unsigned, big-endian. The container ends exactly after its PNG; no padding or trailing bytes are permitted.

```
"GRD3\n"                            5 bytes
manifest_length                     u32, at most 2 MiB
manifest                            canonical UTF-8 JSON, manifest_length bytes
signature                           64 bytes
parent_record_count                 u32; equals signed grid size
parent_records                      as below
png_length                          u64; bounded by container limit
png                                 raw canonical RGB8 PNG, png_length bytes
```

Signature message: `SHA256("GUARD-GRD3-MANIFEST-V1\0" || canonical_manifest_bytes)`, signed with Ed25519. This domain is distinct from GRD2. Base64 is not used for the binary PNG or records. The internal authoring document still has `manifest/signature/image/tiles/redactions`; `decodeGRD3` / `decode3` derive its ordered redactions from record kinds.

For profiles 3.0/3.2, each parent record is kind 0 plus a 16-byte pixel salt, kind 1 plus the original 32-byte parent commitment (black), or kind 2 plus that commitment (legacy blur, warning/read-only). Parent indices are implicit and ordered.

For profiles 3.1/3.3:

- kind 0: 16-byte parent seed;
- kind 1: original 32-byte parent commitment, entire parent black;
- kind 3: u16 sub-record count, then that many ordered child records: kind 0 plus a 16-byte child salt, or kind 1 plus its 32-byte child commitment. Child j is implicit and row-major. Count must equal the signed grid's truncated child count. Both hidden and retained children must exist; fully hidden parents use kind 1 and intact parents kind 0.

Kind 2 is not permitted for fine-grid profiles. Kind 3 is not permitted without a signed subTile. This is the explicit binary extension for U2, whose source plan did not specify a partial-parent binary layout.

The PNG contains only IHDR, consecutive IDAT chunks, and IEND with correct CRCs, RGB8, no interlace and signed dimensions. All five PNG filters are supported. Exact GRD3 verification reconstructs 64-row bands and PNG filter state. Python uses its native Pillow decoder on two-row windows for nonzero filters, preserving bounded memory. Container/compressed-image storage and display/seal/redaction/export buffers are additional to this bound. The browser's large parent-only verifier hashes per-band tile messages through at most eight local blob workers (bounded by hardware concurrency); no external worker URL is fetched.

## Fine commitments and records

For each 64 px parent i, let g=subTile and j enumerate truncated g×g children within that parent. Generate a fresh 16-byte seed k_i:

```
s_ij = HMAC-SHA256(k_i, "GRD-SUB" || u16be(j))[0:16]
c_ij = SHA256("GRD-SUBTILE" || u32be(i) || u16be(j) || s_ij || RGB_ij)
c_i  = SHA256("GRD-TILE2" || u32be(i) || c_i0 || ... || c_i(n_i-1))
```

The signed commitment vector keeps one c_i per parent. The new subTile field/profile adds a small amount of signed metadata; adding the visual layer adds its own vector. No claim of exactly unchanged signed byte size is made.

GRD2 JSON records are exactly one of `{index,seed}`, `{index,commitment}`, or `{index,sub:[{j,salt}|{j,commitment},...]}`. Seeds/salts use 32 lowercase hex characters; commitments use 64. An intact parent discloses its seed. A partial parent MUST NOT contain its seed, must include every ordered child exactly once and must contain both retained and hidden children. Every hidden child/parent must be black. Aggregated child commitments must match the signed c_i. A retained mismatch identifies the parent/sub-proof; without expected retained child hashes in the wire format, an exact changed-child index cannot always be inferred.

Rectangle export rounds outward to granularity 8/16/32/64, never finer than the signed subTile (or 64 for legacy files). It drops newly hidden salts, preserves previous hidden openings, coalesces wholly hidden parents, and preserves the original manifest and signature. Repeating a redaction, including a wholly hidden parent, is semantically idempotent. Pixel-equivalent encodings need not have identical compressed chunk boundaries.

Reports include precise hidden child rectangles, subTile, subTilesTotal and subTilesVisible. Whole-parent retained counts remain separate. A partly hidden one-parent image is VERIFIED WITH REDACTIONS, not FULLY REDACTED, when any original child remains.

## Signed visual layer and GRDP sidecar

`manifest.visual` is exactly `{version:"y8c16-v1", tau:9, commitments:[e_0,...]}`. For each parent, compute 96 unsigned bytes: 64 Y means on an 8×8 cell grid followed by 16 Cb means and 16 Cr means on 16×16 cells. For RGB bytes:

```
Y  = floor((299R + 587G + 114B + 500)/1000)
Cb = clamp(floor((128000000 - 168736R - 331264G + 500000B + 500000)/1000000))
Cr = clamp(floor((128000000 + 500000R - 418688G - 81312B + 500000)/1000000))
```

Clamp to 0..255. Cell mean is `floor((sum + floor(count/2))/count)`. Edge cells average existing pixels only. Empty cells outside a truncated parent are encoded as Y=0, Cb=Cr=128. A visual nonce is `HMAC-SHA256(parent_salt_or_seed,"GRD-VIS")[0:16]`; this domain is distinct from child salt derivation.

`e_i = SHA256("GRD-VIS" || u32be(i) || visual_nonce_i || feature_i)`.

Sidecar: `"GRDP\n" + canon({manifest, signature, vis})`, at most 16 MiB. Each ordered vis record is either `{index,salt,feature}` (salt=canonical base64 of 16 bytes, feature=canonical base64 of 96 bytes), or `{index,commitment}` for a wholly hidden parent. No pixels or exact-layer pixel salts are included. Export reverifies the source first. Partial parents are explicitly refused: disclosing their original whole-parent averages could leak hidden content. Exact fine redaction and plain export are unaffected.

Visual verification checks canonical framing, the original manifest signature/domain, root, visual openings and local trust/revocation. Candidate PNG/JPEG/WebP dimensions are checked before full decode, bounded to 8192-edge/36M pixels and 256 MiB. Aspect-ratio changes above 1% give VISUALLY INCONSISTENT; otherwise native-size RGB is mapped directly to signed cells by the integer area-average method below. No library resize is used in candidate verification. Decoder/colour-management differences require empirical cross-checking and are not assumed bit-identical.

For disclosed parents, compare all 96 absolute differences. For hidden parents, compare all nonempty Y values against zero. The worst error determines VISUALLY CONSISTENT (<7), BORDERLINE (decoder-dependent) (7..11), or VISUALLY INCONSISTENT (>11), with signed tau still 9. `genuine` is always false. `verdict` preserves untrusted/demo/self-signed status on a matching copy; only a trusted asset key receives VISUALLY CONSISTENT as its primary verdict. Visual inconsistency exits 2; consistency and valid-but-untrusted statuses exit 5; borderline exits 7. A wholly hidden sidecar makes no visible-content claim.

A matching result authenticates only the disclosed block averages under the stated signer key. It does not authenticate fine detail, source capture or an untrusted identity. Mean-preserving edits can pass exactly, and some blurs pass. JPEG quality ranges and detection percentages are measured outcomes, not wire-format guarantees. See SECURITY_MODEL.md and UPGRADE_RESULTS.md.

### Native candidate area mapping and BORDERLINE (28 October 2026)

Copy checking decodes the candidate to native-size RGB, compositing transparency on white, without resizing. For a signed W×H image and native cw×ch candidate, a signed cell `[x0,x1) × [y0,y1)` (8×8 luma or 16×16 chroma, clipped to the signed image edge) maps to `[x0*cw/W,x1*cw/W) × [y0*ch/H,y1*ch/H)`. Use integer units: L=x0*cw, R=x1*cw, T=y0*ch, B=y1*ch. Candidate pixel (u,v) has weight

`wx=max(0,min(R,(u+1)*W)-max(L,u*W))`, `wy=max(0,min(B,(v+1)*H)-max(T,v*H))`, `weight=wx*wy`.

First convert each candidate pixel to integer Y/Cb/Cr with the existing y8c16-v1 formulas. Then sum `weight*component` and return `floor((sum+floor(A/2))/A)`, where A=(R-L)*(B-T). Empty outside-image cells remain Y=0, Cb/Cr=128. Python uses arbitrary-precision integers; JS Number integer sums are exact: A≤256*cw*ch≤9,216,000,000 and sum≤255*A≤2,350,080,000,000 (<2^42). All products and rounded divisions therefore stay within exact integer bounds; no floating-point geometric overlap is used.

At identical dimensions this is exactly the original feature function. The signed commitment format and `y8c16-v1` version remain unchanged; candidate normalization semantics change for differently sized copies. Same-size vectors and hand-calculated overlap/rounding vectors check compatibility. The aspect-ratio and native decoding limits still apply.

Tau stays 9. For worstError e, e<7 gives VISUALLY CONSISTENT, 7≤e≤11 gives **BORDERLINE (decoder-dependent)**, and e>11 gives VISUALLY INCONSISTENT. BORDERLINE has `genuine=false`, `visualConsistent=false`, CLI exit 7 and warning “Close to the threshold; result may differ between apps”. Signer trust remains a separate field; borderline grants no identity or consistency acceptance. The browser shows the warning in amber with explicit text. A fully hidden proof makes no positive visible-content claim. Exact GRD verification is unchanged.

All implementations now share the integer area mapping; remaining cross-runtime visual differences can arise in native image decoders/colour or alpha conversion. The borderline band reduces unstable near-threshold decisions but does not mathematically guarantee identical verdicts for every encoded image.

## V4 report and exit semantics (local update, 29 October 2026)

No tile commitment, manifest digest domain, tau or visual-feature format changed. BORDERLINE now has a distinct exit code, so exit-code-only consumers cannot confuse it with consistency. Exit 0 alone means GENUINE. Operational failures may return 1; argparse usage failures may return 2.

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

Exact reports add `signerStatus` (`trusted`, `unknown`, `revoked`, `self`, `demo`, `none`), `signerDisplayName` (configured name or null) and `fingerprint` (SHA-256 of the parsed public key, otherwise null). Names come from the configured public registry or a manually imported root-signed bundle, not from a claim in the image. A self-signed/personal purpose cannot become a trusted asset by pinning its key. A revoked key remains revoked even if explicitly pinned.

Unknown signatures grant no genuineness or automatic viewability. The viewer can show an explicit user-requested, stamped preview after valid file checks; this does not change verdict, key trust or the proof. Default GRD1 API results still withhold image payload; an explicit display option is used only after the button is pressed. Malformed unknown files are not eligible for display. CLI `verify --quiet` suppresses the human signer line; stdout remains JSON.

The public registry at `.well-known/guard-signers.json` must match `src/trusted-keys.json`; build failure prevents publishing inconsistent registries. Offline viewers do not fetch it. Session-only bundle import requires a separately verified Ed25519 public root, preserves in-session rollback state, rechecks expiry, resets the displayed file on trust changes, and cannot undo bundled revocations. No browser persistent storage or network permission was added.
