import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from number_checks import snapshot,compare,compare_aggregate

def test_numeric_drift_and_unknown_values_are_detected(tmp_path):
    p=tmp_path/'summary.csv';p.write_text('policy,n,bits,unknown\nexact,10,0.25,\n')
    expected=snapshot(tmp_path,'summary.csv')
    assert compare(tmp_path,expected)==(2,[])
    p.write_text('policy,n,bits,unknown\nexact,10,0.35,0\n')
    count,errors=compare(tmp_path,expected)
    assert count==1 and len(errors)==2
    assert any('bits' in e for e in errors) and any('unknown' in e for e in errors)

def test_missing_rows_and_cohort_labels_fail(tmp_path):
    p=tmp_path/'summary.csv';p.write_text('policy,n\nexact,10\n')
    expected=snapshot(tmp_path,'summary.csv')
    p.write_text('policy,n\nfield,10\n')
    assert len(compare(tmp_path,expected)[1])==1
    p.write_text('policy,n\n')
    assert 'row count changed' in compare(tmp_path,expected)[1][0]

def test_cited_counts_are_recomputed_and_filtered(tmp_path):
    (tmp_path/'summary.csv').write_text('C,n\n128,188\n192,2\n')
    spec=dict(id='changed',path='summary.csv',where={'C':128},operation='sum',column='n',expected=188)
    assert compare_aggregate(tmp_path,spec)==(1,[])
    spec['expected']=189
    assert compare_aggregate(tmp_path,spec)[0]==0
    assert compare_aggregate(tmp_path,dict(id='cells',path='summary.csv',operation='count',expected=2))==(1,[])
