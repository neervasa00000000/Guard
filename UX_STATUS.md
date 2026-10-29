# Guard UX redesign status

Implemented against `8c260ac`, 29 October 2026. The owner first requested local implementation, then explicitly authorized pushing it. No release tag, DOI, new signer identity or research measurement is created by this change.

## Result

Check and Seal are the only main tasks. A selected file replaces the drop zone with one verdict card, a stamped picture when permitted, plain-language hidden-area labels, download actions and collapsed Details. Advanced contains signer keys, people, bundles, visual-copy checking, reports, viewing settings and the offline copy. About contains the example, limitations, source link and the unchanged full privacy section. All views remain in one HTML file.

Seal now previews optional blackouts before signing/downloading. The default output applies selected areas in memory, verifies the result and downloads only `image.GRD`. Saving `private-original.GRD` requires a separate unchecked opt-in. With no areas selected, the user can deliberately seal the full picture after the privacy acknowledgement. Received, viewable GRD2/3 files retain their original signature and key when blacked out; no signing key is needed. GRD1 and non-viewable files stop rather than bypass verification/withholding. Consent resets after an area changes. Keyboard number entry, removable area chips and pointer dragging are available.

## Measured targets

Measurements use isolated TEST ONLY identities/fixtures, not the public deployment or a user study. Counts include the page header and use the stricter body.innerText count for landing/seal; QA controls are excluded. Responsive trials use Chromium iframe CSS viewports, with native keyboard/pointer checks additionally exercised on a direct page.

| Target | Desktop 1280×800 | Phone CSS viewport 390×844 |
|---|---:|---:|
| Landing words, at most 40 | 37 | 36 |
| Landing controls, at most 6 | 6 | 6 |
| Landing fits without scrolling | Pass | Pass |
| Seal words before image, at most 70 | 41 | 40 |
| Seal controls before image, at most 6 | 6 | 6 |
| Result words above image, at most 45 | Pass | Pass |
| Result buttons with Details closed, at most 3 | Pass | Pass |
| Result title top, at most 160 px on phone | — | 152 px |
| Plain download visible for the 3:2 trusted picture | Pass | Pass |

All 33 normal-size layout cases pass at 1280, 390 and 320 CSS pixels. The largest above-image count is 45. All 18 enlarged-text cases pass: each element is given twice its baseline computed font size, checking for horizontal overflow. This is a CSS text-resize probe, not a native browser-zoom or physical-device trial. Main Check + Seal contain 10 template buttons, including hidden loading/reveal controls.

The brief's before metrics are supplied audit observations; this change independently measures the after state. It does not reclassify those historical observations as new trials.

## Validation

- Node: **118/118** tests (112 retained, six new UX/sealing tests).
- Python shared vectors, conformance, visual/area profiles and CLI regressions: passed.
- C2PA SDK: GRD2 and GRD3 round trips passed, including unanchored and edited rejection.
- Local differential mutations: **50,002**, zero disagreements, accepted mutants or exceptions. This is the repository's seeded byte flip/insert/delete/truncate harness, not the external paper's structural corpus.
- Local attacks: **27/27** named cases and **10,000/10,000** body bit flips rejected in both implementations.
- Redesign browser acceptance: **18/18**, including black output pixels, exactly one default download, explicit original opt-in, original signer retention, PNG export, withheld tampered/unknown behavior, grey operational errors, expert reachability and no runtime HTTP resource entries.
- Existing browser workflows pass: signer/bundle 17/17, visual copy 8/8, encrypted signer 23/23, privacy/drop 10/10. With the 18 redesign checks, all 76 browser workflow assertions pass. Their final reports are in `results/ux-*.json`.
- axe reports zero violations across 34 audited states: every verdict family, Seal including an edited picture, Advanced and About at 1280 and 390, plus a revoked-policy fixture at both widths. See `results/ux-axe.json`.
- Native keyboard: Enter opens real file choosers; Tab reaches the plain download; Enter exports; arrows switch task tabs; Tab/Enter/number entry adds an area; Space confirms consent; Enter seals and focus moves to Check this file. That link opens the checked output.
- Native pointer drag creates a rounded area; removing a chip removes that area and keeps consent gated. No physical touch-device claim is made.
- Protected verifier/crypto/Python modules, trust lists, vectors and conformance files are unchanged. The full privacy section and CSP are byte-for-byte identical to the baseline. Standalone outputs are rebuilt deterministically and checked for equality and script parseability.

## Test changes and reasons

No existing test was deleted and no acceptance/rejection assertion was removed.

| File | Change and reason |
|---|---|
| `tests/result-copy.test.mjs` | Updated presentation strings to the new verdict labels; technical verdict preservation, revoked identity suppression and neutral legacy attribution assertions remain. |
| `tests/converter.test.mjs` | Supplies new UI editor state to the real-handler harness. The expected automatic-open count changes from one to zero because sealing now offers Check this file instead of switching tasks automatically. Download, integrity, size-summary and unlocked-control checks remain. |
| `tests/ux-sealing.test.mjs` (new) | Tests the real submit handler for black pixels before first download, explicit original opt-in, original signature/root preservation without re-signing, failed-check no-download behavior, outward rounding and CSP/no-storage constraints. |
| `scripts/v4-browser-qa.mjs` | Replaces disclosure-state assumptions with separate-view assertions; uses new presentation labels while preserving signer, revoked/unknown, bundle rollback/clear, personal-purpose and copy-verdict checks. Adds 3:2/redacted/fully-hidden fixtures and broader audit states. |
| `scripts/ux-browser-checks.js` (new) | Browser acceptance, view metrics, revoked guard and snapshot fixtures; test-only, never part of production output. |
| `scripts/ux-review-page.html` (new) | Exact-width layout/a11y and enlarged-text fixture runner. Frame guards are disabled only in labelled test copies. |

The enlarged audit found an area-chip accessible-name mismatch; the chip now has separate dimension text and an icon button named Remove area N. Enlarged text also caught input/heading overflow, which is fixed in the final stylesheet.

## Accuracy and implementation choices

- Changed describes failed integrity checks, rather than asserting a malformed file must once have had a valid signature.
- Self-signed describes a self-signed key, rather than assuming every external personal-purpose file used a disposable key. The Seal flow's own disposable-key note remains accurate.
- Fully hidden personal/demo files do not acquire a Genuine title or trusted name.
- Not a Guard file asks for the original GRD; renaming an arbitrary file is insufficient.
- The logo and offline pill are non-interactive, and the extra footer is in About, so the landing view meets the six-control target. About and Advanced remain visible navigation links.
- Adjacent hidden cells merge for UI labels/outlines only; raw report rectangles and JSON stay unchanged. Up to 200 merged entries are rendered in the plain list, with remaining raw detail in Advanced. New editor selections are capped at 200 areas to keep its UI bounded.
- Trust source and full fingerprint remain in Details; raw technical fields and report export are in Advanced. No new trust is granted automatically.

## Evidence and remaining limits

Local raw evidence: `results/ux-layout.json`, `ux-text-200.json`, `ux-axe.json`, `ux-redesign-acceptance.json`, `ux-keyboard.json`, `ux-pointer.json`, `ux-preservation.json`, existing-workflow reports, `results/local-differential.json`, and the `/tmp/guard-ux-*.log` test logs. These diagnostic results are ignored by Git. The committed screenshot gallery is [docs/ux/README.md](docs/ux/README.md); captures are native browser JPEGs at the stated CSS widths.

Direct saved-file/offline-origin browser validation remains pending because the browser tool blocks file URLs. The same self-contained code is exercised through local HTTP, with no external scripts/styles or storage APIs. Runtime Resource Timing reports no HTTP resource requests after the document; a raw DevTools Network-domain capture and a physical phone/screen-reader trial were not performed. No claim is made that these checks prove absence of all defects or establish a new hosted deployment.
