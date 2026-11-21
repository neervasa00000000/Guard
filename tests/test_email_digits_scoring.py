import sys,itertools
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_email_digits import Scores,exact_email_bits,entropy,E,P
def fixture():
    d=E._finish(['a','b','c','d'],[3,3,2,1],[1,2,5,7],{})
    g=np.array([[0,-3,5,0],[0,-4,7,0],[0,-3,5,0],[1,-2,8,1]])
    return d,g
def test_grouped_scores_match_original_e1_metrics_including_empty_and_missing_truth():
    d,g=fixture();scorer=Scores(d,g)
    for take in itertools.product([False,True],repeat=len(scorer.geometry)):
        mask=np.array(take)
        for target in range(len(g)):
            old=E.metrics(d,mask[scorer.group],target,1,np.log2(d['p']))
            bits,h1,h10,truth=scorer.score(mask,target)
            np.testing.assert_allclose([bits,h1,h10],[scorer.h0-old['resid_bits'],old['hit1'],old['hit10']],atol=1e-12)
            assert truth==bool(old['truth_in'])
def test_exact_phase_enumeration_matches_every_original_square_policy_phase():
    d,g=fixture();d['m']=np.ones(4);d['p']=np.array([.1,.2,.3,.4]);scorer=Scores(d,g);prep=P.prepare(g,4,1)
    expected=[]
    for x,y in itertools.product(range(4),repeat=2):
        box=P.square_grid(prep,4,x,y)
        expected.append(entropy(d['p'],np.column_stack(box)))
    np.testing.assert_allclose(exact_email_bits(scorer,prep,'square',4),np.mean(expected),atol=1e-12)
