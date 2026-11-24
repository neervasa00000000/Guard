#!/usr/bin/env python3
"""Figure 1 for 'How Much Does a Redaction Box Reveal?': the three box policies on one form field.

Schematic (relative widths, not measured values); pure matplotlib vector drawing.
Drawn at its printed width (5.0 in) so the text prints at 8.5-9 pt, in the same font as
Figures 2-6 and A1 (Source Sans Pro). Labels as in the manuscript: x_L (text start),
C (padding class width), F (field width).
Run:  python3 manuscript/figures/make_fig_policies.py [--out DIR]
      -> fig1.pdf and a 600-dpi fig1.png in out/paper_figures/
"""
import argparse, itertools, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import Rectangle

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser(); ap.add_argument("--out", default=None); args = ap.parse_args()
OUT = Path(args.out) if args.out else HERE.parents[1] / "out/paper_figures"; OUT.mkdir(parents=True, exist_ok=True)
try:
    fm.findfont(fm.FontProperties(family="Source Sans Pro"), fallback_to_default=False)
    FONT = "Source Sans Pro"
except Exception:
    FONT = "DejaVu Sans"; print("WARNING: Source Sans Pro not found, using DejaVu Sans")
FS = 8.5
matplotlib.rcParams.update({
    "font.family": FONT, "font.size": FS, "pdf.fonttype": 42,
    "mathtext.fontset": "custom", "mathtext.rm": FONT, "mathtext.it": f"{FONT}:italic",
    "savefig.facecolor": "white",
})
ORANGE, GREY, DARK = "#D55E00", "#999999", "#333333"
W_IN, H_IN = 5.0, 1.15
C, FIELD = 48, 104                      # class width C; field width F (schematic; 2C <= F)
NAMES = [("Short name", 30), ("Long name", 80)]   # padded: 1C and 2C
LINE_Y = [1.05, 0.05]
LINE_H, INK_LO, INK_HI = 0.8, 0.14, 0.66

fig, axes = plt.subplots(1, 3, figsize=(W_IN, H_IN), sharey=True)
fig.subplots_adjust(left=0.135, right=0.99, top=0.81, bottom=0.07, wspace=0.10)
titles = ["(a) Exact box", "(b) Start-aligned padding", "(c) Field box"]
for j, ax in enumerate(axes):
    ax.set_xlim(-8, 122); ax.set_ylim(-0.75, 2.0); ax.axis("off")
    ax.set_title(titles[j], fontsize=FS + 0.5, pad=3)
    for (label, w), y0 in zip(NAMES, LINE_Y):
        ax.add_patch(Rectangle((0, y0), FIELD, LINE_H, fill=False, ls=(0, (3, 2)), lw=0.7, ec=GREY, zorder=3))
        if j == 0:
            x1, ylo, yhi = w, y0 + INK_LO, y0 + INK_HI
        elif j == 1:
            k = -(-w // C); x1, ylo, yhi = C * k, y0, y0 + LINE_H
        else:
            x1, ylo, yhi = FIELD, y0, y0 + LINE_H
        ax.add_patch(Rectangle((0, ylo), x1, yhi - ylo, fc="black", ec="none"))
        if j == 0:
            ax.text(-12, y0 + LINE_H / 2, label, ha="right", va="center", clip_on=False)
    ax.plot([0, 0], [-0.25, 2.0], color=DARK, lw=0.9, zorder=4)            # text start x_L
    ax.text(0, -0.32, r"$x_{\mathrm{L}}$", color=DARK, va="top", ha="center")
    if j == 1:
        for m in (1, 2):
            ax.plot([m * C, m * C], [-0.25, 1.88], color=ORANGE, lw=0.8, ls=(0, (2, 1.5)), zorder=5)
        ax.text(2 * C, -0.32, r"$2C$", color=ORANGE, ha="center", va="top")
        ax.annotate("", xy=(0, -0.17), xytext=(C, -0.17),
                    arrowprops=dict(arrowstyle="<->", lw=0.6, shrinkA=0, shrinkB=0))
        ax.text(C / 2, -0.27, r"$C$", ha="center", va="top")
    if j == 2:
        ax.annotate("", xy=(0, -0.17), xytext=(FIELD, -0.17),
                    arrowprops=dict(arrowstyle="<->", lw=0.6, shrinkA=0, shrinkB=0))
        ax.text(FIELD / 2, -0.27, r"$F$", ha="center", va="top")

fig.canvas.draw(); r = fig.canvas.get_renderer()
texts = [t for ax in axes for t in ax.texts + [ax.title]]   # axes are off: tick labels are not drawn
boxes = [(t.get_text(), t.get_window_extent(r)) for t in texts if t.get_text().strip()]
bad = [(a[0], b[0]) for a, b in itertools.combinations(boxes, 2) if a[1].overlaps(b[1])]
Wd, Hd = fig.canvas.get_width_height()
bad += [("CLIPPED", n) for n, bb in boxes if bb.x0 < 1 or bb.y0 < 1 or bb.x1 > Wd - 1 or bb.y1 > Hd - 1]
for b in bad: print("LAYOUT:", b)
fig.savefig(OUT / "fig1.pdf"); fig.savefig(OUT / "fig1.png", dpi=600)
print("LAYOUT PROBLEMS:", len(bad)); sys.exit(1 if bad else 0)
