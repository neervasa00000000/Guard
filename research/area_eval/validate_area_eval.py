#!/usr/bin/env python3
"""Validate B2 raw counts, archived geometry and a fresh-OCR repeated run."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import math
import shlex
import subprocess
import sys
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from run_area_eval import read,write,digest,area,HERE,ROOT,POLICIES,bootstrap

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--first',type=Path,default=HERE/'results')
    parser.add_argument('--repeat',type=Path,default=HERE/'.repeat')
    args=parser.parse_args();first=args.first.resolve();second=args.repeat.resolve()
    c=json.loads((first/'config.json').read_text());r=json.loads((second/'config.json').read_text())
    assert c['status']==r['status']=='complete'
    assert c['bootstrap_seed']==r['bootstrap_seed']==20261121
    assert c['bootstrap_resamples']==r['bootstrap_resamples']==10000
    for key in ['versions','tesseract_version','tesseract_settings','tesseract_language','OMP_THREAD_LIMIT',
                'OMP_NUM_THREADS','normalization','matching','field_geometry','census_sha256','source_funsd_zip_sha256','workers']:
        assert c[key]==r[key],('Repeat parameters differ',key)
    assert (first/'input_manifest.csv').read_bytes()==(second/'input_manifest.csv').read_bytes()
    assert r['force_ocr'] and r['fresh_ocr_jobs']==r['n_unique_ocr_jobs'] and r['cache_hits']==0
    assert c['source_script_sha256']==r['source_script_sha256']==digest(HERE/'run_area_eval.py')
    for key,path in [('policy_source_sha256','research/realworld_e1_eval/run_eval.py'),
                     ('selection_source_sha256','research/realworld_e1_eval/run_generic_attacker.py'),
                     ('funsd_helpers_sha256','research/funsd_validation/funsd_real.py')]:
        assert c[key]==r[key]==digest(ROOT/path),('Archived source changed',path)
    assert c['eng_traineddata_sha256']==r['eng_traineddata_sha256']==digest(c['eng_traineddata_path'])
    assert c['tesseract_binary_sha256']==r['tesseract_binary_sha256']==digest(c['tesseract_path'])
    identical=(first/'summary.csv').read_bytes()==(second/'summary.csv').read_bytes()
    assert identical,'Fresh OCR repeat changed summary.csv; report the mismatch, never patch numbers'
    rows=read(first/'per_page.csv');summary=read(first/'summary.csv')
    assert len(summary)==5 and len(rows)==c['n_redactions']
    assert not ({'text','word','token','surface','string'}&set(rows[0]))
    numeric=['n_gt_words','n_gt_words_total','n_covered50','n_covered_any','ocr_correct',
             'ocr_correct_case_insensitive','ocr_eval_words','ocr_correct_unredacted_visible',
             'ocr_correct_unredacted_visible_case_insensitive','target_fully_covered']
    for row in rows:
        for key in numeric:row[key]=int(row[key])
        for key in ['area_ratio','area_ratio_nominal']:row[key]=float(row[key])
        assert len(row['page_id'])==len(row['target_id'])==len(row['target_sha256'])==64
        assert int(row['target_char_length'])>0
        assert row['n_gt_words']==row['n_gt_words_total']-1
        assert 0<=row['n_covered50']<=row['n_covered_any']<=row['n_gt_words']
        assert row['ocr_eval_words']==row['n_gt_words']-row['n_covered50']
        assert 0<=row['ocr_correct']<=row['ocr_correct_case_insensitive']<=row['ocr_eval_words']
        assert 0<=row['ocr_correct_unredacted_visible']<=row['ocr_eval_words']
        if row['policy']!='field-1000':assert row['target_fully_covered']==1
    groups=defaultdict(list)
    for row in rows:groups[row['policy']].append(row)
    exact={row['target_id']:row for row in groups['exact']}
    for policy in ['grid-16','grid-64','start-aligned-128']:
        assert {row['target_id'] for row in groups[policy]}==set(exact)
        for row in groups[policy]:
            e=exact[row['target_id']]
            assert row['n_covered50']>=e['n_covered50']
            assert row['n_covered_any']>=e['n_covered_any']
            requested=tuple(map(int,row['requested_box'].split(',')))
            paint=tuple(map(int,row['painted_box'].split(',')))
            ereq=tuple(map(int,e['requested_box'].split(',')))
            epaint=tuple(map(int,e['painted_box'].split(',')))
            assert math.isclose(row['area_ratio'],area(paint)/area(epaint),abs_tol=1e-12)
            assert math.isclose(row['area_ratio_nominal'],area(requested)/area(ereq),abs_tol=1e-12)
    for s in summary:
        rs=groups[s['policy']]
        assert int(s['n_redactions'])==len(rs) and int(s['n_pages'])==len({row['page_id'] for row in rs})
        pt,lo,hi,total,valid=bootstrap(rs)
        for i,key in enumerate(['words_covered50_pct','words_covered_any_pct','ocr_word_acc','ocr_word_acc_ci','ocr_drop_points','words_covered_per_redaction']):
            assert math.isclose(float(s[key]),pt[i],abs_tol=1e-12),(s['policy'],key)
            assert math.isclose(float(s[key+'_lo']),lo[i],abs_tol=1e-12)
            assert math.isclose(float(s[key+'_hi']),hi[i],abs_tol=1e-12)
            assert valid[i]==int(s[key+'_valid_bootstrap_draws'])==10000
        assert math.isclose(float(s['area_ratio_median']),float(np.median([row['area_ratio'] for row in rs])))
        assert math.isclose(float(s['area_ratio_p90']),float(np.quantile([row['area_ratio'] for row in rs],.9)))
    ref=read(first/'area_reference_checks.csv');assert len(ref)==3198
    assert all(row['box_matches']=='1' and row['nominal_ratio_matches']=='1' for row in ref)
    reference_summary=[]
    for policy in POLICIES:
        rs=[row for row in ref if row['policy']==policy]
        old=float(np.median([float(row['archived_nominal_area_ratio']) for row in rs]))
        new=float(np.median([float(row['new_nominal_area_ratio']) for row in rs]))
        clipped=float(np.median([float(row['new_clipped_area_ratio']) for row in rs]))
        reference_summary.append(dict(policy=policy,n_paired_test_targets=len(rs),archived_nominal_median=old,
            new_nominal_median=new,new_clipped_median=clipped,nominal_median_matches=math.isclose(old,new,abs_tol=1e-12),
            clipped_median_matches_nominal=math.isclose(old,clipped,abs_tol=1e-12),
            n_clipping_differences=sum(row['clipped_ratio_differs']=='1' for row in rs)))
    write(first/'area_reference_summary.csv',reference_summary)
    manifest=read(first/'input_manifest.csv');assert len(manifest)==199
    assert Counter(row['split'] for row in manifest)=={'training':149,'testing':50}
    assert sum(int(row['n_surname_targets']) for row in manifest)==2649
    assert sum(int(row['n_surname_targets'])==0 for row in manifest)==7
    partial=[row for row in rows if row['target_fully_covered']==0]
    if partial:
        assert all(row['policy']=='field-1000' for row in partial)
        write(first/'field_target_coverage.csv',[{key:row[key] for key in
            ['page_id','target_id','target_sha256','target_char_length','policy',
             'target_coverage_fraction','requested_box','painted_box']} for row in partial])
    proof=dict(passed=True,summary_byte_identical=identical,
        summary_sha256_first=digest(first/'summary.csv'),summary_sha256_repeat=digest(second/'summary.csv'),
        per_page_byte_identical=(first/'per_page.csv').read_bytes()==(second/'per_page.csv').read_bytes(),
        first_fresh_ocr_jobs=c['fresh_ocr_jobs'],first_cache_hits=c['cache_hits'],
        repeated_fresh_ocr_jobs=r['fresh_ocr_jobs'],repeat_cache_hits=r['cache_hits'],
        repeated_ocr_output_differences=r['repeated_ocr_output_differences'],
        paired_archive_boxes=3198,archive_box_mismatches=0,archive_nominal_area_mismatches=0,
        n_clipping_differences=sum(row['clipped_ratio_differs']=='1' for row in ref),
        exact_words_covered_per_redaction=c['sanity_exact_words_per_redaction'],
        grid64_words_covered_per_redaction=c['sanity_grid64_words_per_redaction'],
        all_metrics_and_CIs_recomputed=True,gt_source=c['gt_source'])
    (first/'reproducibility.json').write_text(json.dumps(proof,indent=2)+'\n')
    # Store canonical, executable command lines rather than an unquoted display path.
    one=['.venv/bin/python','-B','research/area_eval/run_area_eval.py','--workers',str(c['workers'])]
    two=one+['--force-ocr','--out','research/area_eval/.repeat']
    c['command']=shlex.join(one)
    c['commands']=[shlex.join(one),shlex.join(two),'.venv/bin/python -B research/area_eval/validate_area_eval.py']
    c['install_commands']=['NONINTERACTIVE=1 HOMEBREW_NO_SUDO=1 HOMEBREW_NO_ANALYTICS=1 /bin/bash /private/tmp/guard-homebrew-install.sh',
        'HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_ANALYTICS=1 /opt/homebrew/bin/brew install tesseract',
        '.venv/bin/python -m pip install pytesseract']
    c['homebrew_installer_url']='https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh'
    installer=Path('/private/tmp/guard-homebrew-install.sh')
    c['homebrew_installer_sha256']=digest(installer) if installer.exists() else None
    c['python']=sys.version;c['field_geometry_file_sha256']=digest(HERE/'field_geometry.json')
    c['import_adapter_sha256']=digest(HERE/'existing.py')
    c['archived_helper_sha256']={path:digest(ROOT/path) for path in
        ['research/e1/e1lib.py','research/e1/policies.py']}
    c['packaging_version']=importlib.metadata.version('packaging')
    c['validation_script_sha256']=digest(Path(__file__))
    c['reproducibility']=proof
    (first/'config.json').write_text(json.dumps(c,indent=2)+'\n')
    readme=first/'README.md'
    text=readme.read_text().split('## Reproduction check')[0]
    text+='\n## Reproduction check\n\n'
    text+=f'Two runs used the same seed/settings; the second bypassed cached OCR for all {r["fresh_ocr_jobs"]} unique images. Summary CSVs are byte-identical (SHA-256 {proof["summary_sha256_first"]}); per-target CSV byte identity: {proof["per_page_byte_identical"]}. OCR output differences: {r["repeated_ocr_output_differences"]}. No numeric results were patched.\n\n'
    text+='From the repository root, after installing the recorded local Tesseract version and Python requirements and providing the independently obtained FUNSD/Census inputs:\n\n```sh\n'+ '\n'.join(c['commands'])+'\n```\n'
    text+='\nOnly the unused import of the unreleased DocLayNet downloader is omitted in memory so the archived selector/policy code can run from released files; their function bodies are unchanged. field_geometry.json releases the sufficient numeric first-1000 geometry parameters, verified against the archived receipt and paired boxes; no font files are distributed.\n'
    text+='\nArea-reference checks compare identical test targets with the archived Table A9 boxes. Nominal medians all match. Image-edge clipping differences and their median effects are listed in area_reference_summary.csv; the existing entity-level FUNSD figures use different targets and do not provide a comparable field-box reference.\n'
    text+=f'\nAll 199 forms were inspected: {c["n_forms_with_targets"]} contain {c["n_targets"]} qualifying surname words; {c["n_forms_skipped"]} forms have none and are skipped. Field-1000 has {c["field_targets"]} in-list targets; the other {c["n_targets"]-c["field_targets"]} targets have no field-1000 case. Ground-truth quality exclusions: {c["gt_quality"]["blank_word_annotations"]} blank word records excluded; {c["gt_quality"]["multiword_text_in_one_annotation"]} multiword annotation entries retained as single annotated units; {c["gt_quality"]["clipped_gt_rectangles"]} rectangles clipped to image boundaries. These counts cover all 199 forms.\n'
    if partial:
        fractions=[float(row['target_coverage_fraction']) for row in partial]
        text+=f'\nThe unchanged archived field surrogate fails to fully cover the annotated target rectangle in {len(partial)} of {len(groups["field-1000"])} cases (coverage {100*min(fractions):.2f}%–{100*max(fractions):.2f}%). These cases remain in the results and are listed by hashes in field_target_coverage.csv. Rectangle coverage alone does not establish whether target ink is exposed. All other policies fully cover each target rectangle.\n'
    text+='\nAdditional utility measures (confidence limits in summary.csv):\n\n| Policy | Area median | Area p90 | Neighbour words >=50% covered/redaction | Unredacted accuracy on same visible set % |\n|---|---:|---:|---:|---:|\n'
    for row in summary:
        text+=f'| {row["policy"]} | {float(row["area_ratio_median"]):.3f} | {float(row["area_ratio_p90"]):.3f} | {float(row["words_covered_per_redaction"]):.3f} | {100*float(row["ocr_acc_unredacted"]):.3f} |\n'
    readme.write_text(text)
    (HERE/'requirements.txt').write_text('\n'.join(f'{name}=={importlib.metadata.version(name)}' for name in ['numpy','pandas','Pillow','pytesseract','packaging'])+'\n')
    print(json.dumps(proof,indent=2))

if __name__=='__main__':main()
