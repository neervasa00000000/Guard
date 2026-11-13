"""Write Tables IV and X companions from the replayed A3 data and archive."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument("output", type=Path)
parser.add_argument("kit", type=Path)
args = parser.parse_args()
out, kit = args.output, args.kit
v = kit/"v5.7-ieee"
previous = pd.read_csv(out/"summary.csv")
checked = pd.read_csv(out/"summary_checked.csv")
pd.testing.assert_frame_equal(previous, checked, check_exact=False, atol=1e-12, rtol=0)
d = pd.concat([previous[previous.condition!="size"], pd.read_csv(out/"size_summary.csv")], ignore_index=True)
d.to_csv(out/"results_summary.csv",index=False)
cases = pd.read_csv(out/"cases.csv.gz")
cases = pd.concat([cases[cases.condition!="size"], pd.read_csv(out/"size_cases.csv.gz")], ignore_index=True)
assert not cases.duplicated(list(cases.columns[:10])).any()
cases.to_csv(out/"results_cases.csv.gz",index=False)
lines = ["# Start-aligned padding with multiple releases", "",
         "The mandatory Table IV and Table X controls passed. The replay checked the archived "
         "targets and pens and regenerated the shared offsets. [Grid check](sanity_grid.csv) · "
         "[Padding check](sanity_edge_pad.csv)", "", "## Table IV companion", "",
         "SANITY CHECK. Shifted copies use the archived two fonts, 16 px and 128 px class. "
         "The last two columns give the paired change from the first release to the fifth.", "",
         "| List | Policy | Grid | Attacker | n | Top-10 k=1 / 2 / 3 / 5 (%) | Bits k=1 / 2 / 3 / 5 | Median area | "
         "Top-10 change [95% CI], pp | Bits change [95% CI] |",
         "|---|---|---:|---|---:|---|---|---:|---|---|"]
for key,p in cases[cases.condition=="shifted"].groupby(["list","model","grid","attacker"]):
    a=p.groupby("k")[["hit10","bits"]].mean()
    x=p[p.k==5][["hit10","bits"]].to_numpy()-p[p.k==1][["hit10","bits"]].to_numpy()
    rng=np.random.default_rng(20261117)
    draws=rng.integers(0,len(x),(10000,len(x)),dtype="int32")
    q=np.quantile(x[draws].mean(axis=1),[.025,.975],axis=0)
    h,b=x.mean(axis=0)
    title,model,g,att=key
    lines.append(f"| {title} | start-pad 128 ({model}) | {g} | {att} | {len(x)} | "+
                 " / ".join(f"{z*100:.2f}" for z in a.hit10)+" | "+
                 " / ".join(f"{z:.4f}" for z in a.bits)+f" | {p[p.k==1].area.median():.2f}×"+
                 f" | {h*100:+.2f} [{q[0,0]*100:+.2f}, {q[1,0]*100:+.2f}] | {b:+.4f} [{q[0,1]:+.4f}, {q[1,1]:+.4f}] |")
lines.extend(["","## Table X companion", "",
              "New policies are shown at the largest copy count in each cell. The CSV retains all "
              "evaluated copy counts and paired intervals. Area is the first release box area divided by its padded tight box area.",
              "", "| Setting | List | Font | Size | Class | Model | Grid | Attacker | k | Top-10 1 → k (%) | "
              "Bits 1 → k | Median area | Changed class | n | Δ top-10 [95% CI], pp | Δ bits [95% CI] |",
              "|---|---|---|---:|---:|---|---:|---|---:|---|---|---:|---:|---:|---|---|"])
edge = pd.read_csv(v/"new_tests_review2/csv/s3_knownstart.csv")
row=edge[(edge.unit=="surnames_DejaVuSans_16")&(edge.variant=="pad")&(edge.attacker=="A1")].set_index("k")
lines.append(f"| Shifted, archived edge | surnames | DejaVuSans | 16 | 128 | layout | 1 | A1 | 5 | "
             f"{row.loc[1,'top10']:.2f} → {row.loc[5,'top10']:.2f} | "
             f"{row.loc[1,'bits']:.4f} → {row.loc[5,'bits']:.4f} | — | — | {row.loc[5,'n']} | — | — |")
jit=pd.read_csv(v/"new_tests_review3/csv/d2jit_pooled.csv")
jit16=pd.read_csv(v/"new_tests_posterior/csv/d2jit16_exact_pooled.csv")
for (title,variant),p in jit16.groupby(["dict","variant"]):
    p=p.set_index("k")
    lines.append(f"| Jitter, archived edge | {title} | pooled | 16 | 128 | layout | 1 | {variant.split('_')[-1]} | 5 | "
                 f"{100*p.loc[1,'top10_lik']:.2f} → {100*p.loc[5,'top10_lik']:.2f} | "
                 f"{p.loc[1,'bits_lik']:.4f} → {p.loc[5,'bits_lik']:.4f} | — | — | {p.loc[5,'n']} | — | — |")
source=pd.read_csv(v/"new_tests_review3/csv/d2jit_cases.csv.gz",usecols=["dict","size","attacker","k"])
for (name,att),p in jit[jit.u.isin(["surnames_24px","words_24px"])].groupby(["u","attacker"]):
    p=p.set_index("k")
    title=name.split("_")[0]
    n=len(source[(source["dict"]==title)&(source["size"]==24)&(source.attacker==att)&(source.k==5)])
    lines.append(f"| Jitter, archived edge | {title} | pooled | 24 | 128 | layout | 1 | {att} | 5 | {p.loc[1,'top10_lik']:.2f} → {p.loc[5,'top10_lik']:.2f} | {p.loc[1,'bits_lik']:.4f} → {p.loc[5,'bits_lik']:.4f} | — | — | {n} | — | — |")
rer = pd.read_csv(v/"new_tests_review2/csv/s2_rerender.csv")
for (s,sc,att), p in rer[(rer["dict"]=="surnames")&(rer.split=="all")&rer.scenario.isin(["font","size","renderer"])].groupby(["size","scenario","attacker"]):
    if (sc=="size" and (s!=24 or att!="A2")) or (sc=="renderer" and (s!=24 or att!="A2")):
        continue
    a,b=p.iloc[0],p.iloc[-1]
    ch=rer[(rer["dict"]=="surnames")&(rer["size"]==s)&(rer.scenario==sc)&(rer.attacker==att)&(rer.k==b.k)&(rer.split=="class_changed")]
    count=int(ch.n.iloc[0]) if len(ch) else 0
    lines.append(f"| {sc}, archived edge | surnames | mixed | {s} | 128 | layout | 1 | {att} | {b.k} | {a.top10:.2f} → {b.top10:.2f} | {a.bits:.4f} → {b.bits:.4f} | — | {count} | {b.n} | — | — |")
keys=list(d.columns[:8])
last=d.loc[d.groupby(keys).k.idxmax()]
for r in last.itertuples(index=False):
    lines.append(f"| {r.condition}, start | {r.list} | {r.font} | {r.size} | {r.class_px} | {r.model} | {r.grid} | "
                 f"{r.attacker} | {r.k} | {r.top10_1:.2f} → {r.top10_k:.2f} | {r.bits_1:.4f} → {r.bits_k:.4f} | "
                 f"{r.median_area:.2f}× | {r.targets_change_class if r.font=='mixed' else '—'} | {r.n} | "
                 f"{r.delta_top10:+.2f} [{r.top10_lo:+.2f}, {r.top10_hi:+.2f}] | "
                 f"{r.delta_bits:+.4f} [{r.bits_lo:+.4f}, {r.bits_hi:+.4f}] |")
lines.extend(["", "LibreOffice layout-box geometry is NOT FOUND. The mixed-renderer condition "
              "uses pixel ink for Pillow and the published LibreOffice ink tables.", "",
              "The jitter run retains the fixed left anchor and full line. Jitter extends the "
              "request before bucketing. Only the right-side draw changes the width class. "
              "The fixed anchor can omit part of the artificial left jitter margin. The "
              "paired archive jitter rows use the edge-aligned definition.", "",
              "## Five-line summary", ""])
for title,scenarios in (("Shifted",["shifted"]),("Harder sets",["harder"]),("Jitter",["jitter"]),
                        ("New font or size",["font","size"]),("Mixed renderer",["renderer"])):
    p=last[last.condition.isin(scenarios)]
    lines.append(f"- {title} changed top-10 from k=1 to the last copy by {p.delta_top10.min():+.3f} to "
                 f"{p.delta_top10.max():+.3f} pp and leakage by {p.delta_bits.min():+.5f} to "
                 f"{p.delta_bits.max():+.5f} bits.")
lines.extend(["", "[Per-target cases](results_cases.csv.gz) · [Paired intervals and area](results_summary.csv) · [Run information](RUN_INFO.md)"])
(out/"RESULTS.md").write_text("\n".join(lines)+"\n")
