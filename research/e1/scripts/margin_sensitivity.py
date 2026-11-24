"""Start-aligned padding with a 0-, 1- (paper) or 2-px box margin, scored exactly over all 50,000 surnames (Appendix B.2).

Usage:  E1_CENSUS=/path/to/Names_2010Census.csv python research/e1/scripts/margin_sensitivity.py [repo root]
        (optional E1_FONT_DIR = folder with the Table A11 fonts)
The 1-px rows must reproduce research/e1/data/per_person/tail_summary.csv (mean bits and largest pointwise leak) in every cell.
Output: margin_sensitivity.csv in the current directory.
"""
import csv, os, sys
from pathlib import Path
import numpy as np

root = (Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]).resolve()
if 'E1_CENSUS' not in os.environ:
    sys.exit('Set E1_CENSUS to the full 2010 Census surname CSV (SHA-256 6b4933...8708).')
sys.path.insert(0, str(root / 'research/e1'))
import e1lib as E

if E.sha256(E.CENSUS) != E.FULL_CENSUS_SHA:
    sys.exit('Census CSV SHA-256 mismatch')
full = E.dict_surnames()
p = np.asarray(full['p'], dtype=np.float64)
ref = {(r['font'], r['size_px'], int(r['width_px'])): r for r in csv.DictReader(open(root / 'research/e1/data/per_person/tail_summary.csv'))
       if r['policy'] == 'start-aligned'}

def score(k):
    _, inv = np.unique(k, return_inverse=True)
    mass = np.bincount(inv, weights=p)
    pw = np.where(mass >= 1 - 1e-12, 0.0, -np.log2(mass))
    names = np.bincount(inv)
    j = int(np.argmax(pw))
    return float((mass * pw).sum()), float(pw[j]), int(names[j])

rows = []
for font in E.FONTS:
    for size in E.SIZES:
        face = E.font(font, size)
        b = np.array([face.getbbox(w, anchor='ls') for w in full['strings']], dtype=np.int64)
        for m in (0, 1, 2):
            left, right = b[:, 0] - m, b[:, 2] + m
            xl = int(left.min())
            for C in (128, 192, 256):
                mean, mx, nm = score(-((xl - right) // C))
                rows.append(dict(font=font, size_px=size, margin_px=m, C=C, mean_bits=mean, max_pointwise_bits=mx, max_class_names=nm))
                if m == 1:
                    r = ref[(font, str(size), C)]
                    assert abs(mean - float(r['mean_bits'])) < 1e-9 and abs(mx - float(r['max_pointwise_bits'])) < 1e-9, \
                        f'{font} {size}px C={C}: 1-px margin does not reproduce tail_summary.csv'
        print(font, size, 'ok', flush=True)
with open('margin_sensitivity.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
for m in (0, 1, 2):
    for C in (128, 192, 256):
        x = [r for r in rows if r['margin_px'] == m and r['C'] == C]
        worst = max(x, key=lambda r: r['max_pointwise_bits'])
        print(f"margin {m} px, C = {C}: mean over 18 cells {sum(r['mean_bits'] for r in x) / len(x):.4f} bits; "
              f"worst {worst['max_pointwise_bits']:.2f} bits ({worst['max_class_names']} names)")
