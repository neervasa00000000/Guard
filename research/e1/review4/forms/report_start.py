"""Write the mock-form start-aligned padding report from the measured CSVs."""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

LABELS = {"b_lo_table": "Matched", "a_paper_renderer": "Mismatched (Pillow)",
          "A1": "A1 (known start)", "A2": "A2 (unknown start)"}
POLICIES = ["exact", "16px", "64px", "D2_pad128", "start128"]


def read(path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def key(row):
    return tuple(row[field] for field in ("renderer", "size", "condition", "attacker"))


def report(root):
    cells = defaultdict(dict)
    for row in read(root / "start_policy_summary.csv"):
        cells[key(row)][row["policy"]] = row
    paired = {key(row): row for row in read(root / "start_vs_grid16_paired.csv")}
    assert len(cells) == len(paired) == 10 and cells.keys() == paired.keys()
    lines = [
        "# Start-aligned 128 px padding on mock forms", "",
        "Surname top-10 hits per 100 forms, with Wilson 95% intervals. Each paired difference "
        "is the 16 px grid minus start-aligned padding, in percentage points. The interval "
        "resamples the same forms in both policies.", "",
        "| Renderer | Size | Condition | Attacker | Exact | 16 px grid | 64 px grid | "
        "Edge-aligned 128 px | Start-aligned 128 px | Paired difference (95% CI) |",
        "| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for group, policies in sorted(cells.items()):
        renderer, size, condition, attacker = group
        estimates = [
            f"{float(r['hits']):.0f} [{float(r['wilson_low']):.1f}, {float(r['wilson_high']):.1f}]"
            for r in (policies[p] for p in POLICIES)
        ]
        r = paired[group]
        delta = (f"{float(r['difference_points']):+.1f} "
                 f"[{float(r['ci_low']):+.1f}, {float(r['ci_high']):+.1f}]")
        values = [renderer, size, condition, LABELS[attacker], *estimates, delta]
        lines.append("| " + " | ".join(values) + " |")

    lines.extend(["", "Median redacted area divided by the padded tight-box area.", "",
                  "| Renderer | Size | Condition | Exact | 16 px grid | 64 px grid | "
                  "Edge-aligned 128 px | Start-aligned 128 px |",
                  "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |"])
    for group, policies in sorted(cells.items()):
        renderer, size, condition, attacker = group
        if attacker not in ("A1", "b_lo_table"):
            continue
        ratios = [f"{float(policies[p]['median_area_ratio']):.2f}×" for p in POLICIES]
        lines.append("| " + " | ".join([renderer, size, condition, *ratios]) + " |")

    lo = [row for row in read(root / "libreoffice_start_cases.csv") if row["attacker"] == "b_lo_table"]
    assert len(lo) == 400 and len({(r["doc"], r["size"], r["cond"]) for r in lo}) == 400
    clipped = [r for r in lo if r["covers_tight_box"] != "True"]
    ink_clipped = [r for r in lo if int(r["missed_ink_bbox_px"]) > 0]
    shifted = [r for r in lo if r["layout_start_x"] != r["published_pen_x"]]
    lines.extend([
        "",
        f"The template-derived start differs from the rounded PDF-origin start in {len(shifted)} "
        f"of {len(lo)} LibreOffice observations. Start-aligned padding contains the full padded "
        f"tight box in {len(lo)-len(clipped)} observations and the measured ink bounds in "
        f"{len(lo)-len(ink_clipped)}. The scores use the specified fixed policy on every form.",
        "",
        "The LibreOffice controls are the archived policies, checked against the regenerated "
        "forms. The new policy uses the margin plus the template tab stop as the pen column "
        "and maps it through the known page rotation for scan-like forms. The anchor offset "
        "is the minimum left offset of the matched surname dictionary minus one pixel. "
        "The width rounds the span to the padded right edge up to a multiple of 128 px. "
        "The full line uses the font metrics expanded to candidate extrema plus one pixel "
        "on each side, as in review4. Both attackers receive the same policy geometry. "
        "Each attacker's candidate right edge uses its original renderer and calibrated "
        "tolerance. Candidate filtering retains the original prior ranking and tie handling.",
        "",
        "**Start recovery from a standalone scan is untested.**",
        "",
        "The Pillow clean replay uses the available LAYOUT-BOX scorer for A1 and A2. Its "
        "original exact and grid controls and A1 edge-padding control match the archive. "
        "The A2 edge-padding count is a replay because the corresponding archived count "
        "was absent.",
        "",
        "The paired bootstrap uses 4,000 resamples with seed 20261117. The form, scan and "
        "calibration seeds are documented with the replay setup. "
        "[Replay setup](FORMS_RESULTS.md) · [Run log](start_replay.log)",
        "",
        "```sh",
        'sh research/e1/review4/forms/run_replay.sh \\',
        '  /private/tmp/tileseal-review4.EKJJXk "$PWD/Rerun/e1_fonts" \\',
        '  "$HOME/tileseal-t3-lm/csv/test3_docs.json" start \\',
        '  > research/e1/review4/forms/start_replay.log 2>&1',
        'python3 research/e1/review4/forms/report_start.py research/e1/review4/forms',
        "```",
        "",
        "[Policy summary CSV](start_policy_summary.csv) · "
        "[Paired differences CSV](start_vs_grid16_paired.csv) · "
        "[LibreOffice cases](libreoffice_start_cases.csv) · [Pillow cases](pillow_start_cases.csv)",
        "",
    ])
    (root / "FORMS_START_RESULTS.md").write_text("\n".join(lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    report(parser.parse_args().output)
