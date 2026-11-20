"""Unit, fixture, and artifact checks for the FUNSD validation."""
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "funsd_validation"))
import funsd_real as real


def test_ceil_matches_the_paper_helper():
    spec = importlib.util.spec_from_file_location("policies", ROOT / "research" / "e1" / "policies.py")
    policies = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policies)
    values = np.array([1, 32, 33, 128])
    assert np.array_equal(real.ceil_multiple(values, 32), policies.ceil_multiple(values, 32))


def test_square_grid_contains_the_exact_box_and_grows_area():
    exact = (10, 20, 31, 44)
    snapped = real.square_grid_box(exact, 16)
    assert snapped[0] <= exact[0] and snapped[1] <= exact[1]
    assert snapped[2] >= exact[2] and snapped[3] >= exact[3]
    assert (snapped[2] - snapped[0]) * (snapped[3] - snapped[1]) >= (exact[2] - exact[0]) * (exact[3] - exact[1])


def test_width_grid_interval_and_start_aligned_identity():
    exact = (5, 4, 40, 20)
    low, high = real.feasible_widths("width_grid", exact, 32)
    assert high == 64  # ceil(35 / 32) * 32, width is 35? 40-5=35, ceil to 64
    assert low == 64 - 32 + 1
    assert real.width_grid_box(exact, 32) == real.policy_half_open("start_aligned", exact, 32)
    assert real.feasible_widths("start_aligned", exact, 32) == (low, high)


def test_expected_hit_splits_ties():
    scores = np.log(np.array([0.4, 0.4, 0.2]))
    assert real.expected_hit(scores, 0, 1) == pytest.approx(0.5)
    assert real.expected_hit(scores, 0, 10) == pytest.approx(1.0)
    assert real.expected_hit(scores, -1, 1) == 0.0


def test_absent_truth_has_no_information_gain():
    scored = real.score_observations(
        [20], [20], ["missing"], ["known"], np.array([20.0]), 2.0, np.array([0.0])
    )
    assert scored.loc[0, "hit1"] == 0.0
    assert math.isnan(scored.loc[0, "truth_info_gain_bits"])


def test_wide_bin_does_not_manufacture_leakage():
    prior = np.array([0.7, 0.3])
    scored = real.score_observations(
        [-1e6], [1e6], ["a"], ["a", "b"], np.array([10.0, 30.0]), 5.0, np.log(prior)
    )
    assert scored.loc[0, "entropy_reduction_bits"] == pytest.approx(0.0, abs=1e-6)
    assert scored.loc[0, "truth_info_gain_bits"] == pytest.approx(0.0, abs=1e-6)
    assert scored.loc[0, "hit1"] == pytest.approx(1.0)


def test_posterior_uses_only_candidates():
    scored = real.score_observations(
        [10], [10], ["secret"], ["other"], np.array([10.0]), 1.0, np.array([0.0])
    )
    assert scored.loc[0, "top_is_truth"] == False
    assert scored.loc[0, "in_list"] == False


def test_normal_bin_matches_math_erf():
    probability = math.exp(real.log_normal_bin(np.array([-0.5]), np.array([0.5]), np.array([0.0]), 1.0)[0])
    scale = math.sqrt(2.0)
    reference = 0.5 * (math.erf(0.5 / scale) - math.erf(-0.5 / scale))
    assert probability == pytest.approx(reference, rel=1e-6)


def test_exclusion_rules_reject_multiline_and_vertical_text():
    image = (100, 100)
    multiline = {
        "text": "two lines",
        "box": [0, 0, 40, 40],
        "words": [
            {"text": "two", "box": [0, 0, 20, 10]},
            {"text": "lines", "box": [0, 20, 30, 30]},
        ],
    }
    assert real.exclusion_reason(multiline, image) == "multiline"
    vertical = {"text": "ID", "box": [0, 0, 8, 40], "words": [{"text": "ID", "box": [0, 0, 8, 40]}]}
    assert real.exclusion_reason(vertical, image) == "vertical_entity"


def test_paint_covers_ink_and_leaves_the_margin():
    gray = np.full((30, 40), 255, dtype=np.uint8)
    gray[10:16, 8:20] = 0
    exact = (8, 10, 20, 16)
    check = real.paint_check(gray, exact, exact)
    assert check["covered"]
    larger = (0, 0, 30, 24)
    assert real.paint_check(gray, exact, larger)["covered"]
    short = (12, 10, 20, 16)
    assert not real.paint_check(gray, exact, short)["covered"]


def test_csv_roundtrip_keeps_na_and_numeric_strings(tmp_path):
    frame = real.pd.DataFrame({
        "text": ["NA", "100", "None"],
        "doc_id": ["0007", "0008", "0009"],
        "count": [1, 2, 3],
    })
    path = tmp_path / "candidates.csv"
    real.write_frame(frame, path)
    loaded = real.read_table(path)
    assert loaded["text"].tolist() == ["NA", "100", "None"]
    assert loaded["doc_id"].tolist() == ["0007", "0008", "0009"]
    assert loaded["count"].tolist() == [1, 2, 3]


def _write_form(directory, split, doc_id, answers):
    folder = directory / split
    (folder / "annotations").mkdir(parents=True)
    (folder / "images").mkdir(parents=True)
    image = Image.new("L", (240, 80), 255)
    draw = ImageDraw.Draw(image)
    form = []
    for index, (text, box) in enumerate(answers):
        draw.rectangle((box[0] + 1, box[1] + 1, box[2] - 1, box[3] - 1), fill=0)
        form.append({
            "id": index,
            "box": list(box),
            "text": text,
            "label": "answer",
            "words": [{"box": list(box), "text": text}],
            "linking": [],
        })
    image.save(folder / "images" / f"{doc_id}.png")
    (folder / "annotations" / f"{doc_id}.json").write_text(json.dumps({"form": form}))


def test_fixture_separates_splits_and_covers_ink(tmp_path):
    root = tmp_path / "dataset"
    _write_form(root, "training_data", "train_a", [
        ("A", [10, 20, 29, 34]),
        ("BBB", [40, 20, 79, 34]),
        ("CCCCC", [90, 20, 149, 34]),
        ("DDDDDDD", [160, 20, 229, 34]),
    ])
    _write_form(root, "testing_data", "test_a", [
        ("A", [10, 20, 29, 34]),
        ("ZZZZZ", [40, 20, 99, 34]),
    ])
    audit, fields = real.load_pages(root)
    assert audit["train_test_stem_overlap"] == []
    assert int(fields["eligible"].sum()) == 6
    coverage = real.coverage_table(fields, root)
    assert bool(coverage["covered"].all())
    train = fields[(fields["eligible"]) & (fields["split"] == "training")]
    candidates = real.training_candidates(train)
    assert set(candidates["text"]) == {"A", "BBB", "CCCCC", "DDDDDDD"}
    model = real.fit_length_model(train)
    assert model["status"] == "ok"
    assert model["slope"] > 0
    test = fields[(fields["eligible"]) & (fields["split"] == "testing")]
    policies = real.policy_table(fields)
    observed = policies[(policies["split"] == "testing") & (policies["policy"] == "exact")]
    merged = test[["text", "doc_id", "entity_id"]].merge(observed, on=["doc_id", "entity_id"])
    means = model["intercept"] + model["slope"] * candidates["length"].to_numpy(float)
    scored = real.score_observations(
        merged["bin_lo"], merged["bin_hi"], merged["text"].tolist(),
        candidates["text"].tolist(), means, model["sigma"], np.log(candidates["prior"].to_numpy(float)),
    )
    by_text = dict(zip(merged["text"], scored["in_list"]))
    assert by_text["A"] == True
    assert by_text["ZZZZZ"] == False
    hidden = scored.loc[~scored["in_list"], "truth_info_gain_bits"]
    assert hidden.isna().all()


def test_saved_funsd_summary_matches_scores_when_present():
    summary_path = ROOT / "research" / "funsd_validation" / "out" / "summary.csv"
    scores_path = ROOT / "research" / "funsd_validation" / "out" / "scores.csv"
    if not summary_path.is_file() or not scores_path.is_file():
        pytest.skip("FUNSD outputs have not been generated")
    summary = real.read_table(summary_path)
    scores = real.read_table(scores_path)
    row = summary[(summary["regime"] == "length_width") & (summary["policy"] == "exact")].iloc[0]
    exact = scores[(scores["regime"] == "length_width") & (scores["policy"] == "exact")]
    assert float(exact["hit1"].mean()) == pytest.approx(float(row["top1"]))
    assert float(exact["hit10"].mean()) == pytest.approx(float(row["top10"]))
    assert float(exact["entropy_reduction_bits"].mean()) == pytest.approx(float(row["entropy_reduction"]))
    verification = json.loads((summary_path.parent / "verification.json").read_text()) if (summary_path.parent / "verification.json").is_file() else None
    if verification is not None:
        assert verification["n_failed"] == 0
