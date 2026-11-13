"""Rebuild the paper tables and figures from the stored summary CSVs."""
import csv
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
TABLES = OUT / "tables"
FIGS = OUT / "figures"
CLEAN = ROOT / "results" / "paper" / "e1" / "pooled_clean_dict_grid_attacker.csv"
POOLED = ROOT / "research" / "e1" / "review4" / "pooled.csv"
POLICY_GRID = {"exact": 1, "square-8": 8, "square-16": 16, "square-32": 32, "square-64": 64}


def a2_from_pooled(frame):
    """Replace the A2 column with the size-pooled LAYOUT-BOX rows in pooled.csv."""
    pooled = pd.read_csv(POOLED)
    pooled = pooled[
        (pooled.model == "LAYOUT-BOX")
        & (pooled.attacker == "A2")
        & (pooled.size_px.astype(str) == "all")
        & (pooled.policy.isin(POLICY_GRID))
    ]
    out = frame.copy()
    seen = set()
    for row in pooled.itertuples(index=False):
        grid = POLICY_GRID[row.policy]
        mask = (out["dict"] == row.list) & (out.grid_px == grid) & (out.attacker == "A2")
        if int(mask.sum()) != 1:
            raise ValueError(f"A2 cell missing from the clean table: {row.list} {row.policy}")
        out.loc[mask, ["top10", "bits_leaked", "over_median", "n"]] = [
            row.top10, row.bits, row.median_overredaction, row.n]
        seen.add((row.list, grid))
    expected = {(r.dict, int(r.grid_px)) for r in out.itertuples(index=False) if r.attacker == "A2"}
    if seen != expected:
        raise ValueError(f"A2 cells not taken from pooled.csv: {sorted(expected - seen)}")
    return out


def write_clean_table(frame):
    lines = ["# Clean pooled leakage", "",
             "| List | Grid | Attacker | Top-10 % | Bits | Median area | n |",
             "|---|---:|---|---:|---:|---:|---:|"]
    order = {"surnames": 0, "words": 1, "emails": 2, "dates": 3, "digits": 4}
    view = frame.sort_values(["dict", "grid_px", "attacker"], key=lambda s: s.map(order) if s.name == "dict" else s)
    for row in view.itertuples(index=False):
        grid = "exact" if row.grid_px == 1 else str(int(row.grid_px))
        lines.append(
            f"| {row.dict} | {grid} | {row.attacker} | {row.top10 * 100:.1f} | "
            f"{row.bits_leaked:.2f} | {row.over_median:.2f} | {int(row.n)} |")
    (TABLES / "table_clean.md").write_text("\n".join(lines) + "\n")


def figures(frame):
    grids = [1, 8, 16, 32, 64]
    labels = ["exact", "8", "16", "32", "64"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for name in ("surnames", "words"):
        part = frame[(frame["dict"] == name) & (frame.attacker == "A1")].set_index("grid_px").loc[grids]
        ax.plot(range(5), part.bits_leaked, marker="o", label=name)
    ax.set_xticks(range(5), labels)
    ax.set_xlabel("Grid (px)")
    ax.set_ylabel("Bits leaked")
    ax.set_title("Figure 1 source: bits leaked on clean renders")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGS / "fig1_bits.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for name in ("surnames", "words"):
        part = frame[(frame["dict"] == name) & (frame.attacker == "A1")].set_index("grid_px").loc[grids]
        ax.plot(part.over_median, part.bits_leaked, marker="o", label=name)
    ax.set_xlabel("Median over-redaction")
    ax.set_ylabel("Bits leaked")
    ax.set_title("Figure 3 source: leakage against area")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGS / "fig3_tradeoff.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for attacker, style in (("A1", "-"), ("A2", "--")):
        part = frame[(frame["dict"] == "surnames") & (frame.attacker == attacker)].set_index("grid_px").loc[grids]
        ax.plot(range(5), part.top10 * 100, linestyle=style, marker="o", label=attacker)
    ax.set_xticks(range(5), labels)
    ax.set_ylabel("Top-10 (%)")
    ax.set_title("Figure 2 source: surname top-10 by grid")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGS / "fig2_top10.png", dpi=150)
    plt.close(fig)


def copy_reports():
    pairs = [
        ROOT / "research/e1/review4/forms/FORMS_START_RESULTS.md",
        ROOT / "research/e1/review4/a3_start/RESULTS.md",
        ROOT / "research/e1/mdpi_checks/posterior_toy/POSTERIOR_CHECK.md",
        ROOT / "research/e1/mdpi_checks/paired_stats/PAIRED_STATS.md",
        ROOT / "research/e1/mdpi_checks/number_audit/NUMBER_AUDIT.md",
    ]
    for path in pairs:
        if path.exists():
            shutil.copy(path, TABLES / path.name)


def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    if not CLEAN.exists():
        print("CLEAN POOL NOT FOUND")
        return 1
    frame = a2_from_pooled(pd.read_csv(CLEAN))
    write_clean_table(frame)
    figures(frame)
    copy_reports()
    named = frame.query("attacker == 'A2' and ((dict == 'surnames' and grid_px == 8) or (dict == 'words' and grid_px == 16))")
    for row in named.itertuples(index=False):
        print(f"A2 from {POOLED.relative_to(ROOT)}: {row.dict} {int(row.grid_px)} px {row.top10 * 100:.1f}/{row.bits_leaked:.2f}")
    print(f"Wrote {TABLES} and {FIGS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
