"""Geometry-leakage checks on fictional names set in real text engines.

The documents are synthetic. The text engines are ReportLab, MuPDF, and
Pillow/FreeType. Nothing here reads a confidential record or a Dutch FOIA
page image. Those page images are not in this repository.
"""
from __future__ import annotations

import hashlib
import io
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SURNAMES = ROOT / "research" / "e1" / "data" / "surnames_head1000.csv"
FONT_TIMES = "/System/Library/Fonts/Supplemental/Times New Roman.ttf"
FONT_ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_COURIER = "/System/Library/Fonts/Supplemental/Courier New.ttf"
FONT_GEORGIA = "/System/Library/Fonts/Supplemental/Georgia.ttf"
FONTS = {
    "Times": FONT_TIMES,
    "Arial": FONT_ARIAL,
    "Courier": FONT_COURIER,
    "Georgia": FONT_GEORGIA,
}
LAYOUT_FONT = {
    "court": "Times",
    "hospital": "Times",
    "government": "Arial",
    "letter": "Arial",
}
PAGE = (612.0, 792.0)
DPI = 144
SCALE = DPI / 72.0
FONT_PT = 12.0
PAD_PX = 1
SEED = 20261116
N_MAIN = 100
BOOTSTRAP = 2000


def load_surnames(path=SURNAMES):
    import csv
    rows = list(csv.DictReader(path.open()))
    names = [row["name"] for row in rows]
    counts = np.array([int(row["count"]) for row in rows], dtype=np.float64)
    ranks = np.array([int(row["rank"]) for row in rows], dtype=np.int64)
    return names, counts, ranks


def sample_names(names, counts, n=N_MAIN, seed=SEED):
    """Weighted sample without replacement, probability proportional to count."""
    rng = np.random.default_rng(seed)
    weights = np.asarray(counts, dtype=np.float64)
    keys = rng.random(len(names)) ** (1.0 / weights)
    chosen = np.sort(np.argsort(keys)[-n:])
    return [names[int(i)] for i in chosen], [int(i) for i in chosen]


def assign_split(name, salt="guard-rw-split"):
    digest = hashlib.sha256(f"{salt}:{name}".encode()).hexdigest()
    return "calibration" if int(digest[:2], 16) < 77 else "test"  # about 30%


def ceil_multiple(value, width):
    value = np.asarray(value)
    return -(-value // int(width)) * int(width)


def snap_out(box, grid):
    x0, y0, x1, y1 = box
    grid = int(grid)
    return (
        np.floor(np.asarray(x0, dtype=np.float64) / grid) * grid,
        np.floor(np.asarray(y0, dtype=np.float64) / grid) * grid,
        ceil_multiple(np.ceil(np.asarray(x1, dtype=np.float64)), grid),
        ceil_multiple(np.ceil(np.asarray(y1, dtype=np.float64)), grid),
    )


def exact_box(ink):
    x0, y0, x1, y1 = ink
    return (int(math.floor(x0) - PAD_PX), int(math.floor(y0) - PAD_PX),
            int(math.ceil(x1) + PAD_PX), int(math.ceil(y1) + PAD_PX))


def width_line_box(origin_x, ink_right, line_top, line_bottom, step):
    span = math.ceil(ink_right) - int(math.floor(origin_x))
    span = max(span, 1)
    width = int(ceil_multiple(span + 2 * PAD_PX, step))
    left = int(math.floor(origin_x) - PAD_PX)
    return (left, int(math.floor(line_top)), left + width, int(math.ceil(line_bottom)))


def field_box(origin_x, max_span, line_top, line_bottom):
    left = int(math.floor(origin_x) - PAD_PX)
    width = int(math.ceil(max_span) + 2 * PAD_PX)
    return (left, int(math.floor(line_top)), left + width, int(math.ceil(line_bottom)))


def glyph_integers(left, top, right, bottom):
    """Page-pixel glyph edges. Arrays in, arrays out."""
    return np.floor(left), np.floor(top), np.ceil(right), np.ceil(bottom)


def candidate_boxes(kind, left, top, right, bottom, x_l, line_top, line_bottom):
    """Integer policy rectangles for one shared start and line.

    `left` and `right` are glyph edges in page pixels, one per candidate.
    Exact and square policies use only that glyph. Width, start-aligned and
    field policies also use the shared start `x_l` and the shared line.
    """
    g_left, g_top, g_right, g_bottom = glyph_integers(left, top, right, bottom)
    tight_l = g_left - PAD_PX
    tight_t = g_top - PAD_PX
    tight_r = g_right + PAD_PX
    tight_b = g_bottom + PAD_PX
    if kind == "exact":
        return tight_l, tight_t, tight_r, tight_b
    if kind in {"square16", "square64"}:
        grid = 16 if kind == "square16" else 64
        return snap_out((tight_l, tight_t, tight_r, tight_b), grid)
    step = {"width64": 64, "start128": 128, "field": None}[kind]
    span = tight_r - x_l
    if kind == "field":
        width = np.full(np.shape(tight_r), np.max(span))
    else:
        width = ceil_multiple(span, step)
    x0 = np.full(np.shape(tight_r), x_l, dtype=np.float64)
    y0 = np.full(np.shape(tight_r), line_top, dtype=np.float64)
    y1 = np.full(np.shape(tight_r), line_bottom, dtype=np.float64)
    return x0, y0, x0 + width, y1


def shared_frame(left, top, right, bottom):
    """Left edge and line used by the list-aware policies, in page pixels."""
    g_left, g_top, g_right, g_bottom = glyph_integers(left, top, right, bottom)
    return float(np.min(g_left) - PAD_PX), float(np.min(g_top) - PAD_PX), float(np.max(g_bottom) + PAD_PX)


def policy_box(kind, ink, origin_x, line_top, line_bottom, max_span=None):
    left = np.asarray([ink[0]], dtype=np.float64)
    top = np.asarray([ink[1]], dtype=np.float64)
    right = np.asarray([ink[2]], dtype=np.float64)
    bottom = np.asarray([ink[3]], dtype=np.float64)
    if kind in {"width64", "start128", "field"}:
        edges = candidate_boxes(kind, left, top, right, bottom, origin_x, line_top, line_bottom)
    else:
        edges = candidate_boxes(kind, left, top, right, bottom, origin_x, line_top, line_bottom)
    return tuple(float(np.asarray(edge)[0]) for edge in edges)


def possibilistic(match, log_prior, index):
    """Prior restricted to the feasible set. Ties are expected hits.

    An empty feasible set is a model miss: the box did not name anyone, so
    the posterior stays the prior and the hit is the no-box hit. A feasible
    set that excludes the truth is a wrong identification: the hit is zero.
    Entropy reduction is reported in both non-empty cases. It is concentration
    of the posterior, including concentration on the wrong name.
    """
    match = np.asarray(match, dtype=bool)
    log_prior = np.asarray(log_prior, dtype=np.float64)
    if not np.any(match):
        return {
            "hit1": expected_hit(log_prior, index, 1),
            "hit10": expected_hit(log_prior, index, 10),
            "entropy_reduction": 0.0,
            "pointwise_bits": "",
            "truth_in_set": False,
            "feasible": 0,
            "empty": True,
        }
    scores = np.where(match, log_prior, -np.inf)
    posterior_scores = scores - logsumexp(scores)
    prior = np.exp(log_prior)
    mass = float(prior[match].sum())
    share = prior[match] / mass
    h0 = float(-(prior * np.log2(prior)).sum())
    h1 = float(-(share * np.log2(share)).sum())
    pointwise = float(-math.log2(mass)) if match[index] else ""
    return {
        "hit1": expected_hit(posterior_scores, index, 1),
        "hit10": expected_hit(posterior_scores, index, 10),
        "entropy_reduction": h0 - h1,
        "pointwise_bits": pointwise,
        "truth_in_set": bool(match[index]),
        "feasible": int(match.sum()),
        "empty": False,
    }


def rng_for(key, seed=SEED):
    digest = hashlib.sha256(f"{seed}:{key}".encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "little"))


POLICIES = ("exact", "square16", "square64", "width64", "start128", "field")


def intersects(a, b):
    x0, y0, x1, y1 = a
    u0, v0, u1, v1 = b
    return not (x1 <= u0 or u1 <= x0 or y1 <= v0 or v1 <= y0)


def area(box):
    return max(0, box[2] - box[0]) * max(0, box[3] - box[1])


def erf_vec(values):
    values = np.asarray(values, dtype=np.float64)
    sign = np.sign(values)
    magnitude = np.abs(values)
    t = 1.0 / (1.0 + 0.3275911 * magnitude)
    poly = t * (0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429))))
    return sign * (1.0 - poly * np.exp(-magnitude * magnitude))


def erfc_vec(values):
    values = np.asarray(values, dtype=np.float64)
    magnitude = np.abs(values)
    t = 1.0 / (1.0 + 0.3275911 * magnitude)
    poly = t * (0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429))))
    tail = poly * np.exp(-magnitude * magnitude)
    return np.where(values >= 0.0, tail, 2.0 - tail)


def log_normal_bin(low, high, mean, sigma):
    sigma = float(sigma)
    mean = np.asarray(mean, dtype=np.float64)
    z0 = (low - mean) / sigma
    z1 = (high - mean) / sigma
    scale = math.sqrt(2.0)
    upper = z0 > 0
    lower = z1 < 0
    middle = ~upper & ~lower
    probability = np.empty(mean.shape, dtype=np.float64)
    probability[upper] = 0.5 * (erfc_vec(z0[upper] / scale) - erfc_vec(z1[upper] / scale))
    probability[lower] = 0.5 * (erfc_vec(-z1[lower] / scale) - erfc_vec(-z0[lower] / scale))
    probability[middle] = 0.5 * (erf_vec(z1[middle] / scale) - erf_vec(z0[middle] / scale))
    return np.log(np.maximum(probability, 1e-300))


def logsumexp(values):
    peak = np.max(values)
    return peak + np.log(np.sum(np.exp(values - peak)))


def expected_hit(log_scores, index, k):
    if index < 0:
        return 0.0
    truth = float(log_scores[index])
    if not np.isfinite(truth):
        return 0.0
    greater = int(np.count_nonzero(log_scores > truth + 1e-8))
    equal = int(np.count_nonzero(np.abs(log_scores - truth) <= 1e-8))
    if equal == 0:
        return 0.0
    return float(min(1.0, max(0.0, (k - greater) / equal)))


def posterior(log_likelihood, log_prior):
    scores = np.asarray(log_likelihood, dtype=np.float64) + np.asarray(log_prior, dtype=np.float64)
    return scores - logsumexp(scores)


def shannon_bits(log_p):
    usable = log_p > -700
    mass = np.exp(log_p[usable])
    return float(-(mass * log_p[usable]).sum() / math.log(2.0))


def class_expected_hits(widths, prior, step=None):
    """Prior-weighted expected hit if the attacker sees the exact width, or its step class."""
    widths = np.asarray(widths)
    key = widths if step is None else ceil_multiple(np.ceil(widths).astype(np.int64), step)
    prior = np.asarray(prior, dtype=np.float64)
    prior = prior / prior.sum()
    hit1 = np.zeros(len(prior))
    hit10 = np.zeros(len(prior))
    order = np.argsort(key, kind="mergesort")
    sorted_key = key[order]
    start = 0
    while start < len(key):
        stop = start
        while stop + 1 < len(key) and sorted_key[stop + 1] == sorted_key[start]:
            stop += 1
        members = order[start:stop + 1]
        mass = prior[members]
        rank = np.argsort(-mass, kind="mergesort")
        ranked = mass[rank]
        greater = np.cumsum(ranked) - ranked
        equal = np.array([np.sum(np.abs(ranked - value) < 1e-15) for value in ranked])
        # ties: expected hit among equal prior
        local1 = np.empty(len(members))
        local10 = np.empty(len(members))
        for i, member_rank in enumerate(rank):
            ahead = int(np.sum(ranked > ranked[i] + 1e-15))
            tied = int(np.sum(np.abs(ranked - ranked[i]) <= 1e-15))
            local1[member_rank] = min(1.0, max(0.0, (1 - ahead) / tied))
            local10[member_rank] = min(1.0, max(0.0, (10 - ahead) / tied))
        hit1[members] = local1
        hit10[members] = local10
        start = stop + 1
    return float((hit1 * prior).sum()), float((hit10 * prior).sum()), hit1, hit10


def cluster_bootstrap_mean(clusters, values, rng, draws=BOOTSTRAP):
    keys = list(clusters)
    unique = np.unique(keys)
    groups = {key: np.asarray(values, dtype=np.float64)[np.asarray(keys) == key] for key in unique}
    stats = np.empty(draws)
    names = list(unique)
    for i in range(draws):
        take = rng.choice(len(names), size=len(names), replace=True)
        sample = np.concatenate([groups[names[j]] for j in take])
        stats[i] = sample.mean()
    return float(np.mean(values)), float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def layout_tokens(kind, name):
    """Top-origin point coordinates. The surname is its own token."""
    tokens = []

    def add(text, x, y, role, size=FONT_PT):
        tokens.append({"text": text, "x": float(x), "y": float(y), "role": role, "size": float(size), "target": role == "target"})

    if kind == "court":
        add("IN THE FICTIONAL DISTRICT COURT", 72, 72, "title", 14)
        add("Case No. CV-2026-1042", 72, 100, "field")
        add("Witness surname", 72, 140, "label")
        add(name, 72, 160, "target")
        add("The witness adopted the transcript on 4 March 2026.", 72, 200, "body")
        add("No other person is identified in this fictional record.", 72, 220, "body")
        add("Date", 72, 280, "label")
        add("4 March 2026", 180, 280, "field")
        add("Signature", 72, 320, "label")
        add("Fictional Clerk", 180, 320, "field")
        add("Page 1 of 1", 72, 740, "footer")
    elif kind == "hospital":
        add("FICTIONAL OUTPATIENT CLINIC", 72, 72, "title", 14)
        add("Department", 72, 120, "label")
        add("General medicine", 220, 120, "field")
        add("Patient surname", 72, 160, "label")
        add(name, 220, 160, "target")
        add("Reference", 72, 200, "label")
        add("OP-44821", 220, 200, "field")
        add("Appointment", 72, 240, "label")
        add("18 April 2026", 220, 240, "field")
        add("This form does not describe a real patient.", 72, 300, "body")
        add("Page 1 of 1", 72, 740, "footer")
    elif kind == "government":
        add("FICTIONAL LICENCE APPLICATION", 72, 72, "title", 14)
        add("Application number", 72, 120, "label")
        add("APP-2026-7781", 260, 120, "field")
        add("Applicant surname", 72, 160, "label")
        add(name, 260, 160, "target")
        add("Office", 72, 200, "label")
        add("North registry", 260, 200, "field")
        add("Submitted", 72, 240, "label")
        add("2 February 2026", 260, 240, "field")
        add("Address line", 72, 280, "label")
        add("100 Example Street", 260, 280, "field")
        add("Page 1 of 1", 72, 740, "footer")
    elif kind == "letter":
        add("Example Supply Cooperative", 72, 72, "title", 14)
        add("100 Example Street", 72, 96, "body")
        add("Recipient surname", 72, 150, "label")
        add(name, 72, 172, "target")
        add("Thank you for the March inventory count.", 72, 220, "body")
        add("The enclosed table is fictional.", 72, 240, "body")
        add("Quantity", 72, 290, "label")
        add("12", 180, 290, "field")
        add("Clerk", 72, 340, "label")
        add("A. Example", 180, 340, "field")
        add("Page 1 of 1", 72, 740, "footer")
    else:
        raise KeyError(kind)
    return tokens
