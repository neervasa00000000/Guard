"""Check this manuscript's A2 column against research/e1/review4/pooled.csv.

The manuscript table is the one scripts/regenerate_tables.py writes. This
script does not read paper_v6_1_ieeeaccess.pdf and does not replay the IEEE
number-audit transcript.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from regenerate_tables import CLEAN, POOLED, a2_from_pooled

MANUSCRIPT = (
    ("surnames", 8, 17.6, 2.63),
    ("words", 16, 34.6, 1.97),
)


def main():
    failed = False

    def report(status, detail):
        nonlocal failed
        if status == "FAIL":
            failed = True
        print(f"{status}\t{detail}")

    frame = a2_from_pooled(pd.read_csv(CLEAN))
    pooled = pd.read_csv(POOLED)
    for name, grid, top10, bits in MANUSCRIPT:
        row = frame.query("dict == @name and grid_px == @grid and attacker == 'A2'").iloc[0]
        got_top = round(row.top10 * 100, 1)
        got_bits = round(row.bits_leaked, 2)
        if got_top == top10 and got_bits == bits:
            report("OK", f"manuscript {name} {grid} px A2 is {got_top}/{got_bits} from pooled.csv")
        else:
            report("FAIL", f"manuscript {name} {grid} px A2 is {got_top}/{got_bits}, expected {top10}/{bits}")
    source = pooled[(pooled.model == "LAYOUT-BOX") & (pooled.attacker == "A2") & (pooled.size_px.astype(str) == "all")]
    if source.empty:
        report("FAIL", "pooled.csv has no size-pooled LAYOUT-BOX A2 rows")
    else:
        report("OK", "A2 column source is research/e1/review4/pooled.csv, not the IEEE text")
    print("SUMMARY " + ("FAIL" if failed else "OK"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
