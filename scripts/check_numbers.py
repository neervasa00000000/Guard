#!/usr/bin/env python3
"""Compare regenerated values with the locked MDPI manuscript numbers."""
import csv
import json
import sys
from pathlib import Path
from v14_numbers import compare

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
    section=spec.get('v1_4',{})
    numeric_passed=0
    for source in section.get('sources',[]):
        count,errors=compare(ROOT,source,section.get('absolute_tolerance',1e-12))
        numeric_passed+=count;failed+=len(errors)
        print(f"V1_4\t{source['path']}\tPASS {count}\tFAIL {len(errors)}")
        for error in errors[:20]:print('FAIL\tV1_4\t'+error)
    if section:
        print(f"V1_4 SUMMARY\tPASS {numeric_passed}\tOVERALL FAIL {failed}\t{section['status']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
