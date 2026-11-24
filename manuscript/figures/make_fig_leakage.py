#!/usr/bin/env python3
"""Figures 2 and 4 for 'How Much Does a Redaction Box Reveal?' (simplified redraw).

Every plotted number is read from an archived CSV in the Guard repository:
  Figure 2  research/e1/pooled/pooled.csv            (surnames, all sizes pooled, LAYOUT-BOX, A1)
            research/e1/data/baselines_nobox.csv     (surname prior entropy)
  Figure 4  research/e1/data/per_person/tail_summary.csv (start-aligned padding, C = 128 px)
Nothing is typed in by hand. PAPER holds the numbers printed in the manuscript;
the cross-check prints every plotted value next to its source row and the paper's number
and counts mismatches (at the paper's rounding).

Run:  python3 manuscript/figures/make_fig_leakage.py [--repo /path/to/Guard] [--out DIR]
Writes fig2.pdf/png and fig4.pdf/png (vector PDF + 600-dpi PNG) and crosscheck.csv to out/paper_figures/.
Exit code is non-zero if a value mismatches or any text overlaps or is clipped.
"""
import argparse, csv, itertools, math, os, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.ticker import FixedLocator, NullLocator, FuncFormatter

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--repo", default=os.environ.get("GUARD_ROOT"))
ap.add_argument("--out", default=None)
args = ap.parse_args()
if args.repo:
    ROOT = Path(args.repo)
else:  # inside the repo this file lives at manuscript/figures/
    ROOT = HERE.parents[1]
    if not (ROOT / "research").exists():
        sys.exit("Run inside the Guard repository or pass --repo /path/to/Guard")
OUT = Path(args.out) if args.out else ROOT / "out/paper_figures"; OUT.mkdir(parents=True, exist_ok=True)

POOLED = ROOT / "research/e1/pooled/pooled.csv"
BASE = ROOT / "research/e1/data/baselines_nobox.csv"
TAIL = ROOT / "research/e1/data/per_person/tail_summary.csv"

# ---------------------------------------------------------------- style
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
# Okabe-Ito colours, as in the earlier figure script
COL = {"exact": "#0072B2", "square": "#0072B2", "start": "#D55E00", "ref": "#7F7F7F",
       "start_light": "#F0B48C"}
FONT_LABEL = {"DejaVuSans": "DejaVu Sans", "DejaVuSerif": "DejaVu Serif",
              "LiberationSans": "Liberation Sans", "LiberationSerif": "Liberation Serif",
              "LiberationMono": "Liberation Mono", "NotoSans": "Noto Sans"}
FONTS = ["DejaVuSans", "DejaVuSerif", "LiberationSans", "LiberationSerif", "LiberationMono", "NotoSans"]

# ---------------------------------------------------------------- numbers printed in the manuscript
# (figure labels / text / tables; used ONLY for the cross-check, never for plotting)
PAPER = {
    ("fig2", "prior"): (12.88, 2),
    ("fig2", "exact", "bits"): (6.66, 2), ("fig2", "exact", "area"): (1.00, 2),
    ("fig2", "square-8", "bits"): (3.30, 2), ("fig2", "square-8", "area"): (1.60, 2),
    ("fig2", "square-16", "bits"): (2.19, 2), ("fig2", "square-16", "area"): (2.45, 2),
    ("fig2", "square-32", "bits"): (1.28, 2), ("fig2", "square-32", "area"): (4.38, 2),
    ("fig2", "square-64", "bits"): (0.67, 2), ("fig2", "square-64", "area"): (10.04, 2),
    ("fig2", "square-128", "bits"): (0.33, 2), ("fig2", "square-128", "area"): (28.64, 2),
    ("fig2", "pen-anchored-64", "bits"): (0.64, 2), ("fig2", "pen-anchored-64", "area"): (2.16, 2),
    ("fig2", "pen-anchored-96", "bits"): (0.30, 2), ("fig2", "pen-anchored-96", "area"): (2.62, 2),
    ("fig2", "pen-anchored-128", "bits"): (0.08, 2), ("fig2", "pen-anchored-128", "area"): (3.36, 2),
    ("fig2", "pen-anchored-192", "bits"): ("<0.01", 2), ("fig2", "pen-anchored-192", "area"): (5.03, 2),
}
_avg16 = {"DejaVuSans": 0.002, "DejaVuSerif": 0.003, "LiberationSans": "<0.001", "LiberationSerif": 0.0,
          "LiberationMono": 0.003, "NotoSans": "<0.001"}
_avg24 = {"DejaVuSans": 0.281, "DejaVuSerif": 0.370, "LiberationSans": 0.085, "LiberationSerif": 0.023,
          "LiberationMono": 0.428, "NotoSans": 0.175}
_pt16 = {"DejaVuSans": (12.9, 37), "DejaVuSerif": (11.9, 63), "LiberationSans": (18.6, 1),
         "LiberationSerif": (None, None), "LiberationMono": (12.0, 62), "NotoSans": (14.9, 9)}
_pt24 = {"DejaVuSans": (4.4, 4188), "DejaVuSerif": (3.8, 5555), "LiberationSans": (6.6, 1351),
         "LiberationSerif": (8.8, 458), "LiberationMono": (3.5, 7201), "NotoSans": (5.3, 2713)}
for fnt in FONTS:
    PAPER[("fig4", fnt, "16", "mean")] = (_avg16[fnt], 3)
    PAPER[("fig4", fnt, "24", "mean")] = (_avg24[fnt], 3)
    PAPER[("fig4", fnt, "16", "max")] = (_pt16[fnt][0], 1)
    PAPER[("fig4", fnt, "24", "max")] = (_pt24[fnt][0], 1)
    PAPER[("fig4", fnt, "16", "names")] = (_pt16[fnt][1], 0)
    PAPER[("fig4", fnt, "24", "names")] = (_pt24[fnt][1], 0)
PAPER[("fig4", "pooled", "mean")] = (0.076, 3)   # Sec 5.3 text: 0.076 bits at C = 128

# ---------------------------------------------------------------- cross-check log
LOG = []   # rows: figure, item, plotted value, source file, source row, paper value, status
def record(fig, item, value, src, rowdesc, key):
    paper, digits = PAPER.get(key, (None, None))
    if paper is None and key in PAPER:
        status = "OK" if (value is None or value == 0 or (isinstance(value, float) and value < 1e-9) or key[-1] == "max" and value == 0) else "MISMATCH"
        paper_s = "none (no wider class)"
    elif paper is None:
        status, paper_s = "NOT IN PAPER", ""
    elif isinstance(paper, str):           # upper bound such as "<0.01"
        bound = float(paper.lstrip("<"))
        status = "OK" if value < bound else "MISMATCH"; paper_s = paper
    else:
        from decimal import Decimal, ROUND_HALF_UP
        q = Decimal(10) ** -digits
        hu = float(Decimal(repr(float(value))).quantize(q, rounding=ROUND_HALF_UP))
        if abs(hu - paper) < 1e-9:
            status = "OK"
        elif abs(abs(value - paper) - 0.5 * 10 ** -digits) < 1e-9:
            status = "ROUNDING TIE"   # exact half-way value; paper rounded down
        else:
            status = "MISMATCH"
        if key[-1] == "max" and paper == 0.0 and value == 0.0: status = "OK"
        paper_s = f"{paper:.{digits}f}" if digits else f"{paper:,.0f}"
    LOG.append([fig, item, "" if value is None else repr(value), os.path.relpath(src, ROOT), rowdesc, paper_s, status])

def read(path):
    with open(path, newline="") as h:
        return list(csv.DictReader(h))

# ---------------------------------------------------------------- overlap / clipping check
def check(fig, name):
    fig.canvas.draw(); r = fig.canvas.get_renderer()
    boxes = []
    for t in fig.findobj(matplotlib.text.Text):
        if not t.get_visible() or not t.get_text().strip():
            continue
        bb = t.get_window_extent(r)
        if bb.width > 1:
            boxes.append((t.get_text().replace("\n", " | "), bb, t.get_gid() == "inbar"))
    bad = [(a[0], b[0]) for a, b in itertools.combinations(boxes, 2) if a[1].overlaps(b[1])]
    inbar = [(n, bb) for n, bb, ib in boxes if ib]
    boxes = [(n, bb) for n, bb, ib in boxes]
    for ax in fig.axes:                       # text vs plotted markers
        for line in ax.get_lines():
            if line.get_marker() in (None, "None", "", " "): continue
            pts = ax.transData.transform(list(zip(line.get_xdata(), line.get_ydata())))
            for n, bb in boxes:
                for px, py in pts:
                    if bb.x0 + 1 < px < bb.x1 - 1 and bb.y0 + 1 < py < bb.y1 - 1:
                        bad.append(("MARKER", n))
        for p in ax.patches:                  # text vs bars (labels must sit beside bars)
            try: pb = p.get_window_extent(r)
            except Exception: continue
            if pb.width < 1 or pb.height < 1: continue
            for n, bb in boxes:
                if n.startswith("$"): continue
                if any(n == m and bb is b2 for m, b2 in inbar):   # inside its own bar: must fit within it
                    if pb.y0 <= bb.y0 and bb.y1 <= pb.y1 and pb.x0 <= bb.x0 and bb.x1 <= pb.x1: continue
                    if not (bb.x0 + 1 < pb.x1 and pb.x0 < bb.x1 - 1 and bb.y0 + 1 < pb.y1 and pb.y0 < bb.y1 - 1): continue
                    if bb.y0 >= pb.y0 - 1 and bb.y1 <= pb.y1 + 1 and pb.x0 <= bb.x0 and bb.x1 <= pb.x1: continue
                if (bb.x0 + 1 < pb.x1 and pb.x0 < bb.x1 - 1 and bb.y0 + 1 < pb.y1 and pb.y0 < bb.y1 - 1):
                    bad.append(("BAR", n))
    Wd, Hd = fig.canvas.get_width_height()
    out = [n for n, bb in boxes if bb.x0 < 2 or bb.y0 < 2 or bb.x1 > Wd - 2 or bb.y1 > Hd - 2]
    small = [t.get_text() for t in fig.findobj(matplotlib.text.Text)
             if t.get_visible() and t.get_text().strip() and t.get_fontsize() < FS - 1e-6]
    for a, b in bad: print(f"  [{name}] OVERLAP: '{a}' <-> '{b}'")
    for n in out: print(f"  [{name}] CLIPPED: '{n}'")
    for n in small: print(f"  [{name}] TEXT < {FS} pt: '{n}'")
    return len(bad) + len(out) + len(small)

def save(fig, name):
    n = check(fig, name)
    fig.savefig(OUT / f"{name}.pdf"); fig.savefig(OUT / f"{name}.png", dpi=600)
    plt.close(fig); print(f"{name}: {n} layout problems"); return n

# ---------------------------------------------------------------- Figure 2
def fig2():
    pooled = read(POOLED)
    def cell(policy):
        hit = [r for r in pooled if r["list"] == "surnames" and r["size_px"] == "all"
               and r["model"] == "LAYOUT-BOX" and r["attacker"] == "A1" and r["policy"] == policy]
        assert len(hit) == 1, (policy, len(hit))
        r = hit[0]
        bits = max(float(r["bits"]), 0.0)          # -1e-13 rounding noise -> 0
        area = float(r["median_overredaction"])
        desc = f"list=surnames,size_px=all,model=LAYOUT-BOX,attacker=A1,policy={policy},n={r['n']}"
        record("fig2", f"{policy} bits", bits, POOLED, desc, ("fig2", policy, "bits"))
        record("fig2", f"{policy} area", area, POOLED, desc, ("fig2", policy, "area"))
        return area, bits
    prior = float([r for r in read(BASE) if r["dict"] == "surnames"][0]["prior_bits"])
    record("fig2", "prior entropy", prior, BASE, "dict=surnames,prior_bits", ("fig2", "prior"))

    ex = cell("exact")
    sq = {g: cell(f"square-{g}") for g in (8, 16, 32, 64, 128)}
    st = {c: cell(f"pen-anchored-{c}") for c in (64, 96, 128, 192)}

    # rows, top to bottom; header rows (no bar) separate the policy families
    rows = [("Exact box", ex, COL["exact"], True),
            (None, None, None, None),
            ("Square grid", None, COL["square"], "header")]
    rows += [(f"{g} px", sq[g], COL["square"], False) for g in sq]
    rows += [(None, None, None, None), ("Start-aligned padding", None, COL["start"], "header")]
    rows += [(f"C = {c} px", st[c], COL["start"], False) for c in st]
    n = len(rows); ys = list(range(n))[::-1]

    fig, (axa, axb) = plt.subplots(1, 2, figsize=(W, 3.8), sharey=True)
    h = 0.62
    for y, (label, val, col, kind) in zip(ys, rows):
        if val is None:
            continue
        area, bits = val
        axa.barh(y, bits, height=h, color=col, lw=0)
        axb.barh(y, area, height=h, color=col, lw=0)
        btxt = "<0.01 bits" if bits < 0.005 else f"{bits:.2f} bits"
        axa.text(bits + 0.25, y, btxt, va="center", ha="left", color="#222222",
                 bbox=dict(facecolor="white", edgecolor="none", pad=0.6))
        from decimal import Decimal, ROUND_HALF_UP
        atxt = str(Decimal(repr(area)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        axb.text(area + 0.5, y, f"{atxt}×", va="center", ha="left", color="#222222")
    axa.set_yticks([y for y, r in zip(ys, rows) if r[0]])
    axa.set_yticklabels([r[0] for r in rows if r[0]])
    for t, r in zip(axa.get_yticklabels(), [r for r in rows if r[0]]):
        t.set_color(r[2] if r[3] in ("header", True) else "#333333")
        if r[3] in ("header", True):
            t.set_fontweight("bold")
    axa.tick_params(axis="y", length=0); axb.tick_params(axis="y", length=0)
    axa.set_ylim(-0.7, n - 0.3)

    axa.axvline(prior, color=COL["ref"], ls="--", lw=0.9, zorder=0)
    from matplotlib.lines import Line2D
    fig.legend(handles=[Line2D([], [], color=COL["ref"], ls="--", lw=0.9,
                               label=f"Prior: {prior:.2f} bits (leaking all of it = name revealed)")],
               loc="upper center", bbox_to_anchor=(0.5, 1.0), handlelength=2.0)
    axa.set_xlim(0, 14.5); axa.set_xticks([0, 4, 8, 12])
    axb.set_xlim(0, 36); axb.set_xticks([0, 10, 20, 30])
    axb.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}×"))
    axa.set_title("(a) Bits leaked")
    axb.set_title("(b) Area blacked out")
    axa.set_xlabel("bits about the surname")
    axb.set_xlabel("blacked-out ÷ requested area")
    for ax in (axa, axb):
        ax.grid(True, axis="x"); ax.set_axisbelow(True)
    fig.tight_layout(pad=0.4, w_pad=0.8, rect=(0, 0, 1, 0.93))
    return save(fig, "fig2")

# ---------------------------------------------------------------- Figure 4
def fig4():
    tail = read(TAIL)
    def cell(font, size):
        hit = [r for r in tail if r["font"] == font and r["size_px"] == str(size)
               and r["policy"] == "start-aligned" and r["width_px"] == "128"]
        assert len(hit) == 1, (font, size, len(hit))
        r = hit[0]
        mean, mx, names = float(r["mean_bits"]), float(r["max_pointwise_bits"]), int(r["max_class_names"])
        k = int(r["max_class_k"])
        desc = f"font={font},size_px={size},policy=start-aligned,width_px=128"
        record("fig4", f"{font} {size}px average bits", mean, TAIL, desc + ",mean_bits", ("fig4", font, str(size), "mean"))
        if k == 1:      # only one class: nobody is separated from anyone else
            mx_plot, names_plot = 0.0, None
        else:
            mx_plot, names_plot = mx, names
        record("fig4", f"{font} {size}px worst-off person bits", mx_plot, TAIL, desc + ",max_pointwise_bits",
               ("fig4", font, str(size), "max"))
        record("fig4", f"{font} {size}px names in that class", names_plot, TAIL, desc + ",max_class_names",
               ("fig4", font, str(size), "names"))
        return mean, mx_plot, names_plot
    pooled = [r for r in tail if r["font"] == "pooled" and r["policy"] == "start-aligned" and r["width_px"] == "128"][0]
    record("fig4", "pooled average bits (caption)", float(pooled["mean_bits"]), TAIL,
           "font=pooled,size_px=all,policy=start-aligned,width_px=128,mean_bits", ("fig4", "pooled", "mean"))
    prior = float([r for r in read(BASE) if r["dict"] == "surnames"][0]["prior_bits"])

    fig, axes = plt.subplots(1, 2, figsize=(W, 3.7), sharey=True)
    h = 0.36; off = 0.25
    inside = []   # worst-off labels; any that would run past the axis go inside their own bar
    ys = list(range(len(FONTS)))[::-1]
    for ax, size, title in zip(axes, (16, 24), ("(a) 16-px text", "(b) 24-px text")):
        for y, font in zip(ys, FONTS):
            mean, mx, names = cell(font, size)
            if mean == 0 and names is None:   # nobody separated: both values are 0
                ax.text(0.4, y, "0 bits for everyone\n(no name singled out)", va="center", ha="left",
                        color="#555555", style="italic", linespacing=1.0,
                        bbox=dict(facecolor="white", edgecolor="none", pad=0.6))
                continue
            ax.barh(y + off, mean, height=h, color=COL["start_light"], edgecolor=COL["start"], lw=0.6)
            ax.barh(y - off, mx, height=h, color=COL["start"], lw=0)
            mean_txt = f"{mean:.3f}" if mean >= 0.001 else "<0.001"
            who = "1, identified" if names == 1 else f"{names:,}"
            # one label per font row: average (light) above, worst-off person (dark) below
            lab = ax.text(mx + 0.6, y - off, f"{mx:.1f} ({who})", va="center", ha="left",
                          bbox=dict(facecolor="white", edgecolor="none", pad=0.6),
                          color="#222222", fontweight="bold" if names == 1 else "normal")
            inside.append((ax, lab, mx))
            ax.text(mean + 0.6, y + off, mean_txt, va="center", ha="left", color="#8A3C00")
        ax.set_yticks(ys); ax.set_yticklabels([FONT_LABEL[f] for f in FONTS])
        ax.tick_params(axis="y", length=0)
        ax.axvline(prior, color=COL["ref"], ls="--", lw=0.9, zorder=0)
        ax.set_title(title)
        ax.grid(True, axis="x"); ax.set_axisbelow(True)
        ax.set_ylim(-0.6, len(FONTS) - 0.4)
        ax.set_xlim(0, 24); ax.set_xticks([0, 5, 10, 15, 20])
        ax.set_xlabel("Bits leaked")
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(facecolor=COL["start_light"], edgecolor=COL["start"], label="Average over everyone"),
                        Patch(facecolor=COL["start"], label="Worst-off person (names in their box)"),
                        Line2D([], [], color=COL["ref"], ls="--", lw=0.9, label=f"Prior {prior:.2f} bits")],
               loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.0), handlelength=1.2, columnspacing=1.0, handletextpad=0.4)
    fig.tight_layout(pad=0.4, rect=(0, 0, 1, 0.92), w_pad=0.6)
    fig.canvas.draw(); r = fig.canvas.get_renderer()
    for ax, lab, mx in inside:
        if lab.get_window_extent(r).x1 > ax.get_window_extent(r).x1:
            lab.set_x(mx - 0.4); lab.set_ha("right"); lab.set_color("white")
            lab.set_bbox(None); lab.set_gid("inbar")
    return save(fig, "fig4")

# ---------------------------------------------------------------- run
problems = fig2() + fig4()
with open(OUT / "crosscheck.csv", "w", newline="") as h:
    w = csv.writer(h); w.writerow(["figure", "item", "plotted_value", "source_file", "source_row", "paper_value", "status"])
    w.writerows(LOG)
print("\nCROSS-CHECK (plotted value | source file : row | paper)")
for f_, item, v, src, row, paper, st in LOG:
    print(f"  {st:9s} {f_} {item:40s} {v:>24s} | {src} : {row} | paper {paper}")
mism = [r for r in LOG if r[-1] == "MISMATCH"]
ties = [r for r in LOG if r[-1] == "ROUNDING TIE"]
for r in ties: print(f"NOTE rounding tie (not a data error): {r[1]} = {r[2]} vs paper {r[5]}")
print(f"\nVALUES: {len(LOG)} checked, {len(mism)} mismatches")
print(f"LAYOUT PROBLEMS: {problems}")
print(f"TOTAL PROBLEMS: {len(mism) + problems}")
sys.exit(1 if (mism or problems) else 0)
