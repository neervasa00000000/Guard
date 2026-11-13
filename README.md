# Black Box Redaction

This folder holds the paper **What the Black Box Reveals: Measuring Redaction-Geometry Leakage and the Tile-Snapping Trade-off in Images** and TileSeal, the tool that seals an image, black out a rectangle on a tile grid, and checks the result. The printed paper is `paper_v6_1_ieeeaccess.pdf`.

## Install

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Reproduce

```sh
bash scripts/reproduce.sh
```

That downloads the public inputs, checks their SHA-256 values, and writes `out/tables` and `out/figures` from `results/`.

## Tests

```sh
.venv/bin/python -m pytest -q
```

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
