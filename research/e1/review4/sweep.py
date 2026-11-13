"""Replay the clean study targets under the review policies."""

import argparse
import csv
from itertools import product
from multiprocessing import Pool
from pathlib import Path
import sys
import time

import numpy as np

from geometry import Geometry, POLICIES, text_bounds
from grouped_scores import GroupedScores

SEED = 20261029
MODELS = ("LAYOUT-BOX", "PIXEL-INK")
ATTACKERS = ("A1", "A2")
E = None
OUTPUT = None


def init(kit, output):
    global E, OUTPUT
    sys.path.insert(0, str(kit / "results/e1-full/scripts"))
    import e1lib

    E, OUTPUT = e1lib, output


def one_unit(unit):
    name, font, size, n = unit
    started = time.monotonic()
    path = OUTPUT / f"{name}_{font}_{size}.npz"
    if path.is_file():
        return
    dictionary = E.get_dict(name)
    rng = np.random.default_rng([SEED, list(E.DICTS).index(name), list(E.FONTS).index(font), size])
    ids, strings = E.sample_targets(dictionary, n, rng)
    pens = rng.integers(*E.PEN_X, n)
    baselines = rng.integers(*E.PEN_Y, n)
    ft = E.font(font, size)
    asc, desc = ft.getmetrics()
    results = {}
    for model in MODELS:
        bounds = (E.geometry(name, font, size) if model == "LAYOUT-BOX" else
                  np.array([text_bounds(ft, s, model) for s in dictionary["strings"]]))
        geom = Geometry(bounds, -asc, desc)
        # Render sampled digits with their actual middle digits. The published
        # candidate space represents each length/first/last class with zeroes.
        target_bounds = (np.array([text_bounds(ft, s, model) for s in strings])
                         if name == "digits" else bounds[ids])
        actual = Geometry(target_bounds, -asc, desc)
        actual.fixed_left = geom.fixed_left
        actual.line_top, actual.line_bottom = geom.line_top, geom.line_bottom
        a, b = target_bounds[:, :2].T, target_bounds[:, 2:].T
        area = np.prod(b - a + 2, axis=0)
        for policy in POLICIES:
            left, right = geom.horizontal(policy)
            full_line = policy.kind in {"ink-anchored", "pen-anchored", "width-grid"}
            keys = np.column_stack((left, right)) if full_line else np.column_stack(
                (left, right, geom.top, geom.bottom)
            )
            scorer = GroupedScores(dictionary, keys)
            left, right = left[scorer.representatives], right[scorer.representatives]
            target_left, target_right = actual.horizontal(policy)
            xs0, xs1 = pens + target_left, pens + target_right
            grid = policy.width if policy.kind in {"square", "width-grid"} else 1
            xs0, xs1 = E.snap(xs0, xs1, grid)
            tops = np.empty(n, dtype=int)
            bottoms = np.empty(n, dtype=int)
            vertical = {}
            masks = {}
            phase = baselines % (grid if policy.kind == "square" else 1)
            shift = baselines - phase
            for y in np.unique(phase):
                mask = phase == y
                t, b = actual.vertical(policy, y)
                tops[mask], bottoms[mask] = (t[mask], b[mask]) if np.ndim(t) else (t, b)
                t, b = geom.vertical(policy, y)
                vertical[y] = (t[scorer.representatives], b[scorer.representatives]) if np.ndim(t) else (t, b)
                masks[y] = {}

            tops += shift
            bottoms += shift
            overhead = (xs1 - xs0) * (bottoms - tops) / area
            records = {att: np.empty((n, 5), dtype=float) for att in ATTACKERS}
            group_widths = right - left
            counts = np.zeros(scorer.size, dtype=np.int64)
            cache = {att: {} for att in ATTACKERS}

            for i, (target, x, y, x0, x1, y0, y1) in enumerate(
                zip(ids, pens, phase, xs0, xs1, tops - shift, bottoms - shift)
            ):
                # Vertical compatibility is independent of the pen. Keep only
                # compatible candidates and prune by the necessary width interval.
                key = int(y0), int(y1)
                if key not in masks[y]:
                    top, bottom = vertical[y]
                    match = (top == y0) & (bottom == y1)
                    masks[y][key] = np.flatnonzero(match) if np.ndim(match) else (
                        np.arange(scorer.size) if match else np.empty(0, dtype=int)
                    )
                candidates = masks[y][key]
                width = group_widths[candidates]
                candidates = candidates[(width >= x1 - x0 - 2 * (grid - 1)) &
                                        (width <= x1 - x0)]
                l, r = left[candidates], right[candidates]
                lo = np.maximum(x0 - l, x1 - grid + 1 - r)
                hi = np.minimum(x0 + grid - 1 - l, x1 - r)
                for attacker in ATTACKERS:
                    low, high = (x, x) if attacker == "A1" else (E.PEN_X[0], E.PEN_X[1] - 1)
                    cache_key = (int(target), int(y), int(x0 - low), int(x1 - low),
                                 int(y0), int(y1), int(high - low))
                    cached = cache[attacker].get(cache_key)
                    if cached is None:
                        count = np.minimum(hi, high) - np.maximum(lo, low) + 1
                        counts.fill(0)
                        counts[candidates] = np.maximum(count, 0)
                        cached = scorer.score(counts, target)
                        cache[attacker][cache_key] = cached
                    h1, h10, bits, truth_in = cached
                    if not truth_in and name != "digits":
                        raise ValueError((unit, model, policy, attacker, i))
                    records[attacker][i] = (h1, h10, bits, overhead[i], truth_in)
            for attacker, rows in records.items():
                results[f"{model}|{policy.label}|{attacker}"] = rows
    with path.with_suffix(".tmp").open("wb") as handle:
        np.savez_compressed(handle, **results)
    path.with_suffix(".tmp").replace(path)
    print(name, font, size, "wall_s", round(time.monotonic() - started, 2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kit", type=Path)
    parser.add_argument("work", type=Path)
    parser.add_argument("sanity", type=Path)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    with args.sanity.open() as handle:
        sanity = list(csv.DictReader(handle))
    init(args.kit, args.work)
    if {(r["font"], r["attacker"]) for r in sanity if r["passed"] == "True"} != set(
        product(E.FONTS, ATTACKERS)
    ):
        raise SystemExit("Complete passing surname sanity check required")
    args.work.mkdir(parents=True, exist_ok=True)
    with (args.kit / "results/e1-full/csv/e1_summary.csv").open() as handle:
        sizes = {(r["dict"], r["font"], int(r["size_px"])): int(r["n"])
                 for r in csv.DictReader(handle) if r["variant"] == "main" and
                 r["condition"] == "clean" and r["attacker"] == "A1" and r["grid_px"] == "1"}
    units = [(*key, sizes[key]) for key in product(E.DICTS, E.FONTS, E.SIZES)]
    started = time.monotonic()
    with Pool(args.workers, initializer=init, initargs=(args.kit, args.work)) as workers:
        for _ in workers.imap_unordered(one_unit, units):
            pass
    print(f"Sweep finished with {args.workers} workers, wall_s={time.monotonic()-started:.2f}")


if __name__ == "__main__":
    main()
