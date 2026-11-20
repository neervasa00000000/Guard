"""Figures from the result tables. Numbers are read, not typed."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
RESULTS = HERE / "results"
FIGURES = HERE / "figures"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard_rw as g
from run_validation import render_text


ORDER = ["exact", "square16", "square64", "width64", "start128", "field"]
LABELS = {
    "exact": "Exact",
    "square16": "Square 16",
    "square64": "Square 64",
    "width64": "Width 64",
    "start128": "Start 128",
    "field": "Field",
}


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    stats = json.loads((RESULTS / "statistics.json").read_text())
    attacks = pd.DataFrame(stats["attacks"])
    matched = attacks[attacks["attacker"] == "matched"].set_index("policy").loc[ORDER]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    x = np.arange(len(ORDER))
    ax.bar(x, matched["top10"] * 100, color="#1f4e79", width=0.7)
    ax.errorbar(
        x, matched["top10"] * 100,
        yerr=[
            (matched["top10"] - matched["top10_ci_low"]) * 100,
            (matched["top10_ci_high"] - matched["top10"]) * 100,
        ],
        fmt="none", ecolor="black", capsize=3,
    )
    nobox = float(matched["nobox_top10"].mean()) * 100
    ax.axhline(nobox, color="#b85c38", linestyle="--", label=f"No-box {nobox:.1f}%")
    ax.set_xticks(x, [LABELS[item] for item in ORDER])
    ax.set_ylabel("Top-10 identification (%)")
    ax.set_title("Matched attacker on test pages")
    ax.legend(frameon=False)
    ax.set_ylim(0, max(80, float(matched["top10_ci_high"].max()) * 100 + 5))
    fig.tight_layout()
    fig.savefig(FIGURES / "top10_matched.png", dpi=160)
    plt.close()

    utility = pd.DataFrame(stats["utility"])
    pooled = utility.groupby("policy")[["median_area_ratio", "mean_covered_words", "documents_with_neighbor_loss"]].mean().loc[ORDER]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar(x, pooled["median_area_ratio"], color="#4d6a4a")
    ax.set_xticks(x, [LABELS[item] for item in ORDER])
    ax.set_ylabel("Median area relative to the exact box")
    ax.set_title("Mask area on test pages")
    fig.tight_layout()
    fig.savefig(FIGURES / "area_ratio.png", dpi=160)
    plt.close()

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar(x - 0.15, pooled["mean_covered_words"], width=0.3, label="Neighbor words", color="#1f4e79")
    loss = utility.groupby("policy")["documents_with_neighbor_loss"].mean().loc[ORDER] * 10
    ax.bar(x + 0.15, loss, width=0.3, label="Share of pages with a loss, ×10", color="#b85c38")
    ax.set_xticks(x, [LABELS[item] for item in ORDER])
    ax.set_ylabel("Count")
    ax.set_title("Neighboring words covered")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIGURES / "utility.png", dpi=160)
    plt.close()

    by_attacker = attacks.pivot(index="policy", columns="attacker", values="top10").loc[ORDER]
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    by_attacker.plot(kind="bar", ax=ax, rot=0)
    ax.set_ylabel("Top-10")
    ax.set_title("Attacker knowledge")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES / "attackers.png", dpi=160)
    plt.close()

    # One court page with the six rectangles.
    measured = pd.read_csv(RESULTS / "policy_measurements.csv")
    page = measured[(measured.engine == "reportlab") & (measured.layout == "court") & (measured.split == "test")].iloc[0]
    name = page["name"]
    _data, _spans, doc = render_text("reportlab", g.layout_tokens("court", name), "Times")
    import pymupdf
    pix = doc[0].get_pixmap(dpi=g.DPI, colorspace=pymupdf.csGRAY, alpha=False)
    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    doc.close()
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    # Crop around the surname line.
    y0 = int(page["box_y0"]) - 80
    y1 = int(max(measured[(measured.name == name) & (measured.engine == "reportlab") & (measured.layout == "court")]["box_y1"])) + 80
    x0 = 80
    x1 = 700
    ax.imshow(image[y0:y1, x0:x1], cmap="gray", vmin=0, vmax=255)
    colors = ["#c0392b", "#1f4e79", "#4d6a4a", "#b85c38", "#6b4c9a", "#222222"]
    same = measured[(measured.name == name) & (measured.engine == "reportlab") & (measured.layout == "court") & (measured.split == "test")]
    for color, kind in zip(colors, ORDER):
        row = same[same.policy == kind].iloc[0]
        ax.add_patch(plt.Rectangle(
            (row.box_x0 - x0, row.box_y0 - y0), row.box_x1 - row.box_x0, row.box_y1 - row.box_y0,
            fill=False, edgecolor=color, linewidth=1.2, label=LABELS[kind],
        ))
    ax.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1))
    ax.set_axis_off()
    ax.set_title(f"Fictional court page, surname {name}")
    fig.tight_layout()
    fig.savefig(FIGURES / "example_boxes.png", dpi=160)
    plt.close()
    print(f"wrote figures for {name}")


if __name__ == "__main__":
    main()
