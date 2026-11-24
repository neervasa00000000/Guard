"""Summaries, figures, and the validation report. Numbers come from the run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import geometry

DRAWS = 10000
POLICY_ORDER = list(geometry.POLICIES)
POLICY_LABEL = {
    "exact": "Exact box",
    "square16": "Square 16",
    "square64": "Square 64",
    "width64": "Width grid 64",
    "start128": "Start-aligned 128",
    "field": "Field-wide",
}


def _rng(key):
    digest = hashlib.sha256(f"20261118:{key}".encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "little"))


def _groups(docs, values):
    docs = np.asarray(docs)
    values = np.asarray(values, dtype=np.float64)
    ok = np.isfinite(values)
    docs, values = docs[ok], values[ok]
    if len(values) == 0:
        return None
    unique, inverse = np.unique(docs, return_inverse=True)
    buckets = [values[inverse == index] for index in range(len(unique))]
    return unique, buckets, values


def mean_ci(docs, values, key):
    grouped = _groups(docs, values)
    if grouped is None:
        return {"estimate": np.nan, "lo": np.nan, "hi": np.nan, "n": 0, "documents": 0}
    unique, buckets, values = grouped
    sums = np.array([bucket.sum() for bucket in buckets])
    counts = np.array([len(bucket) for bucket in buckets])
    estimate = float(values.mean())
    if len(unique) < 2:
        return {"estimate": estimate, "lo": np.nan, "hi": np.nan, "n": int(len(values)), "documents": int(len(unique))}
    take = _rng(key).integers(0, len(unique), size=(DRAWS, len(unique)))
    means = sums[take].sum(axis=1) / np.maximum(counts[take].sum(axis=1), 1)
    return {
        "estimate": estimate,
        "lo": float(np.percentile(means, 2.5)),
        "hi": float(np.percentile(means, 97.5)),
        "n": int(len(values)),
        "documents": int(len(unique)),
    }


def percentile_ci(docs, values, key, quantile):
    grouped = _groups(docs, values)
    if grouped is None:
        return {"estimate": np.nan, "lo": np.nan, "hi": np.nan, "n": 0, "documents": 0}
    unique, buckets, values = grouped
    estimate = float(np.percentile(values, quantile))
    if len(unique) < 2:
        return {"estimate": estimate, "lo": np.nan, "hi": np.nan, "n": int(len(values)), "documents": int(len(unique))}
    rng = _rng(key + f":p{quantile}")
    stats = np.empty(DRAWS)
    for draw in range(DRAWS):
        take = rng.integers(0, len(unique), size=len(unique))
        stats[draw] = np.percentile(np.concatenate([buckets[index] for index in take]), quantile)
    return {
        "estimate": estimate,
        "lo": float(np.percentile(stats, 2.5)),
        "hi": float(np.percentile(stats, 97.5)),
        "n": int(len(values)),
        "documents": int(len(unique)),
    }


def _num(series):
    return pd.to_numeric(series, errors="coerce")


def summarize(frame):
    rows = []
    if frame.empty:
        return pd.DataFrame(rows)
    work = frame[frame["track"] == "controlled_insertion"].copy()
    slices = []
    for size in (12, 16):
        for condition in sorted(work["condition"].unique()):
            part = work[(work["size_px"] == size) & (work["condition"] == condition) & (work["role"] == "evaluation")]
            if len(part):
                slices.append(("all", part))
            if condition == "matched_template_known" and size == 16:
                for category, group in part.groupby("doc_category"):
                    slices.append((str(category), group))
    metrics = [
        ("prior_top1", "prior_hit1", "mean"),
        ("prior_top10", "prior_hit10", "mean"),
        ("geo_top1", "geo_hit1", "mean"),
        ("geo_top10", "geo_hit10", "mean"),
        ("bits", "entropy_reduction", "mean"),
        ("pointwise_mean", "pointwise_bits", "mean"),
        ("feasible_mean", "feasible", "mean"),
        ("fraction_obscured", "fraction_ink_obscured", "mean"),
        ("neighbor_regions", "unrelated_regions", "mean"),
        ("neighbor_words", "neighbor_words_est", "mean"),
        ("neighbor_chars", "neighbor_chars_est", "mean"),
        ("unrelated_overlap", "unrelated_overlap", "mean"),
    ]
    for category, part in slices:
        for policy, group in part.groupby("policy"):
            docs = group["doc_name"].to_numpy()
            key = f"{group['size_px'].iloc[0]}|{group['condition'].iloc[0]}|{category}|{policy}"
            pointwise = _num(group["pointwise_bits"])
            record = {
                "track": "controlled_insertion",
                "role": "evaluation",
                "size_px": int(group["size_px"].iloc[0]),
                "condition": group["condition"].iloc[0],
                "category": category,
                "policy": policy,
                "n_targets": int(len(group)),
                "n_documents": int(group["doc_name"].nunique()),
                "n_pages": int(group["file_name"].nunique()),
                "candidate_n": int(group["candidate_n"].iloc[0]),
                "truth_in_set_rate": float(_num(group["truth_in_set"]).mean()),
                "pointwise_max": None if pointwise.dropna().empty else float(pointwise.max()),
                "ocr_reliability": group["ocr_reliability"].iloc[0],
            }
            for name, column, kind in metrics:
                if kind == "mean":
                    stat = mean_ci(docs, _num(group[column]), key + "|" + name)
                    record[name] = stat["estimate"]
                    record[name + "_lo"] = stat["lo"]
                    record[name + "_hi"] = stat["hi"]
            if group["condition"].iloc[0] == "matched_template_known" and category == "all":
                for name, column, quantile in (
                    ("area_ratio_median", "area_ratio", 50),
                    ("area_ratio_p90", "area_ratio", 90),
                    ("over_area_median", "over_area", 50),
                    ("over_area_p90", "over_area", 90),
                ):
                    stat = percentile_ci(docs, _num(group[column]), key + "|" + name, quantile)
                    record[name] = stat["estimate"]
                    record[name + "_lo"] = stat["lo"]
                    record[name + "_hi"] = stat["hi"]
            else:
                record["area_ratio_median"] = float(np.nanpercentile(_num(group["area_ratio"]), 50))
                record["area_ratio_p90"] = float(np.nanpercentile(_num(group["area_ratio"]), 90))
                record["over_area_median"] = float(np.nanpercentile(_num(group["over_area"]), 50))
                record["over_area_p90"] = float(np.nanpercentile(_num(group["over_area"]), 90))
                record["area_ratio_median_lo"] = np.nan
                record["area_ratio_median_hi"] = np.nan
                record["area_ratio_p90_lo"] = np.nan
                record["area_ratio_p90_hi"] = np.nan
                record["over_area_median_lo"] = np.nan
                record["over_area_median_hi"] = np.nan
                record["over_area_p90_lo"] = np.nan
                record["over_area_p90_hi"] = np.nan
            rows.append(record)
    contrasts = contrast_rows(work)
    return pd.DataFrame(rows), pd.DataFrame(contrasts)


def contrast_rows(work):
    rows = []
    part = work[(work["role"] == "evaluation") & (work["size_px"] == 16) & (work["condition"] == "matched_template_known")]
    pairs = [
        ("exact", "square16"),
        ("exact", "square64"),
        ("exact", "width64"),
        ("exact", "start128"),
        ("exact", "field"),
        ("square16", "square64"),
        ("width64", "start128"),
        ("start128", "field"),
    ]
    for left, right in pairs:
        a = part[part["policy"] == left][["target_id", "doc_name", "entropy_reduction", "geo_hit10", "area_ratio", "fraction_ink_obscured"]]
        b = part[part["policy"] == right][["target_id", "entropy_reduction", "geo_hit10", "area_ratio", "fraction_ink_obscured"]]
        merged = a.merge(b, on="target_id", suffixes=("_l", "_r"))
        if merged.empty:
            continue
        for column in ("entropy_reduction", "geo_hit10", "area_ratio", "fraction_ink_obscured"):
            diff = _num(merged[column + "_l"]) - _num(merged[column + "_r"])
            stat = mean_ci(merged["doc_name"], diff, f"contrast|{left}|{right}|{column}")
            rows.append({
                "size_px": 16,
                "condition": "matched_template_known",
                "left": left,
                "right": right,
                "metric": column,
                "difference": stat["estimate"],
                "lo": stat["lo"],
                "hi": stat["hi"],
                "n_targets": stat["n"],
                "n_documents": stat["documents"],
            })
    return rows


def _lookup(summary, **wanted):
    part = summary
    for key, value in wanted.items():
        part = part[part[key] == value]
    if part.empty:
        return None
    return part.iloc[0]


def _fmt(value, digits=3):
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "—"
    return f"{float(value):.{digits}f}"


def _interval(row, name, digits=3):
    if row is None:
        return "—"
    return f"{_fmt(row[name], digits)} ({_fmt(row[name + '_lo'], digits)}, {_fmt(row[name + '_hi'], digits)})"


def write_figures(out, summary, stage):
    figure_dir = out / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    if summary.empty or stage == "pilot":
        # Pilot figures are still useful as a wiring check. The report says so.
        pass
    matched = summary[
        (summary["condition"] == "matched_template_known")
        & (summary["category"] == "all")
        & (summary["size_px"] == 16)
    ]
    if matched.empty:
        return
    order = [policy for policy in POLICY_ORDER if policy in set(matched["policy"])]
    matched = matched.set_index("policy").loc[order]
    labels = [POLICY_LABEL[policy] for policy in order]
    _bar(labels, matched["bits"], matched["bits_lo"], matched["bits_hi"], "Information leakage (bits)", figure_dir / "leakage_bits")
    _bar(labels, matched["geo_top10"] * 100, matched["geo_top10_lo"] * 100, matched["geo_top10_hi"] * 100, "Geometry top-10 (%)", figure_dir / "top10")
    _bar(labels, matched["area_ratio_median"], matched["area_ratio_median_lo"], matched["area_ratio_median_hi"], "Median area ratio", figure_dir / "area_ratio")
    _bar(labels, matched["fraction_obscured"] * 100, matched["fraction_obscured_lo"] * 100, matched["fraction_obscured_hi"] * 100, "Neighboring ink hidden (%)", figure_dir / "neighbor_ink")
    conditions = ["matched_template_known", "renderer_mismatch", "font_mismatch", "font_unknown", "start_unknown"]
    exact = summary[(summary["policy"] == "exact") & (summary["category"] == "all") & (summary["size_px"] == 16)]
    exact = exact.set_index("condition")
    present = [condition for condition in conditions if condition in exact.index]
    if present:
        part = exact.loc[present]
        _bar(
            present,
            part["geo_top10"] * 100,
            part["geo_top10_lo"] * 100,
            part["geo_top10_hi"] * 100,
            "Exact-box top-10 by attacker condition (%)",
            figure_dir / "exact_by_condition",
        )


def _bar(labels, center, low, high, ylabel, path):
    center = np.asarray(center, dtype=float)
    low = np.asarray(low, dtype=float)
    high = np.asarray(high, dtype=float)
    error = np.vstack([np.nan_to_num(center - low, nan=0.0), np.nan_to_num(high - center, nan=0.0)])
    figure, axis = plt.subplots(figsize=(8.2, 4.4))
    positions = np.arange(len(labels))
    axis.bar(positions, np.nan_to_num(center), color="#3c5a73", width=0.72)
    axis.errorbar(positions, center, yerr=error, fmt="none", ecolor="black", capsize=3, lw=0.8)
    axis.set_xticks(positions)
    axis.set_xticklabels(labels, rotation=25, ha="right")
    axis.set_ylabel(ylabel)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    figure.tight_layout()
    figure.savefig(path.with_suffix(".png"), dpi=140)
    figure.savefig(path.with_suffix(".pdf"))
    plt.close(figure)


def save_examples(out, examples):
    example_dir = out / "examples"
    example_dir.mkdir(parents=True, exist_ok=True)
    notes = ["The surname in each crop was inserted for this experiment. It was not printed on the DocLayNet page.", ""]
    for index, example in enumerate(examples, start=1):
        panels = [("Page", example["rgb"])]
        composed = example["composed"]
        panels.append(("Inserted surname", composed))
        by_policy = {row["policy"]: row for row in example["rows"]}
        image = composed.copy()
        for policy, title in (("exact", "Exact"), ("square64", "Square 64"), ("start128", "Start 128")):
            panel = composed.copy()
            row = by_policy.get(policy)
            if row is not None:
                draw = panel.copy()
                x0, y0, x1, y1 = row["box_x0"], row["box_y0"], row["box_x1"], row["box_y1"]
                draw[y0:y1, x0:x1] = (0, 0, 0)
                panel = draw
            panels.append((title, panel))
        boxes = [row for row in example["rows"] if row["policy"] in {"exact", "square64", "start128"}]
        x0 = min(row["box_x0"] for row in boxes) - 36
        y0 = min(row["box_y0"] for row in boxes) - 36
        x1 = max(row["box_x1"] for row in boxes) + 36
        y1 = max(row["box_y1"] for row in boxes) + 36
        height, width = example["rgb"].shape[:2]
        x0, y0, x1, y1 = geometry.clip_box((x0, y0, x1, y1), width, height)
        figure, axes = plt.subplots(1, len(panels), figsize=(3.1 * len(panels), 3.4))
        for axis, (title, image) in zip(axes, panels):
            axis.imshow(image[y0:y1, x0:x1])
            axis.set_title(title, fontsize=9)
            axis.axis("off")
        figure.suptitle(f"Inserted {example['text']} on a {example['category'].replace('_', ' ')} page", fontsize=11)
        figure.tight_layout()
        figure.savefig(example_dir / f"example_{index}.png", dpi=140)
        figure.savefig(example_dir / f"example_{index}.pdf")
        plt.close(figure)
        notes.append(f"- example_{index}: category {example['category']}, page {example['page_no']}, file {example['file_name']}, inserted string {example['text']}.")
    (example_dir / "NOTES.md").write_text("\n".join(notes) + "\n")


def judgment(summary, contrasts, diagnostics, analytic):
    row = lambda policy: _lookup(summary, size_px=16, condition="matched_template_known", category="all", policy=policy)
    exact, square16, square64 = row("exact"), row("square16"), row("square64")
    width64, start128, field = row("width64"), row("start128"), row("field")
    lines = []
    if exact is None:
        return ["No matched 16 px evaluation rows were produced."]

    def contrast(left, right, metric):
        part = contrasts[(contrasts["left"] == left) & (contrasts["right"] == right) & (contrasts["metric"] == metric)]
        return None if part.empty else part.iloc[0]

    leak = contrast("exact", "square64", "entropy_reduction")
    useful = np.isfinite(exact["bits_lo"]) and exact["bits_lo"] > 0.5 and (exact["geo_top10"] - exact["prior_top10"]) > 0.05
    lines.append(
        "1. Exact-box geometry on these real layouts, with the font and renderer matched and the template known, "
        + ("does expose information beyond the prior. " if useful else "does not clear the predeclared bar for useful leakage. ")
        + f"Mean leakage {_interval(exact, 'bits')} bits; geometry top-10 {_interval(exact, 'geo_top10', 3)}; prior top-10 {_interval(exact, 'prior_top10', 3)}."
    )
    grids_help = leak is not None and np.isfinite(leak["lo"]) and leak["lo"] > 0 and square64["area_ratio_median"] > 3
    lines.append(
        "2. The 64 px square grid "
        + ("reduces leakage and its median area ratio is more than three times the exact box. " if grids_help else "does not meet both parts of the predeclared grid claim. ")
        + f"Exact minus square-64 leakage {_fmt(None if leak is None else leak['difference'])} bits "
        + f"({_fmt(None if leak is None else leak['lo'])}, {_fmt(None if leak is None else leak['hi'])}). "
        + f"Square-16 leakage {_interval(square16, 'bits')}; square-64 leakage {_interval(square64, 'bits')}; "
        + f"median area ratios {_fmt(None if square16 is None else square16['area_ratio_median'], 2)} and {_fmt(square64['area_ratio_median'], 2)}."
    )
    start_low = start128 is not None and np.isfinite(start128["bits_hi"]) and start128["bits_hi"] < 1.0 and start128["bits"] < exact["bits"] / 3
    lines.append(
        "3. Start-aligned 128 px padding, which this protocol can score only because the insertion supplies the template, "
        + ("keeps leakage well below the exact box. " if start_low else "does not meet the predeclared low-leakage bar. ")
        + f"Leakage {_interval(start128, 'bits')} bits; top-10 {_interval(start128, 'geo_top10')}. "
        + "A DocLayNet page does not by itself provide that template."
    )
    field_zero = field is not None and abs(float(field["bits"])) < 1e-8 and abs(float(field["truth_in_set_rate"]) - 1) < 1e-8
    lines.append(
        "4. The fixed field-wide box "
        + ("has zero geometry leakage under the closed 1,000-name list and the supplied template. " if field_zero else "did not reproduce zero geometry leakage. ")
        + f"Leakage {_interval(field, 'bits')} bits; feasible-set mean {_fmt(None if field is None else field['feasible_mean'], 1)}; "
        + f"top-10 {_interval(field, 'geo_top10')}, against prior top-10 {_interval(field, 'prior_top10')}."
    )
    def ink_key(policy):
        current = row(policy)
        if current is None or not np.isfinite(current["fraction_obscured"]):
            return -1
        return float(current["fraction_obscured"])

    ink_policy = max(POLICY_ORDER, key=ink_key)
    lines.append(
        f"5. Among the six policies, {POLICY_LABEL[ink_policy]} hides the largest share of neighboring original ink "
        f"({_interval(row(ink_policy), 'fraction_obscured')} of the scoped original ink). "
        "OCR word and character counts are estimates from Vision with proportional word boxes. "
        "Width-only, start-aligned, and field masks are not equally deployable: they need a template the page does not provide."
    )
    analytic_bits = {item["policy"]: item["analytic_bits"] for item in analytic if item["size_px"] == 16}
    gaps = []
    for policy in POLICY_ORDER:
        current = row(policy)
        if current is None or policy not in analytic_bits:
            continue
        gaps.append(f"{policy} sample {_fmt(current['bits'])} vs layout-free {_fmt(analytic_bits[policy])}")
    lines.append(
        "6. Comparison with the synthetic study is directional. The manuscript's locked surname table is not recomputed here, and this DejaVu file is not the knowledge-matched font binary. "
        "Layout-free leakage from this font and the 1,000-name prior, placed far from a page edge, is the right numerical reference for the matched attack. "
        + " ".join(gaps)
        + ". Original printed text was not given a matched-renderer score: DocLayNet core has no transcription, and a Pillow font hypothesis is not the renderer that produced the page."
    )
    if not diagnostics.get("original_privacy_used", False):
        lines.append(
            f"The original-text privacy rows were withheld. False-accept rate {_fmt(diagnostics.get('false_accept_rate'), 4)}; "
            f"rows withheld {diagnostics.get('original_rows_withheld')}."
        )
    return lines


def write_report(out, summary, contrasts, manifest, diagnostics, analytic, config, stage):
    selected = [row for row in manifest if str(row["decision"]).startswith("selected")]
    excluded = [row for row in manifest if not str(row["decision"]).startswith("selected")]
    counts = pd.Series([row["exclusion_reason"] or row["decision"] for row in manifest]).value_counts().to_dict() if manifest else {}
    eval_pages = len({row["file_name"] for row in selected if row["decision"] == "selected_evaluation"})
    cal_pages = len({row["file_name"] for row in selected if row["decision"] == "selected_calibration"})
    eval_docs = len({row["doc_name"] for row in selected if row["decision"] == "selected_evaluation"})
    text = f"""# DocLayNet validation report

This file is generated from the CSVs in this directory. It does not replace the manuscript and it does not change any locked number.

Stage: `{stage}`. {"These are pilot wiring checks, not the validation estimates." if stage == "pilot" else "Evaluation estimates use document-level bootstrap intervals with 10,000 replicates."}

## Methods

DocLayNet 1.0.0 core, license CDLA-Permissive-1.0, was read from `dataset/DocLayNet_core`. The COCO files were checked against the SHA-256 values in `experiment_config.json`. The archive contains page PNGs and layout boxes. It does not contain PDF text or the DocLayNet extra JSON cells, so layout labels were not treated as transcriptions.

Pages were drawn with seed {config["seed"]}, at most two pages from a document, with no document shared by the calibration and evaluation roles. The primary insertion uses DejaVu Sans at 16 px. A 12 px run is a sensitivity. Surnames are the existing 1,000-name Census list. The font file hash is recorded and is not the hash in the knowledge-matched font manifest.

Policies call `guard_rw.exact_box`, `snap_out`, `candidate_boxes`, and `shared_frame`. Exact and square masks need the painted ink. Width-only, start-aligned, and field masks also need the template this protocol creates by inserting the string. Those three are not scored on original page text.

Attacker conditions are `matched_template_known`, `renderer_mismatch` (PyMuPDF raster of the same font file), `font_mismatch` (Arial), `font_unknown` (union over the font bank and sizes 12–20), and `start_unknown` (exact and square policies only). Hits use the existing expected-hit rule. Leakage is prior entropy minus posterior entropy on the feasible set.

Neighboring-ink loss uses the original pixels outside the rectangle cleared to make room for the insertion. OCR word and character counts are estimates. Area ratio divides by the exact-box area.

## Sample

- Annotated pages in the COCO files: {config["coco_pages"]}
- Pages opened while filling the quotas: {config["pages_opened"]}
- Evaluation pages: {eval_pages} across {eval_docs} documents
- Calibration pages: {cal_pages}
- Decision counts: {json.dumps(counts)}

Exclusions are rows in `dataset_manifest.csv` whose decision does not start with `selected`. Unvisited pages stayed in the corpus and were not treated as evaluated.

## Results

"""
    if summary.empty:
        text += "No evaluation rows were scored.\n"
    else:
        text += "Matched template, 16 px, all evaluation categories. Intervals are document-clustered 95% percentile intervals.\n\n"
        text += "| Policy | Leakage bits | Top-10 | Prior top-10 | Median area ratio | Neighbor ink | Unrelated regions |\n| --- | --- | --- | --- | --- | --- | --- |\n"
        for policy in POLICY_ORDER:
            current = _lookup(summary, size_px=16, condition="matched_template_known", category="all", policy=policy)
            if current is None:
                continue
            text += (
                f"| {POLICY_LABEL[policy]} | {_interval(current, 'bits')} | {_interval(current, 'geo_top10')} | "
                f"{_interval(current, 'prior_top10')} | {_interval(current, 'area_ratio_median', 2)} | "
                f"{_interval(current, 'fraction_obscured')} | {_interval(current, 'neighbor_regions', 2)} |\n"
            )
        text += "\n### Other attacker conditions, exact box, 16 px\n\n"
        text += "| Condition | Top-10 | Truth still feasible | Leakage when defined |\n| --- | --- | --- | --- |\n"
        for condition in ["matched_template_known", "renderer_mismatch", "font_mismatch", "font_unknown", "start_unknown"]:
            current = _lookup(summary, size_px=16, condition=condition, category="all", policy="exact")
            if current is None:
                continue
            text += f"| {condition} | {_interval(current, 'geo_top10')} | {_fmt(current['truth_in_set_rate'])} | {_interval(current, 'bits')} |\n"
        if not contrasts.empty:
            text += "\n### Paired differences, matched 16 px\n\n"
            text += "A positive leakage difference means the first policy leaks more. A positive area difference means it covers more area.\n\n"
            text += "| Contrast | Leakage bits | Top-10 | Area ratio | Neighbor ink |\n| --- | --- | --- | --- | --- |\n"
            for left, right in [("exact", "square64"), ("exact", "start128"), ("exact", "field"), ("exact", "width64")]:
                cells = []
                for metric in ("entropy_reduction", "geo_hit10", "area_ratio", "fraction_ink_obscured"):
                    part = contrasts[(contrasts.left == left) & (contrasts.right == right) & (contrasts.metric == metric)]
                    if part.empty:
                        cells.append("—")
                    else:
                        item = part.iloc[0]
                        cells.append(f"{_fmt(item['difference'])} ({_fmt(item['lo'])}, {_fmt(item['hi'])})")
                text += f"| {POLICY_LABEL[left]} − {POLICY_LABEL[right]} | " + " | ".join(cells) + " |\n"
    text += "\n## Assessment\n\n"
    if stage == "pilot":
        text += "The pilot checks coverage, grid alignment, field-box identity, track labels, and the OCR coordinate transform. It is not the validation claim.\n\n"
    for line in judgment(summary, contrasts, diagnostics, analytic):
        text += line + "\n\n"
    text += f"""## Quality checks

- OCR coordinate check passed: {config.get("ocr_coordinate_check")}
- Verifier true-accept rate: {_fmt(diagnostics.get("true_accept_rate"), 4)}
- Verifier false-accept rate: {_fmt(diagnostics.get("false_accept_rate"), 4)}
- Coverage failures: {len(diagnostics.get("coverage_failures") or [])}
- Quality-check problems: {diagnostics.get("qa_problems")}
- Mean surname redraws before a name fit on the page: {_fmt(diagnostics.get("name_rejection_mean"), 3)}

## Limitations

The matched leakage of an exact box is mostly a property of the font and the candidate list. Real pages change it when a mask is clipped by the page or when the sampled names are those that fit. The layout-free reference is in `analytic_reference.json`. What the real page adds, and what the synthetic pages did not measure in this form, is the neighboring ink and the layout regions a large mask covers.

Start-aligned and field results apply only where a redactor knows the shared start and, for the field, the closed list. This experiment supplies both by construction. It does not show that a DocLayNet page reveals them.

PyMuPDF versus Pillow is one renderer mismatch. It is not the manuscript's Linux FreeType environment. Font-unknown search is limited to the six installed fonts and five sizes.

Original-text verification can fail closed. A line the font bank cannot redraw is excluded. A negative control that accepts the wrong string withdraws the original-text privacy rows. Neither case is filled with an imputed accuracy.

OCR neighbor counts depend on the macOS Vision framework and on splitting a line box by character count. They are estimates. The ink fraction does not use OCR.
"""
    (out / "validation_report.md").write_text(text)


def write_readme(out, config, diagnostics, stage):
    command = "python3 research/doclaynet_validation/run_experiment.py --stage " + stage
    text = f"""# Reproducing the DocLayNet validation

From the repository root:

```sh
python3 -m pytest -q research/doclaynet_validation/test_validation.py
python3 research/doclaynet_validation/run_experiment.py --stage pilot
python3 research/doclaynet_validation/run_experiment.py --stage full
```

The full stage stops unless `results/pilot/PILOT_OK` exists. Outputs are written under `research/doclaynet_validation/results/` and do not modify the manuscript, the archived experiments, or `dataset/DocLayNet_core`.

This run used stage `{stage}`.

- Python: `{config["versions"]["python"].split()[0]}`
- NumPy {config["versions"]["numpy"]}, pandas {config["versions"]["pandas"]}, Pillow {config["versions"]["pillow"]}, matplotlib {config["versions"]["matplotlib"]}
- PyMuPDF: {config["versions"].get("pymupdf")}
- Platform: {config["versions"]["platform"]}
- Seed {config["seed"]}, bootstrap draws {config["bootstrap_draws"]}
- Pages opened: {diagnostics.get("pages_selected")} selected; see `dataset_manifest.csv` for exclusions
- Result rows: {diagnostics.get("result_rows")}
- Seconds: {diagnostics.get("seconds")}

COCO SHA-256 values and font hashes are in `experiment_config.json`. The protocol is `research/doclaynet_validation/PROTOCOL.md`.

`results.csv` is one row per target, policy, and attacker condition. `summary.csv` pools evaluation targets by document. `analytic_reference.json` is the same attack with the pen away from any page edge.
"""
    (out / "README.md").write_text(text)


def write_all(out, frame, manifest, diagnostics, analytic, config, examples, stage):
    summary, contrasts = summarize(frame)
    summary.to_csv(out / "summary.csv", index=False)
    contrasts.to_csv(out / "contrasts.csv", index=False)
    write_figures(out, summary, stage)
    save_examples(out, examples)
    write_report(out, summary, contrasts, manifest, diagnostics, analytic, config, stage)
    write_readme(out, config, diagnostics, stage)
    digest = hashlib.sha256((out / "results.csv").read_bytes()).hexdigest() if (out / "results.csv").exists() else ""
    (out / "checksums.sha256").write_text(
        f"{digest}  results.csv\n{hashlib.sha256((out / 'summary.csv').read_bytes()).hexdigest()}  summary.csv\n"
    )
