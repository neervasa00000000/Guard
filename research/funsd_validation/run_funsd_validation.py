"""Run the FUNSD validation and write tables. Does not touch the manuscript."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from funsd_real import (
    BOOTSTRAP_DRAWS,
    BOOTSTRAP_SEED,
    DATASET,
    MISMATCH_FONTS,
    OUT,
    REPO,
    calibrate_font,
    cluster_bootstrap,
    coverage_table,
    fit_length_model,
    half_open_width_from_stored,
    load_pages,
    no_box_scores,
    policy_table,
    rendered_width,
    score_observations,
    spearman,
    training_candidates,
    write_frame,
)


def rng_for(key):
    import hashlib
    digest = hashlib.sha256(f"{BOOTSTRAP_SEED}:{key}".encode()).hexdigest()
    return np.random.default_rng(int(digest[:8], 16))


def _mean(values):
    return float(np.mean(values))


def _median(values):
    return float(np.median(values))


def ci_mean(doc_ids, values, key):
    usable = np.isfinite(np.asarray(values, dtype=np.float64))
    if usable.sum() == 0:
        return float("nan"), float("nan"), float("nan")
    point = float(np.mean(np.asarray(values, dtype=np.float64)[usable]))
    low, high = cluster_bootstrap(
        np.asarray(doc_ids)[usable],
        np.asarray(values, dtype=np.float64)[usable],
        _mean,
        rng_for(key),
        BOOTSTRAP_DRAWS,
    )
    return point, low, high


def ci_median(doc_ids, values, key):
    point = float(np.median(values))
    low, high = cluster_bootstrap(doc_ids, values, _median, rng_for(key), BOOTSTRAP_DRAWS)
    return point, low, high


def attach_identity(frame, regime, policy, knowledge):
    frame = frame.copy()
    frame.insert(0, "regime", regime)
    frame.insert(1, "policy", policy)
    frame.insert(2, "knowledge", knowledge)
    return frame


def summarize_scores(frame, area_doc, area_values, regime, policy, knowledge, status, note):
    row = {
        "regime": regime,
        "policy": policy,
        "knowledge": knowledge,
        "status": status,
        "note": note,
        "n_fields": int(len(frame)),
        "n_docs": int(pd.Series(frame["doc_id"]).nunique()) if len(frame) else 0,
        "n_in_list": int(frame["in_list"].sum()) if len(frame) else 0,
    }
    if status != "measured" or len(frame) == 0:
        return row
    for name, column in (("top1", "hit1"), ("top10", "hit10"), ("entropy_reduction", "entropy_reduction_bits")):
        point, low, high = ci_mean(frame["doc_id"], frame[column], f"{regime}|{policy}|{name}")
        row[name] = point
        row[f"{name}_ci_low"] = low
        row[f"{name}_ci_high"] = high
    listed = frame[frame["in_list"]]
    row["top1_conditional"] = float(listed["hit1"].mean()) if len(listed) else float("nan")
    row["top10_conditional"] = float(listed["hit10"].mean()) if len(listed) else float("nan")
    if len(listed):
        point, low, high = ci_mean(
            listed["doc_id"], listed["hit1"], f"{regime}|{policy}|top1_conditional"
        )
        row["top1_conditional_ci_low"] = low
        row["top1_conditional_ci_high"] = high
        point, low, high = ci_mean(
            listed["doc_id"], listed["truth_info_gain_bits"], f"{regime}|{policy}|truth_ig"
        )
        row["truth_info_gain"] = point
        row["truth_info_gain_ci_low"] = low
        row["truth_info_gain_ci_high"] = high
        row["n_truth_info_gain"] = int(np.isfinite(listed["truth_info_gain_bits"]).sum())
        row["worst_truth_info_gain"] = float(np.nanmax(listed["truth_info_gain_bits"]))
        worst_ig_row = listed.loc[listed["truth_info_gain_bits"].idxmax()]
        row["worst_truth_ig_doc"] = worst_ig_row["doc_id"]
        row["worst_truth_ig_entity"] = int(worst_ig_row["entity_id"])
    else:
        row["truth_info_gain"] = float("nan")
        row["n_truth_info_gain"] = 0
    row["worst_top_posterior"] = float(frame["posterior_top"].max())
    worst_post = frame.loc[frame["posterior_top"].idxmax()]
    row["worst_top_posterior_doc"] = worst_post["doc_id"]
    row["worst_top_posterior_entity"] = int(worst_post["entity_id"])
    row["fraction_top_posterior_above_half"] = float((frame["posterior_top"] > 0.5).mean())
    if area_values is not None:
        point, low, high = ci_median(area_doc, area_values, f"{regime}|{policy}|area")
        row["median_area_ratio"] = point
        row["median_area_ratio_ci_low"] = low
        row["median_area_ratio_ci_high"] = high
        row["median_area_inflation"] = point - 1.0
        row["worst_area_ratio"] = float(np.max(area_values))
    return row


def load_synthetic_reference():
    rows = []
    table3 = REPO / "out" / "tables" / "table3.csv"
    if table3.is_file():
        frame = pd.read_csv(table3)
        keep = frame[frame["list"] == "surnames"]
        for record in keep.itertuples(index=False):
            rows.append({
                "dataset": "synthetic_manuscript_table3",
                "subset": "surnames",
                "policy": record.policy,
                "label": record.label,
                "n": int(record.n),
                "top10_percent": float(record.top10),
                "bits_layout": float(record.bits_layout),
                "median_area_ratio": float(record.area),
                "knowledge": "matched renderer, dictionary prior, synthetic template",
                "same_estimand_as_funsd": False,
            })
    knowledge_matched = REPO / "research" / "e1" / "data" / "knowledge_matched" / "summary.csv"
    if knowledge_matched.is_file():
        frame = pd.read_csv(knowledge_matched)
        wanted = frame[
            frame["policy"].isin(["square", "start-aligned", "field"])
            & frame["size_px"].isin([16, 24])
            & frame["width_px"].isin([0, 16, 64, 128])
        ]
        for record in wanted.itertuples(index=False):
            rows.append({
                "dataset": "synthetic_knowledge_matched",
                "subset": f"surnames_{int(record.size_px)}px",
                "policy": f"{record.policy}_{int(record.width_px)}",
                "label": "",
                "n": int(record.n),
                "top10_percent": float(record.top10_pct),
                "bits_layout": float(record.bits),
                "median_area_ratio": float(record.median_area),
                "knowledge": "matched renderer, 1000-surname prior, synthetic template",
                "same_estimand_as_funsd": False,
            })
    return pd.DataFrame(rows)


def spearman_ci(frame, x_column, key):
    documents = frame["doc_id"].to_numpy()
    unique = np.unique(documents)
    groups = {doc: frame[frame["doc_id"] == doc] for doc in unique}
    point = spearman(frame[x_column], frame["length"])
    stats = np.empty(BOOTSTRAP_DRAWS, dtype=np.float64)
    rng = rng_for(key)
    for draw in range(BOOTSTRAP_DRAWS):
        chosen = rng.choice(unique, size=len(unique), replace=True)
        sample = pd.concat([groups[doc] for doc in chosen], ignore_index=True)
        stats[draw] = spearman(sample[x_column], sample["length"])
    return {
        "n": int(len(frame)),
        "n_docs": int(len(unique)),
        "spearman": point,
        "ci_low": float(np.nanpercentile(stats, 2.5)),
        "ci_high": float(np.nanpercentile(stats, 97.5)),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    audit, fields = load_pages(DATASET)
    if audit["missing_images"] or audit["train_test_stem_overlap"]:
        raise SystemExit(f"Dataset audit failed: {audit}")
    if audit["n_documents"] != 199:
        raise SystemExit(f"Expected 199 FUNSD documents, found {audit['n_documents']}")
    write_frame(fields, OUT / "answer_entities.csv")
    eligible = fields[fields["eligible"]].copy()
    train = eligible[eligible["split"] == "training"].copy()
    test = eligible[eligible["split"] == "testing"].copy()
    if train.empty or test.empty:
        raise SystemExit("Eligibility left a split empty; refusing to invent scores.")
    exclusions = (
        fields.loc[~fields["eligible"], "exclusion"]
        .value_counts()
        .rename_axis("exclusion")
        .reset_index(name="n")
    )
    write_frame(exclusions, OUT / "exclusions.csv")
    policies = policy_table(fields)
    write_frame(policies, OUT / "policy_boxes.csv")
    print("checking redaction coverage", flush=True)
    coverage = coverage_table(fields, DATASET)
    write_frame(coverage, OUT / "coverage.csv")
    candidates = training_candidates(train)
    write_frame(candidates.drop(columns=[]), OUT / "training_candidates.csv")
    length_model = fit_length_model(train)
    observations = policies.loc[policies["split"] == "testing", [
        "split", "doc_id", "entity_id", "policy", "bin_lo", "bin_hi",
        "area", "exact_area", "area_ratio", "width", "height",
    ]].copy()
    write_frame(observations, OUT / "attacker_observations.csv")
    forbidden = {"text", "length", "prior"}
    if forbidden & set(observations.columns):
        raise SystemExit("Attacker observation table contains ground truth.")

    knowledge = (
        "extra knowledge: training-answer dictionary and a width model; "
        "not a matched renderer and not a naturally occurring redaction"
    )
    score_frames = []
    summary_rows = []
    skipped = []

    def add_skip(regime, policy, reason):
        skipped.append({"regime": regime, "policy": policy, "status": "not_measured", "reason": reason})
        summary_rows.append({
            "regime": regime,
            "policy": policy,
            "knowledge": "unavailable on FUNSD scans",
            "status": "not_measured",
            "note": reason,
            "n_fields": int(len(test)),
            "n_docs": int(test["doc_id"].nunique()),
            "n_in_list": 0,
        })

    add_skip(
        "realistic_image_only",
        "all",
        "No candidate distribution is supplied by the scan. Top-1, top-10, the no-box baseline, and bits are unidentified. Area ratios for the controlled rectangles are reported under the geometry rows.",
    )
    add_skip(
        "fixed_field",
        "field_box",
        "FUNSD annotates text rectangles, not the blank width of the form field. No field box was invented.",
    )
    add_skip(
        "matched_renderer",
        "all",
        "The original font, size, and renderer are not in the dataset, and the six study fonts are not installed here. A matched-renderer attack was not run.",
    )

    test_keys = test[["split", "doc_id", "entity_id", "text"]].copy()
    regimes = []
    if length_model["status"] == "ok":
        regimes.append({
            "name": "length_width",
            "texts": candidates["text"].tolist(),
            "prior": candidates["prior"].to_numpy(dtype=np.float64),
            "mean": length_model["intercept"] + length_model["slope"] * candidates["length"].to_numpy(dtype=np.float64),
            "sigma": length_model["sigma"],
        })
    else:
        add_skip("length_width", "all", length_model["status"])

    calibration_rows = []
    renderer_diagnostics = []
    for font_name, font_path in MISMATCH_FONTS.items():
        path = Path(font_path)
        if not path.is_file():
            add_skip(f"mismatch_{font_name}", "all", f"Font file missing: {font_path}")
            continue
        print(f"calibrating mismatched font {font_name}", flush=True)
        fitted = calibrate_font(train, str(path))
        for point in fitted["curve"]:
            calibration_rows.append({"font": font_name, **point})
        if fitted["status"] != "ok":
            add_skip(f"mismatch_{font_name}", "all", fitted["status"])
            continue
        usable_text = []
        usable_mean = []
        usable_count = []
        counts = dict(zip(candidates["text"], candidates["count"]))
        for text, count in counts.items():
            predicted = fitted["cache"].get(text)
            if predicted is None:
                continue
            usable_text.append(text)
            usable_mean.append(predicted)
            usable_count.append(count)
        counts_array = np.asarray(usable_count, dtype=np.float64)
        regimes.append({
            "name": f"mismatch_{font_name}",
            "texts": usable_text,
            "prior": counts_array / counts_array.sum(),
            "mean": np.asarray(usable_mean, dtype=np.float64),
            "sigma": fitted["sigma"],
            "font_size": fitted["size"],
            "train_mae": fitted["median_abs_error"],
        })
        from PIL import ImageFont
        font = ImageFont.truetype(str(path), int(fitted["size"]))
        predictions = []
        for text in test["text"]:
            try:
                predictions.append(rendered_width(font, text))
            except Exception:
                predictions.append(math.nan)
        predictions = np.asarray(predictions, dtype=np.float64)
        error = np.abs(predictions - test["width"].to_numpy(dtype=np.float64))
        renderer_diagnostics.append({
            "font": font_name,
            "size_selected_on_training": fitted["size"],
            "training_median_abs_error": fitted["median_abs_error"],
            "test_median_abs_error": float(np.nanmedian(error)),
            "test_fields_rendered": int(np.isfinite(predictions).sum()),
            "sigma": fitted["sigma"],
            "n_candidates": len(usable_text),
        })

    print(f"scoring {len(regimes)} regimes", flush=True)
    policy_names = list(observations["policy"].unique())
    for regime in regimes:
        log_prior = np.log(regime["prior"])
        no_box = no_box_scores(test_keys["text"].tolist(), regime["texts"], log_prior)
        no_box = pd.concat([test_keys.reset_index(drop=True), no_box], axis=1)
        no_box = attach_identity(no_box, regime["name"], "no_box", knowledge)
        score_frames.append(no_box)
        summary_rows.append(summarize_scores(
            no_box, None, None, regime["name"], "no_box", knowledge, "measured",
            "Attacker ignores rectangle geometry and ranks the training prior. This is not a redaction of area zero.",
        ))
        for policy_name in policy_names:
            observed = observations[observations["policy"] == policy_name]
            merged = test_keys.merge(
                observed, on=["split", "doc_id", "entity_id"], how="left", validate="one_to_one"
            )
            if merged[["bin_lo", "bin_hi"]].isna().any().any():
                raise SystemExit(f"Missing observation for {policy_name}")
            scored = score_observations(
                merged["bin_lo"], merged["bin_hi"], merged["text"].tolist(),
                regime["texts"], regime["mean"], regime["sigma"], log_prior,
            )
            scored = pd.concat(
                [merged[["split", "doc_id", "entity_id", "area_ratio"]].reset_index(drop=True), scored],
                axis=1,
            )
            scored = attach_identity(scored, regime["name"], policy_name, knowledge)
            score_frames.append(scored)
            summary_rows.append(summarize_scores(
                scored, scored["doc_id"], scored["area_ratio"].to_numpy(),
                regime["name"], policy_name, knowledge, "measured",
                "Controlled rectangle on the FUNSD annotation. Recovery uses the extra-knowledge model named in the regime.",
            ))
            print(f"  {regime['name']} {policy_name} top1={scored['hit1'].mean():.4f}", flush=True)

    scores = pd.concat(score_frames, ignore_index=True)
    write_frame(scores, OUT / "scores.csv")
    summary = pd.DataFrame(summary_rows)
    # Pair each measured rectangle with the no-box baseline from the same regime.
    baseline = summary[summary["policy"] == "no_box"][
        ["regime", "top1", "top1_ci_low", "top1_ci_high", "top10", "top10_ci_low", "top10_ci_high"]
    ].rename(columns={
        "top1": "nobox_top1",
        "top1_ci_low": "nobox_top1_ci_low",
        "top1_ci_high": "nobox_top1_ci_high",
        "top10": "nobox_top10",
        "top10_ci_low": "nobox_top10_ci_low",
        "top10_ci_high": "nobox_top10_ci_high",
    })
    summary = summary.merge(baseline, on="regime", how="left")
    write_frame(summary, OUT / "summary.csv")
    write_frame(pd.DataFrame(skipped), OUT / "not_measured.csv")
    write_frame(pd.DataFrame(calibration_rows), OUT / "renderer_calibration.csv")
    write_frame(pd.DataFrame(renderer_diagnostics), OUT / "renderer_test_error.csv")
    write_frame(load_synthetic_reference(), OUT / "synthetic_reference.csv")

    fields = fields.copy()
    fields["width_half_open_reading"] = half_open_width_from_stored(fields)
    association_rows = []
    for split_name, frame in (
        ("training", train),
        ("testing", test),
        ("all_eligible", eligible),
    ):
        frame = frame.copy()
        frame["width_half_open_reading"] = half_open_width_from_stored(frame)
        for column, label in (("width", "inclusive"), ("width_half_open_reading", "half_open_reading")):
            estimated = spearman_ci(frame, column, f"spearman|{split_name}|{label}")
            association_rows.append({
                "split": split_name,
                "width_definition": label,
                "estimand": "descriptive rank correlation, not attack leakage",
                **estimated,
            })
    write_frame(pd.DataFrame(association_rows), OUT / "width_length_association.csv")

    manifest = {
        "dataset": "FUNSD",
        "n_documents": audit["n_documents"],
        "n_training_documents": audit["n_training_documents"],
        "n_testing_documents": audit["n_testing_documents"],
        "label_counts": audit["label_counts"],
        "image_modes": audit["image_modes"],
        "n_answer_entities": audit["n_answer_entities"],
        "n_eligible": int(len(eligible)),
        "n_eligible_training": int(len(train)),
        "n_eligible_testing": int(len(test)),
        "n_eligible_training_documents": int(train["doc_id"].nunique()),
        "n_eligible_testing_documents": int(test["doc_id"].nunique()),
        "n_training_candidates": int(len(candidates)),
        "test_fields_in_training_dictionary": int(test["text"].isin(set(candidates["text"])).sum()),
        "side_spill_eligible": int(eligible["side_spill"].sum()),
        "side_spill_rate_eligible": float(eligible["side_spill"].mean()),
        "length_model": {key: length_model[key] for key in ("status", "intercept", "slope", "sigma", "n", "residual_mae")},
        "renderer_diagnostics": renderer_diagnostics,
        "bootstrap_draws": BOOTSTRAP_DRAWS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "coverage_all_covered": bool(coverage["covered"].all()) if len(coverage) else False,
        "protocol": "research/funsd_validation/PROTOCOL.md",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (OUT / "dataset_audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps({key: manifest[key] for key in (
        "n_documents", "n_eligible", "n_eligible_training", "n_eligible_testing",
        "test_fields_in_training_dictionary", "coverage_all_covered", "length_model",
    )}, indent=2))
    return manifest


if __name__ == "__main__":
    main()
