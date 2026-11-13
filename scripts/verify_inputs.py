#!/usr/bin/env python3
"""Check the shipped inputs before the tables are rebuilt. No downloads."""
import csv
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "research" / "e1" / "cases"
SUMS = CASES / "SHA256SUMS"
CENSUS = ROOT / "research" / "e1" / "data" / "surnames_head1000.csv"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    failed = False
    lines = [line.split() for line in SUMS.read_text().splitlines() if line.strip()]
    if len(lines) != 25:
        print(f"FAIL\tSHA256SUMS has {len(lines)} entries, expected 25")
        return 1
    records = 0
    for digest, name in lines:
        path = CASES / name
        if not path.is_file():
            print(f"FAIL\tmissing {name}")
            failed = True
            continue
        got = sha256(path)
        if got != digest:
            print(f"FAIL\t{name}\n  expected {digest}\n  got      {got}")
            failed = True
        else:
            print(f"PASS\t{name}")
        import gzip
        with gzip.open(path, "rt") as handle:
            records += max(sum(1 for _ in handle) - 1, 0)
    if records != 3408000:
        print(f"FAIL\tcase records {records}, expected 3408000")
        failed = True
    else:
        print("PASS\t3408000 case records")
    with CENSUS.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1000 or rows[0]["name"] != "SMITH":
        print(f"FAIL\tcensus head has {len(rows)} rows, first {rows[0]['name'] if rows else 'none'}")
        failed = True
    else:
        print("PASS\t1000 census surnames, file order, first SMITH")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
