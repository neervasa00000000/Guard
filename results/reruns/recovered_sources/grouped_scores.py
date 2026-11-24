"""Exact likelihood scoring grouped by identical transformed geometry."""

import numpy as np


class GroupedScores:
    def __init__(self, dictionary, keys):
        _, group = np.unique(keys, axis=0, return_inverse=True)
        self.group = group
        self.size = int(group.max()) + 1
        self.representatives = np.unique(group, return_index=True)[1]
        self.prior = dictionary["p"]
        multiplicity = dictionary["m"]
        mass = self.prior * multiplicity
        self.mass = np.bincount(group, weights=mass)
        self.plogp = np.bincount(group, weights=mass * np.log2(self.prior))
        self.prior_entropy = -self.plogp.sum()

        order = np.lexsort((self.prior, group))
        split = np.searchsorted(group[order], np.arange(self.size + 1))
        # Identical priors share a cumulative interval. Offset arrays keep
        # searches bounded to one geometry group.
        self.offsets = split
        self.sorted_prior = self.prior[order]
        self.cumulative = np.concatenate(([0.0], np.cumsum(multiplicity[order])))
        self.group_multiplicity = np.diff(self.cumulative[split])
        self.max_prior = self.sorted_prior[split[1:] - 1]
        self.min_prior = self.sorted_prior[split[:-1]]

    def score(self, count, target):
        group = self.group[target]
        truth_in = count[group] > 0
        active = np.flatnonzero(count)
        if not len(active):
            return 0.0, 0.0, 0.0, False
        weight = count[active]
        mass = self.mass[active] * weight
        z = mass.sum()
        entropy = np.log2(z) - (
            weight @ self.plogp[active] + mass @ np.log2(weight)
        ) / z
        bits = self.prior_entropy - entropy
        if not truth_in:
            return 0.0, 0.0, bits, False

        qt = self.prior[target] * count[group]
        upper = qt * (1 + 1e-12)
        lower = qt - qt * 1e-12
        greater = self.min_prior[active] * weight > upper
        possible = (~greater) & (self.max_prior[active] * weight >= lower)
        gt = float(self.group_multiplicity[active[greater]].sum())
        if gt >= 10:
            return 0.0, 0.0, bits, True
        eq = 0.0
        for i, w in zip(active[possible], weight[possible]):
            a, b = self.offsets[i:i+2]
            values = self.sorted_prior[a:b]
            # Use the original score comparisons around the binary-search
            # boundary, preserving the phase_exact relative tie tolerance.
            hi = np.searchsorted(values, upper / w, side="right")
            while hi and values[hi-1] * w > upper:
                hi -= 1
            while hi < len(values) and values[hi] * w <= upper:
                hi += 1
            gt += self.cumulative[b] - self.cumulative[a + hi]
            if gt >= 10:
                return 0.0, 0.0, bits, True
            lo = np.searchsorted(values, lower / w, side="left")
            while lo and abs(values[lo-1] * w - qt) <= qt * 1e-12:
                lo -= 1
            while lo < hi and abs(values[lo] * w - qt) > qt * 1e-12:
                lo += 1
            while hi > lo and abs(values[hi-1] * w - qt) > qt * 1e-12:
                hi -= 1
            eq += self.cumulative[a + hi] - self.cumulative[a + lo]
        return min(1.0, max(0.0, (1 - gt) / eq)), min(1.0, (10 - gt) / eq), bits, True
