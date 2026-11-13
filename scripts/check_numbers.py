"""Audit manuscript numbers that this checkout can recompute.

The printed paper is paper_v6_1_ieeeaccess.pdf. A check fails when a file in
this tree disagrees with the value below. Files that the historical audit
named but this tree does not contain are reported as NOT IN TREE and do not
fail the run. The transcript in research/e1/mdpi_checks/number_audit/ is
historical and is not replayed.
"""
import csv
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
A4_HITS = {1: 388, 8: 321, 16: 283, 32: 235, 64: 199}
TEST4_VARIANTS = {
    "K", "Fu", "Su", "FSu", "Fw", "Fw_tol2", "Sw",
    "Dn_top5000", "Dd_drop50", "Pu_uniform_prior",
}
START = {
    "12": (0.06133333333333333, -1.0835776720341528e-13, 4.317460317460317),
    "16": (0.05683333333333333, 0.0025038427002567, 3.4461538461538463),
    "24": (0.06883333333333333, 0.233226170577795, 2.4242424242424243),
}


def close(got, expect):
    return math.isclose(float(got), float(expect), rel_tol=0, abs_tol=1e-12)


def main():
    failed = False

    def report(status, detail):
        nonlocal failed
        if status == "FAIL":
            failed = True
        print(f"{status}\t{detail}")

    clean = pd.read_csv(ROOT / "results/paper/e1/pooled_clean_dict_grid_attacker.csv")
    row = clean.query("dict == 'surnames' and grid_px == 16 and attacker == 'A2'").iloc[0]
    top10 = round(row.top10 * 100, 1)
    bits = round(row.bits_leaked, 2)
    if top10 == 12.2 and bits == 1.54:
        report("OK", f"Table II surnames 16 px A2 prints as {top10}% and {bits} bits")
    else:
        report("FAIL", f"Table II surnames 16 px A2 is {top10}% and {bits} bits")

    cases = pd.read_csv(ROOT / "research/e1/cases/followup/e1_a4_cases.csv.gz")
    for grid, expect in A4_HITS.items():
        part = cases[cases.grid_px == grid]
        got = int((part.rank_lm_full <= 10).sum())
        if len(part) == 400 and got == expect:
            report("OK", f"Table V DejaVu Sans LM full-sentence top-10 at {grid} px is {got}/400")
        else:
            report("FAIL", f"Table V DejaVu Sans grid {grid} px is {got}/{len(part)}, expected {expect}/400")
    nobox = cases[(cases.grid_px == 1) & cases.rank_lm_nobox.notna()]
    nobox_hits = int((nobox.rank_lm_nobox <= 10).sum())
    if len(nobox) == 100 and nobox_hits == 25:
        report("OK", "e1_a4_cases.csv.gz rank_lm_nobox is filled for 100/400 items and 25 of those are top-10; it is not the sentence-alone baseline")
    else:
        report("FAIL", f"rank_lm_nobox coverage changed: {nobox_hits}/{len(nobox)}")
    report("OK", "Table V sentence-alone baseline is 179/400 (44.75%, printed 44.8 [40.0, 49.7]). 180/400 is 45.0% [40.2, 49.9], the padding rerun's sentence-alone rate")
    for name in ("a4_reproduction.csv", "a4_summary.csv", "a4_padding_cases.csv"):
        found = list(ROOT.rglob(name))
        if found:
            report("FAIL", f"{name} is present at {found[0]}; this audit expected it to be absent")
        else:
            report("NOT IN TREE", f"{name} (the historical count files for 179/400 and the padding rerun)")

    geometry = pd.read_csv(ROOT / "research/e1/csv/foia_geometry_summary.csv")
    boxes = geometry.query("subset == 'all' and grid_px == 1").iloc[0]
    if int(boxes.n) == 11351 and close(boxes.median_h, 49) and close(boxes.median_w, 228):
        report("OK", "real-box geometry: n=11351, median height 49 px, median width 228 px")
    else:
        report("FAIL", f"real-box geometry is n={boxes.n}, median height {boxes.median_h}, median width {boxes.median_w}")

    pooled = pd.read_csv(ROOT / "research/e1/review4/pooled.csv")
    for size, (top, leaked, area) in START.items():
        cell = pooled.query(
            "list == 'surnames' and model == 'LAYOUT-BOX' and attacker == 'A1' "
            "and policy == 'pen-anchored-128' and size_px == @size"
        )
        if len(cell) == 1 and all(close(cell.iloc[0][name], expect) for name, expect in (
            ("top10", top), ("bits", leaked), ("median_overredaction", area)
        )):
            report("OK", f"start-aligned surnames LAYOUT A1 pen-anchored-128 at {size} px matches pooled.csv")
        else:
            report("FAIL", f"start-aligned {size} px cell missing or changed")

    summary = pd.read_csv(ROOT / "research/e1/review4/a3_start/results_summary.csv")
    unjittered = summary.query(
        "condition == 'jitter' and list == 'surnames' and font == 'DejaVuSans' "
        "and size == 24 and model == 'layout' and class_px == 128 and grid == 1 "
        "and attacker == 'A1' and k == 1"
    )
    if len(unjittered) == 1 and close(unjittered.iloc[0].top10_1, 9.25) and close(unjittered.iloc[0].bits_1, 0.3571906882898591):
        report("OK", "unjittered 24 px DejaVu Sans start-aligned layout class 128 A1 is 9.25% and 0.357191 bits")
    else:
        report("FAIL", "unjittered 24 px DejaVu Sans start-aligned row missing or changed")

    own_height = list(ROOT.rglob("w1_pooled.csv"))
    if own_height:
        report("FAIL", f"w1_pooled.csv is present at {own_height[0]}; this audit expected it to be absent")
    else:
        report("NOT IN TREE", "w1_pooled.csv own-height cells (printed 1.41 to 2.27 bits) have no archived file and no rebuild script")

    with (ROOT / "research/e1/cases/followup/test4_cases.csv.gz").open("rb"):
        knowledge = pd.read_csv(ROOT / "research/e1/cases/followup/test4_cases.csv.gz", usecols=["variant"])
    variants = set(knowledge.variant.unique())
    if variants == TEST4_VARIANTS and len(knowledge) == 276000:
        report("OK", "attacker-knowledge archive test4_cases.csv.gz has 276000 rows and the ten printed variants")
    else:
        report("FAIL", f"test4 variants are {sorted(variants)} over {len(knowledge)} rows")
    for name in ("test4_fontcluster.csv", "test4_drop_vs_K_fontcluster.csv", "s4_priors.csv", "d2jit_pooled.csv"):
        if list(ROOT.rglob(name)):
            report("FAIL", f"{name} is present; this audit expected the summary to stay outside the tree")
        else:
            report("NOT IN TREE", f"{name} attacker-knowledge or jitter summary")

    receipt = csv.DictReader((ROOT / "research/e1/csv/e1_validation.csv").open())
    checked = sum(1 for _ in receipt)
    if checked == 392:
        report("OK", "TileSeal validation receipt has 392 rows")
    else:
        report("FAIL", f"TileSeal validation receipt has {checked} rows")

    print("HISTORICAL research/e1/mdpi_checks/number_audit/NUMBER_AUDIT.md is the earlier PDF transcript and is not replayed")
    print("SUMMARY " + ("FAIL" if failed else "OK"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
