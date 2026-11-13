"""Compare the grouped scorer to the original phase_exact implementation."""

import sys
from pathlib import Path

import numpy as np

from grouped_scores import GroupedScores
from sanity import load_scorer


def main():
    kit = Path(sys.argv[1])
    sys.path.insert(0, str(kit / "results/e1-full/scripts"))
    import e1lib as E

    reference = load_scorer(kit)
    rng = np.random.default_rng(20261110)
    n_checks = 0
    for name in E.DICTS:
        dictionary = E.get_dict(name)
        n = len(dictionary["p"])
        groups = rng.integers(0, 300, size=(n, 1))
        scorer = GroupedScores(dictionary, groups)
        for trial in range(100):
            target = rng.integers(n)
            counts = rng.integers(0, 5, size=scorer.size)
            if trial == 0:
                counts.fill(0)
            h1, h10, _, h, truth = reference(
                dictionary, dictionary["p"] * counts[scorer.group], target,
                dictionary["length"][target],
            )
            np.testing.assert_allclose(scorer.score(counts, target),
                                       [h1, h10, scorer.prior_entropy - h, truth],
                                       atol=1e-10, rtol=1e-10)
            n_checks += 1
    print(f"Verified grouped scoring against phase_exact on {n_checks} cases", flush=True)


if __name__ == "__main__":
    main()
