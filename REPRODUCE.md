# Reproducing Guard checks

Run commands from this repository. Tested on Node 20.19 and 22; Python 3.13; Chrome 156. Install `npm ci` and the Python packages in `requirements.txt` in your chosen environment. The optional C2PA check additionally needs `requirements-c2pa.txt` (`c2pa-python==0.38.1`). This checkout already has a `.venv-c2pa` environment.

```sh
npm run build
npm test
python3 tests/test_vectors.py
.venv-c2pa/bin/python tests/c2pa_roundtrip.py
node bench/attacks-local.mjs
node bench/large-roundtrip.mjs
```

The local attack catalogue writes `results/local-attacks.json`: 27 explicitly named synthetic cases and 200 seeded body bit flips, checked in both JS and Python. It is a new local catalogue, **not** the external paper's A1–A27 catalogue. Increase its mutation count with:

```sh
FLIPS=10000 node bench/attacks-local.mjs
```

Flips exclude the five-byte magic header. Damage to magic can correctly produce NOT A GRD; a blanket assertion that every possible file-bit mutation is TAMPERED would be false. The existing GRD1 tests separately exhaustively mutate every bit and check rejection.

`bench/large-roundtrip.mjs` seals a seeded 2048×2048 noise image with an ephemeral key, verifies it as GENUINE, blacks out 103/1024 tiles and verifies VERIFIED WITH REDACTIONS. The same two containers are checked in Python. It runs languages sequentially and records diagnostic timing. A single run on an active development laptop is not publication-grade performance evidence.

## Real browser verification

```sh
python3 -m http.server 4195 --bind 127.0.0.1
```

Open `http://127.0.0.1:4195/bench/browser-check.html` in Chrome and click **Run real browser checks**. It runs the shared vectors and independently seals, verifies, redacts and exports a 2048×2048 noise image with native WebCrypto and compression streams. The result must end in ALL PASS.

Open `http://127.0.0.1:4195/` to smoke-test the actual built viewer. Load the example, download a plain image, select the default rectangle, export the redacted GRD and download its plain image. The PNGs must decode to the container pixels, contain only IHDR/IDAT/IEND chunks, and keep hidden tiles zero. The on-screen placeholders and session stamp must not appear in the PNG. UNTRUSTED SIGNER images and their download button stay withheld.

## Deterministic artifacts

```sh
python3 scripts/make-vectors.py
npm run build
```

Record SHA-256 of `tests/vectors/grd2-vectors.json`, `index.html` and `grd_viewer.html`; repeat both commands. The digests must remain unchanged. The two HTML files must match each other. Shared vectors use only a public, explicitly TEST ONLY seed and fixed salts. Their generation must never use an actual issuer key. Existing legacy conformance containers remain unchanged.

## C2PA demonstration

```sh
.venv-c2pa/bin/python examples/c2pa/run_demo.py
```

The demo creates ephemeral certificates in a temporary directory and cleans them up. It checks Trusted + VERIFIED WITH REDACTIONS under its test anchor, Valid but unaccepted without the anchor, and Invalid (`assertion.dataHash.mismatch`) + TAMPERED after a hidden-region pixel edit. It checks that both the actions and Guard proof assertions are present. The signed asset ID is inside the preserved manifest.

Pixel blackout is recorded as `c2pa.edited` with the Guard region map. The standard `c2pa.redacted` action describes assertion/credential removal, which this bridge does not perform; see the [C2PA specification](https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification). Every export gets a new hard binding to its actual PNG pixels.

## External publication protocol remains separate

The supplied documents refer to `/workspace/guard-paper/bench/run-against.sh`, `fetch-data.sh`, `analysis/analyze.py`, a 107-image Kodak/DIV2K corpus and baseline checkout `3970c6f`. Those files and datasets were not supplied in this workspace. The local checks above do not establish the protocol's P1–P8 dataset/benchmark criteria and must not be substituted for its tables.

To run that protocol, recover its harness, analysis scripts and baseline, fetch the licensed datasets with its downloader, and run the supplied sequential protocol against this checkout. Keep downloaded images, derived containers, certificates and raw results out of Git. The published pilot's timings, pass counts and journal/prior-art claims have not been independently reproduced by this work. A limited public-site browser smoke check is recorded in TEST_RESULTS.md; the deployed site still differs from this local build. Publishing fixes, release tagging, Zenodo setup and publication require their own completed release workflow.


## Isolated trusted/revoked viewer QA

`node scripts/browser-fixtures.mjs` writes a copy of the built viewer and synthetic files into `/tmp/guard-qa`, with a complete ephemeral TEST ONLY trust record. Serve that folder on a separate localhost port. Never deploy those HTML copies. Use the real production `index.html` and `grd_viewer.html` for release; their trust records remain unchanged.

The browser conversion smoke must actually click **Convert & download .GRD** and inspect the downloaded result. Calling the core sealer alone does not cover submit-handler scope errors. The follow-up audit demonstrated and fixed such an error.

## First upgrade batch (U0 / U1 / U3 / U2)

The current local results and their limits are in [UPGRADE_RESULTS.md](UPGRADE_RESULTS.md). Rebuild and check with:

```sh
npm ci
npm test
python3 tests/test_vectors.py
FUZZ_N=50002 python3 bench/differential.py
FLIPS=10000 node bench/attacks-local.mjs
python3 scripts/make-grd3-vectors.py
python3 scripts/make-upgrade-vectors.py
npm run build
node bench/v2-scale.mjs
python3 bench/scale-python.py --adaptive-verification
python3 bench/overredaction.py
GUARD_C2PA_VERSION=3 .venv-c2pa/bin/python tests/c2pa_roundtrip.py
```

Repeat vector generation and build, comparing SHA-256 before/after. Use `bench/browser-check.html?scale=33` for the native-browser 33 MP run. The scale scripts use synthetic pixels and disable visual/fine layers for the exact-only diagnostic; the browser run includes visual features. End-of-run heap and process high-water RSS have different meanings.

`grd.py seal` accepts `--format-version 3 --sub-tile 16`; visual features are enabled unless `--no-visual`. `grd.py redact --granularity 16` cannot go finer than the signed grid. `grd.py export-proof INPUT.GRD -o OUTPUT.grdp` exports the visual sidecar; `grd.py verify-visual OUTPUT.grdp COPY.jpg` checks a candidate. A visual match exits 5 and never asserts exact-pixel genuineness; inconsistency exits 2. Supply `--trusted-key PUBLIC.pem` to recognize a test signer. Partial-parent masks deliberately cannot export whole-parent visual means.

Node visual tests use pinned Sharp/libvips, Python uses Pillow and the browser uses native codecs. Integer features are shared, but held-out decoder/resampler agreement is not inferred from a small fixture set. The external attack harness, photographic datasets and research claims in the supplied roadmap still require separate reproduction.

## Native-browser / Python differential report

```sh
python3 bench/browser-differential.py --count 1000
python3 -m http.server 4195 --bind 127.0.0.1
```

Open `http://127.0.0.1:4195/bench/browser-differential.html`, run the cross-check and download its per-case report. Then run:

```sh
python3 bench/browser-differential.py --check /path/to/guard-browser-differential.json
```

The checker requires the same corpus SHA-256, case order, verdicts and acceptance flags. It writes `results/browser-differential.json`. This exercises native browser codecs/WebCrypto on exact containers; visual-copy codec agreement is a separate experiment. Bundle fixtures and explicit-root CLI/API usage are documented in [TRUST_BUNDLES.md](TRUST_BUNDLES.md).

## Submission resize regression and visual-on/off scale

```sh
python3 scripts/make-area-vectors.py
npm test
python3 tests/test_vectors.py
.venv-c2pa/bin/python tests/c2pa_roundtrip.py
node bench/v2-scale.mjs
python3 bench/scale-python.py
python3 bench/visual-corpus.py --fetch
python3 bench/visual-corpus.py
node bench/visual-corpus.mjs
python3 bench/visual-corpus.py --check results/visual-corpus/node-report.json
```

Run the two scale scripts sequentially, without other benchmarks. They now emit ten rows each (five sizes × visual off/on); the Python script uses separate processes. Seal timings exclude input generation and the separately reported container encoding. Candidate transforms deliberately use Pillow during fixture creation; the verifiers themselves do not resize.

Serve localhost and run `bench/visual-corpus.html` in Chrome. Expand Per-case report and save its JSON as `results/visual-corpus/chrome-report.json`, then run `python3 bench/visual-corpus.py --check results/visual-corpus/chrome-report.json`. This checks case IDs, candidate hashes and verdict/acceptance flags. The photographic dataset is downloaded from r0k.us with TLS certificate checking, and kept under ignored data/. The generator's fixed signing seed is public TEST ONLY.

Tau is still nine, with BORDERLINE for worstError seven through eleven inclusive, exit seven and no positive consistency flag. Do not aggregate it with consistent results. Raw vectors at .5/.75/1/1.25/1.5× require exact bytes; encoded photographic candidates can still have decoder differences.

## V4 signer, recipient and accessibility QA

```sh
python3 scripts/make-signer-vectors.py
npm ci
npm test
python3 tests/test_vectors.py
npm run build
python3 scripts/make-trust-bundle-vectors.py
node scripts/v4-browser-qa.mjs
python3 -m http.server 4196 --bind 127.0.0.1 --directory /tmp/guard-v4-qa
```

The fixture generator must run before the QA script: `python3 scripts/make-trust-bundle-vectors.py` creates the ignored prerequisite. On a fresh clone without it, the QA script exits 1 and prints that exact command. The TEST ONLY viewer at localhost:4196 embeds only deterministic test trust and dev-only axe-core. Run its signer flow checks and accessibility audit, and inspect revoked.html separately. Never deploy these QA copies. Production CSP stays `connect-src 'none'` and production HTML does not include axe. `mobile.html` supplies Chromium iframe CSS widths for reflow checking; only these QA fixtures disable the app's frame guard. This is not evidence of a real phone, assistive-technology trial or physical browser zoom. The production frame guard remains intact.

Create empty real-world measurement CSVs with `python3 bench/realworld-templates.py`; it never fabricates rows or overwrites recorded trials. File carrier, watermark and TSA experiments remain pending until implemented and actually measured.
