# Guard UI refinement and blackout workflow fix

29 October 2026, based on published commit `c508f7a`. This revision includes the follow-up blackout workflow fix for publication on main.

## Changes

- A consistent visual system: quieter surfaces, typography, borders, focus states and navigation, with a proper upload icon and clearer task tabs.
- Desktop results pair the picture with its verdict and download actions. Mobile keeps a single column and a full-width primary action.
- Desktop Seal uses a large editor beside a compact consent/download panel. Mobile reduces repeated explanations and puts the original-copy checkbox and signer shortcut under More options.
- When the private original-copy option is enabled, the collapsed summary explicitly says **original copy enabled**. The default remains off and the downloaded blackouts are still applied and verified first.
- Received GRDs now display **Original signer kept · no signing key needed** in the editor instead of the disposable-key note.
- Advanced opens one tool at a time. Signer, person, bundle, visual-copy, report, viewing and offline tools remain available, including deep links. About keeps privacy text behind its existing disclosure; the privacy link opens it directly.
- Shorter preparation feedback; transparency/metadata conversion details remain in About. No verifier, format, crypto or trust-list changes.

## Blackout workflow fix

- Pictures dropped on the checker or Seal now open in the blackout editor; previously the global drop handler always sent them to the verifier.
- The upload target explicitly says “Drop a picture here, or choose a file”. Instructions above the image explain dragging to black out areas, with numerical entry available below.
- Checked GRD2/3 files have a direct **Black out areas** action beside the picture. **Hide preview** also sits there and only shields the on-screen preview. Grid and resizing settings now live beside the editor.
- Unknown-signer files require explicit preview approval and a separate edit action. Export checks signature and region integrity again and retains the unknown verdict. Tampered and revoked files cannot enter the editor, including forced handler calls.
- Existing signed files retain their original signer without requesting a signing key. GRD1 cannot use the key-free blackout flow.

Current native drag screenshot: [blackout-editor-fixed.jpg](docs/ui-polish/blackout-editor-fixed.jpg). It shows two selected areas after an actual pointer drag on a synthetic TEST ONLY image. Earlier gallery captures document the visual polish before the new upload instructions and editor settings; their height measurements are superseded. Final layout measurements show no horizontal overflow at all three tested widths.

## Verification

- All **119 Node tests** pass with `node --test --test-concurrency=1 --test-timeout=60000 tests/*.test.mjs`. The initial concurrent invocation stalled without a failure and was stopped; the complete serial run passes with no skips or cancellations.
- All **90 browser assertions** pass: trust 17, advanced tools 9, encrypted signers 23, privacy/drop 10, sealing 19, blackout discovery 12. An additional revoked-file guard confirms edit blocking. Added checks cover exclusive tool expansion and the visible original-copy-enabled notice.
- All **33 layout cases** pass at 1280, 390 and 320 CSS pixels.
- axe reports zero violations across **42 audited states**, including the newly collapsed expert tools expanded individually, edited Seal controls, and revoked fixtures at desktop/mobile widths.
- All **39 doubled-text cases** pass without horizontal overflow, including every expanded Advanced panel. This is a computed-font doubling probe, not a physical phone or native zoom trial.
- Deterministic build, standalone equality, script parsing and clean diff checks pass.
- Cryptographic/verifier modules, trust lists and vectors remain unchanged from c508f7a. Direct saved-file/offline-origin validation remains the previously recorded manual limitation; no new offline-origin trial or deployment is claimed.

Local diagnostic evidence (ignored by Git): `results/blackout-*.json`, `results/ui-polish-*.json` and `/tmp/guard-blackout-fix-tests.log`. The result-action budget is now five, permitting two direct picture controls alongside download actions; current visible result states use four. QA remains isolated from production HTML. Existing QA assertions are retained; selectors now expand the relevant tool before testing its form. No existing test is deleted.
