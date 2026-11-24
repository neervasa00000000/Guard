"""DocLayNet validation runner.

The pilot and the full run share this file. Neither writes outside
`research/doclaynet_validation/` or modifies the DocLayNet files.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import unicodedata
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

import catalog
import geometry

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "dataset" / "DocLayNet_core"
CACHE = HERE / "cache"
PNG = DATA / "PNG"
SEED = 20261118
BOOTSTRAP_DRAWS = 10000
CATEGORIES = [
    "financial_reports",
    "manuals",
    "laws_and_regulations",
    "scientific_articles",
    "patents",
    "government_tenders",
]
EVAL_QUOTA = {
    "financial_reports": 84,
    "manuals": 84,
    "laws_and_regulations": 83,
    "scientific_articles": 83,
    "patents": 83,
    "government_tenders": 83,
}
CAL_QUOTA = {category: 20 for category in CATEGORIES}
PILOT_EVAL = {category: 2 for category in CATEGORIES}
PILOT_CAL = {category: 1 for category in CATEGORIES}
PRIMARY_SIZE = 16
SENSITIVITY_SIZE = 12
BANK_SIZES = (12, 14, 16, 18, 20)
MAX_PAGES_PER_DOC = 2
VERIFY_SIZES = BANK_SIZES

COCO_SHA256 = {
    "train.json": "d33686f14d929a97a6a8b01351d36e78929300a328292b728a5b3089b47c38ca",
    "val.json": "eacd2ba2a32e6c2ebe2dc5ea1545f405d8461c46bba53e0c35d9c54fba0bcef6",
    "test.json": "37ccce8c7951dcfd9c7c832bbff5aee71cb59c032ed7021e125e6188e6ac4fe1",
}


def font_paths():
    import matplotlib

    base = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    supplemental = Path("/System/Library/Fonts/Supplemental")
    return {
        "DejaVuSans": base / "DejaVuSans.ttf",
        "DejaVuSerif": base / "DejaVuSerif.ttf",
        "Arial": supplemental / "Arial.ttf",
        "Times": supplemental / "Times New Roman.ttf",
        "Georgia": supplemental / "Georgia.ttf",
        "Courier": supplemental / "Courier New.ttf",
    }


def keyed_rng(label):
    digest = hashlib.sha256(f"{SEED}:{label}".encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "little"))


def role_of(doc_name, salt):
    digest = hashlib.sha256(f"{salt}:{doc_name}".encode()).digest()
    return "calibration" if digest[0] < 51 else "evaluation"


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_surnames():
    path = ROOT / "research" / "e1" / "data" / "surnames_head1000.csv"
    rows = list(csv.DictReader(path.open()))
    names = [row["name"] for row in rows]
    counts = np.array([float(row["count"]) for row in rows], dtype=np.float64)
    prior = counts / counts.sum()
    return names, prior, sha256_file(path)


def normalize_token(text):
    text = unicodedata.normalize("NFKC", str(text)).strip().strip(".,;:()[]\"'")
    if not text or any(character.isspace() for character in text):
        return None
    letters = "".join(character for character in text if character.isalpha())
    if not (4 <= len(letters) <= 24):
        return None
    if len(letters) / len(text) < 0.9:
        return None
    if any(ord(character) > 127 for character in letters):
        return None
    return letters.upper()


def _threshold_ink(font, text):
    """Ink edges at the same luminance cutoff the verifier uses on the page."""
    left, top, right, bottom = font.getbbox(text, anchor="ls")
    pad = 4
    width = max(1, int(right - left + 2 * pad))
    height = max(1, int(bottom - top + 2 * pad))
    image = Image.new("RGB", (width, height), (255, 255, 255))
    origin_x = pad - int(left)
    origin_y = pad - int(top)
    ImageDraw.Draw(image).text((origin_x, origin_y), text, fill=(0, 0, 0), font=font, anchor="ls")
    dark = geometry.luminance(np.asarray(image)) < 180
    ys, xs = np.nonzero(dark)
    if len(xs) == 0:
        return None
    return (
        int(xs.min() - origin_x),
        int(ys.min() - origin_y),
        int(xs.max() + 1 - origin_x),
        int(ys.max() + 1 - origin_y),
    )


def verify_render(rgb, search_box, text, fonts, sizes=VERIFY_SIZES):
    """Accept a proposed string only when a bank font reproduces the ink."""
    dark = geometry.luminance(rgb) < 180
    x0, y0, x1, y1 = [int(v) for v in search_box]
    height, width = dark.shape
    x0, y0, x1, y1 = geometry.clip_box((x0, y0, x1, y1), width, height)
    view = np.zeros_like(dark)
    view[y0:y1, x0:x1] = True
    ys, xs = np.nonzero(dark & view)
    if len(xs) < 8:
        return False, {"reason": "no_ink", "best": None, "passes": [], "ambiguous": False}
    dx0, dy0, dx1, dy1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    page_ink = np.zeros_like(dark)
    page_ink[dy0:dy1, dx0:dx1] = dark[dy0:dy1, dx0:dx1]
    page_n = int(page_ink.sum())
    best = None
    passes = []
    for name, path in fonts.items():
        for size in sizes:
            font = ImageFont.truetype(str(path), int(size))
            ink_box = _threshold_ink(font, text)
            if ink_box is None:
                continue
            left, top, right, bottom = ink_box
            pen_x = dx0 - left
            baseline = dy0 - top
            canvas = Image.new("RGB", (rgb.shape[1], rgb.shape[0]), (255, 255, 255))
            ImageDraw.Draw(canvas).text((pen_x, baseline), text, fill=(0, 0, 0), font=font, anchor="ls")
            render = geometry.luminance(np.asarray(canvas)) < 180
            render_n = int(render.sum())
            if render_n == 0:
                continue
            hit = int((render & page_ink).sum())
            recall = hit / render_n
            precision = hit / max(1, page_n)
            width_err = abs((right - left) - (dx1 - dx0))
            record = {
                "font": name,
                "size": int(size),
                "recall": float(recall),
                "precision": float(precision),
                "width_err": int(width_err),
            }
            if best is None or recall > best["recall"]:
                best = record
            if recall >= 0.75 and precision >= 0.45 and width_err <= 3:
                passes.append(record)
    ambiguous = False
    if passes:
        passes.sort(key=lambda item: (-item["recall"], item["font"], item["size"]))
        if len(passes) > 1 and passes[0]["font"] != passes[1]["font"] and passes[0]["recall"] - passes[1]["recall"] < 0.02:
            ambiguous = True
    return bool(passes), {"reason": None if passes else "render_mismatch", "best": best, "passes": passes, "ambiguous": ambiguous}


def separation_problems(rows):
    problems = []
    for row in rows:
        track = row["track"]
        origin = row["text_origin"]
        if track == "verified_original" and origin != "verified_original":
            problems.append("verified original row is not marked as original text")
        if track == "controlled_insertion" and origin != "controlled_insertion":
            problems.append("insertion row is not marked as a controlled insertion")
        if origin == "controlled_insertion" and track != "controlled_insertion":
            problems.append("a controlled insertion is labeled as another track")
    return problems


def load_pages_and_boxes():
    pages = pd.read_json(CACHE / "pages.jsonl", lines=True)
    pages = pages.rename(columns={"id": "image_id"})
    boxes = pd.read_csv(
        CACHE / "boxes.tsv",
        sep="\t",
        header=None,
        names=["split", "image_id", "ann_id", "cat", "x", "y", "w", "h"],
        dtype={"split": str, "image_id": np.int64, "ann_id": np.int64, "cat": np.int16, "x": np.float32, "y": np.float32, "w": np.float32, "h": np.float32},
    )
    key = pages[["split", "image_id", "file_name"]].drop_duplicates()
    boxes = boxes.merge(key, on=["split", "image_id"], how="inner")
    duplicate_files = int(pages["file_name"].duplicated().sum())
    pages = pages.drop_duplicates("file_name").reset_index(drop=True)
    return pages, boxes, duplicate_files


def build_region_index(boxes):
    host = boxes[
        boxes["cat"].isin(geometry.HOST_CATS)
        & boxes["w"].between(140, 980)
        & boxes["h"].between(10, 220)
    ]
    eligible = set(host["file_name"].unique())
    grouped = {
        file_name: group[["ann_id", "cat", "x", "y", "w", "h"]].to_numpy()
        for file_name, group in boxes.groupby("file_name", sort=False)
    }
    return grouped, eligible


def regions_from_array(array):
    regions = []
    for ann_id, cat, x, y, width, height in array:
        regions.append({
            "id": int(ann_id),
            "cat": int(cat),
            "box": geometry.coco_box(float(x), float(y), float(width), float(height)),
        })
    return regions


def picture_overlap(box, regions):
    area = max(1, (box[2] - box[0]) * (box[3] - box[1]))
    worst = 0.0
    for region in regions:
        if region["cat"] != geometry.PICTURE or not geometry.intersects(box, region["box"]):
            continue
        ix0 = max(box[0], region["box"][0])
        iy0 = max(box[1], region["box"][1])
        ix1 = min(box[2], region["box"][2])
        iy1 = min(box[3], region["box"][3])
        worst = max(worst, max(0, ix1 - ix0) * max(0, iy1 - iy0) / area)
    return worst


def background_color(rgb, box):
    x0, y0, x1, y1 = box
    crop = rgb[y0:y1, x0:x1]
    if crop.size == 0:
        return None
    lum = geometry.luminance(crop)
    light = lum >= 180
    if int(light.sum()) >= 30:
        chosen = crop[light]
        color = tuple(int(np.median(chosen[:, channel])) for channel in range(3))
    else:
        flat = crop.reshape(-1, 3)
        order = np.argsort(lum.reshape(-1))
        pick = flat[order[min(len(order) - 1, int(0.85 * len(order)))]]
        color = tuple(int(value) for value in pick)
    if 0.2126 * color[0] + 0.7152 * color[1] + 0.0722 * color[2] < 160:
        return None
    return color


def find_hosts(rgb, regions):
    dark = geometry.luminance(rgb) < 150
    height, width = dark.shape
    found = []
    for region in regions:
        if region["cat"] not in geometry.HOST_CATS:
            continue
        box = region["box"]
        box_w = box[2] - box[0]
        box_h = box[3] - box[1]
        if not (140 <= box_w <= 980 and 10 <= box_h <= 220):
            continue
        if box[0] < 2 or box[1] < 2 or box[2] > width - 2 or box[3] > height - 2:
            continue
        if picture_overlap(box, regions) > 0.30:
            continue
        band = geometry.first_text_band(dark[box[1]:box[3], box[0]:box[2]])
        if band is None:
            continue
        band_box = (box[0], box[1] + band[0], box[2], box[1] + band[1])
        color = background_color(rgb, band_box)
        if color is None:
            continue
        found.append({
            "ann_id": region["id"],
            "cat": region["cat"],
            "box": box,
            "band": band_box,
            "bg": color,
            "band_uncertain": (band_box[3] - band_box[1]) > 28,
            "center_y": (band_box[1] + band_box[3]) / 2,
        })
    found.sort(key=lambda host: (host["band"][1], host["band"][0], host["ann_id"]))
    chosen = []
    for host in found:
        if not chosen:
            chosen.append(host)
            continue
        if abs(host["center_y"] - chosen[0]["center_y"]) < 80:
            continue
        if geometry.intersects(host["box"], chosen[0]["box"]):
            continue
        chosen.append(host)
        break
    return chosen


def place_name(host, ink, page_w, page_h):
    left, top, right, bottom = [int(v) for v in ink]
    band = host["band"]
    ink_h = bottom - top
    band_h = band[3] - band[1]
    ink_top = band[1] + max(0, (band_h - ink_h) // 2)
    baseline = int(ink_top - top)
    pen_x = int(host["box"][0] + 8)
    shifted = False
    if pen_x + right > page_w - 2:
        pen_x = int(page_w - 2 - right)
        shifted = True
    if pen_x + left < 2 or baseline + top < 2 or baseline + bottom > page_h - 2:
        return None
    return {"pen_x": pen_x, "baseline": baseline, "shifted": shifted}


def compose(rgb, placement, font, text, ink_box, bg):
    left, top, right, bottom = [int(v) for v in ink_box]
    pen_x, baseline = placement["pen_x"], placement["baseline"]
    glyph = (pen_x + left, baseline + top, pen_x + right, baseline + bottom)
    clear = geometry.expand(glyph, 2, rgb.shape[1], rgb.shape[0])
    image = Image.fromarray(rgb.copy())
    draw = ImageDraw.Draw(image)
    draw.rectangle([clear[0], clear[1], clear[2] - 1, clear[3] - 1], fill=bg)
    draw.text((pen_x, baseline), text, fill=(0, 0, 0), font=font, anchor="ls")
    return np.asarray(image), glyph, clear


def clipped_boxes(ink_catalog, pen_x, baseline, kind, page_w, page_h):
    left = pen_x + ink_catalog[:, 0]
    top = baseline + ink_catalog[:, 1]
    right = pen_x + ink_catalog[:, 2]
    bottom = baseline + ink_catalog[:, 3]
    edges, x_l, line_top, line_bottom = geometry.policy_edges(kind, left, top, right, bottom)
    raw = np.stack(edges, axis=1)
    clipped = np.stack(geometry.clip_edges(raw[:, 0], raw[:, 1], raw[:, 2], raw[:, 3], page_w, page_h), axis=1)
    return raw, clipped, x_l, line_top, line_bottom


def score_match(match, log_prior, index):
    out = geometry.guard_rw.possibilistic(np.asarray(match, dtype=bool), log_prior, int(index))
    pointwise = out["pointwise_bits"]
    return {
        "prior_hit1": geometry.guard_rw.expected_hit(log_prior, int(index), 1),
        "prior_hit10": geometry.guard_rw.expected_hit(log_prior, int(index), 10),
        "geo_hit1": out["hit1"],
        "geo_hit10": out["hit10"],
        "entropy_reduction": out["entropy_reduction"],
        "pointwise_bits": "" if pointwise == "" else float(pointwise),
        "truth_in_set": int(out["truth_in_set"]),
        "feasible": int(out["feasible"]),
        "empty_feasible": int(out["empty"]),
    }


def start_unknown_match(kind, true_raw, true_clipped, page_w, page_h, ink_catalog, pen_x, baseline):
    if kind not in {"exact", "square16", "square64"}:
        return None
    if kind == "exact":
        observed = true_clipped[0] if true_clipped.ndim == 2 else true_clipped
        touches = observed[0] in (0, page_w) or observed[2] in (0, page_w) or observed[1] in (0, page_h) or observed[3] in (0, page_h)
        raw, clipped, _, _, _ = clipped_boxes(ink_catalog, pen_x, baseline, "exact", page_w, page_h)
        if not touches:
            width = raw[:, 2] - raw[:, 0]
            height = raw[:, 3] - raw[:, 1]
            return (width == int(true_raw[2] - true_raw[0])) & (height == int(true_raw[3] - true_raw[1]))
        return np.all(clipped == observed, axis=1)
    grid = geometry.SQUARE_POLICIES[kind]
    observed = true_clipped
    raw, _, _, _, _ = clipped_boxes(ink_catalog, 0, 0, "exact", 10**6, 10**6)
    widths = raw[:, 2] - raw[:, 0]
    heights = raw[:, 3] - raw[:, 1]
    return geometry.square_start_unknown(widths, heights, observed, grid, page_w, page_h)


def build_catalogs(names):
    paths = font_paths()
    pillow = {}
    for name, path in paths.items():
        pillow[name] = {}
        for size in BANK_SIZES:
            pillow[name][size] = catalog.pillow_catalog(path, size, names)
    mismatch = {
        12: catalog.mupdf_catalog(paths["DejaVuSans"], 12, names),
        16: catalog.mupdf_catalog(paths["DejaVuSans"], 16, names),
    }
    return pillow, mismatch, paths


def analytic_reference(pillow, prior, log_prior):
    """Layout-free leakage at a fixed pen, away from every page edge."""
    rows = []
    catalog_16 = pillow["DejaVuSans"][16]
    for size in (12, 16):
        ink = pillow["DejaVuSans"][size]
        for kind in geometry.POLICIES:
            raw, clipped, _, _, _ = clipped_boxes(ink, 400, 400, kind, 2000, 2000)
            bits = np.empty(len(prior))
            hit10 = np.empty(len(prior))
            pointwise = np.empty(len(prior))
            for index in range(len(prior)):
                match = np.all(clipped == clipped[index], axis=1)
                scored = score_match(match, log_prior, index)
                bits[index] = scored["entropy_reduction"]
                hit10[index] = scored["geo_hit10"]
                pointwise[index] = scored["pointwise_bits"] if scored["pointwise_bits"] != "" else np.nan
            differ = int(np.any(np.any(ink != catalog_16, axis=1))) if size == 16 else ""
            rows.append({
                "size_px": size,
                "policy": kind,
                "analytic_bits": float(np.average(bits, weights=prior)),
                "analytic_top10": float(np.average(hit10, weights=prior)),
                "analytic_worst_pointwise": float(np.nanmax(pointwise)),
                "identical_boxes": int(np.unique(clipped, axis=0).shape[0] == 1),
            })
    return rows


def ensure_ocr():
    binary = HERE / "bin" / "ocr_helper"
    if binary.exists():
        return binary
    binary.parent.mkdir(parents=True, exist_ok=True)
    compile_cmd = ["swiftc", "-O", "-o", str(binary), str(HERE / "ocr_helper.swift")]
    subprocess.run(compile_cmd, check=True)
    return binary


def ocr_paths(paths):
    binary = ensure_ocr()
    found = {}
    chunk = 25
    for start in range(0, len(paths), chunk):
        batch = paths[start:start + chunk]
        process = subprocess.Popen(
            [str(binary)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        payload = "\n".join(str(path) for path in batch) + "\n"
        output, error = process.communicate(payload)
        if process.returncode != 0:
            raise RuntimeError(error.strip() or "OCR helper failed")
        for line in output.splitlines():
            if not line.strip():
                continue
            page = json.loads(line)
            found[page["path"]] = page
    return found


def ocr_coordinate_check(fonts):
    path = CACHE / "ocr_coordinate_check.png"
    image = Image.new("RGB", (400, 160), (255, 255, 255))
    font = ImageFont.truetype(str(fonts["DejaVuSans"]), 16)
    ImageDraw.Draw(image).text((80, 90), "SMITH", fill=(0, 0, 0), font=font, anchor="ls")
    image.save(path)
    page = ocr_paths([path])[str(path)]
    ink = catalog.paste_ink((160, 400), 80, 90, font, "SMITH")
    ys, xs = np.nonzero(ink)
    truth = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    hits = []
    for line in page["lines"]:
        box = (line["x"], line["y"], line["x"] + line["w"], line["y"] + line["h"])
        if "SMITH" in line["text"].upper() and geometry.intersects(box, truth):
            hits.append(line)
    return {"ok": bool(hits), "lines": page["lines"], "truth_box": truth, "error": page.get("error")}


def choose_name(key, host, names, prior, ink_catalog, page_w, page_h):
    rng = keyed_rng(key)
    for attempt in range(30):
        index = int(rng.choice(len(names), p=prior))
        placement = place_name(host, ink_catalog[index], page_w, page_h)
        if placement is not None:
            return index, attempt, placement
    return None, 30, None


def attack_rows(base, pillow, mismatch, names, log_prior, pen_x, baseline, page_w, page_h, index, size):
    true_ink = pillow["DejaVuSans"][size]
    rows = []
    for kind in geometry.POLICIES:
        raw, clipped, x_l, line_top, line_bottom = clipped_boxes(true_ink, pen_x, baseline, kind, page_w, page_h)
        observed = clipped[index]
        observed_raw = raw[index]
        contains = geometry.contains(tuple(int(v) for v in observed_raw), tuple(int(v) for v in raw[index]))
        # The exact raw box is the reference for containment of every policy.
        exact_raw, exact_clipped, _, _, _ = clipped_boxes(true_ink, pen_x, baseline, "exact", page_w, page_h)
        contains_exact = int(geometry.contains(tuple(int(v) for v in observed_raw), tuple(int(v) for v in exact_raw[index])))
        conditions = []
        match = np.all(clipped == observed, axis=1)
        conditions.append(("matched_template_known", match, "DejaVuSans", "Pillow raster of DejaVu Sans at the true size; pen and baseline known"))
        mismatch_boxes = clipped_boxes(mismatch[size], pen_x, baseline, kind, page_w, page_h)[1]
        conditions.append(("renderer_mismatch", np.all(mismatch_boxes == observed, axis=1), "DejaVuSans", "PyMuPDF raster of the same font file; pen and baseline known"))
        arial_boxes = clipped_boxes(pillow["Arial"][size], pen_x, baseline, kind, page_w, page_h)[1]
        conditions.append(("font_mismatch", np.all(arial_boxes == observed, axis=1), "Arial", "Pillow raster of Arial at the true size; pen and baseline known"))
        union = np.zeros(len(names), dtype=bool)
        for font_name, sized in pillow.items():
            for bank_size, bank in sized.items():
                bank_boxes = clipped_boxes(bank, pen_x, baseline, kind, page_w, page_h)[1]
                union |= np.all(bank_boxes == observed, axis=1)
        conditions.append(("font_unknown", union, "bank", "Any bank font and size in {12,14,16,18,20}; pen and baseline known"))
        if kind in {"exact", "square16", "square64"}:
            unknown = start_unknown_match(kind, observed_raw, observed, page_w, page_h, true_ink, pen_x, baseline)
            conditions.append(("start_unknown", unknown, "DejaVuSans", "True font and Pillow renderer; text start and baseline not given"))
        for condition, mask, attacker_font, attacker_requires in conditions:
            scored = score_match(mask, log_prior, index)
            row = dict(base)
            row.update({
                "policy": kind,
                "condition": condition,
                "attacker_font": attacker_font,
                "attacker_requires": attacker_requires,
                "redactor_requires": geometry.REDACTOR_REQUIRES[kind],
                "x_l": x_l,
                "line_top": line_top,
                "line_bottom": line_bottom,
                "box_x0": int(observed[0]),
                "box_y0": int(observed[1]),
                "box_x1": int(observed[2]),
                "box_y1": int(observed[3]),
                "clipped": int(tuple(int(v) for v in observed) != tuple(int(v) for v in observed_raw)),
                "exact_area": geometry.area(tuple(int(v) for v in exact_clipped[index])),
                "mask_area": geometry.area(tuple(int(v) for v in observed)),
                "contains_exact": contains_exact,
                "candidate_n": len(names),
                "grid_ok": "",
            })
            if kind in geometry.SQUARE_POLICIES:
                row["grid_ok"] = int(geometry.grid_aligned(tuple(int(v) for v in observed), geometry.SQUARE_POLICIES[kind], page_w, page_h))
            row["area_ratio"] = row["mask_area"] / row["exact_area"] if row["exact_area"] else ""
            row["over_area"] = row["mask_area"] - row["exact_area"]
            row.update(scored)
            rows.append((row, tuple(int(v) for v in observed), tuple(int(v) for v in exact_clipped[index])))
    return rows


def neighbor_fields(dark, host, clear, mask, regions, lines, page_w, page_h):
    loss = geometry.loss_for(dark, host["box"], host["ann_id"], clear, mask, regions, page_w, page_h)
    if lines is None:
        words, chars, reliability = "", "", "ocr_unavailable"
    else:
        words, chars = geometry.ocr_neighbor_counts(lines, mask, clear)
        reliability = "ocr_proportional_split_estimate"
    loss.update({"neighbor_words_est": words, "neighbor_chars_est": chars, "ocr_reliability": reliability})
    return loss


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sample_pages(pages, grouped, eligible_files, quotas, salt, limit_opens):
    rng = np.random.default_rng(SEED)
    manifest = []
    selected = []
    opened = 0
    for category in CATEGORIES:
        subset = pages[(pages["doc_category"] == category) & pages["file_name"].isin(eligible_files)].copy()
        documents = sorted(subset["doc_name"].unique())
        order = np.array(documents)
        rng.shuffle(order)
        filled = {"evaluation": 0, "calibration": 0}
        for doc_name in order:
            if filled["evaluation"] >= quotas["evaluation"][category] and filled["calibration"] >= quotas["calibration"][category]:
                break
            role = role_of(str(doc_name), salt)
            if filled[role] >= quotas[role][category]:
                continue
            doc_pages = subset[subset["doc_name"] == doc_name].sort_values(["page_no", "file_name"])
            positions = np.arange(len(doc_pages))
            rng.shuffle(positions)
            taken = 0
            for position in positions:
                if taken >= MAX_PAGES_PER_DOC or filled[role] >= quotas[role][category]:
                    if taken >= MAX_PAGES_PER_DOC:
                        skipped = doc_pages.iloc[int(position)]
                        manifest.append(manifest_row(skipped, role, "excluded_page_cap", ""))
                    continue
                record = doc_pages.iloc[int(position)]
                path = PNG / record["file_name"]
                if not path.exists():
                    manifest.append(manifest_row(record, role, "excluded_missing_png", ""))
                    continue
                if opened >= limit_opens:
                    manifest.append(manifest_row(record, role, "excluded_open_limit", ""))
                    return selected, manifest, opened
                opened += 1
                with Image.open(path) as image:
                    if image.size != (int(record["width"]), int(record["height"])):
                        manifest.append(manifest_row(record, role, "excluded_dimension_mismatch", ""))
                        continue
                    rgb = np.asarray(image.convert("RGB"))
                regions = regions_from_array(grouped[record["file_name"]])
                hosts = find_hosts(rgb, regions)
                if not hosts:
                    manifest.append(manifest_row(record, role, "excluded_no_paintable_line", ""))
                    continue
                digest = sha256_file(path)
                selected.append({
                    "record": record.to_dict(),
                    "role": role,
                    "rgb": rgb,
                    "regions": regions,
                    "hosts": hosts,
                    "sha256": digest,
                })
                manifest.append(manifest_row(record, role, f"selected_{role}", digest))
                filled[role] += 1
                taken += 1
                print(f"selected {category} {role} {filled[role]}/{quotas[role][category]} {record['file_name'][:12]}", flush=True)
    return selected, manifest, opened


def manifest_row(record, role, decision, digest):
    return {
        "decision": decision,
        "assigned_role": role,
        "file_name": record["file_name"],
        "sha256": digest,
        "image_id": int(record["image_id"]),
        "coco_split": record["split"],
        "doc_name": record["doc_name"],
        "doc_category": record["doc_category"],
        "page_no": int(record["page_no"]),
        "collection": record["collection"],
        "width": int(record["width"]),
        "height": int(record["height"]),
        "exclusion_reason": "" if decision.startswith("selected") else decision,
    }


def run_stage(stage):
    started = time.time()
    if stage == "pilot":
        quotas = {"evaluation": PILOT_EVAL, "calibration": PILOT_CAL}
        salt = "doclaynet-validation-pilot-v1"
        out = HERE / "results" / "pilot"
        open_limit = 400
    else:
        quotas = {"evaluation": EVAL_QUOTA, "calibration": CAL_QUOTA}
        salt = "doclaynet-validation-v1"
        out = HERE / "results"
        open_limit = 20000
        sentinel = HERE / "results" / "pilot" / "PILOT_OK"
        if not sentinel.exists():
            raise SystemExit("Pilot has not passed. Run --stage pilot first.")
    out.mkdir(parents=True, exist_ok=True)
    print("loading indexes", flush=True)
    pages, boxes, duplicate_files = load_pages_and_boxes()
    print("indexing regions", flush=True)
    grouped, eligible_files = build_region_index(boxes)
    del boxes
    names, prior, surname_sha = load_surnames()
    log_prior = np.log(prior)
    print("building catalogs", flush=True)
    pillow, mismatch, paths = build_catalogs(names)
    fonts = {name: path for name, path in paths.items()}
    print("OCR coordinate check", flush=True)
    ocr_check = ocr_coordinate_check(paths)
    if not ocr_check["ok"]:
        (out / "FAILURES.md").write_text(
            "Pilot blocked: Vision did not return the synthetic surname inside the drawn ink.\n\n"
            + json.dumps(ocr_check, default=str, indent=2)
            + "\n"
        )
        raise SystemExit("OCR coordinate check failed")
    print("sampling pages", flush=True)
    selected, manifest, opened = sample_pages(pages, grouped, eligible_files, quotas, salt, open_limit)
    print(f"scoring {len(selected)} pages", flush=True)
    rows = []
    region_log = []
    true_accept = []
    false_trials = []
    false_accepts = []
    coverage_failures = []
    examples = []
    ocr_needed = [str(PNG / item["record"]["file_name"]) for item in selected]
    print(f"OCR of {len(ocr_needed)} pages", flush=True)
    ocr = ocr_paths(ocr_needed)
    name_rejections = []
    for item in selected:
        record = item["record"]
        rgb = item["rgb"]
        dark = geometry.luminance(rgb) < 150
        lines = ocr.get(str(PNG / record["file_name"]), {}).get("lines", [])
        page_h, page_w = rgb.shape[:2]
        for host_number, host in enumerate(item["hosts"]):
            key = f"{record['file_name']}:{host['ann_id']}"
            index, rejected, placement16 = choose_name(
                key, host, names, prior, pillow["DejaVuSans"][PRIMARY_SIZE], page_w, page_h
            )
            name_rejections.append(rejected)
            if index is None:
                region_log.append({"file_name": record["file_name"], "reason": "no_surname_fit_on_page", "host_ann_id": host["ann_id"]})
                continue
            for size in (SENSITIVITY_SIZE, PRIMARY_SIZE):
                font = ImageFont.truetype(str(paths["DejaVuSans"]), size)
                placement = place_name(host, pillow["DejaVuSans"][size][index], page_w, page_h)
                if placement is None:
                    region_log.append({"file_name": record["file_name"], "reason": f"size_{size}_does_not_fit", "host_ann_id": host["ann_id"]})
                    continue
                ink_mask = catalog.paste_ink(rgb.shape[:2], placement["pen_x"], placement["baseline"], font, names[index])
                base = {
                    "track": "controlled_insertion",
                    "text_origin": "controlled_insertion",
                    "role": item["role"],
                    "size_px": size,
                    "doc_name": record["doc_name"],
                    "doc_category": record["doc_category"],
                    "coco_split": record["split"],
                    "file_name": record["file_name"],
                    "page_no": int(record["page_no"]),
                    "image_id": int(record["image_id"]),
                    "target_id": f"{record['file_name']}:{host['ann_id']}:{size}",
                    "host_ann_id": host["ann_id"],
                    "host_category": geometry.CAT_NAME[host["cat"]],
                    "string": names[index],
                    "font": "DejaVuSans",
                    "pen_x": placement["pen_x"],
                    "baseline": placement["baseline"],
                    "anchor_shifted": int(placement["shifted"]),
                    "band_uncertain": int(host["band_uncertain"]),
                    "names_rejected": rejected,
                }
                produced = attack_rows(base, pillow, mismatch, names, log_prior, placement["pen_x"], placement["baseline"], page_w, page_h, index, size)
                outside = {}
                for row, mask, exact_box in produced:
                    if row["condition"] != "matched_template_known":
                        continue
                    outside[row["policy"]] = geometry.ink_outside(ink_mask, mask)
                for row, mask, exact_box in produced:
                    loss = neighbor_fields(dark, host, geometry.expand(
                        (
                            placement["pen_x"] + int(pillow["DejaVuSans"][size][index][0]),
                            placement["baseline"] + int(pillow["DejaVuSans"][size][index][1]),
                            placement["pen_x"] + int(pillow["DejaVuSans"][size][index][2]),
                            placement["baseline"] + int(pillow["DejaVuSans"][size][index][3]),
                        ),
                        2, page_w, page_h,
                    ), mask, item["regions"], lines, page_w, page_h)
                    row.update(loss)
                    row["coverage_outside_px"] = outside[row["policy"]]
                    if outside[row["policy"]]:
                        coverage_failures.append(row["target_id"] + ":" + row["policy"])
                    rows.append(row)
                composed, glyph, clear = compose(rgb, placement, font, names[index], pillow["DejaVuSans"][size][index], host["bg"])
                search = geometry.expand(glyph, 1, page_w, page_h)
                accepted, detail = verify_render(composed, search, names[index], {"DejaVuSans": paths["DejaVuSans"]}, sizes=(size,))
                true_accept.append({"target_id": base["target_id"], "accepted": int(accepted), "detail": detail["best"]})
                if (
                    len(examples) < 4
                    and item["role"] == "evaluation"
                    and size == PRIMARY_SIZE
                    and record["doc_category"] in {"manuals", "scientific_articles", "patents"}
                    and not host["band_uncertain"]
                ):
                    examples.append({
                        "rgb": rgb,
                        "composed": composed,
                        "placement": placement,
                        "font": font,
                        "text": names[index],
                        "bg": host["bg"],
                        "ink": pillow["DejaVuSans"][size][index],
                        "file_name": record["file_name"],
                        "category": record["doc_category"],
                        "page_no": int(record["page_no"]),
                        "rows": [row for row, _, _ in produced if row["condition"] == "matched_template_known"],
                    })
        if item["role"] == "calibration":
            false_trials.extend(false_accept_trial(rgb, lines, names, prior, paths, record["file_name"]))
    for trial in false_trials:
        false_accepts.append(trial)
    original_rows, original_log = original_track(selected, ocr, names, prior, log_prior, pillow, paths)
    region_log.extend(original_log)
    false_rate = float(np.mean([item["accepted"] for item in false_accepts])) if false_accepts else None
    original_privacy_used = bool(false_accepts) and false_rate <= 0.02
    if original_privacy_used:
        rows.extend(original_rows)
    else:
        region_log.append({
            "file_name": "",
            "reason": "original_privacy_withheld",
            "false_accept_rate": false_rate,
            "confirmed_rows_withheld": len(original_rows),
        })
    frame = pd.DataFrame(rows)
    problems = qa_problems(frame, manifest, ocr_check, true_accept, false_accepts, coverage_failures)
    write_csv(out / "results.csv", rows)
    write_csv(out / "dataset_manifest.csv", manifest)
    write_csv(out / "region_log.csv", region_log)
    (out / "true_accept.json").write_text(json.dumps(true_accept, indent=2))
    (out / "false_accept.json").write_text(json.dumps(false_accepts, indent=2))
    config = experiment_config(stage, salt, quotas, paths, surname_sha, duplicate_files, len(pages), opened, ocr_check)
    (out / "experiment_config.json").write_text(json.dumps(config, indent=2))
    analytic = analytic_reference(pillow, prior, log_prior)
    (out / "analytic_reference.json").write_text(json.dumps(analytic, indent=2))
    diagnostics = {
        "pages_selected": len(selected),
        "result_rows": len(rows),
        "name_rejection_mean": float(np.mean(name_rejections)) if name_rejections else None,
        "name_rejection_max": int(np.max(name_rejections)) if name_rejections else None,
        "true_accept_rate": float(np.mean([item["accepted"] for item in true_accept])) if true_accept else None,
        "false_accept_trials": len(false_accepts),
        "false_accept_rate": false_rate,
        "original_privacy_used": original_privacy_used,
        "original_rows_withheld": 0 if original_privacy_used else len(original_rows),
        "coverage_failures": coverage_failures,
        "qa_problems": problems,
        "duplicate_file_names": duplicate_files,
        "png_files_on_disk": len(list(PNG.glob("*.png"))) if stage == "pilot" else None,
        "seconds": time.time() - started,
    }
    if stage == "full":
        diagnostics["png_files_on_disk"] = sum(1 for _ in PNG.glob("*.png"))
    (out / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2))
    import reporting
    reporting.write_all(out, frame, manifest, diagnostics, analytic, config, examples, stage)
    if problems:
        (out / "FAILURES.md").write_text("\n".join(f"- {problem}" for problem in problems) + "\n")
        if (out / "PILOT_OK").exists():
            (out / "PILOT_OK").unlink()
        raise SystemExit("Quality checks failed:\n" + "\n".join(problems))
    if stage == "pilot":
        stale = out / "FAILURES.md"
        if stale.exists():
            stale.unlink()
        (out / "PILOT_OK").write_text("pilot checks passed\n")
        corrections = out / "CORRECTIONS.md"
        if not corrections.exists():
            corrections.write_text("No implementation correction was required after this pilot.\n")
    print(json.dumps({key: diagnostics[key] for key in ("pages_selected", "result_rows", "true_accept_rate", "false_accept_rate", "qa_problems")}, indent=2))


def false_accept_trial(rgb, lines, names, prior, paths, file_name):
    trials = []
    candidate = None
    for line in lines:
        token = normalize_token(line.get("text", ""))
        height = float(line["h"])
        width = float(line["w"])
        if token is None or line.get("confidence", 0) < 0.80:
            continue
        if not (8 <= height <= 48 and width >= 2.5 * height):
            continue
        candidate = (line, token)
        break
    if candidate is None:
        return trials
    line, token = candidate
    box = (line["x"] - 2, line["y"] - 2, line["x"] + line["w"] + 2, line["y"] + line["h"] + 2)
    rng = keyed_rng("false-accept:" + file_name)
    pool = [index for index, name in enumerate(names) if name != token]
    picks = rng.choice(pool, size=min(15, len(pool)), replace=False, p=None)
    # Nearest ink widths are the proposals most likely to be confused with the line.
    dark = geometry.luminance(rgb) < 180
    x0, y0, x1, y1 = geometry.clip_box(tuple(int(v) for v in box), rgb.shape[1], rgb.shape[0])
    ys, xs = np.nonzero(dark[y0:y1, x0:x1])
    if len(xs) == 0:
        return trials
    target_width = int(xs.max() - xs.min() + 1)
    widths = pillow_width = None
    from_catalog = catalog.pillow_catalog(paths["DejaVuSans"], 16, names)
    order = np.argsort(np.abs((from_catalog[:, 2] - from_catalog[:, 0]) - target_width))
    nearest = [int(index) for index in order if names[int(index)] != token][:10]
    proposed = list(dict.fromkeys(list(nearest) + [int(index) for index in picks]))[:15]
    for index in proposed:
        accepted, _detail = verify_render(rgb, box, names[index], font_paths(), sizes=VERIFY_SIZES)
        trials.append({"file_name": file_name, "proposed": names[index], "ocr_token": token, "accepted": int(accepted)})
    return trials


def original_track(selected, ocr, names, prior, log_prior, pillow, paths):
    lookup = {name.casefold(): index for index, name in enumerate(names)}
    rows = []
    log = []
    fonts = font_paths()
    for item in selected:
        record = item["record"]
        lines = ocr.get(str(PNG / record["file_name"]), {}).get("lines", [])
        verified = 0
        attempts = 0
        for line in sorted(lines, key=lambda entry: (entry["y"], entry["x"])):
            if verified >= 3 or attempts >= 8:
                break
            attempts += 1
            token = normalize_token(line.get("text", ""))
            height = float(line["h"])
            width = float(line["w"])
            if token is None or float(line.get("confidence", 0)) < 0.80 or not (8 <= height <= 48 and width >= 2.5 * height):
                continue
            box = (line["x"] - 2, line["y"] - 2, line["x"] + line["w"] + 2, line["y"] + line["h"] + 2)
            accepted, detail = verify_render(item["rgb"], box, token, fonts, sizes=VERIFY_SIZES)
            if not accepted:
                log.append({"file_name": record["file_name"], "track": "verified_original", "token": token, "reason": "render_did_not_confirm", "best_recall": None if not detail["best"] else detail["best"]["recall"]})
                continue
            verified += 1
            if detail["ambiguous"] or token.casefold() not in lookup:
                reason = "font_ambiguous" if detail["ambiguous"] else "string_not_in_closed_surname_prior"
                log.append({"file_name": record["file_name"], "track": "verified_original", "token": token, "reason": reason, "best_recall": detail["best"]["recall"]})
                continue
            # A confirmed surname still uses a Pillow hypothesis, not the unknown original renderer.
            log.append({"file_name": record["file_name"], "track": "verified_original", "token": token, "reason": "confirmed_but_renderer_is_not_the_original", "best_recall": detail["best"]["recall"]})
            rows.extend(original_privacy_rows(item, line, token, lookup[token.casefold()], detail, pillow, names, log_prior))
    return rows, log


def original_privacy_rows(item, line, token, index, detail, pillow, names, log_prior):
    """Score exact and square policies from the page ink, with the font treated as a hypothesis."""
    record = item["record"]
    rgb = item["rgb"]
    page_h, page_w = rgb.shape[:2]
    dark = geometry.luminance(rgb) < 180
    x0, y0, x1, y1 = geometry.clip_box((int(line["x"]) - 2, int(line["y"]) - 2, int(line["x"] + line["w"]) + 2, int(line["y"] + line["h"]) + 2), page_w, page_h)
    ys, xs = np.nonzero(dark[y0:y1, x0:x1])
    if len(xs) == 0:
        return []
    ink = np.array([[int(x0 + xs.min()), int(y0 + ys.min()), int(x0 + xs.max()) + 1, int(y0 + ys.max()) + 1]])
    # One-element catalog placed at the origin. policy_edges expects edges, so pass the ink as already absolute
    # by using a zero pen after subtracting nothing: the array itself is the page ink.
    rows = []
    best = detail["passes"][0]
    hypothesis = pillow.get(best["font"], {}).get(best["size"])
    for kind in ("exact", "square16", "square64"):
        raw, clipped, x_l, line_top, line_bottom = clipped_boxes(ink, 0, 0, kind, page_w, page_h)
        observed = clipped[0]
        base = {
            "track": "verified_original",
            "text_origin": "verified_original",
            "role": item["role"],
            "size_px": best["size"],
            "doc_name": record["doc_name"],
            "doc_category": record["doc_category"],
            "coco_split": record["split"],
            "file_name": record["file_name"],
            "page_no": int(record["page_no"]),
            "image_id": int(record["image_id"]),
            "target_id": f"original:{record['file_name']}:{int(line['x'])}:{int(line['y'])}:{kind}",
            "host_ann_id": "",
            "host_category": "",
            "string": token,
            "font": best["font"],
            "pen_x": "",
            "baseline": "",
            "anchor_shifted": "",
            "band_uncertain": "",
            "names_rejected": "",
            "policy": kind,
            "condition": "pillow_font_hypothesis",
            "attacker_font": best["font"],
            "attacker_requires": "Pillow raster of the verifier's font hypothesis; this is not the original renderer",
            "redactor_requires": geometry.REDACTOR_REQUIRES[kind],
            "x_l": x_l,
            "line_top": line_top,
            "line_bottom": line_bottom,
            "box_x0": int(observed[0]),
            "box_y0": int(observed[1]),
            "box_x1": int(observed[2]),
            "box_y1": int(observed[3]),
            "clipped": int(tuple(int(v) for v in observed) != tuple(int(v) for v in raw[0])),
            "exact_area": "",
            "mask_area": geometry.area(tuple(int(v) for v in observed)),
            "contains_exact": "",
            "candidate_n": len(names),
            "grid_ok": "",
            "coverage_outside_px": "",
            "neighbor_ink_px": "",
            "scope_ink_px": "",
            "fraction_ink_obscured": "",
            "unrelated_regions": "",
            "unrelated_overlap": "",
            "neighbor_words_est": "",
            "neighbor_chars_est": "",
            "ocr_reliability": "verified_render_match",
        }
        if hypothesis is None:
            base.update({
                "area_ratio": "",
                "over_area": "",
                "prior_hit1": "",
                "prior_hit10": "",
                "geo_hit1": "",
                "geo_hit10": "",
                "entropy_reduction": "",
                "pointwise_bits": "",
                "truth_in_set": "",
                "feasible": "",
                "empty_feasible": "",
            })
            rows.append(base)
            continue
        # Align the hypothesis catalog to the page ink's left and top.
        pen_x = int(ink[0, 0] - hypothesis[index, 0])
        baseline = int(ink[0, 1] - hypothesis[index, 1])
        _raw, hyp_clipped, _, _, _ = clipped_boxes(hypothesis, pen_x, baseline, kind, page_w, page_h)
        match = np.all(hyp_clipped == observed, axis=1)
        scored = score_match(match, log_prior, index)
        exact_raw, exact_clipped, _, _, _ = clipped_boxes(ink, 0, 0, "exact", page_w, page_h)
        base["exact_area"] = geometry.area(tuple(int(v) for v in exact_clipped[0]))
        base["area_ratio"] = base["mask_area"] / base["exact_area"] if base["exact_area"] else ""
        base["over_area"] = base["mask_area"] - base["exact_area"]
        base["pen_x"] = pen_x
        base["baseline"] = baseline
        base.update(scored)
        rows.append(base)
    return rows


def qa_problems(frame, manifest, ocr_check, true_accept, false_accepts, coverage_failures):
    problems = []
    if not ocr_check["ok"]:
        problems.append("OCR coordinate check failed")
    problems.extend(separation_problems(frame.to_dict("records")) if len(frame) else [])
    if coverage_failures:
        problems.append(f"painted pixels remain outside a matched mask: {len(coverage_failures)}")
    if len(frame):
        matched = frame[(frame["track"] == "controlled_insertion") & (frame["condition"] == "matched_template_known")]
        if len(matched) and int((matched["truth_in_set"] == 0).sum()):
            problems.append("matched attacker excluded the inserted surname")
        field = matched[matched["policy"] == "field"]
        if len(field) and float(np.max(np.abs(field["entropy_reduction"].astype(float)))) > 1e-9:
            problems.append("field policy entropy reduction was not zero")
        if len(field) and int((field["feasible"] != 1000).sum()):
            problems.append("field policy feasible set was not the full candidate list")
        squares = matched[matched["policy"].isin(["square16", "square64"])]
        if len(squares) and int((squares["grid_ok"].astype(int) == 0).sum()):
            problems.append("a square mask missed the page grid")
        if len(matched) and int((matched["contains_exact"].astype(int) == 0).sum()):
            problems.append("a policy box did not contain the exact box")
        unknown = frame[(frame["track"] == "controlled_insertion") & (frame["condition"] == "start_unknown")]
        if len(unknown) and int((unknown["truth_in_set"] == 0).sum()):
            problems.append("start-unknown attacker excluded the inserted surname")
        known_font = frame[(frame["track"] == "controlled_insertion") & (frame["condition"] == "font_unknown")]
        if len(known_font) and int((known_font["truth_in_set"] == 0).sum()):
            problems.append("font-unknown union excluded the inserted surname")
    roles = {}
    for row in manifest:
        if row["decision"].startswith("selected"):
            roles.setdefault(row["doc_name"], set()).add("evaluation" if "evaluation" in row["decision"] else "calibration")
    overlap = [doc for doc, seen in roles.items() if len(seen) > 1]
    if overlap:
        problems.append(f"calibration and evaluation share documents: {len(overlap)}")
    if true_accept:
        rate = float(np.mean([item["accepted"] for item in true_accept]))
        if rate < 0.95:
            problems.append(f"verifier true-accept rate {rate:.3f} is below 0.95")
    return problems


def experiment_config(stage, salt, quotas, paths, surname_sha, duplicate_files, n_pages, opened, ocr_check):
    import matplotlib
    import PIL
    versions = {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "pillow": PIL.__version__,
        "matplotlib": matplotlib.__version__,
    }
    try:
        import fitz
        versions["pymupdf"] = fitz.__doc__.splitlines()[0]
    except Exception:
        versions["pymupdf"] = None
    return {
        "stage": stage,
        "seed": SEED,
        "bootstrap_draws": BOOTSTRAP_DRAWS,
        "salt": salt,
        "quotas": quotas,
        "primary_size_px": PRIMARY_SIZE,
        "sensitivity_size_px": SENSITIVITY_SIZE,
        "font_sha256": {name: catalog.file_sha256(path) for name, path in paths.items()},
        "font_paths": {name: str(path) for name, path in paths.items()},
        "study_dejavu_sha256_knowledge_matched": "57f73e11f51999432bf7ab22ce55b6f945d5eca1bf824404cfa9ec2e3718c84e",
        "surname_sha256": surname_sha,
        "candidate_n": 1000,
        "coco_sha256": COCO_SHA256,
        "coco_pages": n_pages,
        "duplicate_file_names_dropped": duplicate_files,
        "pages_opened": opened,
        "dataset_version": "DocLayNet 1.0.0",
        "dataset_license": "CDLA-Permissive-1.0",
        "dataset_note": "Local DocLayNet_core has COCO layout boxes and PNGs. It has no PDF text layer and no DocLayNet extra JSON cells. Layout labels are not used as transcriptions.",
        "ocr_coordinate_check": ocr_check["ok"],
        "versions": versions,
        "policies": list(geometry.POLICIES),
        "redactor_requires": geometry.REDACTOR_REQUIRES,
    }


def main():
    stage = "pilot"
    if len(sys.argv) > 1 and sys.argv[1] == "--stage" and len(sys.argv) > 2:
        stage = sys.argv[2]
    if stage not in {"pilot", "full"}:
        raise SystemExit("Use --stage pilot or --stage full")
    run_stage(stage)


if __name__ == "__main__":
    main()
