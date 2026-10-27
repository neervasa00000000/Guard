# GRD1 layout implemented by this viewer

Derived from the supplied offline viewer, not an independently supplied server specification.

All integer fields are little-endian. The header is 10 bytes: ASCII `GRD1`, uint16 version (1), uint16 flags, uint16 section count. Each section table entry is 50 bytes: uint16 type, uint64 absolute offset, uint64 length, 32-byte SHA-256 digest.

Sections must be unique, contiguous immediately after the table and cover the entire file. Required types: 1 metadata, 2 image, 6 public key, 7 signature. Optional: 3 thumbnail, 4 recovery, 5 timestamp. Flag bit 0 indicates timestamp; bit 1 recovery. Other bits are rejected. Signature must be last, exactly 64 bytes, with a zero digest in its table entry.

Each non-signature section digest must match. The public-key section is 40 bytes: 8-byte key ID plus 32-byte raw Ed25519 public key. The key ID is the first 8 bytes of SHA-256(public key); the viewer also compares the **full public key** with its pinned anchor. The key ID alone is not a trust decision.

The Ed25519 signature verifies against **SHA-256 of all bytes before the signature payload**, not directly against the raw file prefix. This preserves the supplied viewer's convention. The signed prefix includes the header, complete table, section hashes and all non-signature payloads.

Metadata must be UTF-8 JSON. Canonicalisation follows the supplied JavaScript viewer: sorted object keys, compact JSON, arrays in original order. `asset_id` must equal the first 15 hex characters of SHA-256(image section); `key_id` must match the key section. Full signed hashes still bind all image bytes. The short asset ID is not a replacement for a full collision-resistant file fingerprint.

This hardened viewer additionally requires bounded metadata (256 KiB, nesting at most 32, finite numeric values within the safely represented range), bounded total input (64 MiB), and a supported bounded image. It validates encoded and decoded image dimensions in the UI before showing GENUINE.

A future format should define canonicalisation cross-language test vectors, full-length asset identifiers, explicit algorithm/version negotiation, trust-key rotation and independently verifiable timestamp policy. These require coordinated signer/server changes and are not silently retrofitted into GRD1.
