# Verification notes

27 October 2026.

- 12 automated tests pass with Node 22; 7,504 single-bit changes across every byte of a generated GRD1 fixture are refused.
- Reference comparison uses the supplied viewer and an ephemeral test anchor. The original production trust anchor is retained in release output.
- In browser testing, the release viewer refuses the ephemeral test signer even when its signature is valid.
- A separate temporary QA viewer exercises GENUINE with a 960 × 640 generated PNG; malformed image bytes, wrong signed dimensions and unknown keys are refused.
- Viewing modes, keyboard reveal, hide/resume, file replacement and clear state were exercised. Clear removes the previous file name and metadata from the DOM.
- Downloaded JSON report inspected: evidence present, no payload/image bytes.
- Saved viewer inspected after opening a file: original production public key remains, uploaded file name absent, scripts/styles self-contained.
- Browser tool policy blocks `file:` navigation, so opening the downloaded HTML directly as a local file could not be automated. The equivalent self-contained release document was tested over localhost; no workaround was used for that blocked action.
- At 320, 390, 768 and 1440 CSS pixels, the document has no horizontal overflow and the canvas remains within its stage.
- No console warnings/errors were observed in the tested flows. No external network dependencies are used by the viewer.

Not verified: the absent Goose Bumps sample, original server parity, conversion, copy tracing/localisation, Android screenshot blocking, timestamp authority validation or private-key operations.

## Inspector redesign

Replaced the original cream/green editorial layout with a charcoal/cobalt utility interface, bold sans-serif hierarchy, a compact masthead and split import/verification workspace. Verified the empty state at 320, 390, 761, 768 and 1440 CSS pixels with no page overflow. Rechecked the generated genuine state and phone image controls; the canvas stays inside its frame. Cryptographic logic is unchanged.
