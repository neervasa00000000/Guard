#!/usr/bin/env python3
"""Verify source receipts, target identity and output invariants; add coverage table."""
import json
import math
import zipfile
from collections import Counter
import run_analysis as A

def main():
    rows=A.read(A.OUT/'per_token.csv'); pages=A.read(A.OUT/'per_page.csv')
    saved=[r for r in A.read(A.HERE/'results/v2/per_token.csv') if r['policy']=='exact']
    original={r['token_id']:r for r in saved}
    assert len(rows)==len(original)==6071 and len(pages)==2050
    for r in rows:
        s=original[r['token_id']]
        assert all(r[k]==s[k] for k in ['dataset','page_id','token','likely_name','box'])
        for scope in ['line','block','cell','entity','linked']:
            if r.get(scope+'_n','')=='': continue
            ids=json.loads(r[scope+'_neighbour_ids'])
            assert len(ids)==len(set(ids))==int(r[scope+'_n'])
            assert r['source_id'] not in ids
            assert int(r[scope+'_size_known'])+int(r[scope+'_size_unknown'])==len(ids)
            assert int(r[scope+'_font_known'])+int(r[scope+'_font_unknown'])==len(ids)
            if r[scope+'_abs_diff']:
                diff=float(r[scope+'_abs_diff']); med=float(r[scope+'_median_size'])
                assert math.isclose(diff,abs(float(r['token_size'])-med))
                assert int(r[scope+'_same_size'])==int(diff<=(.5 if r['dataset']=='DocLayNet' else .1*med))
            else: assert r[scope+'_same_size']==''
            if r[scope+'_same_font']!='':
                assert r['token_font'] and r[scope+'_modal_font']
                assert int(r[scope+'_same_font'])==int(r['token_font']==r[scope+'_modal_font'])
    # Verify that annotations are the exact archived data used by the previous run.
    receipts=A.read(A.HERE/'results/doclaynet_json_sha256.csv')
    assert len(receipts)==2000
    for r in receipts:
        assert A.digest(A.base.JSON_DIR/(r['page_id']+'.json'))==r['sha256']
    oldconfig=json.loads((A.HERE/'results/run_config.json').read_text())
    for name,sha in oldconfig['doclaynet_sample']['coco_sha256'].items():
        assert A.digest(A.base.COCO_DIR/name)==sha
    config=json.loads((A.HERE/'results/v2/run_config.json').read_text())
    assert A.digest(A.base.FUNSD_ZIP)==config['funsd_scored']['sha256']
    matched_forms=0
    with zipfile.ZipFile(A.base.FUNSD_ZIP) as z:
        for path in (A.base.funsd_split_dir('testing_data')/'annotations').glob('*.json'):
            names=[n for n in z.namelist() if n.endswith('/testing_data/annotations/'+path.name)]
            assert len(names)==1 and z.read(names[0])==path.read_bytes()
            matched_forms+=1
    assert matched_forms==50
    manifest=json.loads((A.OUT/'run_manifest.json').read_text())
    assert A.protected()==manifest['protected_sha256']
    summary=A.read(A.OUT/'summary.csv')
    coverage=['| Dataset/category | Set | Font known/unknown | Target pages | Page-size share known/unknown | Page-font share known/unknown |',
              '|---|---|---:|---:|---:|---:|']
    for r in summary:
        for metric in ['line_same_size','block_same_size','line_same_font','block_same_font']:
            assert int(r[metric+'_usable'])+int(r[metric+'_unknown'])==int(r['n'])
        coverage.append('| '+' | '.join([r['dataset']+('/'+r['doc_category'] if r['doc_category']!='ALL' else ''),r['subset'],
                        r['token_font_usable']+'/'+r['token_font_unknown'],r['n_pages'],
                        r['page_size_usable']+'/'+r['page_size_unknown'],r['page_font_usable']+'/'+r['page_font_unknown']])+' |')
    report=A.HERE/'FONT_CONSISTENCY.md'; text=report.read_text()
    text=text.split('## Additional metadata coverage')[0]
    text+='\n## Additional metadata coverage\n\nKnown/unknown counts below refer to the pages represented in each target subset. Across the complete page inventory, size shares are known on 811/2,000 DocLayNet pages and font shares on 1,756/2,000; the others are unknown (including pages with no COCO Text tokens). FUNSD size shares are known on all 50 forms and font shares on none.\n\n'+'\n'.join(coverage)+'\n'
    text+='\nValidation matched all 2,000 source-JSON receipts, the three COCO archive checksums, all 50 FUNSD annotations against the v2-checksummed ZIP, all 6,071 persisted target identities/boxes/likely flags, and every saved comparison denominator. Protected-file SHA-256s are unchanged. Reproduce with `python -B run_analysis.py`, `python -B run_attacker.py`, then `python -B validate_and_report.py` from this result directory using the study .venv.\n'
    text+='\nFor the optional attacker, 5,245 scored tokens and 37,235 DocLayNet calibration tokens are unmapped or lack required neighbour metadata; the 133 saved FUNSD calibration tokens have unknown font metadata and are ineligible. These exclusions are separate from the main consistency analysis.\n'
    report.write_text(text)
    validation=dict(passed=True,target_tokens=6071,target_identity_matches=6071,doclaynet_source_receipt_matches=2000,coco_archive_checksum_matches=3,
                    funsd_annotation_archive_matches=50,protected_files_unchanged=True,
                    output_sha256={p.name:A.digest(p) for p in sorted(A.OUT.glob('*')) if p.is_file() and p.name!='validation.json'})
    (A.OUT/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    print(json.dumps({k:v for k,v in validation.items() if k!='output_sha256'},indent=2))
    print('\n'.join(coverage))

if __name__=='__main__': main()
