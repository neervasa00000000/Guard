"""Clean redraw of Figures 1-6 for 'How Much Does a Redaction Box Reveal?'.

Every plotted number comes from figs_data.csv (each row cites where it is printed in
the paper). Nothing is interpolated: lines join measured points only.
Run: python3 make_figs_clean.py -> fig1..fig6 .pdf + .png (300 dpi), compare_clean.png,
and a text-overlap / clipping report for every figure.
"""
import csv, os, itertools
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, NullLocator

HERE = os.path.dirname(os.path.abspath(__file__))
W2 = 7.0  # two-panel width (in); placed in the docx at a smaller width
try:
    fm.findfont(fm.FontProperties(family="Source Sans Pro"), fallback_to_default=False)
    FONT = "Source Sans Pro"
except Exception:
    FONT = "DejaVu Sans"; print("WARNING: Source Sans Pro not found, using DejaVu Sans")
FS = 9.5
plt.rcParams.update({
    "font.family": FONT, "font.size": FS, "axes.titlesize": FS + 1.5, "axes.titleweight": "bold",
    "axes.labelsize": FS + 0.5, "xtick.labelsize": FS, "ytick.labelsize": FS, "legend.fontsize": FS,
    "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.8,
    "axes.edgecolor": "#333333", "xtick.color": "#333333", "ytick.color": "#333333",
    "axes.titlelocation": "center", "axes.titlepad": 8, "pdf.fonttype": 42,
    "grid.color": "#E4E4E4", "grid.linewidth": 0.7, "legend.frameon": True,
    "legend.edgecolor": "#CCCCCC", "legend.framealpha": 1.0, "savefig.facecolor": "white",
})

# One colour per policy, identical in every figure (Okabe-Ito)
C = {"exact": "#333333", "square": "#0072B2", "widthonly": "#56B4E9", "start": "#D55E00",
     "edge": "#009E73", "edge_ink": "#009E73", "field": "#CC79A7", "ref": "#7F7F7F"}
START_LIGHT = "#F0B48C"      # lighter shade of the padding colour (second group)
NAME = {"exact": "Exact box", "square": "Square grid", "widthonly": "Width-only grid",
        "start": "Start-aligned padding", "edge": "Edge-aligned padding", "field": "Field box"}
MK = {"exact": "X", "square": "o", "widthonly": "s", "start": "D", "edge": "^", "edge_ink": "^", "field": "P"}

rows = list(csv.DictReader(open(os.path.join(HERE, "figs_data.csv"))))
def get(fig, panel=None):
    return [r for r in rows if r["figure"] == fig and (panel is None or r["panel"] == panel)]
def f(v):
    return None if v in ("", None) else float(v)
PLOTTED = []  # (figure, label, value) for the cross-check

def check(fig, name):
    fig.canvas.draw(); r = fig.canvas.get_renderer()
    boxes = []
    for t in fig.findobj(matplotlib.text.Text):
        if not t.get_visible() or not t.get_text().strip():
            continue
        bb = matplotlib.text.Text.get_window_extent(t, r)  # text only (no leader line)
        if bb.width > 1:
            boxes.append((t.get_text().replace("\n", " | "), bb))
    bad = [(a[0], b[0]) for a, b in itertools.combinations(boxes, 2) if a[1].overlaps(b[1])]
    for ax in fig.axes:
        lg = ax.get_legend()
        if lg is None:
            continue
        lbb = lg.get_window_extent(r); own = {t.get_text() for t in lg.get_texts()} | {lg.get_title().get_text()}
        bad += [("LEGEND", n) for n, bb in boxes if n not in own and lbb.overlaps(bb)]
        # legend vs plotted markers / bars
        for art in ax.collections + ax.patches:
            try:
                abb = art.get_window_extent(r)
            except Exception:
                continue
            if abb.width > 0 and abb.width < fig.bbox.width * 0.9 and lbb.overlaps(abb):
                bad.append(("LEGEND", "data artist " + type(art).__name__))
    Wd, Hd = fig.canvas.get_width_height()
    out = [n for n, bb in boxes if bb.x0 < 3 or bb.y0 < 3 or bb.x1 > Wd - 3 or bb.y1 > Hd - 3]
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

def panel(ax, s):
    ax.set_title(s, loc="center")

# ------------------------------------------------------------------ Figure 1
def fig1():
    fig = plt.figure(figsize=(W2, 2.35))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")
    stages = [
        ("Hidden surname\nrendered in a field", "redactor knows the\ntext and its box; may\nknow the template\nand the list"),
        ("Redaction policy\npublishes a box", "picks a box policy;\npixels hidden; box\nposition, width and\nheight visible"),
        ("Attacker observes\nbox geometry", "same font, renderer,\nlist and prior as\nthe redactor"),
        ("Candidate filtering\nand prior ranking", "renders every entry,\nkeeps those that fit;\nmeasured: top-10/top-1,\nbits leaked, area"),
    ]
    arrows = ["redacts", "box only", "guesses"]
    gap, x0 = 7.0, 0.6
    bw = (100 - 2 * x0 - 3 * gap) / 4
    for i, (t, body) in enumerate(stages):
        x = x0 + i * (bw + gap)
        ax.add_patch(FancyBboxPatch((x, 4), bw, 92, boxstyle="round,pad=0,rounding_size=4",
                                    fc="#EEF3F8", ec="#4A6584", lw=1.1))
        ax.text(x + bw / 2, 80, t, ha="center", va="center", fontsize=FS + 1, fontweight="bold",
                color="#1A1A1A", linespacing=1.05)
        ax.plot([x + 3, x + bw - 3], [64, 64], color="#B7C4D3", lw=0.8)
        ax.text(x + bw / 2, 35, body, ha="center", va="center", fontsize=9, color="#333333", linespacing=1.1)
        if i < 3:
            xa, xb = x + bw + 0.8, x + bw + gap - 0.8
            ax.annotate("", xy=(xb, 50), xytext=(xa, 50),
                        arrowprops=dict(arrowstyle="-|>", color="#222222", lw=1.3, mutation_scale=12))
            ax.text((xa + xb) / 2, 55, arrows[i].replace(" ", "\n"), ha="center", va="bottom",
                    fontsize=9, color="#444444", linespacing=1.0)
    return save(fig, "fig1")

# ------------------------------------------------------------------ Figure 2
def fig2():
    d = get("fig2")
    fig, ax = plt.subplots(figsize=(W2, 4.6))
    fig.subplots_adjust(left=0.08, right=0.985, bottom=0.13, top=0.97)
    short = {"exact": "Exact box", "square": "Grid", "widthonly": "Width", "start": "Pad",
             "edge": "Edge 128 (layout box)", "edge_ink": "Edge 128 (ink box)"}
    # label offsets in points (dx, dy, ha, va); leader line drawn when far from the point
    OFF = {("exact", "1"): (8, 0, "left", "center"),
           ("square", "8"): (8, 0, "left", "center"), ("square", "16"): (8, 0, "left", "center"),
           ("square", "32"): (8, 0, "left", "center"), ("square", "64"): (0, 9, "center", "bottom"),
           ("square", "128"): (0, 9, "center", "bottom"),
           ("widthonly", "16"): (-8, 0, "right", "center"), ("widthonly", "64"): (8, -1, "left", "center"),
           ("widthonly", "128"): (8, 5, "left", "center"),
           ("start", "64"): (-8, 0, "right", "center"), ("start", "96"): (-9, -4, "right", "center"),
           ("start", "128"): (14, -24, "left", "center"), ("start", "192"): (12, -22, "left", "center"),
           ("edge", "128"): (-32, -31, "right", "center"), ("edge_ink", "128"): (-8, 6, "right", "center")}
    seen = set()
    for r in d:
        fam, x, y = r["family"], f(r["x"]), f(r["y"])
        col = C[fam]
        hollow = fam == "edge_ink"
        lab = NAME.get(fam if fam != "edge_ink" else "edge") if (fam if fam != "edge_ink" else "edge") not in seen else None
        seen.add(fam if fam != "edge_ink" else "edge")
        ax.scatter([x], [y], s=62 if fam != "exact" else 80, marker=MK[fam], zorder=4,
                   facecolor="white" if hollow else col, edgecolor=col, linewidth=1.4 if hollow else 0.6,
                   label=None)
        PLOTTED.append(("fig2", r["series"] + " " + r["item"], y)); PLOTTED.append(("fig2", r["series"] + " " + r["item"] + " area", x))
        txt = short[fam] if fam in ("exact", "edge", "edge_ink") else f"{short[fam]} {r['item']}"
        if r["display"].startswith("<"):
            txt += f" ({r['display']} bits)"
        dx, dy, ha, va = OFF[(fam, r["item"])]
        far = abs(dx) > 10 or abs(dy) > 12
        ax.annotate(txt, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha, va=va,
                    fontsize=9, color="#222222", zorder=5,
                    arrowprops=dict(arrowstyle="-", color="#999999", lw=0.6, shrinkA=0, shrinkB=4) if far else None)
    ax.set_xscale("log", base=2)
    ax.set_xlim(0.9, 40); ax.set_ylim(-1.0, 7.1)
    ticks = [1, 2, 4, 8, 16, 32]
    ax.xaxis.set_major_locator(FixedLocator(ticks)); ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xticklabels([f"{t}×" for t in ticks])
    ax.set_yticks(range(0, 8))
    ax.grid(True, which="major"); ax.set_axisbelow(True)
    ax.axhline(0, color="#BBBBBB", lw=0.8, zorder=1)
    ax.set_xlabel("Blacked-out area ÷ requested area (median, log scale)")
    ax.set_ylabel("Bits leaked (lower is better)")
    hs = [Line2D([], [], ls="", marker=MK[k], color=C[k], markersize=7 if k != "exact" else 8, label=NAME[k])
          for k in ("exact", "square", "widthonly", "start", "edge")]
    hs.append(Line2D([], [], ls="", marker="^", markerfacecolor="white", markeredgecolor=C["edge"],
                     markeredgewidth=1.4, markersize=7, label="Edge-aligned, ink box"))
    ax.legend(handles=hs, loc="upper right", ncol=2, handletextpad=0.4, columnspacing=1.2, borderpad=0.6)
    return save(fig, "fig2")

# ------------------------------------------------------------------ Figure 3
def fig3():
    fig, (a, b) = plt.subplots(1, 2, figsize=(W2, 3.4), gridspec_kw=dict(width_ratios=[1.12, 1]))
    fig.subplots_adjust(left=0.085, right=0.99, bottom=0.25, top=0.89, wspace=0.28)
    size_style = {"12 px text": ("#F0B48C", "o"), "16 px text": ("#D55E00", "s"), "24 px text": ("#8A3C00", "D")}
    A = get("fig3", "a")
    a.axhline(0, color=C["field"], lw=2.2, ls=(0, (4, 2)), zorder=2)
    for s, (col, m) in size_style.items():
        pts = sorted((f(r["x"]), f(r["y"])) for r in A if r["series"] == s)
        xs, ys = zip(*pts)
        a.plot(xs, ys, color=col, marker=m, ms=5.5, lw=1.6, zorder=3, label=s.replace(" text", ""))
        z = min(x for x, y in pts if y == 0)  # smallest measured zero-leak C
        a.scatter([z], [0], s=170, facecolor="none", edgecolor="#222222", lw=1.3, zorder=5)
        for x, y in pts: PLOTTED.append(("fig3a", f"{s} C={x:g}", y))
    for r in A:
        if r["series"] == "Field box": PLOTTED.append(("fig3a", "Field box", f(r["y"])))
    for z, s in ((96, "12 px"), (128, "16 px"), (192, "24 px")):
        a.annotate(s, (z, 0), xytext=(0, -10), textcoords="offset points",
                   ha="center", va="top", fontsize=9, color="#222222", linespacing=1.0)
    a.set_xticks([64, 96, 128, 160, 192]); a.set_xlim(54, 204); a.set_ylim(-0.17, 0.95)
    a.set_yticks([0, 0.2, 0.4, 0.6, 0.8])
    a.grid(True, axis="y"); a.set_axisbelow(True)
    a.set_xlabel("Class width C (px)"); a.set_ylabel("Average bits leaked")
    hs, ls = a.get_legend_handles_labels()
    hs += [Line2D([], [], color=C["field"], lw=2.2, ls=(0, (4, 2))),
           Line2D([], [], ls="", marker="o", markerfacecolor="none", markeredgecolor="#222222", markersize=10)]
    ls += ["Field box (0 bits)", "First 0-bit C"]
    a.legend(hs, ls, loc="upper right", title="Start-aligned padding", title_fontsize=9, fontsize=9,
             handlelength=1.8, borderpad=0.5, labelspacing=0.35)
    panel(a, "A · Padding leak falls with class width")
    B = get("fig3", "b")
    sizes = ["12", "16", "24"]; w = 0.36
    for j, (ser, col) in enumerate((("Smallest zero-leak C", C["start"]), ("C = widest field width", START_LIGHT))):
        vals = [f(next(r["y"] for r in B if r["series"] == ser and r["item"] == s)) for s in sizes]
        xs = [i + (j - 0.5) * w for i in range(3)]
        b.bar(xs, vals, w * 0.94, color=col, label=ser, zorder=3)
        for x, v in zip(xs, vals):
            b.text(x, v - 3, f"{v:.0f}%", ha="center", va="top", fontsize=9, color="white" if j == 0 else "#222222", fontweight="bold")
            PLOTTED.append(("fig3b", ser, v))
    b.set_xticks(range(3)); b.set_xticklabels([f"{s} px text" for s in sizes])
    b.set_ylim(0, 100); b.set_yticks(range(0, 101, 20))
    b.grid(True, axis="y"); b.set_axisbelow(True)
    b.set_ylabel("Field-box area ÷ padded area (%)")
    b.legend(loc="upper center", bbox_to_anchor=(0.45, -0.13), ncol=2, fontsize=9, frameon=False,
             handlelength=1.2, handletextpad=0.4, columnspacing=1.0)
    panel(b, "B · Field box saves only rounding slack")
    return save(fig, "fig3")

# ------------------------------------------------------------------ Figure 4 (simplified)
def fig4():
    A, B = get("fig4", "a"), get("fig4", "b")
    fonts = [r["item"] for r in A if r["series"] == "16 px"]
    ys = list(range(len(fonts)))[::-1]
    sty = {"16 px": dict(marker="o", s=58, facecolor=C["start"], edgecolor=C["start"], lw=1.0),
           "24 px": dict(marker="D", s=46, facecolor=START_LIGHT, edgecolor="#8A3C00", lw=1.0)}
    fig, (a, b) = plt.subplots(1, 2, figsize=(W2, 3.3), sharey=True, gridspec_kw=dict(width_ratios=[0.68, 1.32]))
    fig.subplots_adjust(left=0.15, right=0.985, bottom=0.2, top=0.80, wspace=0.08)
    for fn, y in zip(fonts, ys):
        for s in ("16 px", "24 px"):
            ra = next(r for r in A if r["series"] == s and r["item"] == fn)
            va = f(ra["y"]); a.scatter([va], [y], zorder=4, **sty[s]); PLOTTED.append(("fig4a", f"{fn} {s}", va))
            if s == "24 px":
                a.text(va + 0.022, y, ra["display"], va="center", ha="left", fontsize=9, color="#333333")
            rb = next(r for r in B if r["series"] == s and r["item"] == fn)
            vb = f(rb["y"])
            if vb is None:
                b.text(15.2, y, "16 px: none", va="center", ha="left", fontsize=9, color="#666666", style="italic")
                continue
            b.scatter([vb], [y], zorder=4, **sty[s]); PLOTTED.append(("fig4b", f"{fn} {s}", vb))
            n = rb["x"].split(";")[0].replace(" names", "").replace(" name", "")
            pct = rb["x"].split("; ")[1]
            lab = f"1 name ({pct})" if n == "1" else f"{n} ({pct})"
            b.text(vb + 0.55, y, lab, va="center", ha="left", fontsize=9, zorder=5,
                   color="#222222" if n == "1" else "#666666", fontweight="bold" if n == "1" else "normal",
                   bbox=dict(fc="white", ec="none", pad=0.4))
    a.text(0.022, ys[0] + 0.8, "16 px: ≤ 0.003 everywhere", fontsize=9, color="#666666", ha="left", va="center")
    ent = f(next(r["y"] for r in B if r["series"] == "Prior entropy"))
    b.axvline(ent, color="#555555", ls="--", lw=1.0, zorder=1)
    b.text(ent - 0.3, ys[0] + 0.8, f"prior entropy {ent:.2f} bits", ha="right", va="center", fontsize=9, color="#555555")
    a.set_yticks(ys); a.set_yticklabels(fonts); a.tick_params(axis="y", length=0)
    a.set_xlim(-0.01, 0.52); a.set_xticks([0, 0.1, 0.2, 0.3, 0.4, 0.5])
    b.set_xlim(0, 26.5); b.set_xticks([0, 5, 10, 15, 20, 25]); b.tick_params(axis="y", length=0)
    for ax in (a, b):
        ax.grid(True, axis="x"); ax.set_axisbelow(True); ax.set_ylim(-0.6, len(fonts) + 0.15)
        for y in ys: ax.axhline(y, color="#F0F0F0", lw=0.8, zorder=0)
    a.set_xlabel("Average bits leaked"); b.set_xlabel("Bits leaked by one person in the wider class")
    panel(a, "A · Average over everyone"); panel(b, "B · A person in the wider class")
    hs = [Line2D([], [], ls="", marker="o", markersize=7, markerfacecolor=C["start"], markeredgecolor=C["start"], label="16-px text"),
          Line2D([], [], ls="", marker="D", markersize=6, markerfacecolor=START_LIGHT, markeredgecolor="#8A3C00", label="24-px text")]
    fig.legend(handles=hs, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.56, 1.0), handletextpad=0.3, columnspacing=1.6)
    return save(fig, "fig4")

# ------------------------------------------------------------------ Figure 5 (simplified)
def fig5():
    fig, (a, b) = plt.subplots(1, 2, figsize=(W2, 2.75), gridspec_kw=dict(width_ratios=[0.5, 1.5]))
    fig.subplots_adjust(left=0.075, right=0.985, bottom=0.21, top=0.88, wspace=0.55)
    A = sorted(get("fig5", "a"), key=lambda r: f(r["x"]))
    for i, r in enumerate(A):
        v = f(r["y"]); a.bar(i, v, 0.6, color=C["square"], zorder=3)
        a.text(i, v + 0.6, r["display"], ha="center", va="bottom", fontsize=9.5, fontweight="bold")
        PLOTTED.append(("fig5a", "k=" + r["x"], v))
    a.set_xticks(range(len(A)))
    a.set_xticklabels(["1 copy" if f(r["x"]) == 1 else f"{int(f(r['x']))} copies" for r in A])
    a.set_xlim(-0.6, len(A) - 0.4); a.set_ylim(0, 25); a.set_yticks(range(0, 26, 5))
    a.grid(True, axis="y"); a.set_axisbelow(True); a.set_ylabel("Top-10 hit rate (%)")
    panel(a, "A · 16-px grid copies")
    B = get("fig5", "b")
    short = {"Same mask; 5 shifted copies": "Same mask, 5 copies", "Pillow -> LibreOffice": "Pillow → LibreOffice",
             "New text size": "New text size", "Jitter 0-16 px": "Jitter 0–16 px", "New font": "New font",
             "Jitter, C = 192": "Jitter, C = 192"}
    labels = list(dict.fromkeys(r["series"] for r in B)); ys = list(range(len(labels)))[::-1]
    for lab, y in zip(labels, ys):
        v1 = f(next(r["y"] for r in B if r["series"] == lab and r["item"] == "first"))
        v2 = f(next(r["y"] for r in B if r["series"] == lab and r["item"] == "after"))
        b.plot([v1, v2], [y, y], color="#C8C8C8", lw=2, zorder=2)
        b.scatter([v2], [y], marker="D", s=44, color=C["start"], zorder=4)
        b.scatter([v1], [y], marker="o", s=52, facecolor="white", edgecolor=C["start"], lw=1.5, zorder=5)
        txt = f"{v1:.2f} → {v2:.2f}" if v1 != v2 else f"{v1:.2f}, no change"
        b.text(max(v1, v2) + 0.04, y, txt, va="center", ha="left", fontsize=9, color="#333333")
        PLOTTED.extend([("fig5b", lab + " first", v1), ("fig5b", lab + " after", v2)])
    b.set_yticks(ys); b.set_yticklabels([short[l] for l in labels]); b.tick_params(axis="y", length=0)
    b.set_xlim(-0.03, 0.95); b.set_ylim(-0.6, len(labels) - 0.4)
    b.set_xticks([0, 0.2, 0.4, 0.6, 0.8]); b.grid(True, axis="x"); b.set_axisbelow(True)
    b.set_xlabel("Bits leaked (start-aligned padding)")
    hs = [Line2D([], [], ls="", marker="o", markerfacecolor="white", markeredgecolor=C["start"], markeredgewidth=1.5, markersize=7, label="first release"),
          Line2D([], [], ls="", marker="D", color=C["start"], markersize=6, label="after changes")]
    b.legend(handles=hs, loc="upper right", ncol=1, frameon=False, fontsize=9,
             handletextpad=0.3, borderaxespad=0.2, labelspacing=0.3)
    panel(b, "B · Changing the published box")
    return save(fig, "fig5")

# ------------------------------------------------------------------ Figure 6
def fig6():
    fig, axs = plt.subplots(1, 2, figsize=(W2, 3.3), sharey=True)
    fig.subplots_adjust(left=0.2, right=0.985, bottom=0.19, top=0.80, wspace=0.12)
    titles = {"a": "A · PDF writers (816 pages)", "b": "B · DocLayNet (954 surnames)"}
    rename = {"Width-only 64-px grid": "Width-only 64-px grid", "Start-aligned padding (C = 128)": "Start-aligned 128 px"}
    for ax, p in zip(axs, "ab"):
        d = [r for r in get("fig6", p) if r["family"] != "ref"]
        nb = f(next(r["y"] for r in get("fig6", p) if r["family"] == "ref"))
        ys = list(range(len(d)))
        for r, y in zip(d, ys):
            v = f(r["y"])
            ax.barh(y, v, 0.68, color=C[r["family"]], zorder=3)
            ax.text(v + 1.2, y, f"{v:.1f}%", va="center", ha="left", fontsize=9)
            PLOTTED.append(("fig6" + p, r["series"], v))
        PLOTTED.append(("fig6" + p, "No box", nb))
        ax.axvline(nb, color=C["ref"], ls="--", lw=1.1, zorder=4)
        ax.text(nb + 1.0, len(d) - 0.35, f"no box {nb:.1f}%", ha="left", va="bottom", fontsize=9, color="#555555")
        ax.set_yticks(ys); ax.set_yticklabels([rename.get(r["series"], r["series"]) for r in d])
        ax.tick_params(axis="y", length=0)
        ax.set_xlim(0, 108); ax.set_xticks(range(0, 101, 20)); ax.set_ylim(-0.6, len(d) - 0.4)
        ax.grid(True, axis="x"); ax.set_axisbelow(True)
        ax.set_xlabel("Top-10 hit rate (%)")
        ax.set_title(titles[p], pad=20)
    return save(fig, "fig6")

def contact():
    import matplotlib.image as mpimg
    fig, axs = plt.subplots(3, 2, figsize=(11, 10.5))
    for i, ax in enumerate(axs.flat):
        ax.imshow(mpimg.imread(os.path.join(HERE, f"fig{i+1}.png"))); ax.axis("off")
        ax.set_title(f"fig{i+1}", fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "compare_clean.png"), dpi=130); plt.close(fig)

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
    total = sum(fn() for fn in (fig1, fig2, fig3, fig4, fig5, fig6))
    crosscheck(); contact()
    print("TOTAL PROBLEMS:", total)
