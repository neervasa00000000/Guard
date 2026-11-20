#!/usr/bin/env python3
"""Second real-page leakage run.

Imports research/e1 and research/realworld_e1_eval/run_eval.py. It does not
modify them. Run it with research/realworld_e1_eval/.venv, whose Pillow is
12.3.0 linked to the RAQM, HarfBuzz, FriBidi and FreeType libraries in
.prefix.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
os.environ["E1_CENSUS"] = str(HERE.parents[1] / "data" / "census" / "Names_2010Census.csv")
os.environ["E1_OUTPUT"] = str(HERE / "cache")
os.environ["E1_FONT_DIR"] = str(HERE / "fonts")
sys.path.insert(0, str(HERE))
import run_eval as base  # noqa: E402

E = base.E
P = base.P
OUT = HERE / "results" / "v2"
GEOM_OUT = HERE / "data" / "geometry"
FRESH_FONTS = (
    "DejaVuSans",
    "DejaVuSerif",
    "LiberationSans",
    "LiberationSerif",
    "LiberationMono",
)
RETAINED_FONT = "NotoSans"


def require_renderer() -> dict:
    import PIL
    from PIL import features

    report = {
        "pillow": PIL.__version__,
        "raqm_check": bool(features.check("raqm")),
        "raqm": features.version("raqm"),
        "harfbuzz": features.version("harfbuzz"),
        "fribidi": features.version("fribidi"),
        "freetype2": features.version("freetype2"),
        "python": sys.version,
    }
    expected = {
        "pillow": "12.3.0",
        "raqm_check": True,
        "raqm": "0.10.5",
        "harfbuzz": "14.2.1",
        "fribidi": "1.0.16",
        "freetype2": "2.14.3",
    }
    mismatches = {key: report[key] for key, value in expected.items() if report[key] != value}
    if mismatches:
        raise SystemExit(
            "Renderer versions do not match the study. "
            f"Available: {report}. Mismatches: {mismatches}."
        )
    return report


def receipt_digest(bounds: np.ndarray) -> str:
    array = np.ascontiguousarray(bounds)
    return hashlib.sha256(pickle.dumps(array, protocol=4)).hexdigest()


def load_receipts() -> dict:
    path = base.E1 / "data" / "v1_3" / "geometry_receipts.csv"
    return {
        (row["font"], int(row["size_px"])): row["geometry_sha256"]
        for _, row in base.read_rows(path)
    }


def render_geometry(dictionary) -> tuple[dict, dict]:
    """Re-render every font whose pinned file is present. Noto is retained."""
    receipts = load_receipts()
    strings = dictionary["full"]["strings"]
    bank = {}
    comparisons = []
    GEOM_OUT.mkdir(parents=True, exist_ok=True)
    for font in FRESH_FONTS:
        for size in base.SIZES:
            path = GEOM_OUT / f"geom_surnames_{font}_{size}.npy"
            if path.is_file():
                bounds = np.load(path)
            else:
                face = E.font(font, size)
                bounds = np.array([face.getbbox(name, anchor="ls") for name in strings], dtype=np.int32)
                np.save(path, bounds)
            digest = receipt_digest(bounds)
            expect = receipts[(font, size)]
            matched = digest == expect
            comparisons.append({
                "font": font,
                "size_px": size,
                "source": "rendered",
                "digest": digest,
                "receipt": expect,
                "matched": matched,
            })
            if not matched:
                continue
            path = GEOM_OUT / f"geom_surnames_{font}_{size}.npy"
            np.save(path, bounds)
            bank[(font, size)] = bounds
    noto_ok = True
    for size in base.SIZES:
        path = base.GEOM_DIR / f"geom_surnames_{RETAINED_FONT}_{size}.pkl"
        bounds = np.load(path)
        digest = receipt_digest(bounds)
        expect = receipts[(RETAINED_FONT, size)]
        matched = digest == expect and bounds.shape == (50000, 4)
        noto_ok = noto_ok and matched
        comparisons.append({
            "font": RETAINED_FONT,
            "size_px": size,
            "source": "retained because the pinned Noto Sans file is not available",
            "digest": digest,
            "receipt": expect,
            "matched": matched,
        })
        if matched:
            bank[(RETAINED_FONT, size)] = np.ascontiguousarray(bounds, dtype=np.int32)
    fresh = [row for row in comparisons if row["source"] == "rendered"]
    fresh_rate = sum(row["matched"] for row in fresh) / len(fresh)
    all_rate = sum(row["matched"] for row in comparisons) / len(comparisons)
    report = {
        "fresh_files": len(fresh),
        "fresh_matches": sum(row["matched"] for row in fresh),
        "fresh_match_rate": fresh_rate,
        "files": len(comparisons),
        "matches": sum(row["matched"] for row in comparisons),
        "match_rate_including_retained_noto": all_rate,
        "rows": comparisons,
    }
    print(
        f"Fresh geometry match {report['fresh_matches']}/{report['fresh_files']}. "
        f"Receipt match including retained Noto {report['matches']}/{report['files']}.",
        flush=True,
    )
    if fresh_rate < 1 or not noto_ok or len(bank) != 18:
        raise SystemExit(
            "Geometry does not match geometry_receipts.csv. "
            f"Fresh match rate {fresh_rate}. Scoring stopped."
        )
    return bank, report


def prepare_bank(raw: dict, tolerance: int) -> dict:
    pair = (-int(tolerance), int(tolerance))
    tol = (pair, pair, pair, pair)
    bank = {}
    for key, bounds in raw.items():
        array = np.ascontiguousarray(bounds, dtype=np.int64)
        bank[key] = {
            "bounds": array,
            "x_l": int(array[:, 0].min()) - E.PAD,
            "right": array[:, 2] + E.PAD,
            "width": array[:, 2] - array[:, 0],
            "cell": E.Cell(array, tol, 0),
        }
    return bank


def nearest_size(height: float) -> int:
    return min(base.SIZES, key=lambda size: (abs(size - height), size))


def size_choice(embedded, box_height: float) -> tuple[int, float, str]:
    value = None
    try:
        if embedded is not None and embedded != "":
            value = float(embedded)
    except (TypeError, ValueError):
        value = None
    if value is not None and value > 1:
        return nearest_size(value), value, "embedded font size"
    return nearest_size(box_height), box_height, "box height"


def load_saved_pages() -> list[dict]:
    path = HERE / "results" / "doclaynet_page_ids.csv"
    pages = []
    for _, row in base.read_rows(path):
        pages.append({
            "page_id": row["page_id"],
            "file_name": row["file_name"],
            "doc_category": row["doc_category"],
            "source_split": row["source_split"],
            "coco_id": int(row["coco_id"]),
            "width": int(row["width"]),
            "height": int(row["height"]),
            "precedence": int(row["precedence"]),
        })
    base.require(len(pages) == base.PAGE_N, f"Saved DocLayNet page list has {len(pages)} rows")
    base.require(len({page['page_id'] for page in pages}) == base.PAGE_N, "Saved page ids are not unique")
    return pages


def load_coco_pages() -> list[dict]:
    pages = {}
    for split in ("train", "val", "test"):
        path = base.COCO_DIR / f"{split}.json"
        print(f"Reading DocLayNet COCO {split}", flush=True)
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        for image in payload.get("images", []):
            page_id = Path(image["file_name"]).stem
            record = {
                "page_id": page_id,
                "file_name": image["file_name"],
                "doc_category": image.get("doc_category", ""),
                "source_split": split,
                "coco_id": image.get("id") or 0,
                "width": int(image["width"]),
                "height": int(image["height"]),
                "precedence": image.get("precedence", 0),
            }
            current = pages.get(page_id)
            if current is None or base.page_rank(record) < base.page_rank(current):
                pages[page_id] = record
        del payload
    return list(pages.values())


def common_words() -> dict:
    import importlib.metadata
    import wordfreq

    words = wordfreq.top_n_list("en", 5000)
    base.require(len(words) == 5000, f"wordfreq returned {len(words)} English words")
    version = importlib.metadata.version("wordfreq")
    base.require(version == "3.1.1", f"wordfreq {version} is not the study pin 3.1.1")
    return {
        "words": {word.casefold() for word in words},
        "version": version,
        "n": len(words),
    }


def likely_name(surface: str, common: set[str]) -> bool:
    return bool(surface) and surface[0].isupper() and surface.casefold() not in common


def tokens_from_pages(pages: list[dict], dictionary, common: set[str], dataset: str) -> tuple[list[dict], dict]:
    index = dictionary["index"]
    tokens = []
    cells = 0
    outside = 0
    single = 0
    for page in pages:
        path = base.JSON_DIR / f"{page['page_id']}.json"
        if not path.is_file():
            continue
        document = json.loads(path.read_text())
        raw_cells = document.get("cells", [])
        boxes = []
        kept = []
        for cell in raw_cells:
            cells += 1
            box = base.pixel_box(cell.get("bbox") or [])
            if box is None:
                continue
            if box[0] < -2 or box[1] < -2 or box[2] > page["width"] + 2 or box[3] > page["height"] + 2:
                outside += 1
            bbox = cell.get("bbox") or [0, 0, 0, 0]
            words = base.alpha_tokens(cell.get("text", ""))
            font = (cell.get("font") or {})
            boxes.append(box)
            kept.append((words, font, float(bbox[3]) if len(bbox) == 4 else box[3] - box[1]))
        if not boxes:
            continue
        lines = base.line_bounds(boxes)
        for (words, font, raw_height), box, line in zip(kept, boxes, lines):
            if len(words) != 1:
                continue
            single += 1
            surface = words[0]
            truth = index.get(surface.casefold())
            if truth is None:
                continue
            size, measured, source = size_choice(font.get("size"), raw_height)
            tokens.append(make_token(
                dataset, page["page_id"], dictionary, truth, surface, box, line, size, measured, source, common,
            ))
    stats = {
        "cells": cells,
        "cells_outside_page": outside,
        "single_token_cells": single,
        "qualifying_tokens": len(tokens),
        "qualifying_pages": len({token["page_id"] for token in tokens}),
        "likely_names": sum(token["likely_name"] for token in tokens),
    }
    if cells and outside / cells > 0.05:
        raise SystemExit("More than 5% of DocLayNet cell boxes fall outside the page")
    return tokens, stats


def make_token(dataset, page_id, dictionary, truth, surface, box, line, size, measured, source, common) -> dict:
    return {
        "dataset": dataset,
        "page_id": page_id,
        "token": dictionary["full"]["strings"][truth],
        "surface": surface,
        "truth": truth,
        "x0": box[0],
        "y0": box[1],
        "x1": box[2],
        "y1": box[3],
        "line_top": line[0],
        "line_bottom": line[1],
        "size_px": size,
        "height_px": measured,
        "height_source": source,
        "likely_name": int(likely_name(surface, common)),
    }


def collect_funsd_tokens(dictionary, common: set[str], stems: list[str] | None, label: str) -> tuple[list[dict], dict]:
    info = base.prepare_funsd()
    train = base.funsd_split_dir("training_data")
    test = base.funsd_split_dir("testing_data")
    train_stems = sorted(path.stem for path in (train / "annotations").glob("*.json"))
    test_stems = sorted(path.stem for path in (test / "annotations").glob("*.json"))
    base.require(len(train_stems) == 149 and len(test_stems) == 50, "FUNSD split is not 149/50")
    split_dir = train if label == "calibration" else test
    chosen = train_stems if stems is None and label == "calibration" else (stems if stems is not None else test_stems)
    convention = base.box_convention(test if label == "scored" else split_dir)
    add_one = 1 if convention["add_one"] else 0
    index = dictionary["index"]
    tokens = []
    answer_fields = 0
    answer_words = 0
    for stem in chosen:
        path = split_dir / "annotations" / f"{stem}.json"
        payload = json.loads(path.read_text())
        words = []
        for field in payload["form"]:
            if field.get("label") == "answer":
                answer_fields += 1
            for word in field.get("words", []):
                x0, y0, x1, y1 = (int(value) for value in word["box"])
                x1 += add_one
                y1 += add_one
                if x1 <= x0 or y1 <= y0:
                    continue
                words.append({
                    "box": (x0, y0, x1, y1),
                    "text": word.get("text", ""),
                    "label": field.get("label", ""),
                })
        lines = base.line_bounds([word["box"] for word in words]) if words else []
        for word, line in zip(words, lines):
            if word["label"] != "answer":
                continue
            answer_words += 1
            parts = base.alpha_tokens(word["text"])
            if len(parts) != 1:
                continue
            truth = index.get(parts[0].casefold())
            if truth is None:
                continue
            box = word["box"]
            size, measured, source = size_choice(None, box[3] - box[1])
            tokens.append(make_token(
                "FUNSD", path.stem, dictionary, truth, parts[0], box, line, size, measured, source, common,
            ))
    stats = {
        **info,
        "training_forms": len(train_stems),
        "testing_forms": len(test_stems),
        "forms_used": len(chosen),
        "form_ids": chosen,
        "answer_fields": answer_fields,
        "answer_words": answer_words,
        "qualifying_tokens": len(tokens),
        "qualifying_forms": len({token["page_id"] for token in tokens}),
        "likely_names": sum(token["likely_name"] for token in tokens),
        "convention": convention["convention"],
        "zero_area": convention["zero_area"],
        "add_one": convention["add_one"],
    }
    return tokens, stats


def choose_calibration_pages(universe: list[dict], scored: list[dict]) -> tuple[list[dict], dict]:
    scored_ids = {page["page_id"] for page in scored}
    regenerated, _meta = base.sample_doclaynet()
    regenerated_ids = {page["page_id"] for page in regenerated}
    base.require(regenerated_ids == scored_ids, "Saved DocLayNet page list does not match Generator(0)")
    complement = [page for page in universe if page["page_id"] not in scored_ids]
    complement.sort(key=lambda page: page["page_id"])
    count = len(universe) * 20 // 100
    base.require(count <= len(complement), "Calibration sample is larger than the held-out pages")
    rng = np.random.default_rng(base.PAGE_SEED)
    picked = np.sort(rng.choice(len(complement), size=count, replace=False))
    selected = [complement[int(index)] for index in picked]
    meta = {
        "generator": "numpy.random.Generator",
        "seed": base.PAGE_SEED,
        "rule": "uniform draw from unique pages not in the saved 2,000, page ids sorted, count = unique_pages * 20 // 100",
        "unique_pages": len(universe),
        "held_out_pool": len(complement),
        "sampled_pages": len(selected),
        "overlap_with_scored": len({page["page_id"] for page in selected} & scored_ids),
    }
    base.require(meta["overlap_with_scored"] == 0, "Calibration pages overlap the scored pages")
    return selected, meta


def choose_funsd_forms() -> list[str]:
    train = base.funsd_split_dir("training_data")
    test = base.funsd_split_dir("testing_data")
    train_stems = sorted(path.stem for path in (train / "annotations").glob("*.json"))
    test_stems = set(path.stem for path in (test / "annotations").glob("*.json"))
    base.require(len(train_stems) == 149 and len(test_stems) == 50, "FUNSD split is not 149/50")
    rng = np.random.default_rng(base.PAGE_SEED)
    picked = np.sort(rng.choice(len(train_stems), size=10, replace=False))
    chosen = [train_stems[int(index)] for index in picked]
    base.require(not (set(chosen) & test_stems), "A FUNSD calibration form is in the test split")
    return chosen


def width_error(token: dict, raw: dict) -> int:
    observed = token["x1"] - token["x0"]
    size = token["size_px"]
    truth = token["truth"]
    gaps = [abs(int(raw[(font, size)][truth, 2] - raw[(font, size)][truth, 0]) - observed) for font in E.FONTS]
    return min(gaps)


def calibrate(tokens: list[dict], raw: dict) -> tuple[int, float, list[dict]]:
    rows = []
    minimums = []
    for token in tokens:
        error = width_error(token, raw)
        minimum = (error + 1) // 2
        minimums.append(minimum)
        rows.append({
            "dataset": token["dataset"],
            "page_id": token["page_id"],
            "token": token["token"],
            "size_px": token["size_px"],
            "height_px": token["height_px"],
            "height_source": token["height_source"],
            "width_error_px": error,
            "min_tolerance_px": minimum,
            "likely_name": token["likely_name"],
        })
    base.require(rows, "Calibration produced no surname tokens")
    values = np.asarray(minimums)
    chosen = None
    rate = None
    for candidate in range(int(values.max()) + 1):
        rate = float(np.mean(values <= candidate))
        if rate >= 0.95:
            chosen = candidate
            break
    if chosen is None:
        raise SystemExit("No symmetric tolerance puts 95% of calibration tokens in the feasible set")
    print(f"Calibrated symmetric tolerance {chosen}px, truth-in {rate}", flush=True)
    return chosen, rate, rows


def feasible_mask(token: dict, bank: dict, dictionary, policy: str, tolerance: int) -> np.ndarray:
    size = token["size_px"]
    fonts = E.FONTS
    if policy in {"nobox", "field-1000", "field-50000"}:
        width = 1000 if policy == "field-1000" else len(dictionary["full"]["p"])
        return np.ones(width, dtype=bool)
    if policy in {"exact", "grid-16", "grid-64"}:
        grid = {"exact": 1, "grid-16": 16, "grid-64": 64}[policy]
        box = base.released_box(token, None, policy, 0)
        mask = np.zeros(len(dictionary["full"]["p"]), dtype=bool)
        for font in fonts:
            mask |= base.horizontal_feasible(bank[(font, size)]["cell"], box[0], box[2], grid)
        return mask
    width = base.PAD_C if policy == "start-aligned-128" else base.ZERO_LEAK_C[size]
    mask = np.zeros(len(dictionary["full"]["p"]), dtype=bool)
    measured = token["x1"] - token["x0"] + E.PAD
    low = measured - 2 * tolerance
    high = measured + 2 * tolerance
    for font in fonts:
        item = bank[(font, size)]
        classes = P.class_index(item["right"], item["x_l"], width)
        left = int(P.class_index(np.array([low]), item["x_l"], width)[0])
        right = int(P.class_index(np.array([high]), item["x_l"], width)[0])
        mask |= (classes >= left) & (classes <= right)
    return mask


def analytic_exact_in(token: dict, raw: dict, tolerance: int) -> bool:
    return width_error(token, raw) <= 2 * tolerance


def score_tokens(tokens: list[dict], dictionary, bank: dict, raw: dict, tolerance: int) -> list[dict]:
    rows = []
    total = len(tokens)
    policies = ("exact", "grid-16", "grid-64", "start-aligned-128", "start-aligned-zero-leak")
    for number, token in enumerate(tokens, start=1):
        for policy in policies:
            mask = feasible_mask(token, bank, dictionary, policy, tolerance)
            if policy == "exact":
                scored_in = bool(mask[token["truth"]]) if mask.size else False
                base.require(
                    scored_in == analytic_exact_in(token, raw, tolerance),
                    f"Exact feasible set disagrees with the width tolerance at {token['token_id']}",
                )
            scored = base.score_mask(dictionary, mask, token["truth"], short=False)
            if policy in {"exact", "grid-16", "grid-64"}:
                box = base.released_box(token, None, policy, 0)
            else:
                width = base.PAD_C if policy == "start-aligned-128" else base.ZERO_LEAK_C[token["size_px"]]
                box = base.released_box(token, bank[(next(iter(E.FONTS)), token["size_px"])], policy, width)
            rows.append(emit(token, policy, box, scored))
        for policy, short in (
            ("field-1000", True),
            ("field-50000", False),
            ("nobox", False),
            ("nobox-1000", True),
        ):
            if short and token["truth"] >= 1000:
                continue
            width = 1000 if short else len(dictionary["full"]["p"])
            mask = np.ones(width, dtype=bool)
            scored = base.score_mask(dictionary, mask, token["truth"], short=short)
            if policy.startswith("field"):
                limit = width
                item = dict(bank[(next(iter(E.FONTS)), token["size_px"])])
                item["right"] = item["right"][:limit]
                box = base.released_box(token, item, "field", 0)
            else:
                box = ("", "", "", "")
            rows.append(emit(token, policy, box, scored))
        if number % 500 == 0 or number == total:
            print(f"Scored {number}/{total} {token['dataset']}", flush=True)
    return rows


def emit(token, policy, box, scored) -> dict:
    return {
        "dataset": token["dataset"],
        "page_id": token["page_id"],
        "token": token["token"],
        "policy": policy,
        "box": ",".join(str(value) for value in box),
        "candidate_count": scored["candidate_count"],
        "rank": scored["rank"],
        "bits": base.fmt(scored["bits"]),
        "size_px": token["size_px"],
        "likely_name": token["likely_name"],
        "token_id": token["token_id"],
        "hit1": base.fmt(scored["hit1"]),
        "hit10": base.fmt(scored["hit10"]),
        "truth_in": int(scored["truth_in"]),
    }


def grouped(rows: list[dict], dataset: str, policy: str, name_filter: str) -> dict:
    chosen = [row for row in rows if row["dataset"] == dataset and row["policy"] == policy]
    if name_filter == "likely names":
        chosen = [row for row in chosen if int(row["likely_name"]) == 1]
    docs = defaultdict(lambda: {key: [] for key in ("bits", "hit1", "hit10", "truth", "candidates")})
    for row in chosen:
        page = row["page_id"]
        docs[page]["bits"].append(float(row["bits"]))
        docs[page]["hit1"].append(float(row["hit1"]))
        docs[page]["hit10"].append(float(row["hit10"]))
        docs[page]["truth"].append(float(row["truth_in"]))
        docs[page]["candidates"].append(float(row["candidate_count"]))
    return docs


def cluster_interval(docs: dict, key: str, truth_only: bool = False):
    pages = sorted(docs)
    values = []
    for page in pages:
        item = np.asarray(docs[page][key], dtype=np.float64)
        if truth_only:
            item = item[np.asarray(docs[page]["truth"], dtype=np.float64) == 1]
        if item.size:
            values.append(item)
    if not values:
        return None
    sums = np.array([item.sum() for item in values])
    counts = np.array([item.size for item in values])
    point = float(sums.sum() / counts.sum())
    rng = np.random.default_rng(base.BOOT_SEED)
    draws = rng.integers(0, len(values), size=(base.BOOT_DRAWS, len(values)))
    totals = counts[draws].sum(axis=1)
    valid = totals > 0
    means = np.full(base.BOOT_DRAWS, np.nan)
    means[valid] = sums[draws][valid].sum(axis=1) / totals[valid]
    observed = means[valid]
    low, high = (float(item) for item in np.quantile(observed, [0.025, 0.975]))
    return point, low, high, int(counts.sum()), len(values), int(valid.sum())


def summarise(rows: list[dict]) -> list[dict]:
    datasets = []
    policies = []
    for row in rows:
        if row["dataset"] not in datasets:
            datasets.append(row["dataset"])
        if row["policy"] not in policies:
            policies.append(row["policy"])
    summary = []
    for dataset in datasets:
        for policy in policies:
            for name_filter in ("all surname tokens", "likely names"):
                docs = grouped(rows, dataset, policy, name_filter)
                if not docs:
                    summary.append({
                        "dataset": dataset,
                        "token_filter": name_filter,
                        "policy": policy,
                        "n_tokens": 0,
                        "n_documents": 0,
                        "bits": "undefined",
                        "bits_lo": "undefined",
                        "bits_hi": "undefined",
                        "bits_truth_in": "undefined",
                        "bits_truth_in_lo": "undefined",
                        "bits_truth_in_hi": "undefined",
                        "top1": "undefined",
                        "top10": "undefined",
                        "truth_in": "undefined",
                        "mean_candidates": "undefined",
                    })
                    continue
                bits = cluster_interval(docs, "bits")
                restricted = cluster_interval(docs, "bits", truth_only=True)
                hit1 = cluster_interval(docs, "hit1")
                hit10 = cluster_interval(docs, "hit10")
                truth = cluster_interval(docs, "truth")
                candidates = cluster_interval(docs, "candidates")
                summary.append({
                    "dataset": dataset,
                    "token_filter": name_filter,
                    "policy": policy,
                    "n_tokens": bits[3],
                    "n_documents": bits[4],
                    "bits": base.fmt(bits[0]),
                    "bits_lo": base.fmt(bits[1]),
                    "bits_hi": base.fmt(bits[2]),
                    "bits_truth_in": "undefined" if restricted is None else base.fmt(restricted[0]),
                    "bits_truth_in_lo": "undefined" if restricted is None else base.fmt(restricted[1]),
                    "bits_truth_in_hi": "undefined" if restricted is None else base.fmt(restricted[2]),
                    "n_truth_in": 0 if restricted is None else restricted[3],
                    "top1": base.fmt(hit1[0]),
                    "top1_lo": base.fmt(hit1[1]),
                    "top1_hi": base.fmt(hit1[2]),
                    "top10": base.fmt(hit10[0]),
                    "top10_lo": base.fmt(hit10[1]),
                    "top10_hi": base.fmt(hit10[2]),
                    "truth_in": base.fmt(truth[0]),
                    "truth_in_lo": base.fmt(truth[1]),
                    "truth_in_hi": base.fmt(truth[2]),
                    "mean_candidates": base.fmt(candidates[0]),
                    "nobox_policy": "nobox-1000" if policy == "field-1000" else "nobox",
                })
    return summary


def lookup(summary, dataset, policy, name_filter):
    for row in summary:
        if row["dataset"] == dataset and row["policy"] == policy and row["token_filter"] == name_filter:
            return row
    return None


def percent_cell(text: str) -> str:
    if text == "undefined":
        return text
    return base.percent_from_fraction(text)


def synthetic_rows() -> list[dict]:
    sources = base.synthetic_sources()
    pooled = base.E1 / "review4" / "pooled.csv"
    names = {"exact": "exact", "grid-16": "square-16", "grid-64": "square-64"}
    for source in sources:
        policy = names.get(source["policy_key"])
        if policy is None:
            source["truth_in"] = "not in source"
            continue
        _line, row = base.find_row(
            pooled,
            lambda item, policy=policy: item["list"] == "surnames" and item["size_px"] == "all"
            and item["model"] == "LAYOUT-BOX" and item["attacker"] == "A1" and item["policy"] == policy,
        )
        source["truth_in"] = base.percent_from_fraction(row["truth_in"])
    v12 = base.E1 / "data" / "v1_2" / "summary.csv"
    citations = []
    for width in (96, 128, 192):
        line, row = base.find_row(
            v12,
            lambda item, width=width: item["size_px"] == "all" and item["policy"] == "start-aligned" and item["width_px"] == str(width),
        )
        citations.append(f"research/e1/data/v1_2/summary.csv:{line} width {width} bits={row['bits']}")
    zero = {
        "policy_label": "start-aligned zero-leak",
        "policy_key": "start-aligned-zero-leak",
        "n": "not in source",
        "bits": "not in source",
        "bits_lo": "not in source",
        "bits_hi": "not in source",
        "top1": "not in source",
        "top10": "not in source",
        "nobox_top10": "not in source",
        "truth_in": "not in source",
        "source": "no pooled size-matched zero-leak row; " + "; ".join(citations),
    }
    ordered = []
    by_key = {row["policy_key"]: row for row in sources}
    for key in ("exact", "grid-16", "grid-64", "start-aligned-128"):
        ordered.append(by_key[key])
    ordered.append(zero)
    ordered.append(by_key["field-1000"])
    return ordered


def real_line(summary, dataset, label, policy, name_filter, source) -> str:
    row = lookup(summary, dataset, policy, name_filter)
    if row is None or row["n_tokens"] == 0:
        cells = ["0" if row and row["n_tokens"] == 0 else "0", "undefined", "undefined", "undefined", "undefined", "undefined", "undefined"]
    else:
        base_row = lookup(summary, dataset, row.get("nobox_policy", "nobox"), name_filter)
        nobox = "undefined" if base_row is None else percent_cell(str(base_row["top10"]))
        bits = row["bits"] if row["bits"] == "undefined" else f"{row['bits']} [{row['bits_lo']}, {row['bits_hi']}]"
        restricted = row["bits_truth_in"]
        if restricted != "undefined":
            restricted = f"{row['bits_truth_in']} [{row['bits_truth_in_lo']}, {row['bits_truth_in_hi']}]"
        cells = [
            str(row["n_tokens"]),
            percent_cell(str(row["truth_in"])),
            percent_cell(str(row["top1"])),
            percent_cell(str(row["top10"])),
            nobox,
            bits,
            restricted,
        ]
    synthetic = source["source"] if source["bits"] == "not in source" else f"{source['bits']} ({source['source']})"
    return " | ".join([label, name_filter, source["policy_label"], *cells, synthetic])


def write_results(summary, sources, comparison: str) -> None:
    header = "Dataset | Token filter | Policy | n | Truth-in % | Top-1 % | Top-10 % | No-box top-10 % | Bits [95% CI] | Bits (truth-in only) | Synthetic value (source CSV:row)"
    lines = [header, "--- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---"]
    for source in sources:
        synthetic_bits = source["bits"] if source["bits"] == "not in source" else f"{source['bits']} [{source['bits_lo']}, {source['bits_hi']}]"
        synthetic_value = source["source"] if source["bits"] == "not in source" else f"{source['bits']} ({source['source']})"
        lines.append(" | ".join([
            "synthetic",
            "archived surnames",
            source["policy_label"],
            str(source["n"]),
            str(source["truth_in"]),
            str(source["top1"]),
            str(source["top10"]),
            str(source["nobox_top10"]),
            synthetic_bits,
            "not in source",
            synthetic_value,
        ]))
        for dataset, label in (("DocLayNet", "DocLayNet"), ("FUNSD", "FUNSD test")):
            for name_filter in ("all surname tokens", "likely names"):
                lines.append(real_line(summary, dataset, label, source["policy_key"], name_filter, source))
    text = [
        "# Real-page leakage, second run",
        "",
        "Each real token is scored at its nearest study size, 12, 16 or 24 px, with one symmetric edge tolerance frozen from the calibration split. Bits are the scorer's prior entropy minus posterior entropy. Bits (truth-in only) averages that quantity over tokens whose true name is in the feasible set. Intervals are 10,000 document-clustered bootstrap draws from Generator(20261114).",
        "",
        "\n".join(lines),
        "",
        comparison,
        "",
        "summary.csv has full precision, no-box top-1, mean candidate-set size, and the 50,000-surname field.",
        "",
    ]
    (HERE / "RESULTS_v2.md").write_text("\n".join(text))


def comparison_text(summary, tolerance: int, calibration_rate: float, ablation: dict) -> str:
    old_path = HERE / "results" / "summary.csv"
    lines = ["## Old run compared with this run", ""]
    lines.append(
        f"The frozen symmetric tolerance is {tolerance} px. "
        f"On the pooled calibration tokens its exact-box truth-in rate is {base.fmt(calibration_rate)}."
    )
    lines.append("")
    lines.append("Old truth-in is the six-font bank averaged across 12, 16 and 24 px at tolerance 0, from results/summary.csv. The t=0 column is this run's nearest-size attacker at tolerance 0 on the same scored tokens. The v2 column uses the frozen tolerance.")
    lines.append("")
    lines.append("Dataset | Policy | Old truth-in | Nearest size, t=0 | v2 truth-in | Old bits | v2 bits")
    lines.append("--- | --- | --- | --- | --- | --- | ---")
    old_rows = { (row["dataset"], row["policy"]): row for _, row in base.read_rows(old_path) if row["font_mode"] == "bank" }
    for dataset in ("DocLayNet", "FUNSD"):
        for policy in ("exact", "grid-16", "grid-64", "start-aligned-128", "start-aligned-zero-leak", "field-1000"):
            old = old_rows.get((dataset, policy))
            new = lookup(summary, dataset, policy, "all surname tokens")
            if new is None:
                continue
            key = f"{dataset}|{policy}"
            zero = ablation.get(key, "not computed")
            lines.append(" | ".join([
                dataset,
                policy,
                old["truth_in"] if old is not None else "not in old summary",
                zero,
                str(new["truth_in"]),
                old["bits"] if old is not None else "not in old summary",
                str(new["bits"]),
            ]))
    lines.append("")
    lines.append("Nearest-size assignment moves truth-in relative to the old three-size average. The frozen tolerance is the remaining change from that nearest-size t=0 column to the v2 column. Padding and the field box use the same tolerance as a width slack of twice the edge tolerance, because each horizontal edge can move by that many pixels.")
    return "\n".join(lines)


def ablation_truth(tokens, bank, raw) -> dict:
    out = {}
    policies = ("exact", "grid-16", "grid-64", "start-aligned-128", "start-aligned-zero-leak", "field-1000")
    for dataset in ("DocLayNet", "FUNSD"):
        chosen = [token for token in tokens if token["dataset"] == dataset]
        for policy in policies:
            usable = chosen
            if policy == "field-1000":
                usable = [token for token in chosen if token["truth"] < 1000]
            if not usable:
                out[f"{dataset}|{policy}"] = "undefined"
                continue
            hits = []
            for token in usable:
                if policy == "field-1000":
                    hits.append(True)
                else:
                    mask = feasible_mask(token, bank, {"full": {"p": np.ones(50000)}}, policy, 0)
                    hits.append(bool(mask[token["truth"]]))
            out[f"{dataset}|{policy}"] = base.fmt(float(np.mean(hits)))
    return out


def update_deviations(text: str) -> None:
    path = HERE / "DEVIATIONS.md"
    previous = path.read_text() if path.is_file() else ""
    start = "<!-- v2-start -->"
    end = "<!-- v2-end -->"
    block = f"{start}\n{text.rstrip()}\n{end}\n"
    if start in previous and end in previous:
        head, rest = previous.split(start, 1)
        _, tail = rest.split(end, 1)
        path.write_text(head + block + tail.lstrip("\n"))
    else:
        path.write_text(block + "\n" + previous)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    renderer = require_renderer()
    print("Loading the surname list", flush=True)
    dictionary = base.load_dictionary()
    raw, geometry_report = render_geometry(dictionary)
    prepared = prepare_bank(raw, 0)
    base.check_archived_classes(dictionary, prepared)
    words = common_words()
    common = words["words"]
    scored_pages = load_saved_pages()
    universe = load_coco_pages()
    calibration_pages, calibration_meta = choose_calibration_pages(universe, scored_pages)
    print(f"Downloading {len(calibration_pages)} calibration pages and reusing the saved 2,000", flush=True)
    needed = scored_pages + calibration_pages
    download = base.download_cells(needed)
    missing_json = [
        page["page_id"] for page in needed
        if not (base.JSON_DIR / f"{page['page_id']}.json").is_file()
    ]
    base.require(
        not download["failures"] and not download["missing_members"] and not missing_json,
        "DocLayNet JSON download is incomplete: "
        f"{len(download['failures'])} failures, {len(download['missing_members'])} missing members, "
        f"{len(missing_json)} files absent",
    )
    doc_tokens, doc_stats = tokens_from_pages(scored_pages, dictionary, common, "DocLayNet")
    cal_doc_tokens, cal_doc_stats = tokens_from_pages(calibration_pages, dictionary, common, "DocLayNet")
    funsd_forms = choose_funsd_forms()
    funsd_tokens, funsd_stats = collect_funsd_tokens(dictionary, common, None, "scored")
    cal_funsd_tokens, cal_funsd_stats = collect_funsd_tokens(dictionary, common, funsd_forms, "calibration")
    print(
        f"Scored DocLayNet tokens {doc_stats['qualifying_tokens']} likely {doc_stats['likely_names']}; "
        f"FUNSD {funsd_stats['qualifying_tokens']} likely {funsd_stats['likely_names']}",
        flush=True,
    )
    calibration_tokens = cal_doc_tokens + cal_funsd_tokens
    tolerance, calibration_rate, calibration_rows = calibrate(calibration_tokens, raw)
    for row in calibration_rows:
        row["in_at_frozen"] = int(row["min_tolerance_px"] <= tolerance)
    bank = prepare_bank(raw, tolerance)
    base.assign_ids(doc_tokens, "doclaynet")
    base.assign_ids(funsd_tokens, "funsd")
    ablation = ablation_truth(doc_tokens + funsd_tokens, prepared, raw)
    scored = score_tokens(doc_tokens + funsd_tokens, dictionary, bank, raw, tolerance)
    base.write_csv(OUT / "per_token.csv", scored)
    summary = summarise(scored)
    base.write_csv(OUT / "summary.csv", summary)
    base.write_csv(OUT / "calibration.csv", calibration_rows)
    sources = synthetic_rows()
    comparison = comparison_text(summary, tolerance, calibration_rate, ablation)
    write_results(summary, sources, comparison)
    per_dataset = {}
    for dataset in ("DocLayNet", "FUNSD"):
        subset = [row for row in calibration_rows if row["dataset"] == dataset]
        per_dataset[dataset] = {
            "tokens": len(subset),
            "truth_in": None if not subset else float(np.mean([row["in_at_frozen"] for row in subset])),
        }
    config = {
        "seeds": {
            "doclaynet_pages": {"generator": "numpy.random.Generator", "seed": base.PAGE_SEED, "source": "results/doclaynet_page_ids.csv"},
            "calibration_pages": calibration_meta,
            "calibration_funsd_forms": {"generator": "numpy.random.Generator", "seed": base.PAGE_SEED, "forms": funsd_forms},
            "bootstrap": {"generator": "numpy.random.Generator", "seed": base.BOOT_SEED, "draws": base.BOOT_DRAWS},
        },
        "renderer": renderer,
        "numpy": np.__version__,
        "wordfreq": words["version"],
        "wordfreq_list": "top_n_list('en', 5000)",
        "geometry": geometry_report,
        "tolerance_px": tolerance,
        "calibration_truth_in": calibration_rate,
        "calibration_by_dataset": per_dataset,
        "size_rule": "nearest of 12, 16, 24; ties to the smaller size; DocLayNet uses embedded font size when it is greater than 1, otherwise cell height; FUNSD uses box height",
        "doclaynet_scored": doc_stats,
        "doclaynet_calibration": cal_doc_stats,
        "funsd_scored": {key: value for key, value in funsd_stats.items() if key != "form_ids"},
        "funsd_calibration": {key: value for key, value in cal_funsd_stats.items() if key != "form_ids"},
        "download_failures": download.get("failures"),
        "missing_members": download.get("missing_members"),
        "exact_t0_truth_in": ablation,
    }
    (OUT / "run_config.json").write_text(json.dumps(config, indent=2, default=str) + "\n")
    (OUT / "calibration_pages.json").write_text(json.dumps({
        "doclaynet": [page["page_id"] for page in calibration_pages],
        "funsd": funsd_forms,
    }) + "\n")
    deviations = "\n".join([
        "# Deviations in the second real-page run",
        "",
        f"Pillow {renderer['pillow']}, RAQM {renderer['raqm']}, HarfBuzz {renderer['harfbuzz']}, FriBidi {renderer['fribidi']} and FreeType {renderer['freetype2']} match the study. `PIL.features.check('raqm')` is true. Pillow's stock source only includes `raqm.h` when RAQM is a system library, so this build also includes `hb.h` and `fribidi.h`. That exposes the version strings. It does not change layout.",
        "",
        f"Fresh layout arrays were rendered for DejaVu Sans, DejaVu Serif, Liberation Sans, Liberation Serif and Liberation Mono at 12, 16 and 24 px. {geometry_report['fresh_matches']} of {geometry_report['fresh_files']} match `research/e1/data/v1_3/geometry_receipts.csv`. The pinned Noto Sans variable file, SHA-256 7b8cac46a1c86d2533a616b1fcf4e1926b8e39bda69034508b0df96791f56d97, is not in the Google Fonts history checked, Noto Sans releases v2.010, v2.012 and v2.015, or the current fonts.google.com download. `research/e1/data/v1_2/README.md` already records that this binary was unavailable. Noto geometry is the retained array, and its protocol-4 digest matches the receipt. Scoring therefore uses receipt-matched geometry for all 18 font-size files. The fresh-render rate is {geometry_report['fresh_matches']}/{geometry_report['files']}.",
        "",
        "Each token is scored at one study size. The height is the embedded font size when that value is greater than 1. The stored value 1 is the extractor's placeholder: those cells have pixel heights near a text line, so the cell height is used instead. FUNSD has no embedded size, so the word-box height is used. Ties in absolute distance choose the smaller of 12, 16 and 24. Candidate widths are not rescaled.",
        "",
        f"The edge tolerance is the smallest symmetric ±t, in pixels, at which the true surname's layout width at the nearest size matches the annotation width in at least one of the six fonts for 95% of calibration tokens. Calibration uses {calibration_meta['sampled_pages']} DocLayNet pages drawn with Generator(0) from the pages outside the saved 2,000, and 10 FUNSD training forms drawn with a separate Generator(0). None of those pages or forms is scored. The frozen tolerance is {tolerance} px and the pooled calibration truth-in rate is {base.fmt(calibration_rate)}. Exact and grid rows apply that tolerance inside `e1lib.Cell`. Padding treats it as a slack of 2t on the measured width, because both horizontal edges can move by t. The field box already contains every candidate.",
        "",
        "The attacker remains the horizontal half of A2: pen x is unknown and the baseline is not on the page, so height does not remove candidates. An empty feasible set is still replaced by the full prior inside `e1lib.metrics`, which makes bits leaked 0. Bits in the table are reported beside truth-in, and the truth-in-only column drops tokens whose true name is outside the feasible set.",
        "",
        "The likely-name filter keeps a token when its surface form starts with an uppercase letter and its casefold is outside wordfreq's top 5,000 English words. All-caps tokens stay in. The other filter keeps every surname-list token.",
        "",
        "The size-matched zero-leak synthetic cell has no single archived row. The table cites the three v1.2 start-aligned rows for widths 96, 128 and 192 and does not combine them.",
        "",
    ])
    update_deviations(deviations)
    print("Wrote RESULTS_v2.md and results/v2/", flush=True)


if __name__ == "__main__":
    main()
