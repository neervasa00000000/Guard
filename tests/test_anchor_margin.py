"""Synthetic checks for visible-start and latent-width error channels."""
import sys,math
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_anchor_margin import channel

def result(width,error='clean',margin=0):
    return channel(np.array([10,20]),np.array([3,1]),margin,width,error,'synthetic',1,1,np.ones(2))

def test_clean_partition_and_constant_field():
    entropy=-.75*math.log2(.75)-.25*math.log2(.25)
    assert math.isclose(result(16)[0]['avg_bits'],entropy)
    for error in ['clean','start_uniform_-2_2','start_uniform_-4_4','class_width_pm8']:
        row,classes=result(0,error,8)
        assert row['avg_bits']==row['max_pointwise_bits']==0
        assert all(r['names']==2 for r in classes)
        if error in ['clean','class_width_pm8']:
            assert math.isclose(row['extra_area_vs_m0'],.4)

def test_latent_width_error_marginalizes_overlapping_outputs():
    # C=16 -> {8,24}; name 1 emits {16,24}, name 2 emits {24,24}.
    expected=.375*math.log2(.5/.375)+.375*math.log2(.5/.625)+.25*math.log2(1/.625)
    row,classes=result(16,'class_width_pm8')
    assert math.isclose(row['avg_bits'],expected,abs_tol=1e-12)
    overlap=next(r for r in classes if r['released_width_px']==24)
    assert overlap['names']==2 and overlap['prior_mass']==1.
    assert overlap['output_probability']==.625
    assert overlap['min_likelihood']==.5 and overlap['max_likelihood']==1.
