#!/usr/bin/env python3
"""Figure 5 for 'How Much Does a Redaction Box Reveal?': anchor margins.

Reads data/anchor_margin/summary.csv (written by scripts/run_anchor_margin.py). Rows used:
  (a) policy = start-aligned, C_px = 128, template_error in {clean, start_uniform_-4_4},
      margin_px in {0, 2, 4, 8, 16}: the largest max_pointwise_bits over the 18 font-size cells;
      filled marker if that worst-off person is alone in the class (max_class_names = 1).
      Zero line: policy = fixed-field and (start-aligned, C_px = 256): max_pointwise_bits = 0 in
      every cell, margin and template error (checked).
  (b) template_error = clean: mean over the 18 cells of extra_area_vs_m0 (x 100), for
      start-aligned C_px = 128 and fixed-field.
Run:  python3 manuscript/figures/make_fig_margins.py [--repo /path/to/Guard] [--out DIR]
Writes fig5.pdf and a 600-dpi fig5.png (default out/paper_figures/). Exit 1 on a layout problem.
"""
import argparse, csv, itertools, os, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--repo", default=os.environ.get("GUARD_ROOT"))
ap.add_argument("--out", default=None)
args = ap.parse_args()
ROOT = Path(args.repo) if args.repo else HERE.parents[1]
SUMMARY = ROOT / "data/anchor_margin/summary.csv"
if not SUMMARY.exists():
    sys.exit(f"{SUMMARY} not found: run inside the Guard repository or pass --repo /path/to/Guard")
OUT = Path(args.out) if args.out else ROOT / "out/paper_figures"; OUT.mkdir(parents=True, exist_ok=True)

W = 5.0
try:
    fm.findfont(fm.FontProperties(family="Source Sans Pro"), fallback_to_default=False)
    FONT = "Source Sans Pro"
except Exception:
    FONT = "DejaVu Sans"; print("WARNING: Source Sans Pro not found, using DejaVu Sans")
FS = 8.5
plt.rcParams.update({
    "font.family": FONT, "font.size": FS, "axes.titlesize": FS + 0.5, "axes.titleweight": "bold",
    "axes.labelsize": FS + 0.5, "xtick.labelsize": FS, "ytick.labelsize": FS, "legend.fontsize": FS,
    "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.7,
    "axes.edgecolor": "#333333", "xtick.color": "#333333", "ytick.color": "#333333",
    "axes.titlelocation": "left", "axes.titlepad": 6, "pdf.fonttype": 42,
    "grid.color": "#E4E4E4", "grid.linewidth": 0.6, "legend.frameon": False,
    "savefig.facecolor": "white",
})
START, FIELD = "#D55E00", "#000000"
MARGINS = [0, 2, 4, 8, 16]

rows = list(csv.DictReader(open(SUMMARY, newline="")))
def sel(**kw):
    out = [r for r in rows if all(r[k] == str(v) for k, v in kw.items())]
    return out

# (a) worst-off person over the 18 font-size cells
A = {}
for te in ("clean", "start_uniform_-4_4"):
    for m in MARGINS:
        s = sel(policy="start-aligned", C_px=128, template_error=te, margin_px=m)
        assert len(s) == 18, (te, m, len(s))
        top = max(float(r["max_pointwise_bits"]) for r in s)
        names = sorted({int(r["max_class_names"]) for r in s if abs(float(r["max_pointwise_bits"]) - top) < 1e-9})
        A[(te, m)] = (top, names[0] == 1, names)
zero = [r for r in rows if r["policy"] == "fixed-field" or (r["policy"] == "start-aligned" and r["C_px"] == "256")]
zero_max = max(float(r["max_pointwise_bits"]) for r in zero)
assert zero_max == 0.0, zero_max
# (b) extra area, clean template, mean over the 18 cells
B = {}
for key, kw in (("start", dict(policy="start-aligned", C_px=128)), ("field", dict(policy="fixed-field"))):
    for m in MARGINS:
        s = sel(template_error="clean", margin_px=m, **kw); assert len(s) == 18, (key, m, len(s))
        B[(key, m)] = 100 * sum(float(r["extra_area_vs_m0"]) for r in s) / len(s)

print("VALUES (read from", SUMMARY.relative_to(ROOT) if SUMMARY.is_relative_to(ROOT) else SUMMARY, ")")
for (te, m), (v, alone, names) in A.items():
    print(f"  (a) C=128 {te:20s} m={m:2d}: {v:7.3f} bits, worst-off class size {names}")
print(f"  (a) field box and C=256: max pointwise {zero_max} bits over {len(zero)} rows")
for (k, m), v in B.items():
    print(f"  (b) {k:5s} m={m:2d}: {v:6.3f} %")

def check(fig):
    fig.canvas.draw(); r = fig.canvas.get_renderer()
    boxes = [(t.get_text(), t.get_window_extent(r)) for t in fig.findobj(matplotlib.text.Text)
             if t.get_visible() and t.get_text().strip() and t.get_window_extent(r).width > 1]
    bad = [(a[0], b[0]) for a, b in itertools.combinations(boxes, 2) if a[1].overlaps(b[1])]
    for ax in fig.axes:
        for ln in ax.get_lines():
            if ln.get_marker() in (None, "None", "", " "): continue
            for px, py in ax.transData.transform(list(zip(ln.get_xdata(), ln.get_ydata()))):
                bad += [("MARKER", n) for n, bb in boxes if bb.x0 + 1 < px < bb.x1 - 1 and bb.y0 + 1 < py < bb.y1 - 1]
    Wd, Hd = fig.canvas.get_width_height()
    bad += [("CLIPPED", n) for n, bb in boxes if bb.x0 < 2 or bb.y0 < 2 or bb.x1 > Wd - 2 or bb.y1 > Hd - 2]
    for b in bad: print("  LAYOUT:", b)
    return len(bad)

fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.85), gridspec_kw=dict(width_ratios=[1.245, 1]))
fig.subplots_adjust(left=0.10, right=0.980, bottom=0.40, top=0.91, wspace=0.315)
for te, ls, mk in (("clean", "-", "o"), ("start_uniform_-4_4", "--", "D")):
    ys = [A[(te, m)][0] for m in MARGINS]
    a.plot(MARGINS, ys, color=START, ls=ls, lw=1.4, zorder=3)
    for m, y in zip(MARGINS, ys):
        alone = A[(te, m)][1]
        a.plot([m], [y], ls="", marker=mk, ms=5.5 if mk == "o" else 5.0, mec=START, mew=1.3,
               mfc=START if alone else "white", zorder=4)
a.plot([0, 16], [0, 0], color=FIELD, lw=1.6, zorder=3)
a.text(16, 1.0, "field box and C = 256 px: 0 bits", ha="right", va="bottom", fontsize=FS - 0.5)
a.set_xticks(MARGINS); a.set_xlim(-1, 17); a.set_ylim(-1, 21); a.set_yticks([0, 5, 10, 15, 20])
a.grid(True, axis="y"); a.set_axisbelow(True)
a.set_xlabel("Anchor margin m (px)"); a.set_ylabel("Largest pointwise leak (bits)")
a.set_title("(a) Worst-off person")
b.plot(MARGINS, [B[("field", m)] for m in MARGINS], color=FIELD, lw=1.4, marker="s", ms=5, zorder=3)
b.plot(MARGINS, [B[("start", m)] for m in MARGINS], color=START, lw=1.4, marker="o", ms=5, zorder=3)
b.text(16, B[("field", 16)] - 0.9, f"{B[('field', 16)]:.1f}%", ha="center", va="top")
b.text(16, B[("start", 16)] + 0.7, f"{B[('start', 16)]:.1f}%", ha="center", va="bottom", color=START)
b.set_xticks(MARGINS); b.set_xlim(-1, 17.5); b.set_ylim(-0.4, 13); b.set_yticks([0, 4, 8, 12])
b.grid(True, axis="y"); b.set_axisbelow(True)
b.set_xlabel("Anchor margin m (px)"); b.set_ylabel("Extra area vs. m = 0 (%)")
b.set_title("(b) Cost in blacked-out area")
hs = [Line2D([], [], color=START, lw=1.4, marker="o", ms=5, label="Padding C = 128, clean"),
      Line2D([], [], color=START, lw=1.4, ls="--", marker="D", ms=5, label="Padding C = 128, ±4-px start error"),
      Line2D([], [], ls="", marker="o", ms=5, color=START, label="filled: alone in class"),
      Line2D([], [], ls="", marker="o", ms=5, mfc="white", mec=START, mew=1.3, label="hollow: shares class"),
      Line2D([], [], color=FIELD, lw=1.4, marker="s", ms=5.5, label="Fixed field box")]
fig.legend(handles=hs, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0.0), handlelength=2.0,
           columnspacing=1.5, handletextpad=0.5, labelspacing=0.35, fontsize=FS - 0.5)
probs = check(fig)
fig.savefig(OUT / "fig5.pdf"); fig.savefig(OUT / "fig5.png", dpi=600); plt.close(fig)
print(f"LAYOUT PROBLEMS: {probs}"); sys.exit(1 if probs else 0)
