"""Figures for the FUNSD validation. Reads the saved tables and does not rescore."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from funsd_real import DATASET, OUT, inclusive_to_half_open, policy_half_open, read_table

FIGURES = OUT / "figures"
BLUE = "#0072B2"
VERMILION = "#D55E00"
GREEN = "#009E73"
BLACK = "#222222"
GRAY = "#666666"


def style():
    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.6,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.bbox": "tight",
        "savefig.facecolor": "white",
    })


def save(figure, name):
    FIGURES.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURES / f"{name}.pdf")
    figure.savefig(FIGURES / f"{name}.png", dpi=300)
    plt.close(figure)


def figure_exclusions(entities):
    counts = entities.loc[~entities["eligible"], "exclusion"].value_counts()
    labels = {
        "vertical_word": "Vertical word",
        "multiline": "More than one line",
        "vertical_entity": "Vertical entity",
        "empty_text": "Empty text",
        "text_word_mismatch": "Text disagrees with words",
        "too_long": "Longer than 80 characters",
        "insufficient_ink": "Too little ink",
    }
    order = [key for key in labels if key in counts.index]
    values = [int(counts[key]) for key in order]
    figure, axis = plt.subplots(figsize=(6.4, 3.6))
    axis.barh([labels[key] for key in order][::-1], values[::-1], color=BLUE)
    axis.set_xlabel("Answer entities excluded")
    axis.set_title("Why an answer was left out of the scored set")
    save(figure, "funsd_exclusions")


def figure_width_length(entities, model):
    test = entities[(entities["eligible"]) & (entities["split"] == "testing")]
    figure, axis = plt.subplots(figsize=(6.2, 4.2))
    axis.scatter(test["length"], test["width"], s=12, c=BLUE, alpha=0.45, linewidths=0, label="Test fields")
    grid = np.linspace(1, max(40, test["length"].max()), 50)
    axis.plot(grid, model["intercept"] + model["slope"] * grid, color=VERMILION, lw=1.4, label="Training fit")
    axis.set_xlabel("Characters in the annotated answer")
    axis.set_ylabel("Inclusive box width (pixels)")
    axis.set_title("Scanned answer width tracks string length")
    axis.legend(frameon=False)
    save(figure, "funsd_width_length")


def figure_area(summary):
    frame = summary[(summary["regime"] == "length_width") & (summary["policy"] != "no_box") & (summary["status"] == "measured")].copy()
    # Start-aligned rows repeat the width-grid geometry. Show them once.
    frame = frame[~frame["policy"].str.startswith("start_aligned")]
    labels = {
        "exact": "Exact",
        "square_grid_8": "Square 8",
        "square_grid_16": "Square 16",
        "square_grid_32": "Square 32",
        "square_grid_64": "Square 64",
        "width_grid_32": "Width 32",
        "width_grid_64": "Width 64",
        "width_grid_128": "Width 128",
    }
    frame["label"] = frame["policy"].map(labels)
    figure, axis = plt.subplots(figsize=(6.8, 3.8))
    x = np.arange(len(frame))
    axis.bar(x, frame["median_area_ratio"], color=[BLUE if "square" in p else (GREEN if "width" in p else BLACK) for p in frame["policy"]])
    yerr = np.vstack([
        frame["median_area_ratio"] - frame["median_area_ratio_ci_low"],
        frame["median_area_ratio_ci_high"] - frame["median_area_ratio"],
    ])
    axis.errorbar(x, frame["median_area_ratio"], yerr=yerr, fmt="none", ecolor=BLACK, elinewidth=0.8, capsize=2)
    axis.set_xticks(x, frame["label"], rotation=30, ha="right")
    axis.set_ylabel("Median area relative to the exact box")
    axis.set_title("Controlled boxes grow as the grid gets coarser")
    save(figure, "funsd_area")


def figure_leakage(summary):
    frame = summary[(summary["regime"] == "length_width") & (summary["status"] == "measured")].copy()
    frame = frame[~frame["policy"].str.startswith("start_aligned")]
    labels = ["No box", "Exact", "Sq 8", "Sq 16", "Sq 32", "Sq 64", "W 32", "W 64", "W 128"]
    figure, axes = plt.subplots(1, 2, figsize=(7.4, 3.6))
    x = np.arange(len(frame))
    axes[0].errorbar(
        x, frame["entropy_reduction"],
        yerr=np.vstack([
            frame["entropy_reduction"] - frame["entropy_reduction_ci_low"],
            frame["entropy_reduction_ci_high"] - frame["entropy_reduction"],
        ]),
        fmt="o", color=BLUE, ms=4,
    )
    axes[0].set_ylabel("Dictionary entropy reduction (bits)")
    axes[1].errorbar(
        x, frame["top10"] * 100,
        yerr=np.vstack([
            (frame["top10"] - frame["top10_ci_low"]) * 100,
            (frame["top10_ci_high"] - frame["top10"]) * 100,
        ]),
        fmt="o", color=VERMILION, ms=4,
    )
    axes[1].set_ylabel("Top-10 recovery (%)")
    axes[1].set_ylim(0, max(12, float(frame["top10_ci_high"].max()) * 100 + 0.5))
    for axis in axes:
        axis.set_xticks(x, labels, rotation=40, ha="right")
    figure.suptitle("Extra-knowledge length model on held-out FUNSD answers", y=1.02)
    save(figure, "funsd_recovery")


def figure_mismatch(summary):
    policies = ["no_box", "exact", "square_grid_16", "width_grid_128"]
    regimes = ["length_width", "mismatch_Arial", "mismatch_TimesNewRoman", "mismatch_CourierNew"]
    names = ["Length model", "Arial", "Times", "Courier"]
    figure, axis = plt.subplots(figsize=(6.6, 3.8))
    width = 0.18
    for i, (regime, name) in enumerate(zip(regimes, names)):
        rows = []
        for policy in policies:
            row = summary[(summary["regime"] == regime) & (summary["policy"] == policy)].iloc[0]
            rows.append(float(row["entropy_reduction"]))
        axis.bar(np.arange(len(policies)) + (i - 1.5) * width, rows, width=width, label=name)
    axis.set_xticks(np.arange(len(policies)), ["No box", "Exact", "Square 16", "Width 128"])
    axis.set_ylabel("Dictionary entropy reduction (bits)")
    axis.set_title("Mismatched fonts do not reproduce a matched-renderer attack")
    axis.legend(frameon=False, ncol=2)
    save(figure, "funsd_mismatch")


def figure_example(entities):
    test = entities[(entities["eligible"]) & (entities["split"] == "testing")].copy()
    alphabetic = test[test["text"].str.fullmatch(r"[A-Za-z][A-Za-z ]{5,16}")]
    pool = alphabetic if len(alphabetic) else test
    median = pool["width"].median()
    chosen = pool.iloc[(pool["width"] - median).abs().argmin()]
    image_path = DATASET / "testing_data" / "images" / f"{chosen['doc_id']}.png"
    with Image.open(image_path) as image:
        gray = image.convert("L")
    half = inclusive_to_half_open((int(chosen.x0), int(chosen.y0), int(chosen.x1), int(chosen.y1)))
    exact = policy_half_open("exact", half, 0)
    grid = policy_half_open("square_grid", half, 32)
    pad = 18
    x0 = max(0, min(exact[0], grid[0]) - pad)
    y0 = max(0, min(exact[1], grid[1]) - pad)
    x1 = min(gray.width, max(exact[2], grid[2]) + pad)
    y1 = min(gray.height, max(exact[3], grid[3]) + pad)
    panels = []
    for box, fill in ((None, False), (exact, True), (grid, True)):
        panel = gray.crop((x0, y0, x1, y1)).convert("RGB")
        if fill:
            draw = ImageDraw.Draw(panel)
            draw.rectangle((box[0] - x0, box[1] - y0, box[2] - x0 - 1, box[3] - y0 - 1), fill=(0, 0, 0))
        panels.append(panel)
    figure, axes = plt.subplots(1, 3, figsize=(7.2, 2.6))
    titles = ["Original crop", "Exact black box", "Square grid, 32 px"]
    for axis, panel, title in zip(axes, panels, titles):
        axis.imshow(panel, cmap="gray")
        axis.set_title(title, fontsize=10)
        axis.set_xticks([])
        axis.set_yticks([])
        for spine in axis.spines.values():
            spine.set_visible(True)
            spine.set_color("#cccccc")
    figure.suptitle("Controlled redaction of one held-out FUNSD answer", fontsize=11)
    save(figure, "funsd_example")
    return {"doc_id": str(chosen["doc_id"]), "entity_id": int(chosen["entity_id"]), "length": int(chosen["length"])}


def main():
    style()
    entities = read_table(OUT / "answer_entities.csv")
    summary = read_table(OUT / "summary.csv")
    import json
    model = json.loads((OUT / "manifest.json").read_text())["length_model"]
    figure_exclusions(entities)
    figure_width_length(entities, model)
    figure_area(summary)
    figure_leakage(summary)
    figure_mismatch(summary)
    example = figure_example(entities)
    (FIGURES / "example.json").write_text(json.dumps(example, indent=2) + "\n")
    print("figures written", example)


if __name__ == "__main__":
    main()
