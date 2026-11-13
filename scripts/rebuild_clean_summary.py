"""Rebuild the v6.1 clean-grid summary with the archived A2 likelihood scores."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "research/e1/data"
CASES = ROOT / "research/e1/cases/posterior"
SUMMARY = RESULTS / "pooled_clean_dict_grid_attacker.csv"
KEY = ["dict", "grid_px", "attacker"]
METRICS = {
    "hit1": ("top1", "top1"),
    "hit10": ("top10", "top10"),
    "len": ("len_acc", "len"),
    "resid": ("bits_leaked", "bits"),
}


def rebuild():
    summary = pd.read_csv(RESULTS / "pooled_clean_feasible_set.csv").set_index(KEY)
    priors = pd.read_csv(RESULTS / "baselines_nobox.csv").set_index("dict").prior_bits
    phase = pd.read_csv(CASES / "phase_cases.csv.gz")
    digits = pd.read_csv(CASES / "phase_cases_digits.csv.gz")
    phase = pd.concat([phase[phase["dict"] != "digits"], digits], ignore_index=True)
    case_key = ["dict", "font", "size", "variant", "grid_px", "case"]
    if phase.duplicated(case_key).any():
        raise ValueError("Duplicate phase case")
    for metric in METRICS:
        phase[metric] = phase[metric + "_lik"].where(phase.exact_model, phase[metric + "_pub"])
    rng = np.random.default_rng(20261101)
    updated = set()
    for (name, variant, grid), rows in phase.groupby(["dict", "variant", "grid_px"]):
        fonts = rows.groupby("font").agg(n=("case", "size"), **{m: (m, "sum") for m in METRICS})
        n = fonts.n.to_numpy()
        # Use the published RNG stream, which includes the padding cells.
        draws = rng.integers(0, len(fonts), (10000, len(fonts)))
        if variant != "main":
            continue
        key = (name, grid, "A2")
        if len(fonts) != 6 or rows.groupby(["font", "size"]).size().ne(2000).any() or n.sum() != summary.loc[key, "n"]:
            raise ValueError(f"Incomplete phase case coverage for {key}")
        updated.add(key)
        for source, (estimate, interval) in METRICS.items():
            scores = fonts[source].to_numpy()
            point = scores.sum() / n.sum()
            samples = scores[draws].sum(axis=1) / n[draws].sum(axis=1)
            if source == "resid":
                point = priors[name] - point
                samples = priors[name] - samples
            summary.loc[key, [estimate, interval + "_lo", interval + "_hi"]] = [
                point, *np.quantile(samples, [.025, .975])
            ]
        if rows.exact_model.all():
            summary.loc[key, "truth_in_set"] = rows.truth_in_lik.mean()
    if updated != {key for key in summary.index if key[-1] == "A2"}:
        raise ValueError("Missing A2 cells")
    return summary.reset_index()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare against the checked-in summary.")
    args = parser.parse_args()
    frame = rebuild()
    if args.check:
        pd.testing.assert_frame_equal(frame, pd.read_csv(SUMMARY), rtol=0, atol=1e-12)
    else:
        frame.to_csv(SUMMARY, index=False)
    row = frame.query("dict == 'surnames' and grid_px == 16 and attacker == 'A2'").iloc[0]
    print(f"Clean summary verified: surnames 16 px A2 {row.top10:.1%} / {row.bits_leaked:.2f} bits")


if __name__ == "__main__":
    main()
