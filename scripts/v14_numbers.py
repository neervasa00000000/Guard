"""Snapshot and check every numeric cell of the completed v1.4 summary tables."""
import csv,math,re
from pathlib import Path

def cell(value):
    if re.fullmatch(r'[+-]?\d+',value):return int(value)
    try:
        number=float(value)
        return number if math.isfinite(number) else value
    except ValueError:return value

def snapshot(root,path):
    with (Path(root)/path).open(newline='') as f:
        reader=csv.reader(f);columns=next(reader);rows=[[cell(v) for v in r] for r in reader]
    assert all(len(r)==len(columns) for r in rows),path
    return dict(path=path,columns=columns,rows=rows,
        n_numeric_values=sum(isinstance(v,(int,float)) for r in rows for v in r))

def compare(root,source,tolerance=1e-12):
    path=Path(root)/source['path']
    if not path.is_file():return 0,[source['path']+': missing source']
    actual=snapshot(root,source['path']);errors=[];passed=0
    if actual['columns']!=source['columns']:return 0,[source['path']+': headers changed']
    if len(actual['rows'])!=len(source['rows']):return 0,[source['path']+': row count changed']
    for i,(got,expected) in enumerate(zip(actual['rows'],source['rows']),1):
        for key,g,e in zip(source['columns'],got,expected):
            if isinstance(e,(int,float)):
                ok=isinstance(g,(int,float)) and math.isclose(g,e,rel_tol=0,abs_tol=tolerance)
                passed+=int(ok)
            else:ok=type(g) is type(e) and g==e
            if not ok:errors.append(f'{source["path"]}: row {i}, {key}: got {g!r}, expected {e!r}')
    return passed,errors
