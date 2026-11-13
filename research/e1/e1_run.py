#!/usr/bin/env python3
"""E1 main sweep. One work unit = (dictionary, font, size). Within a unit the SAME targets and pen positions are
used for every condition/grid/attacker/defence (paired design).
Cells: conditions {clean,jpeg75,scan} x grids {1,8,16,32,64} x attackers {A1,A2}
       + defences (clean): D1 jitter 0..16px/side at grid 1 and 16; D2 width-bucket 128px + full line height at grid 1 and 16
       + A3 cross-copy (clean, unknown origin, k=1,2,3,5 copies with random 0..63px relative shifts) for grids 8..64
         (A3 only for surnames/words x DejaVuSans/LiberationSerif x 16px, to bound compute).
Tolerance for degraded / kerning cases: per-edge [0.5,99.5] percentile of (observed - model) edge error on a separate
calibration sample of 400 prior-weighted strings with fresh pen positions."""
import os,sys,json,time,gzip,csv,math
import numpy as np
from multiprocessing import Pool
sys.path.insert(0,os.path.dirname(__file__));import e1lib as E
N=int(os.environ.get('E1_N',2000));NCAL=400;SEED=20261029
OUT=os.path.join(E.RUN_ROOT,'csv');CASES=os.path.join(OUT,'cases')
A3_UNITS={(d,f,16) for d in('surnames','words') for f in('DejaVuSans','LiberationSerif')}
def unit(args):
    os.makedirs(CASES,exist_ok=True)
    dn,fn,sz=args;t0=time.time()
    tag=f'{dn}_{fn}_{sz}';outp=os.path.join(CASES,tag+'.csv.gz')
    if os.path.exists(outp+'.done'):
        saved = json.load(open(outp+'.done'))
        if any(row['n'] != N for row in saved):
            raise ValueError(f'{tag} has a different target count. Set a fresh E1_OUTPUT.')
        return saved
    rng=np.random.default_rng([SEED,list(E.DICTS).index(dn),list(E.FONTS).index(fn),sz])
    D=E.get_dict(dn);G=E.geometry(dn,fn,sz);logp=np.log2(D['p'])
    idx,strs=E.sample_targets(D,N,rng)
    pens=np.stack([rng.integers(*E.PEN_X,N),rng.integers(*E.PEN_Y,N)],1)
    cidx,cstrs=E.sample_targets(D,NCAL,rng);cpens=np.stack([rng.integers(*E.PEN_X,NCAL),rng.integers(*E.PEN_Y,NCAL)],1)
    rows=[];summ=[]
    def evaluate(variant,cond,g,attacker,k,Gc,tol,J,obs_list,shifts_list,tbs,boxes_true_area):
        cell=E.Cell(Gc,tol,J);res=[]
        for i in range(N):
            F=cell.feasible(obs_list[i],shifts_list[i],g,attacker)
            r=E.metrics(D,F,idx[i],len(strs[i]),logp)
            X0,X1,Y0,Y1=obs_list[i][0];r['over']=(X1-X0)*(Y1-Y0)/boxes_true_area[i]
            res.append(r)
            rows.append((variant,cond,g,attacker,k,i,X0,X1,Y0,Y1,r['hit1'],r['hit10'],r['len_ok'],round(r['resid_bits'],4),round(r['log10_cands'],3),r['truth_in'],round(r['over'],4)))
        a={key:np.array([r[key] for r in res]) for key in res[0]}
        def prop(key):
            p=a[key].mean();lo,hi=E.wilson(a[key].sum(),N);return p,lo,hi
        t1=prop('hit1');t10=prop('hit10');ln=prop('len_ok');bl=E.boot_ci(a['resid_bits'],rng)
        summ.append(dict(dict=dn,font=fn,size_px=sz,variant=variant,condition=cond,grid_px=g,attacker=attacker,k_copies=k,n=N,
            top1=t1[0],top1_lo=t1[1],top1_hi=t1[2],top10=t10[0],top10_lo=t10[1],top10_hi=t10[2],len_acc=ln[0],len_lo=ln[1],len_hi=ln[2],
            mean_resid_bits=a['resid_bits'].mean(),resid_lo=bl[0],resid_hi=bl[1],prior_bits=H0,bits_leaked=H0-a['resid_bits'].mean(),bits_leaked_lo=H0-bl[1],bits_leaked_hi=H0-bl[0],
            median_log10_cands=float(np.median(a['log10_cands'])),truth_in_set=a['truth_in'].mean(),
            over_median=float(np.median(a['over'])),over_mean=float(a['over'].mean()),
            tol=json.dumps(tol),jitter=J))
    w=D['p']*D['m'];H0=float(-(w*logp).sum())
    # baseline (no box): feasible = everything
    Fall=np.ones(len(D['p']),bool);base=[E.metrics(D,Fall,idx[i],len(strs[i]),logp) for i in range(N)]
    b={key:np.mean([r[key] for r in base]) for key in base[0]}
    summ.append(dict(dict=dn,font=fn,size_px=sz,variant='baseline_nobox',condition='-',grid_px=0,attacker='none',k_copies=0,n=N,top1=b['hit1'],top10=b['hit10'],len_acc=b['len_ok'],mean_resid_bits=b['resid_bits'],prior_bits=H0,bits_leaked=0.0,median_log10_cands=b['log10_cands'],truth_in_set=1.0))
    for cond in ('clean','jpeg75','scan'):
        ink=[E.ink_box(fn,sz,s,cond,rng) for s in strs]
        cink=[E.ink_box(fn,sz,s,cond,rng) for s in cstrs]
        err=np.array([[c[j]-G[ci][j] for j in range(4)] for c,ci in zip(cink,cidx)])
        tol=tuple((int(np.floor(np.percentile(err[:,j],0.5))),int(np.ceil(np.percentile(err[:,j],99.5)))) for j in range(4))
        tbs=[E.tight_box(ink[i],pens[i,0],pens[i,1],0,rng) for i in range(N)]
        area=[(tb[2]-tb[0])*(tb[3]-tb[1]) for tb in tbs]
        for g in E.GRIDS:
            obs=[[E.snapped(tb,g)] for tb in tbs]
            for att in ('A1','A2'):
                sh=[[(int(pens[i,0]) if att=='A1' else 0,int(pens[i,1]))] for i in range(N)]
                evaluate('main',cond,g,att,1,G,tol,0,obs,sh,tbs,area)
        if cond!='clean':continue
        # defences
        for vname,J,GB,inkb in (('D1_jitter16',16,G,ink),('D2_bucket128',0,E.bucket_transform(G,fn,sz),[E.bucket_box(x,fn,sz) for x in ink])):
            tbd=[E.tight_box(inkb[i],pens[i,0],pens[i,1],J,rng) for i in range(N)]
            for g in (1,16):
                obs=[[E.snapped(tb,g)] for tb in tbd]
                for att in ('A1','A2'):
                    sh=[[(int(pens[i,0]) if att=='A1' else 0,int(pens[i,1]))] for i in range(N)]
                    evaluate(vname,'clean',g,att,1,GB,tol,J,obs,sh,tbd,area)
        # A3 cross-copy
        if (dn,fn,sz) in A3_UNITS:
            K=5;offs=rng.integers(0,64,(N,K,2));offs[:,0,:]=0
            for g in (8,16,32,64):
                for k in (1,2,3,5):
                    obs=[];sh=[]
                    for i in range(N):
                        o=[];s_=[]
                        for j in range(k):
                            sx,sy=int(offs[i,j,0]),int(offs[i,j,1])
                            o.append(E.snapped(E.tight_box(ink[i],pens[i,0]+sx,pens[i,1]+sy,0,rng),g));s_.append((sx,int(pens[i,1])+sy))
                        obs.append(o);sh.append(s_)
                    evaluate('A3_crosscopy','clean',g,'A3',k,G,tol,0,obs,sh,tbs,area)
    with gzip.open(outp,'wt',newline='') as f:
        wr=csv.writer(f);wr.writerow(['variant','condition','grid_px','attacker','k','case','X0','X1','Y0','Y1','hit1','hit10','len_ok','resid_bits','log10_cands','truth_in','over_ratio'])
        wr.writerows(rows)
    with gzip.open(os.path.join(CASES,tag+'_targets.csv.gz'),'wt',newline='') as f:
        wr=csv.writer(f);wr.writerow(['case','entry','target','pen_x','baseline_y'])
        for i in range(N):wr.writerow([i,int(idx[i]),strs[i],int(pens[i,0]),int(pens[i,1])])
    json.dump(summ,open(outp+'.done','w'))
    print(tag,'done',round(time.time()-t0),'s',flush=True);return summ
if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lists', nargs='*', help='Dictionary names; omit for all five.')
    only = parser.parse_args().lists
    if set(only) - E.DICTS.keys():
        parser.error('Unknown list. Choose from ' + ', '.join(E.DICTS))
    E.check_render_inputs()
    units=[(d,f,s) for d in E.DICTS for f in E.FONTS for s in E.SIZES if not only or d in only]
    # warm caches (dictionary pickles) serially
    for d in {u[0] for u in units}:E.get_dict(d)
    units.sort(key=lambda u:{'emails':0,'surnames':1,'dates':2,'words':3,'digits':4}[u[0]])
    t0=time.time();allrows=[]
    with Pool(int(os.environ.get('E1_PROCS',6))) as p:
        for s in p.imap_unordered(unit,units):allrows+=s
    keys=[];[keys.append(k) for r in allrows for k in r if k not in keys]
    with open(os.path.join(OUT,'e1_summary.csv'),'w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(allrows)
    print('ALL DONE',round(time.time()-t0),'s')
