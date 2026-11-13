"""Reproduce the clean 16 px surname exact-box reference cells."""

import argparse
import csv
import gzip
import importlib.util
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np


def load_scorer(kit):
    path = kit / "v5.7-ieee/new_tests_posterior/scripts/phase_exact.py"
    spec = importlib.util.spec_from_file_location("phase_exact", path)
    phase = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(phase)
    return phase.scores


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kit", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = args.kit / "results/e1-full"
    sys.path.insert(0, str(root / "scripts"))
    import e1lib as E

    scores = load_scorer(args.kit)
    size, list_name, seed = 16, "surnames", 20261029
    d = E.get_dict(list_name)
    prior_bits = float(-(d["p"] * d["m"] * np.log2(d["p"])).sum())
    reference = {}
    with (root / "csv/e1_summary.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            if (row["dict"], row["size_px"], row["variant"], row["condition"], row["grid_px"]) == (
                list_name, str(size), "main", "clean", "1"
            ):
                reference[row["font"], row["attacker"]] = row

    a2_ref = defaultdict(list)
    path = args.kit / "v5.7-ieee/new_tests_posterior/csv/phase_cases.csv.gz"
    with gzip.open(path, "rt", newline="") as handle:
        for row in csv.DictReader(handle):
            if (row["dict"], row["size"], row["variant"], row["grid_px"]) == (
                list_name, str(size), "main", "1"
            ):
                a2_ref[row["font"]].append((float(row["hit10_lik"]), float(row["resid_lik"])))

    results = []
    for font_index, font in enumerate(E.FONTS):
        n = int(reference[font, "A1"]["n"])
        rng = np.random.default_rng([seed, list(E.DICTS).index(list_name), font_index, size])
        targets, strings = E.sample_targets(d, n, rng)
        pens = rng.integers(*E.PEN_X, n)
        rng.integers(*E.PEN_Y, n)
        geometry = E.geometry(list_name, font, size)
        by_attacker = defaultdict(list)
        for target, string, pen in zip(targets, strings, pens):
            box = geometry[target]
            vertical = np.all(geometry[:, [1, 3]] == box[[1, 3]], axis=1)
            matching_width = (geometry[:, 2] - geometry[:, 0]) == (box[2] - box[0])
            start = pen + box[0] - geometry[:, 0]
            for attacker, horizontal in (
                ("A1", start == pen),
                ("A2", (start >= E.PEN_X[0]) & (start < E.PEN_X[1])),
            ):
                likelihood = vertical & matching_width & horizontal
                h1, h10, _, entropy, truth_in = scores(
                    d, d["p"] * likelihood, target, len(string)
                )
                if not truth_in:
                    raise ValueError(f"Truth absent for {font} {attacker}")
                by_attacker[attacker].append((h1, h10, entropy))

        for attacker, rows in by_attacker.items():
            top1, top10, entropy = np.mean(rows, axis=0)
            bits = prior_bits - entropy
            row = reference[font, attacker]
            if attacker == "A1":
                ref_top10, ref_bits = float(row["top10"]), float(row["bits_leaked"])
                source = "e1_summary.csv"
            else:
                if len(a2_ref[font]) != n:
                    raise ValueError(f"Incomplete exact likelihood reference for {font}")
                ref_top10, ref_entropy = np.mean(a2_ref[font], axis=0)
                ref_bits = prior_bits - ref_entropy
                source = "phase_cases.csv.gz"
            top10_delta, bits_delta = top10 - ref_top10, bits - ref_bits
            passed = math.isclose(top10, ref_top10, abs_tol=1e-10) and math.isclose(
                bits, ref_bits, abs_tol=1e-10
            )
            results.append(dict(
                font=font, attacker=attacker, n=n, seed=seed, top1=top1,
                top10=top10, bits=bits, published_top10=ref_top10, published_bits=ref_bits,
                delta_top10=top10_delta, delta_bits=bits_delta, source=source, passed=passed,
            ))
            print(results[-1], flush=True)

    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    if not all(row["passed"] for row in results):
        raise SystemExit("Published surname sanity check failed")


if __name__ == "__main__":
    main()
