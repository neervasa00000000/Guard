import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from rerun_common import quantile_draws,mean_intervals
def test_quantile_bootstrap_matches_exhaustive_two_target_distribution():
    draws=quantile_draws([0.,1.],.5,np.random.default_rng(20261121),100000)
    values,counts=np.unique(draws,return_counts=True)
    np.testing.assert_array_equal(values,[0,.5,1])
    np.testing.assert_allclose(counts/len(draws),[.25,.5,.25],atol=.006)
def test_multinomial_target_bootstrap_preserves_constant_and_paired_means():
    a=np.array([[2.,0.],[2.,1.]])
    point,lo,hi=mean_intervals(a)
    np.testing.assert_allclose(point,[2.,.5])
    np.testing.assert_allclose(lo,[2.,0.]);np.testing.assert_allclose(hi,[2.,1.])
