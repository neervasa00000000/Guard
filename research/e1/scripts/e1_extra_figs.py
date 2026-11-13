#!/usr/bin/env python3
"""A4 (context LM) summary + FOIA real-geometry figure."""
import os,sys,json
import numpy as np,pandas as pd
import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
sys.path.insert(0,os.path.dirname(__file__));import e1lib as E
C=os.path.join(E.ROOT,'csv');FIG=os.path.join(E.RUN_ROOT,'figures');os.makedirs(FIG,exist_ok=True);GL={1:'exact',8:'8',16:'16',32:'32',64:'64'}
def save(fig,name):
    fig.savefig(os.path.join(FIG,name+'.png'),dpi=300,bbox_inches='tight');fig.savefig(os.path.join(FIG,name+'.svg'),bbox_inches='tight');plt.close(fig)
# ---- FOIA
F=pd.read_csv(os.path.join(C,'foia_boxes.csv'));S=pd.read_csv(os.path.join(C,'foia_geometry_summary.csv'))
fig,ax=plt.subplots(1,3,figsize=(13,3.6))
ax[0].hist(F.w.clip(upper=1500),bins=100,color='C0');ax[0].set_xlabel('box width (px @ ~300 DPI, clipped at 1500)');ax[0].set_ylabel('boxes');ax[0].set_title(f'IJDAR FOIA: {len(F):,} real redactions')
ax[1].hist(F.h.clip(upper=200),bins=100,color='C1');ax[1].set_xlabel('box height (px, clipped at 200)')
for sub,c in (('all','C0'),('single_line_h25to90','C1')):
    q=S[S.subset==sub].sort_values('grid_px')
    ax[2].plot(range(5),q.over_mean,'-o',color=c,label=f'{sub}: mean over-redaction')
    a2=ax[2].twinx() if sub=='all' else a2
    a2.plot(range(5),q.H_width_bits,'--s',color=c,label=f'{sub}: H(snapped width) bits')
ax[2].set_xticks(range(5));ax[2].set_xticklabels([GL[g] for g in (1,8,16,32,64)]);ax[2].set_xlabel('grid (px) at native resolution');ax[2].set_ylabel('over-redaction (solid)');a2.set_ylabel('entropy of snapped widths, bits (dashed)')
ax[2].legend(fontsize=6,loc='center left');a2.legend(fontsize=6,loc='center right')
save(fig,'fig_foia_geometry')
# ---- A4
p=os.path.join(E.ROOT,'cases','followup','e1_a4_cases.csv.gz')
if os.path.exists(p):
    A=pd.read_csv(p);H0=10.10
    D=E.get_dict('words');H0=float(-(D['p']*np.log2(D['p'])).sum())
    rows=[]
    for g,q in A.groupby('grid_px'):
        n=len(q)
        def acc(col,k):return float((q[col]<=k).mean())
        r=dict(grid_px=g,n=n,median_feasible=float(q.n_feasible.median()),
            freq_top1=float(q.hit1_freq.mean()),freq_top10=float(q.hit10_freq.mean()),
            lm_left_top1=acc('rank_lm_left',1),lm_left_top10=acc('rank_lm_left',10),
            lm_full_top1=acc('rank_lm_full',1),lm_full_top10=acc('rank_lm_full',10),
            freq_bits_leaked=H0-float(q.resid_bits_freq.mean()),lm_resid_bits=float(q.resid_bits_lm.mean()))
        for k in ('freq_top1','freq_top10','lm_left_top1','lm_left_top10','lm_full_top1','lm_full_top10'):
            lo,hi=E.wilson(r[k]*n,n);r[k+'_lo']=lo;r[k+'_hi']=hi
        rows.append(r)
    T=pd.DataFrame(rows);nb=A[(A.grid_px==1)&A.rank_lm_nobox.notna()]
    base=dict(n_items=int(A.item.nunique()),nobox_lm_n=len(nb),nobox_lm_top1=float((nb.rank_lm_nobox<=1).mean()) if len(nb) else None,nobox_lm_top10=float((nb.rank_lm_nobox<=10).mean()) if len(nb) else None,
              nobox_freq_top10_expected='see baselines_nobox.csv (words, prior-sampled targets) - A4 targets are context words, not prior-sampled')
    # frequency no-box baseline on the A4 targets themselves
    pr=D['p'];order=np.argsort(-pr);rankmap=np.empty(len(pr),int);rankmap[order]=np.arange(1,len(pr)+1)
    widx={w:i for i,w in enumerate(D['strings'])};q1=A[A.grid_px==1]
    base['nobox_freq_top10_on_A4_targets']=float(np.mean([rankmap[widx[w]]<=10 for w in q1.word]))
    base['nobox_freq_top1_on_A4_targets']=float(np.mean([rankmap[widx[w]]<=1 for w in q1.word]))
    if len(nb):
        lo,hi=E.wilson((nb.rank_lm_nobox<=10).sum(),len(nb));base['nobox_lm_top10_ci']=[lo,hi]
    T.to_csv(os.path.join(E.RUN_ROOT,'figures','e1_a4_summary.csv'),index=False);json.dump(base,open(os.path.join(E.RUN_ROOT,'figures','e1_a4_baselines.json'),'w'),indent=1)
    print(T.to_string());print(base)
    fig,ax=plt.subplots(figsize=(6,4));x=range(len(T))
    for col,lab,c in (('freq_top10','A1 frequency prior','C0'),('lm_left_top10','A4 LM left context','C1'),('lm_full_top10','A4 LM + right-context rerank','C3')):
        ax.errorbar(x,T[col]*100,yerr=[(T[col]-T[col+'_lo'])*100,(T[col+'_hi']-T[col])*100],marker='o',capsize=2,label=lab,color=c)
    if base['nobox_lm_top10'] is not None:ax.axhline(base['nobox_lm_top10']*100,ls=':',color='C1',label=f"LM, no box (n={base['nobox_lm_n']})")
    ax.axhline(base['nobox_freq_top10_on_A4_targets']*100,ls=':',color='C0',label='frequency, no box')
    ax.set_xticks(list(x));ax.set_xticklabels([GL[g] for g in T.grid_px]);ax.set_xlabel('grid (px)');ax.set_ylabel('top-10 accuracy (%)');ax.set_ylim(0,100)
    ax.set_title(f'A4 context attacker, n={base["n_items"]} redacted words in public-domain sentences\n(DejaVu Sans 16 px, known origin; Qwen2.5-0.5B on CPU)',fontsize=9);ax.legend(fontsize=7)
    save(fig,'fig_e1_a4_context')
