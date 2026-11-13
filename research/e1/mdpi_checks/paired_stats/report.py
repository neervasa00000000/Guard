"""Make the paired comparison and per-font tables."""
from pathlib import Path
import sys

import pandas as pd

from paired import ATTACKERS, LISTS, MODELS, TABLE

out=Path(sys.argv[1])
counts=pd.read_csv(out/"ordering_counts.csv")
trials=pd.read_csv(out/"paired_tests.csv")
fonts=pd.read_csv(out/"per_font.csv")
old=pd.read_csv(out/"w9_replayed_summary.csv")
align=pd.read_csv(out/"a2_alignment.csv")
assert len(counts)==112 and counts.cells.eq(18).all()
assert len(trials)==112*19 and len(fonts)==8*6*9
assert not trials.duplicated(list(trials.columns[:7])).any()
assert trials[trials.font=="pooled"].n.eq(36000).all()
assert trials[trials.font!="pooled"].n.eq(2000).all()
assert fonts[fonts.font=="pooled"].n.eq(36000).all()
assert fonts[~fonts.font.isin(["pooled","min","max"])].n.eq(6000).all()
assert trials.p_value.between(0,1).all()
assert (trials.ci_lo<=trials.ci_hi).all()

lines=["# Paired tests and per-font results","",
       f"The archived Holm results reproduced across **{len(old)} families of {old.cells.iloc[0]} cells**. "
       "The control recalculates the independent-proportion z test from the published cell means and "
       "then applies Holm. It also recomputes the archived paired z statistics from retained targets "
       "for surnames and words. For the other lists it uses the archived paired z statistics to replay Holm.",
       "[Holm controls](w9_replayed_summary.csv) · [Control cells](w9_replayed_cells.csv)","",
       "## Methods","",
       "- Pair the stored review4 records by list, font, size and target index. Compute left minus right for expected top-10 and for bits. The bit difference is the right residual entropy minus the left residual entropy.",
       "- Draw 100,000 independent sign flips of each difference vector. One-sided p is (1 + flips at least as large as the observed sum) / 100,001. Each pooled permutation sums the independent cell permutations.",
       "- Resample 10,000 sets of target pairs with replacement and report percentile 95% intervals. The pooled bootstrap draws from all targets in the list.",
       "- Apply Holm across the 18 font–size cells within each comparison, list, attacker, observation model and metric. The pooled p-value is shown separately.",
       "- Score ties in expectation. A published seed for individual tie-breaks was NOT FOUND, so the paired tests use fractional hits and McNemar is unavailable.","",
       f"The stored A2 likelihood scores aligned with the archived per-target values for {len(align)} "
       f"layout-box policy cells ({int(align.n.sum()):,} records). Maximum absolute differences were "
       f"{align.max_hit_error.max():.3g} for hit probabilities and {align.max_bits_error.max():.3g} bits. "
       "The published main A2 scorer uses feasible-set weights. The retained A2 data used here "
       "use the later exact-likelihood rescore. The layout- and ink-box policies share target indices "
       "within each retained NPZ. [A2 alignment](a2_alignment.csv)","",
       "## Ordering counts and pooled effects","",
       "Counts are out of 18. Old counts are independent-proportion tests for layout-box A1 top-10. "
       "Positive counts are the number of observed differences above zero. Raw and Holm counts use p < 0.05. "
       "The pooled top-10 changes and intervals are in percentage points.",""]
pooled=trials[trials.font=="pooled"].set_index(["list","model","attacker","comparison","metric"])
for (name,model,att),group in counts.groupby(["list","model","attacker"]):
    lines += [f"### {name.capitalize()} · {model} · {att}","",
              "| Ordering | Metric | Old raw / Holm | Positive | Paired raw / Holm | Pooled difference [95% CI] | Pooled p |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for r in group.itertuples(index=False):
        p=pooled.loc[(name,model,att,r.comparison,r.metric)]
        scale=100 if r.metric=="top10" else 1
        before=f"{int(r.old_raw)} / {int(r.old_holm)}" if pd.notna(r.old_raw) else "—"
        lines.append(f"| {r.comparison} | {r.metric} | {before} | {r.positive} | {r.paired_raw} / {r.paired_holm} | "
                     f"{p.difference*scale:+.4f} [{p.ci_lo*scale:+.4f}, {p.ci_hi*scale:+.4f}] | {p.p_value:.6g} |")
    lines.append("")
lines += ["## Changes from the published tests",""]
published=counts[counts.old_holm.notna()]
for name,group in published.groupby("list"):
    changed=group[group.old_holm!=group.paired_holm]
    stable=group[group.old_holm==group.paired_holm]
    structure=", ".join(f"{r.comparison} {int(r.old_holm)} → {r.paired_holm} of {r.cells}"
                         for r in changed.itertuples(index=False))
    stable_counts=", ".join(f"{r.comparison} {r.paired_holm} of {r.cells}"
                            for r in stable.itertuples(index=False))
    lines.append(f"- {name.capitalize()} Holm counts changed for {structure}. The counts stayed the same for {stable_counts}.")

lines += ["","## Per-font results","",
          "Each entry gives top-10 (%), bits and median area ratio in that order. Each font pools the three "
          "sizes and the pooled row combines the six fonts. The range lists the minimum and maximum "
          "across fonts for each metric.",""]
names=["Exact","16 px","64 px","Edge 128","Start 128","Width-only 64"]
for name,model,att in ((n,m,a) for n in LISTS for m in MODELS for a in ATTACKERS):
    groups=fonts[(fonts["list"]==name)&(fonts.model==model)&(fonts.attacker==att)]
    lookup=groups.set_index(["font","policy"])
    order=sorted(set(groups.font)-{"min","max","pooled"})+["pooled","range"]
    lines += [f"### {name.capitalize()} · {model} · {att}","","| Font | "+" | ".join(names)+" |",
              "|---|"+"---:|"*len(TABLE)]
    for font in order:
        row=[]
        for policy in TABLE:
            if font=="range":
                a=lookup.loc[("min",policy)]
                b=lookup.loc[("max",policy)]
                token=f"{a.top10_pct:.2f}–{b.top10_pct:.2f} / {a.bits:.3f}–{b.bits:.3f} / {a.median_area:.2f}–{b.median_area:.2f}"
            else:
                a=lookup.loc[(font,policy)]
                token=f"{a.top10_pct:.2f} / {a.bits:.3f} / {a.median_area:.2f}"
            row.append(token)
        lines.append("| "+font+" | "+" | ".join(row)+" |")
    lines.append("")
lines += ["[All paired intervals and p-values](paired_tests.csv) · [Ordering counts](ordering_counts.csv) · "
          "[Per-font CSV](per_font.csv) · [Run information](RUN_INFO.md)"]
(out/"PAIRED_STATS.md").write_text("\n".join(lines)+"\n")
