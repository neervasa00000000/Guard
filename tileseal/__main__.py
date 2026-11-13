"""Run the existing TileSeal CLI. Example:

python -m tileseal seal in.png --key key.pem -o out.GRD
python -m tileseal redact out.GRD --rect x,y,w,h --granularity 64 -o redacted.GRD
python -m tileseal verify redacted.GRD
"""
import sys

from tileseal import grd


if __name__ == "__main__":
    sys.exit(grd.main())
