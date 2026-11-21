#!/usr/bin/env python3
"""B2: local OCR and word concealment, reusing the archived Table A9 boxes."""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import unicodedata
import zipfile
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path

sys.dont_write_bytecode=True
os.environ['OMP_THREAD_LIMIT']='1'
os.environ['OMP_NUM_THREADS']='1'
os.environ['TESSDATA_PREFIX']='/opt/homebrew/share/tessdata/'
import numpy as np
from PIL import Image,ImageDraw
import pytesseract
from existing import load,ROOT

HERE=Path(__file__).resolve().parent
CACHE=HERE/'.cache'
SEED=20261121
SETTINGS='--oem 1 --psm 3'
POLICIES=['exact','grid-16','grid-64','start-aligned-128','field-1000']
GT_SOURCE='FUNSD only: no matching born-digital source PDFs for the 500 DocLayNet evaluation pages were available locally'

def sha(s):return hashlib.sha256(s.encode('utf-8')).hexdigest()
def digest(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def norm(s):return unicodedata.normalize('NFKC',s).strip()
def read(p):
    with Path(p).open(newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    assert rows,str(p)
    with Path(p).open('w',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def command(args):return subprocess.run(args,capture_output=True,text=True,check=True).stdout
def area(box):return max(0,box[2]-box[0])*max(0,box[3]-box[1])
def clipped(box,size):
    w,h=size
    return tuple(int(v) for v in [max(0,min(w,box[0])),max(0,min(h,box[1])),max(0,min(w,box[2])),max(0,min(h,box[3]))])
def overlaps(boxes,mask):
    b=np.asarray(boxes,dtype=np.int64);m=np.asarray(mask)
    return np.maximum(0,np.minimum(b[:,2],m[2])-np.maximum(b[:,0],m[0]))*np.maximum(0,np.minimum(b[:,3],m[3])-np.maximum(b[:,1],m[1]))

def match_words(gt,ocr):
    """One-to-one, geometry-only greedy matching, descending IoU, deterministic ties."""
    correct=np.zeros(len(gt),dtype=bool);insensitive=correct.copy()
    if not ocr:return correct,insensitive
    a=np.asarray([w['box'] for w in gt],dtype=np.float64)
    b=np.asarray([w[:4] for w in ocr],dtype=np.float64)
    dx=np.maximum(0,np.minimum(a[:,None,2],b[None,:,2])-np.maximum(a[:,None,0],b[None,:,0]))
    dy=np.maximum(0,np.minimum(a[:,None,3],b[None,:,3])-np.maximum(a[:,None,1],b[None,:,1]))
    intersection=dx*dy
    union=((a[:,2]-a[:,0])*(a[:,3]-a[:,1]))[:,None]+((b[:,2]-b[:,0])*(b[:,3]-b[:,1]))[None,:]-intersection
    iou=np.divide(intersection,union,out=np.zeros_like(intersection),where=union>0)
    edges=[(-float(iou[i,j]),int(i),int(j)) for i,j in np.argwhere(iou>=.5)]
    used_gt=set();used_ocr=set()
    for _,i,j in sorted(edges):
        if i in used_gt or j in used_ocr:continue
        used_gt.add(i);used_ocr.add(j)
        correct[i]=gt[i]['sha256']==ocr[j][4]
        insensitive[i]=gt[i]['casefold_sha256']==ocr[j][5]
    return correct,insensitive

def pdf_audit(out):
    p=ROOT/'research/doclaynet_validation/results/results_notext.csv'
    targets=[r for r in read(p) if r['role']=='evaluation' and r['size_px']=='16' and r['condition']=='matched_template_known' and r['policy']=='exact']
    assert len(targets)==954
    pages=sorted({Path(r['file_name']).stem for r in targets});assert len(pages)==500
    roots=[ROOT/'dataset',ROOT/'research/datasets/doclaynet/pages']
    found=[p for root in roots if root.exists() for p in root.rglob('*.pdf') if p.stem in set(pages)]
    if found:
        raise SystemExit('Matching DocLayNet source PDFs are now present; stop before claiming the missing-PDF fallback. Native PDF word extraction/coverage must be evaluated for the changed inputs.')
    write(out/'doclaynet_pdf_audit.csv',[dict(page_id_sha256=sha(p),source_pdf_available=0,coverage='',scale_x='',scale_y='',status='source_pdf_missing') for p in pages])
    return dict(evaluation_pages=500,inserted_targets=954,matching_source_pdfs=0,coverage_threshold=.95,
                coverage_checks_executed=0,pages_passing=0,coverage_unknown_missing_pdf=500,
                searched_roots=[str(p.relative_to(ROOT)) for p in roots],source_results_sha256=digest(p))

def field_geometry(out,B,V):
    path=HERE/'field_geometry.json'
    if path.exists():saved=json.loads(path.read_text())
    else:
        saved={};receipts=V.load_receipts()
        for size in B.SIZES:
            p=V.HERE/'data/geometry'/f'geom_surnames_DejaVuSans_{size}.npy'
            a=np.load(p);assert V.receipt_digest(a)==receipts[('DejaVuSans',size)]
            item=V.prepare_bank({('DejaVuSans',size):a},31)[('DejaVuSans',size)]
            saved[str(size)]=dict(font='DejaVuSans',size_px=size,n_candidates=1000,
                x_l=item['x_l'],max_padded_right_first1000=int(item['right'][:1000].max()),
                source_geometry_sha256=digest(p),receipt_sha256=receipts[('DejaVuSans',size)])
        path.write_text(json.dumps(saved,indent=2)+'\n')
    return {int(size):dict(x_l=r['x_l'],right=np.array([r['max_padded_right_first1000']],dtype=np.int64)) for size,r in saved.items()},saved

def prepare(out,B,V,real,D):
    pages={};targets=[];manifest=[];quality=Counter();skipped=[]
    assert B.FUNSD_ZIP.is_file(),'Local official FUNSD archive is required; no implicit download'
    archived=json.loads((V.OUT/'run_config.json').read_text())['funsd_scored']['sha256']
    assert digest(B.FUNSD_ZIP)==archived,'FUNSD archive differs from the archived experiment'
    for label,split in [('calibration','training'),('scored','testing')]:
        selected,stats=V.collect_funsd_tokens(D,set(),None,label)
        assert not stats['add_one'],'v2 coordinate convention changed; stop rather than silently altering geometry'
        splitdir=B.funsd_split_dir('training_data' if split=='training' else 'testing_data')
        grouped=defaultdict(list)
        for i,t in enumerate(selected):t['legacy_token_id']=('funsd-' if split=='testing' else 'training-funsd-')+str(i);grouped[t['page_id']].append(t)
        for p in sorted((splitdir/'annotations').glob('*.json')):
            image_path=splitdir/'images'/(p.stem+'.png');payload=json.loads(p.read_text())
            with Image.open(image_path) as original:
                mode=original.mode;image=original.copy() if mode in ['L','RGB'] else original.convert('RGB')
            image.info.clear();words=[];lookup=defaultdict(list);pid=sha(p.stem)
            for field in payload['form']:
                for wi,w in enumerate(field.get('words',[])):
                    assert isinstance(w.get('text'),str),'Ground-truth word text missing'
                    text=norm(w['text'])
                    if not text:quality['blank_word_annotations']+=1;continue
                    raw=tuple(map(int,w['box']));box=real.inclusive_to_half_open(raw);box=clipped(box,image.size)
                    if area(box)<=0:raise ValueError('Ground-truth word rectangle has no image area')
                    quality['clipped_gt_rectangles']+=int(box!=real.inclusive_to_half_open(raw))
                    quality['multiword_text_in_one_annotation']+=int(len(text.split())>1)
                    parts=B.alpha_tokens(w['text']);canonical=sha(parts[0].title()) if len(parts)==1 else None
                    index=len(words)
                    words.append(dict(box=box,sha256=sha(text),casefold_sha256=sha(text.casefold()),char_length=len(text),
                                      word_id=sha(f'{split}:{p.stem}:{field["id"]}:{wi}')))
                    if field.get('label')=='answer':lookup[(raw,canonical)].append(index)
            ts=grouped.get(p.stem,[]);consumed=set()
            for t in ts:
                key=((t['x0'],t['y0'],t['x1'],t['y1']),sha(t['token']))
                indices=[i for i in lookup[key] if i not in consumed];assert indices,('Saved selector cannot be joined',pid)
                index=indices[0];consumed.add(index)
                targets.append(dict(page_id=pid,target_id=words[index]['word_id'],target_word_index=index,
                    target_sha256=words[index]['sha256'],target_char_length=words[index]['char_length'],
                    legacy_token_id=t['legacy_token_id'],truth=int(t['truth']),size_px=t['size_px'],
                    **{k:t[k] for k in ['x0','y0','x1','y1','line_top','line_bottom']}))
            annsha=digest(p);imsha=digest(image_path)
            manifest.append(dict(page_id=pid,split=split,annotation_sha256=annsha,image_sha256=imsha,
                 image_width=image.width,image_height=image.height,source_mode=mode,ocr_mode=image.mode,
                 n_gt_words=len(words),n_surname_targets=len(ts),scale_x=1.,scale_y=1.))
            if ts:pages[pid]=dict(image=image,words=words,image_sha256=imsha,annotation_sha256=annsha,split=split)
            else:skipped.append(dict(page_id=pid,split=split,reason='no_qualifying_surname_word'))
    assert len(manifest)==199 and Counter(r['split'] for r in manifest)=={'training':149,'testing':50}
    # Check the local annotation/image bytes against the verified official ZIP.
    with zipfile.ZipFile(B.FUNSD_ZIP) as z:
        names=z.namelist()
        for splitname in ['training_data','testing_data']:
            splitdir=B.funsd_split_dir(splitname)
            for folder,extension in [('annotations','json'),('images','png')]:
                for p in (splitdir/folder).glob('*.'+extension):
                    matches=[name for name in names if name.endswith('/'+splitname+'/'+folder+'/'+p.name)]
                    assert len(matches)==1
                    with z.open(matches[0]) as stream:
                        assert hashlib.file_digest(stream,'sha256').hexdigest()==digest(p),'Local FUNSD input differs from archive'
    write(out/'input_manifest.csv',manifest);write(out/'skipped_forms.csv',skipped)
    return pages,targets,dict(quality),manifest

def ocr_job(job,pages,signature,force):
    page=pages[job['page_id']];path=CACHE/(job['key']+'.json')
    previous=json.loads(path.read_text()) if path.exists() else None
    cached=previous is not None and not force
    if cached:words=previous['words']
    else:
        image=page['image'].copy()
        if job['box'] is not None:
            x0,y0,x1,y1=job['box']
            if x1>x0 and y1>y0:ImageDraw.Draw(image).rectangle((x0,y0,x1-1,y1-1),fill=0)
        # Uncompressed local TIFF avoids repeated PNG compression; identical
        # transport and unset DPI metadata for baseline and every redaction.
        fd,tmp=tempfile.mkstemp(prefix='guard-b2-',suffix='.tif');os.close(fd)
        try:
            image.save(tmp,format='TIFF',compression='raw')
            data=pytesseract.image_to_data(tmp,lang='eng',config=SETTINGS,output_type=pytesseract.Output.DICT,timeout=120)
        finally:Path(tmp).unlink(missing_ok=True)
        words=[]
        for i,text in enumerate(data['text']):
            if int(data['level'][i])!=5 or not isinstance(text,str):continue
            text=norm(text)
            x=int(data['left'][i]);y=int(data['top'][i]);w=int(data['width'][i]);h=int(data['height'][i])
            if not text or w<=0 or h<=0:continue
            words.append([x,y,x+w,y+h,sha(text),sha(text.casefold()),len(text)])
        result=dict(signature=signature,words=words)
        tmpjson=path.with_suffix('.tmp');tmpjson.write_text(json.dumps(result,separators=(',',':')));tmpjson.replace(path)
    ocr_digest=sha(json.dumps(words,separators=(',',':')))
    old_digest=sha(json.dumps(previous['words'],separators=(',',':'))) if previous else None
    cs,ci=match_words(page['words'],words)
    return dict(cs=cs,ci=ci,n_ocr_words=len(words),ocr_sha256=ocr_digest,cache_hit=cached,
                repeated_ocr_differs=bool(force and previous is not None and old_digest!=ocr_digest))

def bootstrap(rows):
    # One vector per page; redactions on that page always travel together.
    groups=defaultdict(lambda:np.zeros(9,dtype=np.float64))
    for r in rows:
        groups[r['page_id']]+=np.array([r['n_covered50'],r['n_covered_any'],r['n_gt_words'],r['ocr_correct'],
            r['ocr_correct_case_insensitive'],r['ocr_eval_words'],r['ocr_correct_unredacted_visible'],
            r['ocr_correct_unredacted_visible_case_insensitive'],1.])
    a=np.array([groups[k] for k in sorted(groups)]);total=a.sum(axis=0)
    def measures(t):
        valid=t[...,5]>0
        cs=np.divide(t[...,3],t[...,5],out=np.full_like(t[...,3],np.nan),where=valid)
        ci=np.divide(t[...,4],t[...,5],out=np.full_like(t[...,4],np.nan),where=valid)
        drop=np.divide(100*(t[...,6]-t[...,3]),t[...,5],out=np.full_like(t[...,3],np.nan),where=valid)
        return np.stack([100*t[...,0]/t[...,2],100*t[...,1]/t[...,2],cs,ci,drop,t[...,0]/t[...,8]],axis=-1)
    point=measures(total);rng=np.random.default_rng(SEED);draws=[]
    for start in range(0,10000,100):
        totals=a[rng.integers(0,len(a),size=(100,len(a)))].sum(axis=1);draws.append(measures(totals))
    draws=np.concatenate(draws);lo=np.nanquantile(draws,.025,axis=0);hi=np.nanquantile(draws,.975,axis=0)
    return point,lo,hi,total,np.sum(np.isfinite(draws),axis=0)

def summarize(rows,out):
    summary=[]
    for policy in POLICIES:
        rs=[r for r in rows if r['policy']==policy];pt,lo,hi,total,valid=bootstrap(rs)
        r=dict(dataset='FUNSD',gt_source=GT_SOURCE,policy=policy,n_pages=len({r['page_id'] for r in rs}),n_redactions=len(rs),
               area_ratio_median=float(np.median([r['area_ratio'] for r in rs])),area_ratio_p90=float(np.quantile([r['area_ratio'] for r in rs],.9)))
        for i,key in enumerate(['words_covered50_pct','words_covered_any_pct','ocr_word_acc','ocr_word_acc_ci','ocr_drop_points','words_covered_per_redaction']):
            r.update({key:float(pt[i]),key+'_lo':float(lo[i]),key+'_hi':float(hi[i]),key+'_valid_bootstrap_draws':int(valid[i])})
        r.update(ocr_word_acc_case_insensitive=r['ocr_word_acc_ci'],ocr_acc_unredacted=float(total[6]/total[5]),
                 words_covered_any_per_redaction=float(total[1]/total[8]),
                 area_ratio_nominal_median=float(np.median([r['area_ratio_nominal'] for r in rs])),
                 n_target_not_fully_covered=sum(r['target_fully_covered']==0 for r in rs),
                 n_redactions_without_visible_gt=sum(r['ocr_eval_words']==0 for r in rs))
        summary.append(r)
    write(out/'summary.csv',summary)
    return summary

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=HERE/'results')
    parser.add_argument('--workers',type=int,default=min(8,os.cpu_count() or 1));parser.add_argument('--force-ocr',action='store_true')
    parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);CACHE.mkdir(exist_ok=True)
    binary=Path('/opt/homebrew/bin/tesseract');assert binary.is_file(),'Install Tesseract first'
    pytesseract.pytesseract.tesseract_cmd=str(binary)
    trained=Path('/opt/homebrew/share/tessdata/eng.traineddata');assert trained.is_file()
    version=command([str(binary),'--version'])
    versions={p:importlib.metadata.version(p) for p in ['numpy','Pillow','pandas','pytesseract']}
    B,V,real=load();D=B.load_dictionary();pdf=pdf_audit(out)
    geometry,params=field_geometry(out,B,V)
    pages,targets,quality,manifest=prepare(out,B,V,real,D)
    signature=sha(json.dumps(dict(tesseract_sha256=digest(binary),traineddata_sha256=digest(trained),settings=SETTINGS,
                                  lang='eng',transport='uncompressed TIFF, no DPI override',omp=1),sort_keys=True))
    config=dict(status='prepared',gt_source=GT_SOURCE,doclaynet=pdf,bootstrap_seed=SEED,bootstrap_resamples=10000,
        bootstrap_unit='page',tesseract_path=str(binary),tesseract_version=version,tesseract_binary_sha256=digest(binary),
        eng_traineddata_path=str(trained),eng_traineddata_sha256=digest(trained),versions=versions,
        tesseract_settings=SETTINGS,tesseract_language='eng',TESSDATA_PREFIX=os.environ['TESSDATA_PREFIX'],OMP_THREAD_LIMIT=1,OMP_NUM_THREADS=1,
        image_transport='uncompressed temporary local TIFF; pixels/mode preserved; DPI metadata unset for baseline and every policy; no invented DPI',
        normalization='Unicode NFKC and strip boundary whitespace; case-insensitive uses Unicode casefold; punctuation retained',
        matching='one-to-one descending-IoU greedy geometry-only matching, IoU>=0.5; ties by annotation order then OCR output order; no text-assisted matching',
        target_selection='existing run_v2.collect_funsd_tokens on all 149 training and 50 test forms, all surname-list answer words, no likely-name filter; every target redacted independently',
        ground_truth='all nonempty FUNSD annotated word entries, all entity labels; existing funsd_real.inclusive_to_half_open, clipped to image; exact target word excluded from utility denominators',
        gt_quality=quality,n_forms=199,n_forms_with_targets=len(pages),n_forms_skipped=199-len(pages),n_targets=len(targets),
        field_policy='existing Table A9 first-1000 DejaVuSans surrogate field at nearest 12/16/24px word-height proxy; only truths within first 1000; not an annotated native FUNSD field',
        field_geometry=params,area_ratio='actual clipped rectangle pixels / clipped exact requested rectangle pixels; nominal un-clipped ratio additionally saved for archive comparison',
        baseline='unredacted OCR evaluated on the identical visible non-target word subset for each mask; full-page baseline also saved',
        aggregation='pooled word-observation ratios over separate target redactions; resample complete pages with all their redactions; per_page.csv has one target-policy row; per_page_aggregate.csv supplies page-policy totals',
        units=dict(words_covered50_pct='percent',words_covered_any_pct='percent',ocr_word_acc='fraction',ocr_word_acc_ci='case-insensitive fraction (not confidence interval)',ocr_drop_points='percentage points'),
        workers=args.workers,force_ocr=args.force_ocr,source_script_sha256=digest(Path(__file__)),
        policy_source_sha256=digest(ROOT/'research/realworld_e1_eval/run_eval.py'),
        selection_source_sha256=digest(ROOT/'research/realworld_e1_eval/run_v2.py'),
        funsd_helpers_sha256=digest(ROOT/'research/funsd_validation/funsd_real.py'),
        import_adapter='only unused import of unreleased DocLayNet download_sample omitted in memory; all selected function bodies unchanged',
        census_sha256=D['census_sha256'],source_funsd_zip_sha256=digest(B.FUNSD_ZIP),policies=POLICIES,
        command=f'.venv/bin/python -B research/area_eval/run_area_eval.py --workers {args.workers} --out {out}'+(' --force-ocr' if args.force_ocr else ''))
    records=[];jobs={}
    def jobkey(pid,box):
        page=pages[pid]
        k=sha(json.dumps([signature,page['image_sha256'],page['annotation_sha256'],pid,box],separators=(',',':')))
        jobs.setdefault(k,dict(key=k,page_id=pid,box=box));return k
    baselines={pid:jobkey(pid,None) for pid in pages}
    for t in targets:
        page=pages[t['page_id']];size=page['image'].size
        exact=tuple(map(int,B.released_box(t,None,'exact',0)));exactclip=clipped(exact,size)
        for policy in POLICIES:
            if policy=='field-1000' and t['truth']>=1000:continue
            item=geometry[t['size_px']]
            box=tuple(map(int,B.released_box(t,item,'field' if policy=='field-1000' else policy,128 if policy=='start-aligned-128' else 0)))
            clip=clipped(box,size)
            records.append(dict(t,policy=policy,box=box,paint_box=clip,exact_box=exact,
                area_ratio=area(clip)/area(exactclip),area_ratio_nominal=area(box)/area(exact),
                ocr_job=jobkey(t['page_id'],clip)))
    config.update(n_redactions=len(records),n_unique_ocr_jobs=len(jobs),n_baseline_jobs=len(baselines),field_targets=sum(t['truth']<1000 for t in targets))
    early_archive={(r['token_id'],r['policy']):r for r in read(ROOT/'research/realworld_e1_eval/results/v2/per_token_notext.csv') if r['dataset']=='FUNSD'}
    early_checks=0
    for r in records:
        key=(r['legacy_token_id'],r['policy'])
        if key in early_archive:
            assert tuple(map(int,early_archive[key]['box'].split(',')))==r['box'],'Policy differs from archived Table A9 box'
            early_checks+=1
    assert early_checks==3198
    config['paired_policy_boxes_checked_before_ocr']=early_checks
    (out/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    print('Prepared forms/targets/redactions/unique OCR jobs',len(pages),len(targets),len(records),len(jobs),flush=True)
    if args.prepare_only:return
    results={};start=time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(ocr_job,j,pages,signature,args.force_ocr):k for k,j in sorted(jobs.items())}
        for i,future in enumerate(as_completed(futures),1):
            results[futures[future]]=future.result()
            if i%100==0 or i==len(jobs):print('OCR jobs',i,'/',len(jobs),'elapsed_s',round(time.monotonic()-start,1),flush=True)
    per=[];reference=[]
    archive={(r['token_id'],r['policy']):r for r in read(ROOT/'research/realworld_e1_eval/results/v2/per_token_notext.csv') if r['dataset']=='FUNSD'}
    for r in sorted(records,key=lambda r:(r['page_id'],r['target_id'],POLICIES.index(r['policy']))):
        page=pages[r['page_id']];gt=page['words'];g=np.array([w['box'] for w in gt],dtype=np.int64)
        inter=overlaps(g,r['paint_box']);a=(g[:,2]-g[:,0])*(g[:,3]-g[:,1])
        neighbour=np.ones(len(gt),dtype=bool);neighbour[r['target_word_index']]=False
        covered50=(2*inter>=a)&neighbour;coveredany=(inter>0)&neighbour;visible=(2*inter<a)&neighbour
        current=results[r['ocr_job']];base=results[baselines[r['page_id']]];n=int(visible.sum())
        item=dict(dataset='FUNSD',page_id=r['page_id'],split=page['split'],target_id=r['target_id'],
            target_sha256=r['target_sha256'],target_char_length=r['target_char_length'],policy=r['policy'],
            n_gt_words=len(gt)-1,n_gt_words_total=len(gt),n_covered50=int(covered50.sum()),n_covered_any=int(coveredany.sum()),
            ocr_correct=int(current['cs'][visible].sum()),ocr_correct_case_insensitive=int(current['ci'][visible].sum()),
            ocr_eval_words=n,ocr_correct_unredacted_visible=int(base['cs'][visible].sum()),
            ocr_correct_unredacted_visible_case_insensitive=int(base['ci'][visible].sum()),
            ocr_acc_unredacted=float(base['cs'][visible].mean()) if n else '',
            ocr_acc_unredacted_fullpage=float(base['cs'].mean()),
            area_ratio=r['area_ratio'],area_ratio_nominal=r['area_ratio_nominal'],
            target_fully_covered=int(inter[r['target_word_index']]>=a[r['target_word_index']]),
            target_coverage_fraction=float(inter[r['target_word_index']]/a[r['target_word_index']]),
            requested_box=','.join(map(str,r['box'])),painted_box=','.join(map(str,r['paint_box'])),
            ocr_output_sha256=current['ocr_sha256'])
        per.append(item)
        if (r['legacy_token_id'],r['policy']) in archive:
            old=archive[(r['legacy_token_id'],r['policy'])];oldbox=tuple(map(int,old['box'].split(',')))
            oldexact=tuple(map(int,archive[(r['legacy_token_id'],'exact')]['box'].split(',')))
            oldratio=area(oldbox)/area(oldexact)
            reference.append(dict(policy=r['policy'],target_id=r['target_id'],legacy_token_id=r['legacy_token_id'],
                 box_matches=int(oldbox==r['box']),archived_nominal_area_ratio=oldratio,new_nominal_area_ratio=r['area_ratio_nominal'],
                 new_clipped_area_ratio=r['area_ratio'],nominal_ratio_matches=int(math.isclose(oldratio,r['area_ratio_nominal'],abs_tol=1e-12)),
                 clipped_ratio_differs=int(not math.isclose(oldratio,r['area_ratio'],abs_tol=1e-12))))
    write(out/'per_page.csv',per);write(out/'area_reference_checks.csv',reference)
    totals=defaultdict(lambda:defaultdict(int))
    for r in per:
        key=(r['page_id'],r['policy']);totals[key]['n_redactions']+=1
        for field in ['n_gt_words','n_covered50','n_covered_any','ocr_correct','ocr_correct_case_insensitive','ocr_eval_words','ocr_correct_unredacted_visible']:
            totals[key][field]+=r[field]
    write(out/'per_page_aggregate.csv',[dict(dataset='FUNSD',page_id=pid,policy=policy,**values) for (pid,policy),values in sorted(totals.items())])
    summary=summarize(per,out)
    exact={r['target_id']:r for r in per if r['policy']=='exact'};grid={r['target_id']:r for r in per if r['policy']=='grid-64'}
    assert set(exact)==set(grid)
    assert all(grid[k]['n_covered50']>=exact[k]['n_covered50'] for k in exact)
    assert np.mean([r['n_covered50'] for r in exact.values()])<np.mean([r['n_covered50'] for r in grid.values()])
    assert all(r['box_matches'] and r['nominal_ratio_matches'] for r in reference)
    config.update(status='complete',fresh_ocr_jobs=sum(not r['cache_hit'] for r in results.values()),
        cache_hits=sum(r['cache_hit'] for r in results.values()),repeated_ocr_output_differences=sum(r['repeated_ocr_differs'] for r in results.values()),
        sanity_exact_words_per_redaction=float(np.mean([r['n_covered50'] for r in exact.values()])),
        sanity_grid64_words_per_redaction=float(np.mean([r['n_covered50'] for r in grid.values()])),
        archived_box_comparisons=len(reference),archived_box_mismatches=sum(not r['box_matches'] for r in reference),
        archived_nominal_ratio_mismatches=sum(not r['nominal_ratio_matches'] for r in reference),
        archived_ratio_differences_due_to_image_clipping=sum(r['clipped_ratio_differs'] for r in reference))
    (out/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    lines=['# B2: neighbouring words covered and local OCR accuracy','',GT_SOURCE+'.','',
       'All 199 FUNSD forms were read. Every qualifying surname word is a separate redaction; forms with none are counted in skipped_forms.csv. Ground truth uses the supplied word-level annotations across all entity labels. No OCR-derived word boxes are treated as ground truth.','',
       'Policies and target selection execute the existing Table A9 functions. The first-1000 field is the original DejaVuSans/word-height surrogate and is only evaluated for in-list surnames; it is not an annotated native blank field. The FUNSD entity-level validation does not compute such a field, so its entity-level area summaries are not comparable to this word-target cohort. Paired Table A9 boxes and nominal ratios are checked directly; actual painting clips to image edges and any resulting ratio differences are reported.','',
       'One-to-one OCR matching uses descending IoU >= 0.5 with deterministic geometric ties, then exact NFKC text comparison, with a separate Unicode-casefold comparison. OCR runs locally with --oem 1 --psm 3, English, one OpenMP thread per process. All image transport uses temporary uncompressed TIFF with unchanged pixels and no invented DPI.','',
       'Covered-word denominators exclude the target. Visible-word accuracy excludes words >=50% covered. Its unredacted comparator uses exactly the same visible-word subset for each mask; full-page baseline accuracy is also saved. Per-page CSV rows represent individual target-policy redactions, with page-policy aggregates in a separate file. Pooled proportions count word observations across these separate redactions; complete pages are resampled 10,000 times, seed 20261121.','',
       '| Policy | Pages | Redactions | Median area ratio | >=50% words covered % [95% CI] | Any-overlap words % | OCR accuracy % [95% CI] | Case-insensitive % | OCR drop points [95% CI] |',
       '|---|---:|---:|---:|---|---:|---|---:|---|']
    for r in summary:
        lines.append(f"| {r['policy']} | {r['n_pages']} | {r['n_redactions']} | {r['area_ratio_median']:.3f} | {r['words_covered50_pct']:.3f} [{r['words_covered50_pct_lo']:.3f}, {r['words_covered50_pct_hi']:.3f}] | {r['words_covered_any_pct']:.3f} | {100*r['ocr_word_acc']:.3f} [{100*r['ocr_word_acc_lo']:.3f}, {100*r['ocr_word_acc_hi']:.3f}] | {100*r['ocr_word_acc_ci']:.3f} | {r['ocr_drop_points']:.3f} [{r['ocr_drop_points_lo']:.3f}, {r['ocr_drop_points_hi']:.3f}] |")
    lines+=['',f"Sanity: exact covers {config['sanity_exact_words_per_redaction']:.6f} neighbouring words per redaction versus {config['sanity_grid64_words_per_redaction']:.6f} for the 64px grid.",
       f"Paired archive checks: {len(reference)}; box mismatches {config['archived_box_mismatches']}; nominal area-ratio mismatches {config['archived_nominal_ratio_mismatches']}; actual/nominal differences from clipping {config['archived_ratio_differences_due_to_image_clipping']}. See area_reference_checks.csv.",
       '', 'Limitations: the surname-list selector also admits ordinary words sharing surname spellings; no likely-name filter is added. FUNSD word transcriptions and boxes may be imperfect. Multiword annotation entries remain one annotated unit. Font/renderer properties of the scans are unknown. Field rows use a smaller bounded-list cohort. Loss of words and OCR accuracy on the remaining words are separate quantities. No original text, page images, PDFs or credentials are distributed.','']
    (out/'README.md').write_text('\n'.join(lines))
    print('Completed redactions',len(per),'summary SHA-256',digest(out/'summary.csv'),flush=True)

if __name__=='__main__':main()
