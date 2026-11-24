#!/usr/bin/env python3
"""Figure 6 for 'How Much Does a Redaction Box Reveal?': real-document top-10 hit rates.

Every plotted number is recomputed from archived results in the Guard repository:
  (a) research/realworld_validation/results/attacker_results.csv
      attacker = matched; mean of hit10 per policy (816 pages); no box = mean of nobox_hit10
  (b) research/doclaynet_validation/results/summary.csv
      track = controlled_insertion, role = evaluation, size_px = 16,
      condition = matched_template_known, category = all; geo_top10 per policy, prior_top10 = no box
The values are also checked against manuscript/figures/figs_data.csv (rows fig6).
Colours: blue exact box and square grids, light-blue width-only grid,
orange start-aligned padding, black fixed field box. The value labels and the 'no box'
label are kept off the dashed no-box line.

Run:  python3 manuscript/figures/make_fig_realworld.py [--repo /path/to/Guard] [--out DIR]
Writes fig6.pdf and a 600-dpi fig6.png to out/paper_figures/. Exit code non-zero on a value mismatch or a layout problem.
"""
import argparse, csv, itertools, os, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--repo", default=os.environ.get("GUARD_ROOT"))
ap.add_argument("--out", default=None)
args = ap.parse_args()
ROOT = Path(args.repo) if args.repo else HERE.parents[1]
if not (ROOT / "research").exists():
    sys.exit("Run inside the Guard repository or pass --repo /path/to/Guard")
OUT = Path(args.out) if args.out else ROOT / "out/paper_figures"; OUT.mkdir(parents=True, exist_ok=True)
ATT = ROOT / "research/realworld_validation/results/attacker_results.csv"
DLN = ROOT / "research/doclaynet_validation/results/summary.csv"
FIGS_DATA = ROOT / "manuscript/figures/figs_data.csv"

W = 5.0
try:
    fm.findfont(fm.FontProperties(family="Source Sans Pro"), fallback_to_default=False)
    FONT = "Source Sans Pro"
except Exception:
    FONT = "DejaVu Sans"; print("WARNING: Source Sans Pro not found, using DejaVu Sans")
FS = 8.5
plt.rcParams.update({
    "font.family": FONT, "font.size": FS, "axes.titlesize": FS + 0.5, "axes.titleweight": "bold",
    "axes.labelsize": FS + 0.5, "xtick.labelsize": FS, "ytick.labelsize": FS,
    "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.7,
    "axes.edgecolor": "#333333", "xtick.color": "#333333", "ytick.color": "#333333",
    "axes.titlelocation": "left", "axes.titlepad": 6, "pdf.fonttype": 42,
    "grid.color": "#E4E4E4", "grid.linewidth": 0.6, "savefig.facecolor": "white",
})
COL = {"exact": "#0072B2", "square16": "#0072B2", "square64": "#0072B2", "width64": "#56B4E9",
       "start128": "#D55E00", "field": "#000000", "ref": "#7F7F7F"}
# bottom to top
ORDER = [("exact", "Exact box", "Exact box"), ("square16", "16-px grid", "16-px grid"),
         ("square64", "64-px grid", "64-px grid"),
         ("width64", "Width-only 64-px grid", "Width-only 64-px grid"),
         ("start128", "Start-aligned padding, C = 128", "Start-aligned padding (C = 128)"),
         ("field", "Fixed field box", "Field box")]

def read(p):
    with open(p, newline="") as h:
        return list(csv.DictReader(h))

def panel_a():
    rows = [r for r in read(ATT) if r["attacker"] == "matched"]
    out = {}
    for pol, *_ in ORDER:
        v = [float(r["hit10"]) for r in rows if r["policy"] == pol]
        out[pol] = (100 * sum(v) / len(v), len(v))
    nb = [float(r["nobox_hit10"]) for r in rows if r["policy"] == "exact"]
    return out, 100 * sum(nb) / len(nb), len(nb)

def panel_b():
    rows = [r for r in read(DLN) if r["track"] == "controlled_insertion" and r["role"] == "evaluation"
            and r["size_px"] == "16" and r["condition"] == "matched_template_known" and r["category"] == "all"]
    out = {}
    for pol, *_ in ORDER:
        hit = [r for r in rows if r["policy"] == pol]; assert len(hit) == 1, pol
        out[pol] = (100 * float(hit[0]["geo_top10"]), int(hit[0]["n_targets"]))
    nb = {round(100 * float(r["prior_top10"]), 6) for r in rows}; assert len(nb) == 1
    return out, nb.pop(), int(rows[0]["n_targets"])

# ---------------------------------------------------------------- data + cross-check
A, nbA, nA = panel_a(); B, nbB, nB = panel_b()
ref = {(r["panel"], r["series"]): float(r["y"]) for r in read(FIGS_DATA) if r["figure"] == "fig6"}
mism = []; LOG = []
for p, d, nb in (("a", A, nbA), ("b", B, nbB)):
    for pol, _, ser in ORDER:
        v = round(d[pol][0], 1); LOG.append((p, ser, d[pol][0], ref[(p, ser)]))
        if v != ref[(p, ser)]: mism.append((p, ser, v, ref[(p, ser)]))
    LOG.append((p, "No box", nb, ref[(p, "No box")]))
    if round(nb, 1) != ref[(p, "No box")]: mism.append((p, "No box", nb, ref[(p, "No box")]))
print("CROSS-CHECK (panel | series | recomputed | figs_data.csv)")
for p, s, v, r in LOG: print(f"  {p} {s:34s} {v:8.3f} {r:6.1f} {'OK' if round(v, 1) == r else 'MISMATCH'}")
print(f"n: (a) {nA} pages, (b) {nB} names")

# ---------------------------------------------------------------- figure
def check(fig):
    fig.canvas.draw(); r = fig.canvas.get_renderer(); bad = []
    boxes = [(t.get_text(), t.get_window_extent(r)) for t in fig.findobj(matplotlib.text.Text)
             if t.get_visible() and t.get_text().strip() and t.get_window_extent(r).width > 1]
    bad += [(a[0], b[0]) for a, b in itertools.combinations(boxes, 2) if a[1].overlaps(b[1])]
    for ax in fig.axes:
        for p in ax.patches:
            pb = p.get_window_extent(r)
            for n, bb in boxes:
                if bb.x0 + 1 < pb.x1 and pb.x0 < bb.x1 - 1 and bb.y0 + 1 < pb.y1 and pb.y0 < bb.y1 - 1:
                    bad.append(("BAR", n))
        for ln in ax.get_lines():           # dashed no-box line: no text may touch it
            xs = ax.transData.transform([(x, 0) for x in ln.get_xdata()])[:, 0]
            y0, y1 = ax.transData.transform([(0, y) for y in ln.get_ydata()])[:, 1]
            for n, bb in boxes:
                if bb.x0 - 1 < xs[0] < bb.x1 + 1 and bb.y0 < max(y0, y1) and min(y0, y1) < bb.y1:
                    bad.append(("NO-BOX LINE", n))
    Wd, Hd = fig.canvas.get_width_height()
    bad += [("CLIPPED", n) for n, bb in boxes if bb.x0 < 2 or bb.y0 < 2 or bb.x1 > Wd - 2 or bb.y1 > Hd - 2]
    small = [t.get_text() for t in fig.findobj(matplotlib.text.Text)
             if t.get_visible() and t.get_text().strip() and t.get_fontsize() < FS - 1e-6]
    for b in bad: print("  LAYOUT:", b)
    for s in small: print("  TEXT <", FS, "pt:", s)
    return len(bad) + len(small)

fig, axs = plt.subplots(1, 2, figsize=(W, 2.3), sharey=True)
fig.subplots_adjust(left=0.335, right=0.975, bottom=0.25, top=0.86, wspace=0.08)
titles = {"a": f"(a) Invented pages ({nA})", "b": f"(b) DocLayNet ({nB} names)"}
ys = list(range(len(ORDER)))
for ax, p, d, nb in ((axs[0], "a", A, nbA), (axs[1], "b", B, nbB)):
    top = len(ORDER) - 0.5
    for (pol, lab, _), y in zip(ORDER, ys):
        v = d[pol][0]
        ax.barh(y, v, 0.66, color=COL[pol], zorder=3)
        # label right of the bar, and always clear of the dashed no-box line
        ax.text(max(v, nb) + 3.0, y, f"{v:.1f}%", va="center", ha="left")
    ax.plot([nb, nb], [-0.6, top], color=COL["ref"], ls="--", lw=1.0, zorder=4)
    ax.text(nb - 1.0, top + 0.1, f"no box {nb:.1f}%", ha="left", va="bottom", color="#555555")
    ax.set_yticks(ys); ax.set_yticklabels([o[1] for o in ORDER]); ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, 122); ax.set_xticks(range(0, 101, 20)); ax.set_ylim(-0.6, len(ORDER) + 0.25)
    ax.grid(True, axis="x"); ax.set_axisbelow(True)
    ax.set_xlabel("Top-10 hit rate (%)")
    ax.set_title(titles[p], pad=8)
probs = check(fig)
fig.savefig(OUT / "fig6.pdf"); fig.savefig(OUT / "fig6.png", dpi=600); plt.close(fig)
print(f"VALUES: {len(LOG)} checked, {len(mism)} mismatches"); print(f"LAYOUT PROBLEMS: {probs}")
sys.exit(1 if (mism or probs) else 0)
