"""Compare the independent enumerator with archived and live harness scores."""
import csv
import gzip
import hashlib
from fractions import Fraction
from itertools import product
from math import fsum
from pathlib import Path
import platform
import random
import re
import subprocess
import sys

import numpy as np
from PIL import __version__ as pillow_version, features

import adapter
import posterior as P


KIT, REVIEW, OUT = map(Path, sys.argv[1:])
V = KIT/"v5.7-ieee"
TOY_SEED = 20261118
SAMPLE_SIZES = (100,1000,10000)
BASELINE = 60
ZERO = ((0,0),)


def save(name, rows):
    with (OUT/name).open("w",newline="") as stream:
        writer = csv.DictWriter(stream,fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def reference():
    root = V/"release_additions/posterior_audit"
    archive = (root/"toy_posterior_check_output.txt").read_text()
    launch = "import adapter, runpy, sys; from pathlib import Path; adapter.load(*map(Path, sys.argv[1:3])); runpy.run_path(sys.argv[3], run_name='__main__')"
    replay = subprocess.check_output([sys.executable,"-c",launch,str(KIT),str(REVIEW),
                                      str(root/"toy_posterior_check.py")],text=True)
    (OUT/"published_replay.log").write_text(replay)
    line = r"toy: .*H\(W\)=([0-9.]+).*\nA2 exact box \(g=1\).*?I\(W;B\)=\s*([0-9.]+)"
    expected = re.search(line,archive).groups()
    actual = re.search(line,replay).groups()
    assert actual == expected and "RESULT: PASS" in replay, (actual,expected)
    print("Published sanity passed",*actual,flush=True)
    return actual


def prior(weights):
    total = sum(weights)
    return tuple(Fraction(w)/total for w in weights)


def test(name, raw, p, g=1, j=0, offsets=ZERO, known=False, padding=None, fixed=False,
         line=None, collapse=False, starts=range(64)):
    anchor = min(row[0] for row in raw)-1 if fixed else None
    boxes = [P.bounds(row,padding,anchor,line) for row in raw]
    counts,total = P.observation_counts(boxes,starts,BASELINE,g,j,offsets,known,collapse)
    mi,entropies,masses = P.information(p,counts,total)
    reference_boxes = adapter.geometry(raw,padding,fixed,line)
    scorer = adapter.Scorer(reference_boxes,p,starts,BASELINE,g,j,offsets)
    independent = {}
    max_mass = 0.0
    for key,row in counts.items():
        c,h = scorer.evaluate(key,collapse)
        np.testing.assert_array_equal(c,row)
        independent[key] = h
        max_mass=max(max_mass,abs(float(masses[key])-np.dot(scorer.prior,c)/total))
    harness_mi = P.entropy(p) - fsum(float(masses[k])*h for k,h in independent.items())
    rng = random.Random(TOY_SEED)
    keys = list(counts)
    sampled = rng.choices(keys,weights=[float(masses[k]) for k in keys],k=SAMPLE_SIZES[-1])
    values = dict(mutual_information=mi,harness_mi=harness_mi,max_mi_difference=abs(mi-harness_mi),
                  max_entropy_difference=max(abs(h-independent[k]) for k,h in entropies.items()),
                  max_probability_difference=max_mass)
    for n in SAMPLE_SIZES:
        a = P.sampled_bits(p,entropies,sampled[:n])
        b = P.sampled_bits(p,independent,sampled[:n])
        values[f"equation2_n{n}"]=a
        values[f"equation2_difference_n{n}"]=abs(a-b)
        values[f"equation2_minus_mi_n{n}"]=a-mi
    print("Compared",name,g,j,known,padding,fixed,len(offsets),len(counts),flush=True)
    values=dict(test=name,grid=g,jitter=j,attacker="A1" if known else ("A3" if len(offsets)>1 else "A2"),
                padding=padding or 0,start_aligned=fixed,full_line=line is not None,k=len(offsets),
                start_min=starts[0],start_max=starts[-1],boxes=len(counts),**values)
    for field,value in values.items():
        if "difference" in field:
            assert value <= 1e-9,(field,value)
    return values


def check_toys():
    rows = []
    widths = (10,11,13,17,17,29)
    t1 = [(0,-8,w,2) for w in widths]
    p1 = prior((6,5,4,3,2,1))
    for g,known in product((1,8,16),(False,True)):
        rows.append(test("T1",t1,p1,g,known=known))
    g1 = (None,((0,32,48,64),))
    law,_ = P.observation_counts([P.tight(box) for box in t1],range(64),BASELINE,16,0,ZERO,False)
    weights = law[g1]
    q,z = P.posterior(p1,weights)
    hand = [dict(candidate=i+1,width=w,prior=str(p),start_count=c,likelihood=str(Fraction(c,64)),
                 joint=str(p*Fraction(c,64)),posterior=str(v))
            for i,(w,p,c,v) in enumerate(zip(widths,p1,weights,q))]
    save("hand_check.csv",hand)
    rng = np.random.default_rng(1)
    t2 = [(0,-8,int(w),2) for w in rng.integers(5,61,20)]
    p2 = prior([Fraction(1,i) for i in range(1,21)])
    for g,j in product((1,8,16,32,64),(0,4,16)):
        rows.append(test("T2",t2,p2,g,j,collapse=True))
    t3 = [(i%3,-8-i%2,w+i%3,2+i%2) for i,w in enumerate((6,9,12,13,17,19,25,29))]
    for offsets in (((0,0),(7,0)),((0,0),(7,0),(13,0))):
        rows.append(test("T3",t3,prior(range(8,0,-1)),16,offsets=offsets))
    t4 = [(i%4-2,-8-i%3,w+i%4-2,2+i%2)
          for i,w in enumerate((8,12,16,24,28,30,32,42,59,65))]
    for c,fixed,line,known in product((32,64),(False,True),(None,(-15,6)),(False,True)):
        rows.append(test("T4",t4,prior(range(10,0,-1)),known=known,padding=c,fixed=fixed,line=line))
    save("toy_comparison.csv",rows)
    return rows,hand,P.entropy(q),z/64


def read_gz(path):
    with gzip.open(path,"rt",newline="") as source:
        return list(csv.DictReader(source))


def real():
    E = adapter.E
    f = E.font("DejaVuSans",16)
    D = E.get_dict("surnames")
    assert np.all(D["m"]==1)
    entries = D["strings"]
    raw = np.array([f.getbbox(word,anchor="ls") for word in entries],dtype=np.int64)
    boxes = raw+np.array([-1,-1,1,1])
    archived = V/"new_tests_padding/csv/cases_a3"
    unit = "surnames_DejaVuSans_16"
    targets = read_gz(archived/f"{unit}_targets.csv.gz")[:200]
    reference = {(r["case"],r["grid_px"],r["attacker"]):r
                 for r in read_gz(archived/f"{unit}.csv.gz")
                 if r["variant"]=="main" and r["condition"]=="clean" and r["k"]=="1"}
    phase = {}
    with gzip.open(V/"new_tests_posterior/csv/phase_cases.csv.gz","rt",newline="") as stream:
        for r in csv.DictReader(stream):
            if (r["dict"],r["font"],r["size"],r["variant"])==("surnames","DejaVuSans","16","main"):
                phase[r["case"],r["grid_px"]] = r
            elif phase and r["font"] != "DejaVuSans":
                break
    rows = []
    prepared = np.unique(boxes,axis=0,return_inverse=True)
    for target in targets:
        case,entry = target["case"],int(target["entry"])
        x,y = int(target["pen_x"]),int(target["baseline_y"])
        assert target["target"]==entries[entry]
        for g,a in product((1,16),("A1","A2")):
            pub = reference[case,str(g),a]
            observed = tuple(int(pub[k]) for k in ("X0","X1","Y0","Y1"))
            fresh = next(iter(P.draw_counts(boxes[entry],x,y,g,0)))
            assert observed==fresh,(case,g,observed,fresh)
            starts = (x,) if a=="A1" else range(*E.PEN_X)
            count = P.rendered_likelihood(prepared,observed,starts,y,g)
            assert count[entry]>0
            h = P.entropy(D["p"]*count)
            stored = float(pub["resid_bits"] if a=="A1" else phase[case,str(g)]["resid_lik"])
            tol = .00005+1e-9 if a=="A1" else 1e-9
            rows.append(dict(case=case,grid_px=g,attacker=a,independent=h,stored=stored,
                             absolute_difference=abs(h-stored),tolerance=tol,match=abs(h-stored)<=tol))
    save("real_comparison.csv",rows)
    return rows


def report(control, rows, hand, h, mass, real_rows):
    lines = ["# Independent posterior check", "",
             f"The archived toy replay reproduced prior entropy **{control[0]} bits** and A2 exact mutual information "
             f"**{control[1]} bits** at printed precision. [Sanity replay](published_replay.log)", "",
             "## Toy universes", "",
             "The independent code enumerates starts and jitter draws. Exact integer counts and rational priors "
             "give posterior weights and observation masses before evaluating logarithms. A1 includes the known "
             "start in each observation. A3 enumerates every copy at the same start. T2 has identical vertical "
             "offsets for every candidate, so the vertical jitter factor has no effect on any posterior. Its "
             "vertical outcomes are marginalized using their full multiplicity.", "",
             "The adapter calls the unchanged `Cell.feasible`, `metrics` and `bucket_transform` in "
             "`results/e1-full/scripts/e1lib.py`, the unchanged `scores` in "
             "`new_tests_posterior/scripts/phase_exact.py`, and the unchanged jitter count `cnt` in "
             "`new_tests_review3/scripts/d1_exact.py`. It supplies inclusive start counts using the interval "
             "formula in `phase_exact.py` and `a3_exact.py`. It uses `Geometry.horizontal` in "
             "`research/e1/review4/geometry.py` for the full-line start-padding policy.", "",
             "T1 uses prior weights 6 through 1. T2 uses NumPy seed 1 and Zipf exponent 1. "
             "T3 uses descending prior weights 8 through 1. T4 uses descending weights 10 through 1, "
             "a fixed anchor at the minimum tight left edge, and line offsets −15 and 6 for full-line cells. "
             "The [toy CSV](toy_comparison.csv) records every configuration, its exact mutual information and "
             "the paired Equation 2 checks at the three sample sizes.", "",
             "| Test | Configurations | Max per-box entropy difference | Max Eq. 2 difference | Max mutual information difference | Pass |",
             "|---|---:|---:|---:|---:|---|"]
    for test_name in ("T1","T2","T3","T4"):
        group = [r for r in rows if r["test"]==test_name]
        a=max(r["max_entropy_difference"] for r in group)
        b=max(r[f"equation2_difference_n{n}"] for r in group for n in SAMPLE_SIZES)
        c=max(r["max_mi_difference"] for r in group)
        lines.append(f"| {test_name} | {len(group)} | {a:.3g} | {b:.3g} | {c:.3g} | PASS |")
    lines += ["", "Equation 2 uses seeded samples of observation boxes from the exact marginal distribution. "
              "The difference from exact mutual information can fluctuate as the sample grows.", "",
              "| Samples | Mean absolute Equation 2 minus exact mutual information |",
              "|---:|---:|"]
    for n in SAMPLE_SIZES:
        diff = fsum(abs(r[f"equation2_minus_mi_n{n}"]) for r in rows)/len(rows)
        lines.append(f"| {n:,} | {diff:.6f} bits |")
    lines += ["","## Hand check", "",
              "T1, A2, 16-px grid, baseline 60, observation `[0,32) × [51,67)` before vertical "
              "snapping is represented below using the actual snapped vertical edges."]
    lines[-1] = ("T1, A2, 16-px grid. The common padded vertical interval [51,63) snaps to [48,64). "
                 "For horizontal observation [0,32), floor((x − 1)/16) × 16 = 0 gives starts 1 through 16. "
                 "The right edge requires 17 ≤ x + width + 1 ≤ 32. Intersect those two integer intervals and "
                 "divide the count by 64. Multiply by the prior and divide by the total joint mass.")
    lines += ["","| Entry | Width | Prior | Starts | Likelihood | Joint probability | Posterior |",
              "|---:|---:|---:|---:|---:|---:|---:|"]
    for r in hand:
        lines.append("| "+" | ".join(str(x) for x in r.values())+" |")
    lines += ["",f"The sum of the joint column is {mass}. Substituting the posterior column in "
              f"−Σ p log₂ p gives **{h:.9f} bits**.","","## Published surname targets","",
              "The first 200 archived targets use DejaVu Sans at 16 px. The independent scorer recomputes "
              "all candidate bounds with `font.getbbox(word, anchor='ls')` using Pillow 12.3.0 and RAQM, "
              "then enumerates the pen range for A2. Every target box was checked against the archive. "
              "A1 uses archived residuals rounded to four decimal places. A2 uses archived exact-likelihood "
              "residuals at full precision. [Case results](real_comparison.csv)","",
              "| Attacker | Grid | Targets | Max absolute difference (bits) | Mismatches |",
              "|---|---:|---:|---:|---:|"]
    for a,g in product(("A1","A2"),(1,16)):
        items=[r for r in real_rows if r["attacker"]==a and r["grid_px"]==g]
        maximum=max(r["absolute_difference"] for r in items)
        bad=sum(not r["match"] for r in items)
        lines.append(f"| {a} | {g} | {len(items)} | {maximum:.9g} | {bad} |")
    bad=sum(not r["match"] for r in real_rows)
    lines += ["","## Three-line summary","",
              f"- {len(rows)} toy configurations passed the 1e-9-bit comparison.",
              f"- Maximum toy per-box difference was {max(r['max_entropy_difference'] for r in rows):.3g} bits.",
              f"- {bad} mismatches in {len(real_rows)} real-target comparisons at stored precision.","",
              "[Independent code](posterior.py) · [Adapter](adapter.py) · [Versions and command](run.log) · "
              "[Git before](git_before.txt) · [Git after](git_after.txt)"]
    (OUT/"POSTERIOR_CHECK.md").write_text("\n".join(lines)+"\n")


if __name__ == "__main__":
    print(platform.platform(),sys.version,"NumPy",np.__version__,"Pillow",pillow_version,
          {name:features.version(name) for name in ("raqm","harfbuzz","fribidi","freetype2")},flush=True)
    print("Observation sample seed",TOY_SEED,"T2 width seed",1,flush=True)
    control = reference()
    adapter.load(KIT,REVIEW)
    import json
    manifest = json.loads((KIT/"results/e1-full/data/fonts.json").read_text())
    font = Path(adapter.E.FONTS["DejaVuSans"][0])
    assert hashlib.sha256(font.read_bytes()).hexdigest()==manifest["DejaVuSans"]["sha256"]
    toy_data=check_toys()
    real_data=real()
    report(control,*toy_data,real_data)
