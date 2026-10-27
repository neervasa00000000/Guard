# Guard exact and visual profiles: security model

This is a written model and reduction argument for review, not a machine-checked proof or a claim that testing establishes absence of bugs. It covers the implemented exact profiles and describes the visual check's limited deterministic statement. It does not establish novelty or performance relative to other systems.

## Assets, parties and trust

An issuer holds an Ed25519 signing key. A verifier receives an independently authenticated trust/revocation policy. An arbitrary holder may remove selected image regions without the issuer's key. A verifier can attribute the manifest only to a trusted key; it cannot infer camera capture, scene truth, consent, ownership, or trusted time from a valid signature. `created` is asserted by the signer. Browser-generated keys remain self-signed.

Let H be SHA-256, C be sorted-key canonical JSON, and i a four-byte big-endian parent-tile index. An exact manifest binds dimensions, RGB8 format, 64 px parent grid, the complete ordered commitment vector, root, public key, purpose, policy, profile and public metadata. GRD3 uses a different signature domain from GRD2. All field lengths and numeric encodings are validated before accepting an opening.

The adversary may obtain seals of chosen images, see retained pixels and published metadata, redact regions, re-encode PNGs losslessly, and choose arbitrary candidate containers. It cannot obtain the trusted issuer's key. Its local verifier and trust policy are honest. Issuer compromise, maliciously staged scenes, malicious trusted issuers, browser compromise and side channels are outside this model.

## Exact commitment definitions

For the legacy 64 px construction, tile i contains row-major RGB bytes X_i and fresh 128-bit salt s_i:

`c_i = H("GRD-TILE" || u32be(i) || s_i || X_i)`.

For a fine-grid tile, g is the signed sub-tile edge (8, 16 or 32). The issuer generates an independent 128-bit seed k_i. Sub-tile indices j are row-major within the truncated parent tile:

```
s_ij = HMAC-SHA256(k_i, "GRD-SUB" || u16be(j))[0:16]
c_ij = H("GRD-SUBTILE" || u32be(i) || u16be(j) || s_ij || X_ij)
c_i  = H("GRD-TILE2" || u32be(i) || c_i0 || ... || c_i(n_i-1))
```

An intact parent discloses its seed. Once any sub-tile is hidden, the parent seed is removed. Retained sub-tiles disclose only their individual derived salts; hidden ones disclose only commitments. Completely hidden parents disclose only c_i. No export restores a removed salt. Hidden blackout pixels must be zero, regardless of whether the viewer could cover them.

The Merkle root is a consistency check and compact identifier. The full ordered vector is already signed. None of the security arguments below requires the root as an additional binding assumption.

## Exact unforgeability game (UF-RED)

The challenger generates a trusted issuer key. The adversary requests seals of images and receives the resulting containers. It wins by producing an accepted exact proof under that key for which either:

1. the signed canonical manifest was never authorized by the signing oracle, or
2. at least one disclosed original pixel region differs from that region in the image of every oracle response carrying that manifest.

Authorized redaction and lossless PNG re-encoding are explicitly not winning changes. Changing bytes is not, by itself, a forgery: GRD binds exact decoded pixels and openings, while legitimate disclosure changes are allowed.

**Reduction argument.** In case 1, a new signature on a previously unsigned manifest digest is an Ed25519 EUF-CMA forgery. If two distinct accepted manifests share the same signed digest, their distinct domain-prefixed canonical encodings yield a SHA-256 collision. Strict canonical parsing prevents duplicate-key/whitespace ambiguities from producing distinct accepted representations of the same signing message.

In case 2, fix an authorized manifest. In the legacy construction, accepting different disclosed RGB bytes and/or salt under the same c_i gives distinct inputs with the same hash output. For fine tiles, if the ordered child-commitment vector differs, equality to the signed parent c_i yields a parent-hash collision. Otherwise a changed disclosed child's bytes/opening with the same c_ij yields a child-hash collision. The index/domain encodings prevent substituting another tile or sub-tile without entering one of these collision cases. Coalescing completely hidden children into their original c_i reveals no new original content and is authorized.

A detailed tightness calculation would count the relevant hash queries and selected tile/sub-tile reductions. The qualitative bound consists of an Ed25519 forgery term and SHA-256 collision terms. No trusted timestamp or capture-provenance result follows.

## Hiding game (IND-HIDE), with explicit leakage

The adversary chooses two equal-dimension images that agree on every finally disclosed region. The challenger seals one selected by a hidden bit, redacts the differing regions and reveals the final redacted container. It does not reveal the unredacted challenge seal or any earlier challenge copy containing those pixels/openings.

Leakage includes dimensions, grid/profile, the visible redaction mask, count and shape of disclosures, purpose/policy, signer key, public label, signer-claimed time, asset ID, commitment vector, signature and the optional signed visual commitments (to block means). Disclosed visual features/openings are also public leakage when a visual proof is released. Copies of one seal remain linkable. Black regions reveal their positions through their pixels; this design does not claim position hiding.

**Reduction argument.** In the random-oracle model, an unknown 128-bit legacy salt protects a hidden opening against direct guessing: q guesses hit one such salt with probability at most q/2^128. For fine-grid parents, replace derived HMAC outputs with independent random values in a PRF hybrid. The seed is absent whenever any child is hidden, and the revealed sibling outputs use different, unambiguous j inputs. The adversary gains only its PRF distinguishing advantage in the replacement. Hidden child salts are then unknown random 128-bit values and the same query-guessing argument applies, with a union bound over hidden openings.

The visual nonce uses a distinct HMAC input `"GRD-VIS"` under the disclosed parent salt/seed. A wholly hidden parent's nonce is not disclosed. Fine partial parents deliberately cannot export a whole-tile visual opening: its original 8 px/16 px averages could reveal facts about hidden pixels. This restriction is part of the implemented privacy boundary, not an optimization to bypass.

This argument assumes independent cryptographic randomness at sealing and secure erasure from the exported artifact, not erasure from the issuer's machine. Anyone retaining an original or earlier copy can still read it.

## Visual-consistency lemma

The visual layer signs commitments to a deterministic 96-byte feature per parent tile: 64 rounded integer brightness means over 8×8 cells, then 16 Cb and 16 Cr means over 16×16 cells. The integer coefficients and edge-cell convention are specified in GRD_SPEC.md. A retained visual opening contains its feature and 128-bit nonce; a hidden parent contains only its signed commitment.

Assume signature and hash binding as above. If `visualConsistent` is true, then, after this verifier's documented decoding/normalization:

- every disclosed feature component differs from its authenticated reference by at most tau=9; and
- every nonempty 8×8 brightness cell in a hidden parent has mean at most 9.

This follows directly from opening each authenticated visual commitment and checking the maximum component difference. The trust verdict remains separate. An untrusted/self-signed key does not become a trusted identity because features match, and `genuine` is always false on this path.

The lemma says nothing about differences preserving those means. Swapping pixels inside common 8×8 brightness/16×16 colour cells can preserve the feature exactly. Smooth blurs and other edits may pass. No lower bound on edit detection, and no guarantee for all JPEG qualities/resizes, follows from the lemma. Such rates require a specified, held-out empirical evaluation.

The verifiers now share one exact integer area-average mapping from native candidate RGB to the signed cell grid. No verifier-side library resampler remains. Remaining cross-runtime differences arise from image decoding, including colour/alpha conversion. Raw-RGB feature vectors isolate the shared arithmetic. BORDERLINE at tau±2 makes no positive consistency claim and warns about decoder dependence; it does not prove agreement for every encoded input.

## Verdict and resource semantics

- Exact acceptance requires a valid signature, supported/bounded profile, valid disclosures, pixel commitments and blackout checks. Trust/purpose determines the final exact verdict.
- Input/proof failures are TAMPERED; explicitly exceeded bounds are LIMIT EXCEEDED; unsupported capabilities/profiles are not accepted. Local verifier/policy faults are CANNOT VERIFY, never genuine evidence.
- GRD3 verification processes RGB in 64-row bands plus PNG filter state and per-band tile messages. The input container/compressed PNG and the small signed commitment vector are still resident. Displaying, sealing, redacting or exporting an image necessarily uses additional image buffers; the bounded-band statement is about exact verification, not total browser/GPU memory.
- The standalone viewer still uses its static trust snapshot. Opt-in root-signed bundle tooling now checks expiry, sequence and same-sequence equivocation, with an atomic, locked CLI cache; see TRUST_BUNDLES.md for its local-clock/state assumptions. Production root provisioning, standalone import/refresh UX, RFC 3161 time, hardware-key registration and production C2PA certificate trust remain pending.

## Evidence boundaries

Unit/property-style tests, differential mutations, native browser exercises and the real C2PA SDK round trips are recorded separately from these arguments. A proof review, formal-tool model, external 50,002/one-million-case run, 24-hour fuzz runs, mobile trials and the reported Kodak/DIV2K measurements must not be asserted without their actual artifacts and results.
