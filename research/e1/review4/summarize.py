"""Summarize normalized, target-level clean sweep output by cell and font."""

import argparse
from collections import defaultdict
import csv
from itertools import combinations
from pathlib import Path

import numpy as np

from font_stats import METRICS, font_draws, summary
from geometry import POLICIES


KEY = ("list", "size_px", "policy", "attacker", "model")
TARGET_FIELDS = ("top1", "top10", "bits", "overredaction")
PADDING = ("ink-anchored-128", "pen-anchored-128")


def write_csv(path, rows, fields):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def process(source, output, seed):
    by_cell = defaultdict(lambda: defaultdict(dict))
    with source.open(newline="") as handle:
        for row in csv.DictReader(handle):
            cell = tuple(row[field] for field in KEY)
            targets = by_cell[cell][row["font"]]
            target_id = row["target_id"]
            if target_id in targets:
                raise ValueError(f"Duplicate target {target_id!r} in {cell}, {row['font']}")
            targets[target_id] = [float(row[field]) for field in TARGET_FIELDS]

    if not by_cell:
        raise ValueError("No target rows")
    fonts = sorted(set().union(*(set(font_rows) for font_rows in by_cell.values())))
    if len(fonts) != 6:
        raise ValueError(f"Expected six fonts, got {fonts}")
    draws = font_draws(fonts, seed)
    points, pooled, paired = {}, {}, []
    for cell, font_rows in sorted(by_cell.items()):
        if set(font_rows) != set(fonts):
            raise ValueError(f"Incomplete font coverage for {cell}")
        values = [np.asarray(list(font_rows[font].values())) for font in fonts]
        if any(not np.isfinite(rows).all() for rows in values):
            raise ValueError(f"Nonfinite metric for {cell}")
        pooled[cell] = dict(zip(KEY, cell)) | summary(values, draws)
        for font, rows in zip(fonts, values):
            metrics = np.r_[rows[:, :3].mean(axis=0), np.median(rows[:, 3])]
            points[cell, font] = dict(zip(KEY, cell)) | {"font": font, "n": len(rows)}
            points[cell, font].update(zip(METRICS, metrics))

    for (cell, font), point in points.items():
        if point["policy"] not in PADDING:
            continue
        grid = (*cell[:2], "square-64", *cell[3:])
        if by_cell[cell][font].keys() != by_cell.get(grid, {}).get(font, {}).keys():
            raise ValueError(f"Unpaired padding and square-64 targets for {cell}, {font}")
        baseline = points[grid, font]
        paired.append({key: point[key] for key in (*KEY, "font", "n")} | {
            f"delta_{metric}": point[metric] - baseline[metric] for metric in METRICS
        })

    grouped = defaultdict(dict)
    for cell, row in pooled.items():
        list_name, size, policy, attacker, model = cell
        grouped[list_name, size, attacker, model][policy] = row
    matches = []
    for (list_name, size, attacker, model), rows in grouped.items():
        for policy_a, policy_b in combinations([p.label for p in POLICIES if p.label in rows], 2):
            a, b = rows[policy_a], rows[policy_b]
            area_a, area_b = a["median_overredaction"], b["median_overredaction"]
            # Symmetric criterion: the larger overhead is at most 110% of the smaller.
            if max(area_a, area_b) > 1.10 * min(area_a, area_b):
                continue
            matches.append({
                "list": list_name, "size_px": size, "attacker": attacker, "model": model,
                "policy_a": policy_a, "policy_b": policy_b,
                "overredaction_a": area_a, "overredaction_b": area_b,
                **{f"delta_{m}_b_minus_a": b[m] - a[m] for m in METRICS[:3]},
            })
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "per_font.csv", points.values(), [*KEY, "font", "n", *METRICS])
    write_csv(output / "pooled.csv", pooled.values(), list(next(iter(pooled.values()))))
    write_csv(output / "padding_minus_64.csv", paired,
              [*KEY, "font", "n", *(f"delta_{m}" for m in METRICS)])
    write_csv(output / "matched_overredaction.csv", matches, [
        "list", "size_px", "attacker", "model", "policy_a", "policy_b",
        "overredaction_a", "overredaction_b", *(f"delta_{m}_b_minus_a" for m in METRICS[:3]),
    ])
    print(f"Summarized {len(points)} font cells, {len(pooled)} pooled cells, "
          f"{len(paired)} paired rows and {len(matches)} matched comparisons")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--bootstrap-seed", type=int, required=True)
    args = parser.parse_args()
    process(args.source, args.output, args.bootstrap_seed)
