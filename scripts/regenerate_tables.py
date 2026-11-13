#!/usr/bin/env python3
"""Rebuild manuscript tables from the archived CSVs.

Numbers are computed here. manuscript/expected_numbers.json is the lock
from Vasa_MDPI_Computers_v8_5.docx and is not read by this script.
"""
import csv
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "research" / "e1" / "data"
CASES = ROOT / "research" / "e1" / "cases"
POOLED = ROOT / "research" / "e1" / "review4" / "pooled.csv"
OUT = ROOT / "out" / "tables"
VALUES = []


def add(item_id, value):
    VALUES.append((item_id, float(value)))


def pooled_row(frame, list_name, model, attacker, policy):
    hit = frame[
        (frame.list == list_name)
        & (frame.model == model)
        & (frame.attacker == attacker)
        & (frame.policy == policy)
        & (frame.size_px.astype(str) == "all")
    ]
    if len(hit) != 1:
        raise SystemExit(f"pooled cell {list_name} {model} {attacker} {policy}: {len(hit)} rows")
    return hit.iloc[0]


def write_md(path, title, header, rows):
    lines = [f"# {title}", "", "| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    path.write_text("\n".join(lines) + "\n")


def fmt(value, digits):
    from decimal import Decimal, ROUND_HALF_UP
    return str(Decimal(repr(float(value))).quantize(Decimal(10) ** -digits, rounding=ROUND_HALF_UP))


def table3(pooled):
    policies = [
        ("exact", "Exact box", False),
        ("square-16", "Square grid, 16 px", True),
        ("square-64", "Square grid, 64 px", False),
        ("square-128", "Square grid, 128 px", False),
        ("width-grid-64", "Width-only grid, 64 px", False),
        ("width-grid-128", "Width-only grid, 128 px", False),
        ("ink-anchored-128", "Edge-aligned padding, 128 px", False),
        ("ink-anchored-192", "Edge-aligned padding, 192 px", False),
        ("pen-anchored-96", "Start-aligned padding, 96 px", False),
        ("pen-anchored-128", "Start-aligned padding, 128 px", False),
        ("pen-anchored-192", "Start-aligned padding, 192 px", False),
    ]
    rows = []
    md = []
    for policy, label, skip_ink in policies:
        slug = policy.replace("-", "")
        for list_name in ("surnames", "words"):
            layout = pooled_row(pooled, list_name, "LAYOUT-BOX", "A1", policy)
            add(f"table3.{list_name}.{slug}.bits_layout", layout.bits)
            add(f"table3.{list_name}.{slug}.area", layout.median_overredaction)
            add(f"table3.{list_name}.{slug}.top10", layout.top10 * 100)
            ink_bits = None
            if not (skip_ink and list_name == "surnames" and policy == "square-16"):
                if not (list_name == "words"):
                    ink = pooled_row(pooled, list_name, "PIXEL-INK", "A1", policy)
                    ink_bits = float(ink.bits)
                    add(f"table3.{list_name}.{slug}.bits_ink", ink_bits)
            rows.append({
                "list": list_name, "policy": policy, "label": label,
                "bits_layout": float(layout.bits), "bits_ink": ink_bits,
                "area": float(layout.median_overredaction), "top10": float(layout.top10) * 100,
                "n": int(layout.n),
            })
        s = pooled_row(pooled, "surnames", "LAYOUT-BOX", "A1", policy)
        ink = None if skip_ink else pooled_row(pooled, "surnames", "PIXEL-INK", "A1", policy)
        w = pooled_row(pooled, "words", "LAYOUT-BOX", "A1", policy)
        ink_txt = "–" if ink is None else fmt(ink.bits, 2)
        if policy == "pen-anchored-192":
            ink_txt = "<0.005" if (ink is not None and ink.bits < 0.005) else ink_txt
            s_bits = "<0.005" if s.bits < 0.005 else fmt(s.bits, 2)
            w_bits = "<0.005" if w.bits < 0.005 else fmt(w.bits, 2)
        else:
            s_bits = fmt(s.bits, 2)
            w_bits = fmt(w.bits, 2)
        md.append([label, f"{s_bits} / {ink_txt}", f"{fmt(s.median_overredaction, 2)}×", w_bits, f"{fmt(w.median_overredaction, 2)}×"])
    pd.DataFrame(rows).to_csv(OUT / "table3.csv", index=False)
    write_md(OUT / "table3.md", "Table 3. Policy summary", ["Policy", "Surnames bits layout/ink", "Surnames area", "Words bits", "Words area"], md)


def table4():
    geo = pd.read_csv(DATA / "foia_geometry_summary.csv")
    all_rows = geo[geo.subset == "all"]
    out = []
    md = []
    for _, row in all_rows.iterrows():
        grid = int(row.grid_px)
        add(f"table4.g{grid}.widths", row.distinct_widths)
        add(f"table4.g{grid}.h_width", row.H_width_bits)
        add(f"table4.g{grid}.h_wh", row.H_wh_bits)
        if grid != 1:
            add(f"table4.g{grid}.area", row.over_median)
            add(f"table4.g{grid}.area_p90", row.over_p90)
        if grid == 1:
            add("table4.n", row.n)
            add("table4.median_w", row.median_w)
            add("table4.median_h", row.median_h)
        area = "–" if grid == 1 else f"{fmt(row.over_median, 2)}× ({fmt(row.over_p90, 2)}×)"
        label = "Exact" if grid == 1 else f"{grid} px"
        md.append([label, int(row.distinct_widths), fmt(row.H_width_bits, 2), fmt(row.H_wh_bits, 2), area])
        out.append(row)
    pd.DataFrame(out).to_csv(OUT / "table4.csv", index=False)
    write_md(OUT / "table4.md", "Table 4. Real-box geometry", ["Grid", "Distinct widths", "H(width)", "H(width, height)", "Area"], md)


def table_a1():
    rows = [
        ["Clean", "Exact and square grid", "1, 8, 16, 32, 64", 5],
        ["JPEG quality 75", "Exact and square grid", "1, 8, 16, 32, 64", 5],
        ["Scan-like", "Exact and square grid", "1, 8, 16, 32, 64", 5],
        ["Clean", "Jitter 0–16 px per side, then snap", "1, 16", 2],
        ["Clean", "Edge-aligned 128-px class, full-line height, then snap", "1, 16", 2],
    ]
    cells = sum(r[3] for r in rows)
    units = 99
    redactions = units * cells * 2000
    result_rows = redactions * 2 + 128000
    add("tablea1.cells", cells)
    add("tablea1.units", units)
    add("tablea1.redactions", redactions)
    add("tablea1.result_rows", result_rows)
    write_md(OUT / "table_a1.md", "Table A1. Main-sweep cells", ["Condition", "Policy", "Grid settings (px)", "Cells"], rows)


def table_a2(pooled):
    clean = pd.read_csv(DATA / "pooled_clean_dict_grid_attacker.csv")
    base = pd.read_csv(DATA / "baselines_nobox.csv").set_index("dict")
    policy_for = {1: "exact", 8: "square-8", 16: "square-16", 32: "square-32", 64: "square-64"}
    rows = []
    md = []
    for name in ("surnames", "words"):
        add(f"tablea2.{name}.prior", base.loc[name, "prior_bits"])
        add(f"tablea2.{name}.nobox.top10", base.loc[name, "top10"] * 100)
        for grid, policy in policy_for.items():
            for attacker in ("A1", "A2"):
                if attacker == "A1":
                    src = clean[(clean["dict"] == name) & (clean.grid_px == grid) & (clean.attacker == "A1")].iloc[0]
                    top, bits, area = src.top10 * 100, src.bits_leaked, src.over_median
                else:
                    src = pooled_row(pooled, name, "LAYOUT-BOX", "A2", policy)
                    top, bits, area = src.top10 * 100, src.bits, src.median_overredaction
                add(f"tablea2.{name}.g{grid}.{attacker}.top10", top)
                add(f"tablea2.{name}.g{grid}.{attacker}.bits", bits)
                if attacker == "A1":
                    add(f"tablea2.{name}.g{grid}.area", area)
                rows.append({"list": name, "grid_px": grid, "attacker": attacker, "top10": top, "bits": bits, "area": area})
        line_bits = []
        line_top = []
        area = None
        for grid in policy_for:
            a1 = next(r for r in rows if r["list"] == name and r["grid_px"] == grid and r["attacker"] == "A1")
            a2 = next(r for r in rows if r["list"] == name and r["grid_px"] == grid and r["attacker"] == "A2")
            line_top.append(f"{fmt(a1['top10'], 1)} / {fmt(a2['top10'], 1)}")
            line_bits.append(f"{fmt(a1['bits'], 2)} / {fmt(a2['bits'], 2)}")
            area = f"{fmt(a1['area'], 2)}×"
            label = "Exact" if grid == 1 else f"{grid} px"
            if name == "surnames":
                md.append([label, line_top[-1], line_bits[-1], area, "", "", ""])
            else:
                md[-5 + list(policy_for).index(grid)][4] = line_top[-1]
                md[-5 + list(policy_for).index(grid)][5] = line_bits[-1]
                md[-5 + list(policy_for).index(grid)][6] = area
    pd.DataFrame(rows).to_csv(OUT / "table_a2.csv", index=False)
    write_md(
        OUT / "table_a2.md",
        "Table A2. Leakage by grid",
        ["Grid", "Surnames top-10 A1/A2", "Surnames bits A1/A2", "Surnames area", "Words top-10 A1/A2", "Words bits A1/A2", "Words area"],
        md,
    )


def table_a3():
    forms = pd.read_csv(DATA / "forms" / "start_policy_summary.csv")
    paired = pd.read_csv(DATA / "forms" / "start_vs_grid16_paired.csv")
    spec = [
        ("lo16c", "LibreOffice", 16, "clean", "b_lo_table", "LibreOffice, 16 px, clean"),
        ("lo16s", "LibreOffice", 16, "scan", "b_lo_table", "LibreOffice, 16 px, scan-like"),
        ("lo24c", "LibreOffice", 24, "clean", "b_lo_table", "LibreOffice, 24 px, clean"),
        ("lo24s", "LibreOffice", 24, "scan", "b_lo_table", "LibreOffice, 24 px, scan-like"),
        ("lopm", "LibreOffice", 16, "clean", "a_paper_renderer", "LibreOffice, 16 px, clean, Pillow model"),
        ("pA1", "Pillow", 16, "clean", "A1", "Pillow, 16 px, clean, A1"),
        ("pA2", "Pillow", 16, "clean", "A2", "Pillow, 16 px, clean, A2"),
    ]
    rows = []
    md = []
    for key, renderer, size, cond, attacker, label in spec:
        part = forms[(forms.renderer == renderer) & (forms["size"] == size) & (forms.condition == cond) & (forms.attacker == attacker) & (forms.field == "surname")]
        def hits(policy):
            hit = part[part.policy == policy]
            if len(hit) != 1:
                raise SystemExit(f"form cell {label} {policy}: {len(hit)}")
            return hit.iloc[0]
        exact, g16, start, g64 = hits("exact"), hits("16px"), hits("start128"), hits("64px")
        pair = paired[(paired.renderer == renderer) & (paired["size"] == size) & (paired.condition == cond) & (paired.attacker == attacker) & (paired.field == "surname")]
        if len(pair) != 1:
            raise SystemExit(f"paired form cell {label}: {len(pair)}")
        pair = pair.iloc[0]
        add(f"tablea3.{key}.exact", exact.hits)
        add(f"tablea3.{key}.g16", g16.hits)
        add(f"tablea3.{key}.start", start.hits)
        add(f"tablea3.{key}.diff", pair.difference_points)
        add(f"tablea3.{key}.ci_lo", pair.ci_low)
        add(f"tablea3.{key}.ci_hi", pair.ci_high)
        add(f"tablea3.{key}.area_start", start.median_area_ratio)
        add(f"tablea3.{key}.area_64", g64.median_area_ratio)
        rows.append({"key": key, "exact": exact.hits, "g16": g16.hits, "start": start.hits, "diff": pair.difference_points, "ci_lo": pair.ci_low, "ci_hi": pair.ci_high, "area_start": start.median_area_ratio, "area_64": g64.median_area_ratio})
        md.append([label, fmt(exact.hits, 0), fmt(g16.hits, 0), fmt(start.hits, 0), f"+{fmt(pair.difference_points, 0)} [{fmt(pair.ci_low, 0)}, {fmt(pair.ci_high, 0)}]", f"{fmt(start.median_area_ratio, 2)}× / {fmt(g64.median_area_ratio, 2)}×"])
    pd.DataFrame(rows).to_csv(OUT / "table_a3.csv", index=False)
    write_md(OUT / "table_a3.md", "Table A3. Mock forms", ["Forms", "Exact", "16-px grid", "Start-aligned", "Difference [CI]", "Area, start / 64 px"], md)


def table_a4():
    frame = pd.read_csv(CASES / "followup" / "e1_a4_cases.csv.gz")
    rows = []
    md = []
    for grid, label in ((1, "exact"), (8, "8"), (16, "16"), (32, "32"), (64, "64")):
        part = frame[frame.grid_px == grid]
        prior = part.hit10_freq.mean() * 100
        lm = part.rank_lm_full.le(10).mean() * 100
        add(f"tablea4.dejavu.{label}.prior", prior)
        add(f"tablea4.dejavu.{label}.lm", lm)
        rows.append({"grid": label, "prior": prior, "lm": lm, "n": int(len(part))})
        md.append([label, fmt(prior, 1), fmt(lm, 1), "EXPLORATORY (needs a4_reproduction.csv)"])
    pd.DataFrame(rows).to_csv(OUT / "table_a4.csv", index=False)
    write_md(OUT / "table_a4.md", "Table A4. DejaVu Sans sentence context (Liberation Serif and the no-box LM count are not in the archive)", ["Grid", "Prior", "LM", "Gain"], md)


def table_a5():
    frame = pd.read_csv(DATA / "paired_tests.csv")
    comparisons = [
        ("exact>8", "exact8"),
        ("8>16", "g8g16"),
        ("16>32", "g16g32"),
        ("32>64", "g32g64"),
        ("64>pad", "g64edge"),
        ("64>start", "g64start"),
    ]
    rows = []
    md = []
    for comparison, slug in comparisons:
        for list_name in ("surnames", "words"):
            for metric in ("top10", "bits"):
                sub = frame[(frame.list == list_name) & (frame.attacker == "A1") & (frame.model == "LAYOUT-BOX") & (frame.comparison == comparison) & (frame.metric == metric)]
                fonts = sub[sub.font != "pooled"]
                pooled = sub[sub.font == "pooled"]
                if fonts.empty or pooled.empty:
                    continue
                holm = int((fonts.p_holm < 0.05).sum())
                delta = float(pooled.iloc[0].difference)
                scale = 100.0 if metric == "top10" else 1.0
                add(f"tablea5.{list_name}.{slug}.{metric}.holm", holm)
                add(f"tablea5.{list_name}.{slug}.{metric}.delta", delta * scale)
                add(f"tablea5.{list_name}.{slug}.{metric}.ci_lo", float(pooled.iloc[0].ci_lo) * scale)
                add(f"tablea5.{list_name}.{slug}.{metric}.ci_hi", float(pooled.iloc[0].ci_hi) * scale)
                rows.append({"list": list_name, "comparison": comparison, "metric": metric, "holm": holm, "delta": delta * scale, "ci_lo": float(pooled.iloc[0].ci_lo) * scale, "ci_hi": float(pooled.iloc[0].ci_hi) * scale, "n_fonts": int(len(fonts))})
        s_top = next(r for r in rows if r["list"] == "surnames" and r["comparison"] == comparison and r["metric"] == "top10")
        s_bits = next(r for r in rows if r["list"] == "surnames" and r["comparison"] == comparison and r["metric"] == "bits")
        w_top = next(r for r in rows if r["list"] == "words" and r["comparison"] == comparison and r["metric"] == "top10")
        md.append([
            comparison,
            s_top["holm"],
            s_bits["holm"],
            f"{fmt(s_top['delta'], 1)} [{fmt(s_top['ci_lo'], 1)}, {fmt(s_top['ci_hi'], 1)}]",
            w_top["holm"],
            f"{fmt(w_top['delta'], 1)} [{fmt(w_top['ci_lo'], 1)}, {fmt(w_top['ci_hi'], 1)}]",
        ])
    pd.DataFrame(rows).to_csv(OUT / "table_a5.csv", index=False)
    write_md(OUT / "table_a5.md", "Table A5. Paired tests (paired Holm count and pooled delta; the pre-correction arrow is not a separate column)", ["Comparison", "Surnames Holm top-10", "Surnames Holm bits", "Surnames Δ top-10 [CI]", "Words Holm top-10", "Words Δ top-10 [CI]"], md)


def table_a6(pooled):
    fonts = pd.read_csv(DATA / "per_font.csv")
    policies = ["exact", "square-16", "square-64", "ink-anchored-128", "pen-anchored-128", "width-grid-64"]
    part = fonts[(fonts.list == "surnames") & (fonts.model == "LAYOUT-BOX") & (fonts.attacker == "A1") & (fonts.policy.isin(policies))]
    rows = []
    md = []
    order = ["DejaVuSans", "DejaVuSerif", "LiberationMono", "LiberationSans", "LiberationSerif", "NotoSans"]
    for font in order:
        cells = []
        for policy in policies:
            block = part[(part.font == font) & (part.policy == policy)]
            if block.empty or int(block.n.sum()) == 0:
                raise SystemExit(f"per-font cell missing {font} {policy}")
            weight = block.n.to_numpy()
            top = (block.top10.to_numpy() * weight).sum() / weight.sum() * 100
            bits = (block.bits.to_numpy() * weight).sum() / weight.sum()
            add(f"tablea6.{font}.{policy}.top10", top)
            add(f"tablea6.{font}.{policy}.bits", bits)
            cells.append(f"{fmt(top, 1)} / {fmt(bits, 2)}")
            rows.append({"font": font, "policy": policy, "top10": top, "bits": bits, "n": int(weight.sum())})
        md.append([font, *cells])
    pooled_cells = []
    for policy in policies:
        row = pooled_row(pooled, "surnames", "LAYOUT-BOX", "A1", policy)
        add(f"tablea6.pooled.{policy}.top10", row.top10 * 100)
        add(f"tablea6.pooled.{policy}.bits", row.bits)
        add(f"tablea6.pooled.{policy}.area", row.median_overredaction)
        pooled_cells.append(f"{fmt(row.top10 * 100, 1)} / {fmt(row.bits, 2)}")
        rows.append({"font": "pooled", "policy": policy, "top10": row.top10 * 100, "bits": row.bits, "n": int(row.n)})
    md.append(["Pooled", *pooled_cells])
    md.append(["Area, pooled", *[f"{fmt(pooled_row(pooled, 'surnames', 'LAYOUT-BOX', 'A1', p).median_overredaction, 2)}×" for p in policies]])
    pd.DataFrame(rows).to_csv(OUT / "table_a6.csv", index=False)
    write_md(OUT / "table_a6.md", "Table A6. Per-font surnames", ["Font", "Exact", "16-px grid", "64-px grid", "Edge-aligned 128", "Start-aligned 128", "Width-only 64"], md)


def copies_and_jitter(pooled):
    a3 = pd.read_csv(CASES / "posterior" / "a3_cases.csv.gz")
    base = pd.read_csv(DATA / "baselines_nobox.csv").set_index("dict").prior_bits
    summary = pd.read_csv(DATA / "results_summary.csv")
    fig4 = []
    for name in ("surnames", "words"):
        for grid in (8, 16, 32, 64):
            for k in (1, 2, 3, 5):
                part = a3[(a3["dict"] == name) & (a3["size"] == 16) & (a3.font.isin(["DejaVuSans", "LiberationSerif"])) & (a3.grid_px == grid) & (a3.k == k)]
                if part.empty:
                    continue
                top = part.hit10_lik.mean() * 100
                bits = float(base[name] - part.resid_lik.mean())
                add(f"fig4a.{name}.g{grid}.k{k}.top10", top)
                add(f"fig4a.{name}.g{grid}.k{k}.bits", bits)
                fig4.append({"series": "grid", "list": name, "grid_px": grid, "k": k, "top10": top, "bits": bits})
    pad = summary[(summary.condition == "shifted") & (summary.list == "surnames") & (summary["size"] == 16) & (summary.attacker == "A3") & (summary.model == "layout") & (summary.class_px == 128) & (summary.grid == 1)]
    for k in (1, 5):
        part = pad[pad.k == k]
        add(f"fig4a.pad.k{int(k)}.top10", float(part.top10_1.mean()))
        fig4.append({"series": "pad", "list": "surnames", "grid_px": 128, "k": int(k), "top10": float(part.top10_1.mean()), "bits": float(part.bits_1.mean())})
    jitter = summary[(summary.condition == "jitter") & (summary.list == "surnames") & (summary.font == "DejaVuSans") & (summary["size"] == 24) & (summary.model == "layout") & (summary.class_px == 128) & (summary.grid == 1) & (summary.attacker == "A1")]
    for _, row in jitter.iterrows():
        add(f"fig4b.jitter.k{int(row.k)}.bits", row.bits_k if int(row.k) == 5 else row.bits_1)
        add(f"fig4b.jitter.k{int(row.k)}.top10", row.top10_k if int(row.k) == 5 else row.top10_1)
    canon = pooled[(pooled.list == "surnames") & (pooled["size_px"].astype(str) == "24") & (pooled.model == "LAYOUT-BOX") & (pooled.attacker == "A1") & (pooled.policy == "pen-anchored-128")]
    # per-font DejaVu Sans is the canonical single-font mask named in Section 4.4
    fonts = pd.read_csv(DATA / "per_font.csv")
    one = fonts[(fonts.list == "surnames") & (fonts.font == "DejaVuSans") & (fonts["size_px"] == 24) & (fonts.model == "LAYOUT-BOX") & (fonts.attacker == "A1") & (fonts.policy == "pen-anchored-128")]
    if len(one) != 1:
        raise SystemExit(f"canonical mask rows: {len(one)}")
    add("fig4b.unjittered.bits", float(one.iloc[0].bits))
    font = summary[(summary.condition == "font") & (summary.list == "surnames") & (summary.font == "mixed") & (summary["size"] == 24) & (summary.model == "layout") & (summary.class_px == 128) & (summary.attacker == "A1") & (summary.k == 5)]
    if len(font) != 1:
        raise SystemExit(f"font-change rows: {len(font)}")
    font = font.iloc[0]
    add("fig4b.font.k1.bits", float(font.bits_1))
    add("fig4b.font.k5.bits", float(font.bits_k))
    add("fig4b.font.changed", float(font.targets_change_class))
    wide = summary[(summary.condition == "font") & (summary.list == "surnames") & (summary.font == "mixed") & (summary["size"] == 24) & (summary.model == "layout") & (summary.class_px == 192) & (summary.attacker == "A1") & (summary.k == 5)]
    add("fig4b.class192.k5.bits", float(wide.iloc[0].bits_k))
    pd.DataFrame(fig4).to_csv(OUT / "figure4a.csv", index=False)
    _ = canon


def attacker_and_extra():
    test4 = pd.read_csv(CASES / "followup" / "test4_cases.csv.gz")
    grouped = test4.groupby(["dict", "grid_px", "attacker", "variant"], as_index=False).agg(top10=("hit10", "mean"), bits=("bits_leaked", "mean"), n=("case", "size"))
    grouped.to_csv(OUT / "test4_fontcluster.csv", index=False)
    for variant, slug in (("K", "known"), ("Fu", "font_unknown"), ("Pu_uniform_prior", "uniform")):
        row = grouped[(grouped["dict"] == "surnames") & (grouped.grid_px == 1) & (grouped.attacker == "A1") & (grouped.variant == variant)].iloc[0]
        add(f"fig5.{slug}.top10", row.top10 * 100)
    d2 = pd.read_csv(CASES / "followup" / "d2jit_cases.csv.gz")
    pool = d2.groupby(["dict", "size", "attacker", "k"], as_index=False).agg(top10=("hit10_lik", "mean"), resid=("resid_lik", "mean"), H0=("H0", "first"), n=("case", "size"))
    pool["bits"] = pool.H0 - pool.resid
    pool.to_csv(OUT / "d2jit_pooled.csv", index=False)
    d16 = pd.read_csv(CASES / "posterior" / "d2jit16_cases.csv.gz")
    pool16 = d16.groupby(["dict", "size", "variant", "k"], as_index=False).agg(top10=("hit10_lik", "mean"), resid=("resid_lik", "mean"), n=("case", "size"))
    pool16.to_csv(OUT / "d2jit16_pooled.csv", index=False)


def table_a7():
    rows = [
        ["Table 3, Figure 2, Figure 3, Table A6", "research/e1/review4/pooled.csv, research/e1/data/per_font.csv", "REPRODUCED"],
        ["Table 4, Figure not separate", "research/e1/data/foia_geometry_summary.csv", "REPRODUCED"],
        ["Table A1", "research/e1/e1_run.py cell matrix", "REPRODUCED"],
        ["Table A2, Figure 1", "research/e1/data/pooled_clean_dict_grid_attacker.csv and pooled.csv A2 column", "REPRODUCED"],
        ["Table A3, Figure 6", "research/e1/data/forms/start_policy_summary.csv", "REPRODUCED"],
        ["Table A4 DejaVu exact and grids", "research/e1/cases/followup/e1_a4_cases.csv.gz", "REPRODUCED"],
        ["Table A4 Liberation, sentence-alone 179/400, padding gain", "a4_reproduction.csv", "EXPLORATORY"],
        ["Table A5 paired Holm and pooled delta", "research/e1/data/paired_tests.csv", "REPRODUCED"],
        ["Table A5 earlier independent-proportion arrow", "not a column in paired_tests.csv", "EXPLORATORY"],
        ["Figure 4a grid copies", "research/e1/cases/posterior/a3_cases.csv.gz", "REPRODUCED"],
        ["Figure 4b jitter and font change", "research/e1/data/results_summary.csv and per_font.csv", "REPRODUCED"],
        ["Figure 4b edge-aligned 0.38 to 1.30", "not in results_summary.csv", "EXPLORATORY"],
        ["Figure 5 font-unknown and uniform prior", "research/e1/cases/followup/test4_cases.csv.gz", "REPRODUCED"],
        ["Figure 5 word-frequency prior 48.3 to 21.2 and 6.48 bits", "s4_priors.csv", "EXPLORATORY"],
        ["Figure 5 recalibrated 31/100", "not a row in the form summary", "EXPLORATORY"],
        ["Own-height cells", "w1_pooled.csv; the manuscript says these cells are not reported", "EXPLORATORY"],
        ["Form page images", "not in the repository", "EXPLORATORY"],
        ["s2_rerender.csv raw file", "class-change count 188 is in results_summary.csv; the raw file is absent", "EXPLORATORY"],
        ["d2jit_pooled.csv", "rebuilt by this script from d2jit_cases.csv.gz", "REPRODUCED"],
        ["test4_fontcluster.csv", "rebuilt by this script from test4_cases.csv.gz", "REPRODUCED"],
    ]
    write_md(OUT / "table_a7.md", "Table A7. Evidence inventory for this artifact", ["Item", "File", "Status"], rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pooled = pd.read_csv(POOLED)
    table3(pooled)
    table4()
    table_a1()
    table_a2(pooled)
    table_a3()
    table_a4()
    table_a5()
    table_a6(pooled)
    copies_and_jitter(pooled)
    attacker_and_extra()
    table_a7()
    with (OUT / "values.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "value"])
        writer.writerows(VALUES)
    print(f"Wrote {len(VALUES)} values to {OUT}")


if __name__ == "__main__":
    main()
