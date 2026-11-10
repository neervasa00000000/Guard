# Local upgrade verification — 27 October 2026

This records U0, U1, U3 and U2 from the supplied roadmap. These are development measurements, not publication benchmarks or evidence that every possible attack is rejected. Later upgrades remain listed in UPGRADE_STATUS.md. Raw synthetic artifacts under `results/` are ignored by Git; the generators and tests are public source.

## Automated checks

- JavaScript: **84/84 tests passed** (`npm test`), including legacy compatibility, framing, streamed PNG filters, cross-language alpha compositing, fine redactions, visual proofs and fail-closed policy checks.
- Python: legacy shared vectors, all 25 conformance containers with both string and Path trust paths, three shared GRD3 cases, and 12 exact plus four visual upgrade vectors passed.
- Local deterministic differential campaign: **50,002 mutations; zero verdict disagreements, accepted mutants or uncaught exceptions**, in 40.71 seconds. This uses byte flips, insertion, deletion and truncation on small GRD2/GRD3/fine/visual-profile exact containers. It is a different campaign from the external 50,002-file structural suite mentioned in the supplied document.
- Existing attack harness: 27 cases plus 10,000 seeded flips passed. Shared vectors and the built standalone HTML are reproducible.
- Real C2PA SDK round trips passed for GRD2 and GRD3: trusted under the ephemeral test anchor, unaccepted without it, and invalid hard binding plus TAMPERED after pixel modification. These temporary test certificates establish no production identity. CLI proof export, visual-match exit 5, visual-mismatch exit 2 and redact commands also passed.

## Real browser checks

Chrome 156, native WebCrypto, compression streams and local workers:

- 7680 × 4320 (**33,177,600 pixels**) synthetic image sealed and verified GENUINE; 816 of 8160 parent tiles blacked out; result VERIFIED WITH REDACTIONS. Plain export decoded at the original dimensions. Combined seal/check/redact/export run: **21.43 seconds**, eight workers. The observed end-of-run JS heap was 580,858,397 bytes; this is not peak browser memory or total process/GPU memory.
- The actual standalone viewer checked the 33 MP container under its CSP and withheld the image for its unknown test key, as expected.
- The actual conversion submit handler completed a 4000 × 3000 synthetic JPEG at its original size, downloaded a 27.7 MiB GRD3 file and reopened it as self-signed. This covers the earlier `file is not defined` failure path.
- A 16 px demo blackout exported and reopened. The partial-parent visual-proof restriction was shown.
- Visual-copy UI: JPEG quality 50 and a half-size copy returned VISUALLY CONSISTENT with an untrusted-signer warning; a pasted white patch returned INCONSISTENT (worst difference 217). These fixtures do not establish general photographic detection rates.

## Scale diagnostics

One sequential synthetic-noise Node run, exact-only parent commitments (visual/fine layers disabled):

| Image | Format | JS seal | JS verify | Python verify |
|---|---|---:|---:|---:|
| 2048 × 2048 | GRD2 | 1.073 s | 1.203 s | 0.308 s |
| 4000 × 2000 | GRD3 | 0.935 s | 0.382 s | 0.120 s |
| 4000 × 3000 | GRD3 | 1.429 s | 0.576 s | 0.155 s |
| 6000 × 4000 | GRD3 | 2.771 s | 1.149 s | 0.319 s |
| 7680 × 4320 | GRD3 | 3.614 s | 1.518 s | 0.429 s |

33 MP container size: 100,327,307 bytes. Node process peak RSS reached 984,645,632 bytes cumulatively over the five sizes; the separate Python verifier reported 141,410,304 bytes on macOS. These are not comparable isolated peak-memory measurements. See `results/v2-scale.json`.

An independent Python 33 MP sealing run (`results/python-scale.json`) produced 100,254,368 bytes: seal 6.152 s, encode 0.064 s, verify 0.342 s, process peak RSS 575,946,752 bytes. Re-encoding the same pixels with Pillow adaptive PNG filters verified in 0.768 s; combined high-water RSS including that extra experiment was 686,948,352 bytes. Timings vary with laptop load, PNG filters and enabled proof layers; do not compare these numbers directly with VerITAS or claim a speedup without the external matched protocol.

## Fine redaction geometry

For 200 seed-42 random placements of an 80 × 80 box on a 1024 × 768 canvas, median covered/requested area was **2.56× at 64 px** and **1.44× at 16 px** (means 3.1712× and 1.422×). For 40 px boxes the medians were 5.12× and 1.92×. These are geometric experiments, not privacy or usability studies. Reproduce with `python3 bench/overredaction.py`.

## Limits and pending work

VISUALLY CONSISTENT binds signed block means, not exact pixels: some smooth blurs and mean-preserving edits pass. Native browser, Sharp/libvips and Pillow decoding/resampling can differ; held-out codec agreement remains pending. A partial-parent blackout cannot export its original whole-parent visual means without leaking hidden content, so that combination is deliberately refused.

Hardware keys, trusted timestamps, signed key-bundle distribution, production C2PA credentials, verifiable pixelation, metadata-hiding redesign and a released external attack corpus are later work. SECURITY_MODEL.md supplies a written model and reduction arguments for review, not a machine-checked proof or independent security audit. Affiliation approval, research manuscript completion and public benchmark/DOI work remain separate.

## Continued assurance phase

- Full suite now **87/87 passed**, including three signed-bundle test groups with malformed/forged/expired/rollback cases and actual signing, verification and revocation CLI operations.
- Native Chrome 156 vs independent Python: **1,026 cases, zero disagreements**, 532.1 ms browser verification time. Corpus seed 20261028; 26 exact shared cases plus 1,000 byte mutations. The browser report was downloaded and independently checked by Python, including corpus SHA-256 `ea73022a782d8676f7e7751d2ccac2197b28f44283beb89d659fdfc50b2e52d4`. This is distinct from the earlier 50,002 Node/Python campaign and the external structural harness.
- Native Chrome signed-bundle checks: **14/14 agreed with Python**, including valid, revoked, expiry boundary, rollback, equivocation, malformed/duplicate key and forged-signature fixtures. A valid bundle containing a revoked key is accepted as a trust-policy update; its revoked signer is excluded from trusted anchors.
- Signed-bundle tooling is opt-in. No production root, new signer identity, browser storage or deployment was introduced. See [TRUST_BUNDLES.md](TRUST_BUNDLES.md).

Raw evidence: `results/browser-differential.json`, `results/browser-differential.png`, `results/trust-bundle-vectors.json` and `results/trust-bundle-browser.png`.

## Submission fixes: measured visual-on/off sealing (28 October 2026)

These new measurements supersede the interpretation of earlier exact-only sealing numbers. Each engine used its own seeded synthetic pixels, identical within its on/off pair; the engines use different generators. One sequential sample per size/mode on the development laptop, fine sub-tiles disabled. Do not read an on/off difference as a controlled overhead estimate or compare it with another paper’s hardware. Node process RSS is cumulative high-water; Python uses isolated child processes. Native image input/generation and encoding are outside the reported seal interval. Raw rows retain encode/verify times and sizes.

| Size | Visual layer | JS seal | Python seal |
|---|---|---:|---:|
| 2048 × 2048 | off | 0.975 s | 0.478 s |
| 2048 × 2048 | on | 2.005 s | 4.677 s |
| 4000 × 2000 | off | 0.952 s | 0.769 s |
| 4000 × 2000 | on | 1.118 s | 8.279 s |
| 4000 × 3000 | off | 1.414 s | 1.218 s |
| 4000 × 3000 | on | 1.709 s | 11.644 s |
| 6000 × 4000 | off | 3.052 s | 2.215 s |
| 6000 × 4000 | on | 3.468 s | 25.174 s |
| 7680 × 4320 | off | 5.091 s | 3.322 s |
| 7680 × 4320 | on | 4.781 s | 38.473 s |

Raw: `results/v2-scale.json` and `results/python-scale.json`. These are new local measurements; the supplied paper’s figures and dagger-marked results have not been replaced.

## Submission regression results (28 October 2026)

91/91 Node tests and the Python vector suite passed after the shared integer native-area mapping and BORDERLINE changes. Same-size y8c16-v1 bytes remain identical, so no signed-feature version bump was made. Both real-SDK C2PA formats now pass through the default single test command.

The newly generated Kodak corpus has 168 cases (24 × seven documented transforms). Node and native Chrome 156 both agree with Python on every verdict/acceptance flag. Chrome's per-case DOM report was saved and rechecked independently in Python against the same candidate hashes. JPEG q30 includes two borderline cases; radius-2 blur includes one borderline case. Do not count borderline as accepted, and do not equate this corpus with the absent external transform harness. See SUBMISSION_STATUS.md and `results/visual-corpus/summary.json`.
