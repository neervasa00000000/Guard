#!/usr/bin/env python3
"""Compute v1.3 class tails from the retained paper geometry, without rendering."""
import argparse
import csv
import gzip
import hashlib
import math
import sys
from itertools import product
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research/e1"))
import e1lib as E
import policies as P

E1 = ROOT / "research/e1"
OUT = E1 / "data/v1_3"
WIDTHS = (64, 96, 128, 160, 192, 256)
N = 2000
SEED = 20261029
REFERENCE = "LAYOUT-BOX|pen-anchored-128|A1"


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def write_csv(path, rows):
    with path.open("w", newline="") as source:
        writer = csv.DictWriter(source, rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def classes(counts, keys, font, size, policy, width):
    total = int(sum(counts))
    rows = []
    for k in np.unique(keys):
        group = counts[keys == k]
        mass = int(sum(group))/total
        rows.append(dict(font=font, size_px=size, policy=policy, width_px=width,
                         k=int(k), prior_mass=mass, names=len(group),
                         pointwise_bits=0.0 if mass==1 else -math.log2(mass),
                         max_name_prior=int(group.max())/total))
    return rows


def summary(rows, n_units, peak_name, font, size):
    worst = max(rows, key=lambda row: row["pointwise_bits"])
    return dict(font=font, size_px=size, policy=worst["policy"], width_px=worst["width_px"],
                n_units=n_units, mean_bits=math.fsum(r["prior_mass"]*r["pointwise_bits"] for r in rows)/n_units,
                max_pointwise_bits=worst["pointwise_bits"], max_class_prior_mass=worst["prior_mass"],
                max_class_names=worst["names"], max_class_k=worst["k"],
                max_class_font=worst["font"], max_class_size_px=worst["size_px"],
                min_entropy_bits=math.log2(math.fsum(r["max_name_prior"] for r in rows)/(n_units*peak_name)),
                prior_pct_lt100=100*math.fsum(r["prior_mass"] for r in rows if r["names"]<100)/n_units,
                prior_pct_lt10=100*math.fsum(r["prior_mass"] for r in rows if r["names"]<10)/n_units)


def archive_candidate_tails():
    """Use only recorded clean A1 candidate counts or their recorded logarithms."""
    source = E1/"data/results_cases.csv.gz"
    fields = ("candidate_count","n_candidates","n_cands","log10_cands")
    with gzip.open(source,"rt",newline="") as handle:
        header = next(csv.reader(handle))
    if any(field in header for field in fields):
        raise ValueError("Review the A1 policy labels and candidate-count column in results_cases.csv.gz.")
    rows = [dict(source=source.relative_to(ROOT),font="pooled",size_px="all",
                 scope="requested archive",grid_px=g,status="unavailable",
                 n="",target_pct_lt100="",target_pct_lt10="") for g in (1,16,64)]
    subset = []
    for path in sorted((E1/"cases/main-subset").glob("surnames_*.csv.gz")):
        if "_targets" in path.name:
            continue
        _,font,size = path.name.split(".")[0].split("_")
        with gzip.open(path,"rt",newline="") as handle:
            cases = [r for r in csv.DictReader(handle) if r["variant"]=="main"
                     and r["condition"]=="clean" and r["attacker"]=="A1" and r["k"]=="1"]
        for grid in (1,16,64):
            values = [float(r["log10_cands"]) for r in cases if int(r["grid_px"])==grid]
            if len(values)!=N:
                raise ValueError(f"Incomplete archive subset: {path}, grid {grid}")
            subset.append((path,font,size,grid,values))
    for path,font,size,grid,values in subset:
        rows.append(target_tail(path.relative_to(ROOT),font,size,grid,values))
    for grid in (1,16,64):
        values = [v for _,_,_,g,block in subset if g==grid for v in block]
        if values:
            rows.append(target_tail("research/e1/cases/main-subset","two fonts",16,grid,values))
    return rows


def target_tail(path, font, size, grid, values):
    # log10 was rounded to 3 decimals. Adjacent integer counts on either
    # side of each strict threshold remain distinguishable.
    assert all(round(math.log10(k-1),3)<math.log10(k) for k in (10,100))
    values = np.asarray(values)
    return dict(source=path,font=font,size_px=size,scope="available subset only",grid_px=grid,
                status="computed",n=len(values),target_pct_lt100=100*np.mean(values<2),
                target_pct_lt10=100*np.mean(values<1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry",type=Path,required=True,help="Trusted retained e1-full/data/cache directory")
    parser.add_argument("--scores",type=Path,required=True,help="Retained review4_grouped directory")
    args = parser.parse_args()
    if not E.CENSUS.is_file() or digest(E.CENSUS)!=E.FULL_CENSUS_SHA:
        parser.error("E1_CENSUS must point to the hash-verified full Census CSV.")
    names, counts = E.census(50000)
    counts = np.asarray(counts,dtype=np.int64)
    if len(set(names))!=50000 or len(names)!=50000:
        raise ValueError("Unexpected Census cohort")
    total = int(sum(counts))
    peak_name = int(counts.max())/total
    no_box = int(sum(np.sort(counts)[-10:]))
    dictionary = E._finish(names,counts,np.ones(len(names)),{"source":"Census surnames"})
    per_class, per_cell, inputs, control = [], [], [], []
    for font,size in product(E.FONTS,E.SIZES):
        geom = args.geometry/f"geom_surnames_{font}_{size}.pkl"
        scores = args.scores/f"surnames_{font}_{size}.npz"
        bounds = np.load(geom,allow_pickle=True)
        if bounds.shape!=(len(names),4) or bounds.dtype.kind not in "iu":
            raise ValueError(f"Invalid layout geometry: {geom}")
        inputs.append(dict(font=font,size_px=size,geometry_file=geom.name,geometry_sha256=digest(geom),
                           scores_file=scores.name,scores_sha256=digest(scores)))
        # Padding classes use only the layout left and right offsets.
        left = int(bounds[:,0].min())-E.PAD
        right = bounds[:,2].astype(np.int64)+E.PAD
        for width in (*WIDTHS,0):
            policy = "start-aligned" if width else "fixed-field"
            keys = P.class_index(right,left,width) if width else np.ones(len(names),dtype=np.int64)
            rows = classes(counts,keys,font,size,policy,width)
            per_class.extend(rows)
            per_cell.append(summary(rows,1,peak_name,font,size))
            if width!=128:
                continue
            rng = np.random.default_rng([SEED,list(E.DICTS).index("surnames"),list(E.FONTS).index(font),size])
            chosen,_ = E.sample_targets(dictionary,N,rng)
            bits,hits = P.class_attack(dictionary["p"],keys)
            with np.load(scores) as saved:
                archive = saved[REFERENCE]
            np.testing.assert_allclose(bits[chosen],archive[:,2],atol=1e-9,rtol=0)
            np.testing.assert_allclose(hits[chosen],archive[:,1],atol=1e-12,rtol=0)
            control.append(dict(font=font,size_px=size,n=N,analytic_bits=per_cell[-1]["mean_bits"],
                                replay_bits=bits[chosen].mean(),archived_bits=archive[:,2].mean(),
                                max_abs_target_bits_diff=np.max(np.abs(bits[chosen]-archive[:,2]))))
    for width in (*WIDTHS,0):
        rows = [row for row in per_class if row["width_px"]==width]
        per_cell.append(summary(rows,len(E.FONTS)*len(E.SIZES),peak_name,"pooled","all"))
    archived = archive_candidate_tails()
    OUT.mkdir(parents=True,exist_ok=True)
    write_csv(OUT/"tail_per_class.csv",per_class)
    write_csv(OUT/"tail_summary.csv",per_cell)
    write_csv(OUT/"archive_candidate_tails.csv",archived)
    write_csv(OUT/"geometry_receipts.csv",inputs)
    write_csv(OUT/"control_128.csv",control)
    write_csv(OUT/"no_box.csv",[dict(names=len(names),top10_count_sum=no_box,total_count=total,
                                    expected_top10=no_box/total,expected_top10_pct=100*no_box/total)])
    files = ("tail_per_class.csv","tail_summary.csv","archive_candidate_tails.csv","geometry_receipts.csv",
             "control_128.csv","no_box.csv","README.md")
    (OUT/"SHA256SUMS").write_text("".join(f"{digest(OUT/name)}  {name}\n" for name in files if (OUT/name).is_file()))
    print(f"No-box top-10 {no_box}/{total} = {100*no_box/total:.3f}%")
    print("C=128 pooled analytic",next(row["mean_bits"] for row in per_cell if row["font"]=="pooled" and row["width_px"]==128))
    print("C=128 pooled replay",np.mean([r["replay_bits"] for r in control]))
    print("Wrote",len(per_class),"classes and",len(per_cell),"summary rows")


if __name__=="__main__":
    main()
