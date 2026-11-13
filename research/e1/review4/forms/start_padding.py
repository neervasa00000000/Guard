"""Score the review4 start-aligned policy on the published surname forms."""

import csv
import json
import math
from pathlib import Path
import sys

import numpy as np
import pandas as pd

import attack as A
import e1lib as E
import r2lib as R
from geometry import Geometry, Policy, ceil_multiple

OUT = Path("/out")
POLICY = Policy("pen-anchored", 128)
POLICIES = ("exact", "16px", "64px", "D2_pad128", "start128")
ATTACKERS = {"b_lo_table": "Matched", "a_paper_renderer": "Pillow mismatch"}
BOOTSTRAP_SEED = 20261117
RESAMPLES = 4000


def start_box(frame, x, y, tight):
    x0, y0, x1, y1 = tight
    left = x + frame.fixed_left
    right = left + int(ceil_multiple(x1 - left, POLICY.width))
    top, bottom = frame.vertical(POLICY, y)
    covers = left <= x0 and top <= y0 and y1 <= bottom
    return (left, right, top, bottom), covers


def mapped_start(row, layout_x, run):
    y = row.pen_y_pdf
    if row.cond == "clean":
        return layout_x, round(y)
    # Original scan_page affine map applied to the template column, using
    # the original page centre and baseline before rounding.
    height, width = R.raster(str(run / f"work/pdf/form{row.doc:03d}_{row.size}.pdf"))[0].shape
    cx, cy = width / 2, height / 2
    angle = math.radians(row.angle)
    def rotate(x):
        dx, dy = x - cx, y - cy
        return (round(cx + dx * math.cos(angle) + dy * math.sin(angle)),
                round(cy - dx * math.sin(angle) + dy * math.cos(angle)))

    assert rotate(row.pen_x_pdf) == (row.pen_x, row.pen_y)
    return rotate(layout_x)


def libreoffice(run):
    observations = pd.read_csv(run / "csv/forms_obs.csv")
    layout = pd.read_csv(OUT / "libreoffice_layout_start.csv")
    starts = layout.set_index(["doc", "size_px"]).layout_start
    assert layout["match"].all()
    frames = {}
    for key, bounds in A.GL.items():
        ascent, descent = E.font(*key).getmetrics()
        frames[key] = Geometry(bounds, -ascent, descent)
    results = []
    for row in observations.itertuples(index=False):
        key = row.font, row.size
        x, y = mapped_start(row, int(starts.loc[row.doc, row.size]), run)
        tight = (row.ink_x0 - 1, row.ink_y0 - 1, row.ink_x1 + 1, row.ink_y1 + 1)
        frame = frames[key]
        box, covers = start_box(frame, x, y, tight)
        left, right, top, bottom = box
        width = right - left
        area = (tight[2] - tight[0]) * (tight[3] - tight[1])
        for attacker, candidate_bounds, tol_key in (
            ("b_lo_table", A.GL[key], "lo_tab"), ("a_paper_renderer", A.GP[key], "pil")
        ):
            _, _, (dr0, dr1), _ = A.TOL[tol_key, *key, row.cond]
            # The template and fixed policy anchor are public to both A1
            # attackers. Propagate their published right-edge tolerance
            # through the bucket using each attacker's geometry.
            span = candidate_bounds[:, 2].astype(np.int64) + E.PAD - frame.fixed_left
            feasible = ((ceil_multiple(span + dr0, POLICY.width) <= width) &
                        (width <= ceil_multiple(span + dr1, POLICY.width)))
            score = E.metrics(A.D, feasible, row.truth_idx, len(row.truth), A.LOGP)
            results.append(dict(
                doc=row.doc, font=row.font, size=row.size, cond=row.cond,
                renderer="LibreOffice", field="surname", attacker=attacker,
                variant="start128", hit10=score["hit10"], truth_in=score["truth_in"],
                n_feasible=int(feasible.sum()), over=width * (bottom - top) / area,
                layout_start_x=x, layout_baseline_y=y, published_pen_x=row.pen_x,
                published_pen_y=row.pen_y, left=left, right=right, top=top, bottom=bottom,
                covers_tight_box=covers,
                missed_margin_px=max(0, left - tight[0], top - tight[1], tight[3] - bottom),
                missed_ink_bbox_px=max(0, left-row.ink_x0, top-row.ink_y0, row.ink_y1-bottom),
            ))
    return pd.DataFrame(results)


def pillow():
    docs = json.loads(Path("/test3_docs.json").read_text())
    frames = {}
    for font in {doc["font"] for doc in docs}:
        asc, desc = E.font(font, 16).getmetrics()
        frames[font] = Geometry(A.GP[font, 16], -asc, desc)
    results = []
    for doc in docs:
        font = doc["font"]
        x, y = doc["margin"] + 200, 200
        target = doc["surname_idx"]
        truth = doc["surname"]
        bounds = A.GP[font, 16]
        frame = frames[font]
        tight = E.tight_box(tuple(bounds[target]), x, y, 0, None)
        area = (tight[2] - tight[0]) * (tight[3] - tight[1])
        for variant, grid in (("exact", 1), ("16px", 16), ("64px", 64),
                              ("D2_pad128", 1), ("start128", 1)):
            if variant == "start128":
                box, covers = start_box(frame, x, y, tight)
                left, right = frame.horizontal(POLICY)
                top, bottom = frame.vertical(POLICY, 0)
                candidate = np.column_stack((left + E.PAD, np.full(len(left), top + E.PAD),
                                             right - E.PAD, np.full(len(left), bottom - E.PAD)))
                assert covers
            else:
                padded = variant == "D2_pad128"
                candidate = E.bucket_transform(bounds, font, 16) if padded else bounds
                original = E.tight_box(tuple(candidate[target]), x, y, 0, None) if padded else tight
                box = E.snapped(original, grid)
                covers = True
            cell = E.Cell(candidate, ((0, 0),) * 4, 0)
            for attacker in ("A1", "A2"):
                feasible = cell.feasible([box], [(x if attacker == "A1" else 0, y)], grid, attacker)
                score = E.metrics(A.D, feasible, target, len(truth), A.LOGP)
                results.append(dict(doc=doc["doc"], font=font, size=16, cond="clean",
                                    renderer="Pillow", field="surname", attacker=attacker,
                                    variant=variant, hit10=score["hit10"], truth_in=score["truth_in"],
                                    n_feasible=int(feasible.sum()), covers_tight_box=covers,
                                    over=(box[1] - box[0]) * (box[3] - box[2]) / area))
    return pd.DataFrame(results)


def summarize(cases):
    rows, diffs = [], []
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    for keys, group in cases.groupby(["renderer", "size", "cond", "attacker"], sort=True):
        base = dict(zip(("renderer", "size", "condition", "attacker"), keys), field="surname")
        pivot = group.pivot(index="doc", columns="variant", values="hit10")
        assert len(pivot) == 100 and set(pivot.columns) == set(POLICIES)
        assert not pivot.isna().any().any()
        for policy in POLICIES:
            hits = pivot[policy].sum()
            lo, hi = E.wilson(hits, len(pivot))
            area = group.loc[group.variant == policy, "over"].median()
            rows.append(dict(base, policy=policy, hits=hits, n=len(pivot),
                             wilson_low=100 * lo, wilson_high=100 * hi, median_area_ratio=area))
        diff = (pivot["16px"] - pivot["start128"]).to_numpy() * 100
        draws = rng.integers(0, len(diff), size=(RESAMPLES, len(diff)))
        lo, hi = np.percentile(diff[draws].mean(axis=1), [2.5, 97.5])
        diffs.append(dict(base, difference_points=diff.mean(), ci_low=lo, ci_high=hi, n=len(diff)))
    return pd.DataFrame(rows), pd.DataFrame(diffs)


def main():
    ref, run = (Path(p) for p in sys.argv[1:])
    lo = libreoffice(run)
    lo.to_csv(OUT / "libreoffice_start_cases.csv", index=False)
    coverage = lo.drop_duplicates(["doc", "size", "cond"])
    print(coverage.groupby(["size", "cond"]).covers_tight_box.agg(["sum", "size"]))
    print("Template-mapped x differs from the rounded PDF-origin x on",
          int((coverage.layout_start_x != coverage.published_pen_x).sum()), "observations")
    if not coverage.covers_tight_box.all():
        print("Coverage warning: at least one box fails to contain the complete padded target")
    originals = pd.read_csv(ref / "csv/r2_cases.csv")
    originals = originals[originals.attacker.isin(ATTACKERS) &
                          originals.variant.isin(POLICIES[:-1])]
    originals = originals.assign(renderer="LibreOffice", field="surname")
    pil = pillow()
    controls = pd.read_csv(OUT / "pillow_surname_sanity.csv")
    measured = pil.groupby(["attacker", "variant"]).hit10.sum()
    for row in controls.itertuples(index=False):
        assert math.isclose(measured.loc[row.attacker, "D2_pad128" if row.policy == "D2_bucket128" else row.policy], row.replay_hits,
                            rel_tol=0, abs_tol=1e-9)
    pil.to_csv(OUT / "pillow_start_cases.csv", index=False)
    summary, paired = summarize(pd.concat([originals, lo, pil], ignore_index=True))
    summary.to_csv(OUT / "start_policy_summary.csv", index=False)
    paired.to_csv(OUT / "start_vs_grid16_paired.csv", index=False)
    print(summary.to_string(index=False))
    print(paired.to_string(index=False))


if __name__ == "__main__":
    main()
