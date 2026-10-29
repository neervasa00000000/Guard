# Implementation and test record — 27 October 2026 (Australia/Melbourne)

The three supplied documents were treated as reference requirements, not as proof of completed work or authority to publish. Work was applied to the local `Guard` checkout. That statement described the initial preparation phase; later authorized pushes and verified deployment revisions are recorded below.

## Changes

- Both implementations reject non-zero pixels in tiles claimed as black: TAMPERED, `blackout incomplete (tile i)`. Legacy blur remains accepted with a per-tile warning and can be sanitized by re-export.
- Typed PNG/proof failures separate damaged input from verifier faults. Injected hash and decoder faults produce CANNOT VERIFY; malformed UTF-8, JSON, base64, PNG and DEFLATE produce TAMPERED.
- Python enforces GRD2 size/dimension/pixel/tile bounds with LIMIT EXCEEDED. Oversized unknown-format input also hits the 32 MiB gate; existing GRD1 retains its 64 MiB limit.
- CLI verdict exit codes now use 0/2/3/4/5/6 as requested. This changes the previous 10–43 contract; consumers must migrate.
- New GRD2 seals use signed profile 2.1, random 16-byte asset IDs and UTC times claimed by the signer. Legacy manifests remain supported. Tile commitments are unchanged.
- Plain PNG export is available in the viewer and CLI; the CLI also exports JPEG. Broken proofs are refused. Hidden pixels stay zero and viewer overlays are omitted.
- Fixed the C2PA bridge's reference to removed `grd.PINNED`. Added a reusable real-SDK demo and tightened the edited-pixel regression.
- Documented the commitment-vector/Merkle-root security distinction and rebuilt both standalone viewers.

## Observed local evidence

| Check | Result |
|---|---|
| Baseline before edits | 54/54 existing Node tests passed; these tests still allowed dirty blackout tiles |
| Final Node suite | 62/62 passed, no skips (includes actual conversion submit handler) |
| Shared deterministic vectors | 11/11 in JS and Python; legacy, 2.1, blackout forgery, identity/time edits, damaged DEFLATE |
| Existing conformance corpus | All 22 cases agree in JS/Python; legacy containers were retained |
| Python regressions | Malformed shapes, policy faults, injected faults, truncation, 200 seeded body flips and all CLI verdict-code groups passed |
| New local attack catalogue | 27/27 named synthetic cases passed in both languages |
| Extended local mutations | 10,000/10,000 seeded body flips returned TAMPERED in both languages |
| Existing mutation tests | 7,504 exhaustive GRD1 flips and 2,000 GRD2 mutations rejected |
| Large image interoperability | 2048×2048 seeded RGB noise, 16,911,663-byte container; GENUINE and VERIFIED WITH REDACTIONS after hiding 103/1024 tiles, in Node, Python and Chrome 156 |
| Browser shared vectors | 11/11 passed in Chrome 156 |
| Actual viewer smoke | Loaded demo, clicked plain download, selected rectangle, exported/reopened redacted GRD, clicked plain download again |
| Downloaded PNG inspection | 384×256, only IHDR/IDAT/IEND, zero `GRD` byte sequences in these fixtures; redacted tile zero and decoded pixels identical to source |
| C2PA 0.38.1 | Trusted + VERIFIED WITH REDACTIONS with test anchor; Valid/unaccepted without anchor; edited copy Invalid with dataHash mismatch + TAMPERED |
| Build and vector regeneration | Repeated generation was byte-identical; both standalone HTML outputs match |
| Private-key scan | No tracked PEM/key files and no private-key blocks in scanned JSON/PEM files |
| Whitespace check | `git diff --check` passed |

The 20 MB base64 shape scan measured 68–89 ms when run independently on this laptop. Timings are diagnostic, not publication measurements. Mutation checks use small deterministic test vectors and exclude magic bytes. The new local catalogue is not the unavailable paper harness, despite also containing 27 cases.

Raw local logs and JSON are in ignored `results/`. The captured Chrome result is shown below.

![Chrome 156 shared-vector and 4 MP verification results](results/browser-check.png)
Commands are in [REPRODUCE.md](REPRODUCE.md).

## Still unverified

The external 107-image Kodak/DIV2K benchmark, its original A/B/R attack tables, original-build comparison, dedicated-machine performance runs and second-device tests were not run because the referenced harness/datasets are absent here. No publication-ready claim is made. Release citation metadata, a DOI and tagging are also outstanding; research novelty and venue claims from the plan were not reviewed.

## Follow-up: actual browser workflow audit

A fresh end-to-end check found two additional defects, both fixed locally and rebuilt:

1. The conversion submit handler referenced `file.size` outside the file-selection handler where `file` was defined. A real browser conversion failed with `Conversion failed: file is not defined` before downloading. The selected image now retains its original byte size as `sourceBytes`; the submit handler uses that snapshot. A regression executes the actual handler with real signing/verifying code and asserts the download, automatic reopen, finite size summary, and restored controls. It failed before the fix and passed afterward.
2. Re-exporting a legacy blur container in JS cleared its pixels but retained `method: blur`, unlike Python. JS now labels all sanitized hidden tiles `black`. The regression compares JS/Python mask entries and pixels, and preserves the original signature/manifest.

The QA fixture helper was also repaired to replace the complete temporary trust record (including its fingerprint). Temporary QA viewers remain under `/tmp/guard-qa`; production trust data is unchanged.

### Current browser results (Chrome 156)

- Trusted GRD2: GENUINE; plain download available.
- Honest redaction: VERIFIED WITH REDACTIONS; plain download available.
- Edited signed metadata or forged blackout: TAMPERED; image/plain download withheld.
- Ordinary non-GRD input: NOT A GRD; plain download withheld.
- Unknown signer: UNTRUSTED SIGNER; image/plain download withheld.
- Fully hidden: FULLY REDACTED; no visible image claim/plain button.
- Revoked test key: REVOKED KEY; image/plain download withheld.
- Actual 12 MP JPEG conversion: 4000×3000 → 2305×1728, 999 tiles. Downloaded and reopened as UNVERIFIED: SELF-SIGNED, as expected for a browser-generated key. Then exported a blackout copy and its plain PNG. Python independently verified both downloaded GRDs; the root and asset ID were preserved. The plain PNG exactly matched the redacted pixels, tile 0 was zero, and only IHDR/IDAT/IEND chunks were present.
- Repeated full suite: 62/62; Python vectors/regressions and the real C2PA SDK checks passed. The local 27-case/10,000-body-mutation check also passed in both languages. Rebuilt viewers and shared vectors reproduced byte-for-byte.

### Historical public-site observations before the 28 October push

At `https://neervasa00000000.github.io/Guard/` during this audit:

- The existing 16 MiB legacy noise fixture verified as UNVERIFIED: SELF-SIGNED (1014/1014 tiles), rather than TAMPERED. This is one fixture, not a rerun of the external 26-image set.
- A forged-blackout demo still received DEMO with a hidden-pixel warning instead of TAMPERED.
- A 96×64 PNG conversion failed with `Conversion failed: file is not defined`.
- The plain-download feature was absent.

Those observations describe the site before the fix was published. Commit 5c616009 was pushed on 28 October 2026. On 29 October, the deployed index.html was fetched and was byte-identical to that commit: SHA-256 2745a9327c71a0cfbc90e01474bd1bf8fbfb370a8b2495ff489b84df37ad717c. This does not describe the subsequent v4 changes. No release tag or DOI was created by this work.

![Observed public-site conversion error](results/live-conversion-failure.png)

Raw follow-up evidence: `results/recheck-npm.log`, `results/recheck-python.log`, `results/recheck-c2pa.json`, `results/browser-verdict-checks.json`, and `results/browser-conversion-roundtrip.json`.


## Later upgrade batch

The observations above are historical. The conversion repair was subsequently pushed and checked live. New U0/U1/U3/U2 implementation evidence is recorded in [UPGRADE_RESULTS.md](UPGRADE_RESULTS.md), with remaining scope in [UPGRADE_STATUS.md](UPGRADE_STATUS.md). The published revision is identified by the live hash recorded above; these local test results do not establish a later deployment.

## V4 local batch — 29 October 2026

| Check | Measured result |
|---|---|
| Node 22.16 and Node 20.19 | 100/100 tests passed in each runtime |
| Python 3.13 | Shared exact/area/signer vectors, CLI visual exits 5/7/2, human line and --quiet passed |
| Real C2PA SDK | GRD2 and GRD3 passed default round-trip command |
| Named attacks | 27/27; 200/200 seeded body flips rejected in both implementations |
| Local differential mutations | 10,000 cases; zero verdict disagreements, accepted mutants or uncaught exceptions |
| Browser signer/trust workflow | Nine checks passed: trusted/self/unknown display, plain export, signed bundle, rollback and clear |
| Browser privacy/conversion/drop | Ten checks passed, including real self-signed conversion and required acknowledgement |
| axe-core 4.14 / Chrome 156 | Zero serious/critical issues across eight viewer states |
| CSS reflow | 12/12 checks: empty/trusted/unknown at 320, 360, 390 and 1440 CSS pixels, no horizontal overflow |
| Keyboard | Arrow/tab task navigation and Enter-triggered plain export exercised |
| Revoked browser fixture | Red “Signer key revoked”, preview withheld, no unknown-signer override |

These checks use deterministic TEST ONLY identities in isolated local QA copies. The iframe reflow fixtures disable frame guards only in those QA copies; production frame protection stays intact. This is not a real-phone, screen-reader, physical zoom or user-study result. That earlier revision used the label **Neer**; the independent-review follow-up removes that attribution from the ownership-unconfirmed legacy key. The key remains revoked. A new public key has not been supplied. These observations were recorded locally before v4 source publication; they are not a hosted-deployment check.

Evidence: `results/v4-signer-flows.json`, `v4-privacy-drop.json`, `v4-axe.json`, `v4-css-viewports.json`, `v4-keyboard.json`, `v4-revoked.png`, `v4-reflow.png`; see V4_STATUS.md and REPRODUCE.md. No screenshot-reseal watermark rate or timestamp validity is claimed.


## Verified v4 deployment, 29 October 2026

Commit 3631573 was pushed on 29 October 2026 at 13:59 AEDT and GitHub Pages serves it (index.html SHA-256 7c3ec4b255347d92e5190f503009f48f54eb24d400e5c65e80c37b3f49899341, byte-identical to that commit and its build). No release tag or DOI was created by this work. Source publication of the independent-review follow-up was subsequently authorized separately; verify its Pages revision independently.

## Independent-review follow-up (local)

105/105 Node tests pass, including explicit CLI rename permission, symlink-safe CLI entry detection, neutral legacy attribution, revoked-banner identity suppression, plain-language titles and fresh-clone QA prerequisite messaging. Python vector/CLI checks and both C2PA formats pass. Chrome passes 14/14 updated signer/title workflow checks; accessibility results are recorded in `results/review-followup-axe.json`. Generated standalone files are checked for deterministic rebuild equivalence. No signature domains, pixel commitments, feature bytes, tau, verdict strings or exit codes changed in this follow-up. The owner subsequently authorized source publication of these fixes; this test record does not establish a later Pages deployment.

## Simplified recipient interface (local, 29 October 2026)

Trust import and copy checking now share a collapsed Advanced tools disclosure below the image preview. The main result keeps the plain-picture download; visual-proof and offline-viewer downloads remain available in Advanced tools. Redaction controls, privacy details and technical evidence expand on demand. Security verdicts and verification algorithms are unchanged.

Validation: 105/105 Node tests; Chrome signer/session-trust flow, 8/8 advanced-tool checks (including consistent, borderline and inconsistent copy results), 10/10 privacy/conversion/drop checks; axe-core reports zero violations in eight states; 12/12 CSS viewport checks pass at 320, 360, 390 and 1440 pixels. Keyboard Enter collapses Advanced tools, and Privacy details opens its disclosure. These use isolated TEST ONLY identities and synthetic fixtures, not a user study or a hosted deployment check. Evidence is recorded in ignored local `results/simple-ui-*.json` and screenshots.

## Wider workspace and consistent disclosures (local, 29 October 2026)

Removed the 1120 px page cap; fluid side margins use 16–48 px. All six native details controls now share a right-aligned plus/minus indicator and retain keyboard expansion. Chrome measured a 1203 px workspace in a 1280 px viewport (94%). The extended iframe suite passes 18/18 cases at 320, 360, 390, 1440, 1920 and 2560 CSS pixels; eight-state axe reports zero violations. Enter toggling and computed plus/minus indicators were checked in Chrome. Local evidence: `results/wide-ui-axe.json`, `results/wide-ui-viewports.json`, `results/wide-ui-main.png`. These are local checks, not a deployment check.

## Offline signer setup and recipient trust (local, 29 October 2026)

Guard now creates a password-encrypted `.guardkey` backup, unlocks it to a nonextractable in-memory Ed25519 key, exports only public contact data, and signs new asset-purpose GRDs. Creating/unlocking never automatically trusts that signer. Recipients can explicitly trust a public `.guardsigner` contact after independently confirming its full fingerprint and name; this trust is tab-only. Existing disposable personal files remain self-signed. Revoked keys stay rejected. Download offline viewer is also available in Seal a picture.

Validation:

- Node: 112/112 tests, including wrong passwords, salt/nonce/ciphertext changes, fixed KDF bounds, malformed/oversized envelopes, public-contact validation, mismatched private/public pairs, unknown/trusted/revoked assets and unchanged personal-purpose semantics.
- Chromium: 23/23 signer workflow checks through actual form handlers, including encrypted export/unlock, public-only export, named conversion, explicit trust, clear/revocation, cancellation during unlock/sign/import, and saved HTML excluding runtime passwords and keys. QA captures downloads in memory with random TEST ONLY identities; it does not establish a real signer or prove a browser completed saving to disk.
- Existing browser workflows: 17/17 signer/bundle, 10/10 privacy/conversion/drop and 8/8 copy-consistency checks passed on appropriately fresh pages.
- Python independently decrypts the encrypted key envelope, matches its public key, verifies unknown/trusted GRDs, and produces a signature verified by Web Crypto. Shared Python format/visual/CLI regressions also pass.
- Final layout: zero axe violations across 10 states, and 30/30 CSS reflow cases passed at 320, 360, 390, 1440, 1920 and 2560 pixels, including the expanded signer and person-trust forms. Results are recorded in `results/offline-signer-axe.json` and `results/offline-signer-viewports.json`.

Evidence is in ignored `results/offline-signer-*.json`, `results/offline-signer-setup.png`, `/tmp/guard-offline-final-tests.log` and `/tmp/guard-offline-python.log`. No real user key was generated, pinned or committed; no hardware, timestamp or C2PA identity claim is added. Direct saved-file/offline-origin browser testing remains **PENDING**: the browser tool explicitly blocks file URLs. HTTP Chromium tests exercise the same self-contained build, which has no online runtime dependencies; they must not be described as that pending file-origin trial. No deployment is established by these local checks.

## UX redesign, 29 October 2026

The redesign adds pre-download blackouts and one-card results, with expert tools and privacy in separate in-page views. Detailed scope, changed tests, actual measurements and limitations are recorded in [UX_STATUS.md](UX_STATUS.md). The retained 112 tests plus six new sealing/UX checks pass; Python, real C2PA formats, 50,002 local differential mutations, 27 named attacks and 10,000 body flips pass. No protected verifier, crypto, trust-list or format code changed. This record establishes local validation, not Pages deployment.
