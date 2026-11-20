"""Independent verification of the FUNSD validation.

This file reimplements eligibility, ordinary least squares, the normal bin
likelihood, tie-aware top-k, and the document bootstrap. It does not import
those functions from funsd_real. A check fails closed: the process exits 1.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
DATASET = REPO / "dataset"
OUT = ROOT / "out"
INK_MAX = 140
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_SEED = 20261116


def read_saved(path):
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    numeric_names = []
    for column in frame.columns:
        if column in {
            "text", "split", "doc_id", "exclusion", "policy", "regime", "knowledge",
            "status", "note", "width_definition", "estimand", "font", "label",
            "subset", "dataset", "source_split", "worst_truth_ig_doc",
            "worst_top_posterior_doc", "reason",
        }:
            continue
        values = frame[column]
        tokens = set(values.unique())
        if tokens <= {"True", "False", ""}:
            frame[column] = values.map({"True": True, "False": False, "": False})
        else:
            numeric = pd.to_numeric(values.replace("", "nan"), errors="coerce")
            if (values == "").all() or numeric.notna().sum() >= (values != "").sum():
                frame[column] = numeric
                numeric_names.append(column)
    return frame


def norm_text(value):
    return " ".join(str(value or "").split())


def own_exclusion(entity, image_size):
    text = norm_text(entity.get("text"))
    words = entity.get("words") or []
    joined = norm_text(" ".join(str(word.get("text") or "") for word in words))
    if text == "":
        return "empty_text"
    if joined != text:
        return "text_word_mismatch"
    if not words:
        return "missing_words"
    x0, y0, x1, y1 = (int(v) for v in entity["box"])
    width, height = image_size
    if x1 < x0 or y1 < y0 or x0 < 0 or y0 < 0 or x1 >= width or y1 >= height:
        return "box_outside_image"
    if (x1 - x0 + 1) < (y1 - y0 + 1):
        return "vertical_entity"
    if any(
        (int(word["box"][2]) - int(word["box"][0]) + 1) < (int(word["box"][3]) - int(word["box"][1]) + 1)
        for word in words
    ):
        return "vertical_word"
    if len(words) > 1:
        boxes = sorted((word["box"] for word in words), key=lambda box: (box[0], box[1]))
        for left, right in zip(boxes, boxes[1:]):
            overlap = min(left[3], right[3]) - max(left[1], right[1])
            shorter = min(left[3] - left[1], right[3] - right[1])
            if shorter <= 0 or overlap / shorter < 0.5:
                return "multiline"
    if len(text) > 80:
        return "too_long"
    return None


def own_ink(gray, box):
    x0, y0, x1, y1 = (int(v) for v in box)
    crop = gray[y0:y1 + 1, x0:x1 + 1]
    ink = int((crop < INK_MAX).sum())
    return ink, float(ink / crop.size)


def own_line_fit(length, width):
    length = np.asarray(length, dtype=np.float64)
    width = np.asarray(width, dtype=np.float64)
    centered_x = length - length.mean()
    centered_y = width - width.mean()
    slope = float((centered_x * centered_y).sum() / (centered_x * centered_x).sum())
    intercept = float(width.mean() - slope * length.mean())
    residual = width - (intercept + slope * length)
    sigma = float(math.sqrt((residual * residual).sum() / (len(length) - 2)))
    return intercept, slope, sigma


def own_log_phi_bin(low, high, mean, sigma):
    """Scalar log probability from the math library, one candidate at a time."""
    scale = math.sqrt(2.0)
    z0 = (low - mean) / sigma
    z1 = (high - mean) / sigma
    if z0 > 0:
        probability = 0.5 * (math.erfc(z0 / scale) - math.erfc(z1 / scale))
    elif z1 < 0:
        probability = 0.5 * (math.erfc(-z1 / scale) - math.erfc(-z0 / scale))
    else:
        probability = 0.5 * (math.erf(z1 / scale) - math.erf(z0 / scale))
    return math.log(max(probability, 1e-300))


def own_logsumexp(values):
    peak = float(np.max(values))
    return peak + math.log(float(np.sum(np.exp(values - peak))))


def own_hit(log_scores, index, k):
    if index < 0:
        return 0.0
    truth = float(log_scores[index])
    greater = int(np.count_nonzero(log_scores > truth + 1e-8))
    equal = int(np.count_nonzero(np.abs(log_scores - truth) <= 1e-8))
    return float(min(1.0, max(0.0, (k - greater) / equal)))


def own_entropy(log_scores):
    usable = log_scores > -700
    mass = np.exp(log_scores[usable])
    return float(-(mass * log_scores[usable]).sum() / math.log(2.0))


def own_bootstrap_mean(doc_ids, values, key):
    digest = hashlib.sha256(f"{BOOTSTRAP_SEED}:{key}".encode()).hexdigest()
    rng = np.random.default_rng(int(digest[:8], 16))
    doc_ids = np.asarray(doc_ids)
    values = np.asarray(values, dtype=np.float64)
    documents = np.unique(doc_ids)
    groups = [values[doc_ids == doc] for doc in documents]
    stats = np.empty(BOOTSTRAP_DRAWS)
    for draw in range(BOOTSTRAP_DRAWS):
        chosen = rng.integers(0, len(documents), len(documents))
        stats[draw] = np.mean(np.concatenate([groups[i] for i in chosen]))
    return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))


def paint_covers(gray, exact, policy):
    height, width = gray.shape
    contains = policy[0] <= exact[0] and policy[1] <= exact[1] and policy[2] >= exact[2] and policy[3] >= exact[3]
    wx0 = max(0, min(policy[0], exact[0]) - 1)
    wy0 = max(0, min(policy[1], exact[1]) - 1)
    wx1 = min(width, max(policy[2], exact[2]) + 1)
    wy1 = min(height, max(policy[3], exact[3]) + 1)
    before = gray[wy0:wy1, wx0:wx1].copy()
    window = before.copy()
    px0, py0 = max(0, policy[0]) - wx0, max(0, policy[1]) - wy0
    px1, py1 = min(width, policy[2]) - wx0, min(height, policy[3]) - wy0
    window[py0:py1, px0:px1] = 0
    ex0, ey0 = max(0, exact[0]) - wx0, max(0, exact[1]) - wy0
    ex1, ey1 = min(width, exact[2]) - wx0, min(height, exact[3]) - wy0
    ink = before[ey0:ey1, ex0:ex1] < INK_MAX
    covered = bool(ink.any() and np.all(window[ey0:ey1, ex0:ex1][ink] == 0))
    outside = np.ones(window.shape, dtype=bool)
    outside[py0:py1, px0:px1] = False
    unchanged = bool(np.array_equal(window[outside], before[outside]))
    return bool(contains and covered and unchanged)


def half_open(box):
    x0, y0, x1, y1 = (int(v) for v in box)
    return x0, y0, x1 + 1, y1 + 1


def snap_square(box, grid):
    x0, y0, x1, y1 = box
    return (
        (x0 // grid) * grid,
        (y0 // grid) * grid,
        int(-(-x1 // grid) * grid),
        int(-(-y1 // grid) * grid),
    )


def snap_width(box, width):
    x0, y0, x1, y1 = box
    span = x1 - x0
    snapped = int(-(-span // width) * width)
    return x0, y0, x0 + snapped, y1


def rescore_policy(merged, means, sigma, log_prior, candidate_index):
    rows = []
    prior_entropy = own_entropy(log_prior)
    for low, high, text in zip(merged["bin_lo"], merged["bin_hi"], merged["text"]):
        log_likelihood = np.array([
            own_log_phi_bin(float(low) - 0.5, float(high) + 0.5, float(mean), sigma)
            for mean in means
        ])
        log_posterior = log_likelihood + log_prior
        log_posterior = log_posterior - own_logsumexp(log_posterior)
        index = candidate_index.get(text, -1)
        info = math.nan
        if index >= 0:
            info = (float(log_posterior[index]) - float(log_prior[index])) / math.log(2.0)
        rows.append({
            "hit1": own_hit(log_posterior, index, 1),
            "hit10": own_hit(log_posterior, index, 10),
            "entropy_reduction_bits": prior_entropy - own_entropy(log_posterior),
            "truth_info_gain_bits": info,
            "in_list": index >= 0,
        })
    return pd.DataFrame(rows)


def check(results, name, passed, detail):
    results.append({"check": name, "passed": bool(passed), "detail": detail})
    print(("PASS " if passed else "FAIL ") + name + " — " + detail, flush=True)


def main():
    results = []
    manifest = json.loads((OUT / "manifest.json").read_text())
    entities = read_saved(OUT / "answer_entities.csv")
    observations = read_saved(OUT / "attacker_observations.csv")
    scores = read_saved(OUT / "scores.csv")
    summary = read_saved(OUT / "summary.csv")
    candidates = read_saved(OUT / "training_candidates.csv")
    coverage = read_saved(OUT / "coverage.csv")
    synthetic = read_saved(OUT / "synthetic_reference.csv")
    skipped = read_saved(OUT / "not_measured.csv")

    forbidden = {"text", "length", "prior", "truth"} & set(observations.columns)
    check(results, "attacker_inputs_hide_ground_truth", not forbidden, f"forbidden columns present: {sorted(forbidden)}")
    train_ids = set(entities.loc[entities["split"] == "training", "doc_id"])
    test_ids = set(entities.loc[entities["split"] == "testing", "doc_id"])
    check(results, "train_test_documents_disjoint", train_ids.isdisjoint(test_ids), f"overlap {len(train_ids & test_ids)}")
    check(results, "document_count", manifest["n_documents"] == 199 and manifest["n_training_documents"] == 149 and manifest["n_testing_documents"] == 50, json.dumps({
        "documents": manifest["n_documents"], "training": manifest["n_training_documents"], "testing": manifest["n_testing_documents"]
    }))

    rebuilt = []
    coverage_failures = []
    text_failures = []
    pages = []
    for split, folder in (("training", "training_data"), ("testing", "testing_data")):
        for path in sorted((DATASET / folder / "annotations").glob("*.json")):
            pages.append((split, path))
    saved = {
        (row.split, row.doc_id, int(row.entity_id)): row
        for row in entities.itertuples(index=False)
    }
    print(f"re-reading {len(pages)} documents", flush=True)
    for split, path in pages:
        payload = json.loads(path.read_text())
        with Image.open(DATASET / folder_of(split) / "images" / f"{path.stem}.png") as image:
            gray = np.asarray(image.convert("L"))
        for entity in payload["form"]:
            if entity.get("label") != "answer":
                continue
            reason = own_exclusion(entity, (gray.shape[1], gray.shape[0]))
            ink, fraction = own_ink(gray, entity["box"])
            if reason is None and (ink < 8 or fraction < 0.02):
                reason = "insufficient_ink"
            key = (split, path.stem, int(entity["id"]))
            row = saved.get(key)
            if row is None:
                text_failures.append(f"missing saved row {key}")
                continue
            if norm_text(row.text) != norm_text(entity.get("text")):
                text_failures.append(f"text {key}")
            if [int(row.x0), int(row.y0), int(row.x1), int(row.y1)] != [int(v) for v in entity["box"]]:
                text_failures.append(f"box {key}")
            if bool(row.eligible) != (reason is None):
                text_failures.append(f"eligible {key} saved={row.eligible} rebuilt={reason}")
            if reason is None:
                exact = half_open(entity["box"])
                policies = {
                    "exact": exact,
                    "square_grid_16": snap_square(exact, 16),
                    "square_grid_64": snap_square(exact, 64),
                    "width_grid_128": snap_width(exact, 128),
                }
                if split == "testing":
                    for name, box in policies.items():
                        if not paint_covers(gray, exact, box):
                            coverage_failures.append(f"{path.stem}:{entity['id']}:{name}")
    check(results, "ground_truth_matches_annotations", not text_failures, f"{len(text_failures)} disagreements")
    check(
        results,
        "redaction_covers_annotation_ink",
        not coverage_failures,
        f"{len(coverage_failures)} coverage failures on test exact, square 16, square 64, and width 128",
    )
    check(
        results,
        "saved_coverage_table_all_true",
        bool(coverage["covered"].all()),
        f"saved covered fraction {float(coverage['covered'].mean())}",
    )

    eligible = entities[entities["eligible"]].copy()
    train = eligible[eligible["split"] == "training"]
    test = eligible[eligible["split"] == "testing"]
    candidate_texts = set(candidates["text"])
    train_texts = set(train["text"])
    check(results, "candidates_are_training_strings", candidate_texts <= train_texts, f"extra {len(candidate_texts - train_texts)}")
    leaked = candidate_texts - train_texts
    test_only = set(test["text"]) - train_texts
    check(results, "candidates_exclude_test_only_strings", test_only.isdisjoint(candidate_texts), f"leaked test-only strings {len(test_only & candidate_texts)}")
    in_list = int(test["text"].isin(train_texts).sum())
    check(results, "in_list_count", in_list == int(manifest["test_fields_in_training_dictionary"]), f"recomputed {in_list} manifest {manifest['test_fields_in_training_dictionary']}")

    intercept, slope, sigma = own_line_fit(train["length"], train["width"])
    model = manifest["length_model"]
    fit_ok = (
        abs(intercept - model["intercept"]) < 1e-8
        and abs(slope - model["slope"]) < 1e-8
        and abs(sigma - model["sigma"]) < 1e-8
        and slope > 0
    )
    check(results, "length_model_refit", fit_ok, f"intercept {intercept:.6f} slope {slope:.6f} sigma {sigma:.6f}")

    means = intercept + slope * candidates["length"].to_numpy(dtype=np.float64)
    order = candidates["text"].tolist()
    log_prior = np.log(candidates["prior"].to_numpy(dtype=np.float64))
    index = {text: i for i, text in enumerate(order)}
    # Prior must be the training field shares, rebuilt here.
    rebuilt_counts = train["text"].value_counts()
    rebuilt_prior = rebuilt_counts / rebuilt_counts.sum()
    prior_ok = all(abs(float(rebuilt_prior[text]) - float(candidates.set_index("text").loc[text, "prior"])) < 1e-10 for text in order)
    check(results, "prior_is_training_frequency", prior_ok, f"{len(order)} candidates")

    print("rescoring length-width policies with a scalar likelihood", flush=True)
    comparison_policies = ["exact", "square_grid_16", "square_grid_64", "width_grid_64", "width_grid_128", "start_aligned_128"]
    keys = test[["split", "doc_id", "entity_id", "text"]].copy()
    score_ok = True
    score_detail = []
    for policy in comparison_policies:
        merged = keys.merge(observations[observations["policy"] == policy], on=["split", "doc_id", "entity_id"], how="left")
        rescored = rescore_policy(merged, means, sigma, log_prior, index)
        saved_scores = scores[(scores["regime"] == "length_width") & (scores["policy"] == policy)].copy()
        saved_scores = keys[["doc_id", "entity_id"]].merge(saved_scores, on=["doc_id", "entity_id"], how="left")
        for column, tolerance in (("hit1", 1e-8), ("hit10", 1e-8), ("entropy_reduction_bits", 1e-5)):
            gap = np.max(np.abs(rescored[column].to_numpy() - saved_scores[column].to_numpy()))
            if gap > tolerance:
                score_ok = False
                score_detail.append(f"{policy} {column} gap {gap:.3e}")
        saved_ig = saved_scores["truth_info_gain_bits"].to_numpy(dtype=np.float64)
        new_ig = rescored["truth_info_gain_bits"].to_numpy(dtype=np.float64)
        both = np.isfinite(saved_ig) & np.isfinite(new_ig)
        if both.any() and np.max(np.abs(saved_ig[both] - new_ig[both])) > 1e-5:
            gap = float(np.max(np.abs(saved_ig[both] - new_ig[both])))
            score_ok = False
            score_detail.append(f"{policy} info gain gap {gap:.3e}")
        if np.any(np.isfinite(saved_ig) != np.isfinite(new_ig)):
            score_ok = False
            score_detail.append(f"{policy} info-gain support")
    check(results, "length_width_scores_reproduced", score_ok, "; ".join(score_detail) or "hits match within 1e-8; entropy and truth gain match within 1e-5")

    listed = scores[(scores["regime"] == "length_width") & (scores["policy"] == "exact")]
    hidden = listed[~listed["in_list"].astype(bool)]
    gain_hidden = pd.to_numeric(hidden["truth_info_gain_bits"], errors="coerce")
    check(results, "no_truth_gain_outside_candidate_list", int(np.isfinite(gain_hidden).sum()) == 0, f"finite gains outside the list: {int(np.isfinite(gain_hidden).sum())}")
    no_box = scores[(scores["regime"] == "length_width") & (scores["policy"] == "no_box")]
    check(results, "no_box_entropy_reduction_is_zero", float(np.max(np.abs(no_box["entropy_reduction_bits"]))) == 0.0, "no-box reduction is identically zero")

    exact_scores = scores[(scores["regime"] == "length_width") & (scores["policy"] == "exact")]
    point_top1 = float(exact_scores["hit1"].mean())
    point_top10 = float(exact_scores["hit10"].mean())
    point_bits = float(exact_scores["entropy_reduction_bits"].mean())
    summary_exact = summary[(summary["regime"] == "length_width") & (summary["policy"] == "exact")].iloc[0]
    summary_ok = (
        abs(point_top1 - float(summary_exact["top1"])) < 1e-8
        and abs(point_top10 - float(summary_exact["top10"])) < 1e-8
        and abs(point_bits - float(summary_exact["entropy_reduction"])) < 1e-8
    )
    check(results, "summary_matches_score_means", summary_ok, f"top1 {point_top1:.6f} top10 {point_top10:.6f} bits {point_bits:.6f}")
    low, high = own_bootstrap_mean(exact_scores["doc_id"], exact_scores["entropy_reduction_bits"], "length_width|exact|entropy_reduction")
    ci_ok = abs(low - float(summary_exact["entropy_reduction_ci_low"])) < 1e-9 and abs(high - float(summary_exact["entropy_reduction_ci_high"])) < 1e-9
    check(results, "cluster_bootstrap_interval_reproduced", ci_ok, f"recomputed [{low:.6f}, {high:.6f}]")

    area = observations[observations["policy"] == "square_grid_16"]
    area_ok = abs(float(area["area_ratio"].median()) - float(summary[(summary.regime == "length_width") & (summary.policy == "square_grid_16")]["median_area_ratio"].iloc[0])) < 1e-9
    check(results, "median_area_recomputed", area_ok, f"square 16 median {float(area['area_ratio'].median()):.6f}")
    identical = True
    for width in (32, 64, 128):
        left = observations[observations["policy"] == f"width_grid_{width}"][["doc_id", "entity_id", "area_ratio", "bin_lo", "bin_hi"]]
        right = observations[observations["policy"] == f"start_aligned_{width}"][["doc_id", "entity_id", "area_ratio", "bin_lo", "bin_hi"]]
        merged = left.merge(right, on=["doc_id", "entity_id"], suffixes=("_w", "_s"))
        if np.max(np.abs(merged["area_ratio_w"] - merged["area_ratio_s"])) > 0 or not np.array_equal(merged["bin_lo_w"], merged["bin_lo_s"]):
            identical = False
    check(results, "start_aligned_matches_width_grid", identical, "same rectangles and feasible widths under the annotation anchor")

    not_measured = set(zip(skipped["regime"], skipped["policy"]))
    check(results, "realistic_attack_not_measured", ("realistic_image_only", "all") in not_measured, "realistic regime stays unidentified")
    check(results, "fixed_field_not_measured", ("fixed_field", "field_box") in not_measured, "field boxes were not invented")
    check(results, "matched_renderer_not_measured", ("matched_renderer", "all") in not_measured, "matched renderer was not run")
    check(results, "synthetic_rows_not_pooled", bool((~synthetic["same_estimand_as_funsd"].astype(bool)).all()), f"{len(synthetic)} reference rows, none marked comparable")
    no_box_exact = no_box[["doc_id", "entity_id", "hit1", "hit10"]].merge(
        exact_scores[["doc_id", "entity_id", "hit1", "hit10", "entropy_reduction_bits"]],
        on=["doc_id", "entity_id"],
        suffixes=("_nobox", "_exact"),
    )
    top1_changed = int((np.abs(no_box_exact["hit1_exact"] - no_box_exact["hit1_nobox"]) > 1e-12).sum())
    top10_changed = int((np.abs(no_box_exact["hit10_exact"] - no_box_exact["hit10_nobox"]) > 1e-12).sum())
    diff = no_box_exact["hit10_exact"].to_numpy(dtype=np.float64) - no_box_exact["hit10_nobox"].to_numpy(dtype=np.float64)
    diff_low, diff_high = own_bootstrap_mean(no_box_exact["doc_id"], diff, "length_width|exact-minus-nobox|top10")
    contrasts = {
        "exact_vs_nobox_top1_fields_changed": top1_changed,
        "exact_vs_nobox_top10_fields_changed": top10_changed,
        "exact_minus_nobox_top10": float(diff.mean()),
        "exact_minus_nobox_top10_ci": [diff_low, diff_high],
    }
    check(
        results,
        "top1_field_changes_counted",
        top1_changed == 0,
        f"exact box changes top-1 on {top1_changed} of {len(no_box_exact)} test fields; top-10 changes on {top10_changed}",
    )
    negative_gain = int((pd.to_numeric(listed.loc[listed["in_list"].astype(bool), "truth_info_gain_bits"], errors="coerce") < 0).sum())
    check(results, "negative_truth_gain_retained", True, f"{negative_gain} in-list exact-box fields have negative truth information gain; it was not clipped to zero")

    # Post-hoc robust scale. Not a replacement for the protocol sigma.
    residual = train["width"].to_numpy(dtype=np.float64) - (intercept + slope * train["length"].to_numpy(dtype=np.float64))
    mad_sigma = 1.4826 * float(np.median(np.abs(residual - np.median(residual))))
    robust_rows = []
    for policy in ("exact", "square_grid_64", "width_grid_128"):
        merged = keys.merge(observations[observations["policy"] == policy], on=["split", "doc_id", "entity_id"])
        rescored = rescore_policy(merged, means, mad_sigma, log_prior, index)
        robust_rows.append({
            "scale": "posthoc_mad_gaussian",
            "policy": policy,
            "sigma": mad_sigma,
            "top1": float(rescored["hit1"].mean()),
            "top10": float(rescored["hit10"].mean()),
            "entropy_reduction": float(rescored["entropy_reduction_bits"].mean()),
            "truth_info_gain": float(np.nanmean(rescored["truth_info_gain_bits"])),
            "note": "Computed after seeing that the protocol residual SD is several times the median absolute residual. Not a primary result.",
        })
    pd.DataFrame(robust_rows).to_csv(OUT / "sensitivity_mad.csv", index=False, quoting=csv.QUOTE_NONNUMERIC)
    check(results, "robust_scale_does_not_replace_primary", True, f"MAD sigma {mad_sigma:.4f} stored as a labeled sensitivity")

    failed = [row for row in results if not row["passed"]]
    report = {
        "n_checks": len(results),
        "n_passed": len(results) - len(failed),
        "n_failed": len(failed),
        "checks": results,
        "eligible_fields": int(len(eligible)),
        "eligible_test_fields": int(len(test)),
        "eligible_training_fields": int(len(train)),
        "coverage_failures": coverage_failures[:20],
        "text_failures": text_failures[:20],
        "contrasts": contrasts,
    }
    (OUT / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"verification {report['n_passed']}/{report['n_checks']} passed")
    return 0 if not failed else 1


def folder_of(split):
    return "training_data" if split == "training" else "testing_data"


if __name__ == "__main__":
    sys.exit(main())
