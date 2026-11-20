"""Recompute the published summaries from the CSVs.

This file does not import the scorer. A mismatch exits non-zero.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
RESULTS = HERE / "results"
SEED = 20261116
BOOTSTRAP = 2000


def rng_for(key):
    digest = hashlib.sha256(f"{SEED}:{key}".encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "little"))


def read_csv(path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def cluster_mean_ci(names, values, rng):
    values = np.asarray(values, dtype=np.float64)
    keys = np.asarray(names)
    unique = sorted(set(keys.tolist()))
    groups = {key: values[keys == key] for key in unique}
    stats = np.empty(BOOTSTRAP)
    for i in range(BOOTSTRAP):
        take = rng.choice(len(unique), size=len(unique), replace=True)
        stats[i] = np.concatenate([groups[unique[j]] for j in take]).mean()
    return float(values.mean()), float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))


def expected_hit(log_prior, index, k):
    truth = float(log_prior[index])
    greater = int(np.count_nonzero(log_prior > truth + 1e-8))
    equal = int(np.count_nonzero(np.abs(log_prior - truth) <= 1e-8))
    return float(min(1.0, max(0.0, (k - greater) / equal)))


def main():
    attacks = read_csv(RESULTS / "attacker_results.csv")
    stats = json.loads((RESULTS / "statistics.json").read_text())
    failures = []

    def check(name, ok, detail):
        if not ok:
            failures.append(f"{name}: {detail}")

    check("not a pilot", stats.get("pilot") is False, stats.get("pilot"))
    check("1200 documents", stats["n_documents"] == 1200, stats["n_documents"])
    check("no sanitizer failures", stats["n_failures"] == 0, stats["n_failures"])

    grouped = defaultdict(list)
    for row in attacks:
        grouped[(row["attacker"], row["policy"])].append(row)
        hit1 = float(row["hit1"])
        hit10 = float(row["hit10"])
        check("hit range", 0 <= hit1 <= 1 and 0 <= hit10 <= 1, row["name"])
        entropy = float(row["entropy_reduction"])
        check("entropy non-negative", entropy >= -1e-9, entropy)
        empty = row["empty_set"] in {"True", "true", "1"}
        truth = row["truth_in_set"] in {"True", "true", "1"}
        if empty:
            check("empty set has no bits", abs(entropy) <= 1e-9, entropy)
        elif not truth:
            check("wrong set scores a miss", hit1 == 0 and hit10 == 0, (hit1, hit10, row["policy"]))
        if row["policy"] == "field":
            check("field feasible is the whole list", int(float(row["feasible"])) == 1000, row["feasible"])
            check("field top10 equals no-box", abs(hit10 - float(row["nobox_hit10"])) <= 1e-9, row["name"])
            check("field bits are zero", abs(entropy) <= 1e-9, entropy)

    # No-box hits recomputed from the census file.
    surname_path = HERE.parents[1] / "research" / "e1" / "data" / "surnames_head1000.csv"
    table = read_csv(surname_path)
    counts = np.array([float(row["count"]) for row in table])
    prior = counts / counts.sum()
    log_prior = np.log(prior)
    index = {row["name"]: i for i, row in enumerate(table)}
    seen = {}
    for row in attacks:
        if row["name"] in seen:
            continue
        i = index[row["name"]]
        seen[row["name"]] = (
            expected_hit(log_prior, i, 1),
            expected_hit(log_prior, i, 10),
        )
        check(
            "stored no-box",
            abs(seen[row["name"]][1] - float(row["nobox_hit10"])) <= 1e-9,
            (row["name"], seen[row["name"]][1], row["nobox_hit10"]),
        )

    published = {(row["attacker"], row["policy"]): row for row in stats["attacks"]}
    for key, rows in sorted(grouped.items()):
        point, low, high = cluster_mean_ci(
            [row["name"] for row in rows],
            [float(row["hit10"]) for row in rows],
            rng_for(f"top10:{key[0]}:{key[1]}"),
        )
        got = published[key]
        check("top10 point", abs(point - float(got["top10"])) <= 1e-8, (key, point, got["top10"]))
        check("top10 ci", abs(low - float(got["top10_ci_low"])) <= 1e-8 and abs(high - float(got["top10_ci_high"])) <= 1e-8, key)
        check("row count", int(got["n"]) == len(rows), key)

    documents = read_csv(RESULTS / "documents.csv")
    edge = np.array([float(row["edge_error_px"]) for row in documents])
    check("glyph edges match catalog", float(np.median(edge)) < 0.05 and float(edge.max()) < 0.5, (float(np.median(edge)), float(edge.max())))
    check("document rows", len(documents) == 1200, len(documents))

    report = {
        "n_checks_failed": len(failures),
        "failures": failures[:30],
        "n_attack_rows": len(attacks),
        "n_documents": len(documents),
        "median_edge_error_px": float(np.median(edge)),
        "max_edge_error_px": float(edge.max()),
    }
    (RESULTS / "verification.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
