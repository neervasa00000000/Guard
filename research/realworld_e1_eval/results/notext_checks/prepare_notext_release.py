#!/usr/bin/env python3
"""Create distribution copies without changing any research source or original result.

Run from any directory with Python 3. Existing scorer scripts are not modified.
Original text-bearing results are required only for the conversion operation;
--check-only recomputes the cited numbers from distributed _notext CSVs alone.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]

def sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()

def destination(path):
    return path.with_name(path.stem+'_notext.csv')

def read(path):
    with (ROOT/path).open(newline='',encoding='utf-8') as f:
        return list(csv.DictReader(f))

def write(path, rows, fields):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n')
        w.writeheader(); w.writerows(rows)

class JSONNumber(str):
    """Preserve the original lexical representation of JSON numeric leaves."""

def sanitize(path, columns):
    before=digest(path); out=destination(path); count=0
    if path.suffix=='.csv':
        with path.open(newline='',encoding='utf-8') as source, out.open('w',newline='',encoding='utf-8') as target:
            reader=csv.DictReader(source); original=reader.fieldnames
            textcols=[k for k in original if k in columns]
            assert textcols, ('Expected document-text columns',path)
            fields=[]
            for key in original:
                fields.extend([key+'_sha256',key+'_char_length'] if key in textcols else [key])
            writer=csv.DictWriter(target,fieldnames=fields,lineterminator='\n'); writer.writeheader()
            for row in reader:
                item={}
                for key,value in row.items():
                    assert value is not None, ('Ragged CSV',path,count,key)
                    if key in textcols:
                        item[key+'_sha256']=sha(value); item[key+'_char_length']=len(value)
                    else: item[key]=value
                writer.writerow(item); count+=1
        # Independently compare every retained field, row count and hash against source.
        with path.open(newline='',encoding='utf-8') as sf, out.open(newline='',encoding='utf-8') as tf:
            sr=csv.DictReader(sf); tr=csv.DictReader(tf)
            for row in sr:
                result=next(tr)
                for key,value in row.items():
                    if key in textcols:
                        assert result[key+'_sha256']==sha(value)
                        assert int(result[key+'_char_length'])==len(value)
                    else: assert result[key]==value, (path,key)
            assert next(tr,None) is None
        method='source-text columns hashed; every other CSV cell preserved'
    elif path.suffix=='.json':
        payload=json.loads(path.read_text(),parse_int=JSONNumber,parse_float=JSONNumber)
        rows=[]
        def visit(value,pointer):
            if isinstance(value,dict):
                for key,child in value.items(): visit(child,pointer+'/'+key.replace('~','~0').replace('/','~1'))
            elif isinstance(value,list):
                for index,child in enumerate(value): visit(child,pointer+'/'+str(index))
            else:
                row=dict(json_pointer=pointer,value_type='',numeric_value='',boolean_value='',text_sha256='',text_char_length='')
                if isinstance(value,JSONNumber): row.update(value_type='number',numeric_value=str(value))
                elif isinstance(value,bool): row.update(value_type='boolean',boolean_value=str(value).lower())
                elif value is None: row.update(value_type='null')
                else:
                    assert isinstance(value,str)
                    row.update(value_type='string',text_sha256=sha(value),text_char_length=len(value))
                rows.append(row)
        visit(payload,''); fields=['json_pointer','value_type','numeric_value','boolean_value','text_sha256','text_char_length']
        write(out,rows,fields); count=len(rows); textcols=['all JSON string leaves']
        method='flattened JSON leaves; numeric lexemes unchanged; all string values hashed'
    elif path.suffix=='.md':
        lines=path.read_text(encoding='utf-8').splitlines(keepends=True)
        rows=[dict(line_number=i+1,text_sha256=sha(line),text_char_length=len(line)) for i,line in enumerate(lines)]
        write(out,rows,['line_number','text_sha256','text_char_length'])
        count=len(rows); textcols=['entire report line, including line terminator']
        method='report lines hashed; original prose and quotations excluded'
    else: raise ValueError(path)
    assert before==digest(path), ('Original changed',path)
    return dict(source=str(path.relative_to(ROOT)),copy=str(out.relative_to(ROOT)),
                source_sha256=before,copy_sha256=digest(out),rows=count,method=method,text_columns=textcols,
                copy_bytes=out.stat().st_size,original_unchanged=True)

def mean(rows,key):
    values=[float(r[key]) for r in rows if r[key]!='']
    assert values
    return math.fsum(values)/len(values),len(values)

def checks():
    results=[]
    def check(label,rows,key,cited,places,scale=1):
        value,n=mean(rows,key); value*=scale
        item=dict(metric=label,n=n,recomputed=value,cited=cited,decimal_places=places,
                  matches_cited_rounding=round(value,places)==cited)
        results.append(item)
    generic_attacker=read('research/realworld_e1_eval/results/generic_attacker/per_token_notext.csv')
    doc=[r for r in generic_attacker if r['dataset']=='DocLayNet' and r['policy']=='exact']
    fun=[r for r in generic_attacker if r['dataset']=='FUNSD' and r['policy']=='exact']
    assert len(doc)==5311 and len(fun)==760
    check('DocLayNet generic-attacker exact bits',doc,'bits',.061,3)
    check('DocLayNet generic-attacker exact top-10 percent',doc,'hit10',.038,3,100)
    check('FUNSD generic-attacker exact bits',fun,'bits',.0026,4)
    font=read('research/realworld_e1_eval/results/font_consistency/per_token_notext.csv')
    font=[r for r in font if r['dataset']=='DocLayNet']; assert len(font)==5311
    check('DocLayNet line same-size percent',font,'line_same_size',92.63,2,100)
    check('DocLayNet line same-font percent',font,'line_same_font',77.57,2,100)
    attacker=read('research/realworld_e1_eval/results/font_consistency/attacker_per_token_notext.csv')
    results.append(dict(metric='Font-matched attacker n',n=len(attacker),recomputed=len(attacker),cited=66,
                        decimal_places=0,matches_cited_rounding=len(attacker)==66))
    check('Font-matched attacker bits',attacker,'bits',1.66,2)
    painted=read('research/doclaynet_validation/results/results_notext.csv')
    painted=[r for r in painted if r['role']=='evaluation' and r['condition']=='matched_template_known' and r['policy']=='exact' and r['size_px']=='16']
    assert len(painted)==954
    check('DocLayNet painted exact matched 16px bits',painted,'entropy_reduction',6.94,2)
    # This is a different FUNSD experiment from generic-attacker: verify it separately, without mixing numbers.
    scored=read('research/funsd_validation/out/scores_notext.csv')
    scored=[r for r in scored if r['regime']=='length_width' and r['policy']=='exact']
    reference=read('research/funsd_validation/out/summary.csv')
    reference=next(r for r in reference if r['regime']=='length_width' and r['policy']=='exact')
    val,n=mean(scored,'entropy_reduction_bits')
    results.append(dict(metric='Separate FUNSD length-width summary integrity',n=n,recomputed=val,
                        cited=float(reference['entropy_reduction']),decimal_places=10,
                        matches_cited_rounding=math.isclose(val,float(reference['entropy_reduction']),abs_tol=1e-9)))
    (HERE/'summary_checks.json').write_text(json.dumps(results,indent=2)+'\n')
    lines=['# Checks from no-text distribution copies','',
           'These calculations read numeric columns from the distributed no-text CSVs. They do not read any excluded original text, page images, raw annotations or dataset archives. Numerical field preservation is exhaustively checked during conversion.','',
           '| Metric | n usable | Recomputed | Cited | Match at cited precision |',
           '|---|---:|---:|---:|---|']
    for r in results:
        lines.append(f"| {r['metric']} | {r['n']} | {r['recomputed']:.12g} | {r['cited']} | {r['matches_cited_rounding']} |")
    lines+=['','The painted result is the 16px, exact-box, matched-template evaluation arm (954 targets). The two font-consistency percentages use line neighbours and exclude unknown comparisons. FUNSD generic-attacker and the separate length-width experiment are distinct analyses.','',
            'Recheck without originals: `python3 research/realworld_e1_eval/results/notext_checks/prepare_notext_release.py --check-only`.','']
    (HERE/'SUMMARY_CHECKS.md').write_text('\n'.join(lines))
    for r in results: print(json.dumps(r))
    assert all(r['matches_cited_rounding'] for r in results), 'A cited number mismatches; inspect summary_checks.json'

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--check-only',action='store_true'); args=parser.parse_args()
    if not args.check_only:
        plan=json.loads((HERE/'notext_plan.json').read_text())
        manifest=[sanitize(ROOT/source,set(plan['csv_source_text_columns'])) for source in plan['sources']]
        assert all(r['copy_bytes']<100_000_000 for r in manifest), 'Distribution copy exceeds the approved size limit'
        (HERE/'notext_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        print('Converted files:',len(manifest))
    checks()

if __name__=='__main__': main()
