# TileSeal

**Versions.** The IEEE Access manuscript in preparation cites [commit f8f2558](https://github.com/neervasa00000000/Guard/commit/f8f2558a5f82bb99842781a0e3bc03fec39fd3c5), the [`paper-v5.7` pin](https://github.com/neervasa00000000/Guard/tree/paper-v5.7). The current [live demo](https://neervasa00000000.github.io/Guard/) adds the TileSeal interface and 128 px width-class padding.

[![MIT licence](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Verify and build](https://github.com/neervasa00000000/Guard/actions/workflows/check.yml/badge.svg?branch=main)](https://github.com/neervasa00000000/Guard/actions/workflows/check.yml)

TileSeal (repository: Guard) lets you black out parts of a picture, save a `.GRD`, and later check that the visible pixels still match the sealed file. Images and private keys stay in your browser. See the [privacy notice](PRIVACY.md).

1. **Choose a picture.** Use the [live demo](https://neervasa00000000.github.io/Guard/#seal), open [index.html](index.html) locally, or run `npm run dev` and visit `http://127.0.0.1:4195/`.
2. **Black out and seal.** Draw boxes, review the preview, and save the `.GRD`. The editor rounds outward to 16 px by default and pads widths in steps of 128 px. Padding reduces the clues a box's width gives about hidden text length. The editor also offers 32 and 64 px rounding. The Python CLI supports 8 px for compatible seals.
3. **Check the file.** Open it in [Check a file](https://neervasa00000000.github.io/Guard/#check). New files are self-signed. A successful check confirms that the visible pixels match the seal, while the signer's identity remains unverified. You can black out more areas on GRD2 and GRD3 without the signing key. **Download plain picture** saves a PNG without the proof. Keep the `.GRD` to check it again.

See the [browser test plan](TILESEAL.md), [format specification](GRD_SPEC.md), [security model](SECURITY_MODEL.md), [CLI guide](REDACTION.md), and [signer trust guide](SIGNERS.md). The project uses the [MIT licence](LICENSE). The [citation file](CITATION.cff) identifies the manuscript pin, and the [E1 checklist](research/e1/README.md) records the status of the research artifacts.

## Build and test

Use Node.js 22 and Python 3.13. Run from the repository root:

```sh
npm ci
python3 -m pip install -r requirements.txt
npm run build
npm test
python3 tests/test_vectors.py
python3 tests/test_padding.py
```

The build writes identical standalone files to `index.html` and `grd_viewer.html`. See [REPRODUCE.md](REPRODUCE.md) for additional verification commands and the [archive](docs/archive/) for historical reports.
