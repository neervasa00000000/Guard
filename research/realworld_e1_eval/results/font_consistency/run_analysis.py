#!/usr/bin/env python3
"""Read v2's persisted targets; write only this directory and FONT_CONSISTENCY.md."""
from __future__ import annotations
import csv
import hashlib
import json
import math
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
HERE = OUT.parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import run_eval as base

def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''): h.update(b)
    return h.hexdigest()

def protected():
    return {str(p.relative_to(ROOT)): digest(p) for folder in [base.E1, HERE/'results/v2']
            for p in sorted(folder.rglob('*')) if p.is_file()}

def read(p):
    with p.open(newline='') as f: return list(csv.DictReader(f))

def write(name, rows):
    if not rows: return
    with (OUT/name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        w.writeheader(); w.writerows(rows)

def array_items(path, key):
    """Bounded-memory reader for a top-level array in the local COCO JSON."""
    decoder = json.JSONDecoder()
    with path.open() as f:
        buf = ''
        pattern = re.compile(r'"'+re.escape(key)+r'"\s*:\s*\[')
        while True:
            buf += f.read(65536)
            m = pattern.search(buf)
            if m: buf = buf[m.end():]; break
            if len(buf) > 100000: buf = buf[-100:]
            if not buf: raise ValueError(key)
        while True:
            buf = buf.lstrip(' \r\n\t,')
            if buf.startswith(']'): return
            try:
                obj, end = decoder.raw_decode(buf)
            except json.JSONDecodeError:
                chunk = f.read(65536)
                if not chunk: raise
                buf += chunk
                continue
            yield obj
            buf = buf[end:]

def size(value):
    try: v = float(value)
    except (ValueError, TypeError): return None
    return v if math.isfinite(v) and v > 1 else None

def font(value):
    return value if isinstance(value, str) and value.strip() else None

def pieces(text):
    return re.findall(r'\S+', unicodedata.normalize('NFKC', text or '').replace('\u00ad', ''))

def mode(values):
    c = Counter(v for v in values if v is not None)
    if not c: return None
    top = max(c.values())
    winners = sorted(k for k, n in c.items() if n == top)
    return winners[0] if len(winners) == 1 else None

def overlap(a, b):
    return max(0, min(a[2],b[2])-max(a[0],b[0])) * max(0,min(a[3],b[3])-max(a[1],b[1]))

def block_for(box, blocks):
    area = (box[2]-box[0])*(box[3]-box[1])
    scores = [(overlap(box,b['box'])/area,b) for b in blocks]
    best = max((v for v,b in scores), default=0)
    winners = [b for v,b in scores if abs(v-best) < 1e-10]
    return winners[0] if best > .5 and len(winners) == 1 else None

def same_line(a,b):
    # Pairwise 50% overlap of BOTH heights avoids transitive merging through tall cells.
    ov = min(a[3],b[3])-max(a[1],b[1])
    return ov > 0 and 2*ov >= max(a[3]-a[1],b[3]-b[1])

def stats(target, neighbours, prefix, dataset):
    known = [n['size'] for n in neighbours if n['size'] is not None]
    med = float(np.median(known)) if known else None
    diff = abs(target['size']-med) if target['size'] is not None and med is not None else None
    common = mode([n['font'] for n in neighbours])
    return {prefix+'_n':len(neighbours), prefix+'_neighbour_ids':json.dumps([n['source_id'] for n in neighbours],separators=(',',':')), prefix+'_size_known':len(known),
            prefix+'_size_unknown':len(neighbours)-len(known), prefix+'_median_size':med,
            prefix+'_abs_diff':diff,
            prefix+'_same_size':int(diff <= (.5 if dataset=='DocLayNet' else .1*med)) if diff is not None else None,
            prefix+'_font_known':sum(n['font'] is not None for n in neighbours),
            prefix+'_font_unknown':sum(n['font'] is None for n in neighbours),
            prefix+'_modal_font':common,
            prefix+'_same_font':int(target['font']==common) if target['font'] is not None and common is not None else None}

def page_stats(dataset, page, category, words, body):
    row = dict(dataset=dataset,page_id=page,doc_category=category,n_text_tokens=len(words),n_body_tokens=len(body))
    for key in ['size','font']:
        known = [w[key] for w in body if w[key] is not None]
        c = Counter(known)
        row[key+'_known'] = len(known); row[key+'_unknown'] = len(body)-len(known)
        row['dominant_'+key] = mode(known)
        row['dominant_'+key+'_ties'] = json.dumps(sorted(k for k,v in c.items() if v==max(c.values()))) if c else '[]'
        # Share remains defined when modes tie; identity is unknown.
        row['dominant_'+key+'_share'] = max(c.values())/len(body) if c and body else None
    return row

def make_result(saved, target, words, neighbours, page):
    row = {k:saved[k] for k in ['dataset','page_id','token_id','token','likely_name']}
    row.update(doc_category=page['doc_category'],box=saved['box'],source_box=','.join(map(str,target['box'])),surface=target['text'],
               source_id=target['source_id'],block_id=target['block'],token_size=target['size'],token_font=target['font'])
    for prefix, ns in neighbours.items(): row.update(stats(target, ns, prefix, saved['dataset']))
    row.update(page_dominant_size_share=page['dominant_size_share'],page_dominant_font_share=page['dominant_font_share'])
    return row

def doc_page(page, saved, blocks):
    payload = json.loads((base.JSON_DIR/(page['page_id']+'.json')).read_text())
    words=[]; sources={}
    for ci, cell in enumerate(payload.get('cells', [])):
        box = base.pixel_box(cell.get('bbox') or [])
        if box is None: continue
        f = cell.get('font') or {}; block = block_for(box, blocks)
        source=[]
        for wi, text in enumerate(pieces(cell.get('text',''))):
            w = dict(text=text, box=box, size=size(f.get('size')),font=font(f.get('name')),
                     block=block['id'] if block else None,category=block['category'] if block else None,
                     source_id=f'cell:{ci}/word:{wi}',cell=ci)
            words.append(w); source.append(w)
        sources[ci]=(cell,box,source)
    body=[w for w in words if w['category']=='Text']
    pr=page_stats('DocLayNet',page['page_id'],page['doc_category'],words,body)
    pr['unassigned_layout_tokens']=sum(w['block'] is None for w in words)
    rows=[]; consumed=set()
    for saved_row in saved:
        x0,y0,x1,y1=map(int,saved_row['box'].split(','))
        target_box=(x0+base.E.PAD,y0+base.E.PAD,x1-base.E.PAD,y1-base.E.PAD)
        matches=[]
        for ci,(cell,box,source) in sources.items():
            # This identifies a persisted v2 target; no surname dictionary/filter is run.
            parts=base.alpha_tokens(cell.get('text',''))
            if box!=target_box or len(parts)!=1 or parts[0].casefold()!=saved_row['token'].casefold(): continue
            matches += [w for w in source if base.alpha_tokens(w['text'])==parts and w['source_id'] not in consumed]
        assert matches, ('unmatched persisted token',saved_row)
        # Identical duplicate source cells are consumed in source order, as in v2.
        target=matches[0]; consumed.add(target['source_id'])
        others=[w for w in words if w is not target]
        line=[w for w in others if same_line(target['box'],w['box'])]
        block=[w for w in others if target['block'] is not None and w['block']==target['block']]
        cell=[w for w in others if w['cell']==target['cell']]
        rows.append(make_result(saved_row,target,words,dict(line=line,block=block,cell=cell),pr))
    return rows,pr

def fun_page(path, saved, add_one):
    payload=json.loads(path.read_text()); words=[]; links=defaultdict(set)
    for field in payload['form']:
        for a,b in field.get('linking',[]): links[a].add(b); links[b].add(a)
        for wi,word in enumerate(field.get('words',[])):
            x0,y0,x1,y1=map(int,word['box']); box=(x0,y0,x1+add_one,y1+add_one)
            if box[2]<=x0 or box[3]<=y0 or not word.get('text','').strip(): continue
            words.append(dict(text=word['text'],box=box,size=box[3]-box[1],font=None,
                              block=field['id'],label=field.get('label'),source_id=f"entity:{field['id']}/word:{wi}"))
    pr=page_stats('FUNSD',path.stem,'not available',words,words)
    pr['unassigned_layout_tokens']=0
    rows=[]; consumed=set()
    for s in saved:
        x0,y0,x1,y1=map(int,s['box'].split(','))
        box=(x0+base.E.PAD,y0+base.E.PAD,x1-base.E.PAD,y1-base.E.PAD)
        matches=[w for w in words if w['box']==box and w['label']=='answer' and
                 [p.casefold() for p in base.alpha_tokens(w['text'])]==[s['token'].casefold()] and w['source_id'] not in consumed]
        assert matches, ('unmatched persisted FUNSD token',s)
        t=matches[0]; consumed.add(t['source_id'])
        other=[w for w in words if w is not t]
        ns=dict(line=[w for w in other if same_line(t['box'],w['box'])],
                block=[w for w in other if w['block'] in ({t['block']}|links[t['block']])],
                entity=[w for w in other if w['block']==t['block']],
                linked=[w for w in other if w['block'] in links[t['block']]])
        rows.append(make_result(s,t,words,ns,pr))
    return rows,pr

def interval(rows, key):
    # Token-weighted statistic, page-cluster bootstrap; unknowns excluded per metric.
    groups=defaultdict(lambda:[0.,0.])
    for r in rows:
        if r.get(key) is not None:
            groups[r['page_id']][0]+=float(r[key]); groups[r['page_id']][1]+=1
    if not groups: return (None,None,None,0,len(rows))
    a=np.array(list(groups.values())); n=int(a[:,1].sum())
    rng=np.random.default_rng(0); draws=[]
    for start in range(0,10000,100):
        ix=rng.integers(0,len(a),size=(min(100,10000-start),len(a)))
        totals=a[ix].sum(axis=1); draws.extend(totals[:,0]/totals[:,1])
    lo,hi=np.quantile(draws,[.025,.975])
    return float(a[:,0].sum()/n),float(lo),float(hi),n,len(rows)-n

def summaries(rows,pages):
    result=[]
    for dataset in ['DocLayNet','FUNSD']:
        cats=['ALL']+sorted({r['doc_category'] for r in rows if r['dataset']==dataset}) if dataset=='DocLayNet' else ['ALL']
        for cat in cats:
            for likely in [False,True]:
                chosen=[r for r in rows if r['dataset']==dataset and (cat=='ALL' or r['doc_category']==cat) and (not likely or int(r['likely_name']))]
                ids={r['page_id'] for r in chosen}; ps=[p for p in pages if p['dataset']==dataset and p['page_id'] in ids]
                summary=dict(dataset=dataset,doc_category=cat,subset='likely names' if likely else 'all',n=len(chosen),n_pages=len(ps),
                             token_size_usable=sum(r['token_size'] is not None for r in chosen),token_size_unknown=sum(r['token_size'] is None for r in chosen),
                             token_font_usable=sum(r['token_font'] is not None for r in chosen),token_font_unknown=sum(r['token_font'] is None for r in chosen))
                for metric in ['line_same_size','block_same_size','line_same_font','block_same_font']:
                    point,lo,hi,usable,unknown=interval(chosen,metric)
                    summary.update({metric:point,metric+'_lo':lo,metric+'_hi':hi,metric+'_usable':usable,metric+'_unknown':unknown})
                for key in ['size','font']:
                    values=[p['dominant_'+key+'_share'] for p in ps if p['dominant_'+key+'_share'] is not None]
                    summary['median_page_'+key+'_share']=float(np.median(values)) if values else None
                    summary['page_'+key+'_usable']=len(values); summary['page_'+key+'_unknown']=len(ps)-len(values)
                result.append(summary)
    return result

def pct(v): return 'unknown' if v is None else f'{100*v:.2f}'
def table(rows):
    lines=['| Dataset/category | Set | n | Size known/unknown | Line size % [95% CI]; usable/unknown | Block size % [95% CI]; usable/unknown | Line font %; usable/unknown | Block font %; usable/unknown | Page size/font share % |',
           '|---|---|---:|---:|---|---|---|---|---|']
    for r in rows:
        cells=[r['dataset']+('/'+r['doc_category'] if r['doc_category']!='ALL' else ''),r['subset'],str(r['n']),f"{r['token_size_usable']}/{r['token_size_unknown']}"]
        for key in ['line_same_size','block_same_size','line_same_font','block_same_font']:
            v=pct(r[key])
            if key.endswith('size') and r[key] is not None: v+=f" [{pct(r[key+'_lo'])}, {pct(r[key+'_hi'])}]"
            v+=f"; {r[key+'_usable']}/{r[key+'_unknown']}"
            cells.append(v)
        cells.append(pct(r['median_page_size_share'])+'/'+pct(r['median_page_font_share']))
        lines.append('| '+' | '.join(cells)+' |')
    return '\n'.join(lines)

def main():
    before=protected()
    targets=[r for r in read(HERE/'results/v2/per_token.csv') if r['policy']=='exact']
    assert len({r['token_id'] for r in targets})==6071
    assert Counter(r['dataset'] for r in targets)=={'DocLayNet':5311,'FUNSD':760}
    assert Counter(r['dataset'] for r in targets if int(r['likely_name']))=={'DocLayNet':524,'FUNSD':209}
    by_page=defaultdict(list)
    for r in targets: by_page[r['page_id']].append(r)
    selected=read(HERE/'results/doclaynet_page_ids.csv'); assert len(selected)==2000
    blocks=defaultdict(list)
    for split in ['train','val','test']:
        ps={int(p['coco_id']):p['page_id'] for p in selected if p['source_split']==split}
        print('Reading COCO blocks',split,flush=True)
        for a in array_items(base.COCO_DIR/(split+'.json'),'annotations'):
            if a['image_id'] in ps:
                x,y,w,h=a['bbox']
                blocks[ps[a['image_id']]].append(dict(id=a['id'],category={1:'Caption',2:'Footnote',3:'Formula',4:'List-item',5:'Page-footer',6:'Page-header',7:'Picture',8:'Section-header',9:'Table',10:'Text',11:'Title'}[a['category_id']],box=(x,y,x+w,y+h)))
    rows=[]; pages=[]
    for i,p in enumerate(selected):
        rs,pr=doc_page(p,by_page[p['page_id']],blocks[p['page_id']]); rows+=rs; pages.append(pr)
        if (i+1)%500==0: print('DocLayNet pages',i+1,flush=True)
    config=json.loads((HERE/'results/v2/run_config.json').read_text())
    paths=sorted((base.funsd_split_dir('testing_data')/'annotations').glob('*.json')); assert len(paths)==50
    for path in paths:
        rs,pr=fun_page(path,by_page[path.stem],int(config['funsd_scored']['add_one'])); rows+=rs; pages.append(pr)
    assert {r['token_id'] for r in rows}=={r['token_id'] for r in targets}
    # Union fieldnames because DocLayNet and FUNSD have additional different context scopes.
    keys=list(dict.fromkeys(k for r in rows for k in r))
    rows=[{k:r.get(k) for k in keys} for r in rows]
    write('per_token.csv',rows); write('per_page.csv',pages)
    summary=summaries(rows,pages); write('summary.csv',summary)
    # Diverse failures: at most one example per page, prioritise likely names, both datasets.
    examples=[]
    for dataset,count in [('DocLayNet',6),('FUNSD',4)]:
        candidates=sorted([r for r in rows if r['dataset']==dataset and any(r[k]==0 for k in ['line_same_size','block_same_size','line_same_font','block_same_font'])],key=lambda r:(-int(r['likely_name']),r['page_id'],r['token_id']))
        seen=set()
        for r in candidates:
            if r['page_id'] in seen: continue
            seen.add(r['page_id']); examples.append(r)
            if len(seen)==count: break
    write('examples.csv',examples)
    ex=['| Dataset | Token (likely) | Page id | Box | Token size; font | Line median; mode | Block median; mode |','|---|---|---|---|---|---|---|']
    for r in examples:
        ex.append('| '+' | '.join(map(str,[r['dataset'],f"{r['surface']} ({r['likely_name']})",r['page_id'],r['box'],f"{r['token_size']}; {r['token_font']}",f"{r['line_median_size']}; {r['line_modal_font']}",f"{r['block_median_size']}; {r['block_modal_font']}"]))+' |')
    text='''# Font consistency on the v2 targets

The saved v2 exact-policy rows are the target list: **5,311 DocLayNet tokens (524 likely names), 760 FUNSD tokens (209 likely names)**. No target or likely-name filter is rerun. All 2,000 saved DocLayNet pages and all 50 FUNSD test forms are read. Percentages below exclude unknown comparisons; each cell gives its own usable/unknown denominator. Missing target metadata is additionally counted in the size column and summary.csv (including font counts).

DocLayNet sizes are the stored embedded point sizes, with size 1 (and invalid/nonpositive values) unknown; no box-height fallback. Font equality compares exact stored names, including subset prefixes and styles. A tied neighbour font mode has unknown identity. A token matches size when its absolute distance from the median of known neighbour sizes is ≤0.5 pt. FUNSD uses the v2 box convention and word-box heights in pixels, matching within 10% of the neighbour median; all font names are unknown.

Neighbours exclude the target. Line membership uses pairwise vertical overlap ≥50% of **both** boxes' heights, across the page, without transitive merging. This is an operational geometric line definition: separate columns at the same height can share a line, and no baseline metadata exists. DocLayNet whitespace tokens inherit their extracted cell's font and box; no positions are invented inside a cell. Layout-block membership uses the unique COCO annotation with greatest overlap covering >50% of the extracted cell; ambiguous/unassigned blocks are unknown. Block neighbours are other text tokens in that layout block (including tables); same-extraction-cell neighbours are also saved. FUNSD block neighbours are the union of the same entity and directly linked fields (undirected links, deduplicated); separate entity-only and linked-only statistics are saved too. Missing neighbour sizes are excluded from medians and counted; a comparison with no known neighbours is unknown.

Page shares use all whitespace tokens in COCO **Text** blocks as DocLayNet body text, and all annotated words for FUNSD (which has no body-text class). The denominator includes unknown metadata, so these are observed shares, not estimates of missing values; a page with no usable size/font is unknown. Modal-share ties have a known share but unknown mode identity. The table gives the median over unique pages containing that row's target subset (not token-weighted); per_page.csv includes all 2,050 pages and their usable/unknown counts. Summary.csv gives page counts and unknown page-share counts for every group.

95% percentile CIs use **10,000 page-cluster bootstrap resamples, NumPy Generator(0)**, of the token-weighted match proportion, independently reset for each metric/group; only pages with a usable comparison enter that metric's bootstrap. Categories are DocLayNet's saved document categories. The size and font statistics are descriptive consistency measures, not attacker scores.

'''+table([r for r in summary if r['doc_category']=='ALL'])+'\n\n## DocLayNet document categories\n\n'+table([r for r in summary if r['doc_category']!='ALL'])+'\n\n## Ten examples to inspect\n\nNone means unknown. Full source-cell/entity ids, differences, neighbour counts and comparison flags are in examples.csv; these examples were selected deterministically, preferring likely names, at most one per page.\n\n'+'\n'.join(ex)+'\n\n## Optional font-matched attacker\n\nNot yet run.\n'
    (HERE/'FONT_CONSISTENCY.md').write_text(text)
    after=protected(); assert before==after, 'Protected inputs changed'
    manifest=dict(target_source='results/v2/per_token.csv; policy=exact',target_source_sha256=digest(HERE/'results/v2/per_token.csv'),
                  pages=2000,forms=50,n=6071,bootstrap_seed=0,bootstrap_draws=10000,bootstrap_unit='page',
                  protected_inputs_unchanged=True,protected_sha256=before,script_sha256=digest(Path(__file__)))
    (OUT/'run_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(table(summary),flush=True)

if __name__=='__main__': main()
