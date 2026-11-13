"""Compare regenerated tables with the number audit. Paper rows that were not
recomputed stay NOT FOUND. This does not invent a match.
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "research/e1/mdpi_checks/number_audit/number_audit.csv"


def main():
    if not AUDIT.exists():
        print("PAPER VALUES NOT FOUND")
        return 0
    rows = list(csv.DictReader(AUDIT.open()))
    if not rows:
        print("PAPER VALUES NOT FOUND")
        return 0
    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
        print(f"{row['status']}\t{row['location']}\t{row['context']}\tprinted {row['printed']}\tcomputed {row['computed']}")
    print("SUMMARY " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
