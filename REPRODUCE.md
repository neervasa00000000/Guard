# Reproducing Guard checks

Run commands from this repository. Node 22 or later is needed for the JSON imports and native compression streams. Install `npm ci` and the Python packages in `requirements.txt` in your chosen environment. The optional C2PA check additionally needs `requirements-c2pa.txt` (`c2pa-python==0.38.1`). This checkout already has a `.venv-c2pa` environment.

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
