import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import pytest
pytest.importorskip("pymupdf")
from lo_reconstruction_worker import words,measure

def test_pdf_word_segmentation_preserves_origins_across_tab_gaps():
    def char(c,x):return dict(c=c,origin=[x,20],bbox=[x,10,x+5,22])
    class Page:
        def get_text(self,kind):
            assert kind=='rawdict'
            return dict(blocks=[dict(lines=[dict(spans=[dict(font='Test',size=12,chars=[char('A',10),char('b',15),char('C',100),char('d',105)])])])])
    result=words(Page())
    assert [r['text'] for r in result]==['Ab','Cd']
    assert [r['origin'] for r in result]==[[10,20],[100,20]]

def test_measure_uses_actual_raster_ink_instead_of_pdf_typographic_box():
    image=np.full((30,30),255,dtype=np.uint8);image[10:15,12:18]=0
    item=dict(bbox=[8,6,15,13],origin=[9,12],font='Test',size=12)
    result=measure(None,item,image)
    assert result['bounds']==[0,-6,6,-1]
    assert result['pen_x']==12 and result['baseline_y']==16
