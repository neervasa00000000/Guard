"""How common padding singletons are across anchor offsets (Section 6.2).

Start-aligned padding with its anchor moved left by d = 0, 1, ..., C-1 px (every class-boundary phase), scored exactly
over all 50,000 Census surnames in the 18 font-size cells. A singleton is a class holding one name.
Usage:  E1_CENSUS=/path/to/Names_2010Census.csv python anchor_offsets.py [repo root]
Checks: d = 0 reproduces research/e1/data/per_person/tail_summary.csv (mean bits, largest pointwise leak) and
d = 2, 4, 8, 16 reproduce the clean rows of data/anchor_margin/summary.csv (singletons, singleton mass, mean bits).
Output: anchor_offsets.csv (one row per cell, C and offset) in the current directory.
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
tail = {(r['font'], r['size_px'], int(r['width_px'])): r for r in csv.DictReader(open(root / 'research/e1/data/per_person/tail_summary.csv'))
        if r['policy'] == 'start-aligned'}
am = {(r['font'], r['size_px'], int(r['margin_px']), int(r['C_px'])): r for r in csv.DictReader(open(root / 'data/anchor_margin/summary.csv'))
      if r['policy'] == 'start-aligned' and r['template_error'] == 'clean'}
rows = []; checks = 0
for font in E.FONTS:
    for size in E.SIZES:
        face = E.font(font, size)
        b = np.array([face.getbbox(w, anchor='ls') for w in full['strings']], dtype=np.int64)
        right = b[:, 2] + E.PAD; xl = int(b[:, 0].min()) - E.PAD
        for C in (64, 96, 128, 192, 256):
            for d in range(C):
                k = -((xl - d - right) // C)
                _, inv = np.unique(k, return_inverse=True)
                mass = np.bincount(inv, weights=p); names = np.bincount(inv)
                pw = np.where(mass >= 1 - 1e-12, 0.0, -np.log2(mass))
                single = names == 1
                r = dict(font=font, size_px=size, C=C, offset_px=d, mean_bits=float((mass * pw).sum()),
                         max_pointwise_bits=float(pw.max()), n_singletons=int(single.sum()),
                         singleton_mass=float(mass[single].sum()), singleton_in_top_class=int(bool(single[-1])) if single.any() else 0,
                         names_in_classes_lt10=int(names[names < 10].sum()))
                rows.append(r)
                if d == 0 and (font, str(size), C) in tail:
                    t = tail[(font, str(size), C)]
                    assert abs(r['mean_bits'] - float(t['mean_bits'])) < 1e-9 and abs(r['max_pointwise_bits'] - float(t['max_pointwise_bits'])) < 1e-9
                    checks += 1
                if (font, str(size), d, C) in am:
                    a = am[(font, str(size), d, C)]
                    assert r['n_singletons'] == round(float(a['n_singletons'])) and abs(r['singleton_mass'] - float(a['singleton_mass'])) < 1e-12 \
                        and abs(r['mean_bits'] - float(a['avg_bits'])) < 1e-9, (font, size, d, C)
                    checks += 1
        print(font, size, 'ok', flush=True)
with open('anchor_offsets.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print('archive checks passed:', checks)
for C in (64, 96, 128, 192, 256):
    x = [r for r in rows if r['C'] == C]
    n_off = len(x); with_s = sum(r['n_singletons'] > 0 for r in x)
    cells = {(r['font'], r['size_px']) for r in x if r['n_singletons'] > 0}
    print(f"C = {C}: {with_s} of {n_off} cell-offset pairs ({100*with_s/n_off:.2f}%) had a singleton; cells affected {len(cells)} of 18; "
          f"mean singleton prior mass per pair {np.mean([r['singleton_mass'] for r in x]):.3e}; "
          f"mean names in singleton classes per pair {np.mean([r['n_singletons'] for r in x]):.4f}")
