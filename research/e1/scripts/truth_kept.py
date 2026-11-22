"""Split the exact-box entropy-reduction score of Table A13 by whether the true name was kept (Section 7.3).

Usage:  python research/e1/scripts/truth_kept.py [repo root]
Input:  research/realworld_e1_eval/results/v4_fontmatched/per_token.csv.gz
Output: truth_kept.csv in the current directory. Needs pandas.
"""
import sys
from pathlib import Path
import pandas as pd

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
d = pd.read_csv(root / 'research/realworld_e1_eval/results/v4_fontmatched/per_token.csv.gz', low_memory=False)
e = d[d.policy == 'exact']
rows = []
for a, g in e.groupby('attacker'):
    k = g.truth_in == 1
    rows.append(dict(attacker=a, n=len(g), bits_all=g.bits.mean(), n_kept=int(k.sum()), bits_kept=g.bits[k].mean(),
                     n_dropped=int((~k).sum()), bits_dropped=g.bits[~k].mean(),
                     share_of_score_from_dropped=g.bits[~k].sum() / g.bits.sum(), median_candidates=g.candidate_count.median()))
fe = e[e.attacker == 'font-estimated']
m = fe[fe.estimated_font == 'LiberationMono']
rows.append(dict(attacker='font-estimated, Liberation Mono chosen', n=len(m), bits_all=m.bits.mean(),
                 n_kept=int((m.truth_in == 1).sum()), bits_kept=m.bits[m.truth_in == 1].mean(),
                 n_dropped=int((m.truth_in == 0).sum()), bits_dropped=m.bits[m.truth_in == 0].mean(),
                 # for this row: share of the font-estimated attacker's total exact-box score
                 share_of_score_from_dropped=m.bits.sum() / fe.bits.sum(), median_candidates=m.candidate_count.median()))
out = pd.DataFrame(rows)
out.to_csv('truth_kept.csv', index=False)
print(out.to_string())
