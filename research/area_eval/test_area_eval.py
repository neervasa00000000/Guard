"""Meaningful geometry/matching checks with synthetic strings only."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_area_eval import clipped,overlaps,match_words,norm,sha

def test_one_ocr_word_cannot_count_twice():
    gt=[dict(box=(0,0,10,10),sha256=sha('X'),casefold_sha256=sha('x'))]*2
    ocr=[[0,0,10,10,sha('X'),sha('x'),1]]
    cs,ci=match_words(gt,ocr)
    assert cs.sum()==ci.sum()==1

def test_matching_is_geometric_and_case_comparisons_are_separate():
    gt=[dict(box=(0,0,10,10),sha256=sha(norm('Ａ')),casefold_sha256=sha(norm('Ａ').casefold()))]
    ocr=[[0,0,10,10,sha(norm('a')),sha(norm('a').casefold()),1]]
    cs,ci=match_words(gt,ocr)
    assert not cs[0] and ci[0]

def test_half_open_edges_and_exact_fifty_percent_threshold():
    boxes=np.array([[0,0,10,10],[10,0,20,10]])
    assert overlaps(boxes,(0,0,10,10)).tolist()==[100,0]
    assert overlaps(boxes,(0,0,5,10)).tolist()==[50,0]
    assert clipped((-2,-3,50,60),(20,30))==(0,0,20,30)
