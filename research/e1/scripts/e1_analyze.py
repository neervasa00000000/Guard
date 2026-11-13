#!/usr/bin/env python3
"""Aggregate E1 case files -> pooled tables (markdown + CSV) and figures (PNG 300 dpi + SVG)."""
import os,sys,glob,gzip,json,math
import numpy as np,pandas as pd
import matplotlib;matplotlib.use('Agg');import matplotlib.ticker;import matplotlib.pyplot as plt
sys.path.insert(0,os.path.dirname(__file__));import e1lib as E
R=E.RUN_ROOT;C=os.path.join(R,'csv');FIG=os.path.join(R,'figures')
if not glob.glob(os.path.join(C,'cases','*.done')):
    raise SystemExit('No completed render cells in '+C+'. Run scripts/rerun_full.sh first.')
os.makedirs(FIG,exist_ok=True)
rng=np.random.default_rng(7)
H0={d:float(-(E.get_dict(d)['p']*E.get_dict(d)['m']*np.log2(E.get_dict(d)['p'])).sum()) for d in {os.path.basename(p).split('_')[0] for p in glob.glob(os.path.join(C,'cases','*.done'))}}
frames=[]
for p in sorted(glob.glob(os.path.join(C,'cases','*.csv.gz'))):
    if p.endswith('_targets.csv.gz'):continue
    tag=os.path.basename(p)[:-7];dn,fn,sz=tag.split('_');df=pd.read_csv(p);df['dict']=dn;df['font']=fn;df['size_px']=int(sz)
    df['bits_leaked']=H0[dn]-df['resid_bits'];frames.append(df)
A=pd.concat(frames,ignore_index=True)
summ=pd.concat([pd.DataFrame(json.load(open(p))) for p in glob.glob(os.path.join(C,'cases','*.done'))],ignore_index=True)
summ.to_csv(os.path.join(C,'e1_summary.csv'),index=False)
base=summ[summ.variant=='baseline_nobox']
def wil(x):
    n=len(x);k=x.sum();lo,hi=E.wilson(k,n);return lo,hi
def boot(x,B=1000):
    x=np.asarray(x);mu=[x[rng.integers(0,len(x),len(x))].mean() for _ in range(B)];return np.percentile(mu,2.5),np.percentile(mu,97.5)
def pooled(df,keys):
    out=[]
    for k,g in df.groupby(keys):
        k=k if isinstance(k,tuple) else (k,)
        t10=wil(g.hit10.values);t1=wil(g.hit1.values);ln=wil(g.len_ok.values);bl=boot(g.bits_leaked.values)
        out.append(dict(zip(keys,k),n=len(g),cells=g.groupby(['font','size_px']).ngroups,top1=g.hit1.mean(),top1_lo=t1[0],top1_hi=t1[1],top10=g.hit10.mean(),top10_lo=t10[0],top10_hi=t10[1],
            len_acc=g.len_ok.mean(),len_lo=ln[0],len_hi=ln[1],bits_leaked=g.bits_leaked.mean(),bits_lo=bl[0],bits_hi=bl[1],
            truth_in_set=g.truth_in.mean(),over_median=g.over_ratio.median(),over_mean=g.over_ratio.mean()))
    return pd.DataFrame(out)
main=A[(A.variant=='main')&(A.size_px.isin(E.SIZES))]
mainall=A[(A.variant=='main')]
P_clean=pooled(main[main.condition=='clean'],['dict','grid_px','attacker']);P_clean.to_csv(os.path.join(C,'pooled_clean_dict_grid_attacker.csv'),index=False)
P_cond=pooled(main,['dict','condition','grid_px','attacker']);P_cond.to_csv(os.path.join(C,'pooled_condition.csv'),index=False)
P_size=pooled(mainall[mainall.condition=='clean'],['dict','size_px','grid_px','attacker']);P_size.to_csv(os.path.join(C,'pooled_size.csv'),index=False)
P_font=pooled(main[main.condition=='clean'],['dict','font','grid_px','attacker']);P_font.to_csv(os.path.join(C,'pooled_font.csv'),index=False)
DEF=A[A.variant.isin(['D1_jitter16','D2_bucket128'])&(A.size_px.isin(E.SIZES))]
P_def=pooled(DEF,['dict','variant','grid_px','attacker']);P_def.to_csv(os.path.join(C,'pooled_defences.csv'),index=False)
X3=A[A.variant=='A3_crosscopy']
P_a3=pooled(X3,['dict','grid_px','k']) if len(X3) else pd.DataFrame();P_a3.to_csv(os.path.join(C,'pooled_crosscopy.csv'),index=False)
B=base.groupby('dict').agg(top1=('top1','mean'),top10=('top10','mean'),len_acc=('len_acc','mean'),prior_bits=('prior_bits','mean')).reset_index();B.to_csv(os.path.join(C,'baselines_nobox.csv'),index=False)
DICTS=[d for d in E.DICTS if d in set(A.dict)];GL={1:'exact',8:'8',16:'16',32:'32',64:'64'}
def save(fig,name):
    fig.savefig(os.path.join(FIG,name+'.png'),dpi=300,bbox_inches='tight');fig.savefig(os.path.join(FIG,name+'.svg'),bbox_inches='tight');plt.close(fig)
# Fig 1 leakage vs grid
fig,ax=plt.subplots(2,len(DICTS),figsize=(3.2*len(DICTS),6),sharex=True,squeeze=False)
ax=np.atleast_2d(ax)
for j,d in enumerate(DICTS):
    for i,(m,lab) in enumerate((('top10','top-10 accuracy'),('len_acc','length accuracy'))):
        a=ax[i,j]
        for att,c in (('A1','C0'),('A2','C1')):
            q=P_clean[(P_clean.dict==d)&(P_clean.attacker==att)].sort_values('grid_px');x=range(len(q))
            lo={'top10':'top10_lo','len_acc':'len_lo'}[m];hi={'top10':'top10_hi','len_acc':'len_hi'}[m]
            a.errorbar(x,q[m]*100,yerr=[(q[m]-q[lo])*100,(q[hi]-q[m])*100],marker='o',color=c,label=att,capsize=2)
        b=B[B.dict==d][m].values[0]*100;a.axhline(b,ls=':',color='gray',label='no box')
        a.set_xticks(range(5));a.set_xticklabels([GL[g] for g in (1,8,16,32,64)])
        if i==0:a.set_title(d)
        if j==0:a.set_ylabel(lab+' (%)')
        if i==1:a.set_xlabel('grid (px)')
ax[0,0].legend(fontsize=8);fig.suptitle('E1: leakage vs tile grid (clean renders, pooled over 6 fonts x 3 sizes; Wilson 95% CI)',fontsize=10);save(fig,'fig_e1_leakage_vs_grid')
# Fig 2 bits leaked
fig,ax=plt.subplots(1,2,figsize=(10,4),sharey=False)
for k,att in enumerate(('A1','A2')):
    for d in DICTS:
        q=P_clean[(P_clean.dict==d)&(P_clean.attacker==att)].sort_values('grid_px')
        ax[k].errorbar(range(len(q)),q.bits_leaked,yerr=[q.bits_leaked-q.bits_lo,q.bits_hi-q.bits_leaked],marker='o',label=f'{d} (prior {H0[d]:.1f} b)',capsize=2)
    ax[k].set_xticks(range(5));ax[k].set_xticklabels([GL[g] for g in (1,8,16,32,64)]);ax[k].set_title(f'{att}');ax[k].set_xlabel('grid (px)');ax[k].set_ylabel('bits leaked (prior H - mean residual H)')
ax[0].legend(fontsize=7);save(fig,'fig_e1_bits_leaked')
# Fig 3 trade-off (main)
fig,ax=plt.subplots(1,2,figsize=(11,4.4))
for k,att in enumerate(('A1','A2')):
    a=ax[k]
    for d,c in zip(DICTS,['C0','C1','C2','C3','C4']):
        q=P_clean[(P_clean.dict==d)&(P_clean.attacker==att)].sort_values('grid_px')
        a.plot(q.over_mean,q.bits_leaked,'-o',color=c,label=d)
        for _,r in q.iterrows():a.annotate(GL[r.grid_px],(r.over_mean,r.bits_leaked),fontsize=6,xytext=(3,3),textcoords='offset points')
        qd=P_def[(P_def.dict==d)&(P_def.attacker==att)]
        for _,r in qd.iterrows():
            mk={'D1_jitter16':'^','D2_bucket128':'s'}[r.variant];a.plot(r.over_mean,r.bits_leaked,mk,color=c,mfc='none',ms=7)
            a.annotate(('J' if r.variant.startswith('D1') else 'B')+('@'+GL[r.grid_px]),(r.over_mean,r.bits_leaked),fontsize=6,xytext=(3,-8),textcoords='offset points',color=c)
    a.set_xscale('log');a.set_xticks([1,1.5,2,3,5,8]);a.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter());a.minorticks_off();a.set_xlabel('mean over-redaction (blacked area / tight text box), same boxes');a.set_ylabel('bits leaked about the hidden string');a.set_title(f'{att}: privacy/utility trade-off')
    a.plot([],[],'k^',mfc='none',label='D1 jitter 0-16px');a.plot([],[],'ks',mfc='none',label='D2 width bucket 128px + line height')
ax[0].legend(fontsize=7);fig.suptitle('E1 joint trade-off: each point = one grid/defence, clean renders pooled over fonts and sizes',fontsize=9);save(fig,'fig_e1_tradeoff_alldicts')

# Fig 3b main trade-off: surnames & words, A1 vs A2, with defences
focus = [name for name in ('surnames','words') if name in DICTS]
if focus:
    fig,axes=plt.subplots(1,len(focus),figsize=(5.5*len(focus),4.4),squeeze=False)
    ax=axes[0]
    for a,d in zip(ax,focus):
        for att,c in (('A1','C0'),('A2','C1')):
            q=P_clean[(P_clean.dict==d)&(P_clean.attacker==att)].sort_values('grid_px')
            a.errorbar(q.over_mean,q.bits_leaked,yerr=[q.bits_leaked-q.bits_lo,q.bits_hi-q.bits_leaked],fmt='-o',color=c,label=f'{att} Guard grid snapping',capsize=2)
            for _,r in q.iterrows():a.annotate(GL[r.grid_px],(r.over_mean,r.bits_leaked),fontsize=7,xytext=(4,4),textcoords='offset points',color=c)
            qd=P_def[(P_def.dict==d)&(P_def.attacker==att)]
            for _,r in qd.iterrows():
                mk={'D1_jitter16':'^','D2_bucket128':'s'}[r.variant];a.plot(r.over_mean,r.bits_leaked,mk,color=c,mfc='none',ms=8)
                a.annotate(('jitter' if r.variant.startswith('D1') else 'bucket')+'@'+GL[r.grid_px],(r.over_mean,r.bits_leaked),fontsize=6,xytext=(4,-9),textcoords='offset points',color=c)
        a.set_xscale('log');a.set_xticks([1,1.5,2,3,5,8,12]);a.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter());a.minorticks_off()
        a.set_xlabel('mean over-redaction (blacked area / tight text box), same boxes');a.set_ylabel(f'bits leaked (prior {H0[d]:.1f} bits)');a.set_title(d)
        a.plot([],[],'k^',mfc='none',label='D1 random jitter 0-16 px/side');a.plot([],[],'ks',mfc='none',label='D2 width bucket 128 px + full line height')
    ax[0].legend(fontsize=7)
    fig.suptitle('Leakage vs over-redaction on the same boxes (clean, 6 fonts x 3 sizes, n=36,000 per point; 95% bootstrap CI)',fontsize=9);save(fig,'fig_e1_tradeoff')
# Fig 4 cross copy
if len(P_a3):
    fig,ax=plt.subplots(1,2,figsize=(10,4))
    for d,ls in zip(sorted(set(P_a3.dict)),['-','--']):
        for g,c in zip((8,16,32,64),['C0','C1','C2','C3']):
            q=P_a3[(P_a3.dict==d)&(P_a3.grid_px==g)].sort_values('k')
            ax[0].errorbar(q.k,q.top10*100,yerr=[(q.top10-q.top10_lo)*100,(q.top10_hi-q.top10)*100],ls=ls,color=c,marker='o',capsize=2,label=f'{d} g={g}')
            ax[1].plot(q.k,q.bits_leaked,ls=ls,color=c,marker='o')
    ax[0].set_xlabel('copies k (differently aligned)');ax[0].set_ylabel('top-10 (%)');ax[1].set_xlabel('copies k');ax[1].set_ylabel('bits leaked');ax[0].legend(fontsize=6)
    fig.suptitle('A3 cross-copy attacker (unknown origin; DejaVu Sans & Liberation Serif, 16 px)',fontsize=9);save(fig,'fig_e1_crosscopy')
# Fig 5 conditions & sizes (A2, surnames/words)
fig,ax=plt.subplots(1,2,figsize=(10,4))
for d,ls in (('surnames','-'),('words','--')):
    for cond,c in zip(('clean','jpeg75','scan'),['C0','C1','C2']):
        q=P_cond[(P_cond.dict==d)&(P_cond.condition==cond)&(P_cond.attacker=='A2')].sort_values('grid_px')
        ax[0].plot(range(len(q)),q.bits_leaked,ls=ls,color=c,marker='o',label=f'{d} {cond}')
    for sz,c in zip(sorted(set(P_size.size_px)),['C3','C4','C5','C6']):
        q=P_size[(P_size.dict==d)&(P_size.size_px==sz)&(P_size.attacker=='A2')].sort_values('grid_px')
        ax[1].plot(range(len(q)),q.bits_leaked,ls=ls,color=c,marker='o',label=f'{d} {sz}px')
for a in ax:a.set_xticks(range(5));a.set_xticklabels([GL[g] for g in (1,8,16,32,64)]);a.set_xlabel('grid (px)');a.set_ylabel('bits leaked (A2)');a.legend(fontsize=6)
ax[0].set_title('render condition');ax[1].set_title('font size (clean)');save(fig,'fig_e1_conditions_sizes')
# markdown tables
def md(df,cols,fmt):
    s='| '+' | '.join(cols)+' |\n|'+'---|'*len(cols)+'\n'
    for _,r in df.iterrows():s+='| '+' | '.join(fmt.get(c,'{}').format(r[c]) for c in cols)+' |\n'
    return s
T=P_clean.copy();T['grid']=T.grid_px.map(GL);T['top10 % [95% CI]']=T.apply(lambda r:f'{100*r.top10:.1f} [{100*r.top10_lo:.1f}, {100*r.top10_hi:.1f}]',axis=1)
T['bits leaked [95% CI]']=T.apply(lambda r:f'{r.bits_leaked:.2f} [{r.bits_lo:.2f}, {r.bits_hi:.2f}]',axis=1);T['len %']=T.len_acc.map(lambda v:f'{100*v:.1f}');T['top1 %']=T.top1.map(lambda v:f'{100*v:.1f}')
T['over-redaction median/mean']=T.apply(lambda r:f'{r.over_median:.2f} / {r.over_mean:.2f}',axis=1)
with open(os.path.join(C,'tables.md'),'w') as f:
    f.write('## Clean renders, pooled over 6 fonts x 3 sizes (n per row = 36,000 targets)\n\n')
    f.write(md(T,['dict','grid','attacker','top1 %','top10 % [95% CI]','len %','bits leaked [95% CI]','over-redaction median/mean'],{}))
    f.write('\n## No-box baselines (same targets)\n\n'+md(B,['dict','top1','top10','len_acc','prior_bits'],{'top1':'{:.4f}','top10':'{:.4f}','len_acc':'{:.3f}','prior_bits':'{:.2f}'}))
    Q=P_def.copy();Q['grid']=Q.grid_px.map(GL)
    f.write('\n## Defences (clean, pooled)\n\n'+md(Q,['dict','variant','grid','attacker','top10','len_acc','bits_leaked','over_median','over_mean'],{'top10':'{:.3f}','len_acc':'{:.3f}','bits_leaked':'{:.2f}','over_median':'{:.2f}','over_mean':'{:.2f}'}))
    Q=P_cond.copy();Q['grid']=Q.grid_px.map(GL)
    f.write('\n## Conditions (pooled over fonts and sizes)\n\n'+md(Q,['dict','condition','grid','attacker','top10','len_acc','bits_leaked','truth_in_set'],{'top10':'{:.3f}','len_acc':'{:.3f}','bits_leaked':'{:.2f}','truth_in_set':'{:.3f}'}))
    Q=P_size.copy();Q['grid']=Q.grid_px.map(GL)
    f.write('\n## By font size (clean)\n\n'+md(Q,['dict','size_px','grid','attacker','top10','len_acc','bits_leaked','over_median'],{'top10':'{:.3f}','len_acc':'{:.3f}','bits_leaked':'{:.2f}','over_median':'{:.2f}'}))
    Q=P_font.copy();Q['grid']=Q.grid_px.map(GL)
    f.write('\n## By font (clean)\n\n'+md(Q,['dict','font','grid','attacker','top10','len_acc','bits_leaked'],{'top10':'{:.3f}','len_acc':'{:.3f}','bits_leaked':'{:.2f}'}))
    if len(P_a3):f.write('\n## A3 cross-copy\n\n'+md(P_a3,['dict','grid_px','k','n','top10','len_acc','bits_leaked','bits_lo','bits_hi'],{'top10':'{:.3f}','len_acc':'{:.3f}','bits_leaked':'{:.2f}','bits_lo':'{:.2f}','bits_hi':'{:.2f}'}))
print(open(os.path.join(C,'tables.md')).read()[:3000])
