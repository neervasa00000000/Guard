#!/usr/bin/env python3
"""Compare regenerated values with the locked MDPI manuscript numbers."""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "manuscript" / "expected_numbers.json"
VALUES = ROOT / "out" / "tables" / "values.csv"


def main():
    if not EXPECTED.is_file():
        print("FAIL\tmanuscript/expected_numbers.json is missing")
        return 1
    if not VALUES.is_file():
        print("FAIL\tout/tables/values.csv is missing; run scripts/regenerate_tables.py")
        return 1
    spec = json.loads(EXPECTED.read_text())
    got = {}
    for row in csv.DictReader(VALUES.open()):
        got[row["id"]] = float(row["value"])
    failed = 0
    passed = 0
    exploratory = 0
    for item in spec["numbers"]:
        status = item.get("status", "CHECK")
        label = f"{item['source']}\t{item['id']}"
        if status == "EXPLORATORY":
            exploratory += 1
            print(f"EXPLORATORY\t{label}\t{item.get('reason', '')}")
            continue
        if item["id"] not in got:
            failed += 1
            print(f"FAIL\t{label}\tmissing from out/tables/values.csv")
            continue
        value = got[item["id"]]
        rule = item.get("rule", "abs")
        expected = item.get("expected")
        tol = float(item.get("tol", 0))
        if rule == "lt":
            ok = value < expected
            detail = f"got {value:.6g}, expected < {expected}"
        else:
            ok = abs(value - expected) <= tol
            detail = f"got {value:.6g}, expected {expected} ± {tol}"
        if ok:
            passed += 1
            print(f"PASS\t{label}\t{detail}")
        else:
            failed += 1
            print(f"FAIL\t{label}\t{detail}")
    print(f"SUMMARY\tPASS {passed}\tFAIL {failed}\tEXPLORATORY {exploratory}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
