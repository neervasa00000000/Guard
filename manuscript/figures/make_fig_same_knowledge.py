#!/usr/bin/env python3
"""Figure 3 for 'How Much Does a Redaction Box Reveal?': padding and the field box with the same knowledge.

Reads (knowledge-matched sweep, A1 on the first 1,000 Census surnames, six fonts):
  research/e1/data/knowledge_matched/summary.csv   columns size_px, policy, width_px, bits
      (a) policy = start-aligned, size_px in {12, 16, 24}: average bits vs class width C;
          policy = field: 0 bits at every size (checked).
  research/e1/cases/knowledge_matched/cases_{12,16,24}px.csv.gz   per-target rows
      columns font, case, policy, width_px, area_ratio, left_rel, top_rel, right_rel, bottom_rel
  research/e1/data/knowledge_matched/field_widths.csv   columns font, size_px, width_px
      (b) dark bars: median over targets of area_ratio(field) / area_ratio(start-aligned, C0),
          C0 = smallest tested C with 0 bits at that size (from summary.csv);
          hatched bars: one C for all six fonts equal to the widest field width W at that size
          (max width_px in field_widths.csv); every listed name fits in one class, so the padded
          box is C wide with the full-line height of the target's field box, and the ratio is
          (field width x height) / (C x height) per target, median over targets.
Run:  python3 manuscript/figures/make_fig_same_knowledge.py [--repo /path/to/Guard] [--out DIR]
Writes fig3.pdf and a 600-dpi fig3.png (default out/paper_figures/). Exit 1 on a layout problem.
"""
import argparse, csv, gzip, itertools, os, statistics, sys
from collections import defaultdict
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--repo", default=os.environ.get("GUARD_ROOT"))
ap.add_argument("--out", default=None)
args = ap.parse_args()
ROOT = Path(args.repo) if args.repo else HERE.parents[1]
DATA = ROOT / "research/e1/data/knowledge_matched"
CASES = ROOT / "research/e1/cases/knowledge_matched"
if not (DATA / "summary.csv").exists():
    sys.exit(f"{DATA}/summary.csv not found: run inside the Guard repository or pass --repo /path/to/Guard")
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
    "savefig.facecolor": "white", "hatch.linewidth": 0.8,
})
FIELD = "#000000"
SIZE = {12: ("#F0B48C", "o"), 16: ("#D55E00", "s"), 24: ("#8A3C00", "D")}
# Class widths drawn in panel (a): the widths of Table A4 (64, 96, 128, 192 px) and, for 24-px text,
# also 160 px, the width at which it first drops to about 0 (Section 5.2).
C_DRAWN = {12: (64, 96, 128, 192), 16: (64, 96, 128, 192), 24: (64, 96, 128, 160, 192)}

summ = list(csv.DictReader(open(DATA / "summary.csv", newline="")))
def bits(size, policy, width):
    r = [x for x in summ if x["size_px"] == str(size) and x["policy"] == policy and x["width_px"] == str(width)]
    assert len(r) == 1, (size, policy, width, len(r)); return max(float(r[0]["bits"]), 0.0)
A = {s: [(c, bits(s, "start-aligned", c)) for c in C_DRAWN[s]] for s in SIZE}
TESTED = sorted({int(x["width_px"]) for x in summ if x["policy"] == "start-aligned"})
C0 = {s: min(c for c in TESTED if bits(s, "start-aligned", c) == 0.0) for s in SIZE}
assert all(bits(s, "field", 0) == 0.0 for s in SIZE)
fw = defaultdict(dict)
for r in csv.DictReader(open(DATA / "field_widths.csv", newline="")):
    fw[int(r["size_px"])][r["font"]] = int(r["width_px"])
B_small, B_wide = {}, {}
for s in SIZE:
    Cw = max(fw[s].values())
    per = defaultdict(dict)
    with gzip.open(CASES / f"cases_{s}px.csv.gz", "rt", newline="") as h:
        for r in csv.DictReader(h):
            if (r["policy"], r["width_px"]) in (("field", "0"), ("start-aligned", str(C0[s]))):
                per[(r["font"], r["case"])][r["policy"]] = r
    small, wide = [], []
    for v in per.values():
        f_, p_ = v["field"], v["start-aligned"]
        small.append(float(f_["area_ratio"]) / float(p_["area_ratio"]))
        fwid = int(f_["right_rel"]) - int(f_["left_rel"])
        assert fwid == fw[s][f_["font"]] and fwid <= Cw      # field box = widest entry; one class of width Cw holds every name
        wide.append(fwid / Cw)
    B_small[s] = 100 * statistics.median(small); B_wide[s] = 100 * statistics.median(wide)
    print(f"  {s}-px: smallest 0-bit C = {C0[s]} px, n = {len(small)}, field/padded median {B_small[s]:.2f}%;"
          f" one C = widest field width {Cw} px: {B_wide[s]:.2f}%")
for s in SIZE: print(f"  (a) {s}-px:", ", ".join(f"C={c}: {v:.4f}" for c, v in A[s]))

def check(fig):
    fig.canvas.draw(); r = fig.canvas.get_renderer()
    boxes = [(t.get_text(), t.get_window_extent(r)) for t in fig.findobj(matplotlib.text.Text)
             if t.get_visible() and t.get_text().strip() and t.get_window_extent(r).width > 1]
    bad = [(a[0], b[0]) for a, b in itertools.combinations(boxes, 2) if a[1].overlaps(b[1])]
    Wd, Hd = fig.canvas.get_width_height()
    bad += [("CLIPPED", n) for n, bb in boxes if bb.x0 < 2 or bb.y0 < 2 or bb.x1 > Wd - 2 or bb.y1 > Hd - 2]
    for b in bad: print("  LAYOUT:", b)
    return len(bad)

fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.7), gridspec_kw=dict(width_ratios=[1.1, 1]))
fig.subplots_adjust(left=0.105, right=0.99, bottom=0.38, top=0.90, wspace=0.34)
a.axhline(0, color=FIELD, lw=1.6, ls="--", zorder=2)
for s, (col, m) in SIZE.items():
    xs, ys = zip(*A[s])
    a.plot(xs, ys, color=col, marker=m, ms=4.5, lw=1.6, zorder=3, label=f"{s}-px text")
    a.scatter([C0[s]], [0], s=110, facecolor="none", edgecolor="#222222", lw=1.1, zorder=5)
    a.text(C0[s], -0.155, f"{s} px", ha="center", va="center", color=col if s != 12 else "#C0702F", fontsize=FS - 0.5)
a.set_xticks([64, 96, 128, 160, 192]); a.set_xlim(54, 204); a.set_ylim(-0.2, 0.92)
a.set_yticks([0, 0.2, 0.4, 0.6, 0.8]); a.grid(True, axis="y"); a.set_axisbelow(True)
a.set_xlabel("Class width C (px)"); a.set_ylabel("Average bits leaked")
hs, ls = a.get_legend_handles_labels()
hs += [Line2D([], [], color=FIELD, lw=1.6, ls="--"),
       Line2D([], [], ls="", marker="o", markerfacecolor="none", markeredgecolor="#222222", markersize=8)]
ls += ["Field box (0 bits)", "Smallest 0-bit C"]
a.legend(hs, ls, loc="upper center", bbox_to_anchor=(0.5, -0.33), ncol=3, fontsize=FS - 0.5,
         handlelength=1.6, labelspacing=0.25, columnspacing=0.9)
a.set_title("(a) Start-aligned padding")
sizes = [12, 16, 24]; w = 0.38
for i, s in enumerate(sizes):
    x0, x1 = i - 0.5 * w, i + 0.5 * w
    b.bar(x0, B_small[s], w * 0.94, color=FIELD, zorder=3)
    b.bar(x1, B_wide[s], w * 0.94, facecolor="white", edgecolor=FIELD, hatch="///", lw=0.8, zorder=3)
    b.text(x0, B_small[s] - 3, f"{B_small[s]:.0f}%", ha="center", va="top", color="white", fontweight="bold", fontsize=FS - 0.5, zorder=4)
    b.text(x1, B_wide[s] - 3, f"{B_wide[s]:.0f}%", ha="center", va="top", color="#222222", fontweight="bold", fontsize=FS - 0.5, zorder=4,
           bbox=dict(facecolor="white", edgecolor="none", pad=0.8))
b.set_xticks(range(3)); b.set_xticklabels([f"{s}-px text" for s in sizes])
b.set_ylim(0, 100); b.set_yticks(range(0, 101, 20)); b.grid(True, axis="y"); b.set_axisbelow(True)
b.set_ylabel("Field-box area ÷ padded area (%)")
b.legend(handles=[Patch(facecolor=FIELD, label="C = smallest zero-leak C"),
                  Patch(facecolor="white", edgecolor=FIELD, hatch="///", label="C = widest field width")],
         loc="upper center", bbox_to_anchor=(0.45, -0.17), ncol=1, fontsize=FS - 0.5,
         handlelength=1.6, handletextpad=0.4, labelspacing=0.25)
b.set_title("(b) Field-box area")
probs = check(fig)
fig.savefig(OUT / "fig3.pdf"); fig.savefig(OUT / "fig3.png", dpi=600); plt.close(fig)
print(f"LAYOUT PROBLEMS: {probs}"); sys.exit(1 if probs else 0)
