#!/usr/bin/env python3
"""Check area/OCR prerequisites, without replacing ground truth with OCR estimates."""
import csv
import gzip
import hashlib
import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def write(p,rows):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)

def main():
    source=ROOT/'research/doclaynet_validation/results/results_notext.csv'
    with source.open(newline='') as f:
        rows=[r for r in csv.DictReader(f) if r['role']=='evaluation' and r['size_px']=='16'
              and r['condition']=='matched_template_known' and r['policy']=='exact']
    assert len(rows)==954
    pages=sorted({r['file_name'] for r in rows})
    inventory=[]
    for name in pages:
        p=ROOT/'research/realworld_e1_eval/data/doclaynet/json'/Path(name).with_suffix('.json')
        record=dict(page_id=Path(name).stem,local_text_cells_json_available=int(p.exists()),
                    json_sha256='',n_text_cells='',n_multiword_cells='',explicit_word_box_structure='')
        if p.exists():
            payload=json.loads(p.read_text());cells=payload.get('cells',[])
            record.update(json_sha256=digest(p),n_text_cells=len(cells),
                          n_multiword_cells=sum(len((c.get('text') or '').split())>1 for c in cells),
                          explicit_word_box_structure=int(any(isinstance(c.get('words'),list) and c['words'] for c in cells)))
        inventory.append(record)
    # DocLayNet COCO/cache boxes are layout regions, not word annotations. Its
    # extra text cells often span multiple words. The old neighbour counts are
    # explicitly OCR proportional-split estimates, not ground-truth word boxes.
    reliability=dict(Counter(r['ocr_reliability'] for r in rows))
    binary=shutil.which('tesseract')
    version=None
    if binary:
        result=subprocess.run([binary,'--version'],capture_output=True,text=True)
        version=(result.stdout+result.stderr).splitlines()[0] if result.returncode==0 else None
    annotations=ROOT/'research/realworld_e1_eval/data/funsd/extracted/dataset/testing_data/annotations'
    forms=sorted(annotations.glob('*.json'));word_boxes=0
    for p in forms:
        payload=json.loads(p.read_text())
        word_boxes+=sum(isinstance(w.get('box'),list) and len(w['box'])==4
                        for field in payload['form'] for w in field.get('words',[]))
    blockers=[]
    if not binary or not version:blockers.append('Tesseract executable not available in PATH; OCR/version/language-data validation cannot run')
    blockers.append('Ground-truth word boxes for the DocLayNet insertion pages are not provided by the existing layout-region cache; multiword extracted cells and previous OCR proportional splits are not ground-truth word boxes')
    config=dict(status='blocked_preflight',experiment_started=False,bootstrap_seed=20261121,
        bootstrap_resamples=10000,bootstrap_unit='page',planned_tesseract_psm=6,
        policies=['exact','grid-16','grid-64','start-aligned-128','field'],class_width_px=128,
        source_results_sha256=digest(source),preflight_code_sha256=digest(Path(__file__)),doclaynet_requested_targets=954,
        doclaynet_targeted_pages=len(pages),doclaynet_existing_count_methods=reliability,
        doclaynet_word_box_granularity_unknown_pages=sum(r['explicit_word_box_structure']=='' for r in inventory),
        tesseract_path=binary,tesseract_version=version,tesseract_language_data_sha256=None,
        word_box_definition='individual ground-truth word rectangle; do not split multiline/multiword cell rectangles or treat OCR estimates as ground truth',
        blockers=blockers,document_text_uploaded=False,
        no_metrics_produced='No redactions or OCR were run; preflight_summary.csv is an input/capability inventory, not summary.csv of the requested experiment')
    (HERE/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    write(HERE/'preflight_pages.csv',inventory)
    write(HERE/'preflight_targets.csv',[{k:r[k] for k in ['target_id','file_name','string_sha256','string_char_length','box_x0','box_y0','box_x1','box_y1']} for r in rows])
    summary=[dict(item='DocLayNet saved insertion targets',count=len(rows)),
             dict(item='DocLayNet distinct targeted pages',count=len(pages)),
             dict(item='Targeted pages with local extra text-cell JSON',count=sum(r['local_text_cells_json_available'] for r in inventory)),
             dict(item='Audited pages with explicit word-box structure',count=sum(r['explicit_word_box_structure']==1 for r in inventory)),
             dict(item='Pages with unknown word-box structure because JSON is unavailable',count=sum(r['explicit_word_box_structure']=='' for r in inventory)),
             dict(item='FUNSD test annotations present',count=len(forms)),
             dict(item='FUNSD annotated word boxes',count=word_boxes)]
    write(HERE/'preflight_summary.csv',summary)
    (HERE/'README.md').write_text(
        '# Area/OCR evaluation: prerequisite check only\n\n'
        'No area/concealment/OCR performance table was generated. See config.json for blockers. '
        'The existing DocLayNet cache contains layout blocks. Extra text cells may contain multiple words, '
        'and the old neighbour-word figures are labelled OCR proportional-split estimates. '
        'Those cannot be relabelled as exact ground-truth word rectangles for any-overlap or 50%-area measurements. '
        'Tesseract must also be available with a fixed version, mode and hashed language data before OCR runs.\n\n'
        'preflight_targets.csv reuses the exact 954 saved insertion targets and contains only hashes/lengths '
        'for inserted text. preflight_pages.csv and preflight_summary.csv record local annotation availability. '
        'No source images, raw annotation JSONs or document text are copied into this folder.\n\n'
        'Required to continue: individual ground-truth word boxes/text for the DocLayNet pages, '
        'and a usable local Tesseract installation/language model. Alternatively, a separately authorized '
        'proxy protocol must be explicitly labelled as such; it is not the requested ground-truth experiment.\n')
    print(json.dumps(config,indent=2))
    for row in summary:print(json.dumps(row))
    return 2

if __name__=='__main__':raise SystemExit(main())
