#!/usr/bin/env python3
"""Fresh, explicitly reconstructed LibreOffice mock-form end-to-end experiment."""
import argparse,csv,io,json,math,subprocess,time
from collections import defaultdict
from pathlib import Path
import numpy as np
from PIL import Image,ImageFilter
from v14_runtime import ROOT,E,P,renderer,digest,text_hash,read,write,mean_intervals,area_intervals,SEED,DRAWS
from run_email_digits import Scores
FONTS=['DejaVuSans','LiberationSerif'];SIZES=[16,24]
ATTACKERS=['pillow_mismatch','libreoffice_matched','pillow_lo_calibrated']
POLICIES=['nobox','exact','grid-16','grid-64','start128','field']

def scan(path,bounds,rng):
    """Fixed local-word scan model; explicitly different from lost full-page scan."""
    im=Image.open(path).convert('L');margin=24;l,t,r,b=bounds
    assert im.size==(r-l,b-t)
    canvas=Image.new('L',(im.width+2*margin,im.height+2*margin),255);canvas.paste(im,(margin,margin))
    ox,oy=margin-l,margin-t;angle=float(rng.uniform(-.5,.5))
    canvas=canvas.rotate(angle,resample=Image.Resampling.BICUBIC,center=(ox,oy),fillcolor=255)
    canvas=canvas.filter(ImageFilter.GaussianBlur(.8))
    a=np.asarray(canvas,dtype=np.float32)+rng.normal(0,10,(canvas.height,canvas.width)).astype(np.float32)
    canvas=Image.fromarray(np.clip(a,0,255).astype(np.uint8));buffer=io.BytesIO();canvas.save(buffer,'JPEG',quality=85)
    a=np.asarray(Image.open(io.BytesIO(buffer.getvalue())).convert('L'))<128;ys,xs=np.nonzero(a)
    assert len(xs)>0
    return [int(xs.min())-ox,int(ys.min())-oy,int(xs.max())+1-ox,int(ys.max())+1-oy],angle

def tolerance(errors):
    errors=np.asarray(errors)
    return tuple((int(np.floor(np.percentile(errors[:,j],.5))),int(np.ceil(np.percentile(errors[:,j],99.5)))) for j in range(4))

def prepare(work,pilot):
    dictionary=E.get_dict('surnames');archived=read(ROOT/'research/e1/data/forms/replayed_forms_obs.csv')
    rows=[r for r in archived if r['size']=='16' and r['cond']=='clean'];assert len(rows)==100
    forms=[]
    for r in rows:
        target=int(r['truth_idx']);assert dictionary['strings'][target]==r['truth']
        forms.append(dict(doc=int(r['doc']),font=r['font'],margin=int(r['margin']),truth=r['truth'],target=target))
    assert len({r['doc'] for r in forms})==100
    plan=dict(strings=dictionary['strings'][:128] if pilot else dictionary['strings'],forms=forms[:2] if pilot else forms,
              fonts={f:dict(filename=E.checked_font_path(f).name,sha256=digest(E.checked_font_path(f))) for f in FONTS},calibration={})
    for fi,font in enumerate(FONTS):
        for size in SIZES:
            rng=np.random.default_rng([SEED,901,fi,size]);n=16 if pilot else 400
            ids,strings=E.sample_targets(dictionary,n,rng)
            plan['calibration'][f'{font}_{size}']=dict(ids=ids.tolist(),strings=strings,row_phase_px=(rng.integers(0,4,math.ceil(n/4))/4).tolist())
    work.mkdir(parents=True,exist_ok=True);(work/'request.json').write_text(json.dumps(plan,separators=(',',':'))+'\n')
    return dictionary,plan

def score(work,dictionary,plan,versions,image):
    out=ROOT/'results/v1_4_archive/mock_forms_reconstruction';out.mkdir(parents=True,exist_ok=True)
    raw=[];observations=[];calibration=[];candidate_rows=[];frames=[];tol={};banks={};source_metadata=json.loads((work/'worker_config.json').read_text())
    for fi,font in enumerate(FONTS):
        for size in SIZES:
            key=f'{font}_{size}';bank=json.loads((work/'measured'/f'bank_{key}.json').read_text())['measurements']
            lo=np.array([r['bounds'] for r in bank]);pil=np.asarray(E.geometry('surnames',font,size));assert lo.shape==pil.shape==(50000,4)
            asc,desc=E.font(font,size).getmetrics();frame=P.prepare(lo,asc,desc)
            frames.append(dict(font=font,size_px=size,x_l=frame['x_l'],line_top=frame['line_top'],line_bottom=frame['line_bottom']))
            for i,name in enumerate(dictionary['strings']):
                candidate_rows.append(dict(font=font,size_px=size,index=i,target_sha256=text_hash(name),target_char_length=len(name),prior=float(dictionary['p'][i]),
                    **{'lo_'+k:int(lo[i,j]) for j,k in enumerate(['l','t','r','b'])},**{'pil_'+k:int(pil[i,j]) for j,k in enumerate(['l','t','r','b'])}))
            bounds={'libreoffice_matched':lo,'pillow_mismatch':pil,'pillow_lo_calibrated':pil}
            banks[(font,size)]=(bounds,{a:Scores(dictionary,g) for a,g in bounds.items()})
            cal=json.loads((work/'measured'/f'calibration_{key}.json').read_text())['measurements'];ids=plan['calibration'][key]['ids'];assert len(cal)==400
            for condition in ['clean','scan']:
                errors={a:[] for a in ATTACKERS}
                for i,(row,target) in enumerate(zip(cal,ids)):
                    measured=row['bounds'];angle=0.
                    rng=np.random.default_rng([SEED,902,fi,size,i])
                    if condition=='scan':measured,angle=scan(work/'glyphs'/f'calibration_{key}'/f'{i}.png',measured,rng)
                    pil_actual=E.ink_box(font,size,dictionary['strings'][target],condition,np.random.default_rng([SEED,903,fi,size,i]))
                    for a in ATTACKERS:
                        actual=pil_actual if a=='pillow_mismatch' else measured
                        error=np.asarray(actual)-bounds[a][target];errors[a].append(error)
                        calibration.append(dict(font=font,size_px=size,condition=condition,attacker=a,case=i,target_sha256=text_hash(dictionary['strings'][target]),
                            target_char_length=len(dictionary['strings'][target]),left_error=int(error[0]),top_error=int(error[1]),right_error=int(error[2]),bottom_error=int(error[3])))
                for a in ATTACKERS:tol[(font,size,condition,a)]=tolerance(errors[a])
    for size in SIZES:
        records=json.loads((work/'measured'/f'forms_{size}.json').read_text())['measurements'];assert len(records)==100
        for i,(record,form) in enumerate(zip(records,plan['forms'])):
            font=form['font'];fi=FONTS.index(font);target=form['target'];bounds,scorers=banks[(font,size)]
            native=bounds['libreoffice_matched'];asc,desc=E.font(font,size).getmetrics();frame=P.prepare(native,asc,desc)
            for condition in ['clean','scan']:
                actual=record['bounds'];angle=0.
                if condition=='scan':actual,angle=scan(work/'glyphs'/f'forms_{size}'/f'{i}.png',actual,np.random.default_rng([SEED,904,size,form['doc']]))
                x,y=record['pen_x'],record['baseline_y'];l,t,r,b=actual
                target_frame=P.prepare(np.asarray([actual]),asc,desc)
                for k in ['x_l','line_top','line_bottom']:target_frame[k]=frame[k]
                common=dict(doc=form['doc'],font=font,size_px=size,condition=condition,target_sha256=text_hash(form['truth']),target_char_length=len(form['truth']))
                observations.append(dict(common,pen_x=x,baseline_y=y,angle_degrees=angle,left=l,top=t,right=r,bottom=b,pdf_font=record['pdf_font'],
                    pdf_origin_x_px=record['pdf_origin_px'][0],pdf_origin_y_px=record['pdf_origin_px'][1],page_width=record['page_width'],page_height=record['page_height']))
                for policy in POLICIES:
                    grid=1
                    if policy=='nobox':box=None
                    elif policy=='exact':box=[x+l-1,y+t-1,x+r+1,y+b+1]
                    elif policy.startswith('grid-'):
                        grid=int(policy.split('-')[1]);box=[int(z[0])+off for z,off in zip(P.square_grid(target_frame,grid,x,y),[x,y,x,y])]
                    elif policy=='start128':box=[int(z[0])+off for z,off in zip(P.start_aligned_padding(target_frame,128),[x,y,x,y])]
                    else:box=[int(z[0])+off for z,off in zip(P.field_box(frame)[:4],[x,y,x,y])]
                    requested=(r-l+2)*(b-t+2);area='' if box is None else (box[2]-box[0])*(box[3]-box[1])/requested
                    for a in ATTACKERS:
                        scorer=scorers[a];tolerance_px=tol[(font,size,condition,a)]
                        if policy in ['nobox','field']:mask=np.ones(len(scorer.geometry),bool)
                        elif policy=='start128':
                            width=box[2]-box[0];dr0,dr1=tolerance_px[2]
                            span=scorer.geometry[:,2]+1-frame['x_l']
                            mask=(P.ceil_multiple(span+dr0,128)<=width)&(P.ceil_multiple(span+dr1,128)>=width)
                        else:
                            cell=E.Cell(scorer.geometry,tolerance_px,0)
                            mask=cell.feasible([(box[0],box[2],box[1],box[3])],[(x,y)],grid,'A1')
                        bits,h1,h10,truth=scorer.score(mask,target)
                        raw.append(dict(common,attacker=a,policy=policy,bits=bits,top1=h1,top10=h10,truth_in=truth,n_candidates=int(np.sum(dictionary['m'][np.isin(scorer.group,np.flatnonzero(mask))])),
                            area_ratio=area,box='' if box is None else json.dumps(box,separators=(',',':')),target_coverage='' if box is None else box[0]<=x+l-1 and box[1]<=y+t-1 and box[2]>=x+r+1 and box[3]>=y+b+1))
    write(out/'raw.csv.gz',raw);write(out/'observations.csv.gz',observations);write(out/'calibration.csv.gz',calibration);write(out/'candidate_geometry.csv.gz',candidate_rows)
    original={(int(r['size']),r['cond'],r['attacker'],r['variant']):float(r['archived'])/int(r['n']) for r in read(ROOT/'research/e1/data/forms/libreoffice_hit_check.csv')}
    groups=defaultdict(list)
    for r in raw:groups[(r['size_px'],r['condition'],r['attacker'],r['policy'])].append(r)
    summary=[]
    for (size,condition,a,policy),rows in sorted(groups.items()):
        assert len(rows)==100
        keys=['bits','top1','top10','truth_in'];values=[[r[k] for k in keys] for r in rows];point,lo,hi=mean_intervals(values)
        s=dict(size_px=size,condition=condition,attacker=a,policy=policy,n=100)
        for j,k in enumerate(keys):s.update({k:float(point[j]),k+'_lo':float(lo[j]),k+'_hi':float(hi[j])})
        if policy!='nobox':s.update(area_intervals([r['area_ratio'] for r in rows]),target_coverage=float(np.mean([r['target_coverage'] for r in rows])))
        else:s.update({k:'' for k in ['area_median','area_median_lo','area_median_hi','area_p90','area_p90_lo','area_p90_hi','target_coverage']})
        old_a={'pillow_mismatch':'a_paper_renderer','libreoffice_matched':'b_lo_table','pillow_lo_calibrated':'b_lo_calibrated'}[a]
        old_policy={'exact':'exact','grid-16':'16px','grid-64':'64px'}.get(policy)
        old=original.get((size,condition,old_a,old_policy));s['historical_top10']=old if old is not None else ''
        s['difference_from_historical_pp']=100*(s['top10']-old) if old is not None else ''
        summary.append(s)
    write(out/'summary.csv',summary)
    config=dict(status='complete_new_reconstruction',original_generator_recovered=False,historical_replication=False,
        command='research/realworld_e1_eval/.venv/bin/python -B scripts/run_lo_reconstruction.py',versions=versions,container=source_metadata,docker_image_id=image,
        network='disabled for container',fonts=plan['fonts'],seed=SEED,bootstrap_seed=SEED,bootstrap_resamples=DRAWS,bootstrap_unit='form: one target on each of the 100 forms in each size/condition cell',
        n_evaluation_forms=100,n_rendered_form_pages=200,n_evaluation_observations=400,n_candidate_geometries=200000,n_calibration_per_font_size=400,
        policies=POLICIES,attackers=ATTACKERS,
        reconstruction='Original 100 archived target IDs, font assignments and margins; newly specified synthetic FODT template. Sizes 16/24 px at 96 DPI. PDF generated by LibreOffice and rasterized by PyMuPDF; actual text origins and threshold-128 ink bounds measured. No archived observation geometry used for scoring.',
        scan='Local target bitmap reconstructed from actual PDF ink; rotate +-0.5 degrees about text origin, bicubic, Gaussian blur sigma .8, Gaussian noise SD10, JPEG85; explicit new local-word scan model, not the missing original full-page transform.',
        candidate_table='All 50000 names rendered in each of two fonts and two sizes. Actual raster bounds are measured, not font metrics or saved observations. Fontconfig sees only the two checked binaries.',
        calibration='Independent 400 prior-drawn strings per font-size; per-edge floor/ceil 0.5/99.5 percentiles. Matched uses fresh LibreOffice errors; mismatch uses its own Pillow errors; third arm calibrates Pillow geometry to fresh LibreOffice observations. Same tolerance frozen across policies.',
        padding='Public fixed native list anchor, full native line, C128; candidate right-edge tolerance propagated through ceil as original start_padding.py. Field covers full 50000-name bounded list.',
        historical_comparison='Same target IDs but different reconstructed template and scan model; differences are reported, not claimed replications.',
        policy_frames=frames,tolerance_px=[dict(font=f,size_px=s,condition=c,attacker=a,edges=v) for (f,s,c,a),v in tol.items()],
        calibration_targets={k:dict(target_sha256=[text_hash(s) for s in r['strings']],target_char_length=[len(s) for s in r['strings']],row_phase_px=r['row_phase_px']) for k,r in plan['calibration'].items()},
        source_sha256={p:digest(ROOT/p) for p in ['scripts/run_lo_reconstruction.py','scripts/lo_reconstruction_worker.py','research/e1/data/forms/replayed_forms_obs.csv','research/e1/data/forms/libreoffice_hit_check.csv']})
    (out/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    (out/'README.md').write_text('# Fresh LibreOffice reconstruction\n\nThis end-to-end experiment generates new LibreOffice documents, PDF pages, raster ink, full-list candidate measurements and attacks. It uses the same 100 archived synthetic surname targets and font assignments, sizes 16/24, and records one hashed row per target/policy/attacker. No saved target geometry is used to score. LibreOffice and all parameters are recorded in config.json. The container has no network access.\n\nThe original generator/template is still missing. The FODT template and local-word scan model are newly specified, so these results do not establish reproduction of the historical mock-form numbers. summary.csv reports differences wherever directly corresponding historical hit rates exist; no historical row is overwritten. Raw PDFs, glyph images, font binaries and text requests remain ignored under out/. Only derived geometry, hashes, counts, config and code are archived.\n\nRun the command in config.json with the existing LibreOffice container and checked study dependencies. Confidence intervals use 10000 form bootstrap draws, seed 20261121. No-box area/coverage is unknown (blank), rather than a fabricated zero.\n')
    print('Completed fresh reconstruction:',len(raw),'per-form rows;',len(summary),'summaries',flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pilot',action='store_true');parser.add_argument('--skip-render',action='store_true')
    parser.add_argument('--image',default='guard-e1-review4-forms',help='Local compatible LibreOffice 25.2.3.2 image; resolved image ID is archived')
    args=parser.parse_args()
    versions=renderer();work=ROOT/'out'/('v14-lo-reconstruction-pilot' if args.pilot else 'v14-lo-reconstruction')
    dictionary,plan=prepare(work,args.pilot)
    image=subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    if not args.skip_render:
        command=['docker','run','--rm','--network','none','--mount',f'type=bind,src={ROOT/"scripts"},dst=/scripts,readonly','--mount',f'type=bind,src={E.checked_font_path(FONTS[0]).parent},dst=/fonts,readonly',
                 '--mount',f'type=bind,src={work},dst=/work','--env','PYTHONDONTWRITEBYTECODE=1',image,'python','-B','/scripts/lo_reconstruction_worker.py','/work']
        subprocess.run(command,check=True)
    if args.pilot:print('Pilot renderer measurement passed; no performance results inferred.');return
    score(work,dictionary,plan,versions,image)
if __name__=='__main__':main()
