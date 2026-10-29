# GRD1 layout implemented by this viewer

Derived from the supplied offline viewer, not an independently supplied server specification.

All integer fields are little-endian. The header is 10 bytes: ASCII `GRD1`, uint16 version (1), uint16 flags, uint16 section count. Each section table entry is 50 bytes: uint16 type, uint64 absolute offset, uint64 length, 32-byte SHA-256 digest.

Sections must be unique, contiguous immediately after the table and cover the entire file. Required types: 1 metadata, 2 image, 6 public key, 7 signature. Optional: 3 thumbnail, 4 recovery, 5 timestamp. Flag bit 0 indicates timestamp; bit 1 recovery. Other bits are rejected. Signature must be last, exactly 64 bytes, with a zero digest in its table entry.

Each non-signature section digest must match. The public-key section is 40 bytes: 8-byte key ID plus 32-byte raw Ed25519 public key. The key ID is the first 8 bytes of SHA-256(public key); the viewer also compares the **full public key** with its pinned anchor. The key ID alone is not a trust decision.

The Ed25519 signature verifies against **SHA-256 of all bytes before the signature payload**, not directly against the raw file prefix. This preserves the supplied viewer's convention. The signed prefix includes the header, complete table, section hashes and all non-signature payloads.

Metadata must be UTF-8 JSON. Canonicalisation follows the supplied JavaScript viewer: sorted object keys, compact JSON, arrays in original order. `asset_id` must equal the first 15 hex characters of SHA-256(image section); `key_id` must match the key section. Full signed hashes still bind all image bytes. The short asset ID is not a replacement for a full collision-resistant file fingerprint.

This hardened viewer additionally requires bounded metadata (256 KiB, nesting at most 32, finite numeric values within the safely represented range), bounded total input (64 MiB), and a supported bounded image. It validates encoded and decoded image dimensions in the UI before showing GENUINE.

A future format should define canonicalisation cross-language test vectors, full-length asset identifiers, explicit algorithm/version negotiation, trust-key rotation and independently verifiable timestamp policy. These require coordinated signer/server changes and are not silently retrofitted into GRD1.

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
