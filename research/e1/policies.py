"""Redaction policies for the v1.2 experiments.

Boxes are in pen and baseline coordinates, half-open, with the same 1 px
expansion as the paper's Geometry. x_L is the shared text start: one less
than the leftmost layout edge in the list. The full line is one pixel
outside the font's ascent and descent, widened to the list's ink if needed.

Start-aligned padding and the start-anchored width-only grid are the same
map: the left edge stays at x_L and the width is rounded up to a multiple
of the class or grid. Square grids snap all edges onto the page grid.
The field box is one rectangle for every string.
"""
import numpy as np


def ceil_multiple(value, width):
    value = np.asarray(value)
    return -(-value // width) * width


def prepare(bounds, ascent, descent):
    """Expand layout bounds the way the paper's Geometry does."""
    left, top, right, bottom = np.asarray(bounds, dtype=np.int64).T
    return {
        "left": left - 1,
        "top": top - 1,
        "right": right + 1,
        "bottom": bottom + 1,
        "line_top": min(-int(ascent), int(top.min())) - 1,
        "line_bottom": max(int(descent), int(bottom.max())) + 1,
        "x_l": int(left.min()) - 1,
        "tight_area": (right - left + 2) * (bottom - top + 2),
    }


def _full_line(prep, left, right):
    top = np.full(left.shape, prep["line_top"], dtype=np.int64)
    bottom = np.full(left.shape, prep["line_bottom"], dtype=np.int64)
    return left, top, right, bottom


def start_aligned_padding(prep, width):
    """Left edge at x_L. Width rounds up to a multiple of `width`."""
    left = np.full(prep["right"].shape, prep["x_l"], dtype=np.int64)
    right = left + ceil_multiple(prep["right"] - left, int(width))
    return _full_line(prep, left, right)


def start_anchored_grid(prep, grid):
    """Width-only grid anchored at the text start. Same boxes as start-aligned padding at C = G."""
    left = np.full_like(prep["right"], prep["x_l"])
    right = left - ((left - prep["right"]) // grid) * grid
    return _full_line(prep, left, right)


def square_grid(prep, grid, pen_x, baseline):
    """Snap outward on the page, then express edges relative to the known pen."""
    left = (pen_x + prep["left"]) // grid * grid - pen_x
    right = ceil_multiple(pen_x + prep["right"], grid) - pen_x
    top = (baseline + prep["top"]) // grid * grid - baseline
    bottom = ceil_multiple(baseline + prep["bottom"], grid) - baseline
    return left, top, right, bottom


def field_box(prep):
    """One box for every string: from x_L across the widest value, full line.

    Field width is the maximum, over the list, of the padded layout span
    from the shared text start to the padded right edge. That is the widest
    rendered value measured from x_L, in pixels. The returned index is the
    first string that attains it.
    """
    span = prep["right"] - prep["x_l"]
    width = int(span.max())
    widest = int(np.flatnonzero(span == width)[0])
    left = np.full(span.shape, prep["x_l"], dtype=np.int64)
    right = np.full(span.shape, prep["x_l"] + width, dtype=np.int64)
    return (*_full_line(prep, left, right), width, widest)


def class_index(right, x_l, width):
    """k(w) = ceil((padded right - x_L) / width)."""
    return ceil_multiple(np.asarray(right) - int(x_l), int(width)) // int(width)


def class_entropy(prior, key):
    """Prior entropy of a deterministic class key, in bits. This is H(k(W))."""
    prior = np.asarray(prior, dtype=np.float64)
    key = np.asarray(key)
    _, inverse = np.unique(key, return_inverse=True)
    mass = np.bincount(inverse, weights=prior)
    mass = mass[mass > 0]
    share = mass / mass.sum()
    return float(-(share * np.log2(share)).sum())


def class_attack(prior, key):
    """Per-string leakage when the box reveals `key` and nothing else.

    Ties in the prior are counted in expectation. Multiplicity is 1, which
    holds for the surname, word, and e-mail lists. `bits` is H(W) - H(W|key=key(w))
    and is constant inside a class. `hit10` is the top-10 success of that
    string.
    """
    prior = np.asarray(prior, dtype=np.float64)
    key = np.asarray(key)
    _, inverse = np.unique(key, axis=0, return_inverse=True)
    bits = np.empty(len(prior), dtype=np.float64)
    hit10 = np.empty(len(prior), dtype=np.float64)
    h0 = float(-(prior * np.log2(prior)).sum())
    for class_id in range(int(inverse.max()) + 1):
        member = np.flatnonzero(inverse == class_id)
        mass = prior[member]
        residual = np.log2(mass.sum()) - float((mass * np.log2(prior[member])).sum()) / mass.sum()
        bits[member] = 0.0 if len(member) == len(prior) else h0 - residual
        order = np.argsort(prior[member], kind="mergesort")
        ranked_prior = prior[member[order]]
        change = np.flatnonzero(np.diff(ranked_prior)) + 1
        starts = np.concatenate(([0], change))
        stops = np.concatenate((change, [len(ranked_prior)]))
        greater = np.empty(len(ranked_prior), dtype=np.float64)
        for start, stop in zip(starts, stops):
            greater[start:stop] = len(ranked_prior) - stop
        for start, stop in zip(starts, stops):
            equal = float(stop - start)
            success = min(1.0, max(0.0, (10.0 - greater[start]) / equal))
            hit10[member[order][start:stop]] = success
    return bits, hit10
