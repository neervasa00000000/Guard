#!/usr/bin/env python3
"""Real-page leakage evaluation using the research/e1 policies and scorer.

This file imports research/e1. It does not modify it and it does not render
glyphs. Candidate boxes are the retained surname layout arrays, checked
against research/e1/data/per_person/geometry_receipts.csv.
"""
from __future__ import annotations

import csv
import gc
import hashlib
import json
import math
import os
import pickle
import re
import sys
import unicodedata
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
E1 = ROOT / "research" / "e1"
GEOM_DIR = ROOT / "out" / "retained-geom"
CENSUS_PATH = ROOT / "data" / "census" / "Names_2010Census.csv"
COCO_DIR = ROOT / "dataset" / "DocLayNet_core" / "COCO"
CORE_ZIP = ROOT / "dataset" / "DocLayNet_core.zip"
DATA = HERE / "data"
JSON_DIR = DATA / "doclaynet" / "json"
FUNSD_ZIP = DATA / "funsd" / "dataset.zip"
FUNSD_ROOT = DATA / "funsd" / "extracted"
RESULTS = HERE / "results"

PAGE_SEED = 0
BOOT_SEED = 20261114
BOOT_DRAWS = 10000
PAGE_N = 2000
SIZES = (12, 16, 24)
ZERO_LEAK_C = {12: 96, 16: 128, 24: 192}
PAD_C = 128
FUNSD_URL = "https://guillaumejaume.github.io/FUNSD/dataset.zip"
DOCLAYNET_VERSION = "1.0.0"

os.environ["E1_CENSUS"] = str(CENSUS_PATH)
os.environ["E1_OUTPUT"] = str(HERE / "cache")
sys.path.insert(0, str(E1))
import e1lib as E  # noqa: E402
import policies as P  # noqa: E402

sys.path.insert(0, str(ROOT / "research" / "datasets" / "doclaynet"))
import download_sample as D  # noqa: E402

FONT_STEMS = (
    ("dejavusans", "DejaVuSans"),
    ("dejavuserif", "DejaVuSerif"),
    ("liberationsans", "LiberationSans"),
    ("liberationserif", "LiberationSerif"),
    ("liberationmono", "LiberationMono"),
    ("notosans", "NotoSans"),
)
ALPHA = re.compile(r"[A-Za-z]+")
TABLE_POLICIES = (
    ("exact", "exact"),
    ("grid-16", "16-px grid"),
    ("grid-64", "64-px grid"),
    ("start-aligned-128", "start-aligned padding"),
    ("field-1000", "field box"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: float) -> str:
    return format(float(value), ".16g")


def read_rows(path: Path) -> list[tuple[int, dict]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        return [(index, row) for index, row in enumerate(reader, start=2)]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def load_dictionary():
    require(CENSUS_PATH.is_file(), f"Census CSV missing: {CENSUS_PATH}")
    census_sha = sha256_file(CENSUS_PATH)
    require(census_sha == E.FULL_CENSUS_SHA, "Census SHA-256 does not match e1lib.FULL_CENSUS_SHA")
    full = E.dict_surnames()
    names, counts = E.census(1000)
    short = E._finish(names, counts, np.ones(len(names)), {"source": "Census head"})
    require(full["strings"][:1000] == list(names), "The 1,000-surname list is not the prefix of the 50,000 list")
    folded = [name.casefold() for name in full["strings"]]
    require(len(folded) == 50000 and len(set(folded)) == 50000, "Surname casefolds are not a set of 50,000")
    index = {name: i for i, name in enumerate(folded)}
    logp = np.log2(full["p"])
    h0 = float(-(full["p"] * logp).sum())
    logp_short = np.log2(short["p"])
    h0_short = float(-(short["p"] * logp_short).sum())
    archived = {row["dict"]: row for _, row in read_rows(E1 / "data" / "baselines_nobox.csv")}
    require(
        abs(h0 - float(archived["surnames"]["prior_bits"])) < 1e-9,
        "Computed 50,000-surname prior entropy disagrees with baselines_nobox.csv",
    )
    return {
        "full": full,
        "short": short,
        "index": index,
        "logp": logp,
        "h0": h0,
        "logp_short": logp_short,
        "h0_short": h0_short,
        "lengths": np.array([len(name) for name in full["strings"]], dtype=np.int32),
        "lengths_short": np.array([len(name) for name in short["strings"]], dtype=np.int32),
        "census_sha256": census_sha,
        "prior_bits_archived": archived["surnames"]["prior_bits"],
    }


def load_geometry(dictionary) -> dict:
    receipts = {
        (row["font"], int(row["size_px"])): row["geometry_sha256"]
        for _, row in read_rows(E1 / "data" / "per_person" / "geometry_receipts.csv")
    }
    bank = {}
    for font in E.FONTS:
        for size in SIZES:
            path = GEOM_DIR / f"geom_surnames_{font}_{size}.pkl"
            require(path.is_file(), f"Retained geometry missing: {path}")
            bounds = np.load(path)
            require(bounds.shape == (50000, 4), f"Unexpected geometry shape: {path}")
            digest = hashlib.sha256(pickle.dumps(np.ascontiguousarray(bounds), protocol=4)).hexdigest()
            require(digest == receipts[(font, size)], f"Geometry receipt mismatch: {font} {size}")
            array = np.ascontiguousarray(bounds, dtype=np.int64)
            x_l = int(array[:, 0].min()) - E.PAD
            right = array[:, 2] + E.PAD
            bank[(font, size)] = {
                "bounds": array,
                "x_l": x_l,
                "right": right,
                "cell": E.Cell(array, ((0, 0), (0, 0), (0, 0), (0, 0)), 0),
                "file_sha256": sha256_file(path),
                "pickle_sha256": digest,
            }
    check_archived_classes(dictionary, bank)
    return bank


def check_archived_classes(dictionary, bank) -> None:
    """Stop if width classes disagree with the archived analytic tail."""
    prior = dictionary["full"]["p"]
    archived = {}
    for line, row in read_rows(E1 / "data" / "per_person" / "tail_summary.csv"):
        if row["font"] == "pooled" or int(row["n_units"]) != 1:
            continue
        archived[(row["font"], int(row["size_px"]), row["policy"], int(row["width_px"]))] = (
            line,
            float(row["mean_bits"]),
        )
    checked = 0
    for (font, size), item in bank.items():
        for width in (64, 96, 128, 160, 192, 256, 0):
            policy = "start-aligned" if width else "fixed-field"
            key = (font, size, policy, width)
            require(key in archived, f"Archived tail row missing for {key}")
            if width:
                keys = P.class_index(item["right"], item["x_l"], width)
            else:
                keys = np.ones(len(prior), dtype=np.int64)
            bits, _hits = P.class_attack(prior, keys)
            got = float(prior @ bits)
            line, expect = archived[key]
            require(abs(got - expect) < 1e-9, f"Class entropy mismatch at tail_summary.csv:{line}")
            checked += 1
    print(f"Archived class check passed for {checked} font-size-width cells", flush=True)


def horizontal_feasible(cell: E.Cell, x0: int, x1: int, grid: int) -> np.ndarray:
    """Horizontal half of e1lib.Cell.feasible for attacker A2 at tolerance 0.

    Pen x is unknown. Top and bottom are not tested: the real baseline is not
    observed, and the requested attacker keeps candidates by length from width.
    """
    lower = np.maximum(x0 - cell.Lhi, x1 - grid + 1 - cell.Rhi)
    upper = np.minimum(x0 + grid - 1 - cell.Llo, x1 - cell.Rlo)
    return lower <= upper


def self_check(dictionary, bank) -> None:
    item = bank[("DejaVuSans", 16)]
    bounds = item["bounds"]
    truth = 0
    pen = 100
    left, right = int(bounds[truth, 0]), int(bounds[truth, 2])
    tight0 = pen + left - E.PAD
    tight1 = pen + right + E.PAD
    for grid in (1, 16, 64):
        x0, x1 = E.snap(tight0, tight1, grid)
        feasible = horizontal_feasible(item["cell"], x0, x1, grid)
        require(bool(feasible[truth]), f"Width self-check failed for grid {grid}")
    sample = {"x0": 10, "y0": 20, "x1": 30, "y1": 40, "line_top": 0, "line_bottom": 0}
    require(released_box(sample, None, "exact", 0) == (9, 19, 31, 41), "Exact box swapped a vertical edge into the width")
    require(released_box(sample, None, "grid-16", 0) == (0, 16, 32, 48), "16 px grid did not snap the horizontal edges")
    exact = released_box(sample, None, "exact", 0)
    require(
        bool(horizontal_feasible(item["cell"], exact[0], exact[2], 1).shape[0] == 50000),
        "Feasible mask is not indexed by the horizontal edges",
    )
    print("Width self-check passed", flush=True)


def map_font(name: str) -> str | None:
    if not name:
        return None
    base = name.split("+")[-1]
    key = re.sub(r"[^a-z]", "", base.casefold())
    for stem, study in FONT_STEMS:
        if key.startswith(stem):
            return study
    return None


def alpha_tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text or "").replace("\u00ad", "")
    return ALPHA.findall(normalized)


def line_bounds(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int]]:
    """Cluster boxes into text lines by vertical overlap, then expand by 1 px."""
    parent = list(range(len(boxes)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left, right = find(left), find(right)
        if left != right:
            parent[right] = left

    for i, box in enumerate(boxes):
        height = box[3] - box[1]
        for j in range(i):
            other = boxes[j]
            other_height = other[3] - other[1]
            overlap = min(box[3], other[3]) - max(box[1], other[1])
            if overlap > 0 and overlap * 2 >= min(height, other_height):
                union(i, j)
    groups = defaultdict(list)
    for index in range(len(boxes)):
        groups[find(index)].append(index)
    assigned = [(0, 0)] * len(boxes)
    for members in groups.values():
        top = min(boxes[index][1] for index in members) - E.PAD
        bottom = max(boxes[index][3] for index in members) + E.PAD
        for index in members:
            assigned[index] = (top, bottom)
    return assigned


def page_rank(record: dict) -> tuple:
    """Prefer precedence 0, then the smaller precedence, id, and split name."""
    return (
        record["precedence"] != 0,
        record["precedence"],
        record["coco_id"],
        record["source_split"],
    )


def sample_doclaynet() -> tuple[list[dict], dict]:
    pages = {}
    infos = {}
    for split in ("train", "val", "test"):
        path = COCO_DIR / f"{split}.json"
        require(path.is_file(), f"COCO split missing: {path}")
        print(f"Reading DocLayNet COCO {split}", flush=True)
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        infos[split] = payload.get("info", {})
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
            if current is None or page_rank(record) < page_rank(current):
                pages[page_id] = record
        del payload
        gc.collect()
    unique = list(pages.values())
    require(all(page["doc_category"] for page in unique), "A COCO page has no doc_category")
    grouped = defaultdict(list)
    for page in unique:
        grouped[page["doc_category"]].append(page)
    categories = sorted(grouped)
    for category in categories:
        grouped[category].sort(key=lambda page: page["page_id"])
    total = sum(len(grouped[category]) for category in categories)
    require(total >= PAGE_N, f"Only {total} unique DocLayNet pages are available")
    raw = {category: PAGE_N * len(grouped[category]) / total for category in categories}
    quota = {category: math.floor(raw[category]) for category in categories}
    remainder = PAGE_N - sum(quota.values())
    ranked = sorted(categories, key=lambda category: (-(raw[category] - quota[category]), category))
    for category in ranked[:remainder]:
        quota[category] += 1
    rng = np.random.default_rng(PAGE_SEED)
    selected = []
    for category in categories:
        pool = grouped[category]
        take = quota[category]
        require(0 < take <= len(pool), f"Bad quota for {category}: {take} of {len(pool)}")
        picked = np.sort(rng.choice(len(pool), size=take, replace=False))
        selected.extend(pool[int(index)] for index in picked)
    require(len(selected) == PAGE_N and len({page["page_id"] for page in selected}) == PAGE_N, "Page sample is not 2,000 unique pages")
    meta = {
        "generator": "numpy.random.Generator",
        "seed": PAGE_SEED,
        "numpy": np.__version__,
        "allocation": "proportional stratified, largest remainder, ties by category name",
        "unique_pages": total,
        "quotas": quota,
        "coco_info": infos,
        "coco_sha256": {name: sha256_file(COCO_DIR / name) for name in ("train.json", "val.json", "test.json")},
    }
    print(f"Sampled {len(selected)} DocLayNet pages", flush=True)
    return selected, meta


def use_local_zip_cache() -> None:
    cache = DATA / "doclaynet" / "zip-cache"
    cache.mkdir(parents=True, exist_ok=True)
    source = ROOT / "research" / "datasets" / "doclaynet" / "cache" / "extra-central-directory.bin"
    target = cache / "extra-central-directory.bin"
    if source.is_file() and not target.is_file():
        target.write_bytes(source.read_bytes())
    D.CACHE = cache


def archive_size(url: str) -> int:
    headers = D.head_metadata(url)
    return int(headers["content-length"])


def download_cells(pages: list[dict]) -> dict:
    use_local_zip_cache()
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    size = archive_size(D.EXTRA_URL)
    headers = D.head_metadata(D.EXTRA_URL)
    entries = D.load_central_directory(D.EXTRA_URL, size, "extra-central-directory.bin")
    by_name = {}
    for entry in entries:
        by_name.setdefault(Path(entry.name).name, []).append(entry)
    missing = []
    jobs = []
    for page in pages:
        member_name = page["page_id"] + ".json"
        chosen = D.choose_member(by_name.get(member_name, []), "JSON")
        if chosen is None:
            missing.append(page["page_id"])
            continue
        jobs.append((page, chosen))

    def fetch(job):
        page, entry = job
        dest = JSON_DIR / f"{page['page_id']}.json"
        D.extract_member(D.EXTRA_URL, entry, dest)
        return page["page_id"], sha256_file(dest), dest.stat().st_size

    hashes = {}
    failures = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(fetch, job): job[0]["page_id"] for job in jobs}
        done = 0
        for future in as_completed(futures):
            page_id = futures[future]
            done += 1
            try:
                fetched_id, digest, nbytes = future.result()
                hashes[fetched_id] = {"sha256": digest, "bytes": nbytes}
            except (SystemExit, Exception) as exc:  # noqa: BLE001 - one bad member must not abort the sample
                failures.append({"page_id": page_id, "error": str(exc)})
            if done % 100 == 0 or done == len(futures):
                print(f"DocLayNet JSON {done}/{len(futures)}", flush=True)
    return {
        "extra_url": D.EXTRA_URL,
        "extra_content_length": size,
        "extra_etag": headers.get("etag", ""),
        "extra_last_modified": headers.get("last-modified", ""),
        "json_members": len(jobs),
        "missing_members": missing,
        "failures": failures,
        "sha256": hashes,
    }


def pixel_box(bbox: list) -> tuple[int, int, int, int] | None:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None
    try:
        x, y, width, height = (float(value) for value in bbox)
    except (TypeError, ValueError):
        return None
    x0, y0 = math.floor(x), math.floor(y)
    x1, y1 = math.ceil(x + width), math.ceil(y + height)
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


def tokens_from_doclaynet(pages: list[dict], dictionary) -> tuple[list[dict], dict]:
    index = dictionary["index"]
    tokens = []
    stats = Counterish()
    font_sizes = defaultdict(int)
    outside = 0
    cells = 0
    for page in pages:
        path = JSON_DIR / f"{page['page_id']}.json"
        if not path.is_file():
            stats.add("pages_without_json")
            continue
        document = json.loads(path.read_text())
        metadata = document.get("metadata", {})
        require(metadata.get("page_hash") == page["page_id"], f"JSON page hash mismatch: {page['page_id']}")
        raw_cells = document.get("cells", [])
        boxes = []
        kept = []
        for cell in raw_cells:
            cells += 1
            box = pixel_box(cell.get("bbox") or [])
            if box is None:
                stats.add("bad_bbox")
                continue
            if box[0] < -2 or box[1] < -2 or box[2] > page["width"] + 2 or box[3] > page["height"] + 2:
                outside += 1
            words = alpha_tokens(cell.get("text", ""))
            font = (cell.get("font") or {}).get("name", "")
            font_sizes[str((cell.get("font") or {}).get("size"))] += 1
            boxes.append(box)
            kept.append((words, font, cell.get("text", "")))
        if not boxes:
            continue
        lines = line_bounds(boxes)
        for (words, font, original), box, line in zip(kept, boxes, lines):
            stats.add("cells_with_box")
            if len(words) != 1:
                stats.add("multi_or_empty")
                continue
            stats.add("single_token_cells")
            truth = index.get(words[0].casefold())
            if truth is None:
                continue
            tokens.append({
                "dataset": "DocLayNet",
                "page_id": page["page_id"],
                "token": dictionary["full"]["strings"][truth],
                "original": original,
                "truth": truth,
                "x0": box[0],
                "y0": box[1],
                "x1": box[2],
                "y1": box[3],
                "line_top": line[0],
                "line_bottom": line[1],
                "font_name": font,
                "mapped_font": map_font(font) or "",
                "list": "full",
            })
    stats_out = stats.as_dict()
    stats_out.update({
        "cells": cells,
        "cells_outside_page": outside,
        "font_size_values": dict(font_sizes),
        "qualifying_tokens": len(tokens),
        "qualifying_pages": len({token["page_id"] for token in tokens}),
        "mapped_font_tokens": sum(1 for token in tokens if token["mapped_font"]),
    })
    if cells and outside / cells > 0.05:
        raise SystemExit(
            "More than 5% of DocLayNet cell boxes fall outside the COCO page. "
            "The pixel-coordinate reading is not safe to continue."
        )
    print(
        f"DocLayNet surname tokens {stats_out['qualifying_tokens']} "
        f"on {stats_out['qualifying_pages']} pages",
        flush=True,
    )
    return tokens, stats_out


class Counterish:
    def __init__(self):
        self.values = defaultdict(int)

    def add(self, key: str) -> None:
        self.values[key] += 1

    def as_dict(self) -> dict:
        return dict(self.values)


def prepare_funsd() -> dict:
    FUNSD_ZIP.parent.mkdir(parents=True, exist_ok=True)
    if not FUNSD_ZIP.is_file():
        print("Downloading FUNSD", flush=True)
        partial = FUNSD_ZIP.with_suffix(".zip.partial")
        result = D.run_curl([
            "curl", "-L", "--fail", "--retry", "5", "--retry-all-errors",
            "-o", str(partial), FUNSD_URL,
        ])
        if result.returncode != 0:
            raise SystemExit(result.stderr)
        partial.replace(FUNSD_ZIP)
    digest = sha256_file(FUNSD_ZIP)
    with zipfile.ZipFile(FUNSD_ZIP) as archive:
        names = archive.namelist()
        extracted = FUNSD_ROOT.exists() and any(FUNSD_ROOT.rglob("testing_data"))
        if not extracted:
            FUNSD_ROOT.mkdir(parents=True, exist_ok=True)
            archive.extractall(FUNSD_ROOT)
    return {"sha256": digest, "url": FUNSD_URL, "members": len(names)}


def funsd_split_dir(name: str) -> Path:
    matches = [
        path for path in FUNSD_ROOT.rglob(name)
        if path.is_dir() and "__MACOSX" not in path.parts and (path / "annotations").is_dir()
    ]
    require(len(matches) == 1, f"FUNSD {name} directory count is {len(matches)}: {matches}")
    return matches[0]


def box_convention(split_dir: Path) -> dict:
    """Use the annotated integers as half-open unless a zero-area box shows they are inclusive."""
    from PIL import Image

    forms = 0
    words = 0
    zero_area = 0
    outside = 0
    for annotation_path in sorted((split_dir / "annotations").glob("*.json")):
        forms += 1
        image_path = split_dir / "images" / f"{annotation_path.stem}.png"
        with Image.open(image_path) as image:
            width, height = image.size
        payload = json.loads(annotation_path.read_text())
        for field in payload["form"]:
            for word in field.get("words", []):
                x0, y0, x1, y1 = (int(value) for value in word["box"])
                words += 1
                if x1 <= x0 or y1 <= y0:
                    zero_area += 1
                if x0 < 0 or y0 < 0 or x1 > width or y1 > height:
                    outside += 1
    if outside:
        raise SystemExit("A FUNSD word box lies outside its image; coordinate reading stopped")
    add_one = zero_area > 0
    convention = (
        "annotated corners are inclusive; x1 and y1 were increased by 1"
        if add_one else
        "annotated integers are used as half-open edges; no zero-area word forced an inclusive reading"
    )
    return {"convention": convention, "add_one": add_one, "forms": forms, "words": words, "zero_area": zero_area}


def tokens_from_funsd(dictionary) -> tuple[list[dict], dict]:
    info = prepare_funsd()
    train = funsd_split_dir("training_data")
    test = funsd_split_dir("testing_data")
    counts = {
        "training_forms": len(list((train / "annotations").glob("*.json"))),
        "testing_forms": len(list((test / "annotations").glob("*.json"))),
        "validation_dirs": [
            str(path) for path in FUNSD_ROOT.rglob("*")
            if path.is_dir() and "__MACOSX" not in path.parts and path.name.casefold() in {"val", "valid", "validation", "validation_data"}
        ],
    }
    require(counts["training_forms"] == 149 and counts["testing_forms"] == 50, "FUNSD split counts are not the official 149/50")
    convention = box_convention(test)
    add_one = 1 if convention["add_one"] else 0
    labels = defaultdict(int)
    answer_words = 0
    answer_fields = 0
    tokens = []
    index = dictionary["index"]
    for path in sorted((test / "annotations").glob("*.json")):
        payload = json.loads(path.read_text())
        words = []
        for field in payload["form"]:
            labels[field.get("label", "")] += 1
            for word in field.get("words", []):
                x0, y0, x1, y1 = (int(value) for value in word["box"])
                x1 += add_one
                y1 += add_one
                if x1 <= x0 or y1 <= y0:
                    continue
                record = {
                    "box": (x0, y0, x1, y1),
                    "text": word.get("text", ""),
                    "label": field.get("label", ""),
                    "field_id": field.get("id"),
                }
                words.append(record)
        lines = line_bounds([word["box"] for word in words]) if words else []
        for word, line in zip(words, lines):
            if word["label"] != "answer":
                continue
            answer_words += 1
            parts = alpha_tokens(word["text"])
            if len(parts) != 1:
                continue
            truth = index.get(parts[0].casefold())
            if truth is None:
                continue
            tokens.append({
                "dataset": "FUNSD",
                "page_id": path.stem,
                "token": dictionary["full"]["strings"][truth],
                "original": word["text"],
                "truth": truth,
                "x0": word["box"][0],
                "y0": word["box"][1],
                "x1": word["box"][2],
                "y1": word["box"][3],
                "line_top": line[0],
                "line_bottom": line[1],
                "font_name": "",
                "mapped_font": "",
                "list": "full",
                "field_id": word["field_id"],
            })
        answer_fields += sum(1 for field in payload["form"] if field.get("label") == "answer")
    stats = {
        **counts,
        **info,
        **convention,
        "labels": dict(labels),
        "answer_fields": answer_fields,
        "answer_words": answer_words,
        "qualifying_tokens": len(tokens),
        "qualifying_forms": len({token["page_id"] for token in tokens}),
        "hidden_value_rule": "answer-field words whose case-normalised text is one alphabetic token in the 50,000-surname list",
    }
    print(
        f"FUNSD test forms {counts['testing_forms']}, answer fields {answer_fields}, "
        f"answer words {answer_words}, surname tokens {len(tokens)}",
        flush=True,
    )
    return tokens, stats


def released_box(token: dict, item: dict | None, policy: str, width: int) -> tuple[int, int, int, int]:
    """Return (x0, y0, x1, y1). e1lib.snapped returns (X0, X1, Y0, Y1), so it is not used here."""
    x0, y0, x1, y1 = token["x0"] - E.PAD, token["y0"] - E.PAD, token["x1"] + E.PAD, token["y1"] + E.PAD
    if policy in {"exact", "grid-16", "grid-64"}:
        grid = {"exact": 1, "grid-16": 16, "grid-64": 64}[policy]
        left, right = E.snap(x0, x1, grid)
        top, bottom = E.snap(y0, y1, grid)
        return left, top, right, bottom
    require(item is not None, "Padding and field boxes need list geometry")
    anchor = token["x0"] + item["x_l"]
    top, bottom = token["line_top"], token["line_bottom"]
    if policy == "field":
        field_width = int((item["right"] - item["x_l"]).max())
        return anchor, top, anchor + field_width, bottom
    span = (token["x1"] - token["x0"] + E.PAD) - item["x_l"]
    padded = int(P.ceil_multiple(np.array([span]), width)[0])
    return anchor, top, anchor + padded, bottom


def feasible_for(token: dict, bank: dict, dictionary, policy: str, size: int, fonts: tuple[str, ...]) -> np.ndarray:
    if policy in {"nobox", "field-1000", "field-50000"}:
        width = 1000 if policy == "field-1000" else len(dictionary["full"]["p"])
        return np.ones(width, dtype=bool)
    if policy in {"exact", "grid-16", "grid-64"}:
        grid = {"exact": 1, "grid-16": 16, "grid-64": 64}[policy]
        box = released_box(token, None, policy, 0)
        mask = np.zeros(len(dictionary["full"]["p"]), dtype=bool)
        for font in fonts:
            mask |= horizontal_feasible(bank[(font, size)]["cell"], box[0], box[2], grid)
        return mask
    width = PAD_C if policy == "start-aligned-128" else ZERO_LEAK_C[size]
    mask = np.zeros(len(dictionary["full"]["p"]), dtype=bool)
    measured = token["x1"] - token["x0"] + E.PAD
    for font in fonts:
        item = bank[(font, size)]
        observed = int(P.class_index(np.array([measured]), item["x_l"], width)[0])
        classes = P.class_index(item["right"], item["x_l"], width)
        mask |= classes == observed
    return mask


def score_mask(dictionary, mask: np.ndarray, truth: int, short: bool) -> dict:
    if short:
        prior = dictionary["short"]["p"]
        logp = dictionary["logp_short"]
        lengths = dictionary["lengths_short"]
        bundle = dictionary["short"]
        h0 = dictionary["h0_short"]
    else:
        prior = dictionary["full"]["p"]
        logp = dictionary["logp"]
        lengths = dictionary["lengths"]
        bundle = dictionary["full"]
        h0 = dictionary["h0"]
    count = int(mask.sum())
    scored = E.metrics(bundle, mask, truth, int(lengths[truth]), logp)
    rank = ""
    if mask[truth]:
        mass = prior[mask]
        greater = int(np.sum(mass > prior[truth]))
        equal = int(np.sum(mass == prior[truth]))
        rank = greater + (equal + 1) / 2
    return {
        "candidate_count": count,
        "rank": rank,
        "bits": h0 - scored["resid_bits"],
        "hit1": scored["hit1"],
        "hit10": scored["hit10"],
        "truth_in": scored["truth_in"],
    }


def iter_jobs(token: dict):
    fonts = tuple(E.FONTS)
    yield "bank", "", fonts
    if token.get("mapped_font"):
        yield "matched", token["mapped_font"], (token["mapped_font"],)


def score_tokens(tokens: list[dict], dictionary, bank: dict) -> list[dict]:
    rows = []
    total = len(tokens)
    for number, token in enumerate(tokens, start=1):
        for mode, font_name, fonts in iter_jobs(token):
            for policy in ("exact", "grid-16", "grid-64", "start-aligned-128", "start-aligned-zero-leak"):
                for size in SIZES:
                    if policy == "start-aligned-zero-leak" and size == 16 and PAD_C == ZERO_LEAK_C[16]:
                        pass
                    mask = feasible_for(token, bank, dictionary, policy, size, fonts)
                    scored = score_mask(dictionary, mask, token["truth"], short=False)
                    item = bank[(fonts[0], size)]
                    if policy in {"exact", "grid-16", "grid-64"}:
                        box = released_box(token, None, policy, 0)
                    elif policy == "start-aligned-128":
                        box = released_box(token, item, "start-aligned-128", PAD_C)
                    else:
                        box = released_box(token, item, "start-aligned-zero-leak", ZERO_LEAK_C[size])
                    rows.append(row_from(token, policy, size, mode, font_name, box, scored))
            for policy, short in (
                ("field-1000", True),
                ("field-50000", False),
                ("nobox", False),
                ("nobox-1000", True),
            ):
                if short and token["truth"] >= 1000:
                    continue
                if short:
                    mask = np.ones(1000, dtype=bool)
                else:
                    mask = np.ones(len(dictionary["full"]["p"]), dtype=bool)
                scored = score_mask(dictionary, mask, token["truth"], short=short)
                if policy.startswith("nobox"):
                    box = ("", "", "", "")
                else:
                    limit = 1000 if short else 50000
                    item = dict(bank[(fonts[0], 16)])
                    item["right"] = item["right"][:limit]
                    box = released_box(token, item, "field", 0)
                rows.append(row_from(token, policy, "all", mode, font_name, box, scored))
        if number % 250 == 0 or number == total:
            print(f"Scored {number}/{total} {token['dataset']}", flush=True)
    return rows


def row_from(token, policy, size, mode, font_name, box, scored) -> dict:
    return {
        "dataset": token["dataset"],
        "page_id": token["page_id"],
        "token": token["token"],
        "policy": policy,
        "box": ",".join(str(value) for value in box),
        "candidate_count": scored["candidate_count"],
        "rank": scored["rank"],
        "bits": fmt(scored["bits"]),
        "size_px": size,
        "font_mode": font_name or mode,
        "token_id": token["token_id"],
        "hit1": fmt(scored["hit1"]),
        "hit10": fmt(scored["hit10"]),
        "truth_in": scored["truth_in"],
    }


def documents_for(rows: list[dict], dataset: str, policy: str, mode: str) -> dict[str, dict[str, list]]:
    chosen = [row for row in rows if row["dataset"] == dataset and row["policy"] == policy]
    if mode == "bank":
        chosen = [row for row in chosen if row["font_mode"] == "bank"]
    else:
        chosen = [row for row in chosen if row["font_mode"] != "bank"]
    grouped = defaultdict(list)
    for row in chosen:
        grouped[row["token_id"]].append(row)
    docs = defaultdict(lambda: {key: [] for key in ("bits", "hit1", "hit10", "truth", "candidates")})
    for items in grouped.values():
        page = items[0]["page_id"]
        docs[page]["bits"].append(float(np.mean([float(item["bits"]) for item in items])))
        docs[page]["hit1"].append(float(np.mean([float(item["hit1"]) for item in items])))
        docs[page]["hit10"].append(float(np.mean([float(item["hit10"]) for item in items])))
        docs[page]["truth"].append(float(np.mean([float(item["truth_in"]) for item in items])))
        docs[page]["candidates"].append(float(np.mean([float(item["candidate_count"]) for item in items])))
    return docs


def cluster_interval(docs: dict, key: str) -> tuple[float, float, float, int, int]:
    pages = sorted(docs)
    values = [np.asarray(docs[page][key], dtype=np.float64) for page in pages]
    sums = np.array([item.sum() for item in values])
    counts = np.array([item.size for item in values])
    point = float(sums.sum() / counts.sum())
    rng = np.random.default_rng(BOOT_SEED)
    draws = rng.integers(0, len(pages), size=(BOOT_DRAWS, len(pages)))
    means = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    low, high = (float(item) for item in np.quantile(means, [0.025, 0.975]))
    return point, low, high, int(counts.sum()), len(pages)


def summarise_all(rows: list[dict]) -> list[dict]:
    datasets = []
    for row in rows:
        if row["dataset"] not in datasets:
            datasets.append(row["dataset"])
    policies = []
    for row in rows:
        if row["policy"] not in policies:
            policies.append(row["policy"])
    summary = []
    for dataset in datasets:
        for policy in policies:
            for mode in ("bank", "matched"):
                docs = documents_for(rows, dataset, policy, mode)
                if not docs:
                    continue
                bits, bits_lo, bits_hi, n_tokens, n_docs = cluster_interval(docs, "bits")
                hit1, hit1_lo, hit1_hi, _, _ = cluster_interval(docs, "hit1")
                hit10, hit10_lo, hit10_hi, _, _ = cluster_interval(docs, "hit10")
                truth, _, _, _, _ = cluster_interval(docs, "truth")
                candidates, _, _, _, _ = cluster_interval(docs, "candidates")
                summary.append({
                    "dataset": dataset,
                    "policy": policy,
                    "font_mode": mode,
                    "n_tokens": n_tokens,
                    "n_documents": n_docs,
                    "bits": fmt(bits),
                    "bits_lo": fmt(bits_lo),
                    "bits_hi": fmt(bits_hi),
                    "top1": fmt(hit1),
                    "top1_lo": fmt(hit1_lo),
                    "top1_hi": fmt(hit1_hi),
                    "top10": fmt(hit10),
                    "top10_lo": fmt(hit10_lo),
                    "top10_hi": fmt(hit10_hi),
                    "truth_in": fmt(truth),
                    "mean_candidates": fmt(candidates),
                })
    return summary


def find_row(path: Path, predicate) -> tuple[int, dict]:
    matches = [(line, row) for line, row in read_rows(path) if predicate(row)]
    require(len(matches) == 1, f"Expected one archived row in {path}, found {len(matches)}")
    return matches[0]


def percent_from_fraction(text: str) -> str:
    rendered = format(Decimal(text) * Decimal(100), "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def synthetic_sources() -> list[dict]:
    pooled = E1 / "pooled" / "pooled.csv"
    knowledge_matched = E1 / "data" / "knowledge_matched" / "summary.csv"
    control = E1 / "data" / "knowledge_matched" / "paper_control.csv"
    baseline = E1 / "data" / "baselines_nobox.csv"
    analytic = E1 / "data" / "per_person" / "no_box.csv"
    sources = []
    for policy, label in (("exact", "exact"), ("square-16", "16-px grid"), ("square-64", "64-px grid")):
        line, row = find_row(
            pooled,
            lambda item, policy=policy: item["list"] == "surnames" and item["size_px"] == "all"
            and item["model"] == "LAYOUT-BOX" and item["attacker"] == "A1" and item["policy"] == policy,
        )
        base_line, base = find_row(baseline, lambda item: item["dict"] == "surnames")
        sources.append({
            "policy_label": label,
            "policy_key": {"exact": "exact", "square-16": "grid-16", "square-64": "grid-64"}[policy],
            "n": row["n"],
            "bits": row["bits"],
            "bits_lo": row["bits_ci_low"],
            "bits_hi": row["bits_ci_high"],
            "top1": percent_from_fraction(row["top1"]),
            "top10": percent_from_fraction(row["top10"]),
            "nobox_top10": percent_from_fraction(base["top10"]),
            "source": f"research/e1/pooled/pooled.csv:{line}; no-box research/e1/data/baselines_nobox.csv:{base_line}",
            "list": "50000",
        })
    line, row = find_row(
        knowledge_matched,
        lambda item: item["size_px"] == "all" and item["policy"] == "start-aligned" and item["width_px"] == "128",
    )
    field_line, field = find_row(
        knowledge_matched,
        lambda item: item["size_px"] == "all" and item["policy"] == "field" and item["width_px"] == "0",
    )
    control_line, control_row = find_row(control, lambda item: item["size_px"] == "all")
    analytic_line, analytic_row = find_row(analytic, lambda item: True)
    require(field["bits"] == "0.0", "knowledge-matched field bits are not zero; the no-box reading of that top-10 is not valid")
    sources.append({
        "policy_label": "start-aligned padding",
        "policy_key": "start-aligned-128",
        "n": row["n"],
        "bits": row["bits"],
        "bits_lo": row["ci_low"],
        "bits_hi": row["ci_high"],
        "top1": "not in source",
        "top10": row["top10_pct"],
        "nobox_top10": field["top10_pct"],
        "source": (
            f"research/e1/data/knowledge_matched/summary.csv:{line}; no-box is the field row "
            f"research/e1/data/knowledge_matched/summary.csv:{field_line} because its bits are 0; "
            f"50,000-surname A1 bits are research/e1/data/knowledge_matched/paper_control.csv:{control_line} "
            f"bits={control_row['bits']}"
        ),
        "list": "1000",
        "paper_control_bits": control_row["bits"],
        "analytic_top10": analytic_row["expected_top10"],
        "analytic_line": analytic_line,
    })
    sources.append({
        "policy_label": "field box",
        "policy_key": "field-1000",
        "n": field["n"],
        "bits": field["bits"],
        "bits_lo": field["ci_low"],
        "bits_hi": field["ci_high"],
        "top1": "not in source",
        "top10": field["top10_pct"],
        "nobox_top10": field["top10_pct"],
        "source": f"research/e1/data/knowledge_matched/summary.csv:{field_line}; bits are 0 so top-10 is the prior top-10",
        "list": "1000",
    })
    return sources


def lookup(summary: list[dict], dataset: str, policy: str, mode: str = "bank") -> dict | None:
    for row in summary:
        if row["dataset"] == dataset and row["policy"] == policy and row["font_mode"] == mode:
            return row
    return None


def real_cells(summary: list[dict], dataset: str, policy: str) -> dict:
    row = lookup(summary, dataset, policy)
    if row is None:
        return {"n": "0", "bits": "undefined", "top1": "undefined", "top10": "undefined", "nobox": "undefined"}
    nobox_policy = "nobox-1000" if policy == "field-1000" else "nobox"
    base = lookup(summary, dataset, nobox_policy)
    return {
        "n": row["n_tokens"],
        "bits": f"{row['bits']} [{row['bits_lo']}, {row['bits_hi']}]",
        "top1": percent_from_fraction(row["top1"]),
        "top10": percent_from_fraction(row["top10"]),
        "nobox": "undefined" if base is None else percent_from_fraction(base["top10"]),
    }


def write_results(summary: list[dict], sources: list[dict]) -> None:
    lines = [
        "Dataset | Policy | n | Bits leaked [95% CI] | Top-1 % | Top-10 % | No-box top-10 % | Synthetic value (A1, matched; source CSV)",
        "--- | --- | --- | --- | --- | --- | --- | ---",
    ]
    real_names = (("DocLayNet", "DocLayNet as-is"), ("FUNSD", "FUNSD test"))
    for source in sources:
        lines.append(
            " | ".join([
                "synthetic",
                source["policy_label"],
                str(source["n"]),
                f"{source['bits']} [{source['bits_lo']}, {source['bits_hi']}]",
                str(source["top1"]),
                str(source["top10"]),
                str(source["nobox_top10"]),
                f"{source['bits']} ({source['source']})",
            ])
        )
        for dataset, label in real_names:
            cells = real_cells(summary, dataset, source["policy_key"])
            lines.append(
                " | ".join([
                    label,
                    source["policy_label"],
                    str(cells["n"]),
                    str(cells["bits"]),
                    str(cells["top1"]),
                    str(cells["top10"]),
                    str(cells["nobox"]),
                    f"{source['bits']} ({source['source']})",
                ])
            )
    text = [
        "# Real-page leakage compared with the archived synthetic runs",
        "",
        "Real rows use the six-font bank. Each token is scored at 12, 16 and 24 px and those three values are averaged before the document-clustered bootstrap. The synthetic cells are copied from the archived CSVs named in the last column. Percentages converted from an archived fraction use exact decimal multiplication. Computed real values are the summary.csv strings times 100 where the column is a percentage.",
        "",
        "\n".join(lines),
        "",
        "summary.csv has the per-policy full precision, the matched-font rows, the 50,000-surname field, the no-box rows, and start-aligned padding at the size-specific widths 96, 128 and 192 px.",
        "",
    ]
    (HERE / "RESULTS.md").write_text("\n".join(text))


def write_deviations(config: dict) -> None:
    doc = config["doclaynet_tokens"]
    funsd = config["funsd"]
    paragraphs = [
        "# Deviations from the synthetic leakage setup",
        "",
        "The evaluation imports `research/e1/policies.py` and `research/e1/e1lib.py` and does not modify them. Where a synthetic setting could not be kept, that part was stopped or the difference is stated here. No archived number was retyped by hand; synthetic figures in RESULTS.md are read from the cited CSV rows.",
        "",
        "## Renderer and geometry",
        "",
        f"This machine has Pillow {config['pillow']} and RAQM {config['raqm']}. The study renderer is Pillow 12.3.0 with RAQM 0.10.5, HarfBuzz 14.2.1 and FreeType 2.14.3 (`research/e1/data/knowledge_matched/run.json`). New glyph renders, including the jpeg75 and scan edge-tolerance calibration in `e1_run.py`, were not run. Candidate layout arrays are the retained files in `out/retained-geom`. Each array's protocol-4 pickle digest matches `research/e1/data/per_person/geometry_receipts.csv`, and the width-class entropy matches `research/e1/data/per_person/tail_summary.csv` to 1e-9.",
        "",
        "## Edge tolerance",
        "",
        "The degraded-image tolerances are the per-edge 0.5 and 99.5 percentiles computed inside `e1_run.py`. Those tuples are not stored in the archived CSVs. They were not recomputed. The scored attacker uses tolerance (0, 0) on every edge, which is the clean surname model. This is not the jpeg75 calibration and not the scan calibration. A real box whose width differs by one pixel from every study font is rejected. An empty feasible set is handled by `e1lib.metrics`: hits become 0 and the residual entropy falls back to the prior, so bits leaked become 0.",
        "",
        "## Attacker",
        "",
        "The exact, 16 px and 64 px rows use the horizontal test from `e1lib.Cell.feasible` for attacker A2: pen x is unknown, and a candidate remains when its layout width is consistent with the snapped box. The vertical test was not applied because the page does not record the synthetic baseline. Keeping candidates by width only can add strings whose height would have failed the four-edge test, which lowers or holds the measured leakage relative to A1. The six-font bank keeps a candidate that passes in any one of the six fonts. The union is larger than a matched-font feasible set, so leakage is lower than the synthetic A1 cell for the true font. Each token is then averaged across 12, 16 and 24 px with equal weight. A page is not known to be set in one of those sizes. A size that does not match the page moves the true name out of its width class.",
        "",
        f"Matched-font scoring ran only when the cell's embedded name, after the subset prefix, starts with one of DejaVuSans, DejaVuSerif, LiberationSans, LiberationSerif, LiberationMono or NotoSans. DocLayNet mapped tokens: {doc.get('mapped_font_tokens', 0)} of {doc.get('qualifying_tokens', 0)}. The JSON font size values were {doc.get('font_size_values', {})}. They were not treated as 12, 16 or 24 px. FUNSD images are scans and have no embedded font name, so the matched-font arm was not run for FUNSD.",
        "",
        "## Anchor p and line bounds",
        "",
        "p is the token's integer left edge: for DocLayNet, the floor of the cell bbox origin; for FUNSD, the annotated x0 after the conversion recorded below. That edge is used as the pen. The token's layout left bearing is taken to be 0, so its layout right is the box width. x_L is the list value from `policies.prepare`, `min(layout left) - 1`, computed separately for each retained font and size. The padding class is `policies.class_index` of the measured padded width against that font's x_L. The bank unions the six fonts.",
        "",
        "Line bounds are the minimum top and maximum bottom of the token's text line, then expanded by 1 px, the same pad as `e1lib.PAD`. A line is a cluster of boxes whose vertical overlap is at least half the shorter height. DocLayNet clusters text cells. FUNSD clusters every word on the form, not only the answer. The synthetic line is the font ascent and descent inside `policies.prepare`, not this cluster. Sidebearings and a one-pixel difference move width classes. A one-word line makes the stored padding or field height equal the word height. The padding and field posteriors use the width class only, so that height is recorded in the box and does not filter candidates.",
        "",
        "## DocLayNet boxes and tokens",
        "",
        "Text-cell bboxes are floats in the COCO pixel frame. Coordinates exceed `original_height` and fit `coco_height`, so they were not scaled from PDF points. The integer box is floor of the origin and ceil of the far corner. Cells are lines. A cell with more than one alphabetic token was not split, because the file has no word box for those tokens. "
        f"Cells: {doc.get('cells', 0)}. Single-token cells: {doc.get('single_token_cells', 0)}. Surname tokens: {doc.get('qualifying_tokens', 0)} on {doc.get('qualifying_pages', 0)} pages. Cells outside the page by more than 2 px: {doc.get('cells_outside_page', 0)}. The core zip SHA-256 is in run_config.json. The extra zip was not stored whole; its content length and etag are in that file, and each extracted text-cell JSON has its own SHA-256 in results/doclaynet_json_sha256.csv. Missing JSON members: {config['doclaynet_download'].get('missing_members')}. Download failures: {config['doclaynet_download'].get('failures')}.",
        "",
        "Membership in the surname list does not mean the token is being used as a person's name. Common words that are also Census surnames qualify.",
        "",
        "## Lists",
        "",
        "Exact, grid and start-aligned scores use the 50,000-surname list and its Census-count prior. The field-box row uses the first 1,000 surnames, with the prior renormalised on those 1,000, and only tokens inside that head. The synthetic start-aligned and field rows in RESULTS.md come from the knowledge-matched 1,000-surname sweep. The archived 50,000-surname start-aligned bits are the paper_control value quoted in the source cell. Those top-10 rates are not on the same list. The 1,000-name prior top-10 is the knowledge-matched field row's top10_pct, because that row's bits are 0. The 50,000-name sampled no-box top-10 is the baselines_nobox.csv value. `research/e1/data/per_person/no_box.csv` has the analytic 50,000-name top-10 and is not mixed into the 50,000-name table cells.",
        "",
        f"The knowledge-matched summary has no top-1 column, so those synthetic top-1 cells say `not in source`.",
        "",
        "## FUNSD",
        "",
        f"The official zip has {funsd.get('training_forms')} training forms and {funsd.get('testing_forms')} testing forms. There is no validation directory ({funsd.get('validation_dirs')}). A 119-form split is not in the zip and was not used. The evaluated set is the test split. Answer fields: {funsd.get('answer_fields')}. Answer words: {funsd.get('answer_words')}. Surname tokens: {funsd.get('qualifying_tokens')} on {funsd.get('qualifying_forms')} forms. "
        + (
            "The 20,000-word list was not used because answer words in the surname list were found."
            if funsd.get("qualifying_tokens") else
            "No answer word is in the surname list. The 20,000-word arm was stopped: retained word-layout arrays are not in the geometry cache, and the study renderer is not available, so word widths were not substituted."
        ),
        "",
        f"Box convention: {funsd.get('convention')} Zero-area annotated words: {funsd.get('zero_area')}.",
        "",
        "## Bootstrap",
        "",
        f"Real intervals resample documents with replacement {BOOT_DRAWS} times using `numpy.random.Generator({BOOT_SEED})`, restarted for every metric, and take the 0.025 and 0.975 quantiles. The same seed makes the document draws match across metrics of one row. Page sampling uses `numpy.random.Generator({PAGE_SEED})`. Synthetic intervals are copied from their CSV columns and were not recomputed. knowledge-matched resampled target rows. `e1lib.boot_ci` uses 2,000 unclustered resamples. The real intervals are a different procedure from those files.",
        "",
        "## What was not substituted",
        "",
        "No nearest study-font size was assigned. No jpeg or scan tolerance was invented. No Arial or Times name was mapped onto Liberation. Multi-token DocLayNet cells were not given estimated word boxes. The manuscript was not edited.",
        "",
    ]
    (HERE / "DEVIATIONS.md").write_text("\n".join(paragraphs))


def assign_ids(tokens: list[dict], prefix: str) -> None:
    for number, token in enumerate(tokens):
        token["token_id"] = f"{prefix}-{number}"


def core_zip_record() -> dict:
    record = {"path": str(CORE_ZIP), "exists": CORE_ZIP.is_file()}
    if not CORE_ZIP.is_file():
        return record
    record["bytes"] = CORE_ZIP.stat().st_size
    sidecar = DATA / "doclaynet" / "core_zip.sha256"
    if sidecar.is_file():
        record["sha256"] = sidecar.read_text().split()[0]
        return record
    print("Hashing DocLayNet core zip", flush=True)
    record["sha256"] = sha256_file(CORE_ZIP)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(record["sha256"] + "\n")
    return record


def main() -> None:
    import PIL

    RESULTS.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    print("Loading the surname list and retained geometry", flush=True)
    dictionary = load_dictionary()
    bank = load_geometry(dictionary)
    self_check(dictionary, bank)
    pages, sample_meta = sample_doclaynet()
    write_csv(RESULTS / "doclaynet_page_ids.csv", pages)
    download = download_cells(pages)
    doc_tokens, doc_stats = tokens_from_doclaynet(pages, dictionary)
    funsd_tokens, funsd_stats = tokens_from_funsd(dictionary)
    assign_ids(doc_tokens, "doclaynet")
    assign_ids(funsd_tokens, "funsd")
    scored = []
    if doc_tokens:
        scored.extend(score_tokens(doc_tokens, dictionary, bank))
    if funsd_tokens:
        scored.extend(score_tokens(funsd_tokens, dictionary, bank))
    elif funsd_stats.get("qualifying_tokens") == 0:
        print("FUNSD surname tokens are 0; word-list scoring was not started", flush=True)
    write_csv(RESULTS / "per_token.csv", scored)
    summary = summarise_all(scored)
    write_csv(RESULTS / "summary.csv", summary)
    sources = synthetic_sources()
    write_results(summary, sources)
    config = {
        "seeds": {
            "doclaynet_pages": {"generator": "numpy.random.Generator", "seed": PAGE_SEED},
            "bootstrap": {
                "generator": "numpy.random.Generator",
                "seed": BOOT_SEED,
                "draws": BOOT_DRAWS,
                "quantile": [0.025, 0.975],
                "clustering": "document id, with replacement; generator restarted per metric",
            },
        },
        "numpy": np.__version__,
        "python": sys.version,
        "pillow": PIL.__version__,
        "raqm": bool(__import__("PIL").features.check("raqm")),
        "census_sha256": dictionary["census_sha256"],
        "prior_bits_50k": fmt(dictionary["h0"]),
        "prior_bits_archived": dictionary["prior_bits_archived"],
        "prior_bits_1000": fmt(dictionary["h0_short"]),
        "doclaynet_version": DOCLAYNET_VERSION,
        "doclaynet_core_zip": core_zip_record(),
        "doclaynet_sample": sample_meta,
        "doclaynet_download": {key: value for key, value in download.items() if key != "sha256"},
        "doclaynet_json_count": len(download.get("sha256", {})),
        "doclaynet_tokens": doc_stats,
        "funsd": funsd_stats,
        "geometry": "protocol-4 pickle digest matched geometry_receipts.csv for all 18 font-size files",
        "tolerance": "clean exact zero; degraded jpeg75 and scan calibration not run",
        "attacker": "six-font union of A2 horizontal feasibility at tolerance 0; padding uses class_index",
    }
    (RESULTS / "run_config.json").write_text(json.dumps(config, indent=2, default=str) + "\n")
    manifest = RESULTS / "doclaynet_json_sha256.csv"
    write_csv(manifest, [
        {"page_id": page_id, **info} for page_id, info in sorted(download.get("sha256", {}).items())
    ])
    write_deviations(config)
    print("Wrote RESULTS.md, DEVIATIONS.md and results/", flush=True)


if __name__ == "__main__":
    main()

