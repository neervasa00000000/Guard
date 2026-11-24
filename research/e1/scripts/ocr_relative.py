"""FUNSD OCR drop of each policy relative to the exact box on the same redactions (Section 7.4; Table A14).
Input: research/area_eval/results/per_page.csv. Pooled word counts as in run_area_eval.py;
95% CI: 10,000 page resamples (seed 20261121), paired by redaction.
Check: every policy's drop reproduces ocr_drop_points in research/area_eval/results/summary.csv.
Usage:  python ocr_relative.py [repo root]   Output: ocr_relative.csv in the current directory."""
import sys, numpy as np, pandas as pd
from pathlib import Path
root = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[3])
d = pd.read_csv(f'{root}/research/area_eval/results/per_page.csv')
def drop(g):  # points
    n = g.ocr_eval_words.sum()
    return 100 * (g.ocr_correct_unredacted_visible.sum() - g.ocr_correct.sum()) / n
summ = pd.read_csv(f'{root}/research/area_eval/results/summary.csv').set_index('policy')
for p, g in d.groupby('policy'):
    assert abs(drop(g) - float(summ.loc[p, 'ocr_drop_points'])) < 1e-9, ('archived drop not reproduced', p)
    print(f'{p:20s} n={len(g)} drop={drop(g):.3f} (matches summary.csv)')
ex = d[d.policy == 'exact'].set_index(['page_id', 'target_id'])
rows = []
rng = np.random.default_rng(20261121)
pages = d.page_id.unique()
for p in ['grid-16', 'grid-64', 'start-aligned-128', 'field-1000']:
    g = d[d.policy == p].set_index(['page_id', 'target_id'])
    e = ex.loc[g.index]
    diff = drop(g.reset_index()) - drop(e.reset_index())
    # page-level sums for bootstrap
    cols = ['ocr_eval_words', 'ocr_correct', 'ocr_correct_unredacted_visible']
    gs = g.reset_index().groupby('page_id')[cols].sum(); es = e.reset_index().groupby('page_id')[cols].sum()
    pg = gs.index.values; G = gs.values; E = es.loc[pg].values
    idx = rng.integers(0, len(pg), size=(10000, len(pg)))
    def dd(M, I):
        s = M[I].sum(axis=1)
        return 100 * (s[:, 2] - s[:, 1]) / s[:, 0]
    bs = dd(G, idx) - dd(E, idx)
    lo, hi = np.percentile(bs, [2.5, 97.5])
    rows.append(dict(policy=p, n_redactions=len(g), n_pages=len(pg), drop_policy=drop(g.reset_index()),
                     drop_exact_same=drop(e.reset_index()), extra_drop=diff, ci_lo=lo, ci_hi=hi))
out = pd.DataFrame(rows); out.to_csv('ocr_relative.csv', index=False); print(out.round(3).to_string())
