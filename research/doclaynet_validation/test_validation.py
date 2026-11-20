"""Checks that do not need the DocLayNet corpus."""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalog
import geometry


FONT = Path(catalog.__file__).resolve().parents[2]
# matplotlib's DejaVu is resolved the same way as the experiment.
import matplotlib

FONT = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans.ttf"


def test_snap_matches_guard():
    rng = np.random.default_rng(20261118)
    for _ in range(50):
        x0, y0 = rng.integers(0, 400, size=2)
        x1 = int(x0 + rng.integers(5, 80))
        y1 = int(y0 + rng.integers(5, 40))
        for grid in (16, 64):
            got = tuple(int(v) for v in geometry.guard_rw.snap_out((int(x0), int(y0), int(x1), int(y1)), grid))
            other = geometry.guard_rw.snap_out((x0, y0, x1, y1), grid)
            assert got == tuple(int(v) for v in other)


def test_square_policy_matches_snap_of_exact():
    names = ["SMITH", "NG", "WILLIAMSON"]
    boxes = catalog.pillow_catalog(FONT, 16, names)
    pen_x, baseline = 100, 200
    left = pen_x + boxes[:, 0]
    top = baseline + boxes[:, 1]
    right = pen_x + boxes[:, 2]
    bottom = baseline + boxes[:, 3]
    exact, _, _, _ = geometry.policy_edges("exact", left, top, right, bottom)
    square, _, _, _ = geometry.policy_edges("square16", left, top, right, bottom)
    for index in range(len(names)):
        snapped = geometry.guard_rw.snap_out(
            tuple(int(edge[index]) for edge in exact), 16
        )
        assert tuple(int(edge[index]) for edge in square) == tuple(int(v) for v in snapped)


def test_field_boxes_are_identical_and_leak_nothing():
    names = ["SMITH", "BROWN", "NG", "GARCIA", "LEE"]
    counts = np.array([50, 20, 5, 10, 8], dtype=np.float64)
    prior = counts / counts.sum()
    boxes = catalog.pillow_catalog(FONT, 16, names)
    pen_x, baseline = 80, 150
    left = pen_x + boxes[:, 0]
    top = baseline + boxes[:, 1]
    right = pen_x + boxes[:, 2]
    bottom = baseline + boxes[:, 3]
    edges, _, _, _ = geometry.policy_edges("field", left, top, right, bottom)
    stacked = np.stack(edges, axis=1)
    assert np.all(stacked == stacked[:1])
    observed = stacked[0]
    match = np.all(stacked == observed, axis=1)
    out = geometry.guard_rw.possibilistic(match, np.log(prior), 3)
    assert out["entropy_reduction"] == 0.0
    assert out["feasible"] == len(names)
    assert out["hit10"] == geometry.guard_rw.expected_hit(np.log(prior), 3, 10)


def test_painted_surname_is_covered_by_exact_box():
    names = ["SMITH"]
    boxes = catalog.pillow_catalog(FONT, 16, names)
    page = np.zeros((80, 200), dtype=bool)
    font = ImageFont.truetype(str(FONT), 16)
    pen_x, baseline = 30, 40
    ink = catalog.paste_ink((80, 200), pen_x, baseline, font, "SMITH")
    assert int(ink.sum()) > 20
    left = np.array([pen_x + boxes[0, 0]])
    top = np.array([baseline + boxes[0, 1]])
    right = np.array([pen_x + boxes[0, 2]])
    bottom = np.array([baseline + boxes[0, 3]])
    edges, _, _, _ = geometry.policy_edges("exact", left, top, right, bottom)
    box = tuple(int(edge[0]) for edge in edges)
    assert geometry.ink_outside(ink, box) == 0
    ys, xs = np.nonzero(ink)
    assert xs.min() == pen_x + boxes[0, 0]
    assert ys.min() == baseline + boxes[0, 1]


def test_start_unknown_square_contains_true_size():
    box = (100, 40, 137, 62)
    snapped = tuple(int(v) for v in geometry.guard_rw.snap_out(box, 16))
    width = box[2] - box[0]
    height = box[3] - box[1]
    found = geometry.square_start_unknown([width], [height], snapped, 16, 1025, 1025)
    assert bool(found[0])
    missing = geometry.square_start_unknown([width + 40], [height + 30], snapped, 16, 1025, 1025)
    assert not bool(missing[0])


def test_verifier_accepts_the_drawn_string_only():
    from run_experiment import verify_render

    image = Image.new("RGB", (240, 80), (255, 255, 255))
    font = ImageFont.truetype(str(FONT), 16)
    ImageDraw.Draw(image).text((40, 50), "SMITH", fill=(0, 0, 0), font=font, anchor="ls")
    rgb = np.asarray(image)
    fonts = {"DejaVuSans": FONT}
    accepted, detail = verify_render(rgb, (30, 20, 120, 70), "SMITH", fonts, sizes=(16,))
    rejected, other = verify_render(rgb, (30, 20, 120, 70), "CHRISTOPHERSON", fonts, sizes=(16,))
    assert accepted, detail
    assert not rejected, other


def test_tracks_cannot_share_a_label():
    from run_experiment import separation_problems

    rows = [
        {"track": "controlled_insertion", "text_origin": "controlled_insertion", "string": "SMITH"},
        {"track": "verified_original", "text_origin": "verified_original", "string": "SMITH"},
    ]
    assert separation_problems(rows) == []
    mixed = [{"track": "verified_original", "text_origin": "controlled_insertion", "string": "SMITH"}]
    assert separation_problems(mixed)
