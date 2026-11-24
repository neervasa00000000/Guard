#!/usr/bin/env python3
"""Optional attacker, isolated from generic-attacker; no target selection or font substitution."""
import json
import math
import os
import sys
from collections import defaultdict, Counter
import numpy as np
import run_analysis as A

sys.dont_write_bytecode=True
os.environ['E1_FONT_DIR']=str(A.HERE/'fonts')
base=A.base
base.E.RUN_ROOT=A.OUT
base.E.CACHE=A.OUT/'cache'
sys.path.insert(0,str(A.HERE))
import run_generic_attacker as generic_attacker

def map_exact(name):
    # Subset tags and PDF leading slash are not family/style identity.
    name=(name or '').split('+')[-1].lstrip('/')
    return name if name in base.E.FONTS else None

def enrich(r,metadata):
    f=map_exact(r['line_modal_font'])
    med=A.size(r['line_median_size'])
    width=A.size(metadata.get('original_width'))
    coco=A.size(metadata.get('coco_width'))
    if f is None or med is None or width is None or coco is None: return None
    return dict(**r,matched_font=f,neighbour_size_pt=med,render_size_px=med*coco/width)

def calibration():
    saved=A.read(A.HERE/'results/generic_attacker/calibration.csv')
    by_page=defaultdict(list)
    for i,r in enumerate(saved):
        if r['dataset']=='DocLayNet': by_page[r['page_id']].append((i,r))
    out=[]; font_mapped=0
    for number,(pid,targets) in enumerate(by_page.items()):
        payload=json.loads((base.JSON_DIR/(pid+'.json')).read_text())
        cells=payload.get('cells',[])
        # A mapped line mode cannot occur if no cell has a mapped font.
        if not any(map_exact((c.get('font') or {}).get('name')) for c in cells): continue
        words=[]; source=[]
        for ci,c in enumerate(cells):
            box=base.pixel_box(c.get('bbox') or [])
            if box is None: continue
            f=c.get('font') or {}; cellwords=[]
            for wi,text in enumerate(A.pieces(c.get('text',''))):
                w=dict(text=text,box=box,size=A.size(f.get('size')),font=A.font(f.get('name')),source_id=f'cell:{ci}/word:{wi}')
                words.append(w); cellwords.append(w)
            source.append((c,box,cellwords))
        cursor=0
        for index,s in targets:
            found=None
            for pos in range(cursor,len(source)):
                c,box,ws=source[pos]; parts=base.alpha_tokens(c.get('text',''))
                if len(parts)!=1 or parts[0].casefold()!=s['token'].casefold(): continue
                rawh=float(c['bbox'][3]); choice,measured,kind=generic_attacker.size_choice((c.get('font') or {}).get('size'),rawh)
                if choice!=int(s['size_px']) or not math.isclose(measured,float(s['height_px']),abs_tol=1e-8): continue
                matches=[w for w in ws if base.alpha_tokens(w['text'])==parts]
                assert len(matches)==1
                found=matches[0]; cursor=pos+1; break
            assert found is not None, ('calibration join failed',index,s)
            ns=[w for w in words if w is not found and A.same_line(w['box'],found['box'])]
            st=A.stats(found,ns,'line','DocLayNet')
            if map_exact(st['line_modal_font']): font_mapped+=1
            rec=enrich(dict(s,token_id=f'v2-calibration-row-{index}',line_modal_font=st['line_modal_font'],line_median_size=st['line_median_size'],source_box=','.join(map(str,found['box']))),payload['metadata'])
            if rec: out.append(rec)
        if number%2000==0: print('Calibration pages visited',number,flush=True)
    return out,dict(total_calibration_tokens=len(saved),doclaynet_calibration_tokens=sum(r['dataset']=='DocLayNet' for r in saved),
                    mapped_font_calibration_tokens=font_mapped,usable_calibration_tokens=len(out))

def main():
    before=A.protected(); renderer=generic_attacker.require_renderer(); dictionary=base.load_dictionary()
    rows=A.read(A.OUT/'per_token.csv'); scored=[]; mapped=0
    for r in rows:
        if r['dataset']!='DocLayNet': continue
        if map_exact(r['line_modal_font']): mapped+=1
        p=json.loads((base.JSON_DIR/(r['page_id']+'.json')).read_text())
        e=enrich(r,p['metadata'])
        if e: scored.append(e)
    cal,coverage=calibration()
    assert not ({r['page_id'] for r in cal}&{r['page_id'] for r in scored})
    keys=sorted({(r['matched_font'],r['render_size_px']) for r in scored+cal})
    raw={}
    for i,(font,sz) in enumerate(keys):
        face=base.E.font(font,sz)
        arr=np.array([face.getbbox(n,anchor='ls') for n in dictionary['full']['strings']],dtype=np.int32)
        raw[(font,sz)]=arr
        np.save(A.OUT/f'attacker_geometry_{i:03d}.npy',arr)
        print('Rendered neighbour font/size',i+1,len(keys),font,sz,flush=True)
    for r in cal:
        truth=dictionary['index'][r['token'].casefold()]
        box=list(map(int,r['source_box'].split(',')))
        g=raw[(r['matched_font'],r['render_size_px'])]
        err=abs(int(g[truth,2]-g[truth,0])-(box[2]-box[0]))
        r['width_error_px']=err; r['min_tolerance_px']=math.ceil(err/2)
    assert cal, 'No mapped calibration tokens; cannot calibrate'
    tolerance=int(np.quantile([r['min_tolerance_px'] for r in cal],.95,method='inverted_cdf'))
    for r in cal: r['truth_in']=int(r['min_tolerance_px']<=tolerance)
    bank={k:base.E.Cell(a.astype(np.int64),tuple([(-tolerance,tolerance)]*4),0) for k,a in raw.items()}
    records=[]
    for r in scored:
        truth=dictionary['index'][r['token'].casefold()]
        x0,y0,x1,y1=map(int,r['box'].split(','))
        cell=bank[(r['matched_font'],r['render_size_px'])]
        mask=base.horizontal_feasible(cell,x0,x1,1)
        score=base.score_mask(dictionary,mask,truth,False)
        nobox=base.score_mask(dictionary,np.ones(50000,dtype=bool),truth,False)
        rec={k:r[k] for k in ['dataset','page_id','token_id','token','likely_name','matched_font','neighbour_size_pt','render_size_px','box','source_box']}
        rec.update(score); rec['nobox_hit10']=nobox['hit10']; records.append(rec)
        box=list(map(int,r['source_box'].split(','))); g=raw[(r['matched_font'],r['render_size_px'])]
        assert bool(mask[truth])==(abs(int(g[truth,2]-g[truth,0])-(box[2]-box[0]))<=2*tolerance)
    A.write('attacker_calibration.csv',cal); A.write('attacker_per_token.csv',records)
    summaries=[]
    for likely in [False,True]:
        chosen=[r for r in records if not likely or int(r['likely_name'])]
        s=dict(subset='likely names' if likely else 'all',n=len(chosen),n_pages=len({r['page_id'] for r in chosen}),tolerance_px=tolerance)
        for key in ['truth_in','hit1','hit10','nobox_hit10','bits']:
            pt,lo,hi,n,u=A.interval(chosen,key); s.update({key:pt,key+'_lo':lo,key+'_hi':hi})
        summaries.append(s)
    A.write('attacker_summary.csv',summaries)
    report=dict(coverage,scored_total=5311,mapped_font_scored=mapped,usable_scored=len(scored),unknown_scored=5311-len(scored),
                calibration_tolerance_px=tolerance,calibration_truth_in=float(np.mean([r['truth_in'] for r in cal])),
                renderer=renderer,font_mapping='exact six regular names after removing PDF subset tag and leading slash; no style/family substitution',
                size_rule='neighbour median embedded pt * metadata.coco_width / metadata.original_width; fractional Pillow size; horizontal scoring only',
                geometry=[dict(font=f,size_px=s,file=f'attacker_geometry_{i:03d}.npy',sha256=A.digest(A.OUT/f'attacker_geometry_{i:03d}.npy')) for i,(f,s) in enumerate(keys)])
    assert before==A.protected()
    report['protected_inputs_unchanged']=True
    (A.OUT/'attacker_manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    lines=['| Set | n | Truth-in % [95% CI] | Top-1 % [95% CI] | Top-10 % [95% CI] | No-box top-10 % [95% CI] | Bits [95% CI] |', '|---|---:|---|---|---|---|---|']
    for s in summaries:
        cells=[s['subset'],str(s['n'])]
        for k in ['truth_in','hit1','hit10','nobox_hit10','bits']:
            scale=1 if k=='bits' else 100
            cells.append(f"{s[k]*scale:.4f} [{s[k+'_lo']*scale:.4f}, {s[k+'_hi']*scale:.4f}]")
        lines.append('| '+' | '.join(cells)+' |')
    text=f'''The optional attacker maps **{mapped}/5,311** scored tokens to an exact regular font name; **{len(scored)}** also have a known neighbour size and page scale. It uses the **line** neighbour mode and median, with no fallback to block context. Mapping removes only PDF subset tags and a leading slash; bold, italic, condensed and other font-family substitutions are excluded. Mapped tokens are a selected subset and are not comparable to the full generic-attacker sample.

Embedded point sizes are converted to horizontal page pixels using the observed `coco_width / original_width`; the pinned Pillow/RAQM renderer renders all 50,000 surnames at that fractional size. No snapping to generic-attacker's three study sizes is used. This isolates the requested neighbour-font-and-size attacker while retaining generic-attacker's exact-box horizontal feasibility, Census prior, padding, rank/tie rules and entropy scorer. No-box top-10 uses the same mapped targets and full prior. Noto Sans's unavailable binary is never substituted.

Calibration reuses generic-attacker's saved calibration token rows, joining them in original source order without rerunning selection. Only mapped DocLayNet calibration tokens can use this attacker (FUNSD has no font metadata): **{len(cal)} usable**, out of {coverage['doclaynet_calibration_tokens']} DocLayNet calibration tokens. The original scored/calibration page split is unchanged and disjoint. The smallest integer symmetric edge tolerance reaching at least 95% truth-in on that usable calibration subset is **±{tolerance} px**, achieving **{report['calibration_truth_in']*100:.2f}%**. Evaluation CIs use the same 10,000 page-cluster draws, seed 0. Bits retain generic-attacker's convention that an empty feasible set falls back to prior entropy.

'''+ '\n'.join(lines)+'\n'
    path=A.HERE/'FONT_CONSISTENCY.md'
    old=path.read_text(); path.write_text(old.split('## Optional font-matched attacker')[0]+'## Optional font-matched attacker\n\n'+text)
    print(text,flush=True)

if __name__=='__main__': main()
