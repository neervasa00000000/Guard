"""Policy rectangles for the DocLayNet validation.

Page coordinates match the PNG: origin at the top left, y downward,
half-open integer edges. The 1 px expansion and the outward grid snap
are the functions in the existing Guard geometry module.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
POLICIES = ("exact", "square16", "square64", "width64", "start128", "field")
TEMPLATE_POLICIES = ("width64", "start128", "field")
SQUARE_POLICIES = {"square16": 16, "square64": 64}

REDACTOR_REQUIRES = {
    "exact": "glyph ink box",
    "square16": "glyph ink box and the page grid",
    "square64": "glyph ink box and the page grid",
    "width64": "shared template start x_L and the shared font line",
    "start128": "shared template start x_L and the shared font line",
    "field": "bounded candidate list, shared template start x_L, and the shared font line",
}

HOST_CATS = {1, 4, 8, 10, 11}
READABLE_CATS = {1, 2, 3, 4, 5, 6, 8, 9, 10, 11}
PICTURE = 7
CAT_NAME = {
    1: "Caption",
    2: "Footnote",
    3: "Formula",
    4: "List-item",
    5: "Page-footer",
    6: "Page-header",
    7: "Picture",
    8: "Section-header",
    9: "Table",
    10: "Text",
    11: "Title",
}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard_rw = _load("guard_rw_doclaynet", ROOT / "research" / "realworld_validation" / "src" / "guard_rw.py")
e1_policies = _load("e1_policies_doclaynet", ROOT / "research" / "e1" / "policies.py")


def clip_box(box, width, height):
    x0, y0, x1, y1 = [int(v) for v in box]
    return (
        int(min(max(x0, 0), width)),
        int(min(max(y0, 0), height)),
        int(min(max(x1, 0), width)),
        int(min(max(y1, 0), height)),
    )


def clip_edges(x0, y0, x1, y1, width, height):
    x0 = np.clip(np.rint(x0), 0, width).astype(np.int64)
    y0 = np.clip(np.rint(y0), 0, height).astype(np.int64)
    x1 = np.clip(np.rint(x1), 0, width).astype(np.int64)
    y1 = np.clip(np.rint(y1), 0, height).astype(np.int64)
    return x0, y0, x1, y1


def area(box):
    return max(0, int(box[2]) - int(box[0])) * max(0, int(box[3]) - int(box[1]))


def intersects(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def coco_box(x, y, w, h):
    return (int(np.floor(x)), int(np.floor(y)), int(np.ceil(x + w)), int(np.ceil(y + h)))


def expand(box, pad, width, height):
    return clip_box((box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad), width, height)


def contains(outer, inner):
    return outer[0] <= inner[0] and outer[1] <= inner[1] and outer[2] >= inner[2] and outer[3] >= inner[3]


def policy_edges(kind, left, top, right, bottom):
    """Unclipped policy edges for every candidate, using the shared list frame."""
    left = np.asarray(left, dtype=np.float64)
    top = np.asarray(top, dtype=np.float64)
    right = np.asarray(right, dtype=np.float64)
    bottom = np.asarray(bottom, dtype=np.float64)
    x_l, line_top, line_bottom = guard_rw.shared_frame(left, top, right, bottom)
    edges = guard_rw.candidate_boxes(kind, left, top, right, bottom, x_l, line_top, line_bottom)
    edges = tuple(np.rint(np.asarray(edge)).astype(np.int64) for edge in edges)
    return edges, int(round(x_l)), int(round(line_top)), int(round(line_bottom))


def observed_box(kind, left, top, right, bottom, index, page_w, page_h):
    edges, x_l, line_top, line_bottom = policy_edges(kind, left, top, right, bottom)
    raw = tuple(int(edge[index]) for edge in edges)
    clipped = clip_box(raw, page_w, page_h)
    return raw, clipped, x_l, line_top, line_bottom


def grid_aligned(box, grid, page_w, page_h):
    def ok(value, limit):
        return value == 0 or value == limit or value % grid == 0
    x0, y0, x1, y1 = [int(v) for v in box]
    return ok(x0, page_w) and ok(y0, page_h) and ok(x1, page_w) and ok(y1, page_h)


def ink_outside(ink, box):
    """How many True ink pixels lie outside a half-open box."""
    ys, xs = np.nonzero(ink)
    if len(xs) == 0:
        return 0
    x0, y0, x1, y1 = box
    inside = (xs >= x0) & (xs < x1) & (ys >= y0) & (ys < y1)
    return int((~inside).sum())


def luminance(rgb):
    rgb = np.asarray(rgb)
    return 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]


def first_text_band(dark_crop):
    """First line-like band in a host crop. Returns (start, end) or None."""
    if dark_crop.size == 0:
        return None
    row = dark_crop.mean(axis=1)
    start = None
    for index, value in enumerate(row):
        if value > 0.012:
            start = index
            break
    if start is None:
        return None
    end = start
    while end + 1 < len(row) and (end - start) < 36 and row[end + 1] > 0.008:
        end += 1
    if (end + 1 - start) < 6:
        return None
    return start, end + 1


def loss_for(dark, host_box, host_ann, clear, mask, regions, page_w, page_h):
    scope = np.zeros(dark.shape, dtype=bool)
    hx0, hy0, hx1, hy1 = expand(host_box, 12, page_w, page_h)
    scope[hy0:hy1, hx0:hx1] = True
    unrelated = 0
    for region in regions:
        if region["id"] == host_ann or region["cat"] not in READABLE_CATS:
            continue
        if not intersects(mask, region["box"]):
            continue
        unrelated += 1
        x0, y0, x1, y1 = clip_box(region["box"], page_w, page_h)
        scope[y0:y1, x0:x1] = True
    cx0, cy0, cx1, cy1 = clip_box(clear, page_w, page_h)
    cleared = np.zeros(dark.shape, dtype=bool)
    cleared[cy0:cy1, cx0:cx1] = True
    mx0, my0, mx1, my1 = clip_box(mask, page_w, page_h)
    covered = np.zeros(dark.shape, dtype=bool)
    covered[my0:my1, mx0:mx1] = True
    base = dark & scope & ~cleared
    hidden = int((base & covered).sum())
    base_n = int(base.sum())
    return {
        "neighbor_ink_px": hidden,
        "scope_ink_px": base_n,
        "fraction_ink_obscured": None if base_n == 0 else hidden / base_n,
        "unrelated_regions": unrelated,
        "unrelated_overlap": int(unrelated > 0),
    }


def word_boxes(line):
    """Split a line box across whitespace tokens in proportion to length."""
    text = str(line["text"])
    parts = text.split()
    if not parts:
        return []
    total = sum(len(part) for part in parts) + max(0, len(parts) - 1)
    if total <= 0 or line["w"] <= 0 or line["h"] <= 0:
        return []
    cursor = float(line["x"])
    gap = float(line["w"]) / total
    words = []
    for index, part in enumerate(parts):
        width = gap * len(part)
        words.append({
            "text": part,
            "box": (cursor, float(line["y"]), cursor + width, float(line["y"]) + float(line["h"])),
        })
        cursor += width
        if index + 1 < len(parts):
            cursor += gap
    return words


def ocr_neighbor_counts(lines, mask, clear):
    words = 0
    chars = 0
    for line in lines:
        for word in word_boxes(line):
            box = word["box"]
            if not intersects(mask, box):
                continue
            word_area = max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])
            if word_area <= 0:
                continue
            ix0 = max(box[0], clear[0])
            iy0 = max(box[1], clear[1])
            ix1 = min(box[2], clear[2])
            iy1 = min(box[3], clear[3])
            overlap = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
            if overlap >= 0.5 * word_area:
                continue
            words += 1
            chars += len(word["text"])
    return words, chars


def square_start_unknown(exact_w, exact_h, observed, grid, page_w, page_h):
    """True when some placement of an exact box of this size snaps to `observed`."""
    widths = np.asarray(exact_w, dtype=np.int64)
    heights = np.asarray(exact_h, dtype=np.int64)
    observed = tuple(int(v) for v in observed)
    feasible = np.zeros(len(widths), dtype=bool)
    cache = {}
    x_left, y_top, x_right, y_bottom = observed
    xs = np.arange(x_left - grid, x_right + 1, dtype=np.int64)
    ys = np.arange(y_top - grid, y_bottom + 1, dtype=np.int64)
    if len(xs) == 0 or len(ys) == 0:
        return feasible
    for index, (width, height) in enumerate(zip(widths.tolist(), heights.tolist())):
        key = (int(width), int(height))
        if key not in cache:
            cache[key] = _size_can_snap(key[0], key[1], observed, grid, page_w, page_h, xs, ys)
        feasible[index] = cache[key]
    return feasible


def _size_can_snap(width, height, observed, grid, page_w, page_h, xs, ys):
    if width <= 0 or height <= 0:
        return False
    x = xs[:, None]
    y = ys[None, :]
    left = np.floor(x / grid) * grid
    top = np.floor(y / grid) * grid
    right = guard_rw.ceil_multiple(np.ceil(x + width), grid)
    bottom = guard_rw.ceil_multiple(np.ceil(y + height), grid)
    left = np.clip(left, 0, page_w)
    top = np.clip(top, 0, page_h)
    right = np.clip(right, 0, page_w)
    bottom = np.clip(bottom, 0, page_h)
    hit = (
        (left == observed[0])
        & (top == observed[1])
        & (right == observed[2])
        & (bottom == observed[3])
    )
    return bool(hit.any())
