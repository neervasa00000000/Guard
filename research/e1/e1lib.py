#!/usr/bin/env python3
"""E1 full study: shared library (dictionaries, rendering, redaction-box model, attackers, metrics).

Geometry model (validated against Guard grd.redact, see e1_validate_guard.py):
  tight box   = layout box from Pillow getbbox (anchor 'ls', RAQM) + 1 px on each side,
                half-open [x0,x1) x [y0,y1)
  snapped box = (floor(x0/g)*g, ceil(x1/g)*g, floor(y0/g)*g, ceil(y1/g)*g); g=1 is an exact-pixel (non-Guard) tool.
Attackers rank geometrically feasible dictionary entries by prior (possibilistic attacker, ties broken at random
in expectation). Entropy = Shannon entropy of the prior restricted to the feasible set."""
import os,csv,math,json,hashlib,random,io,pickle,datetime
import numpy as np
from pathlib import Path
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOT = str(HERE)
RUN_ROOT = Path(os.environ.get('E1_OUTPUT', REPO / 'out' / 'e1-rerun')).resolve()
CACHE = RUN_ROOT / 'cache'
# Shipped file: first 1,000 alphabetic surnames, for the e-mail builder.
# A 50,000-name rerun needs the full Census CSV via E1_CENSUS (hash checked below).
CENSUS = Path(os.environ.get('E1_CENSUS', HERE / 'data' / 'surnames_head1000.csv'))
FULL_CENSUS_SHA = '6b4933178060b4e5ac8dd9a611ec15472d35eab98fe9027474bc5ccc5b7a8708'
FONT_RECEIPTS = HERE / 'data' / 'fonts.json'

@lru_cache(maxsize=None)
def checked_font_path(name):
    path = Path(FONTS[name][0])
    if folder := os.environ.get('E1_FONT_DIR'):
        path = Path(folder) / path.name
    expect = json.loads(FONT_RECEIPTS.read_text())[name]['sha256']
    if not path.is_file() or sha256(path) != expect:
        raise SystemExit(f'Exact study font missing or SHA-256 mismatch: {name} at {path}')
    return path

def check_render_inputs():
    import PIL
    if PIL.__version__ != '12.3.0' or not features.check('raqm'):
        raise SystemExit('The study renderer requires Pillow 12.3.0 with RAQM. The one-command reproduce path does not render.')
    for name in FONTS:
        checked_font_path(name)
    if not CENSUS.is_file() or sha256(CENSUS) != FULL_CENSUS_SHA:
        raise SystemExit(
            f'Full Census CSV missing or SHA-256 mismatch: {CENSUS}. '
            f'Expected {FULL_CENSUS_SHA}. The shipped surnames_head1000.csv is only the e-mail head.')
    print('Pillow', PIL.__version__, *(f'{x}={features.version(x)}' for x in
          ('raqm', 'harfbuzz', 'fribidi', 'freetype2')), flush=True)

FONTS={
 'DejaVuSans':('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','Bitstream Vera / DejaVu licence (free, redistributable)',None),
 'DejaVuSerif':('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf','Bitstream Vera / DejaVu licence (free, redistributable)',None),
 'LiberationSans':('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf','SIL OFL 1.1',None),
 'LiberationSerif':('/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf','SIL OFL 1.1',None),
 'NotoSans':('/usr/share/fonts/truetype/sand-box/google/Noto Sans/NotoSans-VariableFont_wdth,wght.ttf','SIL OFL 1.1',b'Regular'),
 'LiberationMono':('/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf','SIL OFL 1.1',None),
}
SIZES=[12,16,24]; PAD=1; GRIDS=[1,8,16,32,64]
PEN_X=(64,1024); PEN_Y=(64,960)
_fc={}
def font(name,size):
    k=(name,size)
    if k not in _fc:
        _,_,var=FONTS[name];f=ImageFont.truetype(str(checked_font_path(name)),size,layout_engine=ImageFont.Layout.RAQM)
        if var:f.set_variation_by_name(var)
        _fc[k]=f
    return _fc[k]
def sha256(p):return hashlib.sha256(open(p,'rb').read()).hexdigest()

# ---------------------------------------------------------------- dictionaries
def _cache(name,fn):
    p=os.path.join(CACHE,name+'.pkl')
    if os.path.exists(p):return pickle.load(open(p,'rb'))
    CACHE.mkdir(parents=True, exist_ok=True)
    d=fn();pickle.dump(d,open(p,'wb'));return d
def _finish(strings,prior,mult,meta):
    prior=np.asarray(prior,float);mult=np.asarray(mult,float)
    prior=prior/np.sum(prior*mult)   # per-string probability
    L=np.array([len(s) for s in strings])
    return dict(strings=list(strings),p=prior,m=mult,length=L,meta=meta)
def census(n):
    rows=[r for r in csv.DictReader(open(CENSUS)) if r['name'].isalpha()][:n]
    return [r['name'].title() for r in rows],[int(r['count']) for r in rows]
def dict_surnames():
    s,c=census(50000)
    return _finish(s,c,np.ones(len(s)),dict(source='US Census Bureau 2010 surnames, top 50,000 alphabetic (public domain, US Gov work)',url='https://www2.census.gov/topics/genealogy/2010surnames/names.zip',prior='proportional to 2010 count',sha256_csv=sha256(CENSUS)))
def dict_words():
    from wordfreq import top_n_list,word_frequency
    w=[x for x in top_n_list('en',60000) if x.isalpha() and x.isascii()][:20000]
    return _finish(w,[word_frequency(x,'en') for x in w],np.ones(len(w)),dict(source='wordfreq 3.1.1 English, top 20,000 alphabetic ASCII words',licence='wordfreq code Apache-2.0; data CC BY-SA 4.0 (Speer et al.)',prior='wordfreq frequency'))
def dict_digits():
    s=[];m=[];p=[]
    for L in range(4,11):
        for a in range(10):
            for b in range(10):
                s.append(f'{a}'+'0'*(L-2)+f'{b}');m.append(10**(L-2));p.append((1/7)/10**L)
    return _finish(s,p,m,dict(source='synthetic digit strings (phone/ID-like), length uniform 4-10, digits uniform',note='entries are classes (length, first digit, last digit) with multiplicity 10^(L-2); exact for tabular-digit fonts; kerning fonts handled by calibrated tolerance'))
MONTHS=['January','February','March','April','May','June','July','August','September','October','November','December']
def dict_dates():
    s=[];d=datetime.date(1940,1,1);e=datetime.date(2025,12,31)
    while d<=e:
        s.append(f'{d.day:02d}/{d.month:02d}/{d.year}');s.append(f'{d.day} {MONTHS[d.month-1]} {d.year}');d+=datetime.timedelta(1)
    return _finish(s,np.ones(len(s)),np.ones(len(s)),dict(source='all calendar dates 1940-01-01..2025-12-31 in DD/MM/YYYY and "D Month YYYY" (uniform prior)'))
DOMAINS=[('gmail.com',.45),('outlook.com',.2),('yahoo.com',.15),('hotmail.com',.1),('icloud.com',.1)]
def dict_emails():
    sn,c=census(1000);tot=sum(c);s=[];p=[]
    for n,cn in zip(sn,c):
        n=n.lower()
        for loc,pl in [(n,.25)]+[(f'{ch}.{n}',.75/26) for ch in 'abcdefghijklmnopqrstuvwxyz']:
            for dom,pd in DOMAINS:s.append(f'{loc}@{dom}');p.append(cn/tot*pl*pd)
    return _finish(s,p,np.ones(len(s)),dict(source='synthetic emails: top-1,000 Census surnames x {surname, initial.surname} x 5 webmail domains',prior='surname count x pattern (0.25 bare / 0.75 uniform initials) x domain share (.45/.2/.15/.1/.1)'))
DICTS={'surnames':dict_surnames,'words':dict_words,'digits':dict_digits,'dates':dict_dates,'emails':dict_emails}
def get_dict(name):return _cache('dict_'+name,DICTS[name])

def geometry(dname,fname,size):
    def f():
        D=get_dict(dname);ft=font(fname,size)
        return np.array([ft.getbbox(s,anchor='ls') for s in D['strings']],dtype=np.int32)
    return _cache(f'geom_{dname}_{fname}_{size}',f)

def sample_targets(D,n,rng):
    """prior-weighted sample; returns entry indices and the actual strings (digits: random middle digits)."""
    w=D['p']*D['m'];idx=rng.choice(len(w),size=n,p=w/w.sum())
    strs=[]
    for i in idx:
        s=D['strings'][i]
        if D['meta']['source'].startswith('synthetic digit'):
            s=s[0]+''.join(str(rng.integers(10)) for _ in range(len(s)-2))+s[-1]
        strs.append(s)
    return idx,strs

# ---------------------------------------------------------------- observation (what the redactor's tight box is)
def ink_box(fname,size,s,cond,rng):
    """returns ink bbox (l,t,r,b) relative to pen at baseline, as the redactor would find it."""
    ft=font(fname,size)
    if cond=='clean':return ft.getbbox(s,anchor='ls')
    l,t,r,b=ft.getbbox(s,anchor='ls');M=24;W=r-l+2*M;H=b-t+2*M;ox=M-l;oy=M-t
    im=Image.new('L',(W,H),255);ImageDraw.Draw(im).text((ox,oy),s,font=ft,fill=0,anchor='ls')
    if cond=='scan':
        ang=float(rng.uniform(-0.5,0.5))
        im=im.rotate(ang,resample=Image.BICUBIC,center=(ox,oy),fillcolor=255)
        im=im.filter(ImageFilter.GaussianBlur(0.8))
        a=np.asarray(im,np.float32)+rng.normal(0,10,(H,W)).astype(np.float32)
        im=Image.fromarray(np.clip(a,0,255).astype(np.uint8))
        q=85
    else:q=75
    buf=io.BytesIO();im.save(buf,'JPEG',quality=q);im=Image.open(io.BytesIO(buf.getvalue())).convert('L')
    a=np.asarray(im)<128;ys,xs=np.nonzero(a)
    if len(xs)==0:return ft.getbbox(s,anchor='ls')
    return (int(xs.min())-ox,int(ys.min())-oy,int(xs.max())+1-ox,int(ys.max())+1-oy)

# ---------------------------------------------------------------- defences = transforms of offsets
def bucket_transform(G,fname,size,B=128):
    """D2 fixed-width padding: width rounded up to a multiple of B, vertical extent = full font line (ascent..descent)."""
    asc,desc=font(fname,size).getmetrics()
    G=G.copy();w=G[:,2]-G[:,0]+2*PAD;W=-(-w//B)*B
    G[:,2]=G[:,0]+W-2*PAD;G[:,1]=-asc;G[:,3]=desc;return G

def snap(x0,x1,g):return (x0//g)*g,-(-x1//g)*g

# ---------------------------------------------------------------- attack evaluation
class Cell:
    """Pre-computes per-candidate edge offset ranges for a (geometry, tolerance, jitter) setting."""
    def __init__(s,G,tol,J):
        l,t,r,b=[G[:,i].astype(np.int64) for i in range(4)]
        (dl0,dl1),(dt0,dt1),(dr0,dr1),(db0,db1)=tol
        s.Llo=l-PAD+dl0-J;s.Lhi=l-PAD+dl1;s.Rlo=r+PAD+dr0;s.Rhi=r+PAD+dr1+J
        s.Tlo=t-PAD+dt0-J;s.Thi=t-PAD+dt1;s.Blo=b+PAD+db0;s.Bhi=b+PAD+db1+J
    def feasible(s,obs,shifts,g,attacker):
        """obs: list of (X0,X1,Y0,Y1) per copy; shifts: list of (sx,sy) pen offset of each copy relative to copy 0
        attacker A1: pen x of copy 0 known (passed as shifts[0]=(px,py) absolute); A2/A3: pen x unknown, baseline known."""
        F=None;lo=None;hi=None
        for (X0,X1,Y0,Y1),(sx,sy) in zip(obs,shifts):
            fy=(sy+s.Thi>=Y0)&(sy+s.Tlo<=Y0+g-1)&(sy+s.Bhi>=Y1-g+1)&(sy+s.Blo<=Y1)
            F=fy if F is None else F&fy
            if attacker=='A1':
                F&=(sx+s.Lhi>=X0)&(sx+s.Llo<=X0+g-1)&(sx+s.Rhi>=X1-g+1)&(sx+s.Rlo<=X1)
            else:
                a=np.maximum(X0-s.Lhi,X1-g+1-s.Rhi)-sx;b=np.minimum(X0+g-1-s.Llo,X1-s.Rlo)-sx
                lo=a if lo is None else np.maximum(lo,a);hi=b if hi is None else np.minimum(hi,b)
        if attacker!='A1':F&=lo<=hi
        return F

def metrics(D,F,ti,lens_true,logp):
    """D dict; F feasible mask; ti index of truth entry. Returns dict of per-target metrics."""
    p=D['p'];m=D['m'];truth_in=bool(F[ti])
    if not F.any():F=np.ones_like(F)
    pf=p[F];mf=m[F];w=pf*mf;M=w.sum()
    H=math.log2(M)-float((w*logp[F]).sum())/M
    pt=p[ti]
    gt=float(mf[pf>pt].sum());eq=float(mf[pf==pt].sum()) if truth_in else 0.0
    def hit(k):return 0.0 if not truth_in else min(1.0,max(0.0,(k-gt)/eq))
    lm=np.bincount(D['length'][F],weights=w);lc=int(np.argmax(lm))
    return dict(hit1=hit(1),hit10=hit(10),len_ok=float(lc==lens_true),resid_bits=H,log10_cands=math.log10(mf.sum()),truth_in=float(truth_in))

def wilson(k,n,z=1.96):
    if n==0:return (float('nan'),)*2
    ph=k/n;d=1+z*z/n;c=(ph+z*z/(2*n))/d;h=z*math.sqrt(ph*(1-ph)/n+z*z/(4*n*n))/d;return c-h,c+h
def boot_ci(x,rng,B=2000):
    x=np.asarray(x);i=rng.integers(0,len(x),(B,len(x)));mu=x[i].mean(1);return float(np.percentile(mu,2.5)),float(np.percentile(mu,97.5))

def tight_box(box,px,py,J,rng):
    """redactor's pre-snap box from ink bbox offsets; J>0 adds independent uniform 0..J px jitter per side (D1)."""
    l,t,r,b=box
    j=rng.integers(0,J+1,4) if J>0 else (0,0,0,0)
    return (px+l-PAD-int(j[0]),py+t-PAD-int(j[1]),px+r+PAD+int(j[2]),py+b+PAD+int(j[3]))
def snapped(tb,g):
    x0,y0,x1,y1=tb;X0,X1=snap(x0,x1,g);Y0,Y1=snap(y0,y1,g);return (X0,X1,Y0,Y1)
def bucket_box(box,fname,size,B=128):
    return tuple(bucket_transform(np.array([box],dtype=np.int64),fname,size,B)[0])
