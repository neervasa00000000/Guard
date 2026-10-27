# Redaction release checks — 2026-10-27

- Core suite: 30 passing tests; 7,504 generated GRD1 single-bit mutations and 2,000 deterministic GRD2 single-bit mutations rejected.
- GRD2 coverage: exact pixels and edge tiles, salts, immutable manifest/signature through redaction, retained-tile edits, mask disagreement, unknown/demo/revoked keys, fully redacted files, chained black/blur, rectangle rounding, structural and size failures, report data minimisation.
- Independent Python ↔ JavaScript: issue, verify and redact each other's output, including a Unicode label; malformed boolean tile indices rejected.
- Official C2PA SDK integration: PNG manifest/signature trusted under an explicitly configured ephemeral test CA; retained GRD proof valid. Modified exported pixels fail C2PA asset integrity even inside a GRD-hidden tile. No production/global certificate trust inferred.
- Browser: example generation, rectangle selection, export/download and automatic reopening worked. Exported file was also checked with Python: 22 retained / 24 total; hidden tiles 0 and 1 agreed.
- Browser with a temporary QA-only anchor: trusted partial file reports VERIFIED WITH REDACTIONS; changed signed label reports TAMPERED and withholds the image; bundled revoked test key reports REVOKED KEY and withholds the image.
- Responsive DOM check at 390px and 1440px: no horizontal document overflow or off-screen form controls. Full-page mobile screenshot inspected; fields, mask, reports and details remain readable in the normal vertical flow.
- No browser console warnings/errors observed in the failure flow.
- Standalone HTML build is dependency-free at runtime. Actual file:// automation was unavailable in this environment; browser QA used local HTTP. Opening the downloaded HTML offline remains a manual release check.

All fixtures are generated test data. The original Goose Bumps sample and original server are absent. This is regression evidence, not a cryptographic audit or a claim of universal browser/legacy-server parity.
