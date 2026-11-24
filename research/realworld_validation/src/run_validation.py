"""Fictional names in real text engines.

The surnames are the public census list. The case numbers, clinics and
addresses are invented. A black rectangle drawn over live text is not
treated as a secure redaction; text PDFs are sanitized with PyMuPDF
redaction and opened again.
"""
from __future__ import annotations

import argparse
import io
import json
import platform
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard_rw as g

HERE = Path(__file__).resolve().parents[1]
ENGINES = ("reportlab", "mupdf", "pillow")
LAYOUTS = ("court", "hospital", "government", "letter")
ALL_FONTS = ("Times", "Arial", "Courier", "Georgia")
# Half a pixel. Integer policy edges either match or they do not.
# This tolerance is declared here, before any test score is computed.
EDGE_TOL = 0.51


def package_version(name):
    try:
        import importlib.metadata as meta
        return meta.version(name)
    except Exception:
        return None


def measurer(engine, font_name, size_pt):
    path = g.FONTS[font_name]
    if engine == "pillow":
        font = ImageFont.truetype(path, int(round(size_pt * g.SCALE)))
        return lambda text, font=font: float(font.getlength(text))
    if engine == "reportlab":
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, path))
        return lambda text, font_name=font_name, size_pt=size_pt: float(pdfmetrics.stringWidth(text, font_name, size_pt) * g.SCALE)
    import pymupdf
    font = pymupdf.Font(fontfile=path)
    return lambda text, font=font, size_pt=size_pt: float(font.text_length(text, size_pt) * g.SCALE)


def pdf_catalog(engine, font_name, names):
    import pymupdf
    pen_x = 72.0
    per_page = 40
    chunks = [names[i:i + per_page] for i in range(0, len(names), per_page)]
    baselines = {}
    if engine == "reportlab":
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, g.FONTS[font_name]))
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=g.PAGE)
        for page_index, chunk in enumerate(chunks):
            if page_index:
                pdf.showPage()
            for j, name in enumerate(chunk):
                baseline_from_bottom = 740 - j * 16
                baselines[name] = g.PAGE[1] - baseline_from_bottom
                pdf.setFont(font_name, g.FONT_PT)
                pdf.drawString(pen_x, baseline_from_bottom, name)
        pdf.save()
        doc = pymupdf.open(stream=buffer.getvalue(), filetype="pdf")
    elif engine == "mupdf":
        doc = pymupdf.open()
        for chunk in chunks:
            page = doc.new_page(width=g.PAGE[0], height=g.PAGE[1])
            page.insert_font(fontname="Body", fontfile=g.FONTS[font_name])
            for j, name in enumerate(chunk):
                baseline = 48 + j * 16
                baselines[name] = baseline
                page.insert_text((pen_x, baseline), name, fontname="Body", fontsize=g.FONT_PT)
    else:
        raise KeyError(engine)
    found = {}
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    found[span["text"]] = span["bbox"]
    doc.close()
    missing = [name for name in names if name not in found]
    if missing:
        raise RuntimeError(f"{engine} {font_name} catalog missed {missing[:5]}")
    bearing = np.empty(len(names))
    width = np.empty(len(names))
    top = np.empty(len(names))
    bottom = np.empty(len(names))
    for i, name in enumerate(names):
        x0, y0, x1, y1 = found[name]
        bearing[i] = (x0 - pen_x) * g.SCALE
        width[i] = (x1 - x0) * g.SCALE
        top[i] = (y0 - baselines[name]) * g.SCALE
        bottom[i] = (y1 - baselines[name]) * g.SCALE
    return {"bearing": bearing, "width": width, "top": top, "bottom": bottom}


def pillow_catalog(font_name, names):
    font = ImageFont.truetype(g.FONTS[font_name], int(round(g.FONT_PT * g.SCALE)))
    bearing = np.empty(len(names))
    width = np.empty(len(names))
    top = np.empty(len(names))
    bottom = np.empty(len(names))
    for i, name in enumerate(names):
        x0, y0, x1, y1 = font.getbbox(name, anchor="ls")
        bearing[i] = x0
        width[i] = x1 - x0
        top[i] = y0
        bottom[i] = y1
    return {"bearing": bearing, "width": width, "top": top, "bottom": bottom}


def build_catalogs(names):
    catalogs = {}
    for font_name in ALL_FONTS:
        catalogs[("pillow", font_name)] = pillow_catalog(font_name, names)
        for engine in ("reportlab", "mupdf"):
            catalogs[(engine, font_name)] = pdf_catalog(engine, font_name, names)
            print(f"catalog {engine} {font_name} width median {np.median(catalogs[(engine, font_name)]['width']):.2f}", flush=True)
    return catalogs


def place(catalog, origin_x, baseline):
    left = origin_x + catalog["bearing"]
    top = baseline + catalog["top"]
    right = left + catalog["width"]
    bottom = baseline + catalog["bottom"]
    return left, top, right, bottom


def render_text(engine, tokens, font_name):
    import pymupdf
    if engine == "reportlab":
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, g.FONTS[font_name]))
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=g.PAGE)
        for token in tokens:
            pdf.setFont(font_name, token["size"])
            pdf.drawString(token["x"], g.PAGE[1] - token["y"], token["text"])
        pdf.save()
        data = buffer.getvalue()
    else:
        doc = pymupdf.open()
        page = doc.new_page(width=g.PAGE[0], height=g.PAGE[1])
        page.insert_font(fontname="Body", fontfile=g.FONTS[font_name])
        for token in tokens:
            page.insert_text((token["x"], token["y"]), token["text"], fontname="Body", fontsize=token["size"])
        data = doc.tobytes()
        doc.close()
    doc = pymupdf.open(stream=data, filetype="pdf")
    spans = []
    for block in doc[0].get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                spans.append(span)
    return data, spans, doc


def word_boxes(text, bbox, widths):
    parts = text.split(" ")
    advances = [widths(part) for part in parts]
    space = widths(" ")
    total = sum(advances) + space * max(0, len(parts) - 1)
    span = bbox[2] - bbox[0]
    scale = span / total if total else 1.0
    x = bbox[0]
    boxes = []
    for index, part in enumerate(parts):
        w = advances[index] * scale
        boxes.append((x, bbox[1], x + w, bbox[3], part))
        x += w + (space * scale if index + 1 < len(parts) else 0)
    return boxes


def sanitize_text_pdf(data, name, bbox_pt):
    import pymupdf
    from pypdf import PdfReader
    doc = pymupdf.open(stream=data, filetype="pdf")
    page = doc[0]
    rect = pymupdf.Rect(bbox_pt)
    rect.x0 -= 1
    rect.y0 -= 1
    rect.x1 += 1
    rect.y1 += 1
    before = page.get_pixmap(dpi=72, clip=pymupdf.Rect(bbox_pt), colorspace=pymupdf.csGRAY, alpha=False)
    dark_before = int(np.frombuffer(before.samples, dtype=np.uint8).min() < 200) if before.samples else 0
    page.add_redact_annot(rect, fill=(0, 0, 0))
    page.apply_redactions()
    sanitized = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    reopened = pymupdf.open(stream=sanitized, filetype="pdf")
    text_m = reopened[0].get_text()
    annots = list(reopened[0].annots() or [])
    after = reopened[0].get_pixmap(dpi=72, clip=rect, colorspace=pymupdf.csGRAY, alpha=False)
    dark_after = float(np.frombuffer(after.samples, dtype=np.uint8).mean()) if after.samples else 255
    reopened.close()
    reader = PdfReader(io.BytesIO(sanitized))
    text_p = reader.pages[0].extract_text() or ""
    meta = reader.metadata
    meta_blob = " ".join(str(value) for value in meta.values()) if meta else ""
    passed = (name not in text_m) and (name not in text_p) and (name not in meta_blob) and not annots
    return sanitized, {
        "passed": passed,
        "pymupdf_clean": name not in text_m,
        "pypdf_clean": name not in text_p,
        "metadata_clean": name not in meta_blob,
        "annot_count": len(annots),
        "raw_ascii_absent": name.encode("ascii") not in sanitized,
        "ink_seen_before": bool(dark_before),
        "redact_fill_mean": dark_after,
        "check": "pymupdf_apply_redactions_reopened",
    }


def image_only_pdf(image):
    import pymupdf
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    doc = pymupdf.open()
    page = doc.new_page(width=g.PAGE[0], height=g.PAGE[1])
    page.insert_image(page.rect, stream=buffer.getvalue())
    data = doc.tobytes(deflate=True)
    doc.close()
    return data


def check_image_pdf(data, name):
    import pymupdf
    from pypdf import PdfReader
    reopened = pymupdf.open(stream=data, filetype="pdf")
    text_m = reopened[0].get_text()
    annots = list(reopened[0].annots() or [])
    reopened.close()
    text_p = PdfReader(io.BytesIO(data)).pages[0].extract_text() or ""
    return {
        "passed": text_m.strip() == "" and text_p.strip() == "" and not annots,
        "pymupdf_clean": name not in text_m,
        "pypdf_clean": name not in text_p,
        "metadata_clean": True,
        "annot_count": len(annots),
        "raw_ascii_absent": name.encode("ascii") not in data,
        "ink_seen_before": True,
        "redact_fill_mean": 0.0,
        "check": "image_only_pdf_no_text_layer",
    }


def build_documents(names, ranks, catalogs, sampled, save_dir, save_all):
    documents = []
    failures = []
    save_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    for engine in ENGINES:
        width_of = {size: measurer(engine, "Times", size) for size in (12, 14)}
        # measurer font is replaced per document below
        for layout in LAYOUTS:
            font_name = g.LAYOUT_FONT[layout]
            widths = {size: measurer(engine, font_name, size) for size in (12.0, 14.0)}
            pillow_fonts = {}
            for name in sampled:
                tokens = g.layout_tokens(layout, name)
                target = next(token for token in tokens if token["target"])
                origin = target["x"] * g.SCALE
                baseline = target["y"] * g.SCALE
                catalog = catalogs[(engine, font_name)]
                index = names.index(name)
                pred_left = origin + catalog["bearing"][index]
                pred_top = baseline + catalog["top"][index]
                pred_right = pred_left + catalog["width"][index]
                pred_bottom = baseline + catalog["bottom"][index]
                band, long_name = stratum(index + 1, name)
                record = {
                    "engine": engine, "layout": layout, "font": font_name, "name": name,
                    "rank": int(ranks[index]), "file_order": index + 1,
                    "stratum": band, "long_name": long_name, "split": g.assign_split(name),
                    "origin_x": origin, "baseline": baseline,
                }
                if engine == "pillow":
                    image = Image.new("L", (int(g.PAGE[0] * g.SCALE), int(g.PAGE[1] * g.SCALE)), 255)
                    draw = ImageDraw.Draw(image)
                    words = []
                    ink = None
                    for token in tokens:
                        size_key = float(token["size"])
                        if size_key not in pillow_fonts:
                            pillow_fonts[size_key] = ImageFont.truetype(g.FONTS[font_name], int(round(size_key * g.SCALE)))
                        font = pillow_fonts[size_key]
                        draw.text((token["x"] * g.SCALE, token["y"] * g.SCALE), token["text"], font=font, fill=0, anchor="ls")
                        box = font.getbbox(token["text"], anchor="ls")
                        bbox = (token["x"] * g.SCALE + box[0], token["y"] * g.SCALE + box[1],
                                token["x"] * g.SCALE + box[2], token["y"] * g.SCALE + box[3])
                        if token["target"]:
                            ink = bbox
                        else:
                            words.extend(
                                (box[0], box[1], box[2], box[3], token["role"])
                                for box in word_boxes(token["text"], bbox, widths[float(token["size"])])
                            )
                    if ink is None:
                        failures.append({**record, "reason": "pillow_ink_missing"})
                        continue
                    exact = g.candidate_boxes("exact", [ink[0]], [ink[1]], [ink[2]], [ink[3]], 0, 0, 0)
                    paint = tuple(int(v[0]) for v in exact)
                    red = image.copy()
                    red.paste(0, (max(0, paint[0]), max(0, paint[1]), min(red.width, paint[2]), min(red.height, paint[3])))
                    data = image_only_pdf(red)
                    check = check_image_pdf(data, name)
                    crop = np.asarray(red.crop((max(0, paint[0]), max(0, paint[1]), min(red.width, paint[2]), min(red.height, paint[3]))))
                    check["redact_fill_mean"] = float(crop.mean()) if crop.size else 255
                    check["ink_seen_before"] = bool(np.asarray(image.crop((int(ink[0]), int(ink[1]), int(np.ceil(ink[2])), int(np.ceil(ink[3]))))).min() < 200)
                else:
                    data, spans, doc = render_text(engine, tokens, font_name)
                    page = doc[0]
                    if abs(page.rect.width - g.PAGE[0]) > 0.1 or abs(page.rect.height - g.PAGE[1]) > 0.1:
                        failures.append({**record, "reason": "page_size"})
                        doc.close()
                        continue
                    matched = [span for span in spans if span["text"] == name]
                    if len(matched) != 1:
                        failures.append({**record, "reason": "target_span", "n": len(matched)})
                        doc.close()
                        continue
                    span = matched[0]
                    expected = "times" if font_name == "Times" else "arial"
                    if expected not in span["font"].lower():
                        failures.append({**record, "reason": "unexpected_font", "embedded_font": span["font"]})
                        doc.close()
                        continue
                    bb = span["bbox"]
                    ink = tuple(value * g.SCALE for value in bb)
                    words = []
                    for token in tokens:
                        if token["target"]:
                            continue
                        token_spans = [item for item in spans if item["text"] == token["text"]]
                        if len(token_spans) != 1:
                            continue
                        tb = tuple(value * g.SCALE for value in token_spans[0]["bbox"])
                        for box in word_boxes(token["text"], tb, widths[float(token["size"])]):
                            words.append((box[0], box[1], box[2], box[3], token["role"]))
                    doc.close()
                    sanitized, check = sanitize_text_pdf(data, name, bb)
                    data = sanitized
                if not check["passed"] or not check["ink_seen_before"]:
                    failures.append({**record, "reason": "sanitizer", **{k: check[k] for k in ("pymupdf_clean", "pypdf_clean", "ink_seen_before")}})
                    continue
                if save_all or saved < 12:
                    path = save_dir / f"{engine}_{layout}_{saved:04d}.pdf"
                    path.write_bytes(data)
                    saved += 1
                record.update({
                    "ink": ink,
                    "words": words,
                    "width_error_px": abs((ink[2] - ink[0]) - catalog["width"][index]),
                    "edge_error_px": max(
                        abs(ink[0] - pred_left), abs(ink[1] - pred_top),
                        abs(ink[2] - pred_right), abs(ink[3] - pred_bottom),
                    ),
                    "text_check": check["check"],
                    "raw_ascii_absent": check["raw_ascii_absent"],
                    "redact_fill_mean": check["redact_fill_mean"],
                    "sha256": g.sha256_bytes(data),
                })
                documents.append(record)
    return documents, failures


def observed_edges(kind, ink, frame_boxes):
    if kind == "field":
        return tuple(float(np.asarray(edge)[0]) for edge in frame_boxes)
    x0, y0, x1, y1 = g.candidate_boxes(
        kind, np.array([ink[0]]), np.array([ink[1]]), np.array([ink[2]]), np.array([ink[3]]),
        frame_boxes[0] if False else 0, 0, 0,
    )
    # exact and square ignore the shared frame. width policies need it.
    return None


def policy_edges(kind, left, top, right, bottom, x_l, line_top, line_bottom):
    return g.candidate_boxes(kind, left, top, right, bottom, x_l, line_top, line_bottom)


def matches(pred, observed, tol=EDGE_TOL):
    return (
        (np.abs(pred[0] - observed[0]) <= tol)
        & (np.abs(pred[1] - observed[1]) <= tol)
        & (np.abs(pred[2] - observed[2]) <= tol)
        & (np.abs(pred[3] - observed[3]) <= tol)
    )


def frame_of(catalog, origin_x, baseline):
    left, top, right, bottom = place(catalog, origin_x, baseline)
    x_l, line_top, line_bottom = g.shared_frame(left, top, right, bottom)
    return left, top, right, bottom, x_l, line_top, line_bottom


def boxes_for(catalog, origin_x, baseline):
    left, top, right, bottom, x_l, line_top, line_bottom = frame_of(catalog, origin_x, baseline)
    return {
        kind: policy_edges(kind, left, top, right, bottom, x_l, line_top, line_bottom)
        for kind in g.POLICIES
    }, (x_l, line_top, line_bottom)


def scalar_box(edges, index=0):
    return tuple(float(np.asarray(edge)[index]) for edge in edges)


def utility_of(box, words, ink):
    chars = 0
    word_n = 0
    fields = 0
    for x0, y0, x1, y1, role in words:
        if g.intersects(box, (x0, y0, x1, y1)):
            chars += 1  # replaced below
    # recount with the stored word text length via the role-only tuples.
    # words carry no character count. Count boxes and treat each as one word.
    hit_words = [item for item in words if g.intersects(box, item[:4])]
    return {
        "covered_words": len(hit_words),
        "covered_fields": sum(1 for item in hit_words if item[4] in {"label", "field", "title", "footer"}),
        "covered_body_words": sum(1 for item in hit_words if item[4] == "body"),
        "contains_ink": box[0] <= ink[0] + 0.01 and box[1] <= ink[1] + 0.01 and box[2] >= ink[2] - 0.01 and box[3] >= ink[3] - 0.01,
    }


def stratum(file_order, name):
    """Frequency band by position in the shipped list, which is count order.

    Long means 10 or 11 letters. The shipped list has no longer surname.
    """
    if file_order <= 100:
        band = "common"
    elif file_order <= 500:
        band = "medium"
    else:
        band = "rare"
    return band, len(name) >= 10


def score(documents, names, prior, log_prior, catalogs):
    index_of = {name: i for i, name in enumerate(names)}
    nobox = {
        name: (g.expected_hit(log_prior, index_of[name], 1), g.expected_hit(log_prior, index_of[name], 10))
        for name in {doc["name"] for doc in documents}
    }
    measurements = []
    attacks = []
    excluded = []
    cache = {}
    for doc_i, doc in enumerate(documents):
        key = (doc["engine"], doc["font"], round(doc["origin_x"], 3), round(doc["baseline"], 3))
        if key not in cache:
            cache[key] = boxes_for(catalogs[(doc["engine"], doc["font"])], doc["origin_x"], doc["baseline"])
        true_boxes, frame = cache[key]
        other_engines = [engine for engine in ENGINES if engine != doc["engine"]]
        a2_boxes = [boxes_for(catalogs[(engine, doc["font"])], doc["origin_x"], doc["baseline"])[0] for engine in ENGINES]
        a3_boxes = [boxes_for(catalogs[(doc["engine"], font)], doc["origin_x"], doc["baseline"])[0] for font in ("Times", "Arial")]
        held_boxes = [boxes_for(catalogs[(doc["engine"], font)], doc["origin_x"], doc["baseline"])[0] for font in ("Courier", "Georgia")]
        for kind in g.POLICIES:
            if kind == "field":
                observed = scalar_box(true_boxes[kind])
            else:
                edges = policy_edges(
                    kind,
                    np.array([doc["ink"][0]]), np.array([doc["ink"][1]]),
                    np.array([doc["ink"][2]]), np.array([doc["ink"][3]]),
                    frame[0], frame[1], frame[2],
                )
                observed = scalar_box(edges)
            use = utility_of(observed, doc["words"], doc["ink"])
            exact_area = g.area(scalar_box(policy_edges(
                "exact",
                np.array([doc["ink"][0]]), np.array([doc["ink"][1]]),
                np.array([doc["ink"][2]]), np.array([doc["ink"][3]]),
                frame[0], frame[1], frame[2],
            )))
            measurements.append({
                "engine": doc["engine"], "layout": doc["layout"], "font": doc["font"],
                "name": doc["name"], "rank": doc["rank"], "split": doc["split"],
                "policy": kind, "contains_ink": use["contains_ink"],
                "box_x0": observed[0], "box_y0": observed[1], "box_x1": observed[2], "box_y1": observed[3],
                "box_w": observed[2] - observed[0], "box_h": observed[3] - observed[1],
                "ink_w": doc["ink"][2] - doc["ink"][0],
                "area_ratio": (g.area(observed) / exact_area) if exact_area else "",
                "covered_words": use["covered_words"],
                "covered_body_words": use["covered_body_words"],
                "covered_fields": use["covered_fields"],
                "width_error_px": doc["width_error_px"],
                "edge_error_px": doc["edge_error_px"],
            })
            if doc["split"] != "test":
                continue
            if not use["contains_ink"]:
                excluded.append({**measurements[-1], "reason": "mask_does_not_contain_ink"})
                continue
            raw_masks = {
                "matched": matches(true_boxes[kind], observed),
                "unknown_renderer": np.logical_or.reduce([matches(item[kind], observed) for item in a2_boxes]),
                "unknown_font": np.logical_or.reduce([matches(item[kind], observed) for item in a3_boxes]),
                "heldout_font": np.logical_or.reduce([matches(item[kind], observed) for item in held_boxes]),
            }
            # A field box is defined to cover the whole candidate list. An
            # attacker who is told that policy cannot use the rectangle to
            # rank names, whichever font they assume.
            if kind == "field":
                masks = {name: np.ones(len(names), dtype=bool) for name in raw_masks}
            else:
                masks = raw_masks
            base1, base10 = nobox[doc["name"]]
            for attacker, mask in masks.items():
                # Entropy is the possibilistic posterior only. Held-out and
                # mixture attackers use the same posterior rule.
                scored = g.possibilistic(mask, log_prior, index_of[doc["name"]])
                attacks.append({
                    "engine": doc["engine"], "layout": doc["layout"], "font": doc["font"],
                    "name": doc["name"], "rank": doc["rank"], "policy": kind, "attacker": attacker,
                    "hit1": scored["hit1"], "hit10": scored["hit10"],
                    "entropy_reduction": scored["entropy_reduction"],
                    "pointwise_bits": scored["pointwise_bits"],
                    "truth_in_set": scored["truth_in_set"],
                    "feasible": scored["feasible"],
                    "empty_set": scored["empty"],
                    "rectangle_covers_truth": bool(raw_masks[attacker][index_of[doc["name"]]]),
                    "nobox_hit1": base1, "nobox_hit10": base10,
                })
        if doc_i and doc_i % 200 == 0:
            print(f"scored {doc_i}/{len(documents)}", flush=True)
    return measurements, attacks, excluded


def exhaustive(names, prior, log_prior, catalogs):
    rows = []
    origin, baseline = 72 * g.SCALE, 160 * g.SCALE
    for engine in ENGINES:
        for font_name in ALL_FONTS:
            boxes, _frame = boxes_for(catalogs[(engine, font_name)], origin, baseline)
            for kind, edges in boxes.items():
                quantized = np.round(np.stack([np.asarray(edge) for edge in edges], axis=1) * 2).astype(np.int64)
                _unique, inverse = np.unique(quantized, axis=0, return_inverse=True)
                top1, top10, hits1, hits10 = g.class_expected_hits(inverse.astype(np.float64), prior)
                counts = np.bincount(inverse)
                size = counts[inverse]
                mass = np.bincount(inverse, weights=prior)
                pointwise = -np.log2(mass[inverse])
                singletons = np.flatnonzero(size == 1)
                rows.append({
                    "engine": engine, "font": font_name, "policy": kind,
                    "generated": font_name in {"Times", "Arial"},
                    "prior_weighted_top1": top1,
                    "prior_weighted_top10": top10,
                    "singleton_names": int(np.sum(size == 1)),
                    "classes_lt_10": int(np.sum(counts < 10)),
                    "classes_lt_100": int(np.sum(counts < 100)),
                    "n_classes": int(len(counts)),
                    "prior_mass_singleton": float(prior[size == 1].sum()),
                    "prior_mass_lt_10": float(prior[size < 10].sum()),
                    "prior_mass_lt_100": float(prior[size < 100].sum()),
                    "max_pointwise_bits": float(pointwise.max()),
                    "example_singleton": names[int(singletons[0])] if len(singletons) else "",
                    "list": "shipped_surnames_head1000",
                    "mean_hit1_common": _band(hits1, names, prior, "common"),
                    "mean_hit10_common": _band(hits10, names, prior, "common"),
                    "mean_hit1_medium": _band(hits1, names, prior, "medium"),
                    "mean_hit10_medium": _band(hits10, names, prior, "medium"),
                    "mean_hit1_rare": _band(hits1, names, prior, "rare"),
                    "mean_hit10_rare": _band(hits10, names, prior, "rare"),
                    "mean_hit10_long": _band(hits10, names, prior, "long"),
                })
    return rows


def _band(hits, names, prior, band):
    keep = []
    for i, name in enumerate(names):
        label, long_name = stratum(i + 1, name)
        if band == "long" and long_name:
            keep.append(i)
        elif band == label:
            keep.append(i)
    if not keep:
        return None
    keep = np.asarray(keep, dtype=np.int64)
    weight = prior[keep]
    weight = weight / weight.sum()
    return float(np.sum(hits[keep] * weight))


def repeated_releases(documents, names, log_prior, catalogs):
    index_of = {name: i for i, name in enumerate(names)}
    chosen = [doc for doc in documents if doc["engine"] == "reportlab" and doc["split"] == "test"]
    chosen = sorted(chosen, key=lambda doc: (doc["layout"], doc["name"]))[:200]
    rows = []
    for doc in chosen:
        origin, baseline = doc["origin_x"], doc["baseline"]
        font_name = doc["font"]
        other_font = "Arial" if font_name == "Times" else "Times"
        releases = []
        true_index = index_of[doc["name"]]
        # Each release is the rectangle that engine and font would actually draw
        # for this surname. The attacker is told which engine and font that
        # release used. Intersecting with a different engine's explanation of
        # the first rectangle is a different question and is recorded below.
        boxes, _frame = boxes_for(catalogs[("reportlab", font_name)], origin, baseline)
        releases.append(("exact_reportlab", matches(boxes["exact"], scalar_box(boxes["exact"], true_index))))
        other, _ = boxes_for(catalogs[("mupdf", font_name)], origin, baseline)
        releases.append(("exact_mupdf_own_box", matches(other["exact"], scalar_box(other["exact"], true_index))))
        shifted, _shifted_frame = boxes_for(catalogs[("reportlab", font_name)], origin + 7, baseline)
        releases.append(("square16_shifted_7px", matches(shifted["square16"], scalar_box(shifted["square16"], true_index))))
        alt, _alt_frame = boxes_for(catalogs[("reportlab", other_font)], origin, baseline)
        releases.append(("exact_other_font", matches(alt["exact"], scalar_box(alt["exact"], true_index))))
        releases.append(("start128_reportlab", matches(boxes["start128"], scalar_box(boxes["start128"], true_index))))
        conflict = matches(other["exact"], scalar_box(boxes["exact"], true_index))
        rows.append({
            "name": doc["name"], "layout": doc["layout"], "releases": 1, "added": "mupdf_box_equals_reportlab_box",
            "hit1": "", "hit10": "", "feasible": int(conflict.sum()),
            "truth_in_set": bool(conflict[true_index]), "entropy_reduction": "",
            "kind": "cross_engine_same_rectangle",
        })
        running = np.ones(len(names), dtype=bool)
        identical = releases[0][1]
        for count, (label, mask) in enumerate(releases, start=1):
            running = running & mask
            scored = g.possibilistic(running, log_prior, index_of[doc["name"]])
            rows.append({
                "name": doc["name"], "layout": doc["layout"], "releases": count, "added": label,
                "hit1": scored["hit1"], "hit10": scored["hit10"],
                "feasible": scored["feasible"], "truth_in_set": scored["truth_in_set"],
                "entropy_reduction": scored["entropy_reduction"],
                "kind": "new_geometry",
            })
        # Publishing the same exact mask again does not change the feasible set.
        same = g.possibilistic(identical, log_prior, index_of[doc["name"]])
        rows.append({
            "name": doc["name"], "layout": doc["layout"], "releases": 5, "added": "five_copies_of_exact",
            "hit1": same["hit1"], "hit10": same["hit10"], "feasible": same["feasible"],
            "truth_in_set": same["truth_in_set"], "entropy_reduction": same["entropy_reduction"],
            "kind": "identical_mask",
        })
    return rows


def simulate_scans(documents, names, log_prior, catalogs):
    import pymupdf
    calib = take_balanced([doc for doc in documents if doc["engine"] == "reportlab" and doc["split"] == "calibration"], 40)
    test = take_balanced([doc for doc in documents if doc["engine"] == "reportlab" and doc["split"] == "test"], 80)
    rng = g.rng_for("simulated-scan")
    rows = []
    errors = []
    index_of = {name: i for i, name in enumerate(names)}
    for doc in calib + test:
        tokens = g.layout_tokens(doc["layout"], doc["name"])
        _data, _spans, pdf = render_text("reportlab", tokens, doc["font"])
        pix = pdf[0].get_pixmap(dpi=g.DPI, colorspace=pymupdf.csGRAY, alpha=False)
        image = Image.frombytes("L", (pix.width, pix.height), pix.samples)
        pdf.close()
        ink = doc["ink"]
        paint = (int(np.floor(ink[0])), int(np.floor(ink[1])), int(np.ceil(ink[2])), int(np.ceil(ink[3])))
        image.paste(0, paint)
        angle = float(rng.uniform(-0.6, 0.6))
        degraded = image.rotate(angle, resample=Image.BICUBIC, fillcolor=255)
        degraded = degraded.filter(ImageFilter.GaussianBlur(radius=0.6))
        array = np.asarray(degraded).astype(np.float32)
        array = np.clip(array + rng.normal(0, 6, array.shape), 0, 255).astype(np.uint8)
        buffer = io.BytesIO()
        Image.fromarray(array).save(buffer, format="JPEG", quality=40)
        degraded = Image.open(io.BytesIO(buffer.getvalue())).convert("L")
        pad = 18
        x0, y0 = max(0, paint[0] - pad), max(0, paint[1] - pad)
        x1, y1 = min(degraded.width, paint[2] + pad), min(degraded.height, paint[3] + pad)
        crop = np.asarray(degraded.crop((x0, y0, x1, y1)))
        mask = crop < 40
        if not mask.any():
            rows.append({"name": doc["name"], "layout": doc["layout"], "split": doc["split"], "status": "detection_failed", "label": "simulated_scan"})
            continue
        ys, xs = np.nonzero(mask)
        found_w = int(xs.max() - xs.min() + 1)
        ink_w = ink[2] - ink[0]
        error = abs(found_w - ink_w)
        outside = int(np.sum(mask))
        # dark pixels whose location is outside the original paint, in the window
        local_paint = (paint[0] - x0, paint[1] - y0, paint[2] - x0, paint[3] - y0)
        inside = (
            (xs >= local_paint[0]) & (xs < local_paint[2]) & (ys >= local_paint[1]) & (ys < local_paint[3])
        )
        rows.append({
            "name": doc["name"], "layout": doc["layout"], "split": doc["split"], "status": "measured",
            "width_error_px": error, "dark_frac_outside_mask": float(1 - inside.mean()),
            "angle": angle, "label": "simulated_scan_not_a_physical_scan",
        })
        errors.append((doc["split"], error, doc["name"], doc["layout"], found_w, ink_w))
    calib_err = np.array([error for split, error, *_rest in errors if split == "calibration"], dtype=np.float64)
    if len(calib_err) < 8:
        return rows, {"status": "not_scored", "reason": "calibration detections below 8", "n": int(len(calib_err))}
    tolerance = float(np.quantile(calib_err, 0.95))
    scored = []
    for split, error, name, layout, found_w, ink_w in errors:
        if split != "test":
            continue
        catalog = catalogs[("reportlab", g.LAYOUT_FONT[layout])]
        # Feasible names are those whose catalog width is within the calibration tolerance of the detected width.
        mask = np.abs(catalog["width"] - found_w) <= tolerance
        result = g.possibilistic(mask, log_prior, index_of[name])
        base10 = g.expected_hit(log_prior, index_of[name], 10)
        scored.append({
            "name": name, "layout": layout, "hit10": result["hit10"], "hit1": result["hit1"],
            "feasible": result["feasible"], "truth_in_set": result["truth_in_set"],
            "nobox_hit10": base10, "tolerance_px": tolerance,
        })
    summary = {
        "status": "scored",
        "label": "simulated_scan_not_a_physical_scan",
        "calibration_n": int(len(calib_err)),
        "tolerance_px": tolerance,
        "calibration_median_abs_error_px": float(np.median(calib_err)),
        "test_n": len(scored),
        "test_top10": float(np.mean([row["hit10"] for row in scored])) if scored else None,
        "test_top1": float(np.mean([row["hit1"] for row in scored])) if scored else None,
        "test_truth_in_set": float(np.mean([row["truth_in_set"] for row in scored])) if scored else None,
        "test_nobox_top10": float(np.mean([row["nobox_hit10"] for row in scored])) if scored else None,
    }
    if scored:
        point, low, high = g.cluster_bootstrap_mean(
            [row["name"] for row in scored], [row["hit10"] for row in scored], g.rng_for("scan-top10"),
        )
        summary["test_top10_ci"] = [low, high]
    return rows + [{"record": "attack", **row} for row in scored], summary


def take_balanced(docs, n):
    buckets = {layout: [doc for doc in docs if doc["layout"] == layout] for layout in LAYOUTS}
    for layout in buckets:
        buckets[layout].sort(key=lambda doc: doc["name"])
    out = []
    while len(out) < n and any(buckets.values()):
        for layout in LAYOUTS:
            if buckets[layout] and len(out) < n:
                out.append(buckets[layout].pop(0))
    return out


def holm(pvalues):
    order = np.argsort(pvalues)
    adjusted = np.empty(len(pvalues))
    running = 0.0
    m = len(pvalues)
    for rank, index in enumerate(order):
        value = min(1.0, (m - rank) * float(pvalues[index]))
        running = max(running, value)
        adjusted[index] = running
    return adjusted


def bootstrap_p(clusters, values):
    rng = g.rng_for("p:" + str(clusters[0]) + ":" + str(len(clusters)) + ":" + f"{np.mean(values):.6f}")
    # The key above depends on the estimate. Use a caller-supplied rng instead.
    point, low, high = g.cluster_bootstrap_mean(clusters, values, rng)
    return point, low, high


def summarize(attacks, measurements):
    import pandas as pd
    frame = pd.DataFrame(attacks)
    measured = pd.DataFrame(measurements)
    summaries = []
    tests = []
    if not frame.empty:
        for (attacker, policy), group in frame.groupby(["attacker", "policy"], sort=True):
            rng = g.rng_for(f"top10:{attacker}:{policy}")
            point, low, high = g.cluster_bootstrap_mean(group["name"].tolist(), group["hit10"].tolist(), rng)
            rng1 = g.rng_for(f"top1:{attacker}:{policy}")
            p1, l1, h1 = g.cluster_bootstrap_mean(group["name"].tolist(), group["hit1"].tolist(), rng1)
            diff = (group["hit10"] - group["nobox_hit10"]).tolist()
            rngd = g.rng_for(f"diff10:{attacker}:{policy}")
            dpoint, dlow, dhigh = g.cluster_bootstrap_mean(group["name"].tolist(), diff, rngd)
            bits = group["entropy_reduction"].astype(float)
            rngb = g.rng_for(f"bits:{attacker}:{policy}")
            bpoint, blow, bhigh = g.cluster_bootstrap_mean(group["name"].tolist(), bits.tolist(), rngb)
            summaries.append({
                "attacker": attacker, "policy": policy, "n": int(len(group)),
                "names": int(group["name"].nunique()),
                "top1": p1, "top1_ci_low": l1, "top1_ci_high": h1,
                "top10": point, "top10_ci_low": low, "top10_ci_high": high,
                "nobox_top10": float(group["nobox_hit10"].mean()),
                "nobox_top1": float(group["nobox_hit1"].mean()),
                "top10_minus_nobox": dpoint, "diff_ci_low": dlow, "diff_ci_high": dhigh,
                "entropy_reduction": bpoint, "entropy_ci_low": blow, "entropy_ci_high": bhigh,
                "truth_in_set": float(group["truth_in_set"].mean()),
                "median_feasible": float(group["feasible"].median()),
            })
        matched = frame[frame["attacker"] == "matched"]
        pvals = []
        labels = []
        for policy, group in matched.groupby("policy", sort=True):
            diff = (group["hit10"] - group["nobox_hit10"]).to_numpy()
            rng = g.rng_for(f"pval:{policy}")
            _point, _low, _high, draws = _draws(group["name"].tolist(), diff, rng)
            crosses = min(np.mean(draws <= 0), np.mean(draws >= 0))
            p = min(1.0, 2 * (1 + np.sum(draws * 0 <= -1)) )  # placeholder replaced below
            p = min(1.0, 2.0 * (np.sum(draws <= 0) + 1) / (len(draws) + 1))
            pvals.append(p)
            labels.append(policy)
            tests.append({
                "family": "matched_top10_minus_nobox", "policy": policy,
                "estimate": float(np.mean(diff)), "ci_low": _low, "ci_high": _high,
                "p_bootstrap": p,
            })
        adjusted = holm(np.array(pvals))
        for row, value in zip(tests, adjusted):
            row["p_holm"] = float(value)
    utility = []
    test_m = measured[measured["split"] == "test"] if not measured.empty else measured
    for (policy, layout), group in test_m.groupby(["policy", "layout"], sort=True):
        utility.append({
            "policy": policy, "layout": layout, "n": int(len(group)),
            "median_area_ratio": float(group["area_ratio"].median()),
            "mean_area_ratio": float(group["area_ratio"].mean()),
            "mean_covered_words": float(group["covered_words"].mean()),
            "mean_covered_fields": float(group["covered_fields"].mean()),
            "documents_with_neighbor_loss": float((group["covered_words"] > 0).mean()),
            "containment": float(group["contains_ink"].mean()),
        })
    return summaries, utility, tests


def _draws(clusters, values, rng, draws=g.BOOTSTRAP):
    keys = list(clusters)
    unique = list(np.unique(keys))
    groups = {key: np.asarray(values, dtype=np.float64)[np.asarray(keys) == key] for key in unique}
    stats = np.empty(draws)
    for i in range(draws):
        take = rng.choice(len(unique), size=len(unique), replace=True)
        stats[i] = np.concatenate([groups[unique[j]] for j in take]).mean()
    point = float(np.mean(values))
    return point, float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5)), stats


def write_csv(path, rows):
    import pandas as pd
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def public_documents(documents):
    rows = []
    for doc in documents:
        rows.append({
            "engine": doc["engine"], "layout": doc["layout"], "font": doc["font"],
            "name": doc["name"], "rank": doc["rank"], "file_order": doc["file_order"],
            "stratum": doc["stratum"], "long_name": doc["long_name"],
            "split": doc["split"], "text_check": doc["text_check"],
            "raw_ascii_absent": doc["raw_ascii_absent"], "redact_fill_mean": doc["redact_fill_mean"],
            "ink_w": doc["ink"][2] - doc["ink"][0], "ink_h": doc["ink"][3] - doc["ink"][1],
            "width_error_px": doc["width_error_px"], "edge_error_px": doc["edge_error_px"],
            "sha256": doc["sha256"],
        })
    return rows


def environment():
    tools = {}
    for tool in ("soffice", "pdftotext", "pdftoppm", "pdfinfo", "gs", "mutool", "wkhtmltopdf"):
        tools[tool] = shutil.which(tool)
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "pillow": package_version("pillow"),
        "numpy": package_version("numpy"),
        "pandas": package_version("pandas"),
        "matplotlib": package_version("matplotlib"),
        "pymupdf": package_version("pymupdf"),
        "reportlab": package_version("reportlab"),
        "pypdf": package_version("pypdf"),
        "tools": tools,
        "fonts": {name: path for name, path in g.FONTS.items()},
        "seed": g.SEED,
        "dpi": g.DPI,
        "edge_tolerance_px": EDGE_TOL,
        "physical_scan": False,
        "libreoffice": False,
        "poppler": False,
        "ghostscript": False,
        "weasyprint": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out", type=Path, default=HERE / "results")
    parser.add_argument("--save-all", action="store_true")
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    names, counts, ranks = g.load_surnames()
    if list(ranks[:3]) != [1, 2, 3]:
        raise SystemExit("surname ranks are not in census order; sampling assumptions fail")
    prior = counts / counts.sum()
    log_prior = np.log(prior)
    sampled, _index = g.sample_names(names, counts)
    if args.limit:
        sampled = sampled[:args.limit]
    print(f"catalogs for {len(names)} names; documents for {len(sampled)}", flush=True)
    cache = HERE / "data" / "catalogs.npz"
    if cache.is_file():
        loaded = np.load(cache)
        catalogs = {}
        for key in loaded.files:
            engine, font_name, field = key.split("__")
            catalogs.setdefault((engine, font_name), {})[field] = loaded[key]
        print(f"loaded catalogs {cache}", flush=True)
    else:
        catalogs = build_catalogs(names)
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache, **{
            f"{engine}__{font_name}__{field}": value
            for (engine, font_name), catalog in catalogs.items()
            for field, value in catalog.items()
        })
    documents, failures = build_documents(
        names, ranks, catalogs, sampled, HERE / "data" / "redacted", args.save_all or not args.limit,
    )
    print(f"documents {len(documents)} failures {len(failures)}", flush=True)
    if documents:
        errors = np.array([doc["edge_error_px"] for doc in documents])
        print(f"edge error px median {np.median(errors):.4f} max {errors.max():.4f}", flush=True)
    measurements, attacks, excluded = score(documents, names, prior, log_prior, catalogs)
    classes = exhaustive(names, prior, log_prior, catalogs)
    repeated = repeated_releases(documents, names, log_prior, catalogs)
    scan_rows, scan_summary = simulate_scans(documents, names, log_prior, catalogs)
    summaries, utility, tests = summarize(attacks, measurements)
    write_csv(out / "documents.csv", public_documents(documents))
    write_csv(out / "policy_measurements.csv", measurements)
    write_csv(out / "attacker_results.csv", attacks)
    write_csv(out / "utility_results.csv", utility)
    write_csv(out / "worst_case_results.csv", classes)
    write_csv(out / "repeated_releases.csv", repeated)
    write_csv(out / "scan_results.csv", scan_rows)
    write_csv(out / "redaction_failures.csv", failures)
    write_csv(out / "excluded_masks.csv", excluded)
    payload = {
        "pilot": bool(args.limit),
        "n_names_in_list": len(names),
        "n_sampled_names": len(sampled),
        "n_documents": len(documents),
        "n_failures": len(failures),
        "n_excluded_masks": len(excluded),
        "n_attack_rows": len(attacks),
        "attacks": summaries,
        "utility": utility,
        "tests": tests,
        "scan": scan_summary,
        "edge_tolerance_px": EDGE_TOL,
        "environment": environment(),
        "surname_sha256": g.sha256_bytes(g.SURNAMES.read_bytes()),
    }
    (out / "statistics.json").write_text(json.dumps(payload, indent=2, default=float))
    env_path = HERE / "environment.json"
    env_path.write_text(json.dumps(payload["environment"], indent=2, default=float))
    print(json.dumps({"documents": len(documents), "failures": len(failures), "attacks": summaries[:6], "scan": scan_summary}, indent=2, default=float))


if __name__ == "__main__":
    main()
