#!/usr/bin/env python3
"""Re-execute recovered five-font rerender protocol on its original 2000 names."""
import ast,functools,importlib.util,json,sys,time
from pathlib import Path
import numpy as np
from rerun_common import ROOT,E,P,renderer,read,write,digest,text_hash,mean_intervals,SEED,DRAWS
SOURCES=ROOT/'results/reruns/recovered_sources'
def load(name):
    spec=importlib.util.spec_from_file_location(name,SOURCES/(name+'.py'));module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
def main():
    out=ROOT/'results/reruns/rerender_class_changes';out.mkdir(parents=True,exist_ok=True)
    versions=renderer();geom=load('geometry');scoring=load('grouped_scores');dictionary=E.get_dict('surnames');start=time.monotonic();fresh={}
    for font in E.FONTS:
        face=E.font(font,24);g=np.array([face.getbbox(s,anchor='ls') for s in dictionary['strings']],dtype=np.int32)
        old=np.load(ROOT/f'out/retained-geom/geom_surnames_{font}_24.pkl',allow_pickle=True)
        assert np.array_equal(g,old),('Fresh bounds differ',font)
        fresh[font]=g
    source=SOURCES/'a3_start_run.py';tree=ast.parse(source.read_text())
    selected=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in ['indexes','targets','features_for','rerender']]
    namespace=dict(E=E,np=np,SEED=20261029,STUDY=20261120,N=2000,FONTS=('DejaVuSans','LiberationSerif'),
        lru_cache=functools.lru_cache,Geometry=geom.Geometry,Policy=geom.Policy,GroupedScores=scoring.GroupedScores,
        data=lambda d:dictionary,bounds=lambda d,f,s,model,renderer='pillow':fresh[f])
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(source),'exec'),namespace)
    ids,strings,_,_,_=namespace['targets']('surnames','DejaVuSans',24)
    original=read(ROOT/'research/e1/data/results_summary.csv');raw=[];summ=[]
    for width in [128,192]:
        rows=namespace['rerender']('surnames',24,'font','layout',width)
        a1=[r for r in rows if r[7]=='A1'];first={int(r[9]):r for r in a1 if r[8]==1};after={int(r[9]):r for r in a1 if r[8]==5}
        rng=np.random.default_rng([20261120,2,list(E.DICTS).index('surnames'),24,1])
        choices=np.array([rng.permutation(6)[:5] for _ in ids]);fonts=list(E.FONTS);features=[namespace['features_for']('surnames',f,24,'layout',width) for f in fonts]
        metric=[]
        for i,target in enumerate(ids):
            widths=[int(features[j][1][target]) for j in choices[i]];classes=[w//width for w in widths];changed=len(set(classes))>1
            assert changed==bool(after[i][-1])
            raw.append(dict(case=i,target_sha256=text_hash(strings[i]),target_char_length=len(strings[i]),C_px=width,
                old_class=classes[0],new_class=classes[-1],all_release_classes=json.dumps(classes,separators=(',',':')),
                release_fonts=json.dumps([fonts[j] for j in choices[i]],separators=(',',':')),any_class_change=changed,first_last_change=classes[0]!=classes[-1],
                top10_first=first[i][10],top10_after=after[i][10],bits_first=first[i][11],bits_after=after[i][11]))
            metric.append([first[i][10],after[i][10],first[i][11],after[i][11],after[i][11]-first[i][11],float(changed)])
        point,lo,hi=mean_intervals(metric);row=dict(C_px=width,n=2000,k_releases=5,n_class_changes=sum(r['any_class_change'] for r in raw if r['C_px']==width),
            n_first_last_changes=sum(r['first_last_change'] for r in raw if r['C_px']==width))
        for j,key in enumerate(['top10_first','top10_after','bits_first','bits_after','bits_gain','change_fraction']):row.update({key:float(point[j]),key+'_lo':float(lo[j]),key+'_hi':float(hi[j])})
        old=next(r for r in original if r['condition']=='font' and r['list']=='surnames' and r['font']=='mixed' and r['size']=='24' and r['model']=='layout' and int(r['class_px'])==width and r['attacker']=='A1' and r['k']=='5')
        row['archived_class_changes']=int(old['targets_change_class']);row['count_matches']=row['n_class_changes']==row['archived_class_changes']
        for key,col,factor in [('top10_first','top10_1',100),('top10_after','top10_k',100),('bits_first','bits_1',1),('bits_after','bits_k',1)]:
            row[key+'_difference']=row[key]*factor-float(old[col]);assert abs(row[key+'_difference'])<1e-9
        assert row['count_matches'];summ.append(row)
        print('Reproduced',width,'px:',row['n_class_changes'],'of 2000 class changes',flush=True)
    write(out/'raw.csv.gz',raw);write(out/'summary.csv',summ)
    config=dict(status='complete',command='research/realworld_e1_eval/.venv/bin/python -B scripts/run_archive_rerender.py',versions=versions,
        target_seed=20261029,release_seed=20261120,bootstrap_seed=SEED,bootstrap_resamples=DRAWS,
        recovered_source_commit='733d48a',source_sha256=digest(source),wrapper_sha256=digest(__file__),
        protocol='Original font scenario, layout boxes, same 2000 surname targets, five of six fonts per target chosen by seeded permutation; original rerender function body unchanged',
        class_change='Any difference among all five released classes; old_class/new_class are first/last, and the complete sequence is also archived',
        fresh_geometry='All six 24px full-list geometries freshly rendered and numerically identical to retained bounds',elapsed_seconds=time.monotonic()-start)
    (out/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    (out/'README.md').write_text('# Original 24px font-rerender check\n\nRecovered a3_start/run.py from commit 733d48a identifies the original target seed and five-release font scenario. Its rerender function executes unchanged using freshly rendered, receipt-consistent six-font geometry. The 128px and 192px counts reproduce 188 and 2 of 2000 targets, respectively; original top-10 and bits also match within 1e-9.\n\nThe historical count means any class change among five releases, not only first versus last. Each target has one row per width with first/last classes plus the complete five-class sequence and font order. No surname text or font binaries are archived. New target-bootstrap CIs use 10000 resamples, seed 20261121.\n')
if __name__=='__main__':main()
