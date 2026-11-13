"""Target-weighted pooled estimates with font-cluster uncertainty."""

import numpy as np


METRICS = ("top1", "top10", "bits", "median_overredaction")


def font_draws(fonts, seed, n_resamples=10_000):
    """Use one set of font multiplicities for all paired rows."""
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(fonts), size=(n_resamples, len(fonts)))
    return np.stack([(draws == i).sum(axis=1) for i in range(len(fonts))], axis=1)


def weighted_medians(area_by_font, multiplicities):
    """Exact medians of the resampled target-level areas, including even n."""
    unique_areas = np.unique(np.concatenate(area_by_font))
    cumulative = np.column_stack([
        np.searchsorted(np.sort(area), unique_areas, side="right")
        for area in area_by_font
    ])
    totals = multiplicities @ cumulative[-1]
    if np.any(totals == 0):
        raise ValueError("A font resample has no targets")
    weights = np.concatenate((multiplicities, multiplicities), axis=0)
    ranks = np.concatenate(((totals - 1) // 2, totals // 2)) + 1
    low = np.zeros(len(ranks), dtype=int)
    high = np.full(len(ranks), len(unique_areas) - 1, dtype=int)
    while np.any(low < high):
        middle = (low + high) // 2
        cumulative_weight = (weights * cumulative[middle]).sum(axis=1)
        move_right = cumulative_weight < ranks
        low = np.where(move_right, middle + 1, low)
        high = np.where(move_right, high, middle)
    left, right = np.split(unique_areas[low], 2)
    return (left + right) / 2


def estimates(by_font, multiplicities):
    """Input arrays hold target-level top-1, top-10, bits, and area overhead."""
    n = np.array([len(values) for values in by_font])
    totals = multiplicities @ n
    means = (multiplicities @ np.array([v[:, :3].sum(axis=0) for v in by_font]))
    medians = weighted_medians([v[:, 3] for v in by_font], multiplicities)
    return np.column_stack((means / totals[:, None], medians))


def summary(by_font, bootstrap):
    """Return pooled metrics, percentile CIs and leave-one-font-out ranges."""
    n_fonts = len(by_font)
    include_all = np.ones((1, n_fonts), dtype=int)
    leave_one = np.ones((n_fonts, n_fonts), dtype=int) - np.eye(n_fonts, dtype=int)
    point = estimates(by_font, include_all)[0]
    # A font resample depends only on the multiplicity of each font. Evaluate
    # each distinct draw once and restore the original empirical distribution.
    distinct, inverse = np.unique(bootstrap, axis=0, return_inverse=True)
    boot = estimates(by_font, distinct)[inverse]
    ci_low, ci_high = np.quantile(boot, [0.025, 0.975], axis=0)
    loo = estimates(by_font, leave_one)
    row = {"n": sum(map(len, by_font))}
    for metric, value, low, high, loo_low, loo_high in zip(
        METRICS, point, ci_low, ci_high, loo.min(axis=0), loo.max(axis=0)
    ):
        row.update({
            metric: value,
            f"{metric}_ci_low": low,
            f"{metric}_ci_high": high,
            f"{metric}_loo_low": loo_low,
            f"{metric}_loo_high": loo_high,
        })
    return row
