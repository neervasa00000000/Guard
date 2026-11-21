"""Figures 2-5 and A1 for 'How Much Does a Redaction Box Reveal?' (v9.31 redraw).

Changes from make_figs_v918.py: every figure is drawn at its printed width (5.0 in), so
text prints at 8-9 pt instead of ~4 pt; panel labels match the captions, (a)/(b);
policy names match the text ("16-px grid", "start-aligned padding, C = 128 px");
one colour and one marker per policy in every figure; Figure 2 gets a zoom panel so the
low-leak cluster is labelled without crowding. Every plotted number comes from
figs_data.csv (unchanged from v9.18); a cross-check and a text-overlap/clipping check
run for every figure.
Run: python3 make_figs_v931.py -> fig2_leakage_area, fig3_same_knowledge, fig4_pointwise,
fig5_realworld, figA1_releases (.pdf vector + .png 300 dpi).
"""
import csv, os, itertools
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.ticker import FixedLocator, NullLocator

HERE = os.path.dirname(os.path.abspath(__file__))
W = 5.0   # printed width in inches (docx and LaTeX place the figures at this width)
try:
    fm.findfont(fm.FontProperties(family="Source Sans Pro"), fallback_to_default=False)
    FONT = "Source Sans Pro"
except Exception:
    FONT = "DejaVu Sans"; print("WARNING: Source Sans Pro not found, using DejaVu Sans")
FS = 8.5   # printed point size (minimum for any text)
plt.rcParams.update({
    "font.family": FONT, "font.size": FS, "axes.titlesize": FS + 0.5, "axes.titleweight": "bold",
    "axes.labelsize": FS + 0.5, "xtick.labelsize": FS, "ytick.labelsize": FS, "legend.fontsize": FS,
    "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.7,
    "axes.edgecolor": "#333333", "xtick.color": "#333333", "ytick.color": "#333333",
    "axes.titlelocation": "left", "axes.titlepad": 6, "pdf.fonttype": 42,
    "grid.color": "#E4E4E4", "grid.linewidth": 0.6, "legend.frameon": False,
    "savefig.facecolor": "white",
})

# One colour and one marker per policy, identical in every figure (Okabe-Ito palette)
C = {"exact": "#333333", "square": "#0072B2", "widthonly": "#56B4E9", "start": "#D55E00",
     "edge": "#009E73", "edge_ink": "#009E73", "field": "#CC79A7", "ref": "#7F7F7F"}
START_LIGHT = "#F0B48C"; START_DARK = "#8A3C00"   # shades of the padding colour for text sizes
NAME = {"exact": "Exact box", "square": "Square grid", "widthonly": "Width-only grid",
        "start": "Start-aligned padding", "edge": "Edge-aligned padding", "field": "Fixed field box"}
MK = {"exact": "X", "square": "o", "widthonly": "s", "start": "D", "edge": "^", "edge_ink": "^", "field": "P"}

rows = list(csv.DictReader(open(os.path.join(HERE, "figs_data.csv"))))
def get(fig, panel=None):
    return [r for r in rows if r["figure"] == fig and (panel is None or r["panel"] == panel)]
def f(v):
    return None if v in ("", None) else float(v)
PLOTTED = []

def check(fig, name):
    fig.canvas.draw(); r = fig.canvas.get_renderer()
    boxes = []
    for t in fig.findobj(matplotlib.text.Text):
        if not t.get_visible() or not t.get_text().strip():
            continue
        bb = matplotlib.text.Text.get_window_extent(t, r)
        if bb.width > 1:
            boxes.append((t.get_text().replace("\n", " | "), bb))
    bad = [(a[0], b[0]) for a, b in itertools.combinations(boxes, 2) if a[1].overlaps(b[1])]
    for ax in fig.axes:
        lg = ax.get_legend()
        if lg is None:
            continue
        lbb = lg.get_window_extent(r); own = {t.get_text() for t in lg.get_texts()} | {lg.get_title().get_text()}
        bad += [("LEGEND", n) for n, bb in boxes if n not in own and lbb.overlaps(bb)]
        for art in ax.collections + ax.patches:
            try:
                abb = art.get_window_extent(r)
            except Exception:
                continue
            if 0 < abb.width < fig.bbox.width * 0.9 and lbb.overlaps(abb):
                bad.append(("LEGEND", "data artist " + type(art).__name__))
    # text vs markers (scatter points)
    for ax in fig.axes:
        for coll in ax.collections:
            offs = coll.get_offsets()
            if len(offs) == 0: continue
            pts = ax.transData.transform(offs)
            for n, bb in boxes:
                for (px, py) in pts:
                    if bb.x0 + 1 < px < bb.x1 - 1 and bb.y0 + 1 < py < bb.y1 - 1:
                        bad.append(("MARKER", n))
    Wd, Hd = fig.canvas.get_width_height()
    out = [n for n, bb in boxes if bb.x0 < 2 or bb.y0 < 2 or bb.x1 > Wd - 2 or bb.y1 > Hd - 2]
    for a, b in bad: print(f"  [{name}] OVERLAP: '{a}' <-> '{b}'")
    for n in out: print(f"  [{name}] CLIPPED: '{n}'")
    return len(bad) + len(out)

def save(fig, name):
    n = check(fig, name)
    fig.savefig(os.path.join(HERE, name + ".pdf"))
    fig.savefig(os.path.join(HERE, name + ".png"), dpi=300)
    plt.close(fig)
    print(f"{name}: {'OK' if n == 0 else str(n) + ' problems'}")
    return n

# ------------------------------------------------------------------ Figure 2
def fig2():
    d = get("fig2")
    fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.95), gridspec_kw=dict(width_ratios=[1, 1.15]))
    fig.subplots_adjust(left=0.085, right=0.975, bottom=0.17, top=0.75, wspace=0.22)
    # zoom window shown in (b)
    ZX, ZY = (1.75, 6.0), (-0.12, 1.1)
    lab = {"exact": lambda r: "exact", "square": lambda r: f"{r['item']} px",
           "widthonly": lambda r: f"{r['item']} px", "start": lambda r: f"C = {r['item']}",
           "edge": lambda r: "layout box", "edge_ink": lambda r: "ink box"}
    # (a): label exact box and square grids only; (b): zoomed cluster, all labelled
    OFF_A = {("exact", "1"): (6, 0, "left", "center"), ("square", "8"): (6, 0, "left", "center"),
             ("square", "16"): (6, 2, "left", "center"), ("square", "32"): (6, 2, "left", "bottom"), ("widthonly", "16"): (-6, 0, "right", "center"),
             ("square", "64"): (0, -6, "center", "top"), ("square", "128"): (0, 6, "center", "bottom")}
    OFF_B = {("square", "32"): (-6, 0, "right", "center"),
             ("widthonly", "16"): None, ("widthonly", "64"): (-6, 3, "right", "bottom"),
             ("widthonly", "128"): (6, 0, "left", "center"),
             ("start", "64"): (-6, 0, "right", "center"), ("start", "96"): (-6, 0, "right", "center"),
             ("start", "128"): (-6, -2, "right", "top"), ("start", "192"): (0, 6, "center", "bottom"),
             ("edge", "128"): (6, 0, "left", "center"), ("edge_ink", "128"): (6, 0, "left", "center")}
    for ax, zoom in ((a, False), (b, True)):
        for r in d:
            fam, x, y = r["family"], f(r["x"]), f(r["y"])
            col = C[fam]; hollow = fam == "edge_ink"
            if zoom and not (ZX[0] <= x <= ZX[1] and ZY[0] <= y <= ZY[1]):
                continue
            ax.scatter([x], [y], s=34 if fam != "exact" else 44, marker=MK[fam], zorder=4,
                       facecolor="white" if hollow else col, edgecolor=col, linewidth=1.2 if hollow else 0.5)
            if not zoom:
                PLOTTED.append(("fig2", r["series"] + " " + r["item"], y)); PLOTTED.append(("fig2", r["series"] + " " + r["item"] + " area", x))
            off = (OFF_B if zoom else OFF_A).get((fam, r["item"]))
            if off is None:
                continue
            txt = lab[fam](r)
            if r["display"].startswith("<"):
                txt += f" ({r['display']})"
            dx, dy, ha, va = off
            ax.annotate(txt, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha, va=va,
                        fontsize=FS - 0.5, color="#222222", zorder=5)
        ax.set_xscale("log", base=2)
        ax.axhline(0, color="#BBBBBB", lw=0.7, zorder=1)
        ax.grid(True, which="major"); ax.set_axisbelow(True)
    a.set_xlim(0.85, 45); a.set_ylim(-0.4, 7.3)
    ticks = [1, 2, 4, 8, 16, 32]
    a.xaxis.set_major_locator(FixedLocator(ticks)); a.xaxis.set_minor_locator(NullLocator())
    a.set_xticklabels([f"{t}×" for t in ticks]); a.set_yticks(range(0, 8))
    a.add_patch(Rectangle((ZX[0], ZY[0]), ZX[1] - ZX[0], ZY[1] - ZY[0], fill=False, ec="#777777", lw=0.8, ls="--", zorder=2))
    a.set_ylabel("Bits leaked to A1")
    a.set_title("(a) All tested policies")
    b.set_xlim(*ZX); b.set_ylim(*ZY)
    tb = [2, 3, 4, 5, 6]
    b.xaxis.set_major_locator(FixedLocator(tb)); b.xaxis.set_minor_locator(NullLocator())
    b.set_xticklabels([f"{t}×" for t in tb]); b.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    b.set_title("(b) Zoom: dashed box in (a)")
    fig.text(0.54, 0.04, "Blacked-out area ÷ requested area (median, log scale)", ha="center", va="center", fontsize=FS + 0.5)
    hs = [Line2D([], [], ls="", marker=MK[k], color=C[k], markersize=6 if k != "exact" else 7, label=NAME[k])
          for k in ("exact", "square", "widthonly", "start", "edge")]
    hs.append(Line2D([], [], ls="", marker="^", markerfacecolor="white", markeredgecolor=C["edge"],
                     markeredgewidth=1.2, markersize=6, label="Edge-aligned, ink box"))
    fig.legend(handles=hs, loc="upper center", ncol=3, bbox_to_anchor=(0.53, 1.0), handletextpad=0.2,
               columnspacing=1.0, labelspacing=0.25, handlelength=1.0)
    return save(fig, "fig2_leakage_area")

# ------------------------------------------------------------------ Figure 3
def fig3():
    fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.7), gridspec_kw=dict(width_ratios=[1.1, 1]))
    fig.subplots_adjust(left=0.105, right=0.99, bottom=0.38, top=0.90, wspace=0.34)
    size_style = {"12 px text": (START_LIGHT, "o"), "16 px text": (C["start"], "s"), "24 px text": (START_DARK, "D")}
    A = get("fig3", "a")
    a.axhline(0, color=C["field"], lw=2.0, ls=(0, (4, 2)), zorder=2)
    for s, (col, m) in size_style.items():
        pts = sorted((f(r["x"]), f(r["y"])) for r in A if r["series"] == s)
        xs, ys = zip(*pts)
        a.plot(xs, ys, color=col, marker=m, ms=4.5, lw=1.4, zorder=3, label=s.replace(" px text", "-px text"))
        z = min(x for x, y in pts if y == 0)
        a.scatter([z], [0], s=110, facecolor="none", edgecolor="#222222", lw=1.1, zorder=5)
        for x, y in pts: PLOTTED.append(("fig3a", f"{s} C={x:g}", y))
    for r in A:
        if r["series"] == "Field box": PLOTTED.append(("fig3a", "Field box", f(r["y"])))
    a.set_xticks([64, 96, 128, 160, 192]); a.set_xlim(54, 204); a.set_ylim(-0.08, 0.92)
    a.set_yticks([0, 0.2, 0.4, 0.6, 0.8])
    a.grid(True, axis="y"); a.set_axisbelow(True)
    a.set_xlabel("Class width C (px)"); a.set_ylabel("Average bits leaked")
    hs, ls = a.get_legend_handles_labels()
    hs += [Line2D([], [], color=C["field"], lw=2.0, ls=(0, (4, 2))),
           Line2D([], [], ls="", marker="o", markerfacecolor="none", markeredgecolor="#222222", markersize=8)]
    ls += ["Field box (0 bits)", "Smallest 0-bit C"]
    a.legend(hs, ls, loc="upper center", bbox_to_anchor=(0.5, -0.33), ncol=3, fontsize=FS - 0.5, handlelength=1.6, labelspacing=0.25, columnspacing=0.9)
    a.set_title("(a) Start-aligned padding")
    B = get("fig3", "b")
    sizes = ["12", "16", "24"]; w = 0.38
    for j, (ser, col) in enumerate((("Smallest zero-leak C", C["field"]), ("C = widest field width", "#E7B9D6"))):
        vals = [f(next(r["y"] for r in B if r["series"] == ser and r["item"] == s)) for s in sizes]
        xs = [i + (j - 0.5) * w for i in range(3)]
        b.bar(xs, vals, w * 0.94, color=col, label=ser.replace("C = widest field width", "C = widest field width").replace("Smallest zero-leak C", "C = smallest zero-leak C"), zorder=3)
        for x, v in zip(xs, vals):
            b.text(x, v - 3, f"{v:.0f}%", ha="center", va="top", fontsize=FS - 0.5, color="white" if j == 0 else "#222222", fontweight="bold")
            PLOTTED.append(("fig3b", ser, v))
    b.set_xticks(range(3)); b.set_xticklabels([f"{s}-px text" for s in sizes])
    b.set_ylim(0, 100); b.set_yticks(range(0, 101, 20))
    b.grid(True, axis="y"); b.set_axisbelow(True)
    b.set_ylabel("Field-box area ÷ padded area (%)")
    b.legend(loc="upper center", bbox_to_anchor=(0.45, -0.17), ncol=1, fontsize=FS - 0.5,
             handlelength=1.2, handletextpad=0.4, labelspacing=0.25)
    b.set_title("(b) Field-box area")
    return save(fig, "fig3_same_knowledge")

# ------------------------------------------------------------------ Figure 4
def fig4():
    A, B = get("fig4", "a"), get("fig4", "b")
    fonts = [r["item"] for r in A if r["series"] == "16 px"]
    ys = list(range(len(fonts)))[::-1]
    sty = {"16 px": dict(marker="o", s=34, facecolor=C["start"], edgecolor=C["start"], lw=0.8),
           "24 px": dict(marker="D", s=28, facecolor=START_LIGHT, edgecolor=START_DARK, lw=0.8)}
    fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.55), sharey=True, gridspec_kw=dict(width_ratios=[0.7, 1.3]))
    fig.subplots_adjust(left=0.19, right=0.975, bottom=0.21, top=0.79, wspace=0.07)
    for fn, y in zip(fonts, ys):
        for s in ("16 px", "24 px"):
            ra = next(r for r in A if r["series"] == s and r["item"] == fn)
            va = f(ra["y"]); a.scatter([va], [y], zorder=4, **sty[s]); PLOTTED.append(("fig4a", f"{fn} {s}", va))
            if s == "24 px":
                a.text(va + 0.03, y, ra["display"], va="center", ha="left", fontsize=FS - 0.5, color="#333333")
            rb = next(r for r in B if r["series"] == s and r["item"] == fn)
            vb = f(rb["y"])
            if vb is None:
                b.text(16.5, y, "16 px: none", va="center", ha="left", fontsize=FS - 0.5, color="#666666", style="italic")
                continue
            b.scatter([vb], [y], zorder=4, **sty[s]); PLOTTED.append(("fig4b", f"{fn} {s}", vb))
            n = rb["x"].split(";")[0].replace(" names", "").replace(" name", "")
            pct = rb["x"].split("; ")[1]
            lab = f"1 name ({pct})" if n == "1" else f"{n} ({pct})"
            b.text(vb + 0.6, y, lab, va="center", ha="left", fontsize=FS - 0.5, zorder=5,
                   color="#222222" if n == "1" else "#555555", fontweight="bold" if n == "1" else "normal",
                   bbox=dict(fc="white", ec="none", pad=0.3))
    a.text(0.0, ys[0] + 0.85, "16 px: ≤ 0.003 bits", fontsize=FS - 0.5, color="#555555", ha="left", va="center")
    ent = f(next(r["y"] for r in B if r["series"] == "Prior entropy"))
    b.axvline(ent, color="#555555", ls="--", lw=0.9, zorder=1)
    b.text(ent + 0.4, ys[0] + 0.85, f"prior entropy {ent:.2f} bits", ha="left", va="center", fontsize=FS - 0.5, color="#555555")
    a.set_yticks(ys); a.set_yticklabels(fonts); a.tick_params(axis="y", length=0)
    a.set_xlim(-0.02, 0.6); a.set_xticks([0, 0.2, 0.4])
    b.set_xlim(0, 30); b.set_xticks([0, 5, 10, 15, 20, 25]); b.tick_params(axis="y", length=0)
    for ax in (a, b):
        ax.grid(True, axis="x"); ax.set_axisbelow(True); ax.set_ylim(-0.6, len(fonts) + 0.25)
    a.set_xlabel("Average bits leaked"); b.set_xlabel("Pointwise leak (bits)")
    a.set_title("(a) Average over everyone"); b.set_title("(b) A person in the wider class", loc="right")
    hs = [Line2D([], [], ls="", marker="o", markersize=6, markerfacecolor=C["start"], markeredgecolor=C["start"], label="16-px text"),
          Line2D([], [], ls="", marker="D", markersize=5, markerfacecolor=START_LIGHT, markeredgecolor=START_DARK, label="24-px text")]
    fig.legend(handles=hs, loc="upper center", ncol=2, bbox_to_anchor=(0.58, 1.0), handletextpad=0.3, columnspacing=1.6)
    return save(fig, "fig4_pointwise")

# ------------------------------------------------------------------ Figure A1
def figA1():
    fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.3), gridspec_kw=dict(width_ratios=[0.55, 1.45]))
    fig.subplots_adjust(left=0.1, right=0.99, bottom=0.24, top=0.87, wspace=0.62)
    A = sorted(get("fig5", "a"), key=lambda r: f(r["x"]))
    for i, r in enumerate(A):
        v = f(r["y"]); a.bar(i, v, 0.6, color=C["square"], zorder=3)
        a.text(i, v + 0.6, r["display"], ha="center", va="bottom", fontsize=FS - 0.5, fontweight="bold")
        PLOTTED.append(("fig5a", "k=" + r["x"], v))
    a.set_xticks(range(len(A)))
    a.set_xticklabels(["k = 1" if f(r["x"]) == 1 else f"k = {int(f(r['x']))}" for r in A])
    a.set_xlim(-0.6, len(A) - 0.4); a.set_ylim(0, 26); a.set_yticks(range(0, 26, 5))
    a.grid(True, axis="y"); a.set_axisbelow(True); a.set_ylabel("A3 top-10 (%)")
    a.set_title("(a) 16-px grid")
    B = get("fig5", "b")
    short = {"Same mask; 5 shifted copies": "Same mask, 5 shifts", "Pillow -> LibreOffice": "Pillow → LibreOffice",
             "New text size": "New text size", "Jitter 0-16 px": "Jitter 0–16 px", "New font": "New font",
             "Jitter, C = 192": "Jitter, C = 192 px"}
    labels = list(dict.fromkeys(r["series"] for r in B)); ys = list(range(len(labels)))[::-1]
    for lab, y in zip(labels, ys):
        v1 = f(next(r["y"] for r in B if r["series"] == lab and r["item"] == "first"))
        v2 = f(next(r["y"] for r in B if r["series"] == lab and r["item"] == "after"))
        b.plot([v1, v2], [y, y], color="#C8C8C8", lw=1.8, zorder=2)
        b.scatter([v2], [y], marker="D", s=28, color=C["start"], zorder=4)
        b.scatter([v1], [y], marker="o", s=32, facecolor="white", edgecolor=C["start"], lw=1.2, zorder=5)
        txt = f"{v1:.2f} → {v2:.2f}" if v1 != v2 else f"{v1:.2f}, no change"
        b.text(max(v1, v2) + 0.035, y, txt, va="center", ha="left", fontsize=FS - 0.5, color="#333333")
        PLOTTED.extend([("fig5b", lab + " first", v1), ("fig5b", lab + " after", v2)])
    b.set_yticks(ys); b.set_yticklabels([short[l] for l in labels]); b.tick_params(axis="y", length=0)
    b.set_xlim(-0.03, 0.98); b.set_ylim(-0.6, len(labels) - 0.4)
    b.set_xticks([0, 0.2, 0.4, 0.6, 0.8]); b.grid(True, axis="x"); b.set_axisbelow(True)
    b.set_xlabel("Bits leaked (C = 128 px unless marked)")
    hs = [Line2D([], [], ls="", marker="o", markerfacecolor="white", markeredgecolor=C["start"], markeredgewidth=1.2, markersize=6, label="first release"),
          Line2D([], [], ls="", marker="D", color=C["start"], markersize=5, label="after k releases")]
    b.legend(handles=hs, loc="upper right", ncol=1, handletextpad=0.3, borderaxespad=0.1, labelspacing=0.3)
    b.set_title("(b) Start-aligned padding")
    return save(fig, "figA1_releases")

# ------------------------------------------------------------------ Figure 5
def fig5():
    fig, axs = plt.subplots(1, 2, figsize=(W, 2.3), sharey=True)
    fig.subplots_adjust(left=0.335, right=0.975, bottom=0.24, top=0.86, wspace=0.08)
    titles = {"a": "(a) PDF writers (816 pages)", "b": "(b) DocLayNet (954 names)"}
    rename = {"Width-only 64-px grid": "Width-only 64-px grid",
              "Start-aligned padding (C = 128)": "Start-aligned padding, C = 128",
              "Field box": "Fixed field box"}
    for ax, p in zip(axs, "ab"):
        d = [r for r in get("fig6", p) if r["family"] != "ref"]
        nb = f(next(r["y"] for r in get("fig6", p) if r["family"] == "ref"))
        ys = list(range(len(d)))
        for r, y in zip(d, ys):
            v = f(r["y"])
            ax.barh(y, v, 0.66, color=C[r["family"]], zorder=3)
            ax.text(max(v, nb) + 2.0, y, f"{v:.1f}%", va="center", ha="left", fontsize=FS - 0.5)
            PLOTTED.append(("fig6" + p, r["series"], v))
        PLOTTED.append(("fig6" + p, "No box", nb))
        ax.axvline(nb, color=C["ref"], ls="--", lw=1.0, zorder=4)
        ax.text(nb + 2.0, len(d) - 0.45, f"no box {nb:.1f}%", ha="left", va="bottom", fontsize=FS - 0.5, color="#555555")
        ax.set_yticks(ys); ax.set_yticklabels([rename.get(r["series"], r["series"]) for r in d])
        ax.tick_params(axis="y", length=0)
        ax.set_xlim(0, 122); ax.set_xticks(range(0, 101, 20)); ax.set_ylim(-0.6, len(d) + 0.15)
        ax.grid(True, axis="x"); ax.set_axisbelow(True)
        ax.set_xlabel("Top-10 hit rate (%)")
        ax.set_title(titles[p], pad=8)
    return save(fig, "fig5_realworld")

def contact():
    import matplotlib.image as mpimg
    names = ["fig2_leakage_area", "fig3_same_knowledge", "fig4_pointwise", "fig5_realworld", "figA1_releases"]
    fig, axs = plt.subplots(3, 2, figsize=(11, 11))
    for ax in axs.flat: ax.axis("off")
    for n, ax in zip(names, axs.flat):
        ax.imshow(mpimg.imread(os.path.join(HERE, n + ".png"))); ax.set_title(n, fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "contact_v931.png"), dpi=130); plt.close(fig)

def crosscheck():
    vals = {}
    for r in rows:
        for k in ("x", "y"):
            if r[k] not in ("", None):
                try: vals.setdefault(r["figure"], set()).add(round(float(r[k]), 4))
                except ValueError: pass
    bad = [p for p in PLOTTED if p[2] is not None and round(p[2], 4) not in vals.get(p[0][:4], set())]
    print(f"cross-check: {len(PLOTTED)} plotted values, {len(bad)} not found in figs_data.csv", bad)

if __name__ == "__main__":
    print("font:", FONT)
    total = sum(fn() for fn in (fig2, fig3, fig4, fig5, figA1))
    crosscheck(); contact()
    print("TOTAL PROBLEMS:", total)
