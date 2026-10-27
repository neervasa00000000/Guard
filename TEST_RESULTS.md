# Implementation and test record — 27 October 2026 (Australia/Melbourne)

The three supplied documents were treated as reference requirements, not as proof of completed work or authority to publish. Work was applied to the local `Guard` checkout. No release, deployment, push or external communication was performed.

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

### Public site: not yet equivalent to the corrected local build

At `https://neervasa00000000.github.io/Guard/` during this audit:

- The existing 16 MiB legacy noise fixture verified as UNVERIFIED: SELF-SIGNED (1014/1014 tiles), rather than TAMPERED. This is one fixture, not a rerun of the external 26-image set.
- A forged-blackout demo still received DEMO with a hidden-pixel warning instead of TAMPERED.
- A 96×64 PNG conversion failed with `Conversion failed: file is not defined`.
- The plain-download feature was absent.

Therefore the live site cannot be described as fully working. The fixes are present locally; publishing the corrected production viewer remains outstanding. No push or deployment was performed.

![Observed public-site conversion error](results/live-conversion-failure.png)

Raw follow-up evidence: `results/recheck-npm.log`, `results/recheck-python.log`, `results/recheck-c2pa.json`, `results/browser-verdict-checks.json`, and `results/browser-conversion-roundtrip.json`.
