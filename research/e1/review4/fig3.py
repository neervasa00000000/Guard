"""Rerun the published Fig. 3 known-font/size baseline (K)."""

import argparse
import csv
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from font_stats import font_draws


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kit", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    script = args.kit / "results/e1-followup/test4/test4_imperfect.py"
    source = script.read_text()
    # Preserve target draws, geometry, feasibility and scoring of K. Avoid
    # computing unknown/wrong-font alternatives outside the requested baseline.
    source = source.replace("N=500;", "N=2000;", 1)
    source = source.replace("GEO={(f,s):E.geometry(dn,f,s) for f in FONTS for s in SIZES}",
                            "GEO={(f,SZ):E.geometry(dn,f,SZ) for f in FONTS}")
    start = source.index("    CELL=")
    stop = source.index("    for tf in FONTS:", start)
    source = source[:start] + "    CELL={k:E.Cell(g,Z,0) for k,g in GEO.items()}\n" + source[stop:]
    source = source.replace(
        "M={(f,s):CELL[(f,s,'0')].feasible(obs,sh,g,att) for f in FONTS for s in SIZES}",
        "M={(tf,SZ):CELL[(tf,SZ)].feasible(obs,sh,g,att)}",
    )
    start = source.index("                    rec('Fu'")
    stop = source.index("        print(dn,tf", start)
    source = source[:start] + source[stop:]
    source = source[:source.index("d=pd.DataFrame(rows)")]
    env = {"__file__": str(script)}
    sys.path.insert(0, str(args.kit / "results/e1-full/scripts"))
    exec(compile(source, str(script), "exec"), env)
    d = pd.DataFrame(env["rows"])
    d.to_csv(args.output / "fig3_cases.csv.gz", index=False,
             compression={"method": "gzip", "mtime": 0})
    output = []
    metrics = ("hit1", "hit10", "bits_leaked")
    rng_seed = env["SEED"]
    for (name, grid, attacker), rows in d.groupby(["dict", "grid_px", "attacker"]):
        means = rows.groupby("true_font")[list(metrics)].mean()
        draws = font_draws(means.index, rng_seed)
        boot = (draws @ means.to_numpy()) / len(means)
        low, high = np.quantile(boot, [0.025, 0.975], axis=0)
        row = dict(dict=name, size_px=env["SZ"], grid_px=grid, attacker=attacker,
                   variant="K", seed=rng_seed, n=len(rows))
        for metric, value, lo, hi in zip(metrics, means.mean(), low, high):
            row.update({metric: value, f"{metric}_ci_low": lo, f"{metric}_ci_high": hi})
        output.append(row)
    with (args.output / "fig3_baseline.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    print(f"Fig. 3 baseline finished, seed={rng_seed}, wall_s={env['time'].time()-env['t0']:.2f}")


if __name__ == "__main__":
    main()
