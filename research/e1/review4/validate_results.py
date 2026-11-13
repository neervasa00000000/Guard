"""Check sweep coverage, published controls and output invariants."""

import argparse
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

from geometry import POLICIES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kit", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output
    fonts = pd.read_csv(output / "per_font.csv")
    expected_policies = {p.label for p in POLICIES}
    keys = ["list", "font", "size_px", "model", "attacker", "policy"]
    assert not fonts.duplicated(keys).any()
    assert len(fonts) == 5 * 6 * 3 * 2 * 2 * len(expected_policies)
    assert set(fonts.policy) == expected_policies
    assert (fonts.n == 2000).all()
    assert (fonts.top1 <= fonts.top10 + 1e-12).all()
    assert fonts.top1.between(0, 1).all() and fonts.top10.between(0, 1).all()
    assert (fonts[fonts["list"] != "digits"].truth_in == 1).all()
    assert (fonts[fonts.policy == "exact"].median_overredaction == 1).all()

    pooled = pd.read_csv(output / "pooled.csv")
    assert len(pooled) == 5 * 4 * 2 * 2 * len(expected_policies)
    assert set(pooled.n) == {12000, 36000}
    for metric in ("top1", "top10", "bits", "median_overredaction"):
        assert (pooled[f"{metric}_ci_low"] <= pooled[f"{metric}_ci_high"]).all()
        assert (pooled[f"{metric}_loo_low"] <= pooled[f"{metric}_loo_high"]).all()
    matched = pd.read_csv(output / "matched_overredaction.csv")
    first, second = matched.overredaction_a, matched.overredaction_b
    assert (np.maximum(first, second) <= 1.10 * np.minimum(first, second) + 1e-12).all()
    assert len(pd.read_csv(output / "padding_minus_64.csv")) == 5 * 4 * 2 * 2 * 6 * 12

    published = pd.read_csv(args.kit / "results/e1-full/csv/e1_summary.csv")
    old = published[(published.condition == "clean") & (published.attacker == "A1") &
                    (published["dict"] != "digits") & (published.size_px.isin([12, 16, 24]))]
    main = old[(old.variant == "main") | ((old.variant == "D2_bucket128") & (old.grid_px == 1))].copy()
    main["policy"] = np.where(main.variant == "main", "square-" + main.grid_px.astype(str),
                              "ink-anchored-128")
    main.loc[main.policy == "square-1", "policy"] = "exact"
    main = main.rename(columns={"dict": "list"})
    new = fonts[(fonts.model == "LAYOUT-BOX") & (fonts.attacker == "A1")]
    paired = main.merge(new, on=["list", "font", "size_px", "policy"], validate="one_to_one",
                        suffixes=("_published", "_review"))
    assert len(paired) == 4 * 6 * 3 * 6
    for field in ("top1", "top10"):
        paired[f"delta_{field}"] = paired[f"{field}_review"] - paired[f"{field}_published"]
    paired["delta_bits"] = paired.bits - paired.bits_leaked
    paired["delta_area_ratio"] = paired.median_overredaction - paired.over_median
    columns = [*keys[:3], "policy", "delta_top1", "delta_top10", "delta_bits", "delta_area_ratio"]
    paired[columns].to_csv(output / "published_a1_controls.csv", index=False)
    print(f"Validated {len(fonts)} per-font cells and compared {len(paired)} published A1 controls")
    largest = paired[columns[4:]].abs().max()
    print(largest.to_dict())
    assert (largest <= 1e-9).all(), "Published non-digit A1 controls differ beyond rounding"

    audit_path = args.kit / "v5.7-ieee/new_tests_posterior/csv/phase_cases.csv.gz"
    audit = pd.read_csv(audit_path, usecols=[
        "dict", "font", "size", "variant", "grid_px", "hit1_lik", "hit10_lik", "resid_lik",
    ])
    audit = audit[(audit["dict"] != "digits") &
                  ((audit.variant == "main") |
                   ((audit.variant == "D2_bucket128") & (audit.grid_px == 1)))].copy()
    audit["policy"] = np.where(audit.variant == "main", "square-" + audit.grid_px.astype(str),
                               "ink-anchored-128")
    audit.loc[audit.policy == "square-1", "policy"] = "exact"
    audit = audit.rename(columns={"dict": "list", "size": "size_px"})
    audit = audit.groupby(["list", "font", "size_px", "policy"], as_index=False)[
        ["hit1_lik", "hit10_lik", "resid_lik"]
    ].mean()
    prior = main.groupby("list", as_index=False).prior_bits.first()
    audit = audit.merge(prior, on="list", validate="many_to_one")
    a2 = fonts[(fonts.model == "LAYOUT-BOX") & (fonts.attacker == "A2")]
    checks = audit.merge(a2, on=["list", "font", "size_px", "policy"], validate="one_to_one")
    assert len(checks) == len(paired)
    checks["delta_top1"] = checks.top1 - checks.hit1_lik
    checks["delta_top10"] = checks.top10 - checks.hit10_lik
    checks["delta_bits"] = checks.bits - (checks.prior_bits - checks.resid_lik)
    a2_columns = [*keys[:3], "policy", "delta_top1", "delta_top10", "delta_bits"]
    checks[a2_columns].to_csv(output / "published_a2_controls.csv", index=False)
    a2_largest = checks[a2_columns[4:]].abs().max()
    print(f"Compared {len(checks)} non-digit A2 exact-likelihood audit controls")
    print(a2_largest.to_dict())
    assert (a2_largest <= 1e-9).all(), "Published non-digit A2 audit controls differ beyond rounding"

    fig = pd.read_csv(output / "fig3_cases.csv.gz")
    expected = set(product(("surnames", "words"), (1, 16), ("A1", "A2"), fonts.font.unique()))
    sizes = fig.groupby(["dict", "grid_px", "attacker", "true_font"]).size()
    assert set(sizes.index) == expected and (sizes == 2000).all()
    assert set(fig.variant) == {"K"} and (fig.truth_in == 1).all()
    print(f"Verified {len(fig)} Fig. 3 target rows")


if __name__ == "__main__":
    main()
