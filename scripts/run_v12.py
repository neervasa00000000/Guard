#!/usr/bin/env python3
"""Run the paired 1,000-surname A1 experiment and the full-list paper control."""
import argparse
import csv
import gzip
import hashlib
import io
import json
import platform
import sys
import time
from itertools import product
from pathlib import Path

import numpy as np
import PIL
from PIL import features

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research/e1"))
import e1lib as E
import policies as P

CASES = ROOT / "research/e1/cases/v1_2"
DATA = ROOT / "research/e1/data/v1_2"
N = 2000
SEED = 20261029
BOOT = 20261114
DRAWS = 10000
GRIDS = (8, 16, 32, 64)
CLASSES = (32, 48, 64, 96, 128, 160, 192, 256)
SETTINGS = ([("square", g) for g in GRIDS] +
            [(name, c) for name in ("start-width-grid", "start-aligned") for c in CLASSES] +
            [("field", 0)])


def write_csv(path, names, rows):
    if path.suffix == ".gz":
        with path.open("wb") as file, gzip.GzipFile(fileobj=file, filename="", mode="wb", mtime=0) as z:
            with io.TextIOWrapper(z, newline="") as stream:
                writer = csv.writer(stream, lineterminator="\n")
                writer.writerow(names)
                writer.writerows(rows)
    else:
        with path.open("w", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(names)
            writer.writerows(rows)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def targets(dictionary, font, size):
    rng = np.random.default_rng([SEED, 0, list(E.FONTS).index(font), size])
    chosen, _ = E.sample_targets(dictionary, N, rng)
    return chosen, rng.integers(*E.PEN_X, N), rng.integers(*E.PEN_Y, N)


def obs_area(box, tight):
    l, t, r, b = box
    return (r-l)*(b-t)/tight


def archive_height(prep, chosen, archive):
    box = P.start_aligned_padding(prep, 128)
    width = (box[2]-box[0])[chosen]
    values = archive[:,3]*prep["tight_area"][chosen]/width
    height = int(round(float(values[0])))
    np.testing.assert_allclose(values, height, atol=1e-10, rtol=0)
    return height


def inputs(font, size, full, chosen, args, sources):
    if font != "NotoSans" or args.noto_cache is None:
        face = E.font(font, size)
        bounds = np.array([face.getbbox(w, anchor="ls") for w in full["strings"]])
        a, d = face.getmetrics()
        sources[f"{font}/{size}"] = {"font_sha256": sha(E.checked_font_path(font)), "metrics": [a,d]}
        return bounds, a, d
    # The retained review4 area records recover full-line height exactly.
    # No replacement font is used. The entire line can be translated vertically
    # without changing A1 ranks or areas for the full-line policies.
    path = args.noto_cache / f"geom_surnames_{font}_{size}.pkl"
    reference = args.noto_scores / f"surnames_{font}_{size}.npz"
    bounds = np.load(path, allow_pickle=True)
    if bounds.shape != (len(full["strings"]),4) or bounds.dtype.kind not in "iu":
        raise ValueError(f"Unexpected geometry in {path}")
    prep = P.prepare(bounds,0,0)
    with np.load(reference) as source:
        original = source["LAYOUT-BOX|pen-anchored-128|A1"]
    height = archive_height(prep,chosen,original)
    a = int(-bounds[:,1].min())
    d = height-a-2
    if d < bounds[:,3].max():
        raise ValueError("Reconstructed line does not enclose the cached bounds")
    box = P.start_aligned_padding(P.prepare(bounds,a,d),128)
    np.testing.assert_allclose(obs_area(box,prep["tight_area"])[chosen],original[:,3],rtol=0,atol=1e-12)
    bits,hits = P.class_attack(full["p"],box[2])
    np.testing.assert_allclose(bits[chosen],original[:,2],rtol=0,atol=1e-9)
    np.testing.assert_allclose(hits[chosen],original[:,1],rtol=0,atol=1e-12)
    # Confirm the raw cached geometry and pen phases against all archived square grids.
    _,x,y = targets(full,font,size)
    with np.load(reference) as source:
        for grid in GRIDS:
            scored = square_scores(prep,full["p"],chosen,x,y,grid)
            np.testing.assert_allclose(scored[0],source[f"LAYOUT-BOX|square-{grid}|A1"][:,2],atol=1e-9,rtol=0)
            np.testing.assert_allclose(scored[1],source[f"LAYOUT-BOX|square-{grid}|A1"][:,1],atol=1e-12,rtol=0)
    sources[f"{font}/{size}"] = {"geometry_sha256": sha(path), "score_sha256": sha(reference),
                                "recovered_line_height": height, "line_vertical_origin": "relative proxy"}
    return bounds,a,d


def square_scores(prep, prior, chosen, x, y, grid):
    phase = np.column_stack((x%grid,y%grid))
    values = np.empty((len(chosen),2))
    log_prior = np.log2(prior)
    h0 = -prior @ log_prior
    dictionary = dict(p=prior,m=np.ones(len(prior)),length=np.ones(len(prior),dtype=int))
    for px,py in np.unique(phase,axis=0):
        mask = (phase[:,0]==px)&(phase[:,1]==py)
        box = P.square_grid(prep,grid,px,py)
        if mask.sum() < 10:
            for i in np.flatnonzero(mask):
                target = chosen[i]
                feasible = np.logical_and.reduce([edge==edge[target] for edge in box])
                row = E.metrics(dictionary,feasible,target,1,log_prior)
                values[i] = (h0-row["resid_bits"],row["hit10"])
        else:
            bits,hits = P.class_attack(prior,np.column_stack(box))
            values[mask] = np.column_stack((bits[chosen[mask]],hits[chosen[mask]]))
    return values.T


def summarize(blocks, size):
    merged = np.concatenate([block for s, block in blocks if size == "all" or size == s])
    rng = np.random.default_rng(BOOT)
    means = np.empty(DRAWS)
    for i in range(0,DRAWS,64):
        take = rng.integers(0,len(merged),(min(64,DRAWS-i),len(merged)),dtype=np.int32)
        means[i:i+len(take)] = merged[take,0].mean(axis=1)
    return len(merged), merged[:,0].mean(), *np.quantile(means,[.025,.975]), 100*merged[:,1].mean(), np.median(merged[:,2])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--noto-cache",type=Path,help="Explicit fallback to the retained exact-layout geometry directory.")
    parser.add_argument("--noto-scores",type=Path,help="Retained review4 per-target NPZ directory for validating cached Noto geometry.")
    args = parser.parse_args()
    if (args.noto_cache is None) != (args.noto_scores is None):
        parser.error("Pass both Noto replay inputs.")
    started = time.monotonic()
    if PIL.__version__ != "12.3.0" or not features.check("raqm"):
        raise SystemExit("Pillow 12.3.0 with RAQM is required.")
    for font in E.FONTS:
        if font != "NotoSans" or args.noto_cache is None:
            E.checked_font_path(font)
    if sha(E.CENSUS) != E.FULL_CENSUS_SHA:
        raise SystemExit("E1_CENSUS must point at the full verified Census file for the paper control.")
    full = E.dict_surnames()
    names, counts = E.census(1000)
    if full["strings"][:len(names)] != names or len(names) != 1000:
        raise ValueError("Unexpected Census order or cohort size")
    short = E._finish(names,counts,np.ones(len(names)),{"source":"Census head in file order"})
    sources = {}
    geometry = {}
    controls = []
    control_cases = []
    for font,size in product(E.FONTS,E.SIZES):
        chosen,x,y = targets(full,font,size)
        bounds,a,d = inputs(font,size,full,chosen,args,sources)
        print("Geometry ready",font,size,flush=True)
        geometry[font,size] = P.prepare(bounds[:len(names)],a,d)
        prep = P.prepare(bounds,a,d)
        box = P.start_aligned_padding(prep,128)
        bits,hits = P.class_attack(full["p"],box[2])
        area = obs_area(box,prep["tight_area"])
        controls.append((size,np.column_stack((bits[chosen],hits[chosen],area[chosen]))))
        control_cases.extend(zip([font]*N,[size]*N,range(N),chosen,x,y,bits[chosen],hits[chosen],area[chosen]))
    expected = {12:"0.000",16:"0.003",24:"0.23","all":"0.08"}
    control = []
    for size in (*E.SIZES,"all"):
        data = np.concatenate([a for s,a in controls if size=="all" or s==size])
        bits,area = data[:,0].mean(),np.median(data[:,2])
        bit_text = f"{bits:.{len(expected[size].split('.')[1])}f}".replace("-0.000","0.000")
        passed = bit_text==expected[size] and (size!="all" or f"{area:.2f}"=="3.36")
        row = (size,len(data),bits,area,expected[size],"3.36" if size=="all" else "",passed)
        control.append(row)
        print("paper control",*row,flush=True)
    DATA.mkdir(parents=True,exist_ok=True)
    write_csv(DATA/"paper_control.csv",["size_px","n","bits","median_area","printed_bits","printed_area","pass"],control)
    if not all(row[-1] for row in control):
        raise SystemExit("Published 128-px control failed. See paper_control.csv.")
    checks,fields = [],[]
    scores = {key:[] for key in SETTINGS}
    analytics = {c:[] for c in CLASSES}
    all_cases = {size:[] for size in E.SIZES}
    for (font,size),prep in geometry.items():
        print("Scoring",font,size,flush=True)
        chosen,x,y = targets(short,font,size)
        for c in CLASSES:
            g,p = P.start_anchored_grid(prep,c),P.start_aligned_padding(prep,c)
            differences = np.any(np.column_stack(g)!=np.column_stack(p),axis=1)
            checks.append((font,size,c,N,int(differences[chosen].sum()),len(names),int(differences.sum())))
            if differences.any():
                write_csv(DATA/"box_check.csv",["font","size_px","width_px","n","different_boxes","n_candidates","different_candidates"],checks)
                raise SystemExit(f"Boxes differ for {font} {size}px C/G={c}.")
        for policy,width in SETTINGS:
            if policy=="square":
                box = P.square_grid({**prep,**{edge:prep[edge][chosen] for edge in ("left","top","right","bottom")}},width,x,y)
                bits,hits = square_scores(prep,short["p"],chosen,x,y,width)
                area = obs_area(box,prep["tight_area"][chosen])
            else:
                if policy=="field":
                    *candidate_box,w,widest = P.field_box(prep)
                    fields.append((font,size,w,names[widest],prep["x_l"],prep["line_bottom"]-prep["line_top"]))
                elif policy=="start-aligned":
                    candidate_box = P.start_aligned_padding(prep,width)
                    analytics[width].append((size,P.class_entropy(short["p"],P.class_index(prep["right"],prep["x_l"],width))))
                else:
                    candidate_box = P.start_anchored_grid(prep,width)
                b,h = P.class_attack(short["p"],candidate_box[2])
                if policy=="field":
                    np.testing.assert_array_equal(b,np.zeros_like(b))
                bits,hits = b[chosen],h[chosen]
                box = [edge[chosen] for edge in candidate_box]
                area = obs_area(box,prep["tight_area"][chosen])
            scores[policy,width].append((size,np.column_stack((bits,hits,area))))
            all_cases[size].extend(zip([font]*N,[size]*N,[policy]*N,[width]*N,range(N),
                                      chosen,x,y,short["p"][chosen],*box,bits,hits,area))
    rows=[]
    for size in (*E.SIZES,"all"):
        for (policy,width),blocks in scores.items():
            analytic = np.mean([b for s,b in analytics[width] if size=="all" or s==size]) if policy=="start-aligned" else ""
            rows.append((size,policy,width,*summarize(blocks,size),analytic))
    CASES.mkdir(parents=True,exist_ok=True)
    for size,rows_at_size in all_cases.items():
        write_csv(CASES/f"cases_{size}px.csv.gz",
                  ["font","size_px","policy","width_px","case","entry","pen_x","baseline_y","prior",
                   "left_rel","top_rel","right_rel","bottom_rel","bits","hit10","area_ratio"],rows_at_size)
    write_csv(CASES/"paper_control.csv.gz",["font","size_px","case","entry","pen_x","baseline_y","bits","hit10","area_ratio"],control_cases)
    write_csv(DATA/"summary.csv",["size_px","policy","width_px","n","bits","ci_low","ci_high","top10_pct","median_area","analytic_bits"],rows)
    write_csv(DATA/"box_check.csv",["font","size_px","width_px","n","different_boxes","n_candidates","different_candidates"],checks)
    write_csv(DATA/"field_widths.csv",["font","size_px","width_px","widest_from_anchor","left_rel","height_px"],fields)
    metadata = dict(seconds=time.monotonic()-started, platform=platform.platform(), python=platform.python_version(),
                    pillow=PIL.__version__, numpy=np.__version__, census_sha256=sha(E.CENSUS),
                    renderer={name:features.version(name) for name in ("raqm","harfbuzz","fribidi","freetype2")},
                    target_seed=SEED, bootstrap_seed=BOOT, bootstrap_resamples=DRAWS, sources=sources)
    (DATA/"run.json").write_text(json.dumps(metadata,indent=2)+"\n")
    sums = [p for p in sorted(DATA.iterdir()) if p.suffix in {".csv",".json"} and p.name!="check_start128.csv"]
    sums += sorted(CASES.glob("*.csv.gz"))
    (DATA/"SHA256SUMS").write_text("".join(f"{sha(p)}  {p.relative_to(ROOT)}\n" for p in sums))
    print("Identical boxes",sum(r[3] for r in checks),"compared,",sum(r[4] for r in checks),"differ")
    print("Wall seconds",metadata["seconds"])


if __name__ == "__main__":
    main()
