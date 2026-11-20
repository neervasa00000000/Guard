#!/usr/bin/env python3
"""Coordinate-error leakage for start-aligned padding and the fixed field.

No images are rendered. The script reads retained layout bounds
(geom_surnames_<font>_<size>.pkl) for the 50,000 alphabetic Census surnames,
six fonts and 12/16/24 px. Each bound is Pillow getbbox at anchor ls. The
padded span is the paper's start-aligned span: the layout right edge plus one
pixel, minus the shared text start x_L.

The redactor's start estimate is x_L + e. The released class is the usual
ceiling of (span - e) / C. The attacker knows the true template x_L, so the
left edge reveals e, and knows that e is uniform on the stated set. Reported
leakage is the expectation of that conditional class leakage. One condition
uses e in {-4..+4} and another uses e in {-2..+2}.

Full-line height does not depend on which surname is hidden. A baseline shift
moves both line edges together, and a line-bound error of +/-2 px changes only
that shared height, so neither splits the candidate list. Those rows match the
zero-error rows. Class width is mis-set to C+/-8 with equal probability. The
attacker knows the true C and that distribution and sees only the released
width. The fixed field has one shared width, so the same coordinate errors do
not separate surnames.
"""
import argparse
import csv
import hashlib
import math
import sys
from itertools import product
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research/e1"))
import e1lib as E
import policies as P

OUT = ROOT / "research/e1/data/v1_4"
TAIL = ROOT / "research/e1/data/v1_3/tail_summary.csv"
WIDTHS = (128, 192, 256)
CHECK_WIDTHS = (64, 96, 128, 160, 192, 256)
START_SETS = {
    "start_uniform_-4_4": tuple(range(-4, 5)),
    "start_uniform_-2_2": tuple(range(-2, 3)),
}
FIELDS = (
    "font", "size_px", "policy", "width_px", "condition", "n_cells",
    "mean_bits", "max_pointwise_bits", "min_entropy_bits", "prior_pct_lt100",
    "mean_bits_e0", "max_pointwise_bits_e0", "min_entropy_bits_e0", "prior_pct_lt100_e0",
)


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def spans_for(bounds):
    bounds = np.asarray(bounds)
    if bounds.ndim != 2 or bounds.shape[1] != 4 or bounds.dtype.kind not in "iu":
        raise ValueError(f"Unexpected layout bounds {getattr(bounds, 'shape', None)} {getattr(bounds, 'dtype', None)}")
    left = bounds[:, 0].astype(np.int64)
    right = bounds[:, 2].astype(np.int64)
    return right + 1 - (int(left.min()) - 1)


def compress(spans, counts):
    order = np.argsort(spans, kind="mergesort")
    spans = np.asarray(spans, dtype=np.int64)[order]
    counts = np.asarray(counts, dtype=np.int64)[order]
    change = np.flatnonzero(np.diff(spans)) + 1
    starts = np.concatenate((np.array([0], dtype=np.int64), change))
    stops = np.concatenate((change, np.array([spans.size], dtype=np.int64)))
    return dict(
        span=spans[starts],
        count=np.add.reduceat(counts, starts),
        names=(stops - starts).astype(np.int64),
        max_count=np.maximum.reduceat(counts, starts),
    )


def classes_of(span, shift, width):
    return P.ceil_multiple(np.asarray(span, dtype=np.int64) - int(shift), int(width)) // int(width)


def reduce_keys(count, names, max_count, keys):
    order = np.argsort(np.asarray(keys), kind="mergesort")
    keys = np.asarray(keys)[order]
    count = np.asarray(count)[order]
    names = np.asarray(names)[order]
    max_count = np.asarray(max_count)[order]
    change = np.flatnonzero(np.diff(keys)) + 1
    starts = np.concatenate((np.array([0], dtype=np.int64), change))
    return (
        np.add.reduceat(count, starts),
        np.add.reduceat(names, starts),
        np.maximum.reduceat(max_count, starts),
    )


def from_classes(class_count, class_names, class_max, total, peak):
    mean = 0.0
    worst = 0.0
    small = 0
    success_count = 0
    for count, names, max_count in zip(class_count, class_names, class_max):
        count = int(count)
        mass = count / total
        pointwise = 0.0 if count == total else -math.log2(mass)
        mean += mass * pointwise
        worst = max(worst, pointwise)
        success_count += int(max_count)
        if int(names) < 100:
            small += count
    return dict(
        mean_bits=mean,
        max_pointwise_bits=worst,
        min_entropy_bits=math.log2(success_count / peak),
        prior_pct_lt100=100.0 * small / total,
        success=success_count / total,
    )


def partition(group, shift, width, total, peak):
    keys = classes_of(group["span"], shift, width)
    return from_classes(*reduce_keys(group["count"], group["names"], group["max_count"], keys), total, peak)


def average_shifts(group, shifts, width, total, peak):
    rows = [partition(group, shift, width, total, peak) for shift in shifts]
    success = math.fsum(row["success"] for row in rows) / len(rows)
    return dict(
        mean_bits=math.fsum(row["mean_bits"] for row in rows) / len(rows),
        max_pointwise_bits=max(row["max_pointwise_bits"] for row in rows),
        min_entropy_bits=math.log2(success * total / peak),
        prior_pct_lt100=math.fsum(row["prior_pct_lt100"] for row in rows) / len(rows),
        success=success,
    )


def class_width_channel(group, width, total, peak):
    """C is replaced by C-8 or C+8 with equal probability. The attacker sees the width."""
    released = []
    ambiguous = False
    for span in group["span"]:
        widths = [int(P.ceil_multiple(np.int64(span), width + delta)) for delta in (-8, 8)]
        released.append(widths)
        ambiguous = ambiguous or widths[0] != widths[1]
    if not ambiguous:
        keys = [widths[0] for widths in released]
        return from_classes(*reduce_keys(group["count"], group["names"], group["max_count"], keys), total, peak)
    buckets = {}
    residual = 0.0
    emissions = []
    for widths, count, names, max_count in zip(released, group["count"], group["names"], group["max_count"]):
        mass = int(count) / total
        if widths[0] == widths[1]:
            choices = ((widths[0], 1.0),)
        else:
            choices = ((widths[0], 0.5), (widths[1], 0.5))
            residual += mass
        emissions.append(choices)
        for observed, prob in choices:
            probability, name_count, best = buckets.setdefault(observed, [0.0, 0, 0.0])
            buckets[observed] = [
                probability + mass * prob,
                name_count + int(names),
                max(best, (int(max_count) / total) * prob),
            ]
    entropy = -math.fsum(probability * math.log2(probability) for probability, _, _ in buckets.values())
    worst = 0.0
    for choices in emissions:
        for observed, prob in choices:
            worst = max(worst, math.log2(prob / buckets[observed][0]))
    success = math.fsum(best for _, _, best in buckets.values())
    small = math.fsum(probability for probability, names, _ in buckets.values() if names < 100)
    mean_bits = entropy - residual
    if abs(mean_bits) < 1e-12:
        mean_bits = 0.0
    if abs(worst) < 1e-12:
        worst = 0.0
    return dict(
        mean_bits=mean_bits,
        max_pointwise_bits=worst,
        min_entropy_bits=math.log2(success * total / peak),
        prior_pct_lt100=100.0 * small,
        success=success,
    )


def blank():
    return dict(mean_bits=0.0, max_pointwise_bits=0.0, min_entropy_bits=0.0, prior_pct_lt100=0.0, success=0.0)


def cell_conditions(group, total, peak):
    """Return (policy, width, condition) -> metrics, including the zero-error reference."""
    out = {}
    for width in WIDTHS:
        base = partition(group, 0, width, total, peak)
        out[("start-aligned", width, "e0")] = base
        for name, shifts in START_SETS.items():
            out[("start-aligned", width, name)] = average_shifts(group, shifts, width, total, peak)
        # Full-line height is one pair of edges for every surname. These errors
        # do not change the width class and do not depend on the hidden surname.
        out[("start-aligned", width, "baseline_pm2")] = base
        out[("start-aligned", width, "line_bounds_pm2")] = base
        out[("start-aligned", width, "class_width_pm8")] = class_width_channel(group, width, total, peak)
    field = blank()
    field["success"] = peak / total
    for condition in ("e0", *START_SETS, "baseline_pm2", "line_bounds_pm2"):
        out[("fixed-field", 0, condition)] = field
    return out


def check_widths(group, total, peak):
    return {width: partition(group, 0, width, total, peak) for width in CHECK_WIDTHS}


def pool_metrics(rows, total, peak):
    success = math.fsum(row["success"] for row in rows) / len(rows)
    return dict(
        mean_bits=math.fsum(row["mean_bits"] for row in rows) / len(rows),
        max_pointwise_bits=max(row["max_pointwise_bits"] for row in rows),
        min_entropy_bits=0.0 if success == 0 else math.log2(success * total / peak),
        prior_pct_lt100=math.fsum(row["prior_pct_lt100"] for row in rows) / len(rows),
        success=success,
    )


def as_row(font, size, policy, width, condition, metrics, reference, n_cells):
    return dict(
        font=font, size_px=size, policy=policy, width_px=width, condition=condition, n_cells=n_cells,
        mean_bits=metrics["mean_bits"], max_pointwise_bits=metrics["max_pointwise_bits"],
        min_entropy_bits=metrics["min_entropy_bits"], prior_pct_lt100=metrics["prior_pct_lt100"],
        mean_bits_e0=reference["mean_bits"], max_pointwise_bits_e0=reference["max_pointwise_bits"],
        min_entropy_bits_e0=reference["min_entropy_bits"], prior_pct_lt100_e0=reference["prior_pct_lt100"],
    )


def load_tail():
    with TAIL.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    index = {}
    for row in rows:
        if row["font"] == "pooled":
            continue
        index[(row["font"], int(row["size_px"]), row["policy"], int(row["width_px"]))] = row
    return index


def assert_tail(font, size, checks, total, tail):
    for width, metrics in checks.items():
        recorded = tail[(font, size, "start-aligned", width)]
        for key, column in (
            ("mean_bits", "mean_bits"),
            ("max_pointwise_bits", "max_pointwise_bits"),
            ("min_entropy_bits", "min_entropy_bits"),
            ("prior_pct_lt100", "prior_pct_lt100"),
        ):
            got = metrics[key]
            expect = float(recorded[column])
            if abs(got - expect) > 1e-9:
                raise SystemExit(f"Zero-error mismatch {font} {size} C={width} {column}: {got} != {expect}")
    recorded = tail[(font, size, "fixed-field", 0)]
    for column in ("mean_bits", "max_pointwise_bits", "min_entropy_bits", "prior_pct_lt100"):
        if abs(float(recorded[column])) > 1e-12:
            raise SystemExit(f"Fixed field is not one class in the tail file: {font} {size}")
    if total <= 0:
        raise SystemExit("Empty cohort")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry", type=Path, required=True, help="Directory of geom_surnames_<font>_<size>.pkl")
    args = parser.parse_args()
    if not E.CENSUS.is_file() or digest(E.CENSUS) != E.FULL_CENSUS_SHA:
        parser.error("E1_CENSUS must point to the hash-verified full Census CSV.")
    names, counts = E.census(50000)
    counts = np.asarray(counts, dtype=np.int64)
    if len(names) != 50000 or len(set(names)) != 50000:
        raise SystemExit("Unexpected Census cohort")
    total = int(counts.sum())
    peak = int(counts.max())
    tail = load_tail()
    cells = {}
    for font, size in product(E.FONTS, E.SIZES):
        path = args.geometry / f"geom_surnames_{font}_{size}.pkl"
        bounds = np.load(path, allow_pickle=True)
        if len(bounds) != len(names):
            raise SystemExit(f"{path} has {len(bounds)} rows, expected {len(names)}")
        group = compress(spans_for(bounds), counts)
        checks = check_widths(group, total, peak)
        conditions = cell_conditions(group, total, peak)
        assert_tail(font, size, checks, total, tail)
        cells[(font, size)] = conditions
        print(f"checked {font} {size}", flush=True)
    rows = []
    keys = list(next(iter(cells.values())))
    for font, size in product(E.FONTS, E.SIZES):
        conditions = cells[(font, size)]
        for policy, width, condition in keys:
            metrics = conditions[(policy, width, condition)]
            reference = conditions[(policy, width, "e0")]
            rows.append(as_row(font, size, policy, width, condition, metrics, reference, 1))
    for size in (*E.SIZES, "all"):
        members = [cells[key] for key in cells if size == "all" or key[1] == size]
        for policy, width, condition in keys:
            metrics = pool_metrics([item[(policy, width, condition)] for item in members], total, peak)
            reference = pool_metrics([item[(policy, width, "e0")] for item in members], total, peak)
            rows.append(as_row("pooled", size, policy, width, condition, metrics, reference, len(members)))
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in FIELDS})
    print(f"Wrote {len(rows)} rows to {OUT / 'summary.csv'}")


if __name__ == "__main__":
    main()
