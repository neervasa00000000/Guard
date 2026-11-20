"""Geometry and posterior checks. These do not score the experiment."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research" / "realworld_validation" / "src"))
sys.path.insert(0, str(ROOT / "research" / "e1"))

import guard_rw as g
import policies


def test_ceil_matches_manuscript():
    values = np.array([1, 16, 17, 64, 65, 128])
    for step in (16, 64, 128):
        assert np.array_equal(g.ceil_multiple(values, step), policies.ceil_multiple(values, step))


def test_exact_and_square_contain_the_glyph():
    ink = (100.2, 40.4, 174.8, 58.1)
    exact = g.policy_box("exact", ink, 0, 0, 0)
    assert exact[0] <= ink[0] and exact[1] <= ink[1]
    assert exact[2] >= ink[2] and exact[3] >= ink[3]
    square = g.policy_box("square16", ink, 0, 0, 0)
    assert square[0] <= exact[0] and square[1] <= exact[1]
    assert square[2] >= exact[2] and square[3] >= exact[3]
    assert square[0] % 16 == 0 and square[1] % 16 == 0


def test_field_box_is_identical_and_covers_both_names():
    left = np.array([100.0, 100.2])
    top = np.array([40.0, 41.0])
    right = np.array([140.0, 180.5])
    bottom = np.array([55.0, 56.0])
    x_l, line_top, line_bottom = g.shared_frame(left, top, right, bottom)
    box = g.candidate_boxes("field", left, top, right, bottom, x_l, line_top, line_bottom)
    assert box[0][0] == box[0][1] and box[2][0] == box[2][1]
    assert box[0][0] <= left.min() and box[2][0] >= right.max()
    assert box[1][0] <= top.min() and box[3][0] >= bottom.max()


def test_start_aligned_matches_manuscript_on_integer_glyphs():
    # Glyph edges already in the manuscript's pen-relative integer frame.
    bounds = np.array([[10, -8, 40, 3], [10, -8, 55, 3]], dtype=np.int64)
    prep = policies.prepare(bounds, 8, 3)
    left, top, right, bottom = policies.start_aligned_padding(prep, 64)
    page_left = bounds[:, 0].astype(np.float64)
    page_top = bounds[:, 1].astype(np.float64)
    page_right = bounds[:, 2].astype(np.float64)
    page_bottom = bounds[:, 3].astype(np.float64)
    x_l, line_top, line_bottom = g.shared_frame(page_left, page_top, page_right, page_bottom)
    box = g.candidate_boxes("width64", page_left, page_top, page_right, page_bottom, x_l, line_top, line_bottom)
    assert np.array_equal(box[0], left)
    assert np.array_equal(box[2], right)


def test_posterior_is_a_distribution_and_ties_split():
    log_prior = np.log(np.array([0.5, 0.3, 0.2]))
    everyone = g.possibilistic(np.array([True, True, True]), log_prior, 0)
    assert everyone["hit1"] == 1
    assert everyone["entropy_reduction"] == pytest.approx(0, abs=1e-9)
    pair = g.possibilistic(np.array([True, True, False]), log_prior, 0)
    assert pair["hit1"] == 1
    assert pair["truth_in_set"] is True
    assert pair["pointwise_bits"] == pytest.approx(-np.log2(0.8))
    missed = g.possibilistic(np.array([True, True, False]), log_prior, 2)
    assert missed["hit1"] == 0 and missed["hit10"] == 0
    empty = g.possibilistic(np.array([False, False, False]), log_prior, 2)
    assert empty["empty"] is True
    assert empty["hit1"] == g.expected_hit(log_prior, 2, 1)
    tied = np.log(np.array([0.25, 0.25, 0.25, 0.25]))
    both = g.possibilistic(np.array([True, True, False, False]), tied, 0)
    assert both["hit1"] == pytest.approx(0.5)


def test_sample_is_deterministic_and_without_replacement():
    names, counts, ranks = g.load_surnames()
    assert counts[0] >= counts[-1]
    assert ranks[0] == 1
    # Six census ranks are shared by two rows, so rank is not a row number.
    assert len(set(ranks.tolist())) < len(names)
    a, _ = g.sample_names(names, counts)
    b, _ = g.sample_names(names, counts)
    assert a == b
    assert len(a) == len(set(a)) == 100


def test_split_does_not_use_the_engine():
    assert g.assign_split("SMITH") == g.assign_split("SMITH")
    assert g.assign_split("SMITH") in {"calibration", "test"}


@pytest.mark.skipif(not Path(g.FONTS["Times"]).is_file(), reason="Times New Roman is not installed")
def test_reportlab_redaction_removes_the_surname():
    pymupdf = pytest.importorskip("pymupdf")
    pytest.importorskip("reportlab")
    from pypdf import PdfReader
    import io
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    pdfmetrics.registerFont(TTFont("Times", g.FONTS["Times"]))
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=g.PAGE)
    pdf.setFont("Times", 12)
    pdf.drawString(72, 700, "SMITH")
    pdf.drawString(72, 680, "Case No. CV-2026-1042")
    pdf.save()
    doc = pymupdf.open(stream=buffer.getvalue(), filetype="pdf")
    span = [s for b in doc[0].get_text("dict")["blocks"] for ln in b.get("lines", []) for s in ln["spans"] if s["text"] == "SMITH"][0]
    assert "Times" in span["font"]
    rect = pymupdf.Rect(span["bbox"])
    rect.x0 -= 1
    rect.y0 -= 1
    rect.x1 += 1
    rect.y1 += 1
    doc[0].add_redact_annot(rect, fill=(0, 0, 0))
    doc[0].apply_redactions()
    data = doc.tobytes()
    doc.close()
    reopened = pymupdf.open(stream=data, filetype="pdf")
    text = reopened[0].get_text()
    reopened.close()
    assert "SMITH" not in text
    assert "CV-2026-1042" in text
    assert "SMITH" not in (PdfReader(io.BytesIO(data)).pages[0].extract_text() or "")
