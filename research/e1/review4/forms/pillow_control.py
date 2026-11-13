"""Replay available Pillow surname controls against the kit's audit."""

import csv
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, "/workspace/guard-paper/results/e1-full/scripts")
import e1lib as E


def main():
    control = Path("/kit/v5.7-ieee/new_tests_posterior/csv/mock_a2_exact_cases.csv")
    with control.open() as handle:
        audit = {(int(r["doc"]), int(r["grid_px"])): r for r in csv.DictReader(handle)}
    docs = json.loads(Path("/test3_docs.json").read_text())
    assert {row["doc"] for row in docs} == set(range(100))
    d = E.get_dict("surnames")
    logp = np.log2(d["p"])
    cells, padded_cells = {}, {}
    for font in sorted({form["font"] for form in docs}):
        bounds = E.geometry("surnames", font, 16)
        cells[font] = E.Cell(bounds, ((0, 0),) * 4, 0)
        padded_cells[font] = E.Cell(E.bucket_transform(bounds, font, 16), ((0, 0),) * 4, 0)
    results = []
    for form in docs:
        doc, font, target = form["doc"], form["font"], form["surname_idx"]
        truth = form["surname"]
        assert d["strings"][target] == truth
        px, py = form["margin"] + 200, 200
        bbox = E.font(font, 16).getbbox(truth, anchor="ls")
        for policy, grid in (("exact", 1), ("16px", 16), ("64px", 64), ("D2_bucket128", 1)):
            padding = policy == "D2_bucket128"
            offsets = E.bucket_box(bbox, font, 16) if padding else bbox
            obs = [E.snapped(E.tight_box(offsets, px, py, 0, None), grid)]
            cell = (padded_cells if padding else cells)[font]
            for attacker in ("A1", "A2"):
                feasible = cell.feasible(obs, [(px if attacker == "A1" else 0, py)], grid, attacker)
                result = E.metrics(d, feasible, target, len(truth), logp)
                archived = None
                if attacker == "A2" and not padding:
                    row = audit[doc, grid]
                    assert row["font"] == font and row["match_published"] == "True"
                    archived = float(row["hit10_pub"])
                results.append(dict(doc=doc, font=font, policy=policy, attacker=attacker,
                                    hit10=result["hit10"], archived_hit10=archived))
    # The archived renderer-2 report quotes the four Pillow A1 surname cells.
    a1 = dict(zip(("exact", "16px", "64px", "D2_bucket128"), (52, 12, 8, 10)))
    with open("/out/pillow_surname_sanity.csv", "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "attacker", "policy", "n", "replay_hits", "archived_hits", "delta_hits", "reference",
        ])
        writer.writeheader()
        failed = False
        for attacker in ("A1", "A2"):
            for policy in a1:
                rows = [r for r in results if r["policy"] == policy and r["attacker"] == attacker]
                replay = sum(r["hit10"] for r in rows)
                if attacker == "A1":
                    archived, ref = a1[policy], "renderer2 RESULTS.md, T3 reference"
                    mismatch = abs(replay - archived) > 0.05
                elif policy != "D2_bucket128":
                    archived = sum(r["archived_hit10"] for r in rows)
                    ref = "mock_a2_exact_cases.csv"
                    mismatch = any(abs(r["hit10"] - r["archived_hit10"]) > 1e-9 for r in rows)
                else:
                    archived, ref, mismatch = None, "Archived A2 padding reference absent", False
                delta = replay - archived if archived is not None else None
                writer.writerow(dict(attacker=attacker, policy=policy, n=len(rows),
                                     replay_hits=replay, archived_hits=archived,
                                     delta_hits=delta, reference=ref))
                failed |= mismatch
    if failed:
        raise SystemExit("Pillow surname controls differ from archived reference")
    print("Available Pillow clean surname controls match")


if __name__ == "__main__":
    main()
