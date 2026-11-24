#!/usr/bin/env python3
"""Figure A1 for 'How Much Does a Redaction Box Reveal?': what repeated releases add.

Reads:
  research/e1/cases/posterior/a3_cases.csv.gz   columns dict, font, grid_px, k, hit10_lik
      (a) dict = surnames, grid_px = 16, k in {1, 5}: A3 top-10 hit rate = mean of hit10_lik
          per font (DejaVuSans, LiberationSerif), then the mean of the two fonts, x 100.
  research/e1/data/results_summary.csv   columns condition, list, font, size, model, class_px,
      grid, attacker, k, bits_1, bits_k
      (b) list = surnames, grid = 1; one row per line of the figure (ROWS below); bits_1 is the
          first release and bits_k the value after k releases.
Run:  python3 manuscript/figures/make_fig_releases.py [--repo /path/to/Guard] [--out DIR]
Writes figA1.pdf and a 600-dpi figA1.png (default out/paper_figures/). Exit 1 on a layout problem.
"""
import argparse, csv, gzip, itertools, os, statistics, sys
from collections import defaultdict
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
A3 = ROOT / "research/e1/cases/posterior/a3_cases.csv.gz"
SUMM = ROOT / "research/e1/data/results_summary.csv"
for p in (A3, SUMM):
    if not p.exists(): sys.exit(f"{p} not found: run inside the Guard repository or pass --repo /path/to/Guard")
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
    "grid.color": "#E4E4E4", "grid.linewidth": 0.6, "legend.frameon": False, "savefig.facecolor": "white",
})
BAR, START = "#0072B2", "#D55E00"

# (a) A3 top-10 on the 16-px grid
hits = defaultdict(list)
with gzip.open(A3, "rt", newline="") as h:
    for r in csv.DictReader(h):
        if r["dict"] == "surnames" and r["grid_px"] == "16" and r["k"] in ("1", "5"):
            hits[(int(r["k"]), r["font"])].append(float(r["hit10_lik"]))
PA = {}
for k in (1, 5):
    per_font = {f: 100 * statistics.mean(v) for (kk, f), v in hits.items() if kk == k}
    assert sorted(per_font) == ["DejaVuSans", "LiberationSerif"], per_font
    PA[k] = statistics.mean(per_font.values())
    print(f"  (a) T = {k}: " + ", ".join(f"{f} {v:.2f}%" for f, v in sorted(per_font.items())) + f" -> {PA[k]:.3f}%")

# (b) one results_summary.csv row per line:  label, condition, font, size, model, class_px, attacker, k
ROWS = [("Same mask, 5 shifts",  "shifted",  "DejaVuSans", 16, "layout", 128, "A1", 5),
        ("Pillow → LibreOffice", "renderer", "mixed",      24, "ink",    128, "A2", 2),
        ("New text size",        "size",     "mixed",      24, "layout", 128, "A2", 3),
        ("Jitter 0–16 px",       "jitter",   "DejaVuSans", 24, "layout", 128, "A1", 5),
        ("New font",             "font",     "mixed",      24, "layout", 128, "A1", 5),
        ("Jitter, C = 192 px",   "jitter",   "DejaVuSans", 24, "layout", 192, "A1", 5)]
summ = list(csv.DictReader(open(SUMM, newline="")))
PB = []
for lab, cond, font, size, model, cpx, att, k in ROWS:
    m = [r for r in summ if r["list"] == "surnames" and r["grid"] == "1" and r["condition"] == cond and r["font"] == font
         and r["size"] == str(size) and r["model"] == model and r["class_px"] == str(cpx) and r["attacker"] == att and r["k"] == str(k)]
    assert len(m) == 1, (lab, len(m))
    v1, v2 = max(float(m[0]["bits_1"]), 0.0), max(float(m[0]["bits_k"]), 0.0)
    PB.append((lab, v1, v2)); print(f"  (b) {lab}: {v1:.4f} -> {v2:.4f}")

def check(fig):
    fig.canvas.draw(); r = fig.canvas.get_renderer()
    boxes = [(t.get_text(), t.get_window_extent(r)) for t in fig.findobj(matplotlib.text.Text)
             if t.get_visible() and t.get_text().strip() and t.get_window_extent(r).width > 1]
    bad = [(a[0], b[0]) for a, b in itertools.combinations(boxes, 2) if a[1].overlaps(b[1])]
    Wd, Hd = fig.canvas.get_width_height()
    bad += [("CLIPPED", n) for n, bb in boxes if bb.x0 < 2 or bb.y0 < 2 or bb.x1 > Wd - 2 or bb.y1 > Hd - 2]
    for b in bad: print("  LAYOUT:", b)
    return len(bad)

fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.3), gridspec_kw=dict(width_ratios=[0.55, 1.45]))
fig.subplots_adjust(left=0.1, right=0.99, bottom=0.24, top=0.87, wspace=0.62)
for i, k in enumerate((1, 5)):
    a.bar(i, PA[k], 0.6, color=BAR, zorder=3)
    a.text(i, PA[k] + 0.6, f"{PA[k]:.1f}%", ha="center", va="bottom", fontsize=FS - 0.5, fontweight="bold")
a.set_xticks([0, 1]); a.set_xticklabels(["T = 1", "T = 5"])
a.set_xlim(-0.6, 1.6); a.set_ylim(0, 26); a.set_yticks(range(0, 26, 5))
a.grid(True, axis="y"); a.set_axisbelow(True); a.set_ylabel("A3 top-10 (%)")
a.set_title("(a) 16-px grid")
ys = list(range(len(PB)))[::-1]
for (lab, v1, v2), y in zip(PB, ys):
    same = f"{v1:.2f}" == f"{v2:.2f}"
    # where the two markers would sit on top of each other, nudge them apart vertically
    dy = 0.08 if (not same and abs(v2 - v1) < 0.03) else 0.0
    b.plot([v1, v2], [y, y], color="#C8C8C8", lw=1.8, zorder=2)
    b.scatter([v2], [y - dy], marker="D", s=28, color=START, zorder=4)
    b.scatter([v1], [y + dy], marker="o", s=32, facecolor="white", edgecolor=START, lw=1.2, zorder=5)
    txt = f"{v1:.2f}, no change" if same else f"{v1:.2f} → {v2:.2f}"
    b.text(max(v1, v2) + 0.035, y, txt, va="center", ha="left", fontsize=FS - 0.5, color="#333333")
b.set_yticks(ys); b.set_yticklabels([r[0] for r in PB]); b.tick_params(axis="y", length=0)
b.set_xlim(-0.03, 0.98); b.set_ylim(-0.6, len(PB) - 0.4)
b.set_xticks([0, 0.2, 0.4, 0.6, 0.8]); b.grid(True, axis="x"); b.set_axisbelow(True)
b.set_xlabel("Bits leaked (C = 128 px unless marked)")
hs = [Line2D([], [], ls="", marker="o", markerfacecolor="white", markeredgecolor=START, markeredgewidth=1.2, markersize=6, label="first release"),
      Line2D([], [], ls="", marker="D", color=START, markersize=5, label="after T releases")]
b.legend(handles=hs, loc="upper right", ncol=1, handletextpad=0.3, borderaxespad=0.1, labelspacing=0.3)
b.set_title("(b) Start-aligned padding")
probs = check(fig)
fig.savefig(OUT / "figA1.pdf"); fig.savefig(OUT / "figA1.png", dpi=600); plt.close(fig)
print(f"LAYOUT PROBLEMS: {probs}"); sys.exit(1 if probs else 0)
