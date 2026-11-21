#!/usr/bin/env python3
"""Available-font v4 comparison; no document text is written or uploaded.

Run with the pinned realworld_e1_eval/.venv interpreter, -B. Source page JSONs
are local prerequisites; the exact v2 target/calibration lists are never reselected.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
from PIL import ImageFont

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
OUT=HERE/'results/v4_fontmatched'
os.environ['E1_FONT_DIR']=str(HERE/'fonts')
sys.path.insert(0,str(HERE))
import run_v2 as V
sys.path.insert(0,str(HERE/'results/font_consistency'))
import run_analysis as A
B=V.base
B.E.RUN_ROOT=OUT
B.E.CACHE=OUT/'cache'
SEED=20261121
ATTACKERS=['font-known','font-estimated','renderer-mismatch','generic']
POLICIES=['nobox','exact','grid-16','grid-64','start-aligned-128','field-1000']

def sha(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()
def digest(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def identity(n):return (n or '').split('+')[-1].lstrip('/')
def read(p):
    opener=gzip.open if str(p).endswith('.gz') else open
    with opener(p,'rt',newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    assert rows, str(p)
    if str(p).endswith('.gz'):
        with Path(p).open('wb') as raw:
            with gzip.GzipFile(fileobj=raw,filename='',mode='wb',mtime=0) as z:
                with io.TextIOWrapper(z,encoding='utf-8',newline='') as f:
                    w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    else:
        with Path(p).open('w',newline='') as f:
            w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)

class Fonts:
    def __init__(self):
        self.index=json.loads((OUT/'preflight/font_name_index.json').read_text())
        self.used={}
        self.selected={};self.faces={}
    def select(self,name):
        if identity(name) in self.selected:return self.selected[identity(name)]
        fs=self.index.get(identity(name),[])
        if not fs:return None
        fs=sorted(fs,key=lambda f:(not str(f['path']).startswith(str(HERE/'fonts')),
                                    not str(f['path']).startswith('/System/Library/Fonts'),f['path'],f['face_index']))
        f=fs[0]
        assert digest(f['path'])==f['sha256'], 'Font changed since preflight'
        key=f['sha256']+':'+str(f['face_index'])
        self.used[key]=f
        self.selected[identity(name)]=key
        return key
    def face(self,key,size,engine):
        cache=(key,float(size),engine)
        if cache in self.faces:return self.faces[cache]
        f=self.used[key]
        face=ImageFont.truetype(f['path'],size,index=f['face_index'],
            layout_engine=ImageFont.Layout.RAQM if engine=='raqm' else ImageFont.Layout.BASIC)
        self.faces[cache]=face
        return face

def cell_info(payload):
    result=[]
    for ci,c in enumerate(payload.get('cells',[])):
        box=B.pixel_box(c.get('bbox') or [])
        if box is None:continue
        font=c.get('font') or {}
        result.append(dict(ci=ci,box=box,n=len(A.pieces(c.get('text',''))),
                           font=A.font(font.get('name')),size=A.size(font.get('size')),raw=c))
    return result

def context(cells,target):
    sizes=[]; fonts=[]; dims=[]
    for c in cells:
        if not A.same_line(c['box'],target['box']):continue
        n=c['n']-int(c['ci']==target['ci'])
        if n>0:
            if c['font'] is not None:fonts.extend([c['font']]*n)
            if c['size'] is not None:sizes.extend([c['size']]*n)
        # Anonymous word boxes only: never use target geometry, word identities,
        # character lengths, neighbour font names or pixel appearance in estimation.
        if c['ci']!=target['ci'] and c['n']>0:
            box=c['box'];dims.append([box[2]-box[0],box[3]-box[1]])
    return (float(np.median(sizes)) if sizes else None),A.mode(fonts),dims

def prepare(fonts,dictionary,inputs):
    saved=read(HERE/'results/v2/calibration_notext.csv')
    ids=json.loads((HERE/'results/v2/calibration_pages.json').read_text())
    calpages=set(ids['doclaynet'])
    evals=read(HERE/'results/font_consistency/per_token_notext.csv')
    evals=[r for r in evals if r['dataset']=='DocLayNet']
    exact={r['token_id']:r for r in read(HERE/'results/v2/per_token_notext.csv') if r['dataset']=='DocLayNet' and r['policy']=='exact'}
    assert len(evals)==len(exact)==5311
    bypage=defaultdict(list)
    for r in saved:
        if r['dataset']=='DocLayNet':bypage[r['page_id']].append(r)
    assert set(bypage)<=calpages
    assert not (set(bypage)&{r['page_id'] for r in evals})
    hashes={sha(name):i for i,name in enumerate(dictionary['full']['strings'])}
    cohorts={'evaluation':[],'calibration':[]};excluded=[];receipts=[]
    def emit(r,payload,cells,target,split,index,metadata=None):
        s,name,dims=context(cells,target)
        if metadata:
            assert (s if s is not None else '')==(float(metadata['line_median_size']) if metadata['line_median_size'] else '')
            assert (name or '')==metadata['line_modal_font']
        reason=''
        if s is None or not name:reason='unknown_neighbour_size_or_font'
        key=fonts.select(name) if not reason else None
        if not reason and not key:reason='font_not_available'
        if not reason and not dims:reason='no_independent_neighbour_geometry'
        m=payload.get('metadata') or {}
        scale=None
        try:scale=float(m['coco_width'])/float(m['original_width'])
        except (KeyError,TypeError,ValueError,ZeroDivisionError):pass
        if not reason and (scale is None or not math.isfinite(scale) or scale<=0):reason='unknown_page_scale'
        rid=r.get('token_id') or 'v2-calibration-'+str(index)
        base=dict(split=split,token_id=rid,page_id=r['page_id'],token_sha256=r['token_sha256'],token_char_length=r['token_char_length'],likely_name=r['likely_name'])
        if reason:excluded.append(dict(base,reason=reason));return
        truth=hashes[r['token_sha256']]
        box=target['box']
        choice,_,_=V.size_choice(target['raw'].get('font',{}).get('size'),target['raw']['bbox'][3])
        assert choice==int(r['size_px'] if 'size_px' in r else exact[r['token_id']]['size_px'])
        cohorts[split].append(dict(base,truth=truth,x0=box[0],y0=box[1],x1=box[2],y1=box[3],
             v2_size_px=choice,neighbour_size_pt=s,neighbour_size_px=s*scale,
             neighbour_font=name,neighbour_identity=identity(name),target_font=target['font'] or '',
             font_key=key,context_dimensions=json.dumps(dims,separators=(',',':'))))
    grouped=defaultdict(list)
    for r in evals:grouped[r['page_id']].append(r)
    for pid,rs in grouped.items():
        path=B.JSON_DIR/(pid+'.json');payload=json.loads(path.read_text());cells=cell_info(payload)
        receipts.append(dict(page_id=pid,split='evaluation',sha256=digest(path)))
        byci={c['ci']:c for c in cells}
        for r in rs:
            assert all(r[k]==exact[r['token_id']][k] for k in ['token_sha256','token_char_length','page_id','likely_name'])
            ci=int(r['source_id'].split('/')[0].split(':')[1]);target=byci[ci]
            assert tuple(map(int,r['source_box'].split(',')))==target['box']
            emit(r,payload,cells,target,'evaluation',0,r)
    for num,(pid,rs) in enumerate(bypage.items()):
        path=B.JSON_DIR/(pid+'.json');payload=json.loads(path.read_text());cells=cell_info(payload);cursor=0
        receipts.append(dict(page_id=pid,split='calibration',sha256=digest(path)))
        for i,r in enumerate(rs):
            found=None
            for pos in range(cursor,len(cells)):
                c=cells[pos];parts=B.alpha_tokens(c['raw'].get('text',''))
                if len(parts)!=1 or sha(parts[0].title())!=r['token_sha256']:continue
                choice,measured,kind=V.size_choice(c['raw'].get('font',{}).get('size'),c['raw']['bbox'][3])
                if choice!=int(r['size_px']) or not math.isclose(measured,float(r['height_px']),abs_tol=1e-8):continue
                found=c;cursor=pos+1;break
            assert found is not None, ('Saved calibration target cannot be joined',pid,i)
            emit(r,payload,cells,found,'calibration',str(num)+'-'+str(i))
        if (num+1)%1500==0:print('Prepared calibration pages',num+1,flush=True)
    for split,rows in cohorts.items():write(OUT/(split+'_cohort.csv.gz'),rows)
    write(OUT/'excluded.csv.gz',excluded);write(OUT/'source_page_receipts.csv',receipts)
    return cohorts,saved,excluded

class Geometry:
    def __init__(self,fonts,dictionary,probes):
        self.fonts=fonts;self.dictionary=dictionary;self.probes=probes;self.arrays={};self.features={};self.manifest={}
        (OUT/'cache').mkdir(exist_ok=True)
        self.quantiles=np.array([.1,.25,.5,.75,.9])
        self.study={}
        receipts=V.load_receipts()
        for name in B.E.FONTS:
            for size in B.SIZES:
                p=HERE/'data/geometry'/f'geom_surnames_{name}_{size}.npy' if name!='NotoSans' else B.GEOM_DIR/f'geom_surnames_{name}_{size}.pkl'
                a=np.load(p)
                assert V.receipt_digest(a)==receipts[(name,size)]
                self.study[(name,float(size))]=a
    def truth_bounds(self,key,size,engine,truth):
        if key.startswith('study:') and (key[6:],float(size)) in self.study:
            return self.study[(key[6:],float(size))][truth]
        realkey=self.fonts.select(key[6:]) if key.startswith('study:') else key
        return self.fonts.face(realkey,float(size),engine).getbbox(self.dictionary['full']['strings'][truth],anchor='ls')
    def bounds(self,key,size,engine):
        k=(key,float(size),engine)
        if k in self.arrays:return self.arrays[k]
        if key.startswith('study:') and (key[6:],float(size)) in self.study:
            a=self.study[(key[6:],float(size))];source='receipt-matched archived study geometry'
        else:
            realkey=self.fonts.select(key[6:]) if key.startswith('study:') else key
            assert realkey is not None, ('Cannot render unavailable font',key,size)
            cachekey=sha(json.dumps([realkey,float(size).hex(),engine,self.dictionary['census_sha256']]))
            p=OUT/'cache'/(cachekey+'.npy')
            if p.exists():a=np.load(p);source='deterministic local render cache'
            else:
                face=self.fonts.face(realkey,float(size),engine)
                a=np.array([face.getbbox(s,anchor='ls') for s in self.dictionary['full']['strings']],dtype=np.int32)
                np.save(p,a);source='fresh local rendering'
                print('Rendered full candidate bank',len(self.manifest)+1,engine,float(size),flush=True)
        assert a.shape==(50000,4)
        self.arrays[k]=a
        self.manifest[str(k)]=dict(font_key=key,size_px=float(size),engine=engine,source=source,geometry_sha256=V.receipt_digest(a))
        return a
    def feature(self,name,size):
        k=(name,float(size))
        if k not in self.features:
            if k in self.study:a=self.study[k][self.probes]
            else:
                key=self.fonts.select(name);assert key
                face=self.fonts.face(key,float(size),'raqm')
                strings=self.dictionary['full']['strings']
                a=np.array([face.getbbox(strings[i],anchor='ls') for i in self.probes],dtype=np.int32)
            dims=np.column_stack([a[:,2]-a[:,0],a[:,3]-a[:,1]])
            assert np.all(dims>0)
            self.features[k]=np.log(np.quantile(dims,self.quantiles,axis=0))
        return self.features[k]
    def estimate(self,dimensions,stored):
        obs=np.log(np.quantile(np.asarray(dimensions),self.quantiles,axis=0))
        best=None
        for name in B.E.FONTS:
            sizes=sorted(set([12.,16.,24.]+([float(stored)] if name!='NotoSans' and stored>1 else [])))
            for size in sizes:
                distance=float(np.mean((obs-self.feature(name,size))**2))
                candidate=(distance,list(B.E.FONTS).index(name),size,name)
                if best is None or candidate<best:best=candidate
        return best[3],best[2],best[0]

def hydrate(rows):
    out=[]
    for r in rows:
        r=dict(r)
        for k in ['truth','x0','y0','x1','y1','v2_size_px','likely_name','token_char_length']:r[k]=int(r[k])
        for k in ['neighbour_size_pt','neighbour_size_px']:r[k]=float(r[k])
        out.append(r)
    return out

def geometry_choice(r,attacker):
    if attacker=='font-known':return r['font_key'],r['neighbour_size_px'],'raqm'
    if attacker=='renderer-mismatch':return r['font_key'],r['neighbour_size_px'],'basic'
    return 'study:'+r['estimated_font'],r['estimated_size_px'],'raqm'

def threshold(values):
    return int(np.quantile(np.asarray(values,dtype=np.int64),.95,method='inverted_cdf'))

def interval(rows):
    groups=defaultdict(lambda:np.zeros(5))
    for r in rows:groups[r['page_id']]+=np.array([r['truth_in'],r['top1'],r['top10'],r['bits'],1.])
    a=np.array([groups[k] for k in sorted(groups)]);rng=np.random.default_rng(SEED);samples=[]
    for start in range(0,10000,100):
        totals=a[rng.integers(0,len(a),size=(100,len(a)))].sum(axis=1)
        samples.append(totals[:,:4]/totals[:,4,None])
    samples=np.concatenate(samples);point=a[:,:4].sum(axis=0)/a[:,4].sum()
    return point,np.quantile(samples,.025,axis=0),np.quantile(samples,.975,axis=0)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    OUT.mkdir(exist_ok=True,parents=True)
    fonts=Fonts();renderer=V.require_renderer();dictionary=B.load_dictionary()
    sources=[HERE/'results/v2/per_token_notext.csv',HERE/'results/v2/calibration_notext.csv',
             HERE/'results/v2/calibration_pages.json',HERE/'results/font_consistency/per_token_notext.csv',
             OUT/'preflight/font_name_index.json',Path(__file__).resolve()]
    inputs={str(p.relative_to(B.ROOT)):digest(p) for p in sources}
    config=dict(status='preparing',seed=SEED,bootstrap_resamples=10000,bootstrap_unit='page',renderer=renderer,
        cohort='user-authorized available-font subset; usable line size/mode, page scale, independent neighbour text-cell boxes',
        font_mapping='exact preflight full/PostScript identity; prefer pinned study file, then system font; no family/style substitutions',
        font_known_size='median neighbour embedded pt * coco_width / original_width; exact fractional Pillow size',
        font_estimator='anonymous geometry only: minimum squared log-quantile distance of width/height at quantiles .1,.25,.5,.75,.9; 512 fixed prior-weighted Census probes, seed 20261121; no neighbour word identities, character lengths, font names or pixels',
        estimator_context='unique independent nonempty source text-cell boxes on geometric target line; target cell excluded; cells may span multiple words, so context widths need not follow the Census probe distribution',
        estimator_sizes='12,16,24 px plus known neighbour size converted to page pixels for five available pinned fonts; Noto only at receipt-matched archived 12,16,24 because pinned binary is missing',
        estimator_accuracy='strict predicted regular study identity equals neighbour modal font after PDF syntax removal; out-of-bank true identities count incorrect; target-font correctness also saved',
        policies=POLICIES,attackers=ATTACKERS,census_sha256=dictionary['census_sha256'],inputs_sha256=inputs,
        calibration='original saved v2 split; each non-generic attacker calibrated to smallest integer symmetric edge tolerance with >=95% exact truth-in on common usable calibration subset; FUNSD cannot provide font metadata',
        generic='unchanged v2 per-target metrics replayed on identical evaluation token IDs; original pooled calibration independently requantiled; frozen tolerance 31',
        feasible_model='same horizontal exact/grid feasibility, padding latent class/slack and first-1000 fixed-field model as v2; unknown pen/baseline; empty feasible sets retain v2 prior fallback',
        field_cohort='first-1000-surname field uses only targets whose truth is in the first 1000, and the renormalized first-1000 prior, exactly as v2; reported n differs',
        missing_fonts='excluded, not substituted; name match does not establish original font-binary/build equality',
        output_text='only SHA-256 and character length, copied from saved lists; no document text redistributed',
        metric_label='attacker performance (bits)',stage='available-font comparison')
    (OUT/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    meta=OUT/'prepared_manifest.json'
    if meta.exists() and json.loads(meta.read_text())['inputs_sha256']==inputs:
        cache=json.loads(meta.read_text());fonts.used=cache['fonts']
        cohorts={s:read(OUT/(s+'_cohort.csv.gz')) for s in ['evaluation','calibration']}
        excluded=read(OUT/'excluded.csv.gz');saved=read(HERE/'results/v2/calibration_notext.csv')
    else:
        cohorts,saved,excluded=prepare(fonts,dictionary,inputs)
        meta.write_text(json.dumps(dict(inputs_sha256=inputs,fonts=fonts.used),indent=2)+'\n')
    cohorts={s:hydrate(rs) for s,rs in cohorts.items()}
    config['n_evaluation']=len(cohorts['evaluation']);config['n_calibration']=len(cohorts['calibration'])
    config['exclusions']={s:dict(Counter(r['reason'] for r in excluded if r['split']==s)) for s in cohorts}
    config['fonts']=fonts.used
    (OUT/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    print('Common cohorts',config['n_evaluation'],config['n_calibration'],flush=True)
    if args.prepare_only:return
    rng=np.random.default_rng(SEED);probes=rng.choice(50000,size=512,replace=True,p=dictionary['full']['p'])
    config['estimator_probe_indices']=probes.tolist()
    geom=Geometry(fonts,dictionary,probes)
    # A font file/name match is not sufficient: reject font-size cells that the
    # pinned FreeType renderer cannot execute. Do not replace failed widths.
    bad=set();failures=[]
    for split,rs in cohorts.items():
        for r in rs:
            cell=(r['font_key'],r['neighbour_size_px'])
            if cell in bad:continue
            for engine in ['raqm','basic']:
                try:geom.truth_bounds(cell[0],cell[1],engine,r['truth'])
                except OSError as e:
                    bad.add(cell)
                    failures.append(dict(split=split,font_key=cell[0],size_px=cell[1],engine=engine,
                        token_sha256=r['token_sha256'],reason=str(e),phase='calibration/evaluation truth render'))
                    break
    # Validate the complete candidate alphabet/list at every evaluation cell.
    seen=set()
    for r in cohorts['evaluation']:
        cell=(r['font_key'],r['neighbour_size_px'])
        if cell in bad or cell in seen:continue
        seen.add(cell)
        for engine in ['raqm','basic']:
            try:geom.bounds(cell[0],cell[1],engine)
            except OSError as e:
                bad.add(cell)
                failures.append(dict(split='evaluation',font_key=cell[0],size_px=cell[1],engine=engine,
                    token_sha256='',reason=str(e),phase='full candidate bank render'))
                break
    if failures:write(OUT/'render_failures.csv',failures)
    render_excluded=[]
    for split,rs in cohorts.items():
        for r in rs:
            if (r['font_key'],r['neighbour_size_px']) in bad:
                render_excluded.append(dict(split=split,token_id=r['token_id'],page_id=r['page_id'],
                    token_sha256=r['token_sha256'],token_char_length=r['token_char_length'],reason='font_size_not_renderable'))
        cohorts[split]=[r for r in rs if (r['font_key'],r['neighbour_size_px']) not in bad]
        write(OUT/(split+'_renderable_cohort.csv.gz'),cohorts[split])
    if render_excluded:write(OUT/'render_excluded.csv.gz',render_excluded)
    config['render_failures']=failures
    config['render_excluded_counts']=dict(Counter(r['split'] for r in render_excluded))
    config['n_evaluation']=len(cohorts['evaluation']);config['n_calibration']=len(cohorts['calibration'])
    print('Renderable common cohorts',config['n_evaluation'],config['n_calibration'],flush=True)
    for split,rs in cohorts.items():
        for i,r in enumerate(rs):
            name,size,distance=geom.estimate(json.loads(r['context_dimensions']),r['neighbour_size_px'])
            r.update(estimated_font=name,estimated_size_px=size,estimation_distance=distance,
                     estimate_matches_neighbour=int(name==r['neighbour_identity']),estimate_matches_target=int(name==identity(r['target_font'])))
            if (i+1)%500==0:print('Estimated',split,i+1,flush=True)
        write(OUT/(split+'_estimates.csv.gz'),rs)
    # Archived generic calibration includes all original DocLayNet+FUNSD calibration tokens.
    generic_min=[int(r['min_tolerance_px']) for r in saved]
    generic_t=threshold(generic_min);assert generic_t==31
    tolerances={'generic':generic_t};rates={'generic':float(np.mean(np.array(generic_min)<=generic_t))}
    calibration=[]
    for attacker in ATTACKERS[:-1]:
        mins=[]
        for i,r in enumerate(cohorts['calibration']):
            key,size,engine=geometry_choice(r,attacker);a=geom.truth_bounds(key,size,engine,r['truth'])
            err=abs(int(a[2]-a[0])-(r['x1']-r['x0']));t=(err+1)//2;mins.append(t)
            calibration.append(dict(attacker=attacker,page_id=r['page_id'],token_id=r['token_id'],token_sha256=r['token_sha256'],
                token_char_length=r['token_char_length'],width_error_px=err,min_tolerance_px=t))
        tolerances[attacker]=threshold(mins);rates[attacker]=float(np.mean(np.array(mins)<=tolerances[attacker]))
        assert rates[attacker]>=.95
        assert tolerances[attacker]==0 or np.mean(np.array(mins)<=tolerances[attacker]-1)<.95
        print('Calibrated',attacker,tolerances[attacker],rates[attacker],flush=True)
    write(OUT/'calibration.csv.gz',calibration)
    archive={(r['token_id'],r['policy']):r for r in read(HERE/'results/v2/per_token_notext.csv') if r['dataset']=='DocLayNet'}
    records=[];bank={}
    for attacker in ATTACKERS:
        tol=tolerances[attacker]
        for r in cohorts['evaluation']:
            for policy in POLICIES:
                if policy=='field-1000' and r['truth']>=1000:continue
                if attacker=='generic':
                    old=archive[(r['token_id'],policy)]
                    assert old['token_sha256']==r['token_sha256']
                    scored=dict(truth_in=int(old['truth_in']),hit1=float(old['hit1']),hit10=float(old['hit10']),bits=float(old['bits']),candidate_count=int(old['candidate_count']))
                elif policy in ['nobox','field-1000']:
                    scored=B.score_mask(dictionary,np.ones(1000 if policy=='field-1000' else 50000,dtype=bool),r['truth'],policy=='field-1000')
                else:
                    key,size,engine=geometry_choice(r,attacker);a=geom.bounds(key,size,engine);bk=(key,size,engine,tol)
                    if bk not in bank:bank[bk]=V.prepare_bank({('only',size):a},tol)
                    oldfonts=B.E.FONTS
                    # V.feasible_mask implements the exact v2 model; restrict its font loop.
                    try:
                        B.E.FONTS=('only',)
                        token=dict(r,size_px=size)
                        mask=V.feasible_mask(token,bank[bk],dictionary,policy,tol)
                    finally:B.E.FONTS=oldfonts
                    if policy=='exact':
                        assert bool(mask[r['truth']])==(abs(int(a[r['truth'],2]-a[r['truth'],0])-(r['x1']-r['x0']))<=2*tol)
                    scored=B.score_mask(dictionary,mask,r['truth'],False)
                records.append(dict(attacker=attacker,policy=policy,page_id=r['page_id'],token_id=r['token_id'],
                    token_sha256=r['token_sha256'],token_char_length=r['token_char_length'],likely_name=r['likely_name'],
                    tolerance_px=tol,truth_in=scored['truth_in'],top1=scored['hit1'],top10=scored['hit10'],bits=scored['bits'],
                    candidate_count=scored['candidate_count'],estimated_font=r['estimated_font'] if attacker=='font-estimated' else '',
                    estimated_size_px=r['estimated_size_px'] if attacker=='font-estimated' else '',
                    estimate_matches_neighbour=r['estimate_matches_neighbour'] if attacker=='font-estimated' else '',
                    estimate_matches_target=r['estimate_matches_target'] if attacker=='font-estimated' else ''))
        print('Scored',attacker,flush=True)
    write(OUT/'per_token.csv.gz',records)
    summary=[]
    for attacker in ATTACKERS:
        for policy in POLICIES:
            rs=[r for r in records if r['attacker']==attacker and r['policy']==policy]
            if not rs:continue
            point,lo,hi=interval(rs)
            row=dict(attacker=attacker,policy=policy,n_tokens=len(rs),tolerance_px=tolerances[attacker],calib_truth_in=rates[attacker])
            for i,k in enumerate(['truth_in','top1','top10','bits']):row.update({k:float(point[i]),k+'_lo':float(lo[i]),k+'_hi':float(hi[i])})
            row['font_estimate_accuracy']=float(np.mean([r['estimate_matches_neighbour'] for r in rs])) if attacker=='font-estimated' else ''
            summary.append(row)
    write(OUT/'summary.csv',summary)
    config.update(status='complete_available_font_subset',tolerances_px=tolerances,calibration_truth_in=rates,
                  font_geometry=list(geom.manifest.values()),fonts=fonts.used,
                  estimator_accuracy=dict(neighbour=float(np.mean([r['estimate_matches_neighbour'] for r in cohorts['evaluation']])),
                      target=float(np.mean([r['estimate_matches_target'] for r in cohorts['evaluation']])),
                      exact_true_neighbour_in_regular_bank=sum(r['neighbour_identity'] in B.E.FONTS for r in cohorts['evaluation'])))
    for p,expected in inputs.items():assert digest(B.ROOT/p)==expected
    (OUT/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    print('Wrote summary rows',len(summary),flush=True)

if __name__=='__main__':main()
