"""Check the documented LibreOffice tab stop against regenerated text origins."""
import argparse
import csv
from collections import Counter
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("observations", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
with args.observations.open(newline="") as handle:
    rows = list(csv.DictReader(handle))

counts = Counter()
with args.output.open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=[
        "doc", "font", "size_px", "field", "layout_start", "pdf_start_rounded", "match",
    ])
    writer.writeheader()
    for row in rows:
        if row["cond"] != "clean":
            continue
        size = int(row["size"])
        # The generator declares these tab stops for the two page templates.
        layout_start = int(row["margin"]) + {16: 200, 24: 300}[size]
        pdf_start = int(row["pen_x"])
        match = layout_start == pdf_start
        counts[size, match] += 1
        writer.writerow(dict(doc=row["doc"], font=row["font"], size_px=size, field="surname",
                             layout_start=layout_start, pdf_start_rounded=pdf_start, match=match))

for size in sorted({size for size, _ in counts}):
    good, bad = counts[size, True], counts[size, False]
    print(f"{size} px: {good}/{good + bad} layout starts match rounded PDF starts")
