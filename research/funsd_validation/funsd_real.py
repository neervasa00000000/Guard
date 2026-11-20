"""FUNSD real-document validation for the GUARD geometry study.

The routines here implement research/funsd_validation/PROTOCOL.md.
They do not modify the synthetic archives or the manuscript.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageFont

REPO = Path(__file__).resolve().parents[2]
DATASET = REPO / "dataset"
OUT = Path(__file__).resolve().parent / "out"

INK_MAX = 140
MIN_INK_PIXELS = 8
MIN_INK_FRACTION = 0.02
MAX_CHARS = 80
SIDE_SPILL_PIXELS = 2
SIDE_SPILL_MIN = 6
GRIDS = (8, 16, 32, 64)
WIDTH_CLASSES = (32, 64, 128)
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_SEED = 20261116
SIGMA_FLOOR = 1e-3
FONT_SIZES = (8, 10, 12, 14, 16, 18, 20, 22, 24)
MISMATCH_FONTS = {
    "Arial": "/System/Library/Fonts/Supplemental/Arial.ttf",
    "TimesNewRoman": "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    "CourierNew": "/System/Library/Fonts/Supplemental/Courier New.ttf",
}

EXCLUSION_ORDER = (
    "empty_text",
    "text_word_mismatch",
    "missing_words",
    "box_outside_image",
    "vertical_entity",
    "vertical_word",
    "multiline",
    "too_long",
    "insufficient_ink",
)


def norm_text(value) -> str:
    return " ".join(str(value or "").split())


def inclusive_to_half_open(box):
    x0, y0, x1, y1 = (int(v) for v in box)
    return x0, y0, x1 + 1, y1 + 1


def half_open_size(box):
    x0, y0, x1, y1 = box
    return int(x1 - x0), int(y1 - y0)


def ceil_multiple(value, width):
    value = np.asarray(value)
    return -(-value // int(width)) * int(width)


def square_grid_box(half_open, grid):
    x0, y0, x1, y1 = half_open
    grid = int(grid)
    return (
        int((x0 // grid) * grid),
        int((y0 // grid) * grid),
        int(ceil_multiple(x1, grid)),
        int(ceil_multiple(y1, grid)),
    )


def width_grid_box(half_open, width):
    x0, y0, x1, y1 = half_open
    span = int(x1 - x0)
    snapped = int(ceil_multiple(span, int(width)))
    return x0, y0, x0 + snapped, y1


def feasible_widths(policy, half_open, parameter):
    """Integer inclusive widths of the exact box still compatible with the observation.

    Exact: the observed width itself.
    Square grid: widths that can outward-snap to the observed page-grid rectangle.
    Width grid and start-aligned: widths that round up to the observed class.
    The two anchored policies share this geometry; see the protocol.
    """
    width, _height = half_open_size(half_open)
    if policy == "exact":
        return width, width
    if policy == "square_grid":
        snapped = square_grid_box(half_open, parameter)
        observed = snapped[2] - snapped[0]
        grid = int(parameter)
        low = int(observed - 2 * grid + 2)
        return max(1, low), int(observed)
    if policy in ("width_grid", "start_aligned"):
        snapped = width_grid_box(half_open, parameter)
        observed = int(snapped[2] - snapped[0])
        return max(1, observed - int(parameter) + 1), observed
    raise KeyError(policy)


def policy_half_open(policy, half_open, parameter):
    if policy == "exact":
        return tuple(int(v) for v in half_open)
    if policy == "square_grid":
        return square_grid_box(half_open, parameter)
    if policy in ("width_grid", "start_aligned"):
        return width_grid_box(half_open, parameter)
    raise KeyError(policy)


def iter_policy_specs():
    yield "exact", "exact", 0
    for grid in GRIDS:
        yield f"square_grid_{grid}", "square_grid", grid
    for width in WIDTH_CLASSES:
        yield f"width_grid_{width}", "width_grid", width
        yield f"start_aligned_{width}", "start_aligned", width


def is_multiline(words) -> bool:
    boxes = [w["box"] for w in words]
    if len(boxes) <= 1:
        return False
    boxes = sorted(boxes, key=lambda box: (box[0], box[1]))
    for left, right in zip(boxes, boxes[1:]):
        overlap = min(left[3], right[3]) - max(left[1], right[1])
        shorter = min(left[3] - left[1], right[3] - right[1])
        if shorter <= 0 or overlap / shorter < 0.5:
            return True
    return False


def exclusion_reason(entity, image_size):
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
    if is_multiline(words):
        return "multiline"
    if len(text) > MAX_CHARS:
        return "too_long"
    return None


def ink_measurement(gray, inclusive_box):
    x0, y0, x1, y1 = (int(v) for v in inclusive_box)
    crop = gray[y0:y1 + 1, x0:x1 + 1]
    if crop.size == 0:
        return {"ink_pixels": 0, "ink_fraction": 0.0, "side_dark_pixels": 0, "side_spill": False}
    ink = int((crop < INK_MAX).sum())
    height, width = gray.shape
    band_top = y0 + max(1, (y1 - y0 + 1) // 4)
    band_bottom = y1 - max(0, (y1 - y0 + 1) // 4) + 1
    band_top = min(max(band_top, 0), height)
    band_bottom = min(max(band_bottom, band_top), height)
    left = gray[band_top:band_bottom, max(0, x0 - SIDE_SPILL_PIXELS):x0]
    right = gray[band_top:band_bottom, x1 + 1:min(width, x1 + 1 + SIDE_SPILL_PIXELS)]
    side = int((left < INK_MAX).sum()) if left.size else 0
    side += int((right < INK_MAX).sum()) if right.size else 0
    return {
        "ink_pixels": ink,
        "ink_fraction": float(ink / crop.size),
        "side_dark_pixels": side,
        "side_spill": bool(side >= SIDE_SPILL_MIN),
    }


def document_paths(root=DATASET):
    rows = []
    for split, folder in (("training", "training_data"), ("testing", "testing_data")):
        annotations = root / folder / "annotations"
        images = root / folder / "images"
        for path in sorted(annotations.glob("*.json")):
            rows.append({
                "split": split,
                "doc_id": path.stem,
                "annotation": path,
                "image": images / f"{path.stem}.png",
            })
    return rows


def load_pages(root=DATASET):
    """Return audit counts and one record per answer entity."""
    pages = document_paths(root)
    label_counts = {}
    answers = []
    image_modes = {}
    missing_images = []
    for page in pages:
        if not page["image"].is_file():
            missing_images.append(page["doc_id"])
            continue
        with Image.open(page["image"]) as image:
            image_modes[image.mode] = image_modes.get(image.mode, 0) + 1
            gray = np.asarray(image.convert("L"))
        width, height = int(gray.shape[1]), int(gray.shape[0])
        payload = json.loads(page["annotation"].read_text())
        for entity in payload["form"]:
            label = entity.get("label") or ""
            label_counts[label] = label_counts.get(label, 0) + 1
            if label != "answer":
                continue
            reason = exclusion_reason(entity, (width, height))
            ink = ink_measurement(gray, entity["box"])
            if reason is None and (
                ink["ink_pixels"] < MIN_INK_PIXELS or ink["ink_fraction"] < MIN_INK_FRACTION
            ):
                reason = "insufficient_ink"
            half = inclusive_to_half_open(entity["box"])
            box_w, box_h = half_open_size(half)
            text = norm_text(entity.get("text"))
            answers.append({
                "split": page["split"],
                "doc_id": page["doc_id"],
                "entity_id": int(entity["id"]),
                "text": text,
                "length": len(text),
                "x0": int(entity["box"][0]),
                "y0": int(entity["box"][1]),
                "x1": int(entity["box"][2]),
                "y1": int(entity["box"][3]),
                "width": box_w,
                "height": box_h,
                "area": int(box_w * box_h),
                "ink_pixels": ink["ink_pixels"],
                "ink_fraction": ink["ink_fraction"],
                "side_dark_pixels": ink["side_dark_pixels"],
                "side_spill": bool(ink["side_spill"]),
                "eligible": reason is None,
                "exclusion": reason or "",
                "image_width": width,
                "image_height": height,
            })
    stems = {}
    for page in pages:
        stems.setdefault(page["split"], []).append(page["doc_id"])
    overlap = sorted(set(stems.get("training", [])) & set(stems.get("testing", [])))
    audit = {
        "n_documents": len(pages),
        "n_training_documents": sum(page["split"] == "training" for page in pages),
        "n_testing_documents": sum(page["split"] == "testing" for page in pages),
        "missing_images": missing_images,
        "train_test_stem_overlap": overlap,
        "image_modes": image_modes,
        "label_counts": label_counts,
        "n_answer_entities": len(answers),
    }
    return audit, pd.DataFrame(answers)


def paint_check(gray, exact, policy):
    """Paint `policy` black on a local window and test the exact annotation.

    A pass means three things at once: the policy rectangle contains the exact
    rectangle, every dark pixel in the exact rectangle becomes black, and
    pixels in the window outside the policy rectangle stay as they were.
    """
    height, width = gray.shape
    exact = tuple(int(v) for v in exact)
    policy = tuple(int(v) for v in policy)
    contains = (
        policy[0] <= exact[0]
        and policy[1] <= exact[1]
        and policy[2] >= exact[2]
        and policy[3] >= exact[3]
    )
    wx0 = max(0, min(policy[0], exact[0]) - 1)
    wy0 = max(0, min(policy[1], exact[1]) - 1)
    wx1 = min(width, max(policy[2], exact[2]) + 1)
    wy1 = min(height, max(policy[3], exact[3]) + 1)
    if wx1 <= wx0 or wy1 <= wy0:
        return {
            "contains_exact": bool(contains),
            "ink_covered": False,
            "outside_unchanged": False,
            "covered": False,
        }
    before = gray[wy0:wy1, wx0:wx1].copy()
    window = before.copy()
    px0 = max(0, policy[0]) - wx0
    py0 = max(0, policy[1]) - wy0
    px1 = min(width, policy[2]) - wx0
    py1 = min(height, policy[3]) - wy0
    window[py0:py1, px0:px1] = 0
    ex0 = max(0, exact[0]) - wx0
    ey0 = max(0, exact[1]) - wy0
    ex1 = min(width, exact[2]) - wx0
    ey1 = min(height, exact[3]) - wy0
    ink = before[ey0:ey1, ex0:ex1] < INK_MAX
    ink_covered = bool(ink.any() and np.all(window[ey0:ey1, ex0:ex1][ink] == 0))
    outside = np.ones(window.shape, dtype=bool)
    outside[py0:py1, px0:px1] = False
    unchanged = bool(np.array_equal(window[outside], before[outside])) if np.any(outside) else True
    return {
        "contains_exact": bool(contains),
        "ink_covered": ink_covered,
        "outside_unchanged": unchanged,
        "covered": bool(contains and ink_covered and unchanged),
    }


def coverage_table(fields, root=DATASET):
    eligible = fields[fields["eligible"]].copy()
    grouped = {doc_id: frame for doc_id, frame in eligible.groupby("doc_id", sort=False)}
    rows = []
    for page in document_paths(root):
        frame = grouped.get(page["doc_id"])
        if frame is None:
            continue
        with Image.open(page["image"]) as image:
            gray = np.asarray(image.convert("L"))
        for record in frame.itertuples(index=False):
            half = inclusive_to_half_open((record.x0, record.y0, record.x1, record.y1))
            for name, policy, parameter in iter_policy_specs():
                box = policy_half_open(policy, half, parameter)
                check = paint_check(gray, half, box)
                rows.append({
                    "split": record.split,
                    "doc_id": record.doc_id,
                    "entity_id": int(record.entity_id),
                    "policy": name,
                    "contains_exact": check["contains_exact"],
                    "ink_covered": check["ink_covered"],
                    "outside_unchanged": check["outside_unchanged"],
                    "covered": check["covered"],
                })
    return pd.DataFrame(rows)


def policy_table(fields):
    rows = []
    for record in fields[fields["eligible"]].itertuples(index=False):
        half = inclusive_to_half_open((record.x0, record.y0, record.x1, record.y1))
        exact_area = int(record.area)
        for name, policy, parameter in iter_policy_specs():
            box = policy_half_open(policy, half, parameter)
            low, high = feasible_widths(policy, half, parameter)
            box_w, box_h = half_open_size(box)
            area = int(box_w * box_h)
            rows.append({
                "split": record.split,
                "doc_id": record.doc_id,
                "entity_id": int(record.entity_id),
                "policy": name,
                "x0": box[0],
                "y0": box[1],
                "x1": box[2],
                "y1": box[3],
                "width": box_w,
                "height": box_h,
                "area": area,
                "exact_area": exact_area,
                "area_ratio": float(area / exact_area),
                "bin_lo": int(low),
                "bin_hi": int(high),
            })
    return pd.DataFrame(rows)


def erf_vec(values):
    values = np.asarray(values, dtype=np.float64)
    sign = np.sign(values)
    magnitude = np.abs(values)
    t = 1.0 / (1.0 + 0.3275911 * magnitude)
    polynomial = t * (
        0.254829592
        + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429)))
    )
    return sign * (1.0 - polynomial * np.exp(-magnitude * magnitude))


def erfc_vec(values):
    values = np.asarray(values, dtype=np.float64)
    magnitude = np.abs(values)
    t = 1.0 / (1.0 + 0.3275911 * magnitude)
    polynomial = t * (
        0.254829592
        + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429)))
    )
    tail = polynomial * np.exp(-magnitude * magnitude)
    return np.where(values >= 0.0, tail, 2.0 - tail)


def log_normal_bin(low, high, mean, sigma):
    """Log probability of the normal interval (low, high], broadcast over means."""
    sigma = float(sigma)
    z_low = (np.asarray(low, dtype=np.float64) - mean) / sigma
    z_high = (np.asarray(high, dtype=np.float64) - mean) / sigma
    scale = math.sqrt(2.0)
    upper = z_low > 0
    lower = z_high < 0
    middle = ~upper & ~lower
    probability = np.empty(np.broadcast(z_low, z_high).shape, dtype=np.float64)
    probability[upper] = 0.5 * (
        erfc_vec(z_low[upper] / scale) - erfc_vec(z_high[upper] / scale)
    )
    probability[lower] = 0.5 * (
        erfc_vec(-z_high[lower] / scale) - erfc_vec(-z_low[lower] / scale)
    )
    probability[middle] = 0.5 * (
        erf_vec(z_high[middle] / scale) - erf_vec(z_low[middle] / scale)
    )
    probability = np.maximum(probability, 0.0)
    return np.log(np.maximum(probability, 1e-300))


def logsumexp(values):
    peak = np.max(values)
    return peak + np.log(np.sum(np.exp(values - peak)))


def shannon_bits(log_probabilities):
    """Shannon entropy from natural-log probabilities. Zeros do not contribute."""
    usable = log_probabilities > -700
    if not np.any(usable):
        return 0.0
    mass = np.exp(log_probabilities[usable])
    return float(-(mass * log_probabilities[usable]).sum() / math.log(2.0))


def expected_hit(log_scores, index, k):
    if index < 0:
        return 0.0
    truth = log_scores[index]
    greater = int(np.count_nonzero(log_scores > truth + 1e-8))
    equal = int(np.count_nonzero(np.abs(log_scores - truth) <= 1e-8))
    if equal == 0:
        return 0.0
    return float(min(1.0, max(0.0, (k - greater) / equal)))


def posterior_log(log_likelihood, log_prior):
    log_scores = np.asarray(log_likelihood, dtype=np.float64) + np.asarray(log_prior, dtype=np.float64)
    return log_scores - logsumexp(log_scores)


def fit_length_model(train_fields):
    length = train_fields["length"].to_numpy(dtype=np.float64)
    width = train_fields["width"].to_numpy(dtype=np.float64)
    design = np.column_stack([np.ones(len(length)), length])
    coefficient, _, _, _ = np.linalg.lstsq(design, width, rcond=None)
    intercept, slope = (float(v) for v in coefficient)
    residual = width - (intercept + slope * length)
    degrees = max(1, len(length) - 2)
    sigma = float(np.sqrt(np.sum(residual ** 2) / degrees))
    status = "ok"
    if slope <= 0 or sigma < SIGMA_FLOOR or not math.isfinite(sigma):
        status = "failed_degenerate_fit"
    return {
        "status": status,
        "intercept": intercept,
        "slope": slope,
        "sigma": sigma,
        "n": int(len(length)),
        "residual_mae": float(np.median(np.abs(residual))),
    }


def training_candidates(train_fields):
    counts = train_fields["text"].value_counts()
    frame = pd.DataFrame({
        "text": counts.index.astype(str),
        "count": counts.to_numpy(dtype=np.int64),
        "length": [len(text) for text in counts.index.astype(str)],
    })
    frame["prior"] = frame["count"] / frame["count"].sum()
    frame["source_split"] = "training"
    return frame.reset_index(drop=True)


def score_observations(bin_lo, bin_hi, truth, candidate_text, mean, sigma, log_prior):
    """Score fields. `truth` is used only to read out the true candidate after the posterior exists."""
    bin_lo = np.asarray(bin_lo, dtype=np.float64)
    bin_hi = np.asarray(bin_hi, dtype=np.float64)
    mean = np.asarray(mean, dtype=np.float64)
    log_prior = np.asarray(log_prior, dtype=np.float64)
    index_of = {text: i for i, text in enumerate(candidate_text)}
    prior_entropy = shannon_bits(log_prior)
    rows = []
    for i, (low, high, true_text) in enumerate(zip(bin_lo, bin_hi, truth)):
        log_likelihood = log_normal_bin(
            np.array([low - 0.5]),
            np.array([high + 0.5]),
            mean,
            sigma,
        )
        log_posterior = posterior_log(log_likelihood, log_prior)
        posterior_entropy = shannon_bits(log_posterior)
        top = int(np.argmax(log_posterior))
        truth_index = index_of.get(true_text, -1)
        info_gain = math.nan
        posterior_truth = math.nan
        if truth_index >= 0:
            posterior_truth = float(math.exp(log_posterior[truth_index]))
            info_gain = float((log_posterior[truth_index] - log_prior[truth_index]) / math.log(2.0))
        rows.append({
            "in_list": truth_index >= 0,
            "hit1": expected_hit(log_posterior, truth_index, 1),
            "hit10": expected_hit(log_posterior, truth_index, 10),
            "entropy_reduction_bits": float(prior_entropy - posterior_entropy),
            "truth_info_gain_bits": info_gain,
            "posterior_truth": posterior_truth,
            "posterior_top": float(math.exp(log_posterior[top])),
            "top_is_truth": bool(truth_index == top or (
                truth_index >= 0 and abs(log_posterior[truth_index] - log_posterior[top]) <= 1e-8
            )),
        })
    return pd.DataFrame(rows)


def no_box_scores(truth, candidate_text, log_prior):
    index_of = {text: i for i, text in enumerate(candidate_text)}
    rows = []
    for true_text in truth:
        truth_index = index_of.get(true_text, -1)
        rows.append({
            "in_list": truth_index >= 0,
            "hit1": expected_hit(log_prior, truth_index, 1),
            "hit10": expected_hit(log_prior, truth_index, 10),
            "entropy_reduction_bits": 0.0,
            "truth_info_gain_bits": 0.0 if truth_index >= 0 else math.nan,
            "posterior_truth": float(math.exp(log_prior[truth_index])) if truth_index >= 0 else math.nan,
            "posterior_top": float(math.exp(np.max(log_prior))),
            "top_is_truth": bool(
                truth_index >= 0 and abs(log_prior[truth_index] - np.max(log_prior)) <= 1e-8
            ),
        })
    return pd.DataFrame(rows)


def rendered_width(font, text):
    left, _top, right, _bottom = font.getbbox(text)
    return int(right - left)


def calibrate_font(train_fields, font_path, sizes=FONT_SIZES):
    texts = train_fields["text"].tolist()
    widths = train_fields["width"].to_numpy(dtype=np.float64)
    unique = list(dict.fromkeys(texts))
    curve = []
    best = None
    for size in sizes:
        font = ImageFont.truetype(font_path, int(size))
        cache = {}
        failed = 0
        for text in unique:
            try:
                cache[text] = rendered_width(font, text)
            except Exception:
                failed += 1
                cache[text] = None
        predicted = np.array([cache[text] if cache[text] is not None else np.nan for text in texts], dtype=np.float64)
        error = np.abs(predicted - widths)
        mae = float(np.nanmedian(error))
        curve.append({"size": int(size), "median_abs_error": mae, "n_failed": failed})
        if math.isfinite(mae) and (best is None or mae < best["median_abs_error"] - 1e-12 or (
            abs(mae - best["median_abs_error"]) <= 1e-12 and size < best["size"]
        )):
            best = {"size": int(size), "median_abs_error": mae, "cache": cache, "n_failed": failed}
    if best is None:
        return {"status": "failed_no_size", "curve": curve}
    predicted = np.array([
        best["cache"].get(text) if best["cache"].get(text) is not None else np.nan
        for text in texts
    ], dtype=np.float64)
    residual = widths - predicted
    usable = np.isfinite(residual)
    degrees = max(1, int(usable.sum()) - 1)
    sigma = float(np.sqrt(np.sum(residual[usable] ** 2) / degrees))
    status = "ok" if sigma >= SIGMA_FLOOR and int(usable.sum()) > 10 else "failed_degenerate_fit"
    return {
        "status": status,
        "size": best["size"],
        "sigma": sigma,
        "median_abs_error": best["median_abs_error"],
        "n_failed": best["n_failed"],
        "cache": best["cache"],
        "curve": curve,
    }


def rankdata(values):
    values = np.asarray(values, dtype=np.float64)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=np.float64)
    sorted_values = values[order]
    start = 0
    while start < len(values):
        stop = start
        while stop + 1 < len(values) and sorted_values[stop + 1] == sorted_values[start]:
            stop += 1
        ranks[order[start:stop + 1]] = 0.5 * ((start + 1) + (stop + 1))
        start = stop + 1
    return ranks


def spearman(x, y):
    x = rankdata(x)
    y = rankdata(y)
    x = x - x.mean()
    y = y - y.mean()
    denominator = math.sqrt(float((x * x).sum() * (y * y).sum()))
    if denominator == 0.0:
        return float("nan")
    return float((x * y).sum() / denominator)


def cluster_bootstrap(doc_ids, values, statistic, rng, draws=BOOTSTRAP_DRAWS):
    doc_ids = np.asarray(doc_ids)
    values = np.asarray(values, dtype=np.float64)
    documents = np.unique(doc_ids)
    groups = [values[doc_ids == doc] for doc in documents]
    if len(documents) == 0:
        return float("nan"), float("nan")
    stats = np.empty(draws, dtype=np.float64)
    for draw in range(draws):
        chosen = rng.integers(0, len(documents), len(documents))
        sample = np.concatenate([groups[i] for i in chosen])
        stats[draw] = statistic(sample)
    return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))


def half_open_width_from_stored(frame):
    """Alternate reading: stored edges are already a half-open PIL box."""
    return frame["x1"].to_numpy(dtype=np.int64) - frame["x0"].to_numpy(dtype=np.int64)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


STRING_COLUMNS = {
    "text", "split", "doc_id", "exclusion", "policy", "regime", "knowledge",
    "status", "note", "width_definition", "estimand", "font", "label", "subset",
    "dataset", "source_split", "worst_truth_ig_doc", "worst_top_posterior_doc",
    "reason", "protocol", "image", "annotation",
}


def write_frame(frame, path):
    """Quote every non-numeric field so strings such as NA and 100 survive reload."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, float_format="%.10f", quoting=csv.QUOTE_NONNUMERIC)


def read_table(path):
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    for column in frame.columns:
        if column in STRING_COLUMNS:
            continue
        values = frame[column]
        tokens = set(values.unique())
        if tokens <= {"True", "False", ""}:
            frame[column] = values.map({"True": True, "False": False, "": False})
            continue
        if tokens <= {""}:
            continue
        numeric = pd.to_numeric(values.replace("", pd.NA), errors="coerce")
        if numeric.notna().sum() == (values != "").sum():
            frame[column] = numeric
    return frame


def interval_mean(values):
    values = np.asarray(values, dtype=np.float64)
    usable = values[np.isfinite(values)]
    if len(usable) == 0:
        return float("nan")
    return float(usable.mean())
