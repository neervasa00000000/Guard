"""Share of the 50,000 surnames that a field box sized from the 1,000-name list would not cover (Section 8.2).

Usage:  E1_CENSUS=/path/to/Names_2010Census.csv python research/e1/scripts/field_overflow.py [repo root]
        (optional E1_FONT_DIR = folder with the Table A11 fonts)
Uses the repository's research/e1/e1lib.py and policies.py; fonts and the Census CSV are SHA-256 checked.
Checks every field width and anchor against research/e1/data/knowledge_matched/field_widths.csv before reporting.
Output: field_overflow.csv in the current directory.
"""
import csv, os, sys
from pathlib import Path
import numpy as np

root = (Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]).resolve()
if 'E1_CENSUS' not in os.environ:
    sys.exit('Set E1_CENSUS to the full 2010 Census surname CSV (SHA-256 6b4933...8708).')
sys.path.insert(0, str(root / 'research/e1'))
import e1lib as E
import policies as P

if E.sha256(E.CENSUS) != E.FULL_CENSUS_SHA:
    sys.exit('Census CSV SHA-256 mismatch')
full = E.dict_surnames()
assert len(full['strings']) == 50000
ref = {(r['font'], int(r['size_px'])): r for r in csv.DictReader(open(root / 'research/e1/data/knowledge_matched/field_widths.csv'))}
rows = []
for font in E.FONTS:
    for size in E.SIZES:
        face = E.font(font, size)
        b = np.array([face.getbbox(w, anchor='ls') for w in full['strings']], dtype=np.int64)
        a, d = face.getmetrics()
        p1k = P.prepare(b[:1000], a, d)
        *_, width, widest = P.field_box(p1k)
        r = ref[(font, size)]
        assert width == int(r['width_px']) and full['strings'][widest] == r['widest_from_anchor'] and p1k['x_l'] == int(r['left_rel']), \
            f'{font} {size}px: field width or anchor differs from the archive'
        left, right = b[:, 0] - 1, b[:, 2] + 1
        over = (left < p1k['x_l']) | (right > p1k['x_l'] + width)
        rows.append(dict(font=font, size_px=size, field_width_px=width, n_over=int(over.sum()), share_names=float(over.mean()),
                         prior_mass=float(full['p'][over].sum()), over_left=int((left < p1k['x_l']).sum()),
                         over_right=int((right > p1k['x_l'] + width).sum())))
        print(rows[-1], flush=True)
with open('field_overflow.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
sh = [100 * r['share_names'] for r in rows]; pm = [100 * r['prior_mass'] for r in rows]
print(f'Not covered: {min(sh):.2f}-{max(sh):.2f}% of names, {min(pm):.2f}-{max(pm):.2f}% of prior mass')
