"""Pinned study runtime, no-text writers and exact marginal target bootstraps."""
from __future__ import annotations
import csv,gzip,hashlib,io,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['E1_CENSUS']=str(ROOT/'data/census/Names_2010Census.csv')
os.environ['E1_FONT_DIR']=str(ROOT/'research/realworld_e1_eval/fonts')
os.environ['E1_OUTPUT']=str(ROOT/'out/v14-runtime-cache')
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'research/e1'))
import numpy as np
import e1lib as E
import policies as P
SEED=20261121
DRAWS=10000
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def text_hash(s):return hashlib.sha256(s.encode()).hexdigest()
def read(p):
    opener=gzip.open if str(p).endswith('.gz') else open
    with opener(p,'rt',newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    if str(p).endswith('.gz'):
        with p.open('wb') as raw,gzip.GzipFile(fileobj=raw,filename='',mtime=0,mode='wb') as z,io.TextIOWrapper(z,newline='') as f:
            w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    else:
        with p.open('w',newline='') as f:
            w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def renderer():
    import PIL
    from PIL import features
    E.check_render_inputs()
    assert digest(E.CENSUS)==E.FULL_CENSUS_SHA
    info=dict(python=sys.version,numpy=np.__version__,pillow=PIL.__version__,
        **{k:features.version(k) for k in ['raqm','harfbuzz','fribidi','freetype2']},
        fonts={name:digest(E.checked_font_path(name)) for name in E.FONTS},census_sha256=digest(E.CENSUS))
    for k,v in dict(raqm='0.10.5',harfbuzz='14.2.1',fribidi='1.0.16',freetype2='2.14.3').items():
        assert info[k]==v,('Pinned renderer mismatch',k,info[k],v)
    return info
def mean_intervals(values,seed=SEED):
    """Exact target bootstrap via multinomial counts of identical metric vectors."""
    a=np.asarray(values,dtype=float)
    if a.ndim==1:a=a[:,None]
    unique,count=np.unique(a,axis=0,return_counts=True);rng=np.random.default_rng(seed)
    draws=[]
    for start in range(0,DRAWS,100):
        weights=rng.multinomial(len(a),count/len(a),size=min(100,DRAWS-start))
        draws.append(weights@unique/len(a))
    b=np.concatenate(draws)
    return a.mean(axis=0),*np.quantile(b,[.025,.975],axis=0)
def quantile_draws(values,q,rng,n_draws=DRAWS):
    """Exact marginal bootstrap of NumPy's linear quantile, without full draws.

    Generate the two required adjacent uniform order statistics, map through
    the empirical inverse CDF, and interpolate. This is distributionally the
    same statistic as quantiling n IID resampled targets; no approximation.
    Marginal CIs are provided, not paired/joint quantile inferences.
    """
    a=np.sort(np.asarray(values,dtype=float));n=len(a)
    if n==1:return np.full(n_draws,a[0])
    position=q*(n-1);k=int(np.floor(position));fraction=position-k;j=k+1
    u=rng.beta(j,n+1-j,size=n_draws)
    x=a[np.minimum((n*u).astype(int),n-1)]
    if fraction==0:return x
    v=u+(1-u)*rng.beta(1,n-j,size=n_draws)
    y=a[np.minimum((n*v).astype(int),n-1)]
    return x+(y-x)*fraction
def area_intervals(values,seed=SEED):
    rng=np.random.default_rng(seed);out={}
    for name,q in [('area_median',.5),('area_p90',.9)]:
        b=quantile_draws(values,q,rng);lo,hi=np.quantile(b,[.025,.975])
        out.update({name:float(np.quantile(values,q)),name+'_lo':float(lo),name+'_hi':float(hi)})
    return out
