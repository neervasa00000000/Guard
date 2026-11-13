"""Enumerate the observation law and compute Shannon posterior entropy."""
from collections import Counter, defaultdict
from fractions import Fraction
from itertools import product
from math import fsum, log2

import numpy as np


def entropy(weights):
    weights = np.asarray(weights, dtype=float)
    positive = weights[weights > 0]
    assert positive.size
    probability = positive / positive.sum()
    return float(-np.dot(probability, np.log2(probability)))


def tight(offsets):
    left, top, right, bottom = offsets
    return left - 1, top - 1, right + 1, bottom + 1


def ceil_grid(value, step):
    return -(-value // step) * step


def bounds(offsets, padding=None, anchor=None, full_line=None):
    left, top, right, bottom = tight(offsets)
    if padding:
        if anchor is not None:
            left = anchor
        right = left + ceil_grid(right - left, padding)
    if full_line is not None:
        top, bottom = full_line
    return left, top, right, bottom


def draw_counts(box, pen, baseline, grid, jitter, collapse=False):
    left, top, right, bottom = map(int, box)
    a = Counter((pen + left - j) // grid * grid for j in range(jitter + 1))
    b = Counter(ceil_grid(pen + right + j, grid) for j in range(jitter + 1))
    c = Counter((baseline + top - j) // grid * grid for j in range(jitter + 1))
    d = Counter(ceil_grid(baseline + bottom + j, grid) for j in range(jitter + 1))
    if collapse:
        c, d = {None:sum(c.values())}, {None:sum(d.values())}
    return {tuple(edge for edge, _ in row): row[0][1]*row[1][1]*row[2][1]*row[3][1]
            for row in product(a.items(), b.items(), c.items(), d.items())}


def observation_counts(boxes, starts, baseline, grid, jitter, offsets, known, collapse=False):
    counts = defaultdict(lambda: [0] * len(boxes))
    for word, box in enumerate(boxes):
        for start in starts:
            copies = [draw_counts(box, start+dx, baseline+dy, grid, jitter, collapse) for dx, dy in offsets]
            for trial in product(*(c.items() for c in copies)):
                multiplicity = 1
                for _, count in trial:
                    multiplicity *= count
                key = (start if known else None, tuple(observed for observed, _ in trial))
                counts[key][word] += multiplicity
    total = len(starts)*(jitter+1)**(4*len(offsets))
    assert all(sum(row[i] for row in counts.values()) == total for i in range(len(boxes)))
    return counts, total


def posterior(prior, counts):
    joint = [p*c for p, c in zip(prior, counts)]
    mass = sum(joint)
    return [w/mass for w in joint], mass


def information(prior, counts, total):
    entropies = {}
    masses = {}
    for key, values in counts.items():
        q, mass = posterior(prior, values)
        entropies[key] = entropy(q)
        masses[key] = mass/total
    assert sum(masses.values()) == Fraction(1)
    return entropy(prior) - fsum(float(masses[b])*h for b,h in entropies.items()), entropies, masses


def sampled_bits(prior, entropies, observations):
    return entropy(prior) - fsum(entropies[b] for b in observations)/len(observations)


def rendered_likelihood(grouped_boxes, observation, starts, baseline, grid):
    """For real data, try every start on each distinct 4-edge geometry."""
    left, right, top, bottom = observation
    unique, inverse = grouped_boxes
    l, t, r, b = unique.T
    vertical = (grid*((baseline+t)//grid) == top) & (grid*(-(-(baseline+b)//grid)) == bottom)
    result = np.zeros(len(unique), dtype=np.int64)
    aligned = np.flatnonzero(vertical)
    for start in starts:
        result[aligned] += ((grid*((start+l[aligned])//grid) == left)
                            & (grid*(-(-(start+r[aligned])//grid)) == right))
    return result[inverse]
