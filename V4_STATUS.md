# V4 implementation status — 29 October 2026

Reference: BUILD_PROMPTS_V4.md. This local batch addresses items 0 and 1 and the recipient/privacy/accessibility engineering in item 5. The roadmap's estimated effort and target detection rates are not measured results. The owner subsequently authorized publishing this source batch to main. No release tag, DOI or journal submission was created; deployment must be checked separately.

| Item | Implemented locally | Pending scope / evidence |
|---|---|---|
| 0 carry-over | BORDERLINE exit 7; shared exit table checks; documentation and measured deployment correction; no feature/commitment change | Re-run checks recorded below |
| 1 identity | Report fields in JS/Python; trusted/unknown/revoked banners; explicit stamped unknown preview; public registry and pin/revoke helper; session bundle import; CLI signer line and --quiet | Neer's public key/fingerprint not supplied; no replacement identity pinned; public endpoint requires the v4 Pages deployment |
| Legacy key decision | Owner requested revocation; independent review identified an attribution problem, and the owner approved a neutral legacy label. Revocation date and reason remain unchanged. | Old offline/public viewers do not learn this until updated |
| 5 recipient UX | Check/seal tabs; file drop; explanations and exact technical verdict; privacy acknowledgement; local card/A4 heuristic; keyboard tab handling; contrast fixes; axe dev-only QA | Human five-person test, VoiceOver/TalkBack/NVDA, actual phones and physical zoom tests remain unmeasured |
| 2 image carriers | Not implemented in this batch | `.guard.png` exact carrier, JPEG visual carrier, malformed-carrier and sharing tests |
| 3 timestamps | Not implemented | TSA selection and explicit network approval; offline token validation must precede any timestamp claim |
| 4 watermark | Not implemented | Measured research prototype, score calibration/search definition, quality and false-positive experiments; no anti-copy guarantee |
| Real-world plan | Empty CSV templates under ignored results/realworld; generator refuses to overwrite existing results | No sharing-channel or human/device experiment has been invented |

A signature identifies a key and binds signed pixels; it does not establish a truthful scene, capture identity or ownership. The UI retains these limits rather than labelling an arbitrary signed photograph as real. Commit 3631573 was pushed on 29 October 2026 at 13:59 AEDT and GitHub Pages serves it (index.html SHA-256 7c3ec4b255347d92e5190f503009f48f54eb24d400e5c65e80c37b3f49899341, byte-identical to that commit and its build).

## Verification completed

- 100 tests passed on Node 20.19 and Node 22.16; Python vector/CLI checks and both C2PA formats passed.
- 27 named attacks plus 200 flips passed; 10,000 differential mutations produced no disagreements, accepted mutants or exceptions.
- Chrome signer/import workflow: 9/9; privacy/conversion/drop: 10/10.
- Axe: zero serious/critical findings in eight states; CSS reflow 12/12 at 320/360/390/1440 px.
- Keyboard task switching and plain export exercised; revoked fixture cannot be revealed.

See TEST_RESULTS.md for scope and evidence paths. Source publication was authorized on 29 October; Git records the pushed revision. These local checks alone do not establish Pages deployment.

## Independent review follow-up (local)

I1: the revoked, ownership-unconfirmed record now has a neutral legacy label. Neer remains the intended name for a future key whose public fingerprint is supplied and verified. Existing names require explicit --rename; revoked keys cannot be reactivated. I2: the deployed 3631573 hash was independently rechecked. I3: plain titles were added while retaining exact technical verdicts and the signer line. I4: missing QA prerequisites now produce an actionable message; generation order is documented. Source publication of these follow-up fixes was subsequently authorized by the owner; deployment must be checked against that pushed revision.
