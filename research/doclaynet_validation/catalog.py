"""Glyph catalogs for the matched renderer and the mismatch attackers.

Pillow is the renderer that paints the insertion. PyMuPDF measures the
same font file with a different rasterizer. getbbox is recorded only as
a diagnostic; the scored boxes use painted pixels.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import numpy as np
from PIL import Image, ImageDraw, ImageFont

CACHE = Path(__file__).resolve().parent / "cache"


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pillow_ink(font, text):
    """Half-open ink edges relative to a baseline pen. Painted pixels only."""
    left, top, right, bottom = font.getbbox(text, anchor="ls")
    pad = 2
    width = max(1, int(right - left + 2 * pad))
    height = max(1, int(bottom - top + 2 * pad))
    image = Image.new("L", (width, height), 0)
    origin_x = pad - int(left)
    origin_y = pad - int(top)
    ImageDraw.Draw(image).text((origin_x, origin_y), text, fill=255, font=font, anchor="ls")
    ys, xs = np.nonzero(np.asarray(image) > 0)
    if len(xs) == 0:
        return None
    return (
        int(xs.min() - origin_x),
        int(ys.min() - origin_y),
        int(xs.max() + 1 - origin_x),
        int(ys.max() + 1 - origin_y),
    )


def pillow_catalog(font_path, size, names):
    font_path = str(font_path)
    digest = file_sha256(font_path)[:16]
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"pillow_{digest}_{int(size)}.npy"
    if path.exists():
        stored = np.load(path)
        if stored.shape[0] == len(names):
            return stored
    font = ImageFont.truetype(font_path, int(size))
    rows = []
    for name in names:
        box = pillow_ink(font, name)
        if box is None:
            raise RuntimeError(f"Pillow painted no pixels for {name}")
        rows.append(box)
    array = np.asarray(rows, dtype=np.int64)
    np.save(path, array)
    return array


def mupdf_catalog(font_path, size, names):
    """Ink edges from one PyMuPDF pixmap of the same font file."""
    font_path = str(font_path)
    digest = file_sha256(font_path)[:16]
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"mupdf_{digest}_{int(size)}.npy"
    if path.exists():
        stored = np.load(path)
        if stored.shape[0] == len(names):
            return stored
    columns = 5
    cell_w, cell_h = 420, 64
    rows_n = int(np.ceil(len(names) / columns))
    document = fitz.open()
    page = document.new_page(width=columns * cell_w, height=rows_n * cell_h)
    page.insert_font(fontname="F", fontfile=font_path)
    pens = []
    for index, name in enumerate(names):
        row, column = divmod(index, columns)
        pen_x = column * cell_w + 16
        baseline = row * cell_h + 42
        page.insert_text((pen_x, baseline), name, fontname="F", fontsize=int(size), color=(0, 0, 0))
        pens.append((pen_x, baseline))
    pixmap = page.get_pixmap(matrix=fitz.Matrix(1, 1), colorspace=fitz.csGRAY, alpha=False)
    pixels = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width)
    ink = pixels < 200
    catalog = np.zeros((len(names), 4), dtype=np.int64)
    for index, (pen_x, baseline) in enumerate(pens):
        row, column = divmod(index, columns)
        x0 = column * cell_w
        y0 = row * cell_h
        cell = ink[y0:y0 + cell_h, x0:x0 + cell_w]
        ys, xs = np.nonzero(cell)
        if len(xs) == 0:
            raise RuntimeError(f"PyMuPDF painted no pixels for {names[index]}")
        if xs.min() <= 0 or ys.min() <= 0 or xs.max() >= cell_w - 1 or ys.max() >= cell_h - 1:
            raise RuntimeError(f"PyMuPDF ink touched the cell edge for {names[index]}")
        catalog[index] = (
            int(xs.min() + x0 - pen_x),
            int(ys.min() + y0 - baseline),
            int(xs.max() + 1 + x0 - pen_x),
            int(ys.max() + 1 + y0 - baseline),
        )
    document.close()
    np.save(path, catalog)
    return catalog


def paste_ink(page_shape, pen_x, baseline, font, text):
    """Boolean page mask of the pixels Pillow will paint."""
    mask = Image.new("L", (page_shape[1], page_shape[0]), 0)
    ImageDraw.Draw(mask).text((int(pen_x), int(baseline)), text, fill=255, font=font, anchor="ls")
    return np.asarray(mask) > 0
