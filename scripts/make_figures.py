#!/usr/bin/env python3
"""Draw Figures 1–6 from the tables regenerated from the archived CSVs."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "out" / "tables"
FIGS = ROOT / "out" / "figures"
BLUE = "#1f4e79"
ORANGE = "#c47b2b"
INK = "#222222"


def save(fig, name):
    FIGS.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGS / f"{name}.pdf")
    fig.savefig(FIGS / f"{name}.png", dpi=150)
    plt.close(fig)


def figure1():
    frame = pd.read_csv(TABLES / "table_a2.csv")
    pad = pd.read_csv(TABLES / "table3.csv")
    order = [(1, "exact"), (8, "8 px"), (16, "16 px"), (32, "32 px"), (64, "64 px")]
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.2), sharey=True)
    for ax, name, prior in zip(axes, ("surnames", "words"), (5.945, 23.795)):
        part = frame[(frame["list"] == name) & (frame.attacker == "A1")].set_index("grid_px")
        labels = ["no box"] + [label for _, label in order] + ["start 128"]
        vals = [prior] + [part.loc[grid, "top10"] for grid, _ in order]
        start = pad[(pad["list"] == name) & (pad.policy == "pen-anchored-128")].iloc[0].top10
        vals.append(start)
        colors = ["#8a8f98"] + [BLUE] * 5 + [ORANGE]
        ax.bar(range(len(vals)), vals, color=colors)
        ax.axhline(prior, color="#8a8f98", ls="--", lw=0.8)
        ax.set_xticks(range(len(labels)), labels, rotation=40, ha="right")
        ax.set_title(name)
        ax.set_ylabel("Top-10 (%)" if name == "surnames" else "")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    fig.suptitle("Figure 1. Top-10 under A1, clean layout boxes", color=INK)
    fig.tight_layout()
    save(fig, "figure1")


def figure2():
    frame = pd.read_csv(TABLES / "table3.csv")
    part = frame[frame["list"] == "surnames"]
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    ax.plot(part.area, part.bits_layout, "o", color=BLUE)
    for _, row in part.iterrows():
        ax.annotate(row.label.replace(" padding", "").replace(" grid", ""), (row.area, row.bits_layout), fontsize=7, textcoords="offset points", xytext=(4, 3))
    ax.set_xlabel("Median over-redaction")
    ax.set_ylabel("Bits leaked")
    ax.set_title("Figure 2. Surname leakage against area, A1, layout boxes")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    save(fig, "figure2")


def figure3():
    frame = pd.read_csv(TABLES / "table3.csv")
    want = ["exact", "square-64", "width-grid-64", "ink-anchored-128", "pen-anchored-128"]
    part = frame[(frame["list"] == "surnames") & (frame.policy.isin(want))].set_index("policy").loc[want]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    x = range(len(want))
    ax.bar([i - 0.16 for i in x], part.bits_layout, width=0.32, color=BLUE, label="layout")
    ink = part.bits_ink.fillna(0)
    ax.bar([i + 0.16 for i in x], ink, width=0.32, color=ORANGE, label="ink")
    ax.set_xticks(list(x), ["exact", "square 64", "width 64", "edge 128", "start 128"])
    ax.set_ylabel("Bits leaked")
    ax.set_title("Figure 3. Full line and start alignment, surnames, A1")
    ax.legend(frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    save(fig, "figure3")


def figure4():
    copies = pd.read_csv(TABLES / "figure4a.csv")
    values = pd.read_csv(TABLES / "values.csv").set_index("id").value
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.2))
    ax = axes[0]
    for name, color in (("surnames", BLUE), ("words", ORANGE)):
        part = copies[(copies.series == "grid") & (copies["list"] == name) & (copies.grid_px == 16)].sort_values("k")
        ax.plot(part.k, part.top10, marker="o", color=color, label=f"{name}, 16 px grid")
    pad = copies[copies.series == "pad"].sort_values("k")
    if not pad.empty:
        ax.plot(pad.k, pad.top10, marker="s", color="#5b7c5a", label="surname padding")
    ax.set_xticks([1, 2, 3, 5])
    ax.set_xlabel("Copies k")
    ax.set_ylabel("Top-10 (%)")
    ax.set_title("(a) Differently aligned copies")
    ax.legend(frameon=False, fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax = axes[1]
    labels = ["unjittered\nmask", "one jittered\nrelease", "five jittered\nreleases", "one font\nmix", "five font\nmixes"]
    vals = [values["fig4b.unjittered.bits"], values["fig4b.jitter.k1.bits"], values["fig4b.jitter.k5.bits"], values["fig4b.font.k1.bits"], values["fig4b.font.k5.bits"]]
    ax.bar(range(5), vals, color=[BLUE, ORANGE, ORANGE, BLUE, ORANGE])
    ax.set_xticks(range(5), labels, fontsize=8)
    ax.set_ylabel("Bits")
    ax.set_title("(b) Changed releases")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.suptitle("Figure 4. Several releases")
    fig.tight_layout()
    save(fig, "figure4")


def figure5():
    values = pd.read_csv(TABLES / "values.csv").set_index("id").value
    forms = pd.read_csv(TABLES / "table_a3.csv").set_index("key")
    labels = ["known font", "font unknown", "uniform prior", "LibreOffice\nmatched", "Pillow model\non LibreOffice"]
    vals = [values["fig5.known.top10"], values["fig5.font_unknown.top10"], values["fig5.uniform.top10"], forms.loc["lo16c", "exact"], forms.loc["lopm", "exact"]]
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    ax.bar(range(5), vals, color=[BLUE, ORANGE, ORANGE, BLUE, ORANGE])
    ax.axhline(5.945, color="#8a8f98", ls="--", lw=0.8, label="no box, synthetic")
    ax.set_xticks(range(5), labels)
    ax.set_ylabel("Surname top-10 (%)")
    ax.set_title("Figure 5. What the attacker must know")
    ax.legend(frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    save(fig, "figure5")


def figure6():
    forms = pd.read_csv(TABLES / "table_a3.csv")
    want = ["lo16c", "lo16s", "pA1"]
    labels = ["LibreOffice\nclean", "LibreOffice\nscan", "Pillow\nclean"]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    width = 0.2
    series = [("exact", "exact", BLUE), ("g16", "16 px", ORANGE), ("start", "start 128", "#5b7c5a")]
    for i, (col, label, color) in enumerate(series):
        vals = [forms.set_index("key").loc[key, col] for key in want]
        ax.bar([x + (i - 1) * width for x in range(3)], vals, width=width, label=label, color=color)
    ax.set_xticks(range(3), labels)
    ax.set_ylabel("Surname top-10 (%)")
    ax.set_title("Figure 6. Template-controlled mock forms")
    ax.legend(frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    save(fig, "figure6")


def main():
    figure1()
    figure2()
    figure3()
    figure4()
    figure5()
    figure6()
    print(f"Wrote {FIGS}")


if __name__ == "__main__":
    main()
