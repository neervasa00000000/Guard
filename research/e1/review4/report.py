"""Aggregate the clean sweep, then generate the review tables."""

import argparse
from collections import defaultdict
from itertools import combinations, product
from pathlib import Path

import numpy as np
import pandas as pd

from font_stats import METRICS, font_draws, summary
from geometry import POLICIES
from sweep import ATTACKERS, MODELS, SEED

MAIN = ("exact", "square-8", "square-16", "square-32", "square-64",
        "ink-anchored-128", "pen-anchored-128")
BOOTSTRAP_SEED = 20261110


def provenance(name, model, policy):
    if name == "digits":
        return "Model-based digit analysis"
    if model == "LAYOUT-BOX" and policy in MAIN and policy != "pen-anchored-128":
        return "Published condition rerun"
    return "New"


def pooled_report(work, out):
    per_font, pooled, paired, matches = [], [], [], []
    units = defaultdict(dict)
    for path in sorted(work.glob("*.npz")):
        name, font, size = path.stem.split("_")
        units[name][font, int(size)] = path
    if len(units) != 5 or any(len(files) != 18 for files in units.values()):
        raise ValueError("Expected all 90 sweep units")
    policies = [p.label for p in POLICIES]
    for name, files in units.items():
        fonts = sorted({font for font, _ in files})
        sizes = sorted({size for _, size in files})
        draws = font_draws(fonts, BOOTSTRAP_SEED)
        data = {}
        for key, path in files.items():
            with np.load(path) as archive:
                data[key] = dict(archive.items())
        for size, model, attacker in product([*sizes, "all"], MODELS, ATTACKERS):
            selected = sizes if size == "all" else [size]
            rows, font_rows = {}, {}
            base = dict(list=name, size_px=size, model=model, attacker=attacker)
            for policy in policies:
                key = f"{model}|{policy}|{attacker}"
                by_font = [np.concatenate([data[font, s][key] for s in selected])
                           for font in fonts]
                label = base | dict(policy=policy, provenance=provenance(name, model, policy))
                row = label | summary([v[:, :4] for v in by_font], draws)
                row["truth_in"] = float(np.concatenate(by_font)[:, 4].mean())
                rows[policy] = row
                pooled.append(row)
                for font, values in zip(fonts, by_font):
                    point = dict(zip(METRICS, np.r_[values[:, :3].mean(axis=0),
                                                    np.median(values[:, 3])]))
                    point.update(label, font=font, n=len(values), truth_in=values[:, 4].mean())
                    font_rows[font, policy] = point
                    if size != "all":
                        per_font.append(point)
            for font, policy in product(fonts, policies):
                if "anchored" in policy:
                    row = font_rows[font, policy]
                    baseline = font_rows[font, "square-64"]
                    paired.append(base | dict(font=font, policy=policy, n=row["n"]) | {
                        f"delta_{m}": row[m] - baseline[m] for m in METRICS
                    })
            for a, b in combinations(policies, 2):
                first, second = rows[a], rows[b]
                ar, br = (r["median_overredaction"] for r in (first, second))
                if max(ar, br) <= 1.10 * min(ar, br):
                    matches.append(base | dict(policy_a=a, policy_b=b,
                                                overredaction_a=ar, overredaction_b=br) | {
                        f"delta_{m}_b_minus_a": second[m] - first[m] for m in METRICS[:3]
                    } | {f"{m}_{side}": row[m] for side, row in (("a", first), ("b", second))
                         for m in METRICS[:3]})
    for name, rows in (("per_font", per_font), ("pooled", pooled),
                       ("padding_minus_64", paired), ("matched_overredaction", matches)):
        pd.DataFrame(rows).to_csv(out / f"{name}.csv", index=False)
        print(f"{name}: {len(rows)} rows")
    return pd.DataFrame(pooled), pd.DataFrame(matches)


def markdown_table(headers, rows):
    def line(row):
        return "| " + " | ".join(map(str, row)) + " |"
    return "\n".join([line(headers), line(["---"] * len(headers)), *(line(row) for row in rows)])


def report(work, out, kit, reference):
    pooled, matched = pooled_report(work, out)
    fig3 = pd.read_csv(out / "fig3_baseline.csv")
    sanity = pd.read_csv(out / "sanity.csv")
    published = pd.read_csv(reference)
    subset = pooled[(pooled["list"] == "surnames") & (pooled.size_px == 16)]
    pixel_a1 = subset[(subset.model == "PIXEL-INK") & (subset.attacker == "A1")].set_index("policy")
    paired = pd.read_csv(out / "padding_minus_64.csv")
    pixel_paired = paired[(paired["list"] == "surnames") & (paired.size_px == "16") &
                         (paired.model == "PIXEL-INK") & (paired.attacker == "A1") &
                         (paired.policy == "ink-anchored-128")]
    relevant_matches = matched[(matched["list"] == "surnames") & (matched.size_px == 16) &
                               (matched.model == "PIXEL-INK") & (matched.attacker == "A1") &
                               (matched.policy_b.str.contains("anchored")) &
                               (matched.policy_a != "exact")]
    text = [
        "# TileSeal v5.8 review rerun",
        f"The published 16 px surname check passed in {len(sanity)} font–attacker cells. "
        f"The largest absolute differences were {sanity.delta_top10.abs().max():.3g} in top-10 "
        f"and {sanity.delta_bits.abs().max():.3g} bits. A1 uses the original summary reference. "
        "A2 uses the exact-likelihood audit reference, which includes the pen support.",
        "## Task 1. Left-edge rerun",
        "The table shows clean surnames at 16 px pooled over the six fonts. "
        "[Per-font results](per_font.csv), [pooled results and intervals](pooled.csv), and "
        "[paired padding-minus-64 differences](padding_minus_64.csv) cover all five lists and all sizes.",
        markdown_table(
            ("Box model", "Attacker", "Policy", "Top-1", "Top-10 (95% CI)", "Bits (95% CI)",
             "Median area ratio", "n", "Status"),
            [(r.model, r.attacker, r.policy, f"{r.top1:.2%}",
              f"{r.top10:.2%} [{r.top10_ci_low:.2%}, {r.top10_ci_high:.2%}]",
              f"{r.bits:.3f} [{r.bits_ci_low:.3f}, {r.bits_ci_high:.3f}]",
              f"{r.median_overredaction:.2f}×", r.n, r.provenance)
             for r in subset.itertuples() if r.policy in MAIN],
        ),
        f"For PIXEL-INK A1 at 16 px, ink-anchored padding leaked "
        f"{pixel_a1.loc['ink-anchored-128', 'bits']:.3f} bits, the square 64 px grid leaked "
        f"{pixel_a1.loc['square-64', 'bits']:.3f} bits, and pen-anchored padding leaked "
        f"{pixel_a1.loc['pen-anchored-128', 'bits']:.3f} bits. Ink-anchored padding leaked "
        f"more than the grid in {(pixel_paired.delta_bits > 0).sum()} of {len(pixel_paired)} fonts.",
        "The published-condition reruns are the LAYOUT-BOX exact and square-grid rows and "
        "128 px ink-anchored padding. Their A2 values supersede prior-only feasible-set "
        "scoring where the earlier table used it. The PIXEL-INK and pen-anchored results are new.",
        "## Task 2. Area and leakage",
        "Each comparison uses the ratio of the redacted area to that model’s padded tight area. "
        "Matched policies have a larger median area ratio at most 1.10 times the smaller. "
        "The [matched-area CSV](matched_overredaction.csv) gives the comparisons for each "
        "list, size, model and attacker. All policies are in the pooled CSV.",
        markdown_table(
            ("Policy", "LAYOUT-BOX area", "LAYOUT-BOX A1 bits", "LAYOUT-BOX A2 bits",
             "PIXEL-INK area", "PIXEL-INK A1 bits", "PIXEL-INK A2 bits"),
            [(policy, *(value for model in MODELS for value in (
                f"{subset[(subset.policy == policy) & (subset.model == model)].median_overredaction.iloc[0]:.2f}×",
                *(f"{subset[(subset.policy == policy) & (subset.model == model) & (subset.attacker == a)].bits.iloc[0]:.3f}"
                  for a in ATTACKERS),
            ))) for policy in [p.label for p in POLICIES]],
        ),
        "Matched comparisons involving padding for PIXEL-INK A1 on 16 px surnames.",
        markdown_table(
            ("Policy A", "Policy B", "Area ratio A", "Area ratio B", "Bits B − A"),
            [(r.policy_a, r.policy_b, f"{r.overredaction_a:.2f}×", f"{r.overredaction_b:.2f}×",
              f"{r.delta_bits_b_minus_a:+.3f}") for r in relevant_matches.itertuples()],
        ),
        f"The matched-area CSV contains {len(matched)} comparisons, including the rows pooled across sizes.",
        "## Task 3. Fig. 3 known-font and known-size baseline",
        "This reruns variant K from the original Fig. 3 script at the requested sample size "
        "with its original scoring and seed scheme. The final two columns use the original "
        "clean 16 px pooled-size CSV for the Table VII comparison.",
        markdown_table(
            ("List", "Attacker", "Grid", "n", "Top-1 (95% CI)", "Top-10 (95% CI)",
             "Bits (95% CI)", "Clean 16 px top-10", "Clean 16 px bits"),
            fig3_rows(fig3, published),
        ),
        "[Fig. 3 baseline CSV](fig3_baseline.csv) · [Fig. 3 target CSV](fig3_cases.csv.gz)",
        "The expanded K rows are new estimates of the Fig. 3 baseline. They use the original "
        "feasible-set scorer, including for A2.",
        "## Task 4. Single-thread A4",
        "The optional A4 run was skipped. The local feasibility archive is truncated.",
        "## Reproduction",
        "The clean sweep and Fig. 3 ran after the published surname sanity check passed. "
        "The verification log records the rerun with the six supplied fonts. The first "
        "direct-scoring sweep was stopped after its completed units had been saved. "
        "The final sweep uses grouped geometry and was checked against the direct scorer. "
        "It completed before its outer shell emitted a post-run error caused by an edit "
        "to the wrapper during execution. Report validation confirmed all output cells.",
        "The Fig. 3 baseline and target CSVs were reproduced with the finalized wrapper. "
        "The report validation checks target coverage in both lists.",
        f"The clean seed is `[{SEED}, dictionary_index, font_index, size]` and the Fig. 3 seed "
        f"is `[{int(fig3.seed.iloc[0])}, dictionary_index, font_index]`. Percentile intervals "
        f"resample six font clusters 10,000 times with seed `{BOOTSTRAP_SEED}`. Pooled means and "
        "medians weight each target equally. Leave-one-font-out bounds recompute the statistic "
        "after each omission. The area statistic is the median of per-target area ratios.",
        "Per-font padding differences pair the same target draws and subtract the 64 px grid "
        "metric from the padding metric. For area the difference is between the two medians.",
        "For digits the published dictionary compresses each length/first/last class to one "
        "representative string with multiplicity. The sweep renders the sampled target’s actual "
        "middle digits. Exact pen-position counts therefore apply to representative candidate "
        "geometry. When a representative misses the target, the truth earns zero hits. When "
        "the whole candidate set is empty, the entropy calculation falls back to the prior. "
        "The CSVs report `truth_in` so these model-based digit results can be identified. "
        "An exact posterior over individual digit strings is blocked by the grouped "
        "candidate representation in the supplied kit.",
        "Pen-anchored widths round the span from the fixed anchor through the padded right edge "
        "so the box covers the target. Width-only grids snap the horizontal edges to the page "
        "grid and use the same full line vertically as padding. The line starts from "
        "the font ascent and descent, expands to cover any candidate extrema, and includes "
        "the one-pixel margin.",
        "The container used Linux aarch64 on an Apple M4 host. Fonts were installed at the "
        "original paths after checking both the archive manifest and the study receipts.",
        "Linux runtime versions, thread settings, font verification and wall times are in "
        "[sanity.log](sanity.log), [verification.log](verification.log), "
        "[sweep.log](sweep.log) and [fig3.log](fig3.log). FriBidi was 1.0.8. "
        "The other requested rendering versions matched.",
        "The [published A1 controls](published_a1_controls.csv) compare each reproduced "
        "non-digit LAYOUT-BOX cell with the original CSV, including the area statistic. "
        "The [A2 controls](published_a2_controls.csv) use the exact-likelihood audit cases.",
        "\x60\x60\x60sh\n"
        "docker build -t guard-e1-review4 research/e1/review4\n"
        f"kit={kit}\n"
        "mkdir -p Rerun/e1_fonts\n"
        "tar -xzf Rerun/e1_fonts.tar.gz -C Rerun/e1_fonts\n"
        'set -e\n'
        'for mode in sanity sweep fig3 report; do\n'
        '  sh research/e1/review4/run_sanity.sh "$kit" "$PWD/Rerun/e1_fonts.tar.gz" \\\n'
        '    "$PWD/Rerun/e1_fonts" "$mode"\n'
        'done\n'
        "\x60\x60\x60",
    ]
    (out / "RESULTS.md").write_text("\n\n".join(text) + "\n")


def fig3_rows(fig3, published):
    for row in fig3.to_dict("records"):
        name, attacker = row["dict"], row["attacker"]
        clean = published[(published["dict"] == name) & (published.size_px == 16) &
                          (published.grid_px == 16) & (published.attacker == attacker)].iloc[0]
        metrics = []
        for metric in ("hit1", "hit10", "bits_leaked"):
            fmt = ".3f" if metric == "bits_leaked" else ".2%"
            point, lo, hi = [format(row[f"{metric}{suffix}"], fmt)
                             for suffix in ("", "_ci_low", "_ci_high")]
            metrics.append(f"{point} [{lo}, {hi}]")
        yield (name, attacker, "Exact" if row["grid_px"] == 1 else "16 px",
               row["n"], *metrics, f"{clean.top10:.2%}", f"{clean.bits_leaked:.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("kit_host_path")
    parser.add_argument("published_size_csv", type=Path)
    args = parser.parse_args()
    report(args.work, args.out, args.kit_host_path, args.published_size_csv)
