# Black Box Redaction

This folder holds the paper **What the Black Box Reveals: Measuring Redaction-Geometry Leakage and the Tile-Snapping Trade-off in Images** and TileSeal, the tool that seals an image, black out a rectangle on a tile grid, and checks the result. The printed paper is `paper_v6_1_ieeeaccess.pdf`.

## Install

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Reproduce

```sh
. .venv/bin/activate
bash scripts/reproduce.sh
```

The offline run verifies the clean summary against archived per-target scores and writes `out/tables` and `out/figures`. See [the E1 harness](research/e1/README.md) for the full render and input setup.

## Tests

```sh
.venv/bin/python -m pytest -q
```

## Website

The TileSeal page is `index.html`. Rebuild it after a change to `src/`, then open it:

```sh
node scripts/build.mjs
python3 -m http.server 4195 --bind 127.0.0.1
```

Open http://127.0.0.1:4195/. Images and keys stay in the browser.

## Use TileSeal

```sh
.venv/bin/python -m tileseal seal in.png --key key.pem --no-visual -o out.GRD
.venv/bin/python -m tileseal redact out.GRD --rect 8,8,20,12 --granularity 64 -o redacted.GRD
.venv/bin/python -m tileseal verify redacted.GRD
```

Create the key when you need it. Do not commit it.

## Citation

Neer Vasa. What the Black Box Reveals: Measuring Redaction-Geometry Leakage and the Tile-Snapping Trade-off in Images. DOI: PLACEHOLDER.

The same fields are in `CITATION.cff`.
