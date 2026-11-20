"""Schematic of the three box policies on one form field (Guard paper, Figure 1).

Pure matplotlib vector drawing (Rectangle, text, lines): no raster input.
Outputs fig_policies.pdf, fig_policies.svg and a 600-dpi fig_policies.png.
Widths are schematic (relative units), not measured values.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

matplotlib.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 7.5,
    "pdf.fonttype": 42, "svg.fonttype": "path",
})
W_IN, H_IN = 5.4, 0.9                # native size used in the manuscript
C, FIELD = 48, 104                    # class width C; field width W = widest layout right edge (schematic; 2C <= W, not rounded to C)
NAMES = [("Short name", 30), ("Long name", 80)]   # padded: 1C and 2C
LINE_Y = [1.05, 0.05]                  # bottom of each text line
LINE_H, INK_LO, INK_HI = 0.8, 0.14, 0.66   # full line height; layout box inside the line

fig, axes = plt.subplots(1, 3, figsize=(W_IN, H_IN), sharey=True)
fig.subplots_adjust(left=0.135, right=0.995, top=0.84, bottom=0.02, wspace=0.08)
titles = ["(a) Exact box", "(b) Start-aligned padding", "(c) Field box"]
for j, ax in enumerate(axes):
    ax.set_xlim(-8, 122); ax.set_ylim(-0.62, 2.0); ax.axis("off")
    ax.set_title(titles[j], fontsize=8, pad=3)
    for (label, w), y0 in zip(NAMES, LINE_Y):
        # the field on the form: dashed outline from the anchor x_L to the widest entry
        ax.add_patch(Rectangle((0, y0), FIELD, LINE_H, fill=False, ls=(0, (3, 2)),
                               lw=0.7, ec="0.6", zorder=3))
        if j == 0:
            x1, ylo, yhi = w, y0 + INK_LO, y0 + INK_HI
        elif j == 1:
            k = -(-w // C); x1, ylo, yhi = C * k, y0, y0 + LINE_H
        else:
            x1, ylo, yhi = FIELD, y0, y0 + LINE_H
        ax.add_patch(Rectangle((0, ylo), x1, yhi - ylo, fc="black", ec="none"))
        if j == 0:
            ax.text(-14, y0 + LINE_H / 2, label, ha="right", va="center",
                    fontsize=7.5, clip_on=False)
    # anchor tick x_L
    ax.plot([0, 0], [-0.25, 2.0], color="tab:red", lw=0.7, zorder=4)
    ax.text(0, -0.3, r"$x_L$", color="tab:red", fontsize=7, va="top", ha="center")
    if j == 1:
        for m in (1, 2):   # class boundaries at C and 2C, counted from x_L
            ax.plot([m * C, m * C], [-0.25, 1.88], color="tab:blue", lw=0.7,
                    ls=(0, (2, 1.5)), zorder=5)
        ax.text(2 * C, -0.3, r"$2C$", color="tab:blue", fontsize=7, ha="center", va="top")
        ax.annotate("", xy=(0, -0.17), xytext=(C, -0.17),
                    arrowprops=dict(arrowstyle="<->", lw=0.6, shrinkA=0, shrinkB=0))
        ax.text(C / 2, -0.25, r"$C$", ha="center", va="top", fontsize=7)
    if j == 2:
        ax.annotate("", xy=(0, -0.17), xytext=(FIELD, -0.17),
                    arrowprops=dict(arrowstyle="<->", lw=0.6, shrinkA=0, shrinkB=0))
        ax.text(FIELD / 2, -0.25, r"$W$", ha="center", va="top", fontsize=7)

for ext, kw in (("pdf", {}), ("svg", {}), ("png", {"dpi": 600})):
    fig.savefig(f"fig_policies.{ext}", **kw)
print("saved", W_IN, H_IN)
