"""Verify the renderer-2 replay against the archived input, geometry and case files."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil

import numpy as np
import pandas as pd
import PIL
from PIL import features
import pymupdf


def setup():
    print(platform.platform(), platform.machine(), os.cpu_count())
    print("Python", platform.python_version(), "Pillow", PIL.__version__, "NumPy",
          np.__version__, "pandas", pd.__version__, "PyMuPDF", pymupdf.VersionBind)
    print({name: os.environ[name] for name in
           ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")})
    for name in ("raqm", "harfbuzz", "fribidi", "freetype2"):
        print(name, features.check(name), features.version(name))
    if PIL.__version__ != "12.3.0" or not features.check("raqm"):
        raise SystemExit("Pillow 12.3.0 with RAQM is required")
    manifest = Path("/kit/results/e1-full/data/fonts.json")
    for name, row in json.loads(manifest.read_text()).items():
        destination = Path(row["path"])
        matches = [path for path in Path("/fonts").rglob(destination.name)
                   if hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]]
        if len(matches) != 1:
            raise SystemExit(f"Missing exact font {name}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(matches[0], destination)
        print(name, row["sha256"], destination)


def geometry(ref, run):
    rows = []
    for name in ("forms_obs", "calib_obs"):
        old, new = (pd.read_csv(p / f"{name}.csv") for p in (ref, run))
        if len(old) != len(new) or list(old) != list(new):
            raise ValueError(f"{name} changed shape")
        for column in old:
            if column in ("angle", "pen_x_pdf", "pen_y_pdf"):
                mismatch = ~np.isclose(old[column], new[column], rtol=0, atol=1e-7)
            else:
                mismatch = old[column] != new[column]
            for index in np.flatnonzero(mismatch):
                rows.append(dict(dataset=name, row=index, field=column,
                                 archived=old.loc[index, column], replay=new.loc[index, column]))
        new.to_csv(Path("/out") / f"replayed_{name}.csv", index=False)
    if json.loads((ref / "tables_meta.json").read_text()) != json.loads(
        (run / "tables_meta.json").read_text()
    ):
        rows.append(dict(dataset="tables_meta", row="", field="metadata",
                         archived=(ref / "tables_meta.json").read_text(),
                         replay=(run / "tables_meta.json").read_text()))
    pd.DataFrame(rows, columns=["dataset", "row", "field", "archived", "replay"]).to_csv(
        "/out/libreoffice_geometry_diff.csv", index=False
    )
    print(f"LibreOffice geometry comparison: {len(rows)} differing values")
    if any(row["dataset"] != "calib_obs" for row in rows):
        raise SystemExit("Archived LibreOffice form geometry differs from regenerated geometry")
    if rows:
        print("Calibration differences will be checked against the archived hit counts")


def hits(ref, run, primary_only):
    keys = ["size", "cond", "variant", "attacker", "doc"]
    parts = [pd.read_csv(path / "r2_cases.csv").set_index(keys).sort_index()
             for path in (ref, run)]
    pd.testing.assert_index_equal(parts[0].index, parts[1].index)
    compare = parts[0][["hit10"]].rename(columns={"hit10": "archived"})
    compare["replay"] = parts[1].hit10
    result = compare.groupby(level=keys[:-1]).agg(n=("archived", "size"),
                                                   archived=("archived", "sum"),
                                                   replay=("replay", "sum"))
    result["delta_hits"] = result.replay - result.archived
    result.to_csv("/out/libreoffice_hit_check.csv")
    print(f"Largest absolute hit-count difference: {result.delta_hits.abs().max()}")
    checked = result
    if primary_only:
        checked = result.loc[result.index.get_level_values("attacker").isin(
            ("a_paper_renderer", "b_lo_table")
        )]
    if (checked.delta_hits.abs() > 1e-8).any():
        raise SystemExit("Archived LibreOffice hit counts differ from replay")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("setup", "inputs", "geometry", "hits"))
    parser.add_argument("reference", type=Path)
    parser.add_argument("replay", type=Path)
    parser.add_argument("--primary-only", action="store_true")
    args = parser.parse_args()
    ref, run = args.reference / "csv", args.replay / "csv"
    if args.stage == "setup":
        setup()
    elif args.stage == "inputs":
        for name in ("forms.json", "calibration_docs.json"):
            expected, actual = (json.loads((p / name).read_text()) for p in (ref, run))
            if expected != actual:
                raise SystemExit(f"Original seed did not regenerate {name}")
            print(f"{name}: all {len(actual)} archived records match")
    elif args.stage == "geometry":
        geometry(ref, run)
    else:
        hits(ref, run, args.primary_only)


if __name__ == "__main__":
    main()
