#!/usr/bin/env python3
"""Audit prerequisites for v4; never silently substitute a neighbour's font.

This is not an attacker evaluation. It reads only released no-text tables and
local font metadata. A missing required font produces a documented blocked
preflight and exit code 2, before any candidate rendering or calibration.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import math
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
from fontTools.ttLib import TTCollection, TTFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'results/v4_fontmatched/preflight'

def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def read(path):
    with path.open(newline='') as f: return list(csv.DictReader(f))

def write(path, rows):
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)

def number(value):
    try: value = float(value)
    except (TypeError, ValueError): return None
    return value if math.isfinite(value) and value > 1 else None

def identity(value):
    # Only remove PDF syntax; do not equate styles, families or different names.
    return (value or '').split('+')[-1].lstrip('/')

def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font-dir', type=Path, action='append', default=[],
                        help='Additional local font directory to audit (no downloads)')
    args = parser.parse_args()
    source = HERE/'results/font_consistency/per_token_notext.csv'
    targets_source = HERE/'results/v2/per_token_notext.csv'
    font_receipts = ROOT/'research/e1/data/fonts.json'
    protected = {str(p.relative_to(ROOT)): digest(p) for p in [source, targets_source, font_receipts]}
    refs = {ref: git('rev-parse', ref) for ref in ['v1.3-artifact', 'v1.3-artifact^{commit}', 'f8f2558^{commit}']}
    assert git('branch','--show-current') == 'exp-v1.4'
    assert refs['v1.3-artifact^{commit}'] == '18cfe521088c90750ba6bc627fbd1bbe10072fab'
    targets = {r['token_id']:r for r in read(targets_source)
               if r['dataset']=='DocLayNet' and r['policy']=='exact'}
    rows = [r for r in read(source) if r['dataset']=='DocLayNet']
    assert len(rows)==len(targets)==5311
    for r in rows:
        t=targets[r['token_id']]
        assert all(r[k]==t[k] for k in ['page_id','token_sha256','token_char_length','likely_name'])

    roots = [Path('/System/Library/Fonts'),Path('/Library/Fonts'),Path.home()/'Library/Fonts',
             Path('/usr/local/share/fonts'),Path('/opt/homebrew/share/fonts'),HERE/'fonts']
    spec=importlib.util.find_spec('matplotlib')
    if spec and spec.origin: roots.append(Path(spec.origin).parent/'mpl-data/fonts')
    roots.extend(p.expanduser().resolve() for p in args.font_dir)
    roots=sorted(set(p for p in roots if p.is_dir()))
    paths=sorted({p for root in roots for p in root.rglob('*')
                  if p.is_file() and p.suffix.lower() in ['.ttf','.otf','.ttc','.otc']})
    names=defaultdict(list); files=[]; failures=[]
    for i,path in enumerate(paths):
        sha=digest(path)
        try:
            container=TTCollection(path,lazy=True) if path.suffix.lower() in ['.ttc','.otc'] else None
            faces=container.fonts if container else [TTFont(path,lazy=True)]
            for index,face in enumerate(faces):
                identifiers=set()
                for record in face['name'].names:
                    if record.nameID in [4,6]:
                        try: identifiers.add(record.toUnicode())
                        except UnicodeError: continue
                for name in sorted(identifiers): names[name].append(dict(path=str(path),face_index=index,sha256=sha))
            count=len(faces)
            if container: container.close()
            else: faces[0].close()
            files.append(dict(path=str(path),sha256=sha,n_faces=count))
        except Exception as e:
            failures.append(dict(path=str(path),error=type(e).__name__+': '+str(e)))
        if (i+1)%100==0: print('Audited font files',i+1,flush=True)

    per_target=[]; required=Counter(); absent=Counter()
    for r in rows:
        size=number(r['line_median_size']); name=identity(r['line_modal_font'])
        eligible=size is not None and bool(name)
        matches=names.get(name,[]) if eligible else []
        if eligible:
            required[name]+=1
            if not matches: absent[name]+=1
        per_target.append(dict(token_id=r['token_id'],page_id=r['page_id'],
            token_sha256=r['token_sha256'],token_char_length=r['token_char_length'],
            likely_name=r['likely_name'],doc_category=r['doc_category'],
            target_size_known=int(number(r['token_size']) is not None),
            line_size_known=int(size is not None),line_median_size=size if size is not None else '',
            line_modal_font=r['line_modal_font'],font_identity=name,metadata_eligible=int(eligible),
            local_identity_match=int(bool(matches)) if eligible else '',
            matching_faces=len(matches) if eligible else '',
            status='eligible_font_found' if matches else 'missing_font_file' if eligible else 'unknown_neighbour_metadata'))
    summary=[dict(scope='all_saved_doclaynet_targets',n_tokens=len(rows)),
             dict(scope='target_embedded_size_known',n_tokens=sum(r['target_size_known'] for r in per_target)),
             dict(scope='line_font_comparison_known',n_tokens=sum(r['line_same_font']!='' for r in rows)),
             dict(scope='line_neighbour_size_and_font_known',n_tokens=sum(required.values())),
             dict(scope='eligible_with_local_font_identity_match',n_tokens=sum(required.values())-sum(absent.values())),
             dict(scope='eligible_missing_local_font',n_tokens=sum(absent.values())),
             dict(scope='unknown_neighbour_size_or_font',n_tokens=len(rows)-sum(required.values()))]
    availability=[dict(font_identity=name,n_eligible_tokens=n,
                       locally_available=int(bool(names.get(name))),
                       matching_faces_json=json.dumps(names.get(name,[]),sort_keys=True))
                  for name,n in sorted(required.items(),key=lambda item:(-item[1],item[0]))]
    receipts=json.loads(font_receipts.read_text())
    pinned=[dict(font=name,expected_sha256=rec['sha256'],
                 matching_files_json=json.dumps([r['path'] for r in files if r['sha256']==rec['sha256']]),
                 pinned_binary_found=int(any(r['sha256']==rec['sha256'] for r in files)))
            for name,rec in receipts.items()]
    missing_pinned=[r['font'] for r in pinned if not r['pinned_binary_found']]
    blocked=bool(absent) or bool(missing_pinned) or bool(failures)
    config=dict(phase='preflight_only',status='blocked' if blocked else 'prerequisites_available',
        main_attacker_runs_started=False,bootstrap_seed=20261121,bootstrap_draws=10000,bootstrap_unit='page',
        requested_attackers=['font-known','font-estimated','renderer-mismatch','generic'],
        requested_policies=['no-box','exact','grid-16','grid-64','start-aligned-128','field-1000'],
        requested_tolerance_rule='smallest symmetric integer width edge tolerance reaching >=95% calibration truth-in; original v2 split',
        generic_original_tolerance_px=31,study_sizes_px=[12,16,24],
        eligibility='known line-neighbour median embedded size (>1) and unique modal font; excludes unknowns; does not require target size or same-font flag',
        font_identity_rule='exact PostScript name or full font name (name IDs 6 or 4), after removing PDF leading slash/subset prefix; no aliases or style substitutions',
        font_match_limit='matching a local font name does not establish identity of the original source font binary/build',
        font_directories=[str(p) for p in roots],font_file_count=len(files),font_parse_failures=failures,
        missing_pinned_study_fonts=missing_pinned,missing_neighbour_font_identities=len(absent),
        inputs_sha256=protected,protected_git_refs=refs,python=sys.version,fonttools=importlib.metadata.version('fonttools'),
        command='python3 -B research/realworld_e1_eval/preflight_v4_fontmatched.py' + ''.join(' --font-dir '+str(p) for p in args.font_dir))
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    write(OUT/'summary.csv',summary); write(OUT/'font_availability.csv',availability)
    write(OUT/'pinned_font_availability.csv',pinned)
    (OUT/'local_font_files.json').write_text(json.dumps(files,indent=2)+'\n')
    (OUT/'font_name_index.json').write_text(json.dumps(dict(names),indent=2,sort_keys=True)+'\n')
    with (OUT/'per_target.csv.gz').open('wb') as binary:
        with gzip.GzipFile(fileobj=binary,mode='wb',mtime=0,filename='') as z:
            with io.TextIOWrapper(z,encoding='utf-8',newline='') as text:
                writer=csv.DictWriter(text,fieldnames=list(per_target[0]),lineterminator='\n')
                writer.writeheader(); writer.writerows(per_target)
    for path,expected in protected.items(): assert digest(ROOT/path)==expected
    for ref,expected in refs.items(): assert git('rev-parse',ref)==expected
    (OUT/'README.md').write_text(
        '# Font-matched v4 prerequisite audit\n\n'
        'This is a preflight, not an attacker evaluation. No candidate rendering, '
        'font estimation, tolerance calibration, policy scoring or bootstrap inference was run. '
        'The audit reads released no-text tables only; it does not redistribute or upload document text.\n\n'
        'The target cohort is exactly the saved DocLayNet v2 targets. Eligibility uses known line-neighbour '
        'size and font metadata, separately from whether the target itself has a size or matches its neighbours. '
        'Local fonts are indexed by their actual full/PostScript names, with no substitutions. '
        'Font availability is a prerequisite, not a claim of source-binary/build equivalence.\n\n'
        'Outputs: config.json, per_target.csv.gz (hashes/lengths only), summary.csv, '
        'font_availability.csv, pinned_font_availability.csv, local_font_files.json. '
        'Missing fonts are explicit; no attacker-performance table is fabricated.\n\n'
        'The supplied instruction requires stopping if a run cannot execute because prerequisites are missing. '
        'Provide the missing neighbour fonts with suitable local-use rights and the pinned study binaries '
        '(see availability tables), then rerun the preflight with additional --font-dir paths. '
        'Later experiment prompts have not started.\n')
    for row in summary: print(json.dumps(row),flush=True)
    print('Missing pinned fonts:',missing_pinned,'Missing neighbour identities:',len(absent),flush=True)
    return 2 if blocked else 0

if __name__=='__main__': raise SystemExit(main())
