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

## Browser conversion follow-up

- Core suite now has 32 passing tests. Added encoded-image inspection before decode, image size limits, GIF/BMP header bounds, unsupported-content rejection, personal-signature trust isolation, revocation and Python parity.
- Browser PNG conversion downloaded a real GRD2 and reopened it as SELF-SIGNED, with all 6 tiles matching. The downloaded file independently passed Python with the same dimensions, counts and self-signed verdict.
- JPG, WebP, GIF and BMP inputs all produced ready previews at the expected 192 × 128 dimensions.
- Submission without a ready image explained the next action. A text file renamed .jpg was rejected and its preview cleared.
- The converter remained within the viewport at 390px, with no horizontal document overflow or off-screen inputs/buttons; mobile screenshot inspected.
- Optional official C2PA integration still passes. Personal files are not promoted to a trusted C2PA export.

## Large-camera-photo follow-up

- 33 core tests pass, including portrait/landscape/panoramic output bounds, tile-count limits, no upscaling and bounded source inspection.
- A generated 6000 × 4000 (24 MP) JPG previews at 2496 × 1664 with Fit large photos enabled. Opting out explains the output limit; enabling it again recovers the preview.
- The downloaded GRD is made from the displayed fitted pixels; original source pixels and metadata are not embedded. Core verifier limits remain unchanged.

## Trust/privacy audit follow-up

- 40 tests pass. CLI exit 0 is now restricted to GENUINE; personal, demo, partial and fully redacted files return 2 even when their mathematical proofs are valid.
- Every shipped .GRD example is checked in both implementations. The double-encoded redacted asset was regenerated and now reports DEMO with one hidden tile.
- New tests cover an edited image re-signed as personal, rejection of blur exports, unsigned-method reporting, and clearing all hidden pixel bytes (including legacy blur regions) on re-export in JS and Python.
- Cross-language cases include UTF-16 Unicode key ordering, fractional/unsafe metadata numbers, boolean dimensions, lone surrogates, impossible policy dates and extra inflated PNG data. Both reject the covered invalid cases. Legacy fractional metadata is now intentionally outside the acceptance profile.
- The issuer-key helper is tested for restricted private-key permissions and refusal to overwrite existing keys.
- Browser conversion reopened as UNVERIFIED: SELF-SIGNED, with the explicit anyone-can-edit-and-re-sign warning, amber styling, an empty public label and generic image.GRD filename. No blur control is present. Mobile width 390px had no horizontal overflow.
- A cross-origin-port iframe displayed only the open-directly warning and did not initialize the app. This confirms the JS fallback, not HTTP-header enforcement on GitHub Pages. Header-level protection remains host-dependent and is documented in PRIVACY.md.
- Official C2PA round-trip integration still passes. No production trust-list admission, cryptographic audit or universal legacy decoder parity is inferred.
